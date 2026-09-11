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
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUSES = {"pending-authentication", "approved", "diagnostic-only", "retired"}


@dataclass(frozen=True)
class CatalogArtifact:
    id: str
    game_domain: str
    mod_id: int
    mod_name: str
    mod_slug: str
    file_id: int
    file_display_name: str
    file_name: str
    file_version: str
    nms_version: str
    uploaded_at: str
    category: str
    sha256: str
    status: str
    reason: str
    distribution: str
    source_url: str
    compatibility_claim: str

    @property
    def pinned(self) -> bool:
        return bool(self.file_name and SHA256.fullmatch(self.sha256))

    @property
    def cache_relative_directory(self) -> Path:
        return Path(self.game_domain, str(self.mod_id), str(self.file_id))

    @property
    def reference_relative_directory(self) -> Path:
        return Path(
            self.nms_version,
            "mods",
            self.mod_slug,
            str(self.file_id),
        )


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a nonempty string"
        raise AcquisitionError(f"catalog {field} must be {qualifier}")
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise AcquisitionError(f"catalog {field} must be a positive integer")
    return value


def load_catalog(path: str | Path) -> dict[str, CatalogArtifact]:
    catalog_path = Path(path).expanduser().resolve()
    if not catalog_path.is_file() or catalog_path.is_symlink():
        raise AcquisitionError(f"catalog is not a regular file: {catalog_path}")
    try:
        raw = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AcquisitionError(f"cannot read catalog {catalog_path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise AcquisitionError("catalog schema_version must be 1")
    if not isinstance(raw.get("artifacts"), list):
        raise AcquisitionError("catalog must contain an artifacts array")

    artifacts: dict[str, CatalogArtifact] = {}
    for index, value in enumerate(raw["artifacts"]):
        if not isinstance(value, dict):
            raise AcquisitionError(f"catalog artifacts[{index}] must be a table")
        prefix = f"artifacts[{index}]"
        artifact = CatalogArtifact(
            id=_string(value.get("id"), f"{prefix}.id"),
            game_domain=_string(value.get("game_domain"), f"{prefix}.game_domain"),
            mod_id=_positive_int(value.get("mod_id"), f"{prefix}.mod_id"),
            mod_name=_string(value.get("mod_name"), f"{prefix}.mod_name"),
            mod_slug=_string(value.get("mod_slug"), f"{prefix}.mod_slug"),
            file_id=_positive_int(value.get("file_id"), f"{prefix}.file_id"),
            file_display_name=_string(
                value.get("file_display_name"), f"{prefix}.file_display_name"
            ),
            file_name=_string(
                value.get("file_name"), f"{prefix}.file_name", allow_empty=True
            ),
            file_version=_string(value.get("file_version"), f"{prefix}.file_version"),
            nms_version=_string(value.get("nms_version"), f"{prefix}.nms_version"),
            uploaded_at=_string(value.get("uploaded_at"), f"{prefix}.uploaded_at"),
            category=_string(value.get("category"), f"{prefix}.category"),
            sha256=_string(value.get("sha256"), f"{prefix}.sha256", allow_empty=True),
            status=_string(value.get("status"), f"{prefix}.status"),
            reason=_string(value.get("reason"), f"{prefix}.reason"),
            distribution=_string(value.get("distribution"), f"{prefix}.distribution"),
            source_url=_string(value.get("source_url"), f"{prefix}.source_url"),
            compatibility_claim=_string(
                value.get("compatibility_claim"), f"{prefix}.compatibility_claim"
            ),
        )
        if artifact.id in artifacts:
            raise AcquisitionError(f"duplicate catalog artifact ID: {artifact.id}")
        if artifact.game_domain != "nomanssky":
            raise AcquisitionError(
                f"catalog artifact {artifact.id} must use game domain nomanssky"
            )
        if not SLUG.fullmatch(artifact.mod_slug):
            raise AcquisitionError(
                f"catalog artifact {artifact.id} has an invalid mod_slug"
            )
        if artifact.status not in STATUSES:
            raise AcquisitionError(
                f"catalog artifact {artifact.id} has invalid status {artifact.status!r}"
            )
        if artifact.file_name and Path(artifact.file_name).name != artifact.file_name:
            raise AcquisitionError(
                f"catalog artifact {artifact.id} has an unsafe file_name"
            )
        if artifact.sha256 and not SHA256.fullmatch(artifact.sha256):
            raise AcquisitionError(
                f"catalog artifact {artifact.id} has an invalid SHA-256"
            )
        if artifact.status in {"approved", "diagnostic-only"} and not artifact.pinned:
            raise AcquisitionError(
                f"active catalog artifact {artifact.id} must pin file_name and SHA-256"
            )
        artifacts[artifact.id] = artifact
    return artifacts


def artifact_from_catalog(path: str | Path, artifact_id: str) -> CatalogArtifact:
    artifacts = load_catalog(path)
    try:
        return artifacts[artifact_id]
    except KeyError as exc:
        raise AcquisitionError(
            f"catalog artifact does not exist: {artifact_id}"
        ) from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_catalog(path: str | Path, *, cache_root: Path) -> dict[str, Any]:
    artifacts = load_catalog(path)
    results: list[dict[str, Any]] = []
    for artifact in artifacts.values():
        record: dict[str, Any] = {
            "id": artifact.id,
            "status": artifact.status,
            "pinned": artifact.pinned,
        }
        if artifact.status in {"retired", "pending-authentication"}:
            results.append(record)
            continue
        directory = cache_root / artifact.cache_relative_directory
        archive = directory / artifact.file_name
        manifest_path = directory / "acquisition.json"
        if not archive.is_file() or archive.is_symlink():
            raise AcquisitionError(
                f"catalog artifact is not acquired: {artifact.id}: {archive}"
            )
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise AcquisitionError(
                f"acquisition manifest is missing for {artifact.id}: {manifest_path}"
            )
        actual = sha256_file(archive)
        if actual != artifact.sha256:
            raise AcquisitionError(f"catalog hash mismatch for {artifact.id}: {actual}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AcquisitionError(
                f"invalid acquisition manifest for {artifact.id}: {exc}"
            ) from exc
        expected = {
            "artifact_id": artifact.id,
            "game_domain": artifact.game_domain,
            "mod_id": artifact.mod_id,
            "file_id": artifact.file_id,
            "file_name": artifact.file_name,
            "sha256": artifact.sha256,
        }
        mismatches = [
            key for key, value in expected.items() if manifest.get(key) != value
        ]
        if mismatches:
            raise AcquisitionError(
                f"manifest mismatch for {artifact.id}: {', '.join(mismatches)}"
            )
        record.update({"path": str(archive), "sha256": actual})
        results.append(record)
    return {"catalog": str(Path(path).expanduser().resolve()), "artifacts": results}
