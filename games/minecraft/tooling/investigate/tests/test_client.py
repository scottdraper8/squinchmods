from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_minecraft_investigate import client, cli, owned_operation
from squinch_minecraft_investigate.errors import InvestigationError


def _identity(pid: int) -> dict:
    return {
        "pid": pid,
        "ppid": 1,
        "pgrp": pid,
        "session": pid,
        "start_ticks": pid,
        "state": "S",
    }


def test_client_argument_maps_reject_unsafe_or_duplicate_environment_names() -> None:
    assert cli._named_values(["SQUINCH_MODE=ui"], kind="probe") == {
        "SQUINCH_MODE": "ui"
    }
    with pytest.raises(InvestigationError, match="unique SQUINCH_NAME"):
        cli._named_values(["PATH=value"], kind="probe")
    with pytest.raises(InvestigationError, match="unique SQUINCH_NAME"):
        cli._named_values(["SQUINCH_MODE=a", "SQUINCH_MODE=b"], kind="probe")
    with pytest.raises(InvestigationError, match="unique SQUINCH_NAME"):
        cli._named_values(["SQUINCH_MODE=first\nSECOND=value"], kind="probe")
    with pytest.raises(InvestigationError, match="unique SQUINCH_NAME"):
        cli._named_values(["SQUINCH_MODE=value\0suffix"], kind="probe")


def test_client_lifecycle_uses_isolated_run_and_cleans_owned_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    (project / "fabric").mkdir(parents=True)
    (project / "gradlew").write_text("#!/bin/sh\n")
    state_root = tmp_path / "state"
    display_root = tmp_path / "runtime"
    display_root.mkdir()
    active = state_root / "active.json"
    main = _identity(41)
    wrapper_identity = _identity(40)

    class Wrapper:
        returncode = 0
        pid = 40

        def poll(self) -> int:
            return 0

    def launch(**kwargs):
        assert kwargs["environment"]["ALSOFT_DRIVERS"] == "null"
        for variable, value in kwargs["environment"].items():
            if variable == "SQUINCH_RESULT":
                Path(value).write_text(json.dumps({"status": "pass"}))
        wrapper = Wrapper()
        service = {
            "unit": "squinch-mc-test.service",
            "cgroup": "/test",
            "wrapper": wrapper_identity,
        }
        kwargs["publish_start"](wrapper, service, wrapper_identity)
        return wrapper, service, main

    monkeypatch.setattr(client, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(client, "active_path", lambda _project, _loader: active)
    monkeypatch.setattr(client, "lock_path", lambda _project, _loader: state_root / "lock")
    monkeypatch.setattr(client, "git_status", lambda _project: "unchanged")
    monkeypatch.setattr(
        client,
        "sourced_environment",
        lambda: {"PATH": "/bin", "XDG_RUNTIME_DIR": str(display_root)},
    )
    monkeypatch.setattr(owned_operation, "proc_identity", lambda _pid: _identity(39))
    monkeypatch.setattr(owned_operation, "launch_service", launch)
    monkeypatch.setattr(owned_operation, "live_owned_processes", lambda _state: [])
    monkeypatch.setattr(owned_operation, "wait_owned_exit", lambda _state, _timeout: True)
    monkeypatch.setattr(
        owned_operation, "terminate_owned_service", lambda _state, _timeout, label: []
    )
    monkeypatch.setattr(client, "uninterruptible_owned_processes", lambda _root: [])
    monkeypatch.setattr(
        client,
        "probe_overlay_command",
        lambda *_args: (["--overlay"], {
            "runtime_artifacts": [],
            "overlay": "/overlay",
            "runtime": "/runtime",
            "manifest": "/manifest",
            "manifest_sha256": "0" * 64,
            "packs": [],
            "mixins": [],
            "compile_artifacts": [],
            "runtime_output": str(state_root / "mods"),
            "client_run_dir": str(state_root / "client-run"),
            "sentinel": "SQUINCH_DEVELOPMENT_PROBE",
        }),
    )

    result = client.run_client(
        project.resolve(),
        "fabric",
        probe_packs=(tmp_path / "probe",),
        runtime_artifacts=(),
        compile_artifacts=(),
        probe_environment={"SQUINCH_MODE": "ui"},
        result_files={"SQUINCH_RESULT": "result.json"},
        timeout=10,
    )

    assert result["lifecycle"] == "succeeded"
    assert result["results"][0]["result"]["status"] == "pass"
    assert Path(result["run_dir"]).parent == Path(result["artifact_dir"])
    assert (Path(result["run_dir"]) / "options.txt").read_text() == (
        "narrator:0\nonboardAccessibility:false\n"
    )
    assert not Path(result["display"]["runtime_dir"]).exists()
    assert not active.exists()


def test_client_result_rejects_malformed_output(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    state = {"result_files": {"SQUINCH_RESULT": str(path)}}

    path.write_text("not json")
    with pytest.raises(InvestigationError) as invalid:
        client._inspect_results(state)
    assert invalid.value.code == "client_result_invalid"

    path.write_text(json.dumps({"status": "fail"}))
    with pytest.raises(InvestigationError) as failed:
        client._inspect_results(state)
    assert failed.value.code == "client_result_failed"


def test_client_detects_terminal_crash_report(tmp_path: Path) -> None:
    state = {"run_dir": str(tmp_path)}
    assert client._detect_terminal_failure(state) is None

    crash_root = tmp_path / "crash-reports"
    crash_root.mkdir()
    report = crash_root / "crash-test.txt"
    report.write_text("failure")

    failure = client._detect_terminal_failure(state)
    assert isinstance(failure, InvestigationError)
    assert failure.code == "client_crashed"
    assert failure.details == {"crash_reports": [str(report)]}


def test_client_inspects_remapped_runtime_artifact_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source.jar"
    runtime = tmp_path / "runtime.jar"
    evidence = tmp_path / "runtime-artifacts.json"
    source.write_bytes(b"source")
    runtime.write_bytes(b"runtime")
    evidence.write_text(json.dumps([{
        "source_path": str(source),
        "runtime_path": str(runtime),
    }]))
    state = {
        "run_dir": str(tmp_path),
        "probe_overlay": {
            "runtime_evidence": str(evidence),
            "runtime_artifacts": [{
                "id": "example",
                "path": str(source),
                "filename": "source.jar",
                "sha256": client._hash(source),
            }],
        },
    }

    assert client._inspect_runtime_mods(state) == [{
        "id": "example",
        "source_path": str(source),
        "source_sha256": client._hash(source),
        "runtime_path": str(runtime),
        "runtime_sha256": client._hash(runtime),
        "size": 7,
    }]


def test_client_rejects_invalid_runtime_artifact_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "runtime-artifacts.json"
    evidence.write_text("not json")
    state = {
        "run_dir": str(tmp_path),
        "probe_overlay": {
            "runtime_evidence": str(evidence),
            "runtime_artifacts": [],
        },
    }

    with pytest.raises(InvestigationError) as invalid:
        client._inspect_runtime_mods(state)
    assert invalid.value.code == "client_runtime_artifact_invalid"
