"""Versioned local protocol for capabilities supplied by an installed NMS runtime."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .errors import InvestigationError

MAX_BYTES = 1_100_000
MAX_STATE_BYTES = 8 * 1024 * 1024
INSTANCE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{32}$")
ACTION_CAPABILITIES = {
    "start": "search.control/v1",
    "cancel": "search.control/v1",
    "configure": "search.control/v1",
    "inspect_current": "nms.current-world/v1",
}


def read_json(path: Path, *, max_bytes: int = MAX_BYTES) -> dict:
    try:
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("file exceeds its byte bound")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("expected a JSON object")
        return result
    except (OSError, ValueError) as exc:
        raise InvestigationError(
            "runtime_protocol_unavailable", f"Cannot read {path}: {exc}"
        ) from exc


def capabilities(endpoint: dict) -> frozenset[str]:
    schema = endpoint.get("schema")
    if schema != 2:
        raise InvestigationError(
            "runtime_protocol_incompatible", "Unsupported runtime endpoint schema"
        )
    protocol = endpoint.get("protocol")
    advertised = endpoint.get("capabilities")
    if (
        not isinstance(protocol, dict)
        or protocol.get("id") != "search-probes.agent-control"
        or protocol.get("version") != 1
        or not isinstance(advertised, list)
        or not advertised
        or any(not isinstance(item, str) or not item for item in advertised)
    ):
        raise InvestigationError(
            "runtime_protocol_incompatible", "Malformed runtime capability declaration"
        )
    return frozenset(advertised)


def status(directory: Path, *, required_capability: str | None = None) -> tuple[dict, dict]:
    endpoint_path = directory / "agent-control.json"
    endpoint = read_json(endpoint_path)
    state_path = directory / "current.json"
    state = read_json(state_path, max_bytes=MAX_STATE_BYTES)
    if not INSTANCE.fullmatch(str(endpoint.get("instance", ""))):
        raise InvestigationError(
            "runtime_protocol_incompatible", "Malformed runtime instance identity"
        )
    available = capabilities(endpoint)
    if required_capability is not None and required_capability not in available:
        raise InvestigationError(
            "runtime_capability_unavailable",
            f"The installed runtime does not provide {required_capability}",
            advertised=sorted(available),
        )
    try:
        stale = any(time.time() - path.stat().st_mtime > 5 for path in [endpoint_path, state_path])
    except OSError as exc:
        raise InvestigationError(
            "runtime_protocol_unavailable", f"Cannot inspect runtime freshness: {exc}"
        ) from exc
    if stale:
        raise InvestigationError("runtime_protocol_stale", "The runtime endpoint is not live")
    if read_json(endpoint_path).get("instance") != endpoint["instance"]:
        raise InvestigationError(
            "runtime_changed", "NMS restarted while reading its runtime endpoint"
        )
    if not isinstance(state.get("generation"), int):
        raise InvestigationError("runtime_protocol_incompatible", "Missing game generation")
    return endpoint, state


def _write_request(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise InvestigationError(
            "runtime_request_too_large", "Runtime request exceeds its byte bound"
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
            "invalid_runtime_timeout", "Timeout must be between 0.1 and 600 seconds"
        )
    action_type = action.get("type")
    required = ACTION_CAPABILITIES.get(action_type)
    if required is None:
        raise InvestigationError(
            "unsupported_runtime_action", f"Unsupported runtime action: {action_type!r}"
        )
    endpoint, initial = status(directory, required_capability=required)
    instance = endpoint["instance"]
    root = directory / "agent-control" / instance
    if not root.resolve(strict=True).is_relative_to(directory.resolve()):
        raise InvestigationError(
            "unsafe_runtime_endpoint", "Runtime control directory escapes settings"
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
    acknowledgement = None
    try:
        while time.monotonic() < deadline:
            current_endpoint, state = status(directory, required_capability=required)
            if (
                current_endpoint["instance"] != instance
                or state["generation"] != initial["generation"]
            ):
                raise InvestigationError(
                    "runtime_changed", "The runtime or loaded game generation changed"
                )
            if acknowledgement is None and response_path.exists():
                acknowledgement = read_json(response_path)
                if (
                    acknowledgement.get("schema"),
                    acknowledgement.get("instance"),
                    acknowledgement.get("request_id"),
                ) != (1, instance, request_id):
                    raise InvestigationError(
                        "runtime_response_mismatch",
                        "Command acknowledgement does not match request",
                    )
                if acknowledgement.get("error"):
                    raise InvestigationError(
                        "runtime_command_rejected", str(acknowledgement["error"])
                    )
                if (
                    not isinstance(acknowledgement.get("command_id"), int)
                    or acknowledgement["command_id"] < 1
                ):
                    raise InvestigationError(
                        "runtime_response_mismatch", "Missing command identity"
                    )
                if not wait:
                    return {
                        "phase": "queued",
                        "acknowledgement": acknowledgement,
                        "state": state,
                    }
            if (
                acknowledgement is not None
                and state.get("last_command", 0) >= acknowledgement["command_id"]
            ):
                if action_type == "start":
                    if state.get("search_command") != acknowledgement["command_id"]:
                        if state.get("last_command") == acknowledgement["command_id"] and state.get(
                            "error"
                        ):
                            raise InvestigationError("runtime_command_failed", state["error"])
                        raise InvestigationError(
                            "runtime_command_superseded",
                            state.get("error") or "A different command owns the published search",
                        )
                    progress = state.get("progress") or {}
                    if progress.get("phase") in {"completed", "cancelled", "failed"}:
                        return {
                            "phase": progress["phase"],
                            "acknowledgement": acknowledgement,
                            "state": state,
                        }
                else:
                    if (
                        state.get("error")
                        and state["last_command"] == acknowledgement["command_id"]
                    ):
                        raise InvestigationError("runtime_command_failed", state["error"])
                    return {
                        "phase": "applied",
                        "acknowledgement": acknowledgement,
                        "state": state,
                    }
            time.sleep(0.05)
        raise InvestigationError(
            "runtime_command_timeout",
            "Timed out waiting for the runtime; inspect status before retrying",
            request_id=request_id,
            command_id=(acknowledgement.get("command_id") if acknowledgement else None),
        )
    finally:
        request_path.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)
