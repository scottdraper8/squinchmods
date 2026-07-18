from __future__ import annotations

import time
from pathlib import Path

from squinch_qa.errors import ReplaceError

# Written last in each stage — if a sentinel is missing, that stage's work is
# unambiguously incomplete (crashed mid-write) and safe to delete/redo.
INCOMING_READY = ".complete"
STAGING_READY = ".ready"


def path_id_safe(value: str, label: str) -> str:
    """Validate a configured identity before it becomes one path segment."""
    if not value or "/" in value or "\\" in value or value in (".", ".."):
        raise ReplaceError(
            reason="unsafe_storage_id",
            message=f"{label} {value!r} is not filesystem-safe",
        )
    return value


def matrix_id_safe(target_id: str, test_id: str) -> str:
    """Filesystem-safe, unambiguous encoding of a (target, test) pair."""
    for part, label in (target_id, "target_id"), (test_id, "test_id"):
        if not part or "/" in part or "\\" in part or part in (".", ".."):
            raise ReplaceError(
                reason="unsafe_matrix_id",
                message=f"{label} {part!r} is not filesystem-safe",
            )
    return f"{target_id}__{test_id}"


def incoming_dir(qa_root: Path) -> Path:
    return qa_root / "incoming"


def staging_dir(qa_root: Path) -> Path:
    return qa_root / "staging"


def current_dir(qa_root: Path) -> Path:
    return qa_root / "current"


def trash_dir(qa_root: Path) -> Path:
    return qa_root / "trash"


def identity_parts(mod_id: str, target_id: str, test_id: str) -> tuple[str, str, str]:
    return (
        path_id_safe(mod_id, "mod_id"),
        path_id_safe(target_id, "target_id"),
        path_id_safe(test_id, "test_id"),
    )


def identity_dir(root: Path, mod_id: str, target_id: str, test_id: str) -> Path:
    safe_mod_id, safe_target_id, safe_test_id = identity_parts(
        mod_id, target_id, test_id
    )
    return root / safe_mod_id / safe_target_id / safe_test_id


def incoming_job_dir(qa_root: Path, mod_id: str, target_id: str, test_id: str) -> Path:
    return identity_dir(incoming_dir(qa_root), mod_id, target_id, test_id)


def staging_job_dir(qa_root: Path, mod_id: str, target_id: str, test_id: str) -> Path:
    return identity_dir(staging_dir(qa_root), mod_id, target_id, test_id)


def current_job_dir(qa_root: Path, mod_id: str, target_id: str, test_id: str) -> Path:
    return identity_dir(current_dir(qa_root), mod_id, target_id, test_id)


def trash_job_dir(
    qa_root: Path, mod_id: str, target_id: str, test_id: str, run_id: str
) -> Path:
    """A fresh, unique destination each call — trash entries are historical, not current state."""
    ts = int(time.time() * 1000)
    return (
        identity_dir(trash_dir(qa_root), mod_id, target_id, test_id) / f"{ts}-{run_id}"
    )


def _stat_dev(path: Path) -> int:
    """st_dev of path, walking up to the nearest existing ancestor."""
    p = path
    while not p.exists():
        parent = p.parent
        if parent == p:
            raise ReplaceError(
                reason="no_existing_ancestor",
                message=f"no existing ancestor found for {path}",
            )
        p = parent
    return p.stat().st_dev


def assert_same_device(*paths: Path) -> None:
    """Raise ReplaceError(reason="cross_device") if paths don't share a filesystem.

    os.replace (used for the atomic swap) requires source and destination to be
    on the same device — check this early, before any writes, rather than
    failing partway through a promotion.
    """
    devs = {p: _stat_dev(p) for p in paths}
    if len(set(devs.values())) > 1:
        detail = ", ".join(f"{p}={d}" for p, d in devs.items())
        raise ReplaceError(
            reason="cross_device",
            message=f"paths span multiple filesystems: {detail}",
        )
