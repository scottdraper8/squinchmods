from __future__ import annotations

import contextlib
import os
import re
import signal
import socket
import stat
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from .errors import InvestigationError

PROC_STAT_TIMEOUT_SECONDS = 0.1
PROC_ROOT = Path("/proc")
CGROUP_ROOT = Path("/sys/fs/cgroup")
SYSTEMD_TIMEOUT_SECONDS = 5.0


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def port_is_free(port: int, *, timeout: float = 5.0) -> bool:
    """Return whether no TCP listener currently accepts connections on localhost."""
    if timeout <= 0:
        return False
    try:
        result = subprocess.run(
            ["ss", "-H", "-ltn", f"sport = :{port}"],
            text=True,
            capture_output=True,
            timeout=min(timeout, 5.0),
            check=False,
        )
        if result.returncode == 0:
            return not bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Fallback for systems without ss. This can touch the listener, so Linux's
    # read-only socket table is preferred above.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(min(timeout, 0.2))
        return connection.connect_ex(("127.0.0.1", port)) != 0


def port_is_available(port: int) -> bool:
    """Return whether a new listener can safely bind the requested port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _read_proc_path_result(
    path: Path, timeout: float = PROC_STAT_TIMEOUT_SECONDS
) -> tuple[str | None, str | None]:
    if timeout <= 0:
        return None, "procfs inspection had no time budget"
    if threading.current_thread() is not threading.main_thread():
        return None, "procfs inspection requires the main thread"
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()

    def timed_out(_signum: int, _frame: object) -> None:
        raise TimeoutError

    try:
        signal.signal(signal.SIGALRM, timed_out)
        signal.siginterrupt(signal.SIGALRM, True)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        return path.read_text(encoding="utf-8"), None
    except (FileNotFoundError, ProcessLookupError):
        return None, None
    except (PermissionError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer != (0.0, 0.0):
            remaining = max(0.000001, previous_timer[0] - (time.monotonic() - started))
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


def _read_proc_path(
    path: Path, timeout: float = PROC_STAT_TIMEOUT_SECONDS
) -> str | None:
    return _read_proc_path_result(path, timeout)[0]


def _read_proc_text(
    pid: int, field: str, timeout: float = PROC_STAT_TIMEOUT_SECONDS
) -> str | None:
    if not field or "/" in field or field in {".", ".."}:
        raise ValueError(f"invalid procfs field: {field!r}")
    return _read_proc_path(PROC_ROOT / str(pid) / field, timeout)


def _parse_stat(pid: int, stat: str) -> dict | None:
    # The comm field is parenthesized and can contain spaces or closing parentheses.
    close = stat.rfind(")")
    if close < 0:
        return None
    fields = stat[close + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        return {
            "pid": pid,
            "state": fields[0],
            "ppid": int(fields[1]),
            "pgrp": int(fields[2]),
            "session": int(fields[3]),
            "start_ticks": int(fields[19]),
        }
    except ValueError:
        return None


def proc_identity(pid: int) -> dict | None:
    stat = _read_proc_text(pid, "stat")
    return None if stat is None else _parse_stat(pid, stat)


def proc_identity_result(pid: int) -> tuple[dict | None, str | None]:
    stat, error = _read_proc_path_result(PROC_ROOT / str(pid) / "stat")
    if stat is None or error is not None:
        return None, error
    identity = _parse_stat(pid, stat)
    if identity is None:
        return None, f"could not parse /proc/{pid}/stat"
    return identity, None


def proc_thread_identity(process_id: int, thread_id: int) -> dict | None:
    stat = _read_proc_path(
        PROC_ROOT / str(process_id) / "task" / str(thread_id) / "stat"
    )
    return None if stat is None else _parse_stat(thread_id, stat)


def _same_process_identity(expected: dict, actual: dict | None) -> bool:
    return actual is not None and all(
        actual.get(field) == expected.get(field)
        for field in ("pid", "start_ticks", "pgrp", "session")
    )


def service_thread_members(
    service: dict,
    *,
    known_threads: dict[int, dict],
    process_ids: set[int],
    timeout: float = SYSTEMD_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Capture new thread identities directly from the owned service's cgroup."""
    cgroup = str(service.get("cgroup", ""))
    if not cgroup:
        return {"threads": [], "inconclusive": []}
    root = _resolved_cgroup(cgroup)
    try:
        root_mode = root.stat().st_mode
    except FileNotFoundError:
        return {"threads": [], "inconclusive": [], "cgroup_gone": True}
    except OSError as exc:
        return {
            "threads": [],
            "inconclusive": [f"could not inspect owned cgroup thread root: {exc}"],
        }
    if timeout <= 0:
        return {
            "threads": [],
            "inconclusive": ["owned cgroup thread scan had no time budget"],
        }
    if not stat.S_ISDIR(root_mode):
        return {
            "threads": [],
            "inconclusive": ["owned cgroup thread root is not a directory"],
        }
    deadline = time.monotonic() + timeout
    tids: set[int] = set()
    inconclusive: list[str] = []
    found_thread_file = False
    pending = [root]
    while pending:
        if time.monotonic() >= deadline:
            inconclusive.append(
                "owned cgroup thread enumeration exceeded its time budget"
            )
            break
        directory = pending.pop()
        thread_file = directory / "cgroup.threads"
        if thread_file.is_file():
            found_thread_file = True
            remaining = deadline - time.monotonic()
            contents, error = _read_proc_path_result(
                thread_file, min(remaining, PROC_STAT_TIMEOUT_SECONDS)
            )
            if error is not None:
                inconclusive.append(f"could not read owned cgroup thread list: {error}")
            elif contents is not None:
                for value in contents.splitlines():
                    if time.monotonic() >= deadline:
                        inconclusive.append(
                            "owned cgroup thread enumeration exceeded its time budget"
                        )
                        break
                    if value.isdigit():
                        tid = int(value)
                        if tid not in process_ids:
                            tids.add(tid)
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if time.monotonic() >= deadline:
                        inconclusive.append(
                            "owned cgroup thread enumeration exceeded its time budget"
                        )
                        break
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
        except FileNotFoundError:
            pass
        except OSError as exc:
            inconclusive.append(f"could not enumerate owned cgroup thread lists: {exc}")

    if not found_thread_file and not inconclusive:
        try:
            root.stat()
        except FileNotFoundError:
            return {"threads": [], "inconclusive": []}
        except OSError as exc:
            inconclusive.append(f"could not inspect owned cgroup thread root: {exc}")
        else:
            inconclusive.append(
                "owned cgroup exposes no cgroup.threads membership file"
            )
    threads: list[dict] = []
    for tid in sorted(tids):
        if time.monotonic() >= deadline:
            inconclusive.append(
                "owned cgroup thread identity capture exceeded its time budget"
            )
            break
        identity, error = proc_identity_result(tid)
        if error is not None:
            inconclusive.append(f"could not inspect owned thread {tid}: {error}")
        elif identity is not None and not _same_process_identity(
            known_threads.get(tid, {}), identity
        ):
            threads.append(identity)
    return {"threads": threads, "inconclusive": inconclusive}


