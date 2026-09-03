from __future__ import annotations

import json
import os
import signal
from pathlib import Path

import pytest

from squinch_minecraft_investigate import owned_operation
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError


def _identity(pid: int) -> dict:
    return {
        "pid": pid,
        "ppid": 1,
        "pgrp": pid,
        "session": pid,
        "start_ticks": pid,
        "state": "S",
    }


class _Wrapper:
    pid = 40
    returncode = 0

    def poll(self) -> int:
        return 0


def _arguments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    artifact = tmp_path / "run"
    active = tmp_path / "active" / "state.json"
    service = {
        "unit": "squinch-mc-run-1.service",
        "cgroup": "/test",
        "wrapper": _identity(40),
    }
    monkeypatch.setattr(owned_operation, "proc_identity", lambda _pid: _identity(39))
    def launch(**kwargs):
        wrapper = _Wrapper()
        kwargs["publish_start"](wrapper, service, service["wrapper"])
        return wrapper, service, _identity(41)

    monkeypatch.setattr(owned_operation, "launch_service", launch)
    monkeypatch.setattr(owned_operation, "live_owned_processes", lambda _state, *_args: [])
    monkeypatch.setattr(owned_operation, "wait_owned_exit", lambda _state, _timeout: True)
    monkeypatch.setattr(
        owned_operation, "terminate_owned_service", lambda _state, _timeout, label: []
    )
    return {
        "project": tmp_path,
        "loader": "fabric",
        "operation": "finite-test",
        "ownership": "test-owner",
        "run_id": "run-1",
        "artifact_dir": artifact,
        "run_dir": artifact,
        "log_path": artifact / "finite-test.log",
        "active_path": active,
        "lock_path": tmp_path / "lock",
        "command": ["false"],
        "environment": {},
        "timeout": 5,
        "load_active": lambda _project, _loader: pytest.fail("unexpected active state"),
    }


def test_finite_service_removes_active_state_only_after_validation_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)

    state, result = owned_operation.run_finite_service(
        **arguments,
        validate=lambda state: {"pid": state["process"]["pid"]},
        state_fields={"input": "retained"},
    )

    assert result == {"pid": 41}
    assert state["lifecycle"] == "succeeded"
    assert state["cleanup"]["complete"] is True
    assert state["input"] == "retained"
    assert not arguments["active_path"].exists()


def test_finite_service_preserves_failure_evidence_after_clean_teardown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)

    def reject(_state: dict) -> None:
        raise InvestigationError("controlled_failure", "validation rejected result")

    with pytest.raises(InvestigationError) as caught:
        owned_operation.run_finite_service(**arguments, validate=reject)

    assert caught.value.code == "controlled_failure"
    assert caught.value.details["cleanup_complete"] is True
    assert not arguments["active_path"].exists()
    manifest = json.loads((arguments["artifact_dir"] / "manifest.json").read_text())
    assert manifest["lifecycle"] == "failed"
    assert manifest["cleanup"]["complete"] is True


def test_finite_service_defers_repeated_signal_until_cleanup_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)
    calls: list[str] = []

    def interrupted(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGINT, interrupted)
    monkeypatch.setattr(
        owned_operation,
        "live_owned_processes",
        lambda _state, *_args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    def terminate(_state: dict, _timeout: float, *, label: str) -> list[str]:
        calls.append(label)
        os.kill(os.getpid(), signal.SIGINT)
        calls.append("finished")
        return []

    monkeypatch.setattr(owned_operation, "terminate_owned_service", terminate)
    try:
        with pytest.raises(InvestigationError) as caught:
            owned_operation.run_finite_service(
                **arguments, validate=lambda _state: pytest.fail("validation must not run")
            )
    finally:
        signal.signal(signal.SIGINT, previous)

    assert calls == ["finite-test", "finished"]
    assert caught.value.code == "interrupted"
    assert caught.value.details["run_id"] == "run-1"
    assert caught.value.details["cleanup_complete"] is True
    assert not arguments["active_path"].exists()
    manifest = json.loads((arguments["artifact_dir"] / "manifest.json").read_text())
    assert manifest["lifecycle"] == "failed"
    assert manifest["cleanup"]["complete"] is True


def test_finite_service_retains_recoverable_state_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)
    monkeypatch.setattr(
        owned_operation,
        "terminate_owned_service",
        lambda _state, _timeout, label: [f"owned {label} process remains"],
    )

    with pytest.raises(CleanupError, match="cleanup did not complete"):
        owned_operation.run_finite_service(
            **arguments, validate=lambda _state: {"status": "pass"}
        )

    retained = json.loads(arguments["active_path"].read_text())
    assert retained["lifecycle"] == "cleanup_failed"
    assert retained["cleanup"]["complete"] is False


