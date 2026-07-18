from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from squinch_qa.artifacts import (
    default_qa_root,
    default_qa_runs_dir,
    is_valid_run_id,
    make_run_id,
)
from squinch_qa.remote.dispatch import dispatch_run
from squinch_qa.remote.download import download_run
from squinch_qa.remote.errors import DispatchError
from squinch_qa.remote.poll import wait_for_completion
from squinch_qa.replace import promote_run, recover_pending

Emit = Callable[[dict], None]


def _noop_emit(_: dict) -> None:
    return None


def _downloaded_exit_code(run_dir: Path, default: int) -> int:
    try:
        data = json.loads((run_dir / "result.json").read_text())
    except (OSError, json.JSONDecodeError):
        return default
    exit_code = data.get("exit_code")
    if isinstance(exit_code, int) and 0 <= exit_code <= 255:
        return exit_code
    return default


def remote_run(
    *,
    mod: str,
    repo_root: Path,
    qa_runs_dir: Path | None = None,
    target: str | None = None,
    profile: str | None = None,
    promote: bool = False,
    poll_interval: float = 5.0,
    timeout: float = 1800.0,
    run_id: str | None = None,
    clean: bool = True,
    emit: Emit = _noop_emit,
) -> int:
    run_id = run_id or make_run_id()
    if not is_valid_run_id(run_id):
        raise DispatchError(f"invalid run_id {run_id!r}; expected <unix_ms>-<hex8>")
    qa_root = default_qa_root(repo_root)
    qa_runs_dir = qa_runs_dir or default_qa_runs_dir(repo_root)

    emit(
        {
            "type": "remote_run_start",
            "run_id": run_id,
            "mod": mod,
            "target": target,
            "profile": profile,
        }
    )
    dispatch_run(
        mod=mod,
        run_id=run_id,
        target=target,
        profile=profile,
        repo_root=repo_root,
    )
    emit({"type": "remote_dispatched", "run_id": run_id})

    completion = wait_for_completion(
        run_id,
        repo_root=repo_root,
        poll_interval=poll_interval,
        timeout=timeout,
    )
    emit(
        {
            "type": "remote_completed",
            "run_id": run_id,
            "database_id": completion.database_id,
            "conclusion": completion.conclusion,
        }
    )

    run_dir = download_run(
        database_id=completion.database_id,
        run_id=run_id,
        qa_runs_dir=qa_runs_dir,
        repo_root=repo_root,
    )
    emit({"type": "remote_downloaded", "run_id": run_id, "run_dir": str(run_dir)})

    exit_code = _downloaded_exit_code(
        run_dir, default=0 if completion.conclusion == "success" else 4
    )
    if promote and exit_code == 0 and completion.conclusion == "success":
        emit({"type": "promote_start", "run_id": run_id})
        recover_pending(qa_root)
        promote_results = promote_run(qa_root, run_dir)

        for r in promote_results:
            emit(
                {
                    "type": "promote_job",
                    "mod_id": r.mod_id,
                    "target": r.target_id,
                    "test": r.test_id,
                    "promoted": r.promoted,
                    "reason": r.reason,
                }
            )
        emit({"type": "promote_done", "run_id": run_id})
        if any(r.is_failure for r in promote_results):
            exit_code = 6

    if clean:
        from squinch_qa.cleanup import clean_qa

        try:
            actions = clean_qa(qa_root)
            emit({"type": "clean_done", "count": len(actions), "dry_run": False})
        except Exception as exc:
            emit({"type": "clean_error", "error": str(exc)})

    emit(
        {
            "type": "remote_run_complete",
            "run_id": run_id,
            "status": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
        }
    )
    return exit_code
