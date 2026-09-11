from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .catalog import CatalogArtifact, sha256_file
from .errors import AcquisitionError

API_ROOT = "https://api.nexusmods.com/v1"
APPLICATION_NAME = "squinchmods"
APPLICATION_VERSION = "0.1.0"
USER_AGENT = f"{APPLICATION_NAME}-nms-third-party/{APPLICATION_VERSION}"


def cache_root() -> Path:
    cache_home = os.environ.get("SQINCHMODS_CACHE_HOME")
    if cache_home:
        return Path(cache_home) / "third-party" / "nexus-mods"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (
        (Path(xdg) if xdg else Path.home() / ".cache")
        / "squinchmods"
        / "third-party"
        / "nexus-mods"
    )


def _api_key() -> str:
    value = os.environ.get("NEXUSMODS_API_KEY", "")
    if not value:
        raise AcquisitionError(
            "NEXUSMODS_API_KEY is not set; create a personal key on the Nexus Mods API Access page "
            "and provide it through the environment, never the catalog or command line"
        )
    return value


def _headers(*, authenticated: bool = True) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Application-Name": APPLICATION_NAME,
        "Application-Version": APPLICATION_VERSION,
        "User-Agent": USER_AGENT,
    }
    if authenticated:
        headers["apikey"] = _api_key()
    return headers


def _public_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            message = (
                "Nexus Mods denied this request. Unattended download links require Premium; free "
                "accounts must also supply NEXUSMODS_DOWNLOAD_KEY and NEXUSMODS_DOWNLOAD_EXPIRES "
                "from a user-initiated nxm:// download."
            )
        else:
            message = f"Nexus Mods API returned HTTP {exc.code}"
        raise AcquisitionError(f"{message}: {_public_url(url)}") from exc
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(
            f"Nexus Mods request failed: {_public_url(url)}: {exc}"
        ) from exc


def mod_metadata(artifact: CatalogArtifact) -> dict[str, Any]:
    url = f"{API_ROOT}/games/{artifact.game_domain}/mods/{artifact.mod_id}.json"
    result = _get_json(url)
    if not isinstance(result, dict):
        raise AcquisitionError("Nexus Mods mod response was not an object")
    return result


def files_metadata(artifact: CatalogArtifact) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/games/{artifact.game_domain}/mods/{artifact.mod_id}/files.json"
    result = _get_json(url)
    values = result.get("files") if isinstance(result, dict) else None
    if not isinstance(values, list):
        raise AcquisitionError(
            "Nexus Mods files response did not contain a files array"
        )
    return [value for value in values if isinstance(value, dict)]


def selected_metadata(artifact: CatalogArtifact) -> dict[str, Any]:
    matches = [
        value
        for value in files_metadata(artifact)
        if value.get("file_id") == artifact.file_id
    ]
    if not matches:
        raise AcquisitionError(
            f"Nexus Mods file {artifact.file_id} is not visible on mod {artifact.mod_id}"
        )
    return matches[0]


def artifact_metadata(artifact: CatalogArtifact) -> dict[str, Any]:
    return {"mod": mod_metadata(artifact), "file": selected_metadata(artifact)}


def artifact_freshness(artifact: CatalogArtifact) -> dict[str, Any]:
    """Compare the catalog pin with the newest visible MAIN-channel Nexus file."""
    files = files_metadata(artifact)
    selected = next(
        (value for value in files if value.get("file_id") == artifact.file_id),
        None,
    )
    if selected is None:
        raise AcquisitionError(
            f"Nexus Mods file {artifact.file_id} is not visible on mod {artifact.mod_id}"
        )
    eligible = [
        value
        for value in files
        if str(value.get("category_name", "")).casefold() == "main"
        and not value.get("is_deleted", False)
    ]
    if not eligible:
        raise AcquisitionError(
            f"Nexus Mods exposes no MAIN-channel files for mod {artifact.mod_id}"
        )

    def order(value: dict[str, Any]) -> tuple[int, int]:
        uploaded = value.get("uploaded_timestamp")
        return (
            uploaded if isinstance(uploaded, int) else 0,
            value.get("file_id") if isinstance(value.get("file_id"), int) else 0,
        )

    latest = max(eligible, key=order)
    return {
        "artifact_id": artifact.id,
        "release_channel_policy": "newest visible non-deleted MAIN file",
        "catalog_file_id": artifact.file_id,
        "catalog_file_version": artifact.file_version,
        "catalog_nms_version": artifact.nms_version,
        "selected": selected,
        "latest_eligible": latest,
        "fresh": latest.get("file_id") == artifact.file_id,
        "eligible_file_count": len(eligible),
    }


