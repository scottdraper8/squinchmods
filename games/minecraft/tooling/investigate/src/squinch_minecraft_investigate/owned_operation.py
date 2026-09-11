from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable, TypeVar, cast

from .errors import CleanupError, InvestigationError
from .output import timestamp
from .processes import (
    confirm_uninterruptible,
    identity_matches,
    launch_service,
    process_kernel_diagnostics,
    proc_identity,
    service_members,
    signal_recorded_process,
    signal_service,
    stop_service,
)
from .state import atomic_write_json, project_lock

T = TypeVar("T")


@contextlib.contextmanager
def defer_termination_signals():
    pending: list[int] = []

    def record(signum: int, _frame: object) -> None:
        pending.append(signum)

    previous = {
        signum: signal.signal(signum, record)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    try:
        yield pending
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


class Deadline:
    def __init__(self, timeout: float):
        if timeout <= 0:
            raise InvestigationError("operation_timeout_invalid", "timeout must be positive")
        self._end = time.monotonic() + timeout

    def remaining(self, cap: float | None = None) -> float:
        value = max(0.0, self._end - time.monotonic())
        return value if cap is None else min(value, cap)

    def expired(self) -> bool:
        return self.remaining() <= 0.0


def write_active_manifest(state: dict) -> None:
    atomic_write_json(Path(state["active_path"]), state)
    atomic_write_json(Path(state["artifact_dir"]) / "manifest.json", state)


def live_owned_processes(state: dict, timeout: float = 5.0) -> list[dict]:
    recorded = {int(item["pid"]): item for item in state.get("owned_processes", [])}
    for identity in service_members(state["service"], timeout=timeout):
        recorded[identity["pid"]] = identity
    state["owned_processes"] = sorted(recorded.values(), key=lambda item: item["pid"])
    return [item for item in state["owned_processes"] if identity_matches(item)]


def wait_owned_exit(
    state: dict, timeout: float, persistence_failures: list[str] | None = None
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        before = len(state["owned_processes"])
        remaining = max(0.0, deadline - time.monotonic())
        if not live_owned_processes(state, min(remaining, 5.0)):
            return True
        if len(state["owned_processes"]) != before:
            try:
                write_active_manifest(state)
            except OSError as exc:
                if persistence_failures is not None:
                    persistence_failures.append(f"could not persist expanded process ownership: {exc}")
        time.sleep(0.2)
    return not live_owned_processes(state, 0.0)


def terminate_owned_service(state: dict, timeout: float, *, label: str) -> list[str]:
    deadline = Deadline(timeout)
    failures: list[str] = []
    live = live_owned_processes(state, deadline.remaining(5.0))
    if live:
        state["teardown_process_diagnostics"] = [
            process_kernel_diagnostics(item) for item in live
        ]
        try:
            write_active_manifest(state)
        except OSError as exc:
            failures.append(f"could not persist teardown diagnostics: {exc}")
        try:
            signal_service(
                state["service"], signal.SIGTERM, timeout=deadline.remaining(5.0)
            )
        except InvestigationError as exc:
            failures.append(str(exc))
        for identity in live:
            try:
                signal_recorded_process(identity, signal.SIGTERM)
            except OSError as exc:
                failures.append(f"failed to signal owned pid {identity['pid']}: {exc}")
        if not wait_owned_exit(state, deadline.remaining(10.0), failures):
            try:
                signal_service(
                    state["service"], signal.SIGKILL, timeout=deadline.remaining(5.0)
                )
            except InvestigationError as exc:
                failures.append(str(exc))
            for identity in live_owned_processes(state, deadline.remaining(5.0)):
                try:
                    signal_recorded_process(identity, signal.SIGKILL)
                except OSError as exc:
                    failures.append(f"failed to kill owned pid {identity['pid']}: {exc}")
            wait_owned_exit(state, deadline.remaining(5.0), failures)
    try:
        stop_service(state["service"], timeout=deadline.remaining(5.0))
    except InvestigationError as exc:
        failures.append(str(exc))
    remaining = live_owned_processes(state, deadline.remaining(5.0))
    state["remaining_owned_processes"] = remaining
    if remaining:
        failures.append(
            f"owned {label} processes remain alive: {[item['pid'] for item in remaining]}"
        )
    return failures


def run_finite_service(
    *,
    project: Path,
    loader: str,
    operation: str,
    ownership: str,
    run_id: str,
    artifact_dir: Path,
    run_dir: Path,
    log_path: Path,
    active_path: Path,
    lock_path: Path,
    command: list[str],
    environment: dict[str, str],
    timeout: float,
    load_active: Callable[[Path, str], dict],
    validate: Callable[[dict], T],
    poll_failure: Callable[[dict], BaseException | None] | None = None,
    poll_complete: Callable[[dict], bool] | None = None,
    prepare: Callable[[], None] | None = None,
    cleanup: Callable[[dict], list[str]] | None = None,
    state_fields: dict | None = None,
) -> tuple[dict, T]:
    if timeout <= 0:
        raise InvestigationError("process_service_invalid", "operation timeout must be positive")
    reserved = {
        "ownership", "schema_version", "operation", "run_id", "lifecycle", "started_at",
        "finished_at", "project", "loader", "run_dir", "artifact_dir", "log_path",
        "active_path", "process", "service", "launcher", "owned_processes", "command",
        "cleanup", "remaining_owned_processes", "teardown_process_diagnostics",
    }
    overlap = reserved & set(state_fields or {})
    if overlap:
        raise InvestigationError(
            "process_service_invalid",
            f"operation state fields override ownership fields: {sorted(overlap)}",
        )
    launcher = proc_identity(os.getpid())
    if launcher is None:
        raise InvestigationError(
            "process_identity_failed", f"could not retain {operation} launcher identity"
        )
    wrapper: subprocess.Popen[bytes] | None = None
    state = {
        "ownership": ownership,
        "schema_version": 3,
        "operation": operation,
        "run_id": run_id,
        "lifecycle": "launching",
        "started_at": timestamp(),
        "finished_at": None,
        "project": str(project),
        "loader": loader,
        "run_dir": str(run_dir),
        "artifact_dir": str(artifact_dir),
        "log_path": str(log_path),
        "active_path": str(active_path),
        "process": None,
        "service": None,
        "launcher": launcher,
        "owned_processes": [],
        "command": command,
        "cleanup": {"complete": False, "failures": []},
        **(state_fields or {}),
    }
    launch_owned = False
    artifact_created = False
    with project_lock(lock_path):
        if active_path.exists():
            existing = load_active(project, loader)
            raise InvestigationError(
                "already_active",
                f"an investigation is already active for {project}/{loader}",
                details={
                    "run_id": existing["run_id"],
                    "operation": existing["operation"],
                },
            )
        try:
            artifact_dir.mkdir(parents=True, exist_ok=False)
            artifact_created = True
            if prepare is not None:
                prepare()

            def publish_start(
                launched_wrapper: subprocess.Popen[bytes] | None,
                launched_service: dict,
                wrapper_identity: dict | None,
            ) -> None:
                nonlocal launch_owned
                state["service"] = launched_service
                state["process"] = wrapper_identity
                state["owned_processes"] = (
                    [wrapper_identity] if wrapper_identity is not None else []
                )
                launch_owned = True
                write_active_manifest(state)

            with log_path.open("wb") as output:
                wrapper, service, identity = launch_service(
                    unit=f"squinch-mc-{run_id.lower()}.service",
                    command=command,
                    cwd=project,
                    environment=environment,
                    output=output,
                    publish_start=publish_start,
                    runtime_max_seconds=timeout + 20.0,
                )
            state["lifecycle"] = "running"
            state["process"] = identity
            state["service"] = service
            state["owned_processes"] = [identity, service["wrapper"]]
            write_active_manifest(state)
        except BaseException as original:
            with defer_termination_signals():
                failures: list[str] = []
                alive = False
                if launch_owned:
                    try:
                        failures.extend(terminate_owned_service(state, 15.0, label=operation))
                    except BaseException as exc:
                        failures.append(f"{operation} launch cleanup failed: {exc}")
                    alive = bool(state.get("remaining_owned_processes"))
                if alive:
                    state["lifecycle"] = "cleanup_failed"
                    state["failure"] = str(original)
                    state["cleanup"] = {"complete": False, "failures": failures}
                    try:
                        write_active_manifest(state)
                    except OSError as exc:
                        failures.append(f"could not retain active recovery state: {exc}")
                        with contextlib.suppress(OSError):
                            atomic_write_json(artifact_dir / "manifest.json", state)
                else:
                    if launch_owned and active_path.exists():
                        try:
                            active_path.unlink()
                        except OSError as exc:
                            failures.append(f"active state {active_path}: {exc}")
                    if artifact_created and not failures:
                        try:
                            shutil.rmtree(artifact_dir)
                        except OSError as exc:
                            failures.append(f"artifact directory {artifact_dir}: {exc}")
            if failures:
                raise CleanupError(
                    f"{operation} launch failed and rollback did not complete",
                    details={
                        "launch_error": str(original),
                        "run_id": run_id,
                        "artifact_dir": str(artifact_dir),
                        "failures": failures,
                        "recovery_required": alive,
                    },
                ) from original
            raise

    assert wrapper is not None
    failure: BaseException | None = None
    validated: T | None = None
    deadline = time.monotonic() + timeout
    completed_while_running = False
    try:
        while time.monotonic() < deadline:
            live = live_owned_processes(state)
            blocked = [
                confirmed
                for item in live
                if item.get("state") == "D"
                and (confirmed := confirm_uninterruptible(item)) is not None
            ]
            if blocked:
                raise InvestigationError(
                    "host_degraded",
                    f"an investigation-owned {operation} process entered uninterruptible sleep",
                    details={"processes": blocked, "log_path": str(log_path)},
                )
            if poll_failure is not None:
                detected = poll_failure(state)
                if detected is not None:
                    raise detected
            if poll_complete is not None and poll_complete(state):
                completed_while_running = True
                break
            if wrapper.poll() is not None:
                break
            time.sleep(0.25)
        else:
            raise InvestigationError(
                f"{operation.replace('-', '_')}_timeout",
                f"{operation} exceeded {timeout:g} seconds",
            )
        if not completed_while_running and wrapper.returncode != 0:
            raise InvestigationError(
                f"{operation.replace('-', '_')}_failed",
                f"{operation} exited with code {wrapper.returncode}",
            )
        if not completed_while_running and not wait_owned_exit(state, 5.0):
            raise InvestigationError(
                f"{operation.replace('-', '_')}_process_leak",
                f"{operation} service remained active after launch exit",
            )
        validated = validate(state)
    except BaseException as exc:
        failure = exc

    with defer_termination_signals() as pending_signals:
        cleanup_failures = terminate_owned_service(state, 15.0, label=operation)
        if cleanup is not None:
            try:
                cleanup_failures.extend(cleanup(state))
            except BaseException as exc:
                cleanup_failures.append(f"{operation} cleanup callback failed: {exc}")
        if failure is None and pending_signals:
            failure = KeyboardInterrupt()
        state["finished_at"] = timestamp()
        state["cleanup"] = {"complete": not cleanup_failures, "failures": cleanup_failures}
        state["lifecycle"] = "succeeded" if failure is None and not cleanup_failures else "failed"
        if failure is not None:
            state["failure"] = str(failure)
        write_active_manifest(state)
        if cleanup_failures:
            state["lifecycle"] = "cleanup_failed"
            write_active_manifest(state)
        else:
            active_path.unlink()
    if cleanup_failures:
        raise CleanupError(
            f"{operation} cleanup did not complete",
            details={
                "run_id": run_id,
                "artifact_dir": str(artifact_dir),
                "log_path": str(log_path),
                "failures": cleanup_failures,
            },
        ) from failure
    if failure is not None:
        if isinstance(failure, InvestigationError):
            failure.details.update({
                "run_id": run_id,
                "artifact_dir": str(artifact_dir),
                "log_path": str(log_path),
                "cleanup_complete": True,
            })
        if isinstance(failure, KeyboardInterrupt):
            raise InvestigationError(
                "interrupted",
                f"{operation} interrupted by signal",
                details={
                    "run_id": run_id,
                    "artifact_dir": str(artifact_dir),
                    "log_path": str(log_path),
                    "cleanup_complete": True,
                },
            ) from failure
        raise failure
    return state, cast(T, validated)


def recover_finite_service(
    *,
    project: Path,
    loader: str,
    timeout: float,
    lock_path: Path,
    load_active: Callable[[Path, str], dict],
    operations: set[str],
    cleanup: Callable[[dict], list[str]] | None = None,
) -> dict:
    state = load_active(project, loader)
    if state["operation"] not in operations:
        raise InvestigationError(
            "operation_mismatch",
            f"active operation is {state['operation']}, expected one of {sorted(operations)}",
        )
    with project_lock(lock_path):
        state = load_active(project, loader)
        if state["operation"] not in operations:
            raise InvestigationError("operation_mismatch", "active operation changed")
        failures = terminate_owned_service(
            state, timeout, label=str(state["operation"])
        )
        if cleanup is not None:
            try:
                failures.extend(cleanup(state))
            except BaseException as exc:
                failures.append(f"{state['operation']} cleanup callback failed: {exc}")
        state["finished_at"] = timestamp()
        state["cleanup"] = {"complete": not failures, "failures": failures}
        state["lifecycle"] = "failed" if not failures else "cleanup_failed"
        atomic_write_json(Path(state["artifact_dir"]) / "manifest.json", state)
        if failures:
            write_active_manifest(state)
            raise CleanupError(
                f"{state['operation']} recovery was incomplete",
                details={"failures": failures},
            )
        Path(state["active_path"]).unlink()
        return state