def uninterruptible_owned_threads(
    identities: list[dict],
    *,
    timeout: float = 1.5,
    confirmation_seconds: float = 0.5,
) -> dict[str, list[dict] | list[str]]:
    """Confirm D-state threads from previously captured owned-cgroup identities."""
    if not identities:
        return {"threads": [], "inconclusive": []}
    if timeout <= 0:
        return {"threads": [], "inconclusive": ["thread inspection had no time budget"]}
    if threading.current_thread() is not threading.main_thread():
        return {
            "threads": [],
            "inconclusive": ["thread inspection requires the main thread"],
        }

    deadline = time.monotonic() + timeout
    candidates: dict[int, dict] = {}
    inconclusive: list[str] = []
    for expected in identities:
        if time.monotonic() >= deadline:
            inconclusive.append(
                "owned thread inspection exceeded its global time budget"
            )
            break
        tid = int(expected["pid"])
        actual, error = proc_identity_result(tid)
        if error is not None:
            inconclusive.append(f"could not inspect owned thread {tid}: {error}")
        elif _same_process_identity(expected, actual) and actual["state"] == "D":
            candidates[tid] = actual

    if not candidates:
        return {"threads": [], "inconclusive": inconclusive}
    remaining = deadline - time.monotonic()
    if remaining < confirmation_seconds:
        inconclusive.append(
            "could not confirm D-state thread persistence within the time budget"
        )
        return {
            "threads": [{**item, "tid": item["pid"]} for item in candidates.values()],
            "inconclusive": inconclusive,
        }
    time.sleep(confirmation_seconds)

    confirmed: list[dict] = []
    processed: set[int] = set()
    for expected in identities:
        tid = int(expected["pid"])
        if tid not in candidates:
            continue
        if time.monotonic() >= deadline:
            inconclusive.append(
                "owned thread confirmation exceeded its global time budget"
            )
            confirmed.extend(
                {**item, "tid": pending_tid}
                for pending_tid, item in candidates.items()
                if pending_tid not in processed
            )
            break
        actual, error = proc_identity_result(tid)
        processed.add(tid)
        if error is not None:
            inconclusive.append(f"could not confirm owned thread {tid}: {error}")
            confirmed.append({**candidates[tid], "tid": tid})
        elif (
            _same_process_identity(expected, actual)
            and actual["state"] == "D"
            and actual["start_ticks"] == candidates[tid]["start_ticks"]
        ):
            confirmed.append({**actual, "tid": tid})
    return {"threads": confirmed, "inconclusive": inconclusive}


