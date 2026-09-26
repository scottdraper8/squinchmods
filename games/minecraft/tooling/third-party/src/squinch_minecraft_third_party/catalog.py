from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import AcquisitionError

SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATUSES = {"approved", "diagnostic-only", "excluded", "retired"}
SOURCE_STATUSES = {"available", "unavailable", "excluded"}


@dataclass(frozen=True)
class CatalogArtifact:
    id: str
    project_slug: str
    project_id: str
    minecraft_version: str
    loader: str
    version_number: str
    version_id: str
    filename: str
    sha256: str
    status: str
    reason: str
    required_dependencies: tuple[str, ...]
    source_id: str | None

    @property
    def cache_relative_path(self) -> Path:
        return Path(self.minecraft_version, self.loader, self.project_slug, self.version_number, self.filename)


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise AcquisitionError(f"catalog {field} must be a nonempty string")
    return value


def _load_raw(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise AcquisitionError(f"catalog is not a regular file: {path}")
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AcquisitionError(f"cannot read catalog {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AcquisitionError("catalog schema_version must be 1")
    if not isinstance(value.get("artifacts"), list) or not isinstance(value.get("sources"), list):
        raise AcquisitionError("catalog must contain artifacts and sources arrays")
    return value


def load_catalog(path: str | Path) -> tuple[dict[str, CatalogArtifact], dict[str, dict[str, Any]]]:
    catalog_path = Path(path).expanduser().resolve()
    raw = _load_raw(catalog_path)
    artifacts: dict[str, CatalogArtifact] = {}
    for index, value in enumerate(raw["artifacts"]):
        if not isinstance(value, dict):
            raise AcquisitionError(f"catalog artifacts[{index}] must be a table")
        artifact = CatalogArtifact(
            id=_string(value.get("id"), f"artifacts[{index}].id"),
            project_slug=_string(value.get("project_slug"), f"artifacts[{index}].project_slug"),
            project_id=_string(value.get("project_id"), f"artifacts[{index}].project_id"),
            minecraft_version=_string(value.get("minecraft_version"), f"artifacts[{index}].minecraft_version"),
            loader=_string(value.get("loader"), f"artifacts[{index}].loader"),
            version_number=_string(value.get("version_number"), f"artifacts[{index}].version_number"),
            version_id=_string(value.get("version_id"), f"artifacts[{index}].version_id"),
            filename=_string(value.get("filename"), f"artifacts[{index}].filename"),
            sha256=_string(value.get("sha256"), f"artifacts[{index}].sha256"),
            status=_string(value.get("status"), f"artifacts[{index}].status"),
            reason=_string(value.get("reason"), f"artifacts[{index}].reason"),
            required_dependencies=tuple(value.get("required_dependencies", []))
            if isinstance(value.get("required_dependencies", []), list)
            else (),
            source_id=value.get("source_id"),
        )
        if artifact.id in artifacts:
            raise AcquisitionError(f"duplicate catalog artifact ID: {artifact.id}")
        if not SHA256.fullmatch(artifact.sha256):
            raise AcquisitionError(f"catalog artifact {artifact.id} has an invalid SHA-256")
        if artifact.status not in STATUSES:
            raise AcquisitionError(f"catalog artifact {artifact.id} has invalid status {artifact.status!r}")
        if Path(artifact.filename).name != artifact.filename or not artifact.filename.endswith(".jar"):
            raise AcquisitionError(f"catalog artifact {artifact.id} has an invalid filename")
        if not isinstance(value.get("required_dependencies", []), list):
            raise AcquisitionError(f"catalog artifact {artifact.id} dependencies must be an array")
        if any(not isinstance(item, str) or not item for item in artifact.required_dependencies):
            raise AcquisitionError(f"catalog artifact {artifact.id} has invalid dependencies")
        if not isinstance(artifact.source_id, str) or not artifact.source_id:
            raise AcquisitionError(f"catalog artifact {artifact.id} has an invalid source_id")
        artifacts[artifact.id] = artifact

    sources: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(raw["sources"]):
        if not isinstance(value, dict):
            raise AcquisitionError(f"catalog sources[{index}] must be a table")
        source_id = _string(value.get("id"), f"sources[{index}].id")
        if source_id in sources:
            raise AcquisitionError(f"duplicate catalog source ID: {source_id}")
        status = _string(value.get("status"), f"sources[{index}].status")
        if status not in SOURCE_STATUSES:
            raise AcquisitionError(f"catalog source {source_id} has invalid status {status!r}")
        for field in ("repository", "requested_ref", "resolved_commit", "minecraft_version", "checkout", "shallow", "blob_filter", "sparse_paths"):
            if field not in value:
                raise AcquisitionError(f"catalog source {source_id} is missing {field}")
        if status in {"available", "excluded"}:
            if not all(isinstance(value.get(field), str) and value[field] for field in ("repository", "requested_ref", "resolved_commit", "minecraft_version", "checkout")):
                raise AcquisitionError(f"catalog source {source_id} has incomplete acquisition metadata")
            if not re.fullmatch(r"[0-9a-f]{40}", value["resolved_commit"]):
                raise AcquisitionError(f"catalog source {source_id} has an invalid resolved commit")
            if value.get("shallow") is not True or value.get("blob_filter") is not True:
                raise AcquisitionError(f"catalog source {source_id} must declare shallow blob-filtered acquisition")
            checkout = Path(value["checkout"])
            if checkout.is_absolute() or ".." in checkout.parts:
                raise AcquisitionError(f"catalog source {source_id} has an unsafe checkout path")
        if not isinstance(value.get("sparse_paths"), list) or any(not isinstance(item, str) or not item for item in value["sparse_paths"]):
            raise AcquisitionError(f"catalog source {source_id} has invalid sparse paths")
        if not isinstance(value.get("shallow"), bool) or not isinstance(value.get("blob_filter"), bool):
            raise AcquisitionError(f"catalog source {source_id} has invalid acquisition flags")
        sources[source_id] = value

    for artifact in artifacts.values():
        if any(dependency not in artifacts for dependency in artifact.required_dependencies):
            missing = sorted(set(artifact.required_dependencies) - artifacts.keys())
            raise AcquisitionError(f"catalog artifact {artifact.id} references missing dependencies: {missing}")
        if artifact.source_id not in sources:
            raise AcquisitionError(f"catalog artifact {artifact.id} references missing source {artifact.source_id!r}")
    return artifacts, sources


def validate_catalog(
    path: str | Path,
    *,
    cache_root: Path,
    check_files: bool = True,
) -> dict[str, Any]:
    artifacts, sources = load_catalog(path)
    checked: list[dict[str, str]] = []
    for artifact in artifacts.values():
        if artifact.status in {"excluded", "retired"}:
            continue
        target = cache_root / artifact.cache_relative_path
        manifest_path = target.parent / "acquisition.json"
        if check_files:
            if not target.is_file() or target.is_symlink():
                raise AcquisitionError(f"catalog artifact is not acquired: {artifact.id}: {target}")
            if not manifest_path.is_file() or manifest_path.is_symlink():
                raise AcquisitionError(f"acquisition manifest is missing for {artifact.id}: {manifest_path}")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != artifact.sha256:
                raise AcquisitionError(f"catalog hash mismatch for {artifact.id}: {actual}")
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise AcquisitionError(f"invalid acquisition manifest for {artifact.id}: {exc}") from exc
            checks = {
                "project.slug": manifest.get("project", {}).get("slug"),
                "project.id": manifest.get("project", {}).get("id"),
                "version.id": manifest.get("version", {}).get("id"),
                "version.version_number": manifest.get("version", {}).get("version_number"),
                "requested.minecraft_version": manifest.get("requested", {}).get("minecraft_version"),
                "requested.loader": manifest.get("requested", {}).get("loader"),
                "selected_file.filename": manifest.get("selected_file", {}).get("filename"),
                "sha256": manifest.get("sha256"),
            }
            expected = {
                "project.slug": artifact.project_slug,
                "project.id": artifact.project_id,
                "version.id": artifact.version_id,
                "version.version_number": artifact.version_number,
                "requested.minecraft_version": artifact.minecraft_version,
                "requested.loader": artifact.loader,
                "selected_file.filename": artifact.filename,
                "sha256": artifact.sha256,
            }
            mismatches = [key for key, value in checks.items() if value != expected[key]]
            if mismatches:
                raise AcquisitionError(f"manifest mismatch for {artifact.id}: {', '.join(mismatches)}")
        checked.append({"id": artifact.id, "status": artifact.status, "path": str(target), "sha256": artifact.sha256})
    return {"catalog": str(Path(path).expanduser().resolve()), "artifacts": checked, "sources": len(sources)}
