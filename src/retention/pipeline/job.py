"""The pipeline job: runs the steps in order (ingest -> curate -> metrics -> integrate -> analyse).

Spring analogy: a Spring Batch Job. Only the ingest step exists so far (Step 2).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from retention.config import Settings
from retention.domain.source_status import SourceState, SourceStatus
from retention.pipeline.ingest import Mode, run_ingest
from retention.pipeline.run_summary import new_run_id, write_run_summary

log = logging.getLogger(__name__)


def run_pipeline(settings: Settings, mode: Mode) -> int:
    """Run the pipeline and return a process exit code (0 = success, 1 = cannot continue)."""
    started_at = datetime.now(UTC)
    run_id = new_run_id(started_at)
    log.info("Run %s started (mode: %s)", run_id, mode)

    # Step: ingest
    statuses = run_ingest(settings, mode)
    _log_status_table(statuses)

    # Record the run (lineage + source status) for the API / dashboard Trust view.
    summary_path = settings.paths.analytical.parent / "run_summary.json"
    write_run_summary(summary_path, run_id, mode, started_at, datetime.now(UTC), statuses)

    # Decide whether the run can continue.
    unavailable = []
    has_stale = False
    for status in statuses:
        if status.status == SourceState.UNAVAILABLE:
            unavailable.append(status.indicator)
        if status.status == SourceState.STALE:
            has_stale = True

    if unavailable:
        log.error("Cannot continue: no usable data for %s", ", ".join(unavailable))
        return 1
    if has_stale:
        log.warning("Some sources are STALE (last good snapshot used). See run_summary.json.")

    log.info("Run %s finished.", run_id)
    return 0


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
