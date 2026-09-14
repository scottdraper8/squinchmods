#!/usr/bin/env python3
"""Host-side control for a running resident NMS search probe."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path

from search_probes.resident_search_protocol import PROTOCOL_VERSION, normalize_command

ROOT = Path(
    os.environ.get(
        "SQN_RESIDENT_SEARCH_ROOT",
        str(Path(__file__).with_name(".resident-search")),
    )
)
EXECUTOR_HOST = "127.0.0.1"
EXECUTOR_PORT = 6770
EXECUTOR_ESCAPE = b"\x02\x07\x01\x08"


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object in {path}")
    return value


def _session() -> Path:
    current = _read_json(ROOT / "current.json")
    session_id = current.get("session_id")
    if not isinstance(session_id, str):
        raise TypeError("resident current.json has no session_id")
    return ROOT / "sessions" / session_id


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _next_generation(session: Path) -> int:
    state = _read_json(session / "state.json")
    generation = state.get("generation", 0)
    if not isinstance(generation, int) or isinstance(generation, bool):
        raise TypeError("resident state has an invalid generation")
    return generation + 1


def _nms_pids() -> set[int]:
    result: set[int] = set()
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() == "NMS.exe":
                result.add(int(comm.parent.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return result


def _focus_nms_window() -> bool:
    """Best-effort focus return so a paused background client can process teardown."""

    xdotool = shutil.which("xdotool")
    if xdotool is None:
        return False
    search = subprocess.run(
        [xdotool, "search", "--name", "^No Man's Sky$"],
        capture_output=True,
        check=False,
        text=True,
        timeout=5.0,
    )
    windows = [line for line in search.stdout.splitlines() if line]
    if search.returncode != 0 or not windows:
        return False
    activate = subprocess.run(
        [xdotool, "windowactivate", "--sync", windows[-1]],
        capture_output=True,
        check=False,
        text=True,
        timeout=5.0,
    )
    return activate.returncode == 0


def _submit(args: argparse.Namespace) -> int:
    session = _session()
    command_id = args.id or f"{time.time_ns()}-{uuid.uuid4().hex}"
    generation = args.generation
    if generation is None:
        generation = _next_generation(session)
    command: dict[str, object] = {
        "protocol": PROTOCOL_VERSION,
        "id": command_id,
        "generation": generation,
        "action": args.action,
    }
    if args.action in {"candidate", "nearest", "search"}:
        command["criteria"] = json.loads(args.criteria)
    if args.action == "search":
        command["name"] = args.name
        command["result_limit"] = args.result_limit
    if args.action in {"search", "enumerate", "survey", "spawn_survey"}:
        command["candidate_limit"] = args.candidate_limit
    if args.action in {"candidate", "snapshot", "navigate"}:
        command["address"] = args.address
    if args.action == "cancel":
        command["target_id"] = args.target_id
    if args.action == "wiki_mirror_probe":
        command["topic_count"] = args.topic_count
        command["label_prefix"] = args.label_prefix
    command = normalize_command(command)
    _atomic_json(session / "commands" / f"{command_id}.json", command)
    if args.wait <= 0:
        print(
            json.dumps(
                {"submitted": command_id, "session": session.name}, sort_keys=True
            )
        )
        return 0
    result_path = session / "results" / f"{command_id}.json"
    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        if result_path.exists():
            print(json.dumps(_read_json(result_path), indent=2, sort_keys=True))
            return 0
        time.sleep(0.05)
    raise TimeoutError(f"no result for {command_id} within {args.wait:g} seconds")


def _status(_args: argparse.Namespace) -> int:
    session = _session()
    print(json.dumps(_read_json(session / "state.json"), indent=2, sort_keys=True))
    return 0


def _stop(args: argparse.Namespace) -> int:
    session = _session()
    nms_before = _nms_pids()
    if len(nms_before) != 1:
        raise RuntimeError(
            f"expected one NMS.exe before shutdown, found {sorted(nms_before)}"
        )
    command_id = f"shutdown-{time.time_ns()}-{uuid.uuid4().hex}"
    command = normalize_command(
        {
            "protocol": PROTOCOL_VERSION,
            "id": command_id,
            "generation": _next_generation(session),
            "action": "shutdown",
        }
    )
    _atomic_json(session / "commands" / f"{command_id}.json", command)
    # DearPyGUI is an owned top-level window. If it still has focus, some NMS configurations stop
    # advancing the gameplay callback that must restore the hook. Return focus after enqueueing.
    _focus_nms_window()
    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        state = _read_json(session / "state.json")
        if state.get("state") == "closed":
            break
        time.sleep(0.05)
    else:
        raise TimeoutError("resident hook did not report closed; executor left running")

    deadline = time.monotonic() + args.wait
    with socket.create_connection(
        (EXECUTOR_HOST, EXECUTOR_PORT), timeout=2.0
    ) as client:
        client.sendall(EXECUTOR_ESCAPE)
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((EXECUTOR_HOST, EXECUTOR_PORT), timeout=0.2):
                pass
        except OSError:
            break
        time.sleep(0.05)
    else:
        raise TimeoutError("pyMHF executor remained reachable after its exit command")
    nms_after = _nms_pids()
    if nms_after != nms_before:
        raise RuntimeError(
            f"NMS process changed during controller shutdown: {nms_before} -> {nms_after}"
        )
    print(
        json.dumps(
            {
                "status": "closed",
                "session": session.name,
                "nms_pid": next(iter(nms_after)),
                "hook_restored": True,
                "executor_closed": True,
            },
            sort_keys=True,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.set_defaults(run=_status)

    stop = subparsers.add_parser(
        "stop",
        help="restore the resident hook, stop the controller, and verify NMS survival",
    )
    stop.add_argument("--wait", type=float, default=15.0)
    stop.set_defaults(run=_stop)

    submit = subparsers.add_parser("submit")
    submit.add_argument(
        "action",
        choices=(
            "candidate",
            "nearest",
            "search",
            "enumerate",
            "cancel",
            "shutdown",
            "ping",
            "snapshot",
            "survey",
            "spawn_survey",
            "wiki_snapshot",
            "wiki_mirror_probe",
            "scan_event_observations",
            "navigate",
        ),
    )
    submit.add_argument("--id")
    submit.add_argument("--generation", type=int)
    submit.add_argument("--criteria", default="{}")
    submit.add_argument("--result-limit", type=int, default=5)
    submit.add_argument("--name", default="System search")
    submit.add_argument("--candidate-limit", type=int, default=64)
    submit.add_argument("--address")
    submit.add_argument("--target-id")
    submit.add_argument("--topic-count", type=int)
    submit.add_argument("--label-prefix", default="")
    submit.add_argument("--wait", type=float, default=10.0)
    submit.set_defaults(run=_submit)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return int(args.run(args))


if __name__ == "__main__":
    raise SystemExit(main())
