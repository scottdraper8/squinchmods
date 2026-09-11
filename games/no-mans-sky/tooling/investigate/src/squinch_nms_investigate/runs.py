from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvestigationError
from .output import timestamp
from .paths import RUNS_ROOT

RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-z0-9-]+-[0-9a-f]{8}$")


@dataclass(frozen=True)
class Run:
    id: str
    path: Path
    started_at: str

    def write(self, name: str, value: object) -> Path:
        target = self.path / name
        write_json(target, value)
        return target


def write_json(target: Path, value: object) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def create_run(command: str, inputs: dict) -> Run:
    started = timestamp()
    prefix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9]+", "-", command.lower()).strip("-")
    run_id = f"{prefix}-{slug}-{secrets.token_hex(4)}"
    path = RUNS_ROOT / run_id
    path.mkdir(parents=True, exist_ok=False)
    run = Run(run_id, path, started)
    run.write(
        "request.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": command,
            "started_at": started,
            "inputs": inputs,
        },
    )
    return run


def resolve_run(run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise InvestigationError("invalid_run_id", f"Invalid run ID: {run_id}")
    path = RUNS_ROOT / run_id
    if not path.is_dir() or path.is_symlink() or not (path / "request.json").is_file():
        raise InvestigationError("run_not_found", f"Owned run does not exist: {run_id}")
    return path
