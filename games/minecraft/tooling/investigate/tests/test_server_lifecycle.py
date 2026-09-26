from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import threading
import time
import zipfile
from pathlib import Path

import pytest

from squinch_minecraft_investigate import processes, server
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
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


def test_unexpected_run_mods_reports_every_undeclared_entry(tmp_path: Path) -> None:
    mods = tmp_path / "mods"
    mods.mkdir()
    first = mods / "first.jar"
    second = mods / "nested"
    first.write_bytes(b"jar")
    second.mkdir()

    assert server._unexpected_run_mods(tmp_path) == [first, second]


def test_production_launch_cleanup_removes_only_reserved_outputs(tmp_path: Path) -> None:
    mods = tmp_path / "mods"
    mods.mkdir()
    probe = mods / server.DEVELOPMENT_PROBE_JAR
    with zipfile.ZipFile(probe, "w") as archive:
        archive.writestr(server.DEVELOPMENT_PROBE_MARKER, "owned")
    production = [mods / name for name in server.PRODUCTION_SERVER_JARS]
    for path in production:
        path.write_bytes(b"owned")

    assert server._remove_launch_artifacts(
        {"run_dir": str(tmp_path), "launch_task": "prodServer"}
    ) == []
    assert not probe.exists()
    assert all(not path.exists() for path in production)


def test_owned_service_enumerates_nested_cgroup_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cgroup"
    service = root / "user.slice" / "squinch.service"
    child = service / "child"
    child.mkdir(parents=True)
    (service / "cgroup.procs").write_text("41\n")
    (child / "cgroup.procs").write_text("42\n")
    identities = {
        41: {"pid": 41, "ppid": 1, "pgrp": 41, "session": 41, "start_ticks": 1, "state": "S"},
        42: {"pid": 42, "ppid": 41, "pgrp": 41, "session": 41, "start_ticks": 2, "state": "S"},
    }
    monkeypatch.setattr(processes, "CGROUP_ROOT", root)
    monkeypatch.setattr(processes, "proc_identity", lambda pid: identities.get(pid))

    assert processes.service_members(
        {"unit": "squinch-mc-test.service", "cgroup": "/user.slice/squinch.service"}
    ) == [identities[41], identities[42]]


def test_owned_service_resolves_a_launching_cgroup_from_its_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "cgroup"
    cgroup = root / "user.slice" / "squinch.service"
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.procs").write_text("41\n")
    identity = {
        "pid": 41, "ppid": 1, "pgrp": 41, "session": 41,
        "start_ticks": 2, "state": "S",
    }
    service = {"unit": "squinch-mc-test.service", "cgroup": ""}
    monkeypatch.setattr(processes, "CGROUP_ROOT", root)
    monkeypatch.setattr(
        processes,
        "_unit_properties",
        lambda _unit, **_kwargs: {"ControlGroup": "/user.slice/squinch.service"},
    )
    monkeypatch.setattr(processes, "proc_identity", lambda _pid: identity)

    assert processes.service_members(service) == [identity]
    assert service["cgroup"] == "/user.slice/squinch.service"


def test_service_launch_owns_command_environment_and_cgroup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    invocations: list[list[str]] = []
    published: list[dict] = []

    class Process:
        returncode = None
        pid = 90

        def poll(self) -> None:
            return None

    def launch(arguments, **_kwargs):
        invocations.append(arguments)
        return Process()

    identity = {
        "pid": 91, "ppid": 1, "pgrp": 91, "session": 91,
        "start_ticks": 10, "state": "S",
    }
    wrapper_identity = {
        "pid": 90, "ppid": 1, "pgrp": 90, "session": 90,
        "start_ticks": 9, "state": "S",
    }
    monkeypatch.setattr(processes.subprocess, "Popen", launch)
    monkeypatch.setattr(
        processes,
        "_unit_properties",
        lambda _unit: {
            "MainPID": "91",
            "ControlGroup": "/user.slice/squinch-mc-test.service",
            "ActiveState": "active",
            "SubState": "running",
        },
    )
    monkeypatch.setattr(
        processes,
        "proc_identity",
        lambda pid: wrapper_identity if pid == 90 else identity,
    )

    process, service, main = processes.launch_service(
        unit="squinch-mc-test.service",
        command=["bash", "./gradlew", ":fabric:runServer"],
        cwd=tmp_path,
        environment={"JAVA_HOME": "/jdk", "EMPTY": ""},
        output=io.BytesIO(),
        publish_start=lambda _process, service, wrapper: published.append({
            "service": service.copy(), "wrapper": wrapper,
        }),
    )

    assert process.pid == 90
    assert main == identity
    assert service == {
        "unit": "squinch-mc-test.service",
        "cgroup": "/user.slice/squinch-mc-test.service",
        "wrapper": wrapper_identity,
    }
    assert published == [
        {
            "service": {
                "unit": "squinch-mc-test.service",
                "cgroup": "",
                "wrapper": None,
            },
            "wrapper": None,
        },
        {
            "service": {
                "unit": "squinch-mc-test.service",
                "cgroup": "",
                "wrapper": wrapper_identity,
            },
            "wrapper": wrapper_identity,
        },
    ]
    command = invocations[0]
    assert "--property=KillMode=control-group" in command
    assert "--setenv=JAVA_HOME=/jdk" in command
    assert "--setenv=EMPTY=" in command
    assert command[-3:] == ["bash", "./gradlew", ":fabric:runServer"]


