"""Curated layers storage: build in a temp folder, then swap into place (D-41, D-48, D-74).

Spring analogy: a @Repository that writes files, with a "transaction": nothing is visible
until publish(), and a failed run leaves the previous outputs untouched.

    data/.tmp/<run_id>/source_shaped/*.parquet   <- written during the run
    data/.tmp/<run_id>/canonical/*.parquet
                     | publish() (only if every step succeeded)
                     v
    data/curated/source_shaped/   data/curated/canonical/   (the previous versions are removed)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class TableInfo:
    """What was written, for _build.json: e.g. employees.parquet, 2400 rows, sha256 ..."""

    file: str
    rows: int
    sha256: str


class CuratedRepository:
    def __init__(self, layer_dirs: dict[str, Path], build_root: Path) -> None:
        self.layer_dirs = layer_dirs  # {"source_shaped": data/curated/source_shaped, "canonical": ...}
        self.build_root = build_root  # data/.tmp

    def start_build(self, run_id: str) -> Path:
        """Create an empty build folder for this run, e.g. data/.tmp/run-20260927T120052Z."""
        build = self.build_root / run_id
        if build.exists():
            shutil.rmtree(build)
        build.mkdir(parents=True)
        return build

    def layer_path(self, build: Path, layer: str) -> Path:
        """Folder of one layer inside the build, e.g. data/.tmp/<run_id>/canonical (created if needed)."""
        if layer not in self.layer_dirs:
            raise ValueError(f"unknown layer '{layer}' (known: {', '.join(self.layer_dirs)})")
        path = build / layer
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_table(self, build: Path, layer: str, name: str, table: pd.DataFrame) -> TableInfo:
        """Write one table as Parquet and return its row count and SHA-256.

        The same table always gives the same bytes, so the hash proves deterministic reruns (D-74).
        """
        path = self.layer_path(build, layer) / f"{name}.parquet"
        table.to_parquet(path, index=False)
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        return TableInfo(file=path.name, rows=len(table), sha256=sha256)

    def write_json(self, build: Path, layer: str, name: str, data: dict) -> None:
        """Write a JSON document (quality report, _build.json) into a layer of the build."""
        path = self.layer_path(build, layer) / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")

    def read_json(self, build: Path, layer: str, name: str) -> dict:
        """Read back a JSON document written earlier in the same build (e.g. canonical/_build.json)."""
        path = self.layer_path(build, layer) / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def publish(self, build: Path) -> None:
        """Swap every layer of the build into data/curated, then delete the build folder.

        Per layer: move the current folder aside -> move the new one in -> delete the old one.
        If the move-in fails, the old folder is put back, so readers never see an empty layer.
        """
        for layer in sorted(self.layer_dirs):
            new = build / layer
            if not new.exists():
                continue  # this run did not build that layer (e.g. analytical before Step 4)
            target = self.layer_dirs[layer]
            target.parent.mkdir(parents=True, exist_ok=True)
            previous = build / f"_previous_{layer}"

            # 1. Move the current version aside (if there is one).
            if target.exists():
                target.rename(previous)
            # 2. Move the new version in; on failure put the old one back.
            try:
                new.rename(target)
            except OSError:
                if previous.exists():
                    previous.rename(target)
                raise
            # 3. The old version is no longer needed.
            if previous.exists():
                shutil.rmtree(previous)

        shutil.rmtree(build, ignore_errors=True)

    @staticmethod
    def discard(build: Path) -> None:
        """Throw away a failed build; data/curated is left exactly as it was."""
        shutil.rmtree(build, ignore_errors=True)
