from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import SaveToolError

FILES = {"bases": "bases", "starships": "starships", "multitools": "multitools"}
SYSTEMS_SCHEMA = "squinch-nms-systems-library-v1"


def _repo_root() -> Path:
    value = os.environ.get("SQUINCH_REPO_ROOT")
    if not value:
        raise SaveToolError("SQUINCH_REPO_ROOT is not set; invoke through tooling/squinch")
    return Path(value).resolve()


def _library_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    allowed = _repo_root() / "games/no-mans-sky/local"
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise SaveToolError(f"entity library must be below {allowed}: {resolved}") from exc
    return resolved


def _read_entity_file(path: Path, field: str) -> tuple[bytes, dict[str, Any], int]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SaveToolError(f"cannot read inventory artifact {path}: {exc}") from exc
    rows = value.get(field) if isinstance(value, dict) else None
    if not isinstance(rows, list) or value.get("unique_count") != len(rows):
        raise SaveToolError(f"inventory artifact {path} has inconsistent {field} data")
    identities = [row.get("identity") for row in rows if isinstance(row, dict)]
    if len(identities) != len(rows) or any(
        not isinstance(identity, str) or not identity for identity in identities
    ):
        raise SaveToolError(f"inventory artifact {path} has invalid entity identities")
    if len(set(identities)) != len(identities):
        raise SaveToolError(f"inventory artifact {path} contains duplicate identities")
    return raw, value, len(rows)


