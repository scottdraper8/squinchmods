"""Confinement/rollback controls; no Minecraft compatibility claims."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from squinch_minecraft_investigate import cli, owned_operation, server
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
from squinch_minecraft_investigate.paths import active_path, lock_path
from squinch_minecraft_investigate.state import project_lock
from squinch_minecraft_investigate.tranche import require_tranche

# Share only the explicit maintained fixtures, not a second launcher implementation.
pytest_plugins = ["test_packaged_runtime"]


def test_same_tranche_project_is_allowed_but_other_tranche_is_not(recipe):
    spec, path, save = recipe
    project = path.parent / "worktree"
    shutil.copytree(spec["project"], project)
    spec["project"] = str(project)
    spec["source_roots"] = [str(project)]
    assert runtime.validate_spec(save())["project"] == str(project)
    _id, workspace = require_tranche()
    spec["project"] = str(workspace.parent / "other-tranche")
    Path(spec["project"]).mkdir(exist_ok=True)
    with pytest.raises(InvestigationError, match="another tranche"):
        runtime.validate_spec(save())


@pytest.mark.parametrize("kind", ["symlink", "parent-link", "special", "hardlink"])
def test_template_links_and_special_files_are_not_followed(recipe, kind):
    spec, _path, save = recipe
    template = Path(spec["template"]["path"])
    launch = template / "launch.args"
    extra = template / "extra"
    if kind == "symlink":
        extra.symlink_to(launch)
    elif kind == "parent-link":
        extra.symlink_to(template, target_is_directory=True)
    elif kind == "hardlink":
        import os

        os.link(launch, extra)
    else:
        import os

        os.mkfifo(extra)
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save())


def test_modified_copy_fails_preparation_without_launch(
    recipe, subprocess_service, monkeypatch
):
    spec, _path, save = recipe
    original = runtime.shutil.copytree

    def corrupt(source, target, *args, **kwargs):
        result = original(source, target, *args, **kwargs)
        if (Path(target) / "launch.args").exists():
            (Path(target) / "launch.args").write_text("corrupt")
        return result

    monkeypatch.setattr(runtime.shutil, "copytree", corrupt)
    before = set(runtime.RUNS_ROOT.iterdir())
    with pytest.raises(InvestigationError, match="during copy"):
        runtime.run_packaged_runtime(save())
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == before
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_dirty_tracked_and_untracked_source_content_is_snapshotted(recipe):
    spec, _path, _save = recipe
    project = Path(spec["project"])
    source = project / "source.txt"
    source.write_text("dirty one")
    untracked = project / "untracked.txt"
    untracked.write_text("one")
    before = runtime._source_snapshot(project, spec["source_roots"])
    source.write_text("dirty two")
    assert runtime._source_snapshot(project, spec["source_roots"]) != before
    source.write_text("dirty one")
    untracked.write_text("two")
    assert runtime._source_snapshot(project, spec["source_roots"]) != before
    (project / "new-source.txt").write_text("pollution")
    assert (
        runtime._source_snapshot(project, spec["source_roots"])["files"]
        != before["files"]
    )


def client_recipe(recipe, monkeypatch, tmp_path):
    spec, path, save = recipe
    spec["side"] = "client"
    display_root = tmp_path / "xdg"
    display_root.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(display_root))
    run_id = runtime.new_run_id()
    monkeypatch.setattr(runtime, "new_run_id", lambda: run_id)
    return spec, path, save, display_root / f"squinch-{run_id[-10:]}"


def test_display_collision_is_never_removed(
    recipe, subprocess_service, monkeypatch, tmp_path
):
    spec, _path, save, display = client_recipe(recipe, monkeypatch, tmp_path)
    display.mkdir()
    unrelated = display / "unrelated"
    unrelated.write_text("keep")
    with pytest.raises(FileExistsError):
        runtime.run_packaged_runtime(save())
    assert unrelated.read_text() == "keep"
    assert not subprocess_service
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_launch_failure_cleans_private_display(
    recipe, subprocess_service, monkeypatch, tmp_path
):
    spec, _path, save, display = client_recipe(recipe, monkeypatch, tmp_path)

    def fail(**kwargs):
        raise InvestigationError("controlled_launch_failure", "fixture")

    monkeypatch.setattr(owned_operation, "launch_service", fail)
    with pytest.raises(InvestigationError, match="fixture"):
        runtime.run_packaged_runtime(save())
    assert not display.exists()
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_display_rollback_failure_has_valid_recoverable_owner(
    recipe, subprocess_service, monkeypatch, tmp_path
):
    spec, _path, save, display = client_recipe(recipe, monkeypatch, tmp_path)

    def fail(**kwargs):
        raise InvestigationError("controlled_launch_failure", "fixture")

    monkeypatch.setattr(owned_operation, "launch_service", fail)
    original_cleanup = runtime._cleanup_display
    monkeypatch.setattr(
        runtime, "_cleanup_display", lambda _s: ["controlled display failure"]
    )
    with pytest.raises(CleanupError):
        runtime.run_packaged_runtime(save())
    project = Path(spec["project"])
    state = server.load_owned_active(project, spec["loader"])
    assert state["lifecycle"] == "launching"
    assert state["started_at"]
    assert display.exists()
    active = active_path(project, spec["loader"])
    original = json.loads(active.read_text())
    for field, value in (
        ("run_dir", str(display)),
        ("log_path", str(display / "file")),
        ("application_exit", str(display / "exit.json")),
    ):
        changed = {**original, field: value}
        active.write_text(json.dumps(changed))
        with pytest.raises(InvestigationError):
            server.load_owned_active(project, spec["loader"])
    changed = {
        **original,
        "display": {**original["display"], "runtime_root": str(display.parent.parent)},
    }
    active.write_text(json.dumps(changed))
    with pytest.raises(InvestigationError):
        server.load_owned_active(project, spec["loader"])
    changed = {**original, "side": "server"}
    active.write_text(json.dumps(changed))
    with pytest.raises(InvestigationError):
        server.load_owned_active(project, spec["loader"])
    active.write_text(json.dumps(original))
    monkeypatch.setattr(server, "service_members", lambda *_a: [])
    monkeypatch.setattr(server, "capture_service_threads", lambda *_a, **_k: None)
    monkeypatch.setattr(
        server,
        "uninterruptible_owned_threads",
        lambda *_a, **_k: {"threads": [], "inconclusive": []},
    )
    args = cli.parser().parse_args(
        ["status", "--project", str(project), "--loader", "forge", "--json"]
    )
    value, _human = cli._status(args)
    assert value["state"] == "degraded"
    assert value["data"]["process"] is None
    monkeypatch.setattr(runtime, "_cleanup_display", original_cleanup)
    recovered = server.recover(project, spec["loader"], 5)
    assert recovered["cleanup"]["complete"]
    assert not display.exists()
    assert not active.exists()


@pytest.mark.parametrize("loader", ["fabric", "forge", "neoforge", "quilt"])
def test_loader_contract_does_not_require_modern_project_layout(recipe, loader):
    spec, _path, save = recipe
    spec["loader"] = loader
    assert runtime.validate_spec(save())["loader"] == loader


def test_same_project_lock_is_not_bypassed(recipe, subprocess_service):
    spec, _path, save = recipe
    project = Path(spec["project"])
    before = set(runtime.RUNS_ROOT.iterdir())
    with (
        project_lock(lock_path(project, spec["loader"])),
        pytest.raises(InvestigationError, match="another investigation command"),
    ):
        runtime.run_packaged_runtime(save())
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == before


def test_dangling_display_link_cannot_count_as_cleaned(tmp_path):
    path = tmp_path / "squinch-123456789a"
    path.symlink_to(tmp_path / "missing", target_is_directory=True)
    state = {
        "side": "client",
        "run_id": "20261027T000000Z-123456789a",
        "display": {"runtime_root": str(tmp_path), "runtime_dir": str(path)},
    }
    assert runtime._cleanup_display(state)
    assert path.is_symlink()
