from __future__ import annotations

import hashlib
import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import InvestigationError
from .paths import REPOSITORY_ROOT

CATALOG_PATH = REPOSITORY_ROOT / ".squinch" / "games" / "minecraft" / "third-party" / "artifacts.toml"


@dataclass(frozen=True)
class ResolvedArtifact:
    id: str
    project_slug: str
    minecraft_version: str
    loader: str
    filename: str
    sha256: str
    path: Path


def cache_root() -> Path:
    cache_home = os.environ.get("SQINCHMODS_CACHE_HOME")
    if cache_home:
        return Path(cache_home).expanduser().resolve() / "third-party" / "modrinth"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg).expanduser() if xdg else Path.home() / ".cache") / "squinchmods" / "third-party" / "modrinth"


def _error(message: str) -> InvestigationError:
    return InvestigationError("invalid_catalog", message)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog() -> dict[str, dict[str, Any]]:
    try:
        raw = tomllib.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise _error(f"cannot read artifact catalog {CATALOG_PATH}: {exc}") from exc
    if raw.get("schema_version") != 1 or not isinstance(raw.get("artifacts"), list):
        raise _error("artifact catalog schema is invalid")
    artifacts: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(raw["artifacts"]):
        if not isinstance(value, dict):
            raise _error(f"artifacts[{index}] must be a table")
        artifact_id = value.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise _error(f"artifacts[{index}].id must be a nonempty string")
        if artifact_id in artifacts:
            raise _error(f"duplicate artifact ID: {artifact_id}")
        status = value.get("status")
        if status not in {"approved", "diagnostic-only", "excluded", "retired"}:
            raise _error(f"artifact {artifact_id} has invalid status")
        for field in ("project_slug", "project_id", "minecraft_version", "loader", "version_number", "version_id", "filename", "sha256"):
            if not isinstance(value.get(field), str) or not value[field]:
                raise _error(f"artifact {artifact_id} is missing {field}")
        if len(value["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in value["sha256"]):
            raise _error(f"artifact {artifact_id} has an invalid SHA-256")
        if Path(value["filename"]).name != value["filename"] or not value["filename"].endswith(".jar"):
            raise _error(f"artifact {artifact_id} has an invalid filename")
        dependencies = value.get("required_dependencies", [])
        if (
            not isinstance(dependencies, list)
            or any(not isinstance(item, str) or not item for item in dependencies)
            or len(dependencies) != len(set(dependencies))
            or artifact_id in dependencies
        ):
            raise _error(f"artifact {artifact_id} has invalid required_dependencies")
        artifacts[artifact_id] = value
    return artifacts


def resolve_artifacts(ids: tuple[str, ...], *, expected_loader: str, expected_minecraft: str = "1.21.1") -> tuple[ResolvedArtifact, ...]:
    artifacts = _catalog()
    root = cache_root()
    resolved: list[ResolvedArtifact] = []
    for artifact_id in ids:
        value = artifacts.get(artifact_id)
        if value is None:
            raise _error(f"scenario references unknown artifact ID: {artifact_id}")
        if value["status"] not in {"approved", "diagnostic-only"}:
            raise _error(f"scenario references inactive artifact {artifact_id}: {value['status']}")
        if value["loader"] != expected_loader or value["minecraft_version"] != expected_minecraft:
            raise _error(f"artifact {artifact_id} does not match scenario loader/version")
        relative = Path(value["minecraft_version"], value["loader"], value["project_slug"], value["version_number"], value["filename"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
            raise _error(f"catalog artifact is not acquired: {artifact_id}: {path}")
        if _hash(path) != value["sha256"]:
            raise _error(f"catalog artifact hash mismatch: {artifact_id}")
        manifest_path = path.parent / "acquisition.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise _error(f"catalog acquisition manifest is missing: {artifact_id}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _error(f"catalog acquisition manifest is invalid for {artifact_id}: {exc}") from exc
        checks = (
            (manifest.get("project", {}).get("slug"), value["project_slug"]),
            (manifest.get("project", {}).get("id"), value["project_id"]),
            (manifest.get("version", {}).get("id"), value["version_id"]),
            (manifest.get("version", {}).get("version_number"), value["version_number"]),
            (manifest.get("requested", {}).get("minecraft_version"), expected_minecraft),
            (manifest.get("requested", {}).get("loader"), expected_loader),
            (manifest.get("selected_file", {}).get("filename"), value["filename"]),
            (manifest.get("sha256"), value["sha256"]),
        )
        if any(actual != expected for actual, expected in checks):
            raise _error(f"catalog acquisition manifest does not match artifact {artifact_id}")
        resolved.append(ResolvedArtifact(
            artifact_id, value["project_slug"], expected_minecraft, expected_loader,
            value["filename"], value["sha256"], path,
        ))
    return tuple(resolved)


def resolve_artifact_closure(
    ids: tuple[str, ...], *, expected_loader: str, expected_minecraft: str = "1.21.1"
) -> tuple[ResolvedArtifact, ...]:
    artifacts = _catalog()
    ordered: list[str] = []
    visited: set[str] = set()
    visiting: list[str] = []

    def visit(artifact_id: str) -> None:
        if artifact_id in visited:
            return
        if artifact_id in visiting:
            cycle = " -> ".join((*visiting[visiting.index(artifact_id):], artifact_id))
            raise _error(f"artifact dependency cycle: {cycle}")
        value = artifacts.get(artifact_id)
        if value is None:
            owner = visiting[-1] if visiting else "scenario"
            raise _error(f"{owner} references unknown required dependency: {artifact_id}")
        if value["status"] not in {"approved", "diagnostic-only"}:
            raise _error(f"artifact dependency is inactive {artifact_id}: {value['status']}")
        if value["loader"] != expected_loader or value["minecraft_version"] != expected_minecraft:
            raise _error(f"artifact dependency {artifact_id} does not match scenario loader/version")
        visiting.append(artifact_id)
        for dependency in value.get("required_dependencies", []):
            visit(dependency)
        visiting.pop()
        visited.add(artifact_id)
        ordered.append(artifact_id)

    for artifact_id in ids:
        visit(artifact_id)

    resolved = resolve_artifacts(
        tuple(ordered), expected_loader=expected_loader, expected_minecraft=expected_minecraft
    )
    projects: dict[str, ResolvedArtifact] = {}
    filenames: dict[str, ResolvedArtifact] = {}
    for artifact in resolved:
        project = projects.setdefault(artifact.project_slug, artifact)
        if project.sha256 != artifact.sha256:
            raise _error(
                f"runtime closure selects conflicting versions of {artifact.project_slug}: "
                f"{project.id} and {artifact.id}"
            )
        filename = filenames.setdefault(artifact.filename, artifact)
        if filename.sha256 != artifact.sha256:
            raise _error(
                f"runtime closure selects conflicting files named {artifact.filename}: "
                f"{filename.id} and {artifact.id}"
            )
    return resolved
