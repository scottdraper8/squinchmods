from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from squinch_qa.errors import ValidationError


def world_hash(directory: Path) -> str:
    """Deterministic sha256 over a world directory's file contents and executable bits.

    Raises ValidationError(reason="world_unsupported_entry") on symlinks, sockets,
    devices, or unreadable files — a world dir should only ever contain plain
    files and directories, and a world save that doesn't meet that shouldn't be
    silently hashed as if it were trustworthy.
    """
    outer = hashlib.sha256()
    for relpath in _sorted_relpaths(directory):
        full = directory / relpath
        st = full.lstat()
        try:
            file_hash = _sha256_file(full)
        except OSError as e:
            raise ValidationError(
                reason="world_unsupported_entry",
                message=f"unreadable file in world dir: {relpath} ({e})",
            ) from e
        executable_bit = 1 if (st.st_mode & 0o100) else 0
        entry = hashlib.sha256()
        entry.update(str(relpath).encode())
        entry.update(bytes([executable_bit]))
        entry.update(bytes.fromhex(file_hash))
        outer.update(entry.digest())
    return outer.hexdigest()


def _sorted_relpaths(directory: Path) -> list[Path]:
    """All regular-file relpaths under directory, sorted. Validates every entry
    (both directories and files) as it walks, so a symlinked subdirectory is
    caught even though os.walk(followlinks=False) would otherwise just skip
    descending into it silently."""
    result: list[Path] = []
    for root, dirnames, filenames in os.walk(directory, followlinks=False):
        rel_root = Path(root).relative_to(directory)
        dirnames.sort()
        for name in dirnames:
            _check_entry_type(Path(root) / name, _join(rel_root, name))
        for name in sorted(filenames):
            relpath = _join(rel_root, name)
            _check_entry_type(Path(root) / name, relpath)
            result.append(relpath)
    return sorted(result, key=str)


def _join(rel_root: Path, name: str) -> Path:
    return Path(name) if str(rel_root) == "." else rel_root / name


def _check_entry_type(full: Path, relpath: Path) -> None:
    st = full.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise ValidationError(
            reason="world_unsupported_entry",
            message=f"symlink not allowed in world dir: {relpath}",
        )
    if not stat.S_ISDIR(st.st_mode) and not stat.S_ISREG(st.st_mode):
        raise ValidationError(
            reason="world_unsupported_entry",
            message=f"unsupported entry type in world dir: {relpath}",
        )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
