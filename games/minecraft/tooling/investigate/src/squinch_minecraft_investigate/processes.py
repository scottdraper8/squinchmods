from __future__ import annotations

import contextlib
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

from .errors import InvestigationError


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def port_is_free(port: int) -> bool:
    """Return whether no TCP listener currently accepts connections on localhost."""
    try:
        result = subprocess.run(
            ["ss", "-H", "-ltn", f"sport = :{port}"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return not bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Fallback for systems without ss. This can touch the listener, so Linux's
    # read-only socket table is preferred above.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) != 0


def port_is_available(port: int) -> bool:
    """Return whether a new listener can safely bind the requested port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def proc_identity(pid: int) -> dict | None:
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
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


def identity_matches(expected: dict) -> bool:
    actual = proc_identity(int(expected["pid"]))
    if actual is None or actual["state"] == "Z":
        return False
    return all(
        actual.get(field) == expected.get(field)
        for field in ("pid", "start_ticks", "pgrp", "session")
    )


def group_members(pgrp: int) -> list[dict]:
    members: list[dict] = []
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        identity = proc_identity(int(item.name))
        if identity and identity["pgrp"] == pgrp and identity["state"] != "Z":
            members.append(identity)
    return sorted(members, key=lambda value: value["pid"])


def descendants(expected_roots: list[dict]) -> list[dict]:
    """Return live descendants while at least one exact recorded ancestry link exists."""
    snapshot: dict[int, dict] = {}
    for item in Path("/proc").iterdir():
        if item.name.isdigit():
            identity = proc_identity(int(item.name))
            if identity and identity["state"] != "Z":
                snapshot[identity["pid"]] = identity
    accepted: dict[int, dict] = {
        int(root["pid"]): snapshot[int(root["pid"])]
        for root in expected_roots
        if identity_matches(root) and int(root["pid"]) in snapshot
    }
    changed = True
    while changed:
        changed = False
        for identity in snapshot.values():
            if identity["pid"] in accepted or identity["ppid"] not in accepted:
                continue
            parent = accepted[identity["ppid"]]
            if identity["start_ticks"] >= parent["start_ticks"]:
                accepted[identity["pid"]] = identity
                changed = True
    return sorted(accepted.values(), key=lambda value: value["pid"])


def validated_group_members(state: dict) -> list[dict]:
    process = state["process"]
    pgrp = int(process["pgrp"])
    if pgrp <= 1 or pgrp != int(process["pid"]):
        raise InvestigationError(
            "unsafe_process_boundary",
            f"refusing unsafe process group {pgrp} for leader {process['pid']}",
        )
    members = group_members(pgrp)
    earliest = int(process["start_ticks"])
    older = [member for member in members if member["start_ticks"] < earliest]
    if older:
        raise InvestigationError(
            "process_identity_mismatch",
            "process group contains a process older than the tracked launch",
            details={"members": older},
        )
    return members


def listener_owners(port: int) -> list[dict]:
    try:
        result = subprocess.run(
            ["ss", "-H", "-ltnp", f"sport = :{port}"],
            text=True,
            capture_output=True,
            timeout=5,
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


def wait_for_group_exit(pgrp: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not group_members(pgrp):
            return True
        time.sleep(0.2)
    return not group_members(pgrp)


def signal_validated_group(state: dict, sig: signal.Signals) -> None:
    members = validated_group_members(state)
    if not members:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(int(state["process"]["pgrp"]), sig)


def signal_recorded_process(expected: dict, sig: signal.Signals) -> bool:
    if not identity_matches(expected):
        return False
    os.kill(int(expected["pid"]), sig)
    return True
