"""Curate step: raw -> source-shaped -> canonical (D-41, D-61, D-71..D-74).

Spring analogy: one Step of a Spring Batch Job; it only orchestrates.
The rules are in service/, the storage in repository/, the contracts in domain/schemas.py.

Order:
    1. HR pack      -> source_shaped/hr_events, hr_objectives
                    -> canonical/employees, quality_issues, objectives
    2. indicators   -> source_shaped/<provider>_<dataset>   (one per indicator)
                    -> canonical/indicators                  (all indicators, one long table)
    3. quality/coverage report + one _build.json per layer (lineage)
Every table passes its schema contract before it is written.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from retention.client import eurostat, worldbank
from retention.client.hr_files import MANIFEST_NAME
from retention.config import Settings
from retention.domain import schemas
from retention.domain.errors import CurationError
from retention.domain.source_status import SourceStatus
from retention.pipeline.lineage import build_record
from retention.repository.curated_repository import CuratedRepository, TableInfo
from retention.repository.mappings import career_level_lookup, country_lookup
from retention.repository.raw_repository import RawRepository
from retention.service.hr_curation import curate_employees, curate_objectives, source_shaped_events
from retention.service.indicator_curation import (
    SourceLineage,
    combine_indicators,
    curate_indicator,
    provider_last_updated,
)
from retention.service.indicator_parsing import flatten_eurostat, flatten_worldbank
from retention.service.quality_report import build_quality_report

log = logging.getLogger(__name__)

EVENTS_FILE = "employee_lifecycle_events.csv"
OBJECTIVES_FILE = "retention_objectives.csv"


def run_curate(
    settings: Settings,
    statuses: list[SourceStatus],
    raw_repo: RawRepository,
    curated_repo: CuratedRepository,
    build: Path,
    run_id: str,
    built_at: datetime,
) -> dict:
    """Build the source-shaped and canonical layers into `build`. Returns a summary for run_summary.json."""
    written = {"source_shaped": {}, "canonical": {}}  # layer -> table name -> TableInfo (for _build.json)
    inputs = []

    def save(layer: str, name: str, table) -> None:
        """Write one table into the build folder and remember its row count + sha256."""
        written[layer][name] = curated_repo.write_table(build, layer, name, table)

    # Which raw snapshot each source uses (decided by the ingest step), e.g. "unemployment" -> status
    status_by_source = {}
    for status in statuses:
        status_by_source[status.indicator] = status

    # 1. HR pack -------------------------------------------------------------------------------
    hr_status = status_by_source["hr_pack"]
    hr_snapshot = raw_repo.root / hr_status.snapshot
    inputs.extend(_hr_inputs(hr_snapshot, hr_status.snapshot))

    events = source_shaped_events(raw_repo.read_csv_as_text(hr_snapshot, EVENTS_FILE), hr_status.snapshot)
    schemas.check_contract(schemas.HR_EVENTS_SOURCE, events, "source-shaped hr_events")
    save("source_shaped", "hr_events", events)

    objectives_source = raw_repo.read_csv_as_text(hr_snapshot, OBJECTIVES_FILE)
    objectives_source["source_snapshot"] = hr_status.snapshot
    schemas.check_contract(schemas.OBJECTIVES_SOURCE, objectives_source, "source-shaped hr_objectives")
    save("source_shaped", "hr_objectives", objectives_source)

    mappings = settings.paths.mappings
    hr = curate_employees(events, country_lookup(mappings, "hr"), career_level_lookup(mappings))
    schemas.check_contract(schemas.employees_schema(settings.countries), hr.employees, "canonical employees")
    schemas.check_contract(schemas.QUALITY_ISSUES, hr.issues, "canonical quality_issues")
    save("canonical", "employees", hr.employees)
    save("canonical", "quality_issues", hr.issues)

    objectives = curate_objectives(objectives_source)
    schemas.check_contract(schemas.OBJECTIVES, objectives, "canonical objectives")
    save("canonical", "objectives", objectives)

    log.info(
        "Curate HR: %d rows -> %d repeated rows removed -> %d employees (%s)",
        hr.rows_in,
        hr.duplicates_removed,
        len(hr.employees),
        _status_text(hr.employees),
    )

    # 2. Indicators ----------------------------------------------------------------------------
    indicator_results = {}
    indicator_tables = []
    for name, indicator in settings.indicators.items():
        status = status_by_source[name]
        snapshot = raw_repo.root / status.snapshot
        metadata = raw_repo.read_metadata(snapshot)
        inputs.append({"source": name, "snapshot": status.snapshot, "sha256": metadata.get("sha256")})

        # 2a. Raw payload -> source-shaped table (provider's own codes).
        body = raw_repo.read_payload(snapshot)
        if indicator.provider == "eurostat":
            data = eurostat.parse_payload(body)
            source = flatten_eurostat(data)
            schemas.check_contract(schemas.EUROSTAT_SOURCE, source, f"source-shaped {name}")
        else:
            data = worldbank.parse_payload(body)
            source = flatten_worldbank(data)
            schemas.check_contract(schemas.WORLDBANK_SOURCE, source, f"source-shaped {name}")
        source_name = f"{indicator.provider}_{indicator.dataset}"
        save("source_shaped", source_name, source)

        # 2b. Source-shaped -> canonical rows.
        lineage = SourceLineage(
            snapshot=status.snapshot,
            loaded_at=status.loaded_at,
            source_last_updated=provider_last_updated(indicator.provider, data),
        )
        codes = country_lookup(mappings, indicator.provider)
        result = curate_indicator(source, name, indicator, codes, lineage)
        indicator_results[name] = result
        indicator_tables.append(result.rows)
        log.info(
            "Curate %s: %d source rows -> %d canonical rows (%d without value)",
            name,
            result.source_rows,
            len(result.rows),
            result.missing_values_dropped,
        )

    indicators = combine_indicators(indicator_tables)
    indicator_names = list(settings.indicators)
    schemas.check_contract(
        schemas.indicators_schema(settings.countries, indicator_names), indicators, "canonical indicators"
    )
    save("canonical", "indicators", indicators)

    # 3. Quality/coverage report and lineage files ---------------------------------------------
    report = build_quality_report(hr, indicator_results, indicators)
    curated_repo.write_json(build, "canonical", "quality_report", report)

    for layer in ["source_shaped", "canonical"]:
        curated_repo.write_json(
            build, layer, "_build", build_record(layer, run_id, built_at, inputs, written[layer])
        )

    return {
        "hr_rows_in": hr.rows_in,
        "duplicate_rows_removed": hr.duplicates_removed,
        "employees": len(hr.employees),
        "metric_status": report["hr"]["metric_status"],
        "indicator_rows": len(indicators),
        "tables": _row_counts(written),
    }


def _hr_inputs(snapshot: Path, snapshot_ref: str) -> list[dict]:
    """One lineage entry per delivered HR file, with the checksum from the manifest."""
    manifest_path = snapshot / MANIFEST_NAME
    if not manifest_path.exists():
        raise CurationError(f"HR manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = []
    for entry in manifest["files"]:
        inputs.append(
            {"source": "hr", "snapshot": f"{snapshot_ref}/{entry['name']}", "sha256": entry["sha256"]}
        )
    return inputs


def _row_counts(written: dict[str, dict[str, TableInfo]]) -> dict[str, dict[str, int]]:
    counts = {}
    for layer in written:
        counts[layer] = {}
        for name in sorted(written[layer]):
            counts[layer][name] = written[layer][name].rows
    return counts


def _status_text(employees) -> str:
    """e.g. "2378 INCLUDED, 12 QUARANTINED, 10 EXCLUDED"."""
    counts = employees["metric_status"].value_counts()
    parts = []
    for status in ["INCLUDED", "QUARANTINED", "EXCLUDED"]:
        parts.append(f"{int(counts.get(status, 0))} {status}")
    return ", ".join(parts)
