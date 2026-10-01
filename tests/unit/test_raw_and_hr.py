"""Raw snapshot storage (D-48) and HR pack integrity check (D-65)."""

import shutil

import pytest

from retention.client.hr_files import HrIntegrityError, verify_hr_snapshot
from retention.config import load_settings
from retention.repository.raw_repository import RawRepository


def test_snapshots_are_kept_and_latest_pointer_moves(tmp_path):
    repo = RawRepository(tmp_path)
    first = repo.save_snapshot("eurostat", "une_rt_m", "20260101T000000Z", b"{}", {"n": 1})
    second = repo.save_snapshot("eurostat", "une_rt_m", "20260201T000000Z", b"{}", {"n": 2})
    assert first.is_dir() and second.is_dir()  # history kept
    assert repo.latest_snapshot("eurostat", "une_rt_m") == second
    assert repo.read_metadata(second) == {"n": 2}


def test_existing_snapshot_is_never_overwritten(tmp_path):
    repo = RawRepository(tmp_path)
    repo.save_snapshot("eurostat", "une_rt_m", "20260101T000000Z", b"{}", {})
    with pytest.raises(FileExistsError):
        repo.save_snapshot("eurostat", "une_rt_m", "20260101T000000Z", b"{}", {})


def test_no_snapshot_returns_none(tmp_path):
    assert RawRepository(tmp_path).latest_snapshot("eurostat", "une_rt_m") is None


def hr_pack():
    return load_settings().paths.hr_source / "2025-12-31"


def test_supplied_hr_pack_matches_manifest():
    manifest, checks = verify_hr_snapshot(hr_pack())
    assert manifest["workforce_as_of_date"] == "2025-12-31"
    assert len(checks) == 3 and all(c.ok for c in checks)


def test_altered_hr_file_is_detected(tmp_path):
    copy = tmp_path / "2025-12-31"
    shutil.copytree(hr_pack(), copy)
    with open(copy / "retention_objectives.csv", "a", encoding="utf-8") as f:
        f.write("extra line\n")
    with pytest.raises(HrIntegrityError, match="retention_objectives.csv"):
        verify_hr_snapshot(copy)


def test_unreadable_hr_manifest_is_an_integrity_error(tmp_path):
    """F-02 (D-97): a broken manifest makes the HR source unavailable instead of crashing the run."""
    pack = tmp_path / "2025-12-31"
    shutil.copytree(hr_pack(), pack)
    (pack / "assessment_data_manifest.json").write_text("{ not json", encoding="utf-8")
    with pytest.raises(HrIntegrityError):
        verify_hr_snapshot(pack)