def test_service_launch_waits_through_initial_inactive_unit_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        returncode = None
        pid = 90

        def poll(self) -> None:
            return None

    wrapper_identity = {
        "pid": 90, "ppid": 1, "pgrp": 90, "session": 90,
        "start_ticks": 9, "state": "S",
    }
    main_identity = {
        "pid": 91, "ppid": 1, "pgrp": 91, "session": 91,
        "start_ticks": 10, "state": "S",
    }
    observations = iter((
        {
            "MainPID": "0", "ControlGroup": "",
            "ActiveState": "inactive", "SubState": "dead",
        },
        {
            "MainPID": "91",
            "ControlGroup": "/user.slice/squinch-mc-test.service",
            "ActiveState": "active", "SubState": "running",
        },
    ))
    monkeypatch.setattr(processes.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(processes, "_unit_properties", lambda _unit: next(observations))
    monkeypatch.setattr(
        processes,
        "proc_identity",
        lambda pid: wrapper_identity if pid == 90 else main_identity,
    )
    monkeypatch.setattr(processes.time, "sleep", lambda _seconds: None)

    _process, service, main = processes.launch_service(
        unit="squinch-mc-test.service",
        command=["bash", "./gradlew", ":fabric:runServer"],
        cwd=tmp_path,
        environment={},
        output=io.BytesIO(),
        publish_start=lambda *_args: None,
    )

    assert service["cgroup"] == "/user.slice/squinch-mc-test.service"
    assert main == main_identity


def test_service_launch_publishes_recovery_intent_before_wrapper_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[dict] = []
    killed: list[bool] = []

    class Process:
        pid = 90

        def kill(self) -> None:
            killed.append(True)

    monkeypatch.setattr(processes.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(processes, "proc_identity", lambda _pid: None)

    with pytest.raises(InvestigationError, match="wrapper identity"):
        processes.launch_service(
            unit="squinch-mc-test.service",
            command=["bash", "./gradlew", ":fabric:runServer"],
            cwd=tmp_path,
            environment={},
            output=io.BytesIO(),
            publish_start=lambda _process, service, wrapper: published.append({
                "service": service.copy(), "wrapper": wrapper,
            }),
        )

    assert published == [{
        "service": {
            "unit": "squinch-mc-test.service",
            "cgroup": "",
            "wrapper": None,
        },
        "wrapper": None,
    }]
    assert killed == [True]


def test_proc_identity_bounds_each_procfs_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked_read(_path: Path, *, encoding: str) -> str:
        time.sleep(5)
        return ""

    monkeypatch.setattr(processes.Path, "read_text", blocked_read)
    started = time.monotonic()

    assert processes._read_proc_text(41, "stat", timeout=0.02) is None
    assert time.monotonic() - started < 0.5


def test_proc_identity_refuses_unbounded_worker_thread_reads() -> None:
    result: list[dict | None] = []
    worker = threading.Thread(target=lambda: result.append(processes.proc_identity(41)))

    worker.start()
    worker.join(timeout=0.5)

    assert not worker.is_alive()
    assert result == [None]


def test_transient_uninterruptible_state_is_not_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = {
        "pid": 41, "ppid": 1, "pgrp": 41, "session": 41,
        "start_ticks": 2, "state": "D",
    }
    observations = iter((identity, {**identity, "state": "S"}))
    monkeypatch.setattr(processes, "proc_identity", lambda _pid: next(observations))
    monkeypatch.setattr(processes.time, "sleep", lambda _seconds: None)

    assert processes.confirm_uninterruptible(identity) is None


def test_kernel_diagnostics_never_reads_unsafe_procfs_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = {
        "pid": 41, "ppid": 1, "pgrp": 41, "session": 41,
        "start_ticks": 2, "state": "D",
    }
    reads: list[str] = []
    monkeypatch.setattr(processes, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(processes, "proc_identity", lambda _pid: identity)

    def read(_pid: int, field: str) -> str:
        reads.append(field)
        return field

    monkeypatch.setattr(processes, "_read_proc_text", read)

    result = processes.process_kernel_diagnostics(identity)

    assert reads == ["wchan", "status"]
    assert result["stack"] is None
    assert result["stack_unavailable_reason"] == "unsafe procfs pseudo-file"


def test_owned_process_health_scan_has_one_global_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_root = tmp_path / "active"
    active_root.mkdir()
    for index in range(2):
        (active_root / f"run-{index}.json").write_text(json.dumps({
            "ownership": server.OWNERSHIP,
            "run_id": f"run-{index}",
            "owned_processes": [{
                "pid": 40 + index,
                "ppid": 1,
                "pgrp": 40 + index,
                "session": 40 + index,
                "start_ticks": index + 1,
            }],
        }))
    clock = iter((0.0, 0.05, 0.2))
    monkeypatch.setattr(server.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(server, "proc_identity", lambda _pid: None)

    with pytest.raises(InvestigationError) as failure:
        server.uninterruptible_owned_processes(active_root, timeout=0.1)

    assert failure.value.code == "host_health_inconclusive"


def test_start_refuses_globally_tracked_uninterruptible_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    (project / "fabric" / "run").mkdir(parents=True)
    gradlew = project / "gradlew"
    gradlew.write_text("#!/usr/bin/env bash\nexit 99\n")

    state_root = tmp_path / "state"
    active_root = state_root / "active"
    active_root.mkdir(parents=True)
    identity = {
        "pid": 44,
        "ppid": 1,
        "pgrp": 44,
        "session": 44,
        "start_ticks": 123,
        "state": "S",
    }
    (active_root / "other-project.json").write_text(json.dumps({
        "ownership": server.OWNERSHIP,
        "run_id": "blocked-run",
        "project": "/other/project",
        "loader": "fabric",
        "owned_processes": [identity],
    }))
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: active_root / "requested-project.json")
    monkeypatch.setattr(server, "proc_identity", lambda pid: {**identity, "state": "D"} if pid == 44 else None)

    with pytest.raises(InvestigationError, match="uninterruptible sleep") as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=10,
            retention="discard",
        )

    assert failure.value.code == "host_degraded"
    assert failure.value.details["processes"][0]["run_id"] == "blocked-run"


def test_server_preparation_failure_restores_files_and_removes_unlaunched_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    properties = run_dir / "server.properties"
    properties.write_text("motd=preserve\n")
    state_root = tmp_path / "state"
    artifact_dir = state_root / "runs" / "fixed-run"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "new_run_id", lambda: "fixed-run")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")
    original_backup = server._backup_file
    calls = 0

    def fail_second_backup(path: Path, target: Path, relative: Path | None = None) -> dict:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise InvestigationError("backup_failed", "injected backup failure")
        return original_backup(path, target, relative)

    monkeypatch.setattr(server, "_backup_file", fail_second_backup)

    with pytest.raises(InvestigationError, match="injected backup failure"):
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=10,
            retention="discard",
        )

    assert properties.read_text() == "motd=preserve\n"
    assert not (run_dir / "eula.txt").exists()
    assert not artifact_dir.exists()
    assert not (state_root / "active.json").exists()


