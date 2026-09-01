from __future__ import annotations

import subprocess
import time
import zipfile
from pathlib import Path

import pytest

from squinch_minecraft_investigate import server
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate import processes
from squinch_minecraft_investigate.processes import port_is_free


def test_development_probe_cleanup_requires_marker_and_removes_owned_jar(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    probe = run_dir / "mods" / server.DEVELOPMENT_PROBE_JAR
    probe.parent.mkdir(parents=True)
    with zipfile.ZipFile(probe, "w") as archive:
        archive.writestr(server.DEVELOPMENT_PROBE_MARKER, "development evidence only\n")

    assert server._remove_development_probe_jar(run_dir) == []
    assert not probe.exists()

    with zipfile.ZipFile(probe, "w") as archive:
        archive.writestr("unowned.txt", "preserve\n")
    failures = server._remove_development_probe_jar(run_dir)

    assert len(failures) == 1
    assert "lacks the ownership marker" in failures[0]
    assert probe.exists()


def test_proc_scans_snapshot_entry_names_before_reading_process_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient /proc process must not leave lifecycle cleanup with a broken Path."""

    class Entries:
        def __enter__(self) -> list[object]:
            return [
                type("Entry", (), {"name": "41"})(),
                type("Entry", (), {"name": "not-a-pid"})(),
                type("Entry", (), {"name": "42"})(),
            ]

        def __exit__(self, _type: object, _value: object, _traceback: object) -> bool:
            return False

    identities = {
        41: {"pid": 41, "ppid": 1, "pgrp": 41, "session": 41, "start_ticks": 1, "state": "S"},
        42: {"pid": 42, "ppid": 41, "pgrp": 41, "session": 41, "start_ticks": 2, "state": "S"},
    }
    monkeypatch.setattr(processes.os, "scandir", lambda _path: Entries())
    monkeypatch.setattr(processes, "proc_identity", lambda pid: identities.get(pid))
    monkeypatch.setattr(processes, "identity_matches", lambda _expected: True)

    assert processes.group_members(41) == [identities[41], identities[42]]
    assert processes.descendants([identities[41]]) == [identities[41], identities[42]]


def test_forceload_removal_is_persisted_per_acknowledged_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = {"block_min_x": 1, "block_min_z": 2, "block_max_x": 3, "block_max_z": 4}
    second = {"block_min_x": 5, "block_min_z": 6, "block_max_x": 7, "block_max_z": 8}
    state = {"forceload_regions": [first, second]}
    commands: list[str] = []
    snapshots: list[list[dict[str, int]]] = []

    def run(_state: dict, values: list[str], _timeout: float) -> list[dict]:
        commands.extend(values)
        return [{"command": value, "response": "Unmarked"} for value in values]

    monkeypatch.setattr(server, "run_commands", run)
    monkeypatch.setattr(
        server,
        "_write_active",
        lambda current: snapshots.append(list(current["forceload_regions"])),
    )

    assert server._remove_forceload_regions(state, 30) == []
    assert commands == [
        "forceload remove 5 6 7 8",
        "forceload remove 1 2 3 4",
    ]
    assert snapshots == [[first], []]
    assert state["forceload_regions"] == []


@pytest.mark.slow
def test_real_process_group_cleanup_kills_ignoring_child_and_restores_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches cleanup that stops only Gradle's parent while a child listener survives."""
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    gradlew = project / "gradlew"
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew.write_text(f"#!/usr/bin/env bash\nexec python3 {fixture!s}\n")
    gradlew.chmod(0o644)
    original_properties = "motd=user-owned\n"
    (run_dir / "server.properties").write_text(original_properties)
    first_datapack = tmp_path / "first.zip"
    second_datapack = tmp_path / "second.zip"
    first_datapack.write_bytes(b"first")
    second_datapack.write_bytes(b"second")
    runtime_config = tmp_path / "terrablender-region-2.toml"
    runtime_config.write_text("[general]\noverworld_region_size = 2\n")
    config_target = run_dir / "config" / "terrablender.toml"
    config_target.parent.mkdir()
    config_target.write_text("[general]\noverworld_region_size = 3\n")
    original_config = config_target.read_text()
    second_runtime_config = tmp_path / "provider-settings.toml"
    second_runtime_config.write_text("enabled = false\n")
    second_config_target = run_dir / "config" / "nested" / "terrablender.toml"
    second_config_target.parent.mkdir()
    second_config_target.write_text("enabled = true\n")
    second_original_config = second_config_target.read_text()
    absent_config_target = run_dir / "config" / "generated-on-first-start.json"
    absent_config_target.write_text("preserve me\n")

    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    state = server.start_server(
        project.resolve(),
        "fabric",
        seed="123",
        datapacks=[first_datapack, second_datapack],
        runtime_files=[
            (runtime_config, "config/terrablender.toml"),
            (second_runtime_config, "config/nested/terrablender.toml"),
        ],
        runtime_absent_files=["config/generated-on-first-start.json"],
        properties={},
        timeout=10,
        retention="discard",
    )
    assert gradlew.stat().st_mode & 0o111 == 0
    assert not port_is_free(state["ports"]["server"])
    assert not port_is_free(state["ports"]["rcon"])
    assert sorted(path.name for path in (Path(state["world_dir"]) / "datapacks").iterdir()) == [
        "first.zip",
        "second.zip",
    ]
    assert config_target.read_text() == runtime_config.read_text()
    assert second_config_target.read_text() == second_runtime_config.read_text()
    assert not absent_config_target.exists()

    result = server.stop_server(project.resolve(), "fabric", successful=True, timeout=0.5)

    assert result["cleanup"]["complete"] is True
    assert port_is_free(state["ports"]["server"])
    assert port_is_free(state["ports"]["rcon"])
    assert (run_dir / "server.properties").read_text() == original_properties
    assert config_target.read_text() == original_config
    assert second_config_target.read_text() == second_original_config
    assert absent_config_target.read_text() == "preserve me\n"
    assert not (run_dir / "eula.txt").exists()
    assert not Path(state["world_dir"]).exists()
    assert not (state_root / "active.json").exists()


@pytest.mark.slow
def test_startup_timeout_cleans_process_and_provisional_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a startup timeout that leaves its Gradle process or active ownership state behind."""
    project = tmp_path / "project"
    (project / "fabric" / "run").mkdir(parents=True)
    gradlew = project / "gradlew"
    gradlew.write_text("#!/usr/bin/env bash\nsleep 60\n")
    gradlew.chmod(0o644)

    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    with pytest.raises(InvestigationError, match="authenticate over RCON") as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=0.05,
            retention="discard",
        )

    assert failure.value.details["cleanup_complete"] is True
    assert not (state_root / "active.json").exists()
    assert gradlew.stat().st_mode & 0o111 == 0
    summary = next((state_root / "runs").glob("*/summary.json"))
    assert '"complete": true' in summary.read_text()


@pytest.mark.slow
def test_listener_free_gradle_boundary_does_not_consume_full_shutdown_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches teardown waiting the full world-save timeout after both real listeners are gone."""
    project = tmp_path / "project"
    (project / "fabric" / "run").mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew = project / "gradlew"
    gradlew.write_text(f"#!/usr/bin/env bash\nexec python3 {fixture!s}\n")
    gradlew.chmod(0o644)
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")
    state = server.start_server(
        project.resolve(),
        "fabric",
        seed="123",
        datapacks=[],
        properties={
            "fake-child-ignore-term": "false",
            "fake-linger-after-stop": "60",
        },
        timeout=10,
        retention="discard",
    )

    started = time.monotonic()
    result = server.stop_server(project.resolve(), "fabric", successful=True, timeout=30)
    elapsed = time.monotonic() - started

    assert elapsed < 15
    assert result["cleanup"]["complete"] is True
    assert port_is_free(state["ports"]["server"])
    assert port_is_free(state["ports"]["rcon"])
    assert not (state_root / "active.json").exists()


@pytest.mark.slow
def test_probe_overlay_tracked_source_mutation_fails_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches an init overlay that writes into tracked target sources during a development run."""
    project = tmp_path / "project"
    (project / "fabric" / "run").mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew = project / "gradlew"
    gradlew.write_text(
        f"#!/usr/bin/env bash\nprintf 'mutated\\n' > tracked.txt\nexec python3 {fixture!s}\n"
    )
    gradlew.chmod(0o644)
    (project / "tracked.txt").write_text("original\n")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Overlay Test"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.email", "overlay@example.invalid"], cwd=project, check=True
    )
    subprocess.run(["git", "add", "gradlew", "tracked.txt"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    with pytest.raises(InvestigationError) as caught:
        server.start_server(
            project.resolve(),
            "fabric",
            seed="123",
            datapacks=[],
            properties={},
            timeout=10,
            retention="discard",
        )

    assert caught.value.code == "probe_overlay_modified_worktree"
    assert (project / "tracked.txt").read_text() == "mutated\n"
    assert not (state_root / "active.json").exists()
    manifest = next((state_root / "runs").glob("*/manifest.json"))
    assert '"complete": true' in manifest.read_text()


def test_recover_stops_an_orphaned_starting_run(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "lifecycle": "starting",
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [{"pid": 44, "pgrp": 44, "session": 44, "start_ticks": 1}],
        "ports": {"server": 25565, "rcon": 25575},
    }
    observed: dict[str, object] = {}
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(server, "group_members", lambda _pgrp: [])
    monkeypatch.setattr(server, "port_is_free", lambda _port: True)
    monkeypatch.setattr(
        server,
        "proc_identity",
        lambda _pid: {"pid": 44, "ppid": 1, "pgrp": 44, "session": 44, "start_ticks": 1},
    )

    def stop(_project: Path, _loader: str, **kwargs: object) -> dict:
        observed.update(kwargs)
        return {"recovered": True}

    monkeypatch.setattr(server, "stop_server", stop)

    assert server.recover(Path("project"), "fabric", 30) == {"recovered": True}
    assert observed == {"successful": False, "timeout": 30, "allow_orphaned_starting": True}


def test_recover_refuses_a_starting_run_with_live_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "lifecycle": "starting",
        "launcher": {"pid": 33, "pgrp": 33, "session": 33, "start_ticks": 1},
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [{"pid": 44, "pgrp": 44, "session": 44, "start_ticks": 1}],
        "ports": {"server": 25565, "rcon": 25575},
    }
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(server, "group_members", lambda _pgrp: [])
    monkeypatch.setattr(server, "port_is_free", lambda _port: True)

    with pytest.raises(InvestigationError, match="live launching command") as failure:
        server.recover(Path("project"), "fabric", 30)

    assert failure.value.code == "startup_in_progress"


def test_recover_without_live_process_removes_companion_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "project" / "neoforge" / "run"
    mods_dir = run_dir / "mods"
    mods_dir.mkdir(parents=True)
    companion = mods_dir / "example.jar"
    companion.write_bytes(b"owned companion")
    active = tmp_path / "active.json"
    active.write_text("{}")
    state = {
        "lifecycle": "starting",
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [],
        "ports": {"server": 25565, "rcon": 25575},
        "run_dir": str(run_dir),
        "artifact_dir": str(tmp_path / "artifacts"),
        "active_path": str(active),
        "managed_files": [],
        "companion_artifacts": [{"materialized_path": str(companion)}],
    }
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "identity_matches", lambda _identity: False)
    monkeypatch.setattr(server, "group_members", lambda _pgrp: [])
    monkeypatch.setattr(server, "port_is_free", lambda _port: True)
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: tmp_path / "lock")
    monkeypatch.setattr(server, "_remove_protocol_files", lambda _state: [])
    monkeypatch.setattr(server, "_restore_managed_files", lambda _state: [])
    monkeypatch.setattr(server, "_cleanup_world", lambda _state, successful: None)
    monkeypatch.setattr(server, "_write_manifest", lambda _state: None)

    result = server.recover(Path("project"), "neoforge", 30)

    assert result["cleanup"]["complete"] is True
    assert not companion.exists()
    assert not active.exists()
