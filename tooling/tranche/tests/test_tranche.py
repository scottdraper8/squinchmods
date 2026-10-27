from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

import pytest

from squinch_tranche import core
from squinch_tranche.core import (
    TrancheError,
    clean_tranche,
    create_tranche,
    resolve_tranche,
)


def _write(path: Path, content: bytes = b"owned") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _stage(workspace: Path, game: Path, run_id: str = "20261027T120000Z-stage-deadbeef") -> Path:
    destination = game / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    payload = destination / "TEST/file.txt"
    _write(payload)
    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    manifest = workspace / "no-mans-sky/investigate/stages" / f"{run_id}.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "state": "active",
                "run_id": run_id,
                "game_root": str(game),
                "source": str(workspace / "input"),
                "destination": str(destination),
                "pending_destination": str(game / ".squinch-investigation-staging" / run_id),
                "files": {"test/file.txt": digest},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def test_cleaning_one_tranche_preserves_another_and_shared_paths(tmp_path: Path) -> None:
    first = create_tranche(tmp_path, "first-work")
    second = create_tranche(tmp_path, "second-work")
    source = tmp_path / "games/source.py"
    cache = tmp_path / "shared-cache/artifact.jar"
    _write(source, b"source")
    _write(cache, b"cache")
    _write(first / "minecraft/investigate/runs/one/result.json")
    _write(second / "no-mans-sky/investigate/runs/two/result.json")

    preview = clean_tranche(tmp_path, "first-work")
    assert preview["action"] == "dry-run"
    assert first.exists() and second.exists()

    applied = clean_tranche(tmp_path, "first-work", apply=True)
    assert applied["removed"] is True
    assert not first.exists()
    assert second.exists()
    assert source.read_bytes() == b"source"
    assert cache.read_bytes() == b"cache"


def test_cleanup_is_idempotent(tmp_path: Path) -> None:
    create_tranche(tmp_path, "one-shot")
    clean_tranche(tmp_path, "one-shot", apply=True)
    result = clean_tranche(tmp_path, "one-shot", apply=True)
    assert result["action"] == "absent"
    assert result["removed"] is False


@pytest.mark.parametrize("tranche_id", ["../escape", "two/slashes", "Uppercase", "-leading"])
def test_tranche_id_rejects_path_traversal(tmp_path: Path, tranche_id: str) -> None:
    with pytest.raises(TrancheError, match="tranche ID"):
        create_tranche(tmp_path, tranche_id)


def test_cleanup_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "symlink-check")
    outside = tmp_path / "outside"
    _write(outside / "keep.txt")
    (workspace / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "symlink-check", apply=True)
    assert error.value.code == "unsafe_owned_path"
    assert (outside / "keep.txt").exists()


def test_tool_resolution_rejects_existing_owned_symlink(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "tool-symlink")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "redirect").symlink_to(outside, target_is_directory=True)

    with pytest.raises(TrancheError) as error:
        resolve_tranche(tmp_path, "tool-symlink", validate_owned=True)
    assert error.value.code == "unsafe_owned_path"


def test_create_rejects_symlinked_ownership_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".squinch").symlink_to(outside, target_is_directory=True)

    with pytest.raises(TrancheError) as error:
        create_tranche(tmp_path, "symlinked-root")
    assert error.value.code == "unsafe_tranche"
    assert not (outside / "scratch").exists()


def test_cleanup_rejects_mount_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = create_tranche(tmp_path, "mounted-child")
    mounted = workspace / "mounted"
    mounted.mkdir()
    actual_ismount = core.os.path.ismount
    monkeypatch.setattr(
        core.os.path,
        "ismount",
        lambda path: Path(path) == mounted or actual_ismount(path),
    )

    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "mounted-child", apply=True)
    assert error.value.code == "unsafe_owned_path"
    assert workspace.exists()


def test_cleanup_refuses_live_tool_lock(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "live-tool")
    with (workspace / ".lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with pytest.raises(TrancheError) as error:
            clean_tranche(tmp_path, "live-tool", apply=True)
    assert error.value.code == "tranche_live"
    assert workspace.exists()


@pytest.mark.parametrize(
    "marker",
    ["minecraft/investigate/active/server.json", "minecraft/qa/active.json"],
)
def test_cleanup_refuses_incomplete_teardown(tmp_path: Path, marker: str) -> None:
    workspace = create_tranche(tmp_path, "incomplete")
    _write(workspace / marker)
    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "incomplete", apply=True)
    assert error.value.code == "teardown_incomplete"
    assert workspace.exists()


def test_cleanup_removes_exact_unchanged_external_stage(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "nms-stage")
    destination = _stage(workspace, tmp_path / "game")
    result = clean_tranche(tmp_path, "nms-stage", apply=True)
    assert result["removed"] is True
    assert not destination.exists()
    assert not workspace.exists()


def test_cleanup_preserves_modified_external_stage(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "changed-stage")
    destination = _stage(workspace, tmp_path / "game")
    (destination / "TEST/file.txt").write_bytes(b"changed")
    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "changed-stage", apply=True)
    assert error.value.code == "external_path_modified"
    assert destination.exists()
    assert workspace.exists()


def test_cleanup_rejects_external_stage_symlink(tmp_path: Path) -> None:
    workspace = create_tranche(tmp_path, "linked-stage")
    destination = _stage(workspace, tmp_path / "game")
    actual = tmp_path / "outside-stage"
    destination.rename(actual)
    destination.symlink_to(actual, target_is_directory=True)

    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "linked-stage", apply=True)
    assert error.value.code == "unsafe_external_path"
    assert (actual / "TEST/file.txt").exists()
    assert workspace.exists()


def test_cleanup_refuses_running_nms_for_external_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = create_tranche(tmp_path, "running-nms")
    destination = _stage(workspace, tmp_path / "game")
    monkeypatch.setattr(core, "_running_processes", lambda _name: [42])
    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "running-nms", apply=True)
    assert error.value.code == "owned_process_live"
    assert destination.exists()


def test_dry_run_refuses_running_nms_for_external_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = create_tranche(tmp_path, "running-nms-preview")
    destination = _stage(workspace, tmp_path / "game")
    monkeypatch.setattr(core, "_running_processes", lambda _name: [42])
    with pytest.raises(TrancheError) as error:
        clean_tranche(tmp_path, "running-nms-preview")
    assert error.value.code == "owned_process_live"
    assert destination.exists()
