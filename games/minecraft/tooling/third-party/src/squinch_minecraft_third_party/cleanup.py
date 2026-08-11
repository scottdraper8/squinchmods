from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .errors import AcquisitionError
from .modrinth import cache_root


def _single_path_component(value: str, label: str) -> str:
    path = Path(value)
    if not value or path.name != value or value in {".", ".."}:
        raise AcquisitionError(f"{label} must be a single path component: {value!r}")
    return value


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_release_dir(
    version_dir: Path,
    *,
    project: str,
    minecraft_version: str,
    loader: str,
) -> None:
    if version_dir.is_symlink() or not version_dir.is_dir():
        raise AcquisitionError(f"refusing to remove non-directory or symlink: {version_dir}")
    manifest_path = version_dir / "acquisition.json"
    try:
        metadata: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"cannot validate acquisition manifest: {manifest_path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise AcquisitionError(f"acquisition manifest is not an object: {manifest_path}")
    project_metadata = metadata.get("project")
    requested = metadata.get("requested", {})
    if not isinstance(project_metadata, dict) or not isinstance(requested, dict):
        raise AcquisitionError(f"acquisition manifest has invalid identity fields: {manifest_path}")
    recorded_project = project_metadata.get("slug")
    if recorded_project != project or requested.get("minecraft_version") != minecraft_version or requested.get("loader") != loader:
        raise AcquisitionError(f"acquisition manifest does not match requested removal: {manifest_path}")


def _source_path(path: Path, project: str) -> Path:
    candidate = path.expanduser()
    resolved = candidate.resolve(strict=False)
    marker = Path("games") / "minecraft" / "reference" / "sources"
    marker_parts = marker.parts
    if not any(
        resolved.parts[index : index + len(marker_parts)] == marker_parts
        for index in range(len(resolved.parts) - len(marker_parts) + 1)
    ) or len(resolved.parts) < len(marker_parts) + 2:
        raise AcquisitionError(
            "source removal is limited to games/minecraft/reference/sources/<version>/<mod>"
        )
    if resolved.name != project:
        raise AcquisitionError(f"source path does not match project {project!r}: {resolved}")
    if candidate.is_symlink() or resolved in {Path("/"), Path.home().resolve()}:
        raise AcquisitionError(f"refusing unsafe source removal: {candidate}")
    return resolved


def remove_acquired(
    project_name: str,
    minecraft_version: str,
    loader: str,
    *,
    version_number: str | None = None,
    source: Path | None = None,
    destination_root: Path | None = None,
    apply: bool = False,
) -> dict[str, object]:
    """Plan or remove exact, manifest-backed third-party artifacts."""
    project = _single_path_component(project_name, "project")
    minecraft = _single_path_component(minecraft_version, "Minecraft version")
    loader_name = _single_path_component(loader, "loader")
    version = _single_path_component(version_number, "version") if version_number else None

    root = (destination_root or cache_root()).expanduser().resolve(strict=False)
    project_dir = root / minecraft / loader_name / project
    if not _under(project_dir, root) or project_dir.is_symlink():
        raise AcquisitionError(f"refusing unsafe cache removal: {project_dir}")

    if version:
        candidates = [project_dir / version]
    elif project_dir.exists():
        if not project_dir.is_dir() or project_dir.is_symlink():
            raise AcquisitionError(f"refusing unsafe cache removal: {project_dir}")
        candidates = sorted(path for path in project_dir.iterdir() if path.is_dir())
    else:
        candidates = []

    existing_cache: list[Path] = []
    absent_cache: list[Path] = []
    for candidate in candidates:
        if candidate.exists():
            _validate_release_dir(
                candidate,
                project=project,
                minecraft_version=minecraft,
                loader=loader_name,
            )
            existing_cache.append(candidate)
        else:
            absent_cache.append(candidate)

    source_path = _source_path(source, project) if source else None
    if source_path and source_path.exists() and (source_path.is_symlink() or not source_path.is_dir()):
        raise AcquisitionError(f"refusing unsafe source removal: {source_path}")
    prune_project_dir = project_dir.is_dir() and (
        not any(project_dir.iterdir())
        or (bool(existing_cache) and all(child in existing_cache for child in project_dir.iterdir()))
    )

    if apply:
        for candidate in existing_cache:
            shutil.rmtree(candidate)
        if prune_project_dir and project_dir.exists():
            project_dir.rmdir()
        if source_path and source_path.exists():
            shutil.rmtree(source_path)

    return {
        "schema_version": 1,
        "operation": "remove",
        "apply": apply,
        "project": project,
        "minecraft_version": minecraft,
        "loader": loader_name,
        "cache_root": str(root),
        "cache": {
            "removed" if apply else "planned": [str(path) for path in existing_cache],
            "absent": [str(path) for path in absent_cache],
            "pruned_project_dir": prune_project_dir,
        },
        "source": {
            "path": str(source_path) if source_path else None,
            "removed" if apply else "planned": bool(source_path and source_path.exists()),
            "absent": bool(source_path and not source_path.exists()),
        },
    }
