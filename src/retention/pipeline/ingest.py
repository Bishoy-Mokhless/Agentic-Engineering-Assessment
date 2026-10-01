"""Ingest step: bring every source into data/raw and report its status (D-47, D-48, D-62, D-68).

--refresh : fetch each indicator.
              success -> save a new snapshot                  -> status "fresh"
                         (latest.json moves only when the whole run succeeded, D-96)
              failure -> use the last good snapshot instead     -> status "stale"
                         (no snapshot at all)                   -> status "unavailable"
--offline : fetch nothing; use the latest saved snapshot       -> status "replayed"
                         (no snapshot at all)                   -> status "unavailable"
HR pack   : never fetched; its checksums are verified every run -> "replayed" (or "unavailable")
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC
from typing import Literal, Protocol

from retention.client.eurostat import EurostatClient
from retention.client.hr_files import HrIntegrityError, verify_hr_snapshot
from retention.client.http import FetchResult, PayloadSummary, SourceError, build_session
from retention.client.worldbank import WorldBankClient
from retention.config import IndicatorSettings, Settings
from retention.domain.source_status import SourceState, SourceStatus
from retention.repository.mappings import source_country_codes
from retention.repository.raw_repository import RawRepository

log = logging.getLogger(__name__)

Mode = Literal["offline", "refresh"]


class SourceClient(Protocol):
    """What every client must offer."""

    provider: str

    def fetch(self, indicator: IndicatorSettings) -> tuple[FetchResult, PayloadSummary]: ...


def build_clients(settings: Settings) -> dict[str, SourceClient]:
    """Create one client per provider, sharing a single HTTP session (with retries)."""
    session = build_session(settings.http)
    mappings_dir = settings.paths.mappings

    eurostat_geo = source_country_codes(mappings_dir, "eurostat", settings.countries)  # ["EL", "RO", ...]
    worldbank_iso3 = source_country_codes(mappings_dir, "worldbank", settings.countries)  # ["GRC", ...]

    eurostat = EurostatClient(session, settings.providers["eurostat"], settings.http, eurostat_geo)
    worldbank = WorldBankClient(
        session,
        settings.providers["worldbank"],
        settings.http,
        worldbank_iso3,
        end_year=settings.as_of_date.year,
    )
    return {"eurostat": eurostat, "worldbank": worldbank}


def run_ingest(
    settings: Settings,
    mode: Mode,
    repo: RawRepository | None = None,
    clients: dict[str, SourceClient] | None = None,
) -> list[SourceStatus]:
    """Process every indicator plus the HR pack, and return one status per source.

    `repo` and `clients` can be passed in by tests (fake clients, temp folder).
    """
    if repo is None:
        repo = RawRepository(settings.paths.raw)
    if mode == "refresh" and clients is None:
        clients = build_clients(settings)

    statuses = []
    for name, indicator in settings.indicators.items():
        if mode == "refresh":
            client = clients[indicator.provider]
            status = _refresh_one(repo, client, name, indicator)
        else:
            status = _replay_one(repo, name, indicator)
        statuses.append(status)

    statuses.append(_check_hr_pack(repo))
    return statuses


def _refresh_one(
    repo: RawRepository, client: SourceClient, name: str, indicator: IndicatorSettings
) -> SourceStatus:
    """Fetch one indicator and save it. On failure, fall back to the last good snapshot."""
    # 1. Try to fetch.
    try:
        result, summary = client.fetch(indicator)
    except SourceError as exc:
        log.warning("%s/%s: fetch failed: %s", indicator.provider, name, exc)
        return _use_latest_snapshot(
            repo, name, indicator, SourceState.STALE, error=str(exc), retry_count=exc.retry_count
        )

    # 2. Save the untouched response as a new dated snapshot, with metadata for lineage.
    fetched_at_utc = result.fetched_at.astimezone(UTC)
    fetched_at = fetched_at_utc.isoformat(timespec="seconds")  # e.g. "2026-09-27T12:00:52+00:00"
    snapshot_id = fetched_at_utc.strftime("%Y%m%dT%H%M%SZ")  # e.g. "20260927T120052Z"
    metadata = {
        "provider": indicator.provider,
        "indicator": name,
        "dataset": indicator.dataset,
        "url": result.url,
        "fetched_at": fetched_at,
        "http_status": result.http_status,
        "retry_count": result.retry_count,
        "bytes": len(result.body),
        "sha256": hashlib.sha256(result.body).hexdigest(),
        "observation_count": summary.observation_count,
        "latest_source_period": summary.latest_period,
    }
    path = repo.save_snapshot(
        indicator.provider, indicator.dataset, snapshot_id, result.body, metadata, promote=False
    )

    # 3. Report it as fresh.
    return SourceStatus(
        provider=indicator.provider,
        indicator=name,
        dataset=indicator.dataset,
        status=SourceState.FRESH,
        snapshot=repo.relative(path),
        source_period=summary.latest_period,
        loaded_at=fetched_at,
        retry_count=result.retry_count,
    )


def _replay_one(repo: RawRepository, name: str, indicator: IndicatorSettings) -> SourceStatus:
    """Offline mode: use the latest saved snapshot without fetching."""
    return _use_latest_snapshot(
        repo,
        name,
        indicator,
        SourceState.REPLAYED,
        error=None,
        retry_count=0,
        hint_if_missing="no saved snapshot - run `retention run --refresh` first",
    )


def _use_latest_snapshot(
    repo: RawRepository,
    name: str,
    indicator: IndicatorSettings,
    state: SourceState,
    error: str | None,
    retry_count: int,
    hint_if_missing: str | None = None,
) -> SourceStatus:
    """Report the source with the given state, using its latest saved snapshot.

    If there is no snapshot at all, the source is "unavailable".
    """
    snapshot = repo.latest_snapshot(indicator.provider, indicator.dataset)

    if snapshot is None:
        message = error if error else hint_if_missing
        return SourceStatus(
            provider=indicator.provider,
            indicator=name,
            dataset=indicator.dataset,
            status=SourceState.UNAVAILABLE,
            retry_count=retry_count,
            error=message,
        )

    metadata = repo.read_metadata(snapshot)
    return SourceStatus(
        provider=indicator.provider,
        indicator=name,
        dataset=indicator.dataset,
        status=state,
        snapshot=repo.relative(snapshot),
        source_period=metadata.get("latest_source_period"),
        loaded_at=metadata.get("fetched_at"),  # when the snapshot was originally fetched
        retry_count=retry_count,
        error=error,
    )


def _check_hr_pack(repo: RawRepository) -> SourceStatus:
    """The HR pack is delivered, not fetched: verify its checksums against the manifest."""
    snapshot = repo.latest_snapshot("hr")
    if snapshot is None:
        return SourceStatus(
            provider="hr",
            indicator="hr_pack",
            dataset="hr",
            status=SourceState.UNAVAILABLE,
            error="no HR pack in data/raw/hr",
        )

    try:
        manifest, _checks = verify_hr_snapshot(snapshot)
    except HrIntegrityError as exc:
        return SourceStatus(
            provider="hr",
            indicator="hr_pack",
            dataset="hr",
            status=SourceState.UNAVAILABLE,
            snapshot=repo.relative(snapshot),
            error=str(exc),
        )

    return SourceStatus(
        provider="hr",
        indicator="hr_pack",
        dataset="hr",
        status=SourceState.REPLAYED,  # delivered once, never fetched (D-68)
        snapshot=repo.relative(snapshot),
        source_period=manifest["workforce_as_of_date"],
    )