def test_server_launcher_identity_is_required_before_files_are_mutated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    properties = run_dir / "server.properties"
    properties.write_text("motd=preserve\n")
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "proc_identity", lambda _pid: None)

    with pytest.raises(InvestigationError) as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=10,
            retention="discard",
        )

    assert failure.value.code == "process_identity_failed"
    assert properties.read_text() == "motd=preserve\n"
    assert not (run_dir / "eula.txt").exists()
    assert not (state_root / "runs").exists()


def test_unpublished_live_server_retains_recoverable_state_and_prepared_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    properties = run_dir / "server.properties"
    properties.write_text("motd=preserve\n")
    state_root = tmp_path / "state"
    recorded: list[dict] = []
    launcher = {
        "pid": 40, "ppid": 1, "pgrp": 40, "session": 40,
        "start_ticks": 1, "state": "S",
    }
    identity = {
        "pid": 41, "ppid": 40, "pgrp": 41, "session": 41,
        "start_ticks": 2, "state": "S",
    }
    wrapper = {
        "pid": 42, "ppid": 40, "pgrp": 42, "session": 42,
        "start_ticks": 3, "state": "S",
    }

    class Process:
        pid = 42

    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "new_run_id", lambda: "fixed-run")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")
    monkeypatch.setattr(server, "proc_identity", lambda _pid: launcher)
    monkeypatch.setattr(server, "git_status", lambda _project: "clean")
    monkeypatch.setattr(server, "sourced_environment", dict)
    def launch(**kwargs):
        process = Process()
        service = {
            "unit": "squinch-mc-fixed-run.service",
            "cgroup": "/owned",
            "wrapper": wrapper,
        }
        kwargs["publish_start"](process, service, wrapper)
        return process, service, identity

    monkeypatch.setattr(server, "launch_service", launch)
    def retain_process(state: dict, *_args, **_kwargs) -> list[str]:
        state["remaining_owned_processes"] = [wrapper]
        return ["owned server processes remain alive"]

    monkeypatch.setattr(server, "terminate_owned_service", retain_process)
    monkeypatch.setattr(server, "_refresh_owned_processes", lambda _state: [wrapper])
    writes = 0

    def write_active(state: dict) -> None:
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("injected initial state failure")
        recorded.append(state.copy())

    monkeypatch.setattr(server, "_write_active", write_active)

    with pytest.raises(CleanupError) as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=10,
            retention="discard",
        )

    assert failure.value.details["recovery_required"] is True
    assert recorded[0]["lifecycle"] == "cleanup_failed"
    assert recorded[0]["launcher"] == launcher
    assert properties.read_text() != "motd=preserve\n"
    assert (run_dir / "eula.txt").exists()
    assert (state_root / "runs" / "fixed-run").exists()


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

    assert server._remove_forceload_regions(state, server.Deadline(30)) == []
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
def test_rcon_ready_without_probe_boundary_fails_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    with pytest.raises(InvestigationError) as caught:
        server.start_server(
            project.resolve(),
            "fabric",
            seed="123",
            datapacks=[],
            properties={"fake-protocol-ready": "false"},
            timeout=10,
            retention="discard",
        )

    assert caught.value.code == "startup_probe_boundary_missing"
    assert caught.value.details["cleanup_complete"] is True
    assert not (state_root / "active.json").exists()


