"""The whole offline pipeline on the real replay data, writing into a temp folder.

Checks the reconciliation numbers, deterministic reruns (D-74) and that a failed run
keeps the previous curated outputs (D-48). No network: offline mode only.
"""

import json

import duckdb
import pytest

from retention.config import load_settings
from retention.domain.errors import CurationError
from retention.pipeline import job
from retention.pipeline.job import run_pipeline


@pytest.fixture
def settings(tmp_path):
    """Real settings and raw data, but every curated output goes to a temp folder."""
    settings = load_settings()
    settings.paths.source_shaped = tmp_path / "curated" / "source_shaped"
    settings.paths.canonical = tmp_path / "curated" / "canonical"
    settings.paths.analytical = tmp_path / "curated" / "analytical"
    settings.paths.build_tmp = tmp_path / ".tmp"
    return settings


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_offline_run_builds_both_layers_with_reconciled_counts(settings):
    assert run_pipeline(settings, "offline") == 0

    report = read_json(settings.paths.canonical / "quality_report.json")
    assert report["hr"]["reconciliation"] == {
        "rows_in_file": 2407,
        "duplicate_rows_removed": 7,
        "employees_out": 2400,
        "balanced": True,
    }
    assert report["hr"]["metric_status"] == {"INCLUDED": 2378, "QUARANTINED": 12, "EXCLUDED": 10}

    flags = {line["flag"]: line["rows"] for line in report["hr"]["flags"]}
    assert flags["UNVERIFIED_EXIT"] == 12 and flags["REGRETTED_UNKNOWN"] == 2
    assert report["hr"]["regretted_exit"] == {
        "FALSE": 525,
        "NOT_APPLICABLE": 1621,
        "TRUE": 240,
        "UNKNOWN": 14,
    }

    for layer in [settings.paths.source_shaped, settings.paths.canonical]:
        assert (layer / "_build.json").exists()
    summary = read_json(settings.paths.canonical.parent / "run_summary.json")
    assert summary["outcome"] == "succeeded" and summary["steps"]["curate"]["employees"] == 2400


def test_canonical_tables_are_readable_with_sql_and_typed(settings):
    run_pipeline(settings, "offline")
    employees = settings.paths.canonical / "employees.parquet"
    indicators = settings.paths.canonical / "indicators.parquet"

    types = {}
    for column in duckdb.sql(f"DESCRIBE SELECT * FROM '{employees}'").fetchall():
        types[column[0]] = column[1]  # (name, type, ...)
    assert types["hire_date"] == "DATE" and types["termination_date"] == "DATE"

    greece_vacancy = duckdb.sql(
        f"SELECT source_country_code, value FROM '{indicators}' "
        "WHERE indicator = 'job_vacancy' AND country_code = 'GR' AND period = '2022-Q3'"
    ).fetchall()
    assert greece_vacancy == [("EL", 1.1)]  # EL mapped to GR, value unchanged

    provisional = duckdb.sql(f"SELECT count(*) FROM '{indicators}' WHERE obs_status = 'p'").fetchone()[0]
    assert provisional == 14  # publication status preserved


def test_rerun_produces_byte_identical_tables(settings):
    run_pipeline(settings, "offline")
    first = read_json(settings.paths.canonical / "_build.json")
    first_source = read_json(settings.paths.source_shaped / "_build.json")

    run_pipeline(settings, "offline")
    second = read_json(settings.paths.canonical / "_build.json")
    second_source = read_json(settings.paths.source_shaped / "_build.json")

    assert first["tables"] == second["tables"]  # same rows AND same sha256 per file
    assert first_source["tables"] == second_source["tables"]


def test_failed_run_keeps_previous_outputs(settings, monkeypatch):
    run_pipeline(settings, "offline")
    before = read_json(settings.paths.canonical / "_build.json")

    def broken_curate(*args, **kwargs):
        raise CurationError("simulated failure in the curate step")

    monkeypatch.setattr(job, "run_curate", broken_curate)
    assert run_pipeline(settings, "offline") == 1

    after = read_json(settings.paths.canonical / "_build.json")
    assert after == before  # the previous build is untouched
    summary = read_json(settings.paths.canonical.parent / "run_summary.json")
    assert summary["outcome"] == "failed" and "simulated failure" in summary["error"]
    assert list(settings.paths.build_tmp.iterdir()) == []  # the half-built folder was removed
