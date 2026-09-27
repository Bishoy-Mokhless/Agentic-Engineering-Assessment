"""Integrity check for the supplied HR data pack (D-65, D-69).

The pack ships a manifest with a SHA-256 checksum and byte size for each file.
Verifying them proves we are using exactly the files the assessment provided.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "assessment_data_manifest.json"


class HrIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class FileCheck:
    name: str
    ok: bool
    expected_sha256: str
    actual_sha256: str
    expected_bytes: int
    actual_bytes: int


def verify_hr_snapshot(folder: Path) -> tuple[dict, list[FileCheck]]:
    """Check every file listed in the manifest. Return (manifest, checks).

    Raises HrIntegrityError if the manifest or a file is missing, or a file was changed.
    """
    # 1. Read the manifest that came with the pack.
    manifest_path = folder / MANIFEST_NAME
    if not manifest_path.exists():
        raise HrIntegrityError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # 2. For each file: compute its SHA-256 fingerprint and size, compare with the manifest.
    checks = []
    for entry in manifest["files"]:
        path = folder / entry["name"]
        if not path.exists():
            raise HrIntegrityError(f"file listed in manifest is missing: {path.name}")

        content = path.read_bytes()
        actual_sha256 = hashlib.sha256(content).hexdigest()
        actual_bytes = len(content)
        ok = actual_sha256 == entry["sha256"] and actual_bytes == entry["bytes"]

        checks.append(
            FileCheck(
                name=path.name,
                ok=ok,
                expected_sha256=entry["sha256"],
                actual_sha256=actual_sha256,
                expected_bytes=entry["bytes"],
                actual_bytes=actual_bytes,
            )
        )

    # 3. Fail if any file does not match, naming the files.
    altered = []
    for check in checks:
        if not check.ok:
            altered.append(check.name)
    if altered:
        raise HrIntegrityError(f"checksum/size mismatch vs manifest: {', '.join(altered)}")

    return manifest, checks
