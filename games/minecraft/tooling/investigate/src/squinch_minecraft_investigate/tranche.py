from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from pathlib import Path

from .errors import InvestigationError

TRANCHE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def require_tranche() -> tuple[str, Path]:
    tranche_id = os.environ.get("SQUINCH_TRANCHE", "")
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE", "")
    if TRANCHE_ID.fullmatch(tranche_id) is None or not workspace_value:
        raise InvestigationError(
            "tranche_required",
            "select an existing tranche with tooling/squinch --tranche <id>",
        )
    workspace = Path(workspace_value)
    if (
        not workspace.is_absolute()
        or workspace.is_symlink()
        or not workspace.is_dir()
        or workspace.resolve() != workspace
    ):
        raise InvestigationError(
            "invalid_tranche", "selected tranche workspace is unsafe"
        )
    metadata = workspace / ".tranche.json"
    try:
        value = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvestigationError(
            "invalid_tranche", "selected tranche metadata is unreadable"
        ) from exc
    if value != {
        "schema_version": 1,
        "tranche": tranche_id,
        "workspace": str(workspace),
    }:
        raise InvestigationError(
            "invalid_tranche", "selected tranche metadata does not match"
        )
    return tranche_id, workspace


def prepare_owned_directory(*parts: str) -> Path:
    _tranche_id, workspace = require_tranche()
    current = workspace
    for part in parts:
        if not part or Path(part).parts != (part,) or part in {".", ".."}:
            raise InvestigationError(
                "invalid_owned_path", "invalid tranche directory component"
            )
        current /= part
        with suppress(FileExistsError):
            current.mkdir()
        if current.is_symlink() or not current.is_dir() or current.resolve() != current:
            raise InvestigationError(
                "unsafe_owned_path", f"tranche output directory is unsafe: {current}"
            )
    return current


def require_scratch_input(path: Path) -> Path:
    _tranche_id, workspace = require_tranche()
    lexical = Path(os.path.abspath(path.expanduser()))
    if lexical == workspace or not lexical.is_relative_to(workspace):
        raise InvestigationError(
            "unowned_scratch_input",
            f"task-local input must be inside the selected tranche workspace: {lexical}",
        )
    current = workspace
    for part in lexical.relative_to(workspace).parts:
        current /= part
        if current.is_symlink():
            raise InvestigationError(
                "unsafe_scratch_input",
                f"task-local input traverses a symbolic link: {current}",
            )
    resolved = lexical.resolve()
    if not resolved.is_relative_to(workspace):
        raise InvestigationError(
            "unsafe_scratch_input",
            f"task-local input escapes through a symbolic link: {lexical}",
        )
    return resolved


def validate_cli_inputs(args: object) -> None:
    command = getattr(args, "command", None)
    fields: tuple[str, ...] = ()
    if command in {"start", "run"}:
        fields = ("datapack", "probe_pack")
    elif command == "client":
        fields = ("probe_pack",)
    elif command == "scenario":
        fields = ("scenario_file",)
    elif command == "benchmark":
        fields = ("benchmark_file",)
    elif command in {"cell-scan", "preset-export"}:
        fields = ("preset",)
    elif command == "probe":
        fields = ("config",)
    for field in fields:
        value = getattr(args, field, None)
        if value is None:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            require_scratch_input(Path(item))


def validate_scenario_inputs(scenario: object) -> None:
    paths = [scenario.path]
    for name in (
        "ftf_preset",
        "subject_artifact",
        "subject_compile_artifact",
    ):
        value = getattr(scenario, name)
        if value is not None:
            paths.append(value)
    paths.extend(scenario.datapacks)
    paths.extend(source for source, _target in scenario.runtime_files)
    paths.extend(scenario.probe_packs)
    for step in scenario.steps:
        candidate = step.values.get("candidate_file")
        if candidate is not None:
            paths.append(candidate)
    for path in paths:
        require_scratch_input(Path(path))
