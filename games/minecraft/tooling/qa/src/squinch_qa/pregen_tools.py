from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

MODRINTH_API = "https://api.modrinth.com/v2"

# Verified Modrinth project slugs
TOOL_SLUGS: dict[str, str] = {
    "chunksmith": "chunksmith",
    "chunky": "chunky",
}

LOADER_FALLBACKS: dict[str, tuple[str, ...]] = {
    "quilt": ("quilt", "fabric"),
}


class AcquisitionError(Exception):
    """
    Raised when a pregen tool jar cannot be resolved or downloaded.
    Triggers fallback to the next tool in preference order.
    NOT raised after the jar is loaded and the tool has begun executing in-game.
    """


@dataclass
class AcquiredJar:
    path: Path  # absolute path in cache
    sha256: str  # hex string
    tool_name: str  # "chunksmith" | "chunky"
    version: str  # Modrinth version string
    loader: str | None = None  # effective Modrinth loader used for this jar


def _cache_root() -> Path:
    cache_home = os.environ.get("SQINCHMODS_CACHE_HOME")
    if cache_home:
        base = Path(cache_home)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
        base = base / "squinchmods"
    return base / "qa" / "pregen-tools"


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _modrinth_get(path: str) -> dict | list:
    url = f"{MODRINTH_API}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "squinchmods-qa/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        raise AcquisitionError(f"Modrinth request failed: {url}: {e}") from e


def _fetch_latest_version(slug: str, mc_version: str, loader: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "game_versions": json.dumps([mc_version]),
            "loaders": json.dumps([loader]),
        }
    )
    versions = _modrinth_get(f"/project/{slug}/version?{params}")
    if not versions:
        raise AcquisitionError(
            f"No Modrinth version found for {slug!r} on MC {mc_version} loader {loader}"
        )
    return versions[0]  # newest first by default


def _candidate_files(version: dict) -> list[dict]:
    files = version.get("files", [])
    primary = [f for f in files if f.get("primary")]
    if files:
        return primary + [f for f in files if f not in primary]
    raise AcquisitionError(
        f"Modrinth version {version['id']!r} has no downloadable files"
    )


def _download_file(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": "squinchmods-qa/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.rename(dest)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise AcquisitionError(f"Download failed: {url}: {e}") from e


def _loader_candidates(loader: str) -> tuple[str, ...]:
    return LOADER_FALLBACKS.get(loader, (loader,))


def _jar_supports_loader(jar_path: Path, loader: str) -> bool:
    try:
        with zipfile.ZipFile(jar_path) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False

    if loader in {"fabric", "quilt"}:
        return "fabric.mod.json" in names or "quilt.mod.json" in names
    if loader == "forge":
        return "META-INF/mods.toml" in names
    if loader == "neoforge":
        return "META-INF/neoforge.mods.toml" in names or "META-INF/mods.toml" in names
    return True


def acquire_jar(
    tool_name: str,
    mc_version: str,
    loader: str,
    *,
    pinned_sha256: str | None = None,
) -> AcquiredJar:
    """
    Resolve and cache the pregen tool jar for `tool_name`.

    Fallback semantics:
    - AcquisitionError here → caller should try next tool in preference list.
    - Once this function returns, the jar is trusted; any in-game errors after
      loading are test failures, NOT acquisition errors.

    SQINCHMODS_QA_OFFLINE: if set, raises AcquisitionError when the jar is not in cache.
    """
    offline = bool(os.environ.get("SQINCHMODS_QA_OFFLINE"))
    slug = TOOL_SLUGS.get(tool_name)
    if slug is None:
        raise AcquisitionError(f"Unknown pregen tool: {tool_name!r}")

    tool_cache = _cache_root() / slug

    if offline:
        loader_dirs = [
            tool_cache / candidate for candidate in _loader_candidates(loader)
        ]
        candidates = [
            jar
            for loader_dir in loader_dirs
            for jar in (loader_dir.rglob("*.jar") if loader_dir.exists() else [])
            if _jar_supports_loader(jar, loader)
        ]
        if not candidates:
            raise AcquisitionError(
                f"Offline mode: no cached {loader!r} jar for {tool_name!r} at {tool_cache}"
            )
        jar_path = max(candidates, key=lambda p: p.stat().st_mtime)
        version = jar_path.parent.name
        effective_loader = jar_path.parent.parent.name
        sha256 = _sha256_file(jar_path)
        if pinned_sha256 and sha256 != pinned_sha256:
            raise AcquisitionError(
                f"Cached jar sha256 mismatch for {tool_name!r}: "
                f"expected {pinned_sha256}, got {sha256}"
            )
        return AcquiredJar(
            path=jar_path,
            sha256=sha256,
            tool_name=tool_name,
            version=version,
            loader=effective_loader,
        )

    exhausted_loaders: list[str] = []
    for effective_loader in _loader_candidates(loader):
        try:
            version_obj = _fetch_latest_version(slug, mc_version, effective_loader)
        except AcquisitionError as e:
            exhausted_loaders.append(str(e))
            continue

        version_str = version_obj["version_number"]
        cache_dir = tool_cache / effective_loader / version_str
        for file_entry in _candidate_files(version_obj):
            filename = file_entry["filename"]
            url = file_entry["url"]
            jar_path = cache_dir / filename

            if not jar_path.exists():
                cache_dir.mkdir(parents=True, exist_ok=True)
                _download_file(url, jar_path)

            if not _jar_supports_loader(jar_path, loader):
                jar_path.unlink(missing_ok=True)
                exhausted_loaders.append(
                    f"{filename} from loader {effective_loader!r} is not compatible with {loader!r}"
                )
                continue

            sha256 = _sha256_file(jar_path)
            if pinned_sha256 and sha256 != pinned_sha256:
                jar_path.unlink()
                raise AcquisitionError(
                    f"sha256 mismatch for {tool_name!r} {version_str}: "
                    f"expected {pinned_sha256}, got {sha256}"
                )

            return AcquiredJar(
                path=jar_path,
                sha256=sha256,
                tool_name=tool_name,
                version=version_str,
                loader=effective_loader,
            )

    detail = "; ".join(exhausted_loaders)
    raise AcquisitionError(
        f"No compatible {loader!r} jar found for {tool_name!r} on MC {mc_version}: {detail}"
    )
