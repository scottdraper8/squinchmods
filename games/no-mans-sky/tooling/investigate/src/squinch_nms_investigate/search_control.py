"""Session-bound local control of the installed Search Probes Rust backend."""

from __future__ import annotations

import copy
import json
import os
import re
import time
import uuid
from pathlib import Path

from .errors import InvestigationError

MAX_BYTES = 1_100_000
INSTANCE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{32}$")


def read_json(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("file exceeds its byte bound")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("expected a JSON object")
        return result
    except (OSError, ValueError) as exc:
        raise InvestigationError(
            "search_control_unavailable", f"Cannot read {path}: {exc}"
        ) from exc


def settings_directory(game_root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve(strict=True)
    users = game_root.parents[1] / "compatdata/275850/pfx/drive_c/users"
    matches = sorted(p for p in users.glob("*/AppData/Local/SearchProbes") if p.is_dir())
    if len(matches) != 1:
        raise InvestigationError(
            "search_settings_ambiguous",
            "Specify --settings-dir for the running Search Probes installation",
            candidates=[str(p) for p in matches],
        )
    return matches[0].resolve()


def status(directory: Path) -> tuple[dict, dict]:
    endpoint_path = directory / "agent-control.json"
    endpoint = read_json(endpoint_path)
    state_path = directory / "current.json"
    state = read_json(state_path)
    if endpoint.get("schema") != 1 or not INSTANCE.fullmatch(str(endpoint.get("instance", ""))):
        raise InvestigationError("search_control_incompatible", "Unsupported agent endpoint")
    # Both files are refreshed by the same persistence worker. An old endpoint must not
    # turn a command into a request for the next game process that reuses a generation.
    if any(time.time() - p.stat().st_mtime > 5 for p in [endpoint_path, state_path]):
        raise InvestigationError("search_control_stale", "The Search Probes endpoint is not live")
    if read_json(endpoint_path).get("instance") != endpoint["instance"]:
        raise InvestigationError(
            "search_runtime_changed", "NMS restarted while reading its endpoint"
        )
    if not isinstance(state.get("generation"), int):
        raise InvestigationError("search_control_incompatible", "Missing game generation")
    return endpoint, state


def _write_request(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise InvestigationError(
            "search_request_too_large", "Search request exceeds its byte bound"
        )
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def command(directory: Path, action: dict, *, wait: bool = True, timeout: float = 120) -> dict:
    if not 0.1 <= timeout <= 600:
        raise InvestigationError(
            "invalid_search_timeout", "Timeout must be between 0.1 and 600 seconds"
        )
    endpoint, initial = status(directory)
    instance = endpoint["instance"]
    root = directory / "agent-control" / instance
    if not root.resolve(strict=True).is_relative_to(directory.resolve()):
        raise InvestigationError(
            "unsafe_search_endpoint", "Agent control directory escapes settings"
        )
    request_id = uuid.uuid4().hex
    request_path = root / "requests" / f"{request_id}.json"
    response_path = root / "responses" / f"{request_id}.json"
    payload = {
        "schema": 1,
        "instance": instance,
        "request_id": request_id,
        "generation": initial["generation"],
        "expires_unix_ms": int(time.time() * 1000) + min(120_000, max(1000, int(timeout * 1000))),
        "action": action,
    }
    _write_request(request_path, payload)
    deadline = time.monotonic() + timeout
    ack = None
    try:
        while time.monotonic() < deadline:
            current_endpoint, state = status(directory)
            if (
                current_endpoint["instance"] != instance
                or state["generation"] != initial["generation"]
            ):
                raise InvestigationError(
                    "search_runtime_changed", "The runtime or loaded game generation changed"
                )
            if ack is None and response_path.exists():
                ack = read_json(response_path)
                if (ack.get("schema"), ack.get("instance"), ack.get("request_id")) != (
                    1,
                    instance,
                    request_id,
                ):
                    raise InvestigationError(
                        "search_response_mismatch", "Command acknowledgement does not match request"
                    )
                if ack.get("error"):
                    raise InvestigationError("search_command_rejected", str(ack["error"]))
                if not isinstance(ack.get("command_id"), int) or ack["command_id"] < 1:
                    raise InvestigationError("search_response_mismatch", "Missing command identity")
                if not wait:
                    return {"phase": "queued", "acknowledgement": ack, "state": state}
            if ack is not None and state.get("last_command", 0) >= ack["command_id"]:
                if action["type"] in {"start", "continue"}:
                    if state.get("search_command") != ack["command_id"]:
                        if state.get("last_command") == ack["command_id"] and state.get("error"):
                            raise InvestigationError("search_command_failed", state["error"])
                        raise InvestigationError(
                            "search_command_superseded",
                            state.get("error") or "A different command owns the published search",
                        )
                    progress = state.get("progress") or {}
                    if progress.get("phase") in {"completed", "cancelled", "failed", "cached"}:
                        return {"phase": progress["phase"], "acknowledgement": ack, "state": state}
                else:
                    if state.get("error") and state["last_command"] == ack["command_id"]:
                        raise InvestigationError("search_command_failed", state["error"])
                    return {"phase": "applied", "acknowledgement": ack, "state": state}
            time.sleep(0.05)
        raise InvestigationError(
            "search_command_timeout",
            "Timed out waiting for the backend; inspect search status before retrying",
            request_id=request_id,
            command_id=ack.get("command_id") if ack else None,
        )
    finally:
        request_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


def action_from_options(args, state: dict) -> dict:
    if args.action == "cancel":
        return {"type": "cancel"}
    if args.action == "continue":
        return {
            "type": "continue",
            "results": args.results
            if args.results is not None
            else state["settings"]["search"]["results"],
        }
    settings = read_json(args.settings) if args.settings else copy.deepcopy(state["settings"])
    if args.criteria:
        settings["search"]["criteria"] = read_json(args.criteria)
    if args.systems is not None:
        settings["search"]["systems"] = args.systems
    if args.results is not None:
        settings["search"]["results"] = args.results
    if args.action == "configure":
        return {"type": "configure", "settings": settings}
    return {
        "type": "start",
        "settings": settings,
        "restart": args.restart,
        "use_cache": args.use_cache,
    }
