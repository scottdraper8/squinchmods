from __future__ import annotations

import subprocess
from pathlib import Path

from squinch_qa.artifacts import is_valid_run_id
from squinch_qa.remote import _gh
from squinch_qa.remote.errors import DispatchError, GhError

WORKFLOW_FILE = "qa-remote.yml"


def _current_ref(repo_root: Path) -> str:
    for args in (
        ("git", "symbolic-ref", "--short", "HEAD"),
        ("git", "rev-parse", "HEAD"),
    ):
        try:
            result = subprocess.run(
                args,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise DispatchError(f"could not determine git ref for {repo_root}")


def dispatch_run(
    *,
    mod: str,
    run_id: str,
    target: str | None = None,
    profile: str | None = None,
    repo_root: Path | None = None,
    ref: str | None = None,
    gh_timeout: float = 30.0,
) -> None:
    if not is_valid_run_id(run_id):
        raise DispatchError(f"invalid run_id {run_id!r}; expected <unix_ms>-<hex8>")
    if ref is None and repo_root is not None:
        ref = _current_ref(repo_root)

    args = [
        "workflow",
        "run",
        WORKFLOW_FILE,
        "-f",
        f"run_id={run_id}",
        "-f",
        f"mod={mod}",
    ]
    if ref is not None:
        args.extend(["--ref", ref])
    if target is not None:
        args.extend(["-f", f"target={target}"])
    if profile is not None:
        args.extend(["-f", f"profile={profile}"])

    try:
        _gh.run_gh(*args, timeout=gh_timeout, cwd=repo_root)
    except GhError as e:
        raise DispatchError(str(e)) from e
