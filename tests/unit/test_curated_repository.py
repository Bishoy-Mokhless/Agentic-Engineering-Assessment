"""Publishing the curated layers (D-48, D-98): all layers move together, or none of them do."""

from pathlib import Path

import pytest

from retention.repository.curated_repository import CuratedRepository

LAYERS = ("analytical", "canonical", "source_shaped")


def make_repo(tmp_path):
    dirs = {layer: tmp_path / "curated" / layer for layer in LAYERS}
    return CuratedRepository(layer_dirs=dirs, build_root=tmp_path / ".tmp"), dirs


def build_with(repo, run_id, label):
    build = repo.start_build(run_id)
    for layer in LAYERS:
        (repo.layer_path(build, layer) / "table.txt").write_text(label, encoding="utf-8")
    return build


def contents(dirs):
    return {layer: (path / "table.txt").read_text(encoding="utf-8") for layer, path in dirs.items()}


def test_publish_swaps_every_layer(tmp_path):
    repo, dirs = make_repo(tmp_path)
    repo.publish(build_with(repo, "run-1", "old"))
    repo.publish(build_with(repo, "run-2", "new"))
    assert contents(dirs) == {layer: "new" for layer in LAYERS}
    assert list((tmp_path / ".tmp").iterdir()) == []


def test_failed_publish_rolls_back_the_layers_already_swapped(tmp_path, monkeypatch):
    """F-03: if canonical cannot move in, analytical must not stay on the new run."""
    repo, dirs = make_repo(tmp_path)
    repo.publish(build_with(repo, "run-1", "old"))
    build = build_with(repo, "run-2", "new")

    real_rename = Path.rename

    def rename(self, target):
        if self == build / "canonical":  # only the new canonical folder fails to move in
            raise PermissionError("simulated: a file in canonical is held open")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(PermissionError):
        repo.publish(build)

    assert contents(dirs) == {layer: "old" for layer in LAYERS}  # one consistent (previous) run


def test_a_new_run_removes_build_folders_left_by_interrupted_runs(tmp_path):
    """F-16 (D-99): Ctrl+C leaves data/.tmp/<run_id> behind; the next run sweeps it."""
    repo, _dirs = make_repo(tmp_path)
    leftover = tmp_path / ".tmp" / "run-20260101T000000Z"
    (leftover / "canonical").mkdir(parents=True)
    build = repo.start_build("run-20260102T000000Z")
    assert not leftover.exists()
    assert build.is_dir()


def test_json_outputs_use_lf_on_every_platform(tmp_path):
    """F-18 (D-99): Windows must not write CRLF, or a Linux rerun would rewrite the same JSON."""
    from retention.pipeline.run_summary import write_run_summary
    from retention.repository.raw_repository import RawRepository

    repo, _dirs = make_repo(tmp_path)
    build = repo.start_build("run-1")
    repo.write_json(build, "canonical", "doc", {"a": [1, 2]})
    raw = RawRepository(tmp_path / "raw")
    snapshot = raw.save_snapshot("eurostat", "une_rt_m", "20260101T000000Z", b"{}", {"n": 1})
    from datetime import UTC, datetime

    now = datetime(2026, 10, 1, tzinfo=UTC)
    summary = tmp_path / "run_summary.json"
    write_run_summary(
        summary,
        run_id="run-1",
        mode="offline",
        started_at=now,
        finished_at=now,
        sources=[],
        outcome="succeeded",
        steps={},
    )

    written = [
        build / "canonical" / "doc.json",
        snapshot / "metadata.json",
        snapshot.parent / "latest.json",
        summary,
    ]
    for path in written:
        assert b"\r\n" not in path.read_bytes(), path.name
