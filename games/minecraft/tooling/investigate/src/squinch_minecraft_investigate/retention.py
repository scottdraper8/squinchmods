from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .errors import InvestigationError

RUN_ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{10}")


def load_protected_run_ids(path: Path) -> set[str]:
    if not path.is_file():
        raise InvestigationError(
            "retention_index_missing", f"investigation retention index not found: {path}"
        )
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise InvestigationError(
            "retention_index_invalid", f"could not read investigation retention index: {path}"
        ) from error

    if value.get("schema_version") != 1:
        raise InvestigationError(
            "retention_index_invalid", "investigation retention index schema_version must be 1"
        )
    run_ids = value.get("protected_runs")
    if not isinstance(run_ids, list) or not all(isinstance(item, str) for item in run_ids):
        raise InvestigationError(
            "retention_index_invalid", "protected_runs must be an array of run ID strings"
        )
    invalid = [run_id for run_id in run_ids if RUN_ID_PATTERN.fullmatch(run_id) is None]
    if invalid:
        raise InvestigationError(
            "retention_index_invalid", f"invalid protected run ID: {invalid[0]!r}"
        )
    if len(run_ids) != len(set(run_ids)):
        raise InvestigationError(
            "retention_index_invalid", "protected_runs contains duplicate run IDs"
        )
    return set(run_ids)
