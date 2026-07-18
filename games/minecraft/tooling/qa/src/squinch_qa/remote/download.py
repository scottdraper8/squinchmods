from __future__ import annotations

from pathlib import Path

from squinch_qa.artifacts import is_valid_run_id
from squinch_qa.remote import _gh
from squinch_qa.remote.errors import DownloadError, GhError
from squinch_qa.replace._pathsafe import assert_within


def download_run(
    *,
    database_id: int,
    run_id: str,
    qa_runs_dir: Path,
    repo_root: Path | None = None,
    gh_timeout: float = 120.0,
) -> Path:
    if not is_valid_run_id(run_id):
        raise DownloadError(f"invalid run_id {run_id!r}; expected <unix_ms>-<hex8>")

    qa_runs_dir.mkdir(parents=True, exist_ok=True)
    run_dir = assert_within(qa_runs_dir, qa_runs_dir / run_id)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise DownloadError(f"{run_dir} already exists and is not empty")
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        _gh.run_gh(
            "run",
            "download",
            str(database_id),
            "--name",
            f"qa-{run_id}",
            "--dir",
            str(run_dir),
            timeout=gh_timeout,
            cwd=repo_root,
        )
    except GhError as e:
        raise DownloadError(str(e)) from e

    if not (run_dir / "qa-manifest.json").is_file():
        raise DownloadError(f"downloaded artifact qa-{run_id} has no qa-manifest.json")
    return run_dir
