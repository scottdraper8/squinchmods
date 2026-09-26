from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squinch_qa.remote import _gh
from squinch_qa.remote.dispatch import WORKFLOW_FILE
from squinch_qa.remote.errors import GhError, PollError, PollTimeoutError


@dataclass(frozen=True)
class RemoteRun:
    database_id: int
    name: str | None
    status: str | None
    conclusion: str | None
    created_at: str | None = None


@dataclass(frozen=True)
class RunCompletion:
    database_id: int
    status: str
    conclusion: str | None


def _load_json_array(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PollError(f"gh run list returned invalid JSON: {e}") from e
    if not isinstance(data, list):
        raise PollError("gh run list returned JSON that is not an array")
    return data


def _load_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PollError(f"gh run view returned invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise PollError("gh run view returned JSON that is not an object")
    return data


def _run_title(item: dict[str, Any]) -> str | None:
    for key in ("name", "displayTitle", "title"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def find_dispatched_run(
    run_id: str,
    *,
    repo_root: Path | None = None,
    gh_timeout: float = 30.0,
) -> RemoteRun | None:
    try:
        result = _gh.run_gh(
            "run",
            "list",
            "--workflow",
            WORKFLOW_FILE,
            "--event",
            "workflow_dispatch",
            "--limit",
            "50",
            "--json",
            "databaseId,name,displayTitle,status,conclusion,createdAt",
            timeout=gh_timeout,
            cwd=repo_root,
        )
    except GhError as e:
        raise PollError(str(e)) from e

    expected_name = f"qa-{run_id}"
    for item in _load_json_array(result.stdout):
        title = _run_title(item)
        if title != expected_name:
            continue
        database_id = item.get("databaseId")
        if not isinstance(database_id, int):
            raise PollError(f"matched run {expected_name} has no integer databaseId")
        return RemoteRun(
            database_id=database_id,
            name=title,
            status=item.get("status") if isinstance(item.get("status"), str) else None,
            conclusion=item.get("conclusion")
            if isinstance(item.get("conclusion"), str)
            else None,
            created_at=item.get("createdAt")
            if isinstance(item.get("createdAt"), str)
            else None,
        )
    return None


def _view_run(
    database_id: int,
    *,
    repo_root: Path | None,
    gh_timeout: float,
) -> RunCompletion:
    try:
        result = _gh.run_gh(
            "run",
            "view",
            str(database_id),
            "--json",
            "status,conclusion",
            timeout=gh_timeout,
            cwd=repo_root,
        )
    except GhError as e:
        raise PollError(str(e)) from e

    data = _load_json_object(result.stdout)
    status = data.get("status")
    if not isinstance(status, str):
        raise PollError(f"gh run view {database_id} returned no string status")
    conclusion = data.get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise PollError(f"gh run view {database_id} returned invalid conclusion")
    return RunCompletion(database_id=database_id, status=status, conclusion=conclusion)


def wait_for_completion(
    run_id: str,
    *,
    repo_root: Path | None = None,
    poll_interval: float = 5.0,
    timeout: float = 1800.0,
    gh_timeout: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> RunCompletion:
    deadline = monotonic() + timeout
    last_run: RemoteRun | None = None

    while True:
        now = monotonic()
        if now >= deadline:
            if last_run is None:
                raise PollTimeoutError(
                    f"timed out after {timeout:g}s waiting for qa-{run_id} to appear"
                )
            raise PollTimeoutError(
                f"timed out after {timeout:g}s waiting for run {last_run.database_id}"
            )

        remote_run = find_dispatched_run(
            run_id, repo_root=repo_root, gh_timeout=gh_timeout
        )
        if remote_run is not None:
            last_run = remote_run
            completion = _view_run(
                remote_run.database_id, repo_root=repo_root, gh_timeout=gh_timeout
            )
            if completion.status == "completed":
                return completion

        sleep(min(poll_interval, max(0.0, deadline - now)))