def process_kernel_diagnostics(expected: dict) -> dict:
    pid = int(expected["pid"])
    if not identity_matches(expected):
        return {"pid": pid, "identity_valid": False}
    result: dict[str, object] = {"pid": pid, "identity_valid": True}
    for field in ("wchan", "status"):
        value = _read_proc_text(pid, field)
        result[field] = value[:65536] if value is not None else None
    # A target can enter D state between an identity check and a stack read, and
    # /proc/<pid>/stack can then block the observer in the same kernel path. A
    # userspace alarm cannot rescue that read, so this tooling never opens it.
    result["stack"] = None
    result["stack_unavailable_reason"] = "unsafe procfs pseudo-file"
    return result


def identity_matches(expected: dict) -> bool:
    actual = proc_identity(int(expected["pid"]))
    if actual is None or actual["state"] == "Z":
        return False
    return all(
        actual.get(field) == expected.get(field)
        for field in ("pid", "start_ticks", "pgrp", "session")
    )


def confirm_uninterruptible(expected: dict, duration: float = 0.5) -> dict | None:
    deadline = time.monotonic() + duration
    while True:
        actual = proc_identity(int(expected["pid"]))
        if actual is None or actual["state"] != "D":
            return None
        if any(
            actual.get(field) != expected.get(field)
            for field in ("pid", "start_ticks", "pgrp", "session")
        ):
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return actual
        time.sleep(min(0.05, remaining))


def _systemctl(
    *arguments: str,
    check: bool = True,
    timeout: float = SYSTEMD_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    if timeout <= 0:
        raise InvestigationError(
            "process_service_timeout", "user systemd operation has no remaining time"
        )
    try:
        result = subprocess.run(
            ["systemctl", "--user", *arguments],
            text=True,
            capture_output=True,
            timeout=min(timeout, SYSTEMD_TIMEOUT_SECONDS),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError(
            "process_service_unavailable", f"user systemd operation failed: {exc}"
        ) from exc
    if check and result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}"
        )
        raise InvestigationError("process_service_failed", detail)
    return result


def _unit_properties(
    unit: str, *, timeout: float = SYSTEMD_TIMEOUT_SECONDS
) -> dict[str, str]:
    result = _systemctl(
        "show",
        unit,
        "--property=MainPID",
        "--property=ControlGroup",
        "--property=ActiveState",
        "--property=SubState",
        timeout=timeout,
    )
    return dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )


