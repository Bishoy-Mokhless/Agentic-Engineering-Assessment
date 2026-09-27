"""run_summary.json: one record per pipeline run (D-49, D-62).

Read later by /api/health and the dashboard's Trust view.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from retention.domain.source_status import SourceStatus


def new_run_id(started_at: datetime) -> str:
    """e.g. 'run-20260927T120052Z' - unique per run, sortable by time."""
    return started_at.strftime("run-%Y%m%dT%H%M%SZ")


def write_run_summary(
    path: Path,
    run_id: str,
    mode: str,
    started_at: datetime,
    finished_at: datetime,
    sources: list[SourceStatus],
) -> None:
    """Write data/curated/run_summary.json (replaces the previous run's file)."""
    # 1. Build the summary as plain dicts/lists (JSON-friendly).
    source_records = []
    for source in sources:
        source_records.append(source.to_dict())

    summary = {
        "run_id": run_id,
        "mode": mode,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "sources": source_records,
    }

    # 2. Write to a temp file, then swap it in, so readers never see a half-written file.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
