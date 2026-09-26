from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import jsonschema

from . import SCHEMA_VERSION

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "cli-output-v1.json"


def timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def envelope(
    command: str,
    state: str,
    *,
    run_id: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    artifact_paths: list[str] | None = None,
    data: dict | None = None,
    error: dict | None = None,
) -> dict:
    value = {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "state": state,
        "run_id": run_id,
        "timestamps": {
            "emitted_at": timestamp(),
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "artifact_paths": artifact_paths or [],
        "error": error,
        "data": data or {},
    }
    jsonschema.validate(value, schema())
    return value


def emit(value: dict, *, json_mode: bool, human: str | None = None) -> None:
    jsonschema.validate(value, schema())
    if json_mode:
        print(json.dumps(value, sort_keys=True))
    elif human:
        print(human)
    else:
        print(json.dumps(value, indent=2, sort_keys=True))