@pytest.mark.slow
def test_probe_boundary_without_listeners_detects_crashed_minecraft_before_wrapper_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    gradlew = project / "gradlew"
    gradlew.write_text(
        "#!/usr/bin/env bash\n"
        "bash -c 'printf \"[squinch-investigate] protocol ready run=%s pid=%s\\n\" "
        "\"$SQUINCH_INVESTIGATE_RUN_ID\" \"$BASHPID\"'\n"
        "sleep 60\n"
    )
    gradlew.chmod(0o644)

    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    started = time.monotonic()
    with pytest.raises(InvestigationError, match="exited before RCON readiness") as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=30,
            retention="discard",
        )
    elapsed = time.monotonic() - started

    assert elapsed < 15
    assert failure.value.code == "startup_exited"
    assert failure.value.details["cleanup_complete"] is True
    assert not (state_root / "active.json").exists()


@pytest.mark.slow
def test_terminal_launch_log_detects_crashed_minecraft_before_wrapper_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    gradlew = project / "gradlew"
    gradlew.write_text(
        "#!/usr/bin/env bash\n"
        "printf '[main/ERROR] (Minecraft) Failed to start the minecraft server\\n'\n"
        "sleep 60\n"
    )
    gradlew.chmod(0o644)

    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    started = time.monotonic()
    with pytest.raises(InvestigationError, match="terminal failure") as failure:
        server.start_server(
            project.resolve(),
            "fabric",
            seed=None,
            datapacks=[],
            properties={},
            timeout=30,
            retention="discard",
        )
    elapsed = time.monotonic() - started

    assert elapsed < 10
    assert failure.value.code == "startup_exited"
    assert "Failed to start the minecraft server" in failure.value.details["terminal_log"]
    assert failure.value.details["cleanup_complete"] is True
    assert not (state_root / "active.json").exists()


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
        "operation": "server",
        "lifecycle": "starting",
        "service": {"unit": "squinch-mc-test.service", "cgroup": "/test"},
        "launcher": {"pid": 33, "ppid": 1, "pgrp": 33, "session": 33, "start_ticks": 1},
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [{"pid": 44, "pgrp": 44, "session": 44, "start_ticks": 1}],
        "ports": {"server": 25565, "rcon": 25575},
    }
    observed: dict[str, object] = {}
    monkeypatch.setattr(server, "load_owned_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(
        server,
        "identity_matches",
        lambda identity: identity["pid"] == 44,
    )
    monkeypatch.setattr(server, "service_members", lambda _service: [])
    monkeypatch.setattr(server, "port_is_free", lambda _port: True)

    def stop(_project: Path, _loader: str, **kwargs: object) -> dict:
        observed.update(kwargs)
        return {"recovered": True}

    monkeypatch.setattr(server, "stop_server", stop)

    assert server.recover(Path("project"), "fabric", 30) == {"recovered": True}
    assert observed == {"successful": False, "timeout": 30, "allow_orphaned_starting": True}


