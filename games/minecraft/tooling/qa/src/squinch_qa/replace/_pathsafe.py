from __future__ import annotations

from pathlib import Path

from squinch_qa.errors import ReplaceError


def assert_within(root: Path, candidate: Path) -> Path:
    """Resolve candidate and verify it is root itself or strictly inside it.

    Catches '..' segments, absolute-path escapes, and symlink escapes by
    resolving both paths and checking containment on the resolved forms.
    Raises ReplaceError(reason="path_escape") on any violation.
    """
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError:
        raise ReplaceError(
            reason="path_escape",
            message=f"{candidate} resolves to {resolved_candidate}, outside {resolved_root}",
        ) from None
    return resolved_candidate
