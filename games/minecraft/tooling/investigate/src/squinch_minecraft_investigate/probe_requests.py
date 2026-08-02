from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path

from .errors import InvestigationError
from .output import timestamp
from .paths import lock_path
from .server import load_active, persist_active
from .state import atomic_write_json, project_lock


TERMINAL_STATES = {"pass", "fail", "inconclusive", "error"}
PROBE_PHASES = {
    "prediction",
    "structure-start",
    "generation",
    "placement",
    "finished-chunk",
    "reload",
}


def read_probe_transcript(path: Path, request: dict) -> tuple[list[dict], dict]:
    try:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise InvestigationError(
            "invalid_probe_transcript", f"cannot read probe JSONL transcript {path}: {exc}"
        ) from exc
    if not records or any(not isinstance(record, dict) for record in records):
        raise InvestigationError(
            "invalid_probe_transcript", "probe transcript must contain JSON objects"
        )
    required_identity = {
        key: request[key]
        for key in ("run_id", "request_id", "probe_id", "probe_version")
    }
    for index, record in enumerate(records):
        if any(record.get(key) != value for key, value in required_identity.items()):
            raise InvestigationError(
                "probe_identity_mismatch",
                f"probe transcript record {index} identity does not match request",
            )
    terminals = [record for record in records if record.get("type") == "terminal"]
    if len(terminals) != 1:
        raise InvestigationError(
            "probe_terminal_count",
            f"probe transcript must contain exactly one terminal record, found {len(terminals)}",
        )
    terminal = terminals[0]
    if records[-1] is not terminal:
        raise InvestigationError(
            "probe_terminal_order", "the terminal record must be the final transcript record"
        )
    state = terminal.get("state")
    if state not in TERMINAL_STATES:
        raise InvestigationError(
            "probe_missing_terminal", f"invalid or missing probe terminal state: {state!r}"
        )
    if terminal.get("phase") not in PROBE_PHASES:
        raise InvestigationError(
            "probe_invalid_phase", f"invalid or missing probe phase: {terminal.get('phase')!r}"
        )
    completeness = terminal.get("completeness")
    if not isinstance(completeness, dict):
        raise InvestigationError(
            "probe_missing_completeness", "probe terminal lacks a completeness object"
        )
    for key in ("inspected", "skipped"):
        count = completeness.get(key)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise InvestigationError(
                "probe_invalid_completeness",
                f"probe completeness {key} must be a nonnegative integer",
            )
    complete = completeness.get("complete")
    if not isinstance(complete, bool):
        raise InvestigationError(
            "probe_invalid_completeness", "probe completeness complete must be boolean"
        )
    if (state in {"pass", "fail"}) != complete:
        raise InvestigationError(
            "probe_terminal_completeness_conflict",
            f"terminal state {state!r} conflicts with complete={complete!r}",
        )
    if not complete and not isinstance(completeness.get("reason"), str):
        raise InvestigationError(
            "probe_missing_completeness_reason", "incomplete terminal lacks a reason"
        )
    return records, terminal


def submit_probe(
    project: Path,
    loader: str,
    *,
    probe_id: str,
    probe_version: str,
    config: dict,
    timeout: float,
) -> tuple[dict, dict, dict]:
    """Submit an atomic request and return its request, terminal result, and active state."""
    with project_lock(lock_path(project, loader)):
        state = load_active(project, loader)
        if state["lifecycle"] != "ready":
            raise InvestigationError(
                "server_not_ready", f"active lifecycle is {state['lifecycle']}"
            )
        request_id = uuid.uuid4().hex
        protocol_root = Path(state["run_dir"]) / ".squinch-investigate"
        request = {
            "protocol_version": "1",
            "run_id": state["run_id"],
            "request_id": request_id,
            "probe_id": probe_id,
            "probe_version": probe_version,
            "submitted_at": timestamp(),
            "config": config,
        }
        request_path = protocol_root / "requests" / f"{request_id}.json"
        result_path = protocol_root / "results" / f"{request_id}.jsonl"
        atomic_write_json(request_path, request)
        artifact_request = Path(state["artifact_dir"]) / f"probe-request-{request_id}.json"
        atomic_write_json(artifact_request, request)
        state.setdefault("protocol_files", []).extend([str(request_path), str(result_path)])
        persist_active(state)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not result_path.exists():
        time.sleep(0.2)
    if not result_path.exists():
        raise InvestigationError(
            "probe_timeout",
            f"probe produced no terminal result within {timeout:g}s",
            details={
                "run_id": state["run_id"],
                "artifact_dir": state["artifact_dir"],
                "log_path": state["log_path"],
                "request": str(request_path),
                "expected_result": str(result_path),
                "request_artifact": str(artifact_request),
            },
        )
    _records, result = read_probe_transcript(result_path, request)
    shutil.copy2(result_path, Path(state["artifact_dir"]) / f"probe-{request_id}.jsonl")
    return request, result, state
