from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath

from .errors import InvestigationError

PACKAGE_DIR = Path(__file__).resolve().parents[2]
NMS_DIR = PACKAGE_DIR.parents[1]
REPOSITORY_ROOT = NMS_DIR.parents[1]
STATE_ROOT = NMS_DIR / "investigation-state"
RUNS_ROOT = STATE_ROOT / "runs"
STAGES_ROOT = STATE_ROOT / "stages"
TOOLCHAIN_CONFIG = PACKAGE_DIR / "toolchain.toml"

DEFAULT_GAME_ROOTS = (
    Path.home() / ".local/share/Steam/steamapps/common/No Man's Sky",
    Path.home() / ".steam/steam/steamapps/common/No Man's Sky",
)


def cache_root() -> Path:
    explicit = os.environ.get("SQINCHMODS_CACHE_HOME")
    base = (
        Path(explicit)
        if explicit
        else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "squinchmods"
    )
    return base.expanduser().resolve() / "no-mans-sky" / "toolchains"


def resolve_game_root(value: str | Path | None) -> Path:
    candidates = [Path(value).expanduser()] if value else list(DEFAULT_GAME_ROOTS)
    for candidate in candidates:
        path = candidate.resolve()
        if (path / "Binaries/NMS.exe").is_file() and (path / "GAMEDATA/PCBANKS").is_dir():
            return path
    shown = str(candidates[0]) if value else ", ".join(map(str, candidates))
    raise InvestigationError("game_not_found", f"No valid No Man's Sky installation found: {shown}")


def steam_manifest(game_root: Path) -> Path | None:
    candidate = game_root.parents[1] / "appmanifest_275850.acf"
    return candidate if candidate.is_file() else None


def steam_build_id(game_root: Path) -> str | None:
    manifest = steam_manifest(game_root)
    if not manifest:
        return None
    match = re.search(
        r'"buildid"\s+"([0-9]+)"', manifest.read_text(encoding="utf-8", errors="replace")
    )
    return match.group(1) if match else None


def safe_logical_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise InvestigationError("unsafe_path", f"Unsafe NMS logical path: {value!r}")
    return path.as_posix().lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
