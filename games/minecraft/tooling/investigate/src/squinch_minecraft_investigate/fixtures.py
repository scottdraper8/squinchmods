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

FTF_PRESET_PATH = "data/freeterraforged/freeterraforged/worldgen/preset/preset.json"
CLASSIFICATIONS = {"reusable-control", "reusable-stress", "feature-specific"}


def _fixture_error(message: str) -> InvestigationError:
    return InvestigationError("invalid_fixture", message)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def load_fixture(metadata: str | Path) -> dict[str, Any]:
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
        "ftf_version",
        "preset",
        "preset_sha256",
    }
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise _fixture_error(
            f"fixture metadata keys invalid; missing={missing}, unknown={unknown}"
        )
    if value["schema_version"] != 2:
        raise _fixture_error("fixture schema_version must be 2")
    for field in ("id", "purpose", "minecraft_version", "ftf_version"):
        if not isinstance(value[field], str) or not value[field]:
            raise _fixture_error(f"{field} must be a nonempty string")
    if value["classification"] not in CLASSIFICATIONS:
        raise _fixture_error(f"unknown fixture classification: {value['classification']!r}")
    for field in ("applicable_questions", "known_limitations"):
        if not isinstance(value[field], list) or not value[field] or any(
            not isinstance(item, str) or not item for item in value[field]
        ):
            raise _fixture_error(f"{field} must be a nonempty array of strings")
    if value["preset"] != "preset.json":
        raise _fixture_error("preset must be the fixture-local preset.json")
    if not isinstance(value["preset_sha256"], str) or not _is_sha256(
        value["preset_sha256"]
    ):
        raise _fixture_error("preset_sha256 must be a lowercase SHA-256")
    preset_path = metadata_path.parent / value["preset"]
    if preset_path.is_symlink() or not preset_path.is_file():
        raise _fixture_error(f"preset is not a regular file: {preset_path}")
    preset_bytes = preset_path.read_bytes()
    preset_sha256 = hashlib.sha256(preset_bytes).hexdigest()
    if preset_sha256 != value["preset_sha256"]:
        raise _fixture_error("preset hash does not match fixture metadata")
    try:
        preset = json.loads(preset_bytes)
    except json.JSONDecodeError as exc:
        raise _fixture_error(f"preset is not valid JSON: {exc}") from exc
    if not isinstance(preset, dict):
        raise _fixture_error("preset must be a JSON object")
    return {
        "schema_version": 2,
        "id": value["id"],
        "classification": value["classification"],
        "purpose": value["purpose"],
        "applicable_questions": value["applicable_questions"],
        "known_limitations": value["known_limitations"],
        "minecraft_version": value["minecraft_version"],
        "ftf_version": value["ftf_version"],
        "metadata_path": str(metadata_path),
        "preset_path": str(preset_path),
        "preset_sha256": preset_sha256,
        "resolved_preset_sha256": preset_sha256,
        "resolved_preset": preset,
    }


def archive_generated_fixture(source: str | Path, output: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if source_path.is_symlink() or not source_path.is_dir():
        raise _fixture_error(f"generated fixture is not a regular directory: {source_path}")
    files: list[tuple[str, bytes]] = []
    for path in sorted(source_path.rglob("*")):
        if path.is_symlink():
            raise _fixture_error(f"generated fixture contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise _fixture_error(f"generated fixture contains a non-file: {path}")
        files.append((path.relative_to(source_path).as_posix(), path.read_bytes()))
    if not files:
        raise _fixture_error(f"generated fixture is empty: {source_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_symlink() or (output_path.exists() and not output_path.is_file()):
        raise _fixture_error(f"output must be a regular file path: {output_path}")
    temporary = output_path.parent / f".{output_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for relative, content in files:
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "archive_path": str(output_path),
        "archive_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "archive_size": output_path.stat().st_size,
        "file_count": len(files),
    }
