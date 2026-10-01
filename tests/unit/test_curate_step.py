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
    settings.analysis.bootstrap_iterations = 50  # fast tests; the CI width is not asserted here
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


def test_metrics_step_reproduces_the_agreed_headline_numbers(settings):
    """Step 4 golden numbers (same values as the independent Round 13 preview)."""
    assert run_pipeline(settings, "offline") == 0
    analytical = settings.paths.analytical
    cohorts = duckdb.sql(
        f"SELECT objective_id, retained, n, status FROM '{analytical / 'retention_cohorts.parquet'}' "
        "WHERE variant = 'primary' AND scope = 'company' AND grain = 'period' ORDER BY objective_id"
    ).fetchall()
    assert cohorts == [("NEW_HIRE_6M", 1579, 1804, "inconclusive"), ("SENIOR_HIRE_12M", 208, 266, "not_met")]

    turnover = duckdb.sql(
        f"SELECT year(month_end), regretted_exits, round(avg_headcount), status "
        f"FROM '{analytical / 'regretted_turnover.parquet'}' "
        "WHERE variant = 'primary' AND scope = 'company' AND is_year_end ORDER BY 1"
    ).fetchall()
    assert turnover == [
        (2021, 23, 523, "met"),
        (2022, 32, 846, "met"),
        (2023, 38, 1131, "met"),
        (2024, 46, 1395, "met"),
        (2025, 82, 1603, "met"),
    ]
    assert (analytical / "_build.json").exists()


def test_association_step_runs_the_agreed_tests_without_future_information(settings):
    """Step 5: 12 formal tests (3 objectives x 4 indicators), none clearly associated (non-finding)."""
    assert run_pipeline(settings, "offline") == 0
    analytical = settings.paths.analytical

    aligned = analytical / "aligned_observations.parquet"
    future = duckdb.sql(f"SELECT count(*) FROM '{aligned}' WHERE available_from > anchor_date").fetchone()[0]
    assert future == 0

    formal = duckdb.sql(
        f"SELECT objective_id, indicator, round(rho, 2), n_rows, result "
        f"FROM '{analytical / 'association_results.parquet'}' "
        "WHERE is_formal ORDER BY objective_id, indicator"
    ).fetchall()
    assert len(formal) == 12
    new_hire = {row[1]: (row[2], row[3]) for row in formal if row[0] == "NEW_HIRE_6M"}
    assert new_hire == {
        "gdp_growth": (0.0, 90),  # IE excluded (D-59)
        "inflation": (-0.12, 108),
        "job_vacancy": (-0.02, 108),
        "unemployment": (-0.1, 108),
    }
    for row in formal:
        assert row[4] == "The analysis did not show a clear association in this sample."


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

    first_analytical = read_json(settings.paths.analytical / "_build.json")

    run_pipeline(settings, "offline")
    second = read_json(settings.paths.canonical / "_build.json")
    second_source = read_json(settings.paths.source_shaped / "_build.json")
    second_analytical = read_json(settings.paths.analytical / "_build.json")

    assert first["tables"] == second["tables"]  # same rows AND same sha256 per file
    assert first_source["tables"] == second_source["tables"]
    assert first_analytical["tables"] == second_analytical["tables"]


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


# --- F-01 (D-96): a refreshed snapshot becomes "latest" only after the whole run succeeded ---


class ReplayAsFreshClient:
    """Answers a refresh with the bytes of the current snapshot, as if the provider had just sent them."""

    def __init__(self, raw_repo, provider, second):
        self.raw_repo, self.provider, self.second = raw_repo, provider, second

    def fetch(self, indicator):
        from datetime import UTC, datetime

        from retention.client.http import FetchResult, PayloadSummary

        snapshot = self.raw_repo.latest_snapshot(self.provider, indicator.dataset)
        meta = self.raw_repo.read_metadata(snapshot)
        fetched = datetime(2026, 10, 1, 0, 0, self.second, tzinfo=UTC)
        result = FetchResult("https://fake", 200, self.raw_repo.read_payload(snapshot), 0, fetched)
        return result, PayloadSummary(meta["observation_count"], meta["latest_source_period"])


def refresh_setup(settings, tmp_path, monkeypatch):
    """Copy the real raw folder to a temp folder and answer every fetch from it."""
    import shutil

    from retention.pipeline import ingest
    from retention.repository.raw_repository import RawRepository

    raw = tmp_path / "raw"
    shutil.copytree(settings.paths.raw, raw)
    settings.paths.raw = raw
    repo = RawRepository(raw)
    clients = {
        "eurostat": ReplayAsFreshClient(repo, "eurostat", 1),
        "worldbank": ReplayAsFreshClient(repo, "worldbank", 2),
    }
    monkeypatch.setattr(ingest, "build_clients", lambda _settings: clients)
    return raw


def latest_pointers(raw):
    return {p.parent.name: read_json(p)["snapshot"] for p in raw.glob("*/*/latest.json")}


def test_failed_refresh_run_keeps_latest_pointing_at_the_last_good_snapshot(settings, tmp_path, monkeypatch):
    raw = refresh_setup(settings, tmp_path, monkeypatch)
    before = latest_pointers(raw)

    def broken_curate(*args, **kwargs):
        raise CurationError("simulated: the new payload cannot be curated")

    monkeypatch.setattr(job, "run_curate", broken_curate)
    assert run_pipeline(settings, "refresh") == 1

    assert latest_pointers(raw) == before  # the next offline run still uses the last good data
    # the new download is kept as evidence
    assert (raw / "eurostat" / "une_rt_m" / "20261001T000001Z").is_dir()


def test_successful_refresh_run_promotes_the_new_snapshots(settings, tmp_path, monkeypatch):
    raw = refresh_setup(settings, tmp_path, monkeypatch)
    assert run_pipeline(settings, "refresh") == 0
    pointers = latest_pointers(raw)
    assert pointers["une_rt_m"] == "20261001T000001Z"
    assert pointers["NY.GDP.MKTP.KD.ZG"] == "20261001T000002Z"


def test_unexpected_error_still_records_a_failed_run(settings, monkeypatch):
    """F-03 (D-98): a bug outside the expected errors is still written to run_summary.json."""
    run_pipeline(settings, "offline")

    def buggy_metrics(*args, **kwargs):
        raise RuntimeError("simulated programming bug")

    monkeypatch.setattr(job, "run_metrics", buggy_metrics)
    with pytest.raises(RuntimeError):
        run_pipeline(settings, "offline")

    summary = read_json(settings.paths.canonical.parent / "run_summary.json")
    assert summary["outcome"] == "failed" and "simulated programming bug" in summary["error"]
