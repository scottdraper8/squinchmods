from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from .errors import InvestigationError
from .paths import sha256_file


def _git(repository: Path, *args: str, required: bool = True) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        if not required:
            return None
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown Git error"
        raise InvestigationError("git_failed", message, arguments=list(args))
    return completed.stdout.strip()


def _selected_file(repository: Path, value: str) -> tuple[str, Path]:
    logical = PurePosixPath(value)
    if not value or logical.is_absolute() or ".." in logical.parts or str(logical) in {"", "."}:
        raise InvestigationError("invalid_source_path", f"Invalid selected source path: {value}")
    normalized = logical.as_posix()
    target = (repository / normalized).resolve()
    try:
        target.relative_to(repository)
    except ValueError as exc:
        raise InvestigationError(
            "source_path_escape", f"Selected source path escapes the repository: {value}"
        ) from exc
    if not target.is_file() or target.is_symlink():
        raise InvestigationError(
            "source_file_not_found", f"Selected source is not a regular file: {normalized}"
        )
    _git(repository, "ls-files", "--error-unmatch", "--", normalized)
    return normalized, target


def snapshot_source(
    repository: Path,
    selected_files: list[str],
    destination: Path,
    *,
    patterns: list[str] | None = None,
    limit: int = 500,
    allow_dirty: bool = False,
) -> dict:
    root = repository.expanduser().resolve()
    if not root.is_dir():
        raise InvestigationError("source_repository_not_found", f"Not a directory: {root}")
    discovered = _git(root, "rev-parse", "--show-toplevel")
    if discovered is None or Path(discovered).resolve() != root:
        raise InvestigationError(
            "source_repository_root_required",
            f"Source path must be the exact Git worktree root: {root}",
            discovered=discovered,
        )
    if not selected_files:
        raise InvestigationError("source_files_required", "Select at least one tracked source file")
    if len(set(selected_files)) != len(selected_files):
        raise InvestigationError("duplicate_source_file", "Selected source files must be unique")
    if limit < 1:
        raise InvestigationError("invalid_limit", "Source match result limit must be positive")

    status_text = _git(root, "status", "--porcelain=v1", "--untracked-files=all") or ""
    status = status_text.splitlines()
    if status and not allow_dirty:
        raise InvestigationError(
            "dirty_source_repository",
            "Source repository has working-tree changes; pass --allow-dirty only for "
            "diagnostic evidence",
            status=status,
        )

    try:
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns or []]
    except re.error as exc:
        raise InvestigationError("invalid_pattern", f"Invalid source pattern: {exc}") from exc

    destination.mkdir(parents=True, exist_ok=False)
    pattern_counts = {pattern: 0 for pattern in patterns or []}
    matches: list[dict] = []
    records: list[dict] = []
    for value in selected_files:
        logical, source = _selected_file(root, value)
        target = destination / logical
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        text = source.read_text(encoding="utf-8", errors="replace")
        records.append(
            {
                "logical_path": logical,
                "source_path": str(source),
                "snapshot_path": str(target),
                "bytes": source.stat().st_size,
                "sha256": sha256_file(source),
                "git_blob": _git(root, "rev-parse", f"HEAD:{logical}"),
            }
        )
        for line_number, line in enumerate(text.splitlines(), start=1):
            matching = [
                pattern
                for pattern, regex in zip(patterns or [], compiled, strict=True)
                if regex.search(line)
            ]
            if not matching:
                continue
            for pattern in matching:
                pattern_counts[pattern] += 1
            matches.append(
                {
                    "logical_path": logical,
                    "line": line_number,
                    "value": line[:1000],
                    "patterns": matching,
                }
            )

    revision = _git(root, "rev-parse", "HEAD")
    upstream = _git(
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        required=False,
    )
    upstream_revision = _git(root, "rev-parse", upstream, required=False) if upstream else None
    ahead_behind = None
    if upstream_revision:
        counts = _git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        if counts:
            ahead, behind = counts.split()
            ahead_behind = {"ahead": int(ahead), "behind": int(behind)}
    return {
        "repository": str(root),
        "origin": _git(root, "remote", "get-url", "origin", required=False),
        "revision": revision,
        "branch": _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", required=False),
        "upstream": upstream,
        "upstream_revision": upstream_revision,
        "ahead_behind": ahead_behind,
        "commit_time": _git(root, "show", "-s", "--format=%cI", "HEAD"),
        "dirty": bool(status),
        "status": status,
        "allow_dirty": allow_dirty,
        "files": records,
        "patterns": patterns or [],
        "pattern_counts": pattern_counts,
        "all_patterns_matched": all(pattern_counts.values()),
        "match_count": len(matches),
        "matches": matches[:limit],
        "matches_truncated": len(matches) > limit,
        "authority": "selected-files-at-local-git-revision",
    }
