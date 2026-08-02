from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from squinch_minecraft_investigate import server
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.processes import port_is_free


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

    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    state = server.start_server(
        project.resolve(),
        "fabric",
        seed="123",
        datapacks=[first_datapack, second_datapack],
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

    result = server.stop_server(project.resolve(), "fabric", successful=True, timeout=0.5)

    assert result["cleanup"]["complete"] is True
    assert port_is_free(state["ports"]["server"])
    assert port_is_free(state["ports"]["rcon"])
    assert (run_dir / "server.properties").read_text() == original_properties
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
