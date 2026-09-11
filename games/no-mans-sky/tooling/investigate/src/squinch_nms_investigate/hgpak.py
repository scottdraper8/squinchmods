from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .errors import InvestigationError
from .game import pak_files
from .paths import safe_logical_path, sha256_file
from .toolchain import config, hgpak_command


def _execute(
    arguments: list[str], *, cwd: Path, timeout: float = 600
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [*hgpak_command(), *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError("hgpaktool_failed", f"HGPAKtool could not run: {exc}") from exc


def inventory(game_root: Path, destination: Path) -> dict[str, list[str]]:
    archives = pak_files(game_root)
    if not archives:
        raise InvestigationError("no_archives", f"No PAK files found below {game_root}")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "filenames.json"
    result = _execute(
        ["-L", "--platform", config()["hgpaktool"]["platform"], *map(str, archives)],
        cwd=destination,
    )
    if result.returncode != 0 or not output.is_file():
        raise InvestigationError(
            "archive_inventory_failed",
            "HGPAKtool could not inventory the game archives: "
            f"{(result.stderr or result.stdout).strip()}",
        )
    raw = json.loads(output.read_text(encoding="utf-8"))
    normalized: dict[str, list[str]] = {}
    for archive, members in raw.items():
        if not isinstance(members, list):
            raise InvestigationError(
                "invalid_archive_inventory", f"Invalid member list for {archive}"
            )
        normalized[str(Path(archive).resolve())] = [
            safe_logical_path(str(member)) for member in members
        ]
    output.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return normalized


def locate(requested: list[str], catalog: dict[str, list[str]]) -> dict[str, str]:
    reverse: dict[str, list[str]] = {}
    for archive, members in catalog.items():
        for member in members:
            reverse.setdefault(member, []).append(archive)
    result: dict[str, str] = {}
    for value in requested:
        logical = safe_logical_path(value)
        owners = reverse.get(logical, [])
        if not owners:
            raise InvestigationError(
                "asset_not_found", f"Asset is not in the current game archives: {logical}"
            )
        if len(owners) != 1:
            raise InvestigationError(
                "ambiguous_asset",
                f"Asset occurs in multiple game archives: {logical}",
                archives=owners,
            )
        result[logical] = owners[0]
    return result


def extract(requested: list[str], catalog: dict[str, list[str]], destination: Path) -> list[dict]:
    locations = locate(requested, catalog)
    by_archive: dict[str, list[str]] = {}
    for logical, archive in locations.items():
        by_archive.setdefault(archive, []).append(logical)
    request_path = destination.parent / "extract-request.json"
    request_path.write_text(
        json.dumps(by_archive, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    destination.mkdir(parents=True, exist_ok=False)
    result = _execute(
        [
            "-U",
            "--platform",
            config()["hgpaktool"]["platform"],
            "-O",
            str(destination),
            "-j",
            str(request_path),
            str(request_path),
        ],
        cwd=destination.parent,
    )
    if result.returncode != 0:
        raise InvestigationError(
            "asset_extraction_failed",
            f"HGPAKtool extraction failed: {(result.stderr or result.stdout).strip()}",
        )
    records: list[dict] = []
    for logical, archive in sorted(locations.items()):
        path = destination.joinpath(*logical.split("/"))
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "asset_extraction_incomplete", f"HGPAKtool did not produce {logical}"
            )
        archive_path = Path(archive)
        records.append(
            {
                "logical_path": logical,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "archive": str(archive_path),
                "archive_sha256": sha256_file(archive_path),
            }
        )
    manifest_path = destination.parent / f"{destination.name}-manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 1, "files": records}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records
