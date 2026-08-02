from __future__ import annotations

import hashlib
import json
import os
import tomllib
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .errors import InvestigationError

RTF_PRESET_PATH = "data/reterraforged/reterraforged/worldgen/preset/preset.json"
CLASSIFICATIONS = {"reusable-control", "reusable-stress", "feature-specific"}


def _fixture_error(message: str) -> InvestigationError:
    return InvestigationError("invalid_fixture", message)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _fixture_root(metadata_path: Path) -> Path:
    for candidate in (metadata_path.parent, *metadata_path.parents):
        if candidate.name == "fixtures":
            return candidate.resolve()
    raise _fixture_error(f"fixture metadata is not beneath a fixtures directory: {metadata_path}")


def _source_path(metadata_path: Path, value: Any, field: str, root: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise _fixture_error(f"{field} must be a nonempty relative path")
    unresolved = Path(value)
    if unresolved.is_absolute():
        raise _fixture_error(f"{field} must be relative to fixture.toml")
    path = (metadata_path.parent / unresolved).resolve()
    if not path.is_relative_to(root) or path == root:
        raise _fixture_error(f"{field} escapes the declared fixture root: {value}")
    if path.is_symlink() or not path.is_dir():
        raise _fixture_error(f"{field} is not a regular source directory: {path}")
    return path


def _read_source(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise _fixture_error(f"source-form fixture contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise _fixture_error(f"source-form fixture contains a non-file: {path}")
        relative = path.relative_to(root).as_posix()
        result[relative] = path.read_bytes()
    return result


def _content_sha256(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, content in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def _write_archive(files: dict[str, bytes], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_symlink() or (output_path.exists() and not output_path.is_file()):
        raise _fixture_error(f"output must be a regular file path: {output_path}")
    temporary = output_path.parent / f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for relative, content in sorted(files.items()):
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


def _merge_patch(target: Any, patch: Any) -> Any:
    """Apply RFC 7396 JSON Merge Patch without mutating either input."""
    if not isinstance(patch, dict):
        return json.loads(json.dumps(patch))
    result = json.loads(json.dumps(target)) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = _merge_patch(result.get(key), value)
    return result


def load_fixture(metadata: str | Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    metadata_path = Path(metadata).expanduser().resolve()
    if metadata_path.name != "fixture.toml" or not metadata_path.is_file():
        raise _fixture_error(f"fixture metadata does not exist: {metadata_path}")
    try:
        value = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _fixture_error(f"invalid TOML in {metadata_path}: {exc}") from exc
    required = {
        "schema_version",
        "id",
        "classification",
        "purpose",
        "applicable_questions",
        "known_limitations",
        "minecraft_version",
        "rtf_version",
        "base",
        "resolved_preset_sha256",
        "historical_archive_sha256",
    }
    allowed = required | {"overlay"}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing or unknown:
        raise _fixture_error(
            f"fixture metadata keys invalid; missing={missing}, unknown={unknown}"
        )
    if value["schema_version"] != 1:
        raise _fixture_error("fixture schema_version must be 1")
    for field in ("id", "purpose", "minecraft_version", "rtf_version"):
        if not isinstance(value[field], str) or not value[field]:
            raise _fixture_error(f"{field} must be a nonempty string")
    if value["classification"] not in CLASSIFICATIONS:
        raise _fixture_error(f"unknown fixture classification: {value['classification']!r}")
    for field in ("applicable_questions", "known_limitations"):
        if not isinstance(value[field], list) or not value[field] or any(
            not isinstance(item, str) or not item for item in value[field]
        ):
            raise _fixture_error(f"{field} must be a nonempty array of strings")
    for field in ("resolved_preset_sha256", "historical_archive_sha256"):
        if not isinstance(value[field], str) or not _is_sha256(value[field]):
            raise _fixture_error(f"{field} must be a lowercase SHA-256")

    root = _fixture_root(metadata_path)
    base = _source_path(metadata_path, value["base"], "base", root)
    files = _read_source(base)
    overlay = None
    if "overlay" in value:
        overlay = _source_path(metadata_path, value["overlay"], "overlay", root)
        files.update(_read_source(overlay))
    if "pack.mcmeta" not in files or RTF_PRESET_PATH not in files:
        raise _fixture_error("materialized source lacks pack.mcmeta or the RTF preset registry entry")
    preset_bytes = files[RTF_PRESET_PATH]
    if _sha256_bytes(preset_bytes) != value["resolved_preset_sha256"]:
        raise _fixture_error("resolved preset hash does not match fixture metadata")
    try:
        preset = json.loads(preset_bytes)
    except json.JSONDecodeError as exc:
        raise _fixture_error(f"resolved preset is not valid JSON: {exc}") from exc
    if not isinstance(preset, dict):
        raise _fixture_error("resolved preset must be a JSON object")

    manifest = {
        "schema_version": 1,
        "id": value["id"],
        "classification": value["classification"],
        "purpose": value["purpose"],
        "applicable_questions": value["applicable_questions"],
        "known_limitations": value["known_limitations"],
        "minecraft_version": value["minecraft_version"],
        "rtf_version": value["rtf_version"],
        "metadata_path": str(metadata_path),
        "base_path": str(base),
        "overlay_path": str(overlay) if overlay else None,
        "historical_archive_sha256": value["historical_archive_sha256"],
        "resolved_preset_sha256": value["resolved_preset_sha256"],
        "resolved_preset": preset,
        "source_file_count": len(files),
        "source_content_sha256": _content_sha256(files),
    }
    return manifest, files


def materialize_fixture(metadata: str | Path, output: str | Path) -> dict[str, Any]:
    manifest, files = load_fixture(metadata)
    output_path = Path(output).expanduser().resolve()
    _write_archive(files, output_path)
    manifest["archive_path"] = str(output_path)
    manifest["archive_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest["archive_size"] = output_path.stat().st_size
    return manifest


def materialize_ephemeral_fixture(
    *,
    fixture_id: str,
    purpose: str,
    base_metadata: str | Path,
    expected_base_preset_sha256: str,
    patch_file: str | Path,
    output: str | Path,
) -> dict[str, Any]:
    if not fixture_id or Path(fixture_id).name != fixture_id:
        raise _fixture_error("ephemeral preset id must be a nonempty path-safe name")
    if not purpose:
        raise _fixture_error("ephemeral preset purpose must be nonempty")
    if not _is_sha256(expected_base_preset_sha256):
        raise _fixture_error("ephemeral base_preset_sha256 must be a lowercase SHA-256")
    base_manifest, files = load_fixture(base_metadata)
    if base_manifest["resolved_preset_sha256"] != expected_base_preset_sha256:
        raise _fixture_error(
            "ephemeral preset base hash does not match the pinned base_preset_sha256"
        )
    patch_path = Path(patch_file).expanduser().resolve()
    if patch_path.is_symlink() or not patch_path.is_file():
        raise _fixture_error(f"ephemeral preset patch is not a regular file: {patch_path}")
    try:
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fixture_error(f"ephemeral preset patch is not valid JSON: {exc}") from exc
    if not isinstance(patch, dict):
        raise _fixture_error("ephemeral preset patch root must be a JSON object")
    resolved = _merge_patch(base_manifest["resolved_preset"], patch)
    if not isinstance(resolved, dict):
        raise _fixture_error("ephemeral preset patch must resolve to a JSON object")
    preset_bytes = (json.dumps(resolved, indent=2, sort_keys=True) + "\n").encode("utf-8")
    files[RTF_PRESET_PATH] = preset_bytes
    output_path = Path(output).expanduser().resolve()
    _write_archive(files, output_path)
    manifest = {
        "schema_version": 1,
        "id": fixture_id,
        "classification": "ephemeral",
        "purpose": purpose,
        "base_fixture_id": base_manifest["id"],
        "base_metadata_path": base_manifest["metadata_path"],
        "base_preset_sha256": expected_base_preset_sha256,
        "patch_path": str(patch_path),
        "patch_sha256": _sha256_bytes(patch_path.read_bytes()),
        "patch": patch,
        "resolved_preset": resolved,
        "resolved_preset_sha256": _sha256_bytes(preset_bytes),
        "source_file_count": len(files),
        "source_content_sha256": _content_sha256(files),
    }
    manifest["archive_path"] = str(output_path)
    manifest["archive_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest["archive_size"] = output_path.stat().st_size
    return manifest
