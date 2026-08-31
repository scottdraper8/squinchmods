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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import AcquisitionError
from .catalog import CatalogArtifact, load_catalog

API_ROOT = "https://api.modrinth.com/v2"
USER_AGENT = "squinchmods-third-party/0.1"


@dataclass(frozen=True)
class AcquiredRelease:
    project: str
    project_id: str
    version_id: str
    version_number: str
    minecraft_version: str
    requested_loader: str
    effective_loader: str
    path: Path
    sha256: str
    dependencies: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]


def cache_root() -> Path:
    cache_home = os.environ.get("SQINCHMODS_CACHE_HOME")
    if cache_home:
        return Path(cache_home) / "third-party" / "modrinth"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else Path.home() / ".cache") / "squinchmods" / "third-party" / "modrinth"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _get(path: str) -> Any:
    url = f"{API_ROOT}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"Modrinth request failed: {url}: {exc}") from exc


def project(slug_or_id: str) -> dict[str, Any]:
    value = urllib.parse.quote(slug_or_id, safe="")
    result = _get(f"/project/{value}")
    if not isinstance(result, dict):
        raise AcquisitionError(f"Modrinth project response was not an object: {slug_or_id}")
    return result


def _versions(
    project_id: str,
    minecraft_version: str,
    loader: str,
    *,
    include_beta: bool,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "game_versions": json.dumps([minecraft_version]),
            "loaders": json.dumps([loader]),
        }
    )
    values = _get(f"/project/{urllib.parse.quote(project_id, safe='')}/version?{query}")
    if not isinstance(values, list):
        raise AcquisitionError("Modrinth version response was not an array")
    if include_beta:
        return values
    return [value for value in values if value.get("version_type") == "release"]


def audit_latest_catalog(
    artifacts: list[CatalogArtifact], *, include_beta: bool = False
) -> dict[str, Any]:
    """Compare pinned artifacts with Modrinth's current first compatible version."""
    groups: dict[tuple[str, str, str], list[CatalogArtifact]] = {}
    for artifact in artifacts:
        key = (artifact.project_id, artifact.minecraft_version, artifact.loader)
        groups.setdefault(key, []).append(artifact)

    results: list[dict[str, Any]] = []
    for (project_id, minecraft_version, loader), pinned in sorted(groups.items()):
        versions = _versions(
            project_id,
            minecraft_version,
            loader,
            include_beta=include_beta,
        )
        if not versions:
            raise AcquisitionError(
                f"No compatible Modrinth versions for {pinned[0].project_slug} "
                f"on {minecraft_version}/{loader}"
            )
        latest = versions[0]
        latest_id = str(latest.get("id", ""))
        latest_number = str(latest.get("version_number", ""))
        if not latest_id or not latest_number:
            raise AcquisitionError(
                f"Latest Modrinth version metadata is incomplete for {pinned[0].project_slug}"
            )
        results.append({
            "project": pinned[0].project_slug,
            "project_id": project_id,
            "minecraft_version": minecraft_version,
            "loader": loader,
            "channel_policy": "release-or-prerelease" if include_beta else "release",
            "latest": {
                "version_id": latest_id,
                "version_number": latest_number,
                "version_type": latest.get("version_type"),
                "published_at": latest.get("date_published"),
            },
            "pins": [
                {
                    "artifact_id": artifact.id,
                    "version_id": artifact.version_id,
                    "version_number": artifact.version_number,
                    "is_latest": artifact.version_id == latest_id,
                }
                for artifact in sorted(pinned, key=lambda value: value.id)
            ],
        })
    return {
        "channel_policy": "release-or-prerelease" if include_beta else "release",
        "groups": results,
    }


def _select_version(
    versions: list[dict[str, Any]],
    *,
    version_id: str | None,
    version_number: str | None,
    project_name: str,
) -> dict[str, Any]:
    if version_id:
        matches = [value for value in versions if value.get("id") == version_id]
    elif version_number:
        matches = [value for value in versions if value.get("version_number") == version_number]
    else:
        matches = versions
    if not matches:
        requested = version_id or version_number or "latest release"
        raise AcquisitionError(f"No matching {requested} for {project_name}")
    return matches[0]


def _candidate_versions(
    versions: list[dict[str, Any]],
    *,
    version_id: str | None,
    version_number: str | None,
    project_name: str,
) -> list[dict[str, Any]]:
    if version_id or version_number:
        return [_select_version(
            versions,
            version_id=version_id,
            version_number=version_number,
            project_name=project_name,
        )]
    if not versions:
        raise AcquisitionError(f"No matching latest release for {project_name}")
    return versions


