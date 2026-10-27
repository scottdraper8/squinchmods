from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from pathlib import Path

from squinch_qa.errors import ConfigError

TRANCHE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def require_tranche() -> tuple[str, Path]:
    tranche_id = os.environ.get("SQUINCH_TRANCHE", "")
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE", "")
    if TRANCHE_ID.fullmatch(tranche_id) is None or not workspace_value:
        raise ConfigError(
            "select an existing tranche with tooling/squinch --tranche <id>"
        )
    workspace = Path(workspace_value)
    if (
        not workspace.is_absolute()
        or workspace.is_symlink()
        or not workspace.is_dir()
        or workspace.resolve() != workspace
    ):
        raise ConfigError("selected tranche workspace is unsafe")
    try:
        value = json.loads((workspace / ".tranche.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("selected tranche metadata is unreadable") from exc
    if value != {
        "schema_version": 1,
        "tranche": tranche_id,
        "workspace": str(workspace),
    }:
        raise ConfigError("selected tranche metadata does not match")
    return tranche_id, workspace


def prepare_owned_directory(*parts: str) -> Path:
    _tranche_id, workspace = require_tranche()
    current = workspace
    for part in parts:
        if not part or Path(part).parts != (part,) or part in {".", ".."}:
            raise ConfigError("invalid tranche directory component")
        current /= part
        with suppress(FileExistsError):
            current.mkdir()
        if current.is_symlink() or not current.is_dir() or current.resolve() != current:
            raise ConfigError(f"tranche output directory is unsafe: {current}")
    return current


def require_scratch_input(path: Path) -> Path:
    _tranche_id, workspace = require_tranche()
    lexical = Path(os.path.abspath(path.expanduser()))
    if lexical == workspace or not lexical.is_relative_to(workspace):
        raise ConfigError(
            f"task-local plan must be inside the selected tranche: {lexical}"
        )
    current = workspace
    for part in lexical.relative_to(workspace).parts:
        current /= part
        if current.is_symlink():
            raise ConfigError(f"task-local plan traverses a symbolic link: {current}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace):
        raise ConfigError(f"task-local plan escapes through a symbolic link: {lexical}")
    return resolved