def test_finite_service_rejects_state_that_overrides_ownership_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)
    with pytest.raises(InvestigationError, match="override ownership"):
        owned_operation.run_finite_service(
            **arguments,
            validate=lambda _state: None,
            state_fields={"process": {"pid": 999}},
        )


def test_finite_service_checks_active_state_before_creating_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)
    arguments["active_path"].parent.mkdir(parents=True)
    arguments["active_path"].write_text("{}")
    arguments["load_active"] = lambda _project, _loader: {
        "run_id": "existing", "operation": "client"
    }

    with pytest.raises(InvestigationError, match="already active"):
        owned_operation.run_finite_service(
            **arguments,
            prepare=lambda: pytest.fail("preparation must not run"),
            validate=lambda _state: None,
        )

    assert not arguments["artifact_dir"].exists()


def test_finite_service_removes_unlaunched_preparation_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)

    def fail_preparation() -> None:
        (arguments["artifact_dir"] / "partial").write_text("partial")
        raise InvestigationError("preparation_failed", "controlled preparation failure")

    with pytest.raises(InvestigationError, match="controlled preparation failure"):
        owned_operation.run_finite_service(
            **arguments,
            prepare=fail_preparation,
            validate=lambda _state: None,
        )

    assert not arguments["artifact_dir"].exists()


def test_finite_service_retains_live_owner_when_initial_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments = _arguments(tmp_path, monkeypatch)
    retained: list[dict] = []
    writes = 0

    def write(state: dict) -> None:
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("injected initial manifest failure")
        retained.append(state.copy())

    monkeypatch.setattr(owned_operation, "write_active_manifest", write)
    def retain_process(state: dict, *_args, **_kwargs) -> list[str]:
        state["remaining_owned_processes"] = [_identity(40)]
        return ["owned finite-test process remains"]

    monkeypatch.setattr(owned_operation, "terminate_owned_service", retain_process)
    monkeypatch.setattr(
        owned_operation, "live_owned_processes", lambda _state, *_args: [_identity(40)]
    )

    with pytest.raises(CleanupError) as caught:
        owned_operation.run_finite_service(
            **arguments, validate=lambda _state: pytest.fail("validation must not run")
        )

    assert caught.value.details["recovery_required"] is True
    assert retained[0]["lifecycle"] == "cleanup_failed"
    assert retained[0]["cleanup"]["complete"] is False
    assert arguments["artifact_dir"].exists()


def test_owned_teardown_phases_share_one_monotonic_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 100.0
    identity = _identity(41)
    state = {
        "service": {"unit": "squinch-mc-run-1.service", "cgroup": "/test"},
        "owned_processes": [identity],
    }
    live_results = iter(([identity], [identity], []))
    waits: list[float] = []
    signals: list[float] = []
    stops: list[float] = []

    monkeypatch.setattr(owned_operation.time, "monotonic", lambda: now)
    monkeypatch.setattr(
        owned_operation, "live_owned_processes", lambda _state, *_args: list(next(live_results))
    )
    monkeypatch.setattr(owned_operation, "write_active_manifest", lambda _state: None)
    monkeypatch.setattr(
        owned_operation, "process_kernel_diagnostics", lambda value: {"pid": value["pid"]}
    )
    monkeypatch.setattr(
        owned_operation,
        "signal_service",
        lambda _service, _signal, *, timeout: signals.append(timeout),
    )
    monkeypatch.setattr(
        owned_operation, "signal_recorded_process", lambda _identity, _signal: True
    )

    def wait(_state: dict, timeout: float, _failures: list[str]) -> bool:
        nonlocal now
        waits.append(timeout)
        now += 1.5
        return len(waits) > 1

    monkeypatch.setattr(owned_operation, "wait_owned_exit", wait)
    monkeypatch.setattr(
        owned_operation,
        "stop_service",
        lambda _service, *, timeout: stops.append(timeout),
    )

    assert owned_operation.terminate_owned_service(state, 2.0, label="test") == []
    assert waits == [2.0, 0.5]
    assert signals == [2.0, 0.5]
    assert stops == [0.0]