def _jar_files(version: dict[str, Any]) -> list[dict[str, Any]]:
    files = [value for value in version.get("files", []) if str(value.get("filename", "")).endswith(".jar")]
    primary = [value for value in files if value.get("primary")]
    result = primary + [value for value in files if value not in primary]
    if not result:
        raise AcquisitionError(f"Modrinth version {version.get('id')} has no JAR file")
    return result


def _supports_loader(path: Path, loader: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False
    if loader in {"fabric", "quilt"}:
        return "fabric.mod.json" in names or "quilt.mod.json" in names
    if loader == "forge":
        return "META-INF/mods.toml" in names
    if loader == "neoforge":
        return "META-INF/neoforge.mods.toml" in names or "META-INF/mods.toml" in names
    return True


def _download(url: str, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise AcquisitionError(f"Download failed: {url}: {exc}") from exc


def acquire_release(
    project_name: str,
    minecraft_version: str,
    loader: str,
    *,
    version_id: str | None = None,
    version_number: str | None = None,
    pinned_sha256: str | None = None,
    include_beta: bool = False,
    destination_root: Path | None = None,
) -> AcquiredRelease:
    project_info = project(project_name)
    project_id = str(project_info["id"])
    versions = _versions(
        project_id,
        minecraft_version,
        loader,
        include_beta=include_beta,
    )
    candidate_versions = _candidate_versions(
        versions,
        version_id=version_id,
        version_number=version_number,
        project_name=str(project_info.get("title", project_name)),
    )
    root = destination_root or cache_root()
    errors: list[str] = []
    for version in candidate_versions:
        try:
            file_entries = _jar_files(version)
        except AcquisitionError as exc:
            errors.append(f"{version.get('version_number')}: {exc}")
            continue
        version_dir = root / minecraft_version / loader / str(project_info["slug"]) / str(version["version_number"])
        version_dir.mkdir(parents=True, exist_ok=True)
        for file_entry in file_entries:
            path = version_dir / str(file_entry["filename"])
            try:
                expected = str(file_entry.get("hashes", {}).get("sha256", ""))
                if not path.is_file():
                    _download(str(file_entry["url"]), path)
                actual = sha256_file(path)
                if expected and actual != expected:
                    path.unlink(missing_ok=True)
                    raise AcquisitionError(f"Modrinth hash mismatch: expected {expected}, got {actual}")
                if not _supports_loader(path, loader):
                    raise AcquisitionError(f"JAR metadata does not support loader {loader}")
                if pinned_sha256 and actual != pinned_sha256:
                    raise AcquisitionError(f"Pinned SHA-256 mismatch: expected {pinned_sha256}, got {actual}")
                dependencies = tuple(
                    dependency
                    for dependency in version.get("dependencies", [])
                    if dependency.get("dependency_type") == "required"
                )
                metadata = {
                    "acquired_at": datetime.now(UTC).isoformat(),
                    "project": project_info,
                    "version": version,
                    "selected_file": file_entry,
                    "requested": {"minecraft_version": minecraft_version, "loader": loader},
                    "sha256": actual,
                }
                (version_dir / "acquisition.json").write_text(
                    json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                return AcquiredRelease(
                    project=str(project_info["slug"]),
                    project_id=project_id,
                    version_id=str(version["id"]),
                    version_number=str(version["version_number"]),
                    minecraft_version=minecraft_version,
                    requested_loader=loader,
                    effective_loader=loader,
                    path=path,
                    sha256=actual,
                    dependencies=dependencies,
                    metadata=metadata,
                )
            except AcquisitionError as exc:
                errors.append(f"{version.get('version_number')}/{file_entry.get('filename')}: {exc}")
    raise AcquisitionError("No usable JAR found: " + "; ".join(errors))


def acquire_catalog_artifact(
    artifact_id: str,
    catalog_path: Path,
    *,
    destination_root: Path | None = None,
    include_beta: bool = False,
) -> AcquiredRelease:
    artifacts, _sources = load_catalog(catalog_path)
    try:
        artifact = artifacts[artifact_id]
    except KeyError as exc:
        raise AcquisitionError(f"catalog artifact does not exist: {artifact_id}") from exc
    if artifact.status in {"excluded", "retired"}:
        raise AcquisitionError(f"catalog artifact is not active: {artifact_id} ({artifact.status})")
    release = acquire_release(
        artifact.project_slug,
        artifact.minecraft_version,
        artifact.loader,
        version_id=artifact.version_id,
        version_number=artifact.version_number,
        pinned_sha256=artifact.sha256,
        include_beta=include_beta,
        destination_root=destination_root,
    )
    if release.project_id != artifact.project_id or release.version_id != artifact.version_id:
        raise AcquisitionError(f"acquired release metadata does not match catalog artifact: {artifact_id}")
    if release.path.name != artifact.filename:
        raise AcquisitionError(f"acquired filename does not match catalog artifact: {artifact_id}")
    return release
