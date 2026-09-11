from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .paths import sha256_file, steam_build_id, steam_manifest


def pak_files(game_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in (game_root / "GAMEDATA/PCBANKS").iterdir()
            if path.is_file() and path.suffix.casefold() == ".pak"
        ),
        key=lambda path: path.name.casefold(),
    )


def archive_snapshot(game_root: Path) -> dict:
    records = [
        {"name": path.name, "bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
        for path in pak_files(game_root)
    ]
    digest = hashlib.sha256()
    for record in records:
        digest.update(f"{record['name']}\0{record['bytes']}\0{record['mtime_ns']}\n".encode())
    return {"count": len(records), "metadata_sha256": digest.hexdigest(), "archives": records}


def running_processes() -> list[dict]:
    values: list[dict] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return values
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, PermissionError):
            continue
        if name.casefold() == "nms.exe":
            values.append({"pid": int(entry.name), "name": name})
    return sorted(values, key=lambda value: value["pid"])


def host_health() -> dict:
    blocked: list[dict] = []
    proc = Path("/proc")
    if proc.is_dir():
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat_fields = (entry / "stat").read_text(encoding="utf-8").split()
                if len(stat_fields) < 3 or stat_fields[2] != "D":
                    continue
                name = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
                cgroup = (entry / "cgroup").read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue
            blocked.append(
                {
                    "pid": int(entry.name),
                    "name": name,
                    "investigation_owned": "squinch-mc-" in cgroup,
                }
            )
    try:
        load_average = Path("/proc/loadavg").read_text(encoding="ascii").split()[:3]
    except OSError:
        load_average = []
    return {
        "healthy": not blocked,
        "load_average": load_average,
        "uninterruptible_processes": sorted(blocked, key=lambda value: value["pid"]),
    }


def game_identity(
    game_root: Path, *, include_archives: bool = True, include_executable_hash: bool = True
) -> dict:
    executable = game_root / "Binaries/NMS.exe"
    manifest = steam_manifest(game_root)
    result = {
        "game_root": str(game_root),
        "steam_manifest": str(manifest) if manifest else None,
        "steam_build_id": steam_build_id(game_root),
        "executable": {
            "path": str(executable),
            "bytes": executable.stat().st_size,
            "sha256": sha256_file(executable) if include_executable_hash else None,
        },
        "mods_directory": str(game_root / "GAMEDATA/MODS"),
        "disablemods_present": (game_root / "GAMEDATA/PCBANKS/DISABLEMODS.TXT").exists(),
        "running_processes": running_processes(),
    }
    if include_archives:
        result["pak_snapshot"] = archive_snapshot(game_root)
    return result


def host_capabilities() -> dict:
    return {
        "uv": shutil.which("uv"),
        "podman": shutil.which("podman"),
        "dotnet": shutil.which("dotnet"),
        "platform": os.uname().sysname if hasattr(os, "uname") else os.name,
    }