def launch_service(
    *,
    unit: str,
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    output: IO[bytes],
    publish_start: Callable[[subprocess.Popen[bytes] | None, dict, dict | None], None],
    runtime_max_seconds: float | None = None,
) -> tuple[subprocess.Popen[bytes], dict, dict]:
    if not re.fullmatch(r"squinch-mc-[a-z0-9-]+\.service", unit):
        raise InvestigationError(
            "process_service_invalid", f"invalid owned unit name: {unit}"
        )
    invocation = [
        "systemd-run",
        "--user",
        f"--unit={unit}",
        "--collect",
        "--wait",
        "--pipe",
        "--quiet",
        "--expand-environment=no",
        "--property=Type=exec",
        "--property=KillMode=control-group",
        "--property=SendSIGKILL=yes",
        "--property=TimeoutStopSec=10s",
        f"--working-directory={cwd}",
    ]
    if runtime_max_seconds is not None:
        if runtime_max_seconds <= 0:
            raise InvestigationError(
                "process_service_invalid", "service runtime limit must be positive"
            )
        invocation.append(f"--property=RuntimeMaxSec={runtime_max_seconds:g}s")
    invocation.extend(f"--setenv={key}={value}" for key, value in environment.items())
    invocation.extend(("--", *command))
    service = {
        "unit": unit,
        "cgroup": "",
        "wrapper": None,
    }
    publish_start(None, service, None)
    try:
        process = subprocess.Popen(
            invocation,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise InvestigationError(
            "process_service_unavailable",
            f"could not launch user systemd service: {exc}",
        ) from exc
    wrapper_identity = proc_identity(process.pid)
    if wrapper_identity is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        raise InvestigationError(
            "process_service_failed",
            "could not retain the systemd-run wrapper identity",
        )
    service["wrapper"] = wrapper_identity
    publish_start(process, service, wrapper_identity)

    deadline = time.monotonic() + SYSTEMD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise InvestigationError(
                "process_service_failed",
                f"user systemd launch exited with code {process.returncode}",
            )
        try:
            properties = _unit_properties(unit)
        except InvestigationError:
            time.sleep(0.05)
            continue
        main_pid = int(properties.get("MainPID", "0"))
        cgroup = properties.get("ControlGroup", "")
        if cgroup.startswith("/"):
            service["cgroup"] = cgroup
        identity = proc_identity(main_pid) if main_pid > 0 else None
        if identity is not None and cgroup.startswith("/"):
            return process, service, identity
        time.sleep(0.05)
    raise InvestigationError(
        "process_service_failed",
        "user systemd did not publish an owned main process; published launch ownership requires cleanup",
    )


def _resolved_cgroup(value: str) -> Path:
    if not value.startswith("/"):
        raise InvestigationError(
            "process_service_invalid", "owned cgroup path is not absolute"
        )
    path = (CGROUP_ROOT / value.removeprefix("/")).resolve()
    root = CGROUP_ROOT.resolve()
    if path == root or not path.is_relative_to(root):
        raise InvestigationError(
            "process_service_invalid", "owned cgroup escapes cgroup root"
        )
    return path


def service_members(
    service: dict, *, timeout: float = SYSTEMD_TIMEOUT_SECONDS
) -> list[dict]:
    cgroup = str(service.get("cgroup", ""))
    if not cgroup:
        unit = str(service.get("unit", ""))
        if not re.fullmatch(r"squinch-mc-[a-z0-9-]+\.service", unit):
            return []
        try:
            cgroup = _unit_properties(unit, timeout=timeout).get("ControlGroup", "")
        except InvestigationError:
            return []
        if not cgroup.startswith("/"):
            return []
        service["cgroup"] = cgroup
    root = _resolved_cgroup(cgroup)
    if not root.is_dir():
        return []
    pids: set[int] = set()
    try:
        directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
        for directory in directories:
            process_file = directory / "cgroup.procs"
            if not process_file.is_file():
                continue
            for value in process_file.read_text(encoding="utf-8").splitlines():
                if value.isdigit():
                    pids.add(int(value))
    except OSError:
        return []
    return sorted(
        (identity for pid in pids if (identity := proc_identity(pid)) is not None),
        key=lambda value: value["pid"],
    )


def signal_service(
    service: dict,
    sig: signal.Signals,
    *,
    timeout: float = SYSTEMD_TIMEOUT_SECONDS,
) -> None:
    unit = str(service.get("unit", ""))
    if not re.fullmatch(r"squinch-mc-[a-z0-9-]+\.service", unit):
        raise InvestigationError(
            "process_service_invalid", f"invalid owned unit name: {unit}"
        )
    result = _systemctl(
        "kill",
        f"--signal={sig.name}",
        "--kill-whom=all",
        unit,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}"
        )
        if not any(
            marker in detail.lower() for marker in ("not loaded", "could not be found")
        ):
            raise InvestigationError("process_service_failed", detail)


def stop_service(service: dict, *, timeout: float = SYSTEMD_TIMEOUT_SECONDS) -> None:
    unit = str(service.get("unit", ""))
    if not re.fullmatch(r"squinch-mc-[a-z0-9-]+\.service", unit):
        raise InvestigationError(
            "process_service_invalid", f"invalid owned unit name: {unit}"
        )
    _systemctl("stop", unit, check=False, timeout=timeout)


def listener_owners(port: int, *, timeout: float = 5.0) -> list[dict]:
    if timeout <= 0:
        return []
    try:
        result = subprocess.run(
            ["ss", "-H", "-ltnp", f"sport = :{port}"],
            text=True,
            capture_output=True,
            timeout=min(timeout, 5.0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    owners: list[dict] = []
    for pid_text in re.findall(r"pid=(\d+)", result.stdout):
        identity = proc_identity(int(pid_text))
        if identity and identity not in owners:
            owners.append(identity)
    return owners


def signal_recorded_process(expected: dict, sig: signal.Signals) -> bool:
    if not identity_matches(expected):
        return False
    os.kill(int(expected["pid"]), sig)
    return True
