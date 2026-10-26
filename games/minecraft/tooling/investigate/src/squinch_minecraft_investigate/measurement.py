from __future__ import annotations

import hashlib
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from .errors import InvestigationError

POLL_INTERVAL_SECONDS = 0.25
STABLE_POLLS_REQUIRED = 2


def _relative_run_file(run_dir: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or value in {"", "."}:
        raise InvestigationError(
            "invalid_measurement_path",
            f"measurement path must stay inside the run directory: {value}",
        )
    path = (run_dir / relative).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise InvestigationError(
            "invalid_measurement_path",
            f"measurement path escapes the run directory: {value}",
        ) from exc
    return path


def _file_signature(path: Path) -> dict | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    if not path.is_file():
        return None
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def snapshot_measurement_files(
    run_dir: Path, paths: list[str]
) -> dict[str, dict | None]:
    return {
        value: _file_signature(_relative_run_file(run_dir, value)) for value in paths
    }


def wait_for_measurement(
    *,
    log_path: Path,
    log_start: int,
    run_dir: Path,
    capture_files: list[str],
    before_files: dict[str, dict | None],
    wait_for_log: str | None,
    fail_on_log: list[str],
    timeout: float,
    health_check: Callable[[], None],
) -> dict:
    """Wait until a command-owned log marker and output files are complete."""
    completion_pattern = re.compile(wait_for_log) if wait_for_log else None
    failure_patterns = [(value, re.compile(value)) for value in fail_on_log]
    started = time.monotonic()
    log_position = log_start
    log_text = ""
    file_state: dict[str, dict] = {
        value: {"signature": None, "stable_polls": 0, "changed": False}
        for value in capture_files
    }

    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            raise InvestigationError(
                "measurement_timeout",
                "timed out waiting for measured command completion",
                details={
                    "timeout_seconds": timeout,
                    "wait_for_log": wait_for_log,
                    "capture_files": capture_files,
                    "log_tail": log_text[-8000:],
                    "file_state": file_state,
                },
            )

        health_check()
        if log_path.exists():
            with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(log_position)
                chunk = handle.read()
                log_position = handle.tell()
            if chunk:
                log_text += chunk
                for expression, pattern in failure_patterns:
                    match = pattern.search(log_text)
                    if match:
                        raise InvestigationError(
                            "measurement_failed",
                            "measured command emitted a configured failure marker",
                            details={
                                "pattern": expression,
                                "match": match.group(0),
                                "log_tail": log_text[-8000:],
                            },
                        )

        files_complete = True
        for value in capture_files:
            current = _file_signature(_relative_run_file(run_dir, value))
            entry = file_state[value]
            changed = current is not None and current != before_files.get(value)
            entry["changed"] = changed
            if not changed:
                entry["signature"] = current
                entry["stable_polls"] = 0
                files_complete = False
                continue
            if entry["signature"] == current:
                entry["stable_polls"] += 1
            else:
                entry["signature"] = current
                entry["stable_polls"] = 1
            if entry["stable_polls"] < STABLE_POLLS_REQUIRED:
                files_complete = False

        log_complete = completion_pattern is None or completion_pattern.search(log_text)
        if log_complete and files_complete:
            return {
                "elapsed_seconds": elapsed,
                "log_start": log_start,
                "log_end": log_position,
                "log_text": log_text,
                "completion_match": (
                    completion_pattern.search(log_text).group(0)
                    if completion_pattern is not None
                    else None
                ),
                "files": file_state,
            }
        time.sleep(POLL_INTERVAL_SECONDS)


def capture_measurement_files(
    run_dir: Path,
    artifact_dir: Path,
    paths: list[str],
) -> list[dict]:
    captured: list[dict] = []
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for value in paths:
        source = _relative_run_file(run_dir, value)
        if not source.is_file():
            raise InvestigationError(
                "measurement_file_missing",
                f"measured command did not produce required file: {value}",
            )
        target = artifact_dir / value
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        captured.append(
            {
                "source": value,
                "artifact": str(target),
                "size": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    return captured


def extract_metrics(
    metrics: list[dict],
    *,
    run_dir: Path,
    command_log: str,
) -> dict[str, dict]:
    values: dict[str, dict] = {}
    source_cache: dict[str, str] = {"server.log": command_log}
    for metric in metrics:
        source = metric["source"]
        if source not in source_cache:
            path = _relative_run_file(run_dir, source)
            try:
                source_cache[source] = path.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError as exc:
                raise InvestigationError(
                    "metric_source_unreadable",
                    f"could not read metric source {source}: {exc}",
                ) from exc
        match_mode = metric.get("match", "first")
        matches = list(
            re.finditer(metric["pattern"], source_cache[source], re.MULTILINE)
        )
        if not matches:
            if metric.get("required", True):
                raise InvestigationError(
                    "metric_not_found",
                    f"metric {metric['id']} did not match source {source}",
                    details={"pattern": metric["pattern"]},
                )
            continue
        selected = matches if match_mode == "all" else matches[:1]
        try:
            raw_values = [match.group(metric["group"]) for match in selected]
        except IndexError as exc:
            raise InvestigationError(
                "metric_group_missing",
                f"metric {metric['id']} requested unavailable capture group",
                details={"group": metric["group"], "pattern": metric["pattern"]},
            ) from exc
        value_type = metric["value_type"]
        converted: list[int | float | str] = []
        try:
            for raw_value in raw_values:
                numeric = raw_value.replace(",", "")
                if value_type == "int":
                    converted.append(int(numeric))
                elif value_type == "float":
                    converted.append(float(numeric))
                else:
                    converted.append(raw_value)
        except ValueError as exc:
            raise InvestigationError(
                "metric_value_invalid",
                f"metric {metric['id']} is not a valid {value_type}: {raw_value}",
            ) from exc
        values[metric["id"]] = {
            "value": converted if match_mode == "all" else converted[0],
            "raw": raw_values if match_mode == "all" else raw_values[0],
            "value_type": value_type,
            "unit": metric.get("unit"),
            "source": source,
            "pattern": metric["pattern"],
            "match": match_mode,
            "count": len(converted),
        }
    return values
