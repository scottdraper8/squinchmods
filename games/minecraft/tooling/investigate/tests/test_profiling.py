from __future__ import annotations

from pathlib import Path

import pytest

from squinch_minecraft_investigate import profiling
from squinch_minecraft_investigate.errors import InvestigationError


def test_step_jfr_requires_a_real_nonempty_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a successful-looking JFR command whose recording was never written to the run."""
    state = {"run_id": "run-1234567890", "artifact_dir": str(tmp_path), "owned_processes": []}
    monkeypatch.setattr(profiling, "_minecraft_jvm", lambda _state, _command: 42)
    commands: list[tuple[str, ...]] = []

    def fake_jcmd(_command: Path, _pid: int, *arguments: str) -> str:
        commands.append(arguments)
        return "Started recording 1." if arguments[0] == "JFR.start" else "Stopped recording 1."

    monkeypatch.setattr(profiling, "_run_jcmd", fake_jcmd)

    recording = profiling.start_jfr(state, "generate-window", None)
    with pytest.raises(InvestigationError, match="was not created"):
        profiling.stop_jfr(recording, None)

    recording.path.write_bytes(b"real-jfr-bytes")
    result = profiling.stop_jfr(recording, None)
    assert not any(argument.startswith("filename=") for argument in commands[0])
    assert f"filename={recording.path}" in commands[-1]
    assert result["scope"] == "scenario-step"
    assert result["size"] == len(b"real-jfr-bytes")
    assert len(result["sha256"]) == 64


@pytest.mark.parametrize(
    "command_line",
    (
        "java_command: net.fabricmc.installer.ServerLauncher nogui",
        "java_command: net.fabricmc.loader.impl.launch.server.FabricServerLauncher nogui",
        "java_command: net.minecraft.server.Main nogui",
        "java_command: cpw.mods.bootstraplauncher.BootstrapLauncher @neoforge_args.txt nogui",
    ),
)
def test_minecraft_jvm_recognizes_production_launchers(
    monkeypatch: pytest.MonkeyPatch, command_line: str
) -> None:
    monkeypatch.setattr(profiling, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(profiling, "_run_jcmd", lambda _command, _pid, *_args: command_line)

    assert profiling._minecraft_jvm({"owned_processes": [{"pid": 42}]}, Path("jcmd")) == 42


def test_minecraft_jvm_rejects_gradle_wrappers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiling, "identity_matches", lambda _identity: True)
    monkeypatch.setattr(
        profiling,
        "_run_jcmd",
        lambda _command, _pid, *_args: "java_command: org.gradle.wrapper.GradleWrapperMain",
    )

    with pytest.raises(InvestigationError, match="found 0"):
        profiling._minecraft_jvm({"owned_processes": [{"pid": 42}]}, Path("jcmd"))


def test_jfr_host_health_returns_none_for_healthy_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profiling, "proc_identity", lambda _pid: {"pid": 42, "state": "S"})
    state = {"owned_processes": [{"pid": 42}], "run_id": "run-1"}
    assert profiling.verify_jfr_host_health(state) is None


def test_jfr_host_health_detects_uninterruptible_process(monkeypatch: pytest.MonkeyPatch) -> None:
    identity = {"pid": 42, "state": "D", "start_ticks": 100, "pgrp": 42, "session": 42}
    monkeypatch.setattr(profiling, "proc_identity", lambda _pid: identity)
    monkeypatch.setattr(profiling, "confirm_uninterruptible", lambda _expected, **_kw: identity)
    state = {"owned_processes": [identity], "run_id": "run-1"}
    result = profiling.verify_jfr_host_health(state)
    assert result is not None
    assert result.code == "jfr_host_degraded"
