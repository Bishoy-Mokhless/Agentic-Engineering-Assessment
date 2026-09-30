"""The pipeline job: runs the steps in order (ingest -> curate -> metrics -> integrate -> analyse).

Steps: ingest (Step 2), curate (Step 3), metrics (Step 4), analyse (Step 5).

Curated outputs are built in data/.tmp/<run_id>/ and swapped into data/curated/ only when every
step succeeded (D-48). If a step fails, the previous curated outputs stay exactly as they were,
and run_summary.json records the failure.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from retention.client.http import SourceError
from retention.config import Settings
from retention.domain.errors import PipelineError
from retention.domain.source_status import SourceState, SourceStatus
from retention.pipeline.analyse import run_analysis
from retention.pipeline.curate import run_curate
from retention.pipeline.ingest import Mode, run_ingest
from retention.pipeline.lineage import build_record, table_inputs
from retention.pipeline.metrics import run_metrics
from retention.pipeline.run_summary import new_run_id, write_run_summary
from retention.repository.curated_repository import CuratedRepository
from retention.repository.raw_repository import RawRepository

log = logging.getLogger(__name__)


def run_pipeline(settings: Settings, mode: Mode) -> int:
    """Run the pipeline and return a process exit code (0 = success, 1 = cannot continue)."""
    started_at = datetime.now(UTC)
    run_id = new_run_id(started_at)
    log.info("Run %s started (mode: %s)", run_id, mode)
    steps = {}

    # Step: ingest
    raw_repo = RawRepository(settings.paths.raw)
    statuses = run_ingest(settings, mode, repo=raw_repo)
    _log_status_table(statuses)

    # Stop here if a source has no usable data at all.
    unavailable = []
    has_stale = False
    for status in statuses:
        if status.status == SourceState.UNAVAILABLE:
            unavailable.append(status.indicator)
        if status.status == SourceState.STALE:
            has_stale = True

    if unavailable:
        log.error("Cannot continue: no usable data for %s", ", ".join(unavailable))
        _finish(settings, run_id, mode, started_at, statuses, "failed", steps)
        return 1
    if has_stale:
        log.warning("Some sources are STALE (last good snapshot used). See run_summary.json.")

    # Steps that build curated layers: all inside one temporary build folder (D-48).
    curated_repo = CuratedRepository(
        layer_dirs={
            "source_shaped": settings.paths.source_shaped,
            "canonical": settings.paths.canonical,
            "analytical": settings.paths.analytical,
        },
        build_root=settings.paths.build_tmp,
    )
    build = curated_repo.start_build(run_id)
    try:
        # Step: curate (raw -> source_shaped + canonical)
        steps["curate"] = run_curate(settings, statuses, raw_repo, curated_repo, build, run_id, started_at)

        # Step: metrics (canonical -> analytical), reading the canonical tables of THIS build
        metric_tables = run_metrics(settings, curated_repo, build)
        steps["metrics"] = _row_counts(metric_tables)

        # Step: analyse (as-of join + association), reading canonical + metric tables of THIS build
        analysis_tables = run_analysis(settings, curated_repo, build)
        steps["analyse"] = _row_counts(analysis_tables)

        # Lineage for the analytical layer: its inputs are the canonical files (with sha256).
        analytical_tables = dict(metric_tables)
        analytical_tables.update(analysis_tables)
        canonical_record = curated_repo.read_json(build, "canonical", "_build")
        analytical_record = build_record(
            "analytical", run_id, started_at, table_inputs("canonical", canonical_record), analytical_tables
        )
        curated_repo.write_json(build, "analytical", "_build", analytical_record)

        # All steps succeeded: make the new outputs visible.
        curated_repo.publish(build)
    except (PipelineError, SourceError) as exc:
        curated_repo.discard(build)
        log.error("Run stopped: %s", exc)
        log.error("The previous curated outputs in data/curated were kept unchanged.")
        _finish(settings, run_id, mode, started_at, statuses, "failed", steps, error=str(exc))
        return 1
    except Exception:
        curated_repo.discard(build)  # unexpected bug: clean up, then show the full traceback
        raise

    _finish(settings, run_id, mode, started_at, statuses, "succeeded", steps)
    log.info("Run %s finished. Outputs in %s", run_id, settings.paths.canonical.parent)
    return 0


def _finish(
    settings: Settings,
    run_id: str,
    mode: str,
    started_at: datetime,
    statuses: list[SourceStatus],
    outcome: str,
    steps: dict,
    error: str | None = None,
) -> None:
    """Record the run (lineage, source status, step counts) for the API / dashboard Trust view."""
    summary_path = settings.paths.canonical.parent / "run_summary.json"
    write_run_summary(
        summary_path,
        run_id=run_id,
        mode=mode,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        sources=statuses,
        outcome=outcome,
        steps=steps,
        error=error,
    )


def _row_counts(tables: dict) -> dict[str, int]:
    """{"hire_outcomes": 2291, ...} for run_summary.json."""
    counts = {}
    for name in sorted(tables):
        counts[name] = tables[name].rows
    return counts


def _log_status_table(statuses: list[SourceStatus]) -> None:
    """Print one readable line per source."""
    for s in statuses:
        period = s.source_period or "-"
        snapshot = s.snapshot or "-"
        error = f"  ERROR: {s.error}" if s.error else ""
        log.info(
            "  %-9s %-13s %-11s period=%-10s snapshot=%s%s",
            s.provider,
            s.indicator,
            s.status,
            period,
            snapshot,
            error,
        )
