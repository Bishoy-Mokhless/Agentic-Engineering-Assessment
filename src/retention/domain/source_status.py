"""Status of each data source in a pipeline run (D-62, D-68)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class SourceState(StrEnum):
    FRESH = "fresh"  # fetched successfully in this run (--refresh)
    REPLAYED = "replayed"  # deliberately loaded from a saved snapshot (--offline, or the delivered HR pack)
    STALE = "stale"  # a fetch was attempted and failed; last good snapshot used instead
    UNAVAILABLE = "unavailable"  # no usable data at all


@dataclass(frozen=True)
class SourceStatus:
    provider: str
    indicator: str
    dataset: str
    status: SourceState
    snapshot: str | None = None  # raw snapshot used, relative to data/raw (lineage)
    source_period: str | None = None  # latest period present in the data, e.g. "2026-07"
    loaded_at: str | None = None  # when the snapshot was fetched (ISO 8601, UTC)
    retry_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data
