"""Ingest step statuses: fresh / replayed / stale / unavailable (D-62, D-68). No network: fake clients."""

import shutil
from datetime import UTC, datetime

from retention.client.http import FetchResult, PayloadSummary, SourceError
from retention.config import load_settings
from retention.domain.source_status import SourceState
from retention.pipeline.ingest import run_ingest
from retention.repository.raw_repository import RawRepository

_clock = iter(datetime(2026, 9, 27, 0, 0, s, tzinfo=UTC) for s in range(60))


class FakeClient:
    """Stands in for Eurostat/World Bank. Each fetch gets a later timestamp, like a real fetch."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def fetch(self, indicator):
        if self.fail:
            raise SourceError("HTTP 503: service unavailable", retry_count=3)
        result = FetchResult("https://fake", 200, b'{"ok": true}', 1, next(_clock))
        return result, PayloadSummary(10, "2025-12")


def setup(tmp_path):
    """Settings pointing at an empty temp raw folder that contains only a copy of the HR pack."""
    settings = load_settings()
    raw = tmp_path / "raw"
    shutil.copytree(settings.paths.hr_source, raw / "hr")
    settings.paths.raw = raw
    return settings, RawRepository(raw)


def by_indicator(statuses):
    return {s.indicator: s for s in statuses}


def test_refresh_success_saves_snapshot_and_is_fresh(tmp_path):
    settings, repo = setup(tmp_path)
    clients = {"eurostat": FakeClient(), "worldbank": FakeClient()}
    statuses = by_indicator(run_ingest(settings, "refresh", repo, clients))
    s = statuses["unemployment"]
    assert s.status == SourceState.FRESH and s.source_period == "2025-12" and s.retry_count == 1
    assert repo.latest_snapshot("eurostat", "une_rt_m") is not None
    assert statuses["hr_pack"].status == SourceState.REPLAYED


def test_refresh_failure_with_previous_snapshot_is_stale(tmp_path):
    settings, repo = setup(tmp_path)
    run_ingest(settings, "refresh", repo, {"eurostat": FakeClient(), "worldbank": FakeClient()})
    statuses = by_indicator(
        run_ingest(settings, "refresh", repo, {"eurostat": FakeClient(fail=True), "worldbank": FakeClient()})
    )
    s = statuses["unemployment"]
    assert s.status == SourceState.STALE  # never shown as fresh
    assert "503" in s.error and s.retry_count == 3
    assert s.snapshot is not None  # the last good snapshot is still used


def test_refresh_failure_without_snapshot_is_unavailable(tmp_path):
    settings, repo = setup(tmp_path)
    clients = {"eurostat": FakeClient(fail=True), "worldbank": FakeClient()}
    statuses = by_indicator(run_ingest(settings, "refresh", repo, clients))
    assert statuses["unemployment"].status == SourceState.UNAVAILABLE
    assert statuses["gdp_growth"].status == SourceState.FRESH  # other sources continue


def test_offline_uses_saved_snapshot_as_replayed(tmp_path):
    settings, repo = setup(tmp_path)
    run_ingest(settings, "refresh", repo, {"eurostat": FakeClient(), "worldbank": FakeClient()})
    statuses = by_indicator(run_ingest(settings, "offline", repo))
    s = statuses["unemployment"]
    assert s.status == SourceState.REPLAYED
    assert s.loaded_at.startswith("2026-09-27T00:00:")  # the snapshot's original fetch time


def test_offline_without_snapshot_is_unavailable_with_hint(tmp_path):
    settings, repo = setup(tmp_path)
    s = by_indicator(run_ingest(settings, "offline", repo))["unemployment"]
    assert s.status == SourceState.UNAVAILABLE and "--refresh" in s.error