def test_recover_refuses_a_starting_run_with_live_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "operation": "server",
        "lifecycle": "starting",
        "service": {"unit": "squinch-mc-test.service", "cgroup": "/test"},
        "launcher": {"pid": 33, "pgrp": 33, "session": 33, "start_ticks": 1},
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [{"pid": 44, "pgrp": 44, "session": 44, "start_ticks": 1}],
        "ports": {"server": 25565, "rcon": 25575},
    }
    monkeypatch.setattr(server, "load_owned_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(server, "service_members", lambda _service: [])
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
        "operation": "server",
        "lifecycle": "starting",
        "service": {"unit": "squinch-mc-test.service", "cgroup": "/test"},
        "process": {"pid": 44, "ppid": 33, "pgrp": 44, "session": 44, "start_ticks": 1},
        "owned_processes": [],
        "ports": {"server": 25565, "rcon": 25575},
        "run_dir": str(run_dir),
        "artifact_dir": str(tmp_path / "artifacts"),
        "active_path": str(active),
        "managed_files": [],
        "companion_artifacts": [{"materialized_path": str(companion)}],
    }
    monkeypatch.setattr(server, "load_owned_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "load_active", lambda _project, _loader: state)
    monkeypatch.setattr(server, "identity_matches", lambda _identity: False)
    monkeypatch.setattr(server, "service_members", lambda _service: [])
    monkeypatch.setattr(server, "port_is_free", lambda _port: True)
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: tmp_path / "lock")
    monkeypatch.setattr(server, "_remove_protocol_files", lambda _state: [])
    monkeypatch.setattr(server, "_restore_managed_files", lambda _state: [])
    monkeypatch.setattr(server, "_cleanup_world", lambda _state, successful: None)
    monkeypatch.setattr(server, "_write_manifest", lambda _state: None)
    monkeypatch.setattr(server, "stop_service", lambda _service: None)

    result = server.recover(Path("project"), "neoforge", 30)

    assert result["cleanup"]["complete"] is True
    assert not companion.exists()
    assert not active.exists()


def test_server_teardown_defers_signal_and_reports_retained_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "run_id": "run-1",
        "artifact_dir": "/artifacts/run-1",
        "log_path": "/artifacts/run-1/server.log",
    }

    def stop(*_args, **_kwargs):
        os.kill(os.getpid(), signal.SIGINT)
        return state

    monkeypatch.setattr(server, "_stop_server", stop)

    with pytest.raises(InvestigationError) as caught:
        server.stop_server(Path("project"), "fabric", successful=False, timeout=1)

    assert caught.value.code == "interrupted"
    assert caught.value.details["run_id"] == "run-1"
    assert caught.value.details["cleanup_complete"] is True
