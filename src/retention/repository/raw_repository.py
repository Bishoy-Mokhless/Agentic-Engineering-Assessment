"""Raw layer storage: untouched payloads in dated snapshot folders (D-41, D-48).

Layout:
    data/raw/<provider>/<dataset>/<snapshot_id>/payload.json    exactly what the provider returned
    data/raw/<provider>/<dataset>/<snapshot_id>/metadata.json   url, fetch time, retries, sha256, ...
    data/raw/<provider>/<dataset>/latest.json                   {"snapshot": "<snapshot_id>"}
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


class RawRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def dataset_dir(self, provider: str, dataset: str | None = None) -> Path:
        """Folder of one dataset, e.g. data/raw/eurostat/une_rt_m (or data/raw/hr if no dataset)."""
        if dataset:
            return self.root / provider / dataset
        return self.root / provider

    def save_snapshot(
        self,
        provider: str,
        dataset: str,
        snapshot_id: str,
        payload: bytes,
        metadata: dict,
        promote: bool = True,
    ) -> Path:
        """Write a new snapshot folder and, if `promote`, point latest.json at it.

        Existing snapshots are never overwritten (D-48). The ingest step saves with promote=False:
        the pipeline job promotes the snapshot only after the whole run succeeded (D-96).
        """
        target = self.dataset_dir(provider, dataset) / snapshot_id
        if target.exists():
            raise FileExistsError(f"raw snapshot already exists and is never overwritten (D-48): {target}")

        # 1. Write everything into a temporary folder first ...
        tmp = target.with_name(target.name + ".tmp")
        tmp.mkdir(parents=True)
        (tmp / "payload.json").write_bytes(payload)  # exactly the provider's bytes
        metadata_text = json.dumps(metadata, indent=2) + "\n"
        (tmp / "metadata.json").write_text(metadata_text, encoding="utf-8", newline="\n")  # LF (D-99)

        # 2. ... then rename it in one move, so a crash never leaves a half-written snapshot.
        tmp.rename(target)

        # 3. Point latest.json at the new snapshot (or leave that to promote(), D-96).
        if promote:
            self._set_latest(target.parent, snapshot_id)
        return target

    def promote(self, snapshot_ref: str) -> None:
        """Make a saved snapshot the current one, e.g. 'eurostat/une_rt_m/20260927T120052Z' (D-96)."""
        snapshot = self.root / snapshot_ref
        if not snapshot.is_dir():
            raise FileNotFoundError(f"cannot promote a snapshot that does not exist: {snapshot}")
        self._set_latest(snapshot.parent, snapshot.name)

    def latest_snapshot(self, provider: str, dataset: str | None = None) -> Path | None:
        """Return the snapshot to use.

        The one named in latest.json, else the newest dated folder, else None.
        """
        folder = self.dataset_dir(provider, dataset)
        if not folder.is_dir():
            return None

        # 1. Normal case: latest.json says which snapshot is current.
        pointer = folder / "latest.json"
        if pointer.exists():
            snapshot_id = json.loads(pointer.read_text(encoding="utf-8"))["snapshot"]
            snapshot = folder / snapshot_id
            if snapshot.is_dir():
                return snapshot
            return None

        # 2. No pointer (e.g. the delivered HR pack): take the newest dated folder.
        #    Folder names are dates/timestamps, so alphabetical order = time order.
        snapshots = []
        for child in folder.iterdir():
            if child.is_dir() and not child.name.endswith(".tmp"):
                snapshots.append(child)
        if not snapshots:
            return None
        snapshots.sort()
        return snapshots[-1]

    @staticmethod
    def read_metadata(snapshot: Path) -> dict:
        """Read metadata.json of a snapshot ({} if there is none, e.g. the HR pack)."""
        path = snapshot / "metadata.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def read_payload(snapshot: Path) -> bytes:
        """The provider's response exactly as saved (payload.json)."""
        return (snapshot / "payload.json").read_bytes()

    @staticmethod
    def read_csv_as_text(snapshot: Path, file_name: str) -> pd.DataFrame:
        """Read a delivered CSV with every column as text, blanks kept as "" (nothing interpreted yet).

        Example row: {"employee_id": "ACP000560", "hire_date": "", "regretted_exit": "false", ...}
        """
        return pd.read_csv(snapshot / file_name, dtype=str, keep_default_na=False)

    def relative(self, path: Path) -> str:
        """Path relative to data/raw, with forward slashes, e.g. 'eurostat/une_rt_m/20260927T120052Z'."""
        return path.relative_to(self.root).as_posix()

    @staticmethod
    def _set_latest(folder: Path, snapshot_id: str) -> None:
        """Write latest.json via a temp file + swap, so it is never half-written."""
        tmp = folder / "latest.json.tmp"
        tmp.write_text(json.dumps({"snapshot": snapshot_id}) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, folder / "latest.json")
