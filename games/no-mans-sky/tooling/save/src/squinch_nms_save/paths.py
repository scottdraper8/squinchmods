from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import SaveToolError
from .meta import meta_path

SAVE_NAME = re.compile(r"^save(?:(\d+))?\.hg$", re.IGNORECASE)


@dataclass(frozen=True)
class SaveIdentity:
    path: Path
    meta_path: Path
    ordinal: int
    slot: int
    kind: str


def default_nms_root() -> Path:
    return (
        Path.home()
        / ".local/share/Steam/steamapps/compatdata/275850/pfx/drive_c/users/steamuser"
        / "AppData/Roaming/HelloGames/NMS"
    )


def discover_profile(root: Path | None = None) -> Path:
    nms_root = (root or default_nms_root()).expanduser()
    if not nms_root.is_dir():
        raise SaveToolError(f"NMS save root does not exist: {nms_root}")
    profiles = sorted(
        path.resolve()
        for path in nms_root.iterdir()
        if path.is_dir() and any(SAVE_NAME.fullmatch(item.name) for item in path.iterdir())
    )
    if len(profiles) != 1:
        raise SaveToolError(
            f"expected exactly one NMS profile under {nms_root}, found {len(profiles)}; "
            "pass --directory explicitly"
        )
    return profiles[0]


def identity(path: Path) -> SaveIdentity:
    expanded = path.expanduser().absolute()
    if expanded.is_symlink():
        raise SaveToolError(f"save must not be a symlink: {expanded}")
    resolved = expanded.resolve()
    match = SAVE_NAME.fullmatch(resolved.name)
    if not match:
        raise SaveToolError(f"unsupported PC save filename: {resolved.name}")
    ordinal = int(match.group(1) or 1)
    if not 1 <= ordinal <= 20:
        raise SaveToolError(f"save ordinal must be between 1 and 20: {resolved.name}")
    return SaveIdentity(
        path=resolved,
        meta_path=meta_path(resolved),
        ordinal=ordinal,
        slot=(ordinal + 1) // 2,
        kind="auto" if ordinal % 2 else "manual",
    )


def list_saves(directory: Path) -> list[SaveIdentity]:
    profile = directory.expanduser().resolve()
    if not profile.is_dir():
        raise SaveToolError(f"save directory does not exist: {profile}")
    saves = [identity(path) for path in profile.iterdir() if SAVE_NAME.fullmatch(path.name)]
    return sorted(saves, key=lambda item: item.ordinal)


def require_pair(save: SaveIdentity) -> None:
    for label, path in (("save", save.path), ("metadata companion", save.meta_path)):
        if not path.is_file() or path.is_symlink():
            raise SaveToolError(f"{label} must be a regular, non-symlink file: {path}")
