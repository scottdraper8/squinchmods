from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from squinch_qa.errors import ValidationError


def world_hash(directory: Path) -> str:
    outer = hashlib.sha256()
    for relpath in _sorted_relpaths(directory):
        full = directory / relpath
        file_hash = _sha256_file(full)
        executable_bit = 1 if (full.lstat().st_mode & 0o100) else 0
        entry = hashlib.sha256()
        entry.update(str(relpath).encode())
        entry.update(bytes([executable_bit]))
        entry.update(bytes.fromhex(file_hash))
        outer.update(entry.digest())
    return outer.hexdigest()


def _sorted_relpaths(directory: Path) -> list[Path]:
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
    mode = full.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValidationError("world_unsupported_entry", f"symlink in world: {relpath}")
    if not stat.S_ISDIR(mode) and not stat.S_ISREG(mode):
        raise ValidationError(
            "world_unsupported_entry", f"unsupported world entry: {relpath}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(65536), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValidationError(
            "world_unsupported_entry", f"unreadable world file: {path}"
        ) from exc
    return digest.hexdigest()