def publish_library(
    inventory_directory: Path,
    output_directory: Path,
    *,
    replace: bool,
) -> dict[str, Any]:
    inventory = inventory_directory.expanduser().resolve()
    output = _library_path(output_directory)
    if not inventory.is_dir():
        raise SaveToolError(f"inventory directory does not exist: {inventory}")
    if output.is_symlink():
        raise SaveToolError(f"refusing symlinked entity library: {output}")
    if output.exists() and not replace:
        raise SaveToolError("entity library exists; pass --replace to publish a new version")

    preserved_systems: tuple[bytes, dict[str, Any], dict[str, Any]] | None = None
    if output.exists():
        try:
            previous_manifest = json.loads((output / "manifest.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SaveToolError(f"cannot read existing entity library manifest: {exc}") from exc
        previous_artifacts = (
            previous_manifest.get("artifacts") if isinstance(previous_manifest, dict) else None
        )
        system_entry = (
            previous_artifacts.get("systems") if isinstance(previous_artifacts, dict) else None
        )
        if isinstance(system_entry, dict):
            system_file = system_entry.get("file")
            if not isinstance(system_file, str):
                raise SaveToolError("existing systems library entry has no file")
            system_path = output / system_file
            if system_path.parent.resolve() != output.resolve() or system_path.is_symlink():
                raise SaveToolError(f"existing systems library path is unsafe: {system_path}")
            try:
                system_raw = system_path.read_bytes()
            except OSError as exc:
                raise SaveToolError(f"cannot read existing systems library: {exc}") from exc
            if hashlib.sha256(system_raw).hexdigest() != system_entry.get("sha256"):
                raise SaveToolError("existing systems library hash does not match its manifest")
            preserved_systems = (system_raw, copy.deepcopy(system_entry), previous_manifest)

    artifacts = {}
    mapping_hashes = set()
    profile_values = set()
    for name, field in FILES.items():
        source = inventory / f"{name}.json"
        raw, value, count = _read_entity_file(source, field)
        artifacts[name] = {
            "source": source,
            "raw": raw,
            "count": count,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        mapping_hashes.add(value.get("mapping_sha256"))
        profile_values.add(value.get("profile"))
    if len(mapping_hashes) != 1 or not next(iter(mapping_hashes), None):
        raise SaveToolError("inventory entity artifacts do not share one mapping hash")
    if len(profile_values) != 1 or not next(iter(profile_values), None):
        raise SaveToolError("inventory entity artifacts do not share one profile")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    try:
        manifest_artifacts = {}
        for name, artifact in artifacts.items():
            target = temporary / f"{name}.json"
            with target.open("xb") as stream:
                stream.write(artifact["raw"])
                stream.flush()
                os.fsync(stream.fileno())
            manifest_artifacts[name] = {
                "file": target.name,
                "unique_count": artifact["count"],
                "sha256": artifact["sha256"],
                "source": str(artifact["source"]),
            }
        if preserved_systems is not None:
            systems_raw, systems_entry, _previous_manifest = preserved_systems
            with (temporary / "systems.json").open("xb") as stream:
                stream.write(systems_raw)
                stream.flush()
                os.fsync(stream.fileno())
            systems_entry["file"] = "systems.json"
            manifest_artifacts["systems"] = systems_entry
        manifest = {
            "schema": (
                "squinch-nms-entity-library-v2"
                if preserved_systems is not None
                else "squinch-nms-entity-library-v1"
            ),
            "published_at": datetime.now(UTC).isoformat(),
            "source_inventory": str(inventory),
            "profile": next(iter(profile_values)),
            "mapping_sha256": next(iter(mapping_hashes)),
            "artifacts": manifest_artifacts,
        }
        if preserved_systems is not None:
            _systems_raw, _systems_entry, previous_manifest = preserved_systems
            manifest["source_systems"] = previous_manifest.get("source_systems")
            manifest["systems_published_at"] = previous_manifest.get("systems_published_at")
        manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        with (temporary / "manifest.json").open("xb") as stream:
            stream.write(manifest_raw)
            stream.flush()
            os.fsync(stream.fileno())

        previous = None
        if output.exists():
            history = output.parent / f"{output.name}.history"
            history.mkdir(exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            previous = history / f"{stamp}-{uuid.uuid4().hex[:8]}"
            os.replace(output, previous)
        try:
            os.replace(temporary, output)
        except Exception:
            if previous is not None and not output.exists():
                os.replace(previous, output)
            raise
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "library": str(output),
        "manifest": str(output / "manifest.json"),
        "counts": {name: artifact["count"] for name, artifact in artifacts.items()},
        "replaced": replace,
    }


def publish_systems_library(systems_path: Path, output_directory: Path) -> dict[str, Any]:
    source = systems_path.expanduser().resolve()
    output = _library_path(output_directory)
    if output.is_symlink() or not output.is_dir():
        raise SaveToolError(f"entity library does not exist or is unsafe: {output}")
    try:
        systems_raw = source.read_bytes()
        systems = json.loads(systems_raw)
        manifest_raw = (output / "manifest.json").read_bytes()
        manifest = json.loads(manifest_raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SaveToolError(f"cannot read systems/library artifact: {exc}") from exc
    rows = systems.get("systems") if isinstance(systems, dict) else None
    if systems.get("schema") != SYSTEMS_SCHEMA or not isinstance(rows, list):
        raise SaveToolError(f"unsupported systems artifact: {source}")
    identities = [row.get("identity") for row in rows if isinstance(row, dict)]
    if (
        systems.get("unique_count") != len(rows)
        or len(identities) != len(rows)
        or any(not isinstance(identity, str) or not identity for identity in identities)
        or len(set(identities)) != len(identities)
    ):
        raise SaveToolError("systems artifact has inconsistent or duplicate identities")
    if not isinstance(manifest, dict) or manifest.get("schema") not in {
        "squinch-nms-entity-library-v1",
        "squinch-nms-entity-library-v2",
    }:
        raise SaveToolError("persistent entity library has an unsupported manifest")
    mapping = systems.get("mapping")
    if not isinstance(mapping, dict) or mapping.get("sha256") != manifest.get("mapping_sha256"):
        raise SaveToolError("systems and entity library mapping hashes differ")
    if systems.get("profile") != manifest.get("profile"):
        raise SaveToolError("systems and entity library profiles differ")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SaveToolError("entity library manifest has no artifacts")

    existing: dict[str, bytes] = {}
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict) or not isinstance(artifact.get("file"), str):
            raise SaveToolError(f"entity library artifact {name!r} is invalid")
        path = output / artifact["file"]
        if path.parent.resolve() != output.resolve() or path.is_symlink():
            raise SaveToolError(f"entity library artifact is unsafe: {path}")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise SaveToolError(f"cannot read entity library artifact {path}: {exc}") from exc
        if hashlib.sha256(raw).hexdigest() != artifact.get("sha256"):
            raise SaveToolError(f"entity library artifact hash mismatch: {path}")
        existing[path.name] = raw

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    previous = None
    try:
        for name, raw in existing.items():
            with (temporary / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        with (temporary / "systems.json").open("xb") as stream:
            stream.write(systems_raw)
            stream.flush()
            os.fsync(stream.fileno())
        updated = copy.deepcopy(manifest)
        updated["schema"] = "squinch-nms-entity-library-v2"
        updated["systems_published_at"] = datetime.now(UTC).isoformat()
        updated["source_systems"] = str(source)
        updated["artifacts"]["systems"] = {
            "file": "systems.json",
            "unique_count": len(rows),
            "record_counts": systems.get("record_counts"),
            "visited_system_count": systems.get("visited_system_count"),
            "sha256": hashlib.sha256(systems_raw).hexdigest(),
            "source": str(source),
        }
        new_manifest_raw = (json.dumps(updated, indent=2, sort_keys=True) + "\n").encode()
        with (temporary / "manifest.json").open("xb") as stream:
            stream.write(new_manifest_raw)
            stream.flush()
            os.fsync(stream.fileno())

        history = output.parent / f"{output.name}.history"
        history.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        previous = history / f"{stamp}-{uuid.uuid4().hex[:8]}"
        os.replace(output, previous)
        try:
            os.replace(temporary, output)
        except Exception:
            if not output.exists():
                os.replace(previous, output)
            raise
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "library": str(output),
        "manifest": str(output / "manifest.json"),
        "systems": str(output / "systems.json"),
        "unique_systems": len(rows),
        "previous_library": str(previous),
    }