def _download_links(artifact: CatalogArtifact) -> list[dict[str, Any]]:
    parameters: dict[str, str] = {}
    download_key = os.environ.get("NEXUSMODS_DOWNLOAD_KEY", "")
    download_expires = os.environ.get("NEXUSMODS_DOWNLOAD_EXPIRES", "")
    if bool(download_key) != bool(download_expires):
        raise AcquisitionError(
            "NEXUSMODS_DOWNLOAD_KEY and NEXUSMODS_DOWNLOAD_EXPIRES must be set together"
        )
    if download_key:
        parameters.update({"key": download_key, "expires": download_expires})
    query = f"?{urllib.parse.urlencode(parameters)}" if parameters else ""
    url = (
        f"{API_ROOT}/games/{artifact.game_domain}/mods/{artifact.mod_id}/files/"
        f"{artifact.file_id}/download_link.json{query}"
    )
    result = _get_json(url)
    if not isinstance(result, list) or not result:
        raise AcquisitionError("Nexus Mods download-link response was empty")
    return [value for value in result if isinstance(value, dict) and value.get("URI")]


def _safe_filename(value: Any) -> str:
    filename = str(value or "")
    if not filename or Path(filename).name != filename:
        raise AcquisitionError(f"Nexus Mods returned an unsafe file name: {filename!r}")
    return filename


def _write_manifest(
    artifact: CatalogArtifact,
    destination: Path,
    *,
    acquisition_method: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    actual = sha256_file(destination)
    if artifact.file_name and destination.name != artifact.file_name:
        raise AcquisitionError(
            f"catalog filename mismatch: expected {artifact.file_name}, got {destination.name}"
        )
    if artifact.sha256 and actual != artifact.sha256:
        raise AcquisitionError(
            f"catalog SHA-256 mismatch: expected {artifact.sha256}, got {actual}"
        )
    manifest = {
        "schema_version": 1,
        "acquired_at": datetime.now(UTC).isoformat(),
        "acquisition_method": acquisition_method,
        "artifact_id": artifact.id,
        "game_domain": artifact.game_domain,
        "mod_id": artifact.mod_id,
        "file_id": artifact.file_id,
        "file_name": destination.name,
        "sha256": actual,
        "source_url": artifact.source_url,
        "distribution": artifact.distribution,
        "nexus_metadata": metadata,
    }
    (destination.parent / "acquisition.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def acquire(
    artifact: CatalogArtifact, *, destination_root: Path | None = None
) -> dict[str, Any]:
    metadata = artifact_metadata(artifact)
    filename = _safe_filename(metadata["file"].get("file_name"))
    directory = (destination_root or cache_root()) / artifact.cache_relative_directory
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    temporary = directory / f".{filename}.part"
    links = _download_links(artifact)
    request = urllib.request.Request(
        str(links[0]["URI"]), headers=_headers(authenticated=False)
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=300) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
        manifest = _write_manifest(
            artifact, destination, acquisition_method="nexus-api", metadata=metadata
        )
    except AcquisitionError:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise AcquisitionError(f"Nexus Mods archive download failed: {exc}") from exc
    return {
        "path": str(destination),
        "sha256": manifest["sha256"],
        "catalog_pin_required": not artifact.pinned,
        "manifest": str(directory / "acquisition.json"),
    }


def import_archive(
    artifact: CatalogArtifact,
    source: Path,
    *,
    destination_root: Path | None = None,
) -> dict[str, Any]:
    resolved = source.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise AcquisitionError(f"manual archive is not a regular file: {resolved}")
    directory = (destination_root or cache_root()) / artifact.cache_relative_directory
    directory.mkdir(parents=True, exist_ok=True)
    filename = artifact.file_name or resolved.name
    if Path(filename).name != filename:
        raise AcquisitionError(f"unsafe archive filename: {filename!r}")
    destination = directory / filename
    copied = False
    if destination.exists() and destination.resolve() != resolved:
        if destination.is_symlink() or not destination.is_file():
            raise AcquisitionError(
                f"cache destination is not a regular file: {destination}"
            )
        if sha256_file(destination) != sha256_file(resolved):
            raise AcquisitionError(
                f"cache destination contains different bytes: {destination}"
            )
    elif destination.resolve() != resolved:
        shutil.copy2(resolved, destination)
        copied = True
    try:
        manifest = _write_manifest(
            artifact,
            destination,
            acquisition_method="manual-browser-import",
            metadata=None,
        )
    except AcquisitionError:
        if copied:
            destination.unlink(missing_ok=True)
        raise
    return {
        "path": str(destination),
        "sha256": manifest["sha256"],
        "catalog_pin_required": not artifact.pinned,
        "manifest": str(directory / "acquisition.json"),
    }
