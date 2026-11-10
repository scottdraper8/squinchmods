from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

from .codec import RawNumber

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/cli-output-v1.json"


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@lru_cache(maxsize=1)
def schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def jsonable(value: Any) -> Any:
    if isinstance(value, RawNumber):
        return json.loads(value.text)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def envelope(
    command: str,
    state: str,
    *,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    artifact_paths: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    now = timestamp()
    value = {
        "schema_version": "1",
        "command": command,
        "state": state,
        "run_id": run_id,
        "timestamps": {"emitted_at": now, "started_at": None, "finished_at": now},
        "artifact_paths": artifact_paths or [],
        "error": error,
        "data": jsonable(data or {}),
    }
    jsonschema.validate(value, schema())
    return value


def emit(value: dict[str, Any], *, error: bool = False) -> None:
    jsonschema.validate(value, schema())
    print(json.dumps(value, sort_keys=True), file=sys.stderr if error else sys.stdout)
