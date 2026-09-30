"""Read-only access to the published curated layers, for the API (D-05, D-44).

Files are read on every request. They are small (< 100 KB each) and this way the API always
serves the latest published build: after `retention run` swaps a new build in, the next request
sees it, with no restart and no cache to invalidate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from retention.config import Settings
from retention.domain.errors import DataNotBuiltError

NOT_BUILT_HINT = "run `retention run` first to build the data"


class CuratedStore:
    def __init__(self, settings: Settings) -> None:
        self.layers = {
            "source_shaped": settings.paths.source_shaped,
            "canonical": settings.paths.canonical,
            "analytical": settings.paths.analytical,
        }
        self.run_summary_path = settings.paths.canonical.parent / "run_summary.json"

    def table(self, layer: str, name: str) -> pd.DataFrame:
        """e.g. table("analytical", "retention_cohorts"). Raises DataNotBuiltError if missing."""
        path = self.layers[layer] / f"{name}.parquet"
        if not path.exists():
            raise DataNotBuiltError(f"{layer}/{name}.parquet not found - {NOT_BUILT_HINT}")
        return pd.read_parquet(path)

    def document(self, layer: str, name: str) -> dict:
        """e.g. document("canonical", "quality_report") -> the JSON as a dict."""
        return _read_json(self.layers[layer] / f"{name}.json")

    def run_summary(self) -> dict | None:
        """The latest run record, or None if nothing ever ran."""
        if not self.run_summary_path.exists():
            return None
        return json.loads(self.run_summary_path.read_text(encoding="utf-8"))

    def is_built(self) -> bool:
        return (self.layers["analytical"] / "_build.json").exists()


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise DataNotBuiltError(f"{path.name} not found - {NOT_BUILT_HINT}")
    return json.loads(path.read_text(encoding="utf-8"))
