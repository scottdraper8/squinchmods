from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codec import RawNumber, decode_bytes, decode_file, encode_document
from .errors import SaveToolError
from .jsonops import apply_patch, json_equal
from .meta import inspect_meta_bytes, rename_meta, update_meta
from .paths import identity, require_pair

STAGE_SCHEMA = "squinch-nms-save-stage-v1"


def _metadata_size_mode(meta_info: Any, decoded_size: int, compressed_size: int) -> str:
    if meta_info.decompressed_size == decoded_size:
        return "decoded"
    if (
        meta_info.decompressed_size == compressed_size
        and meta_info.compressed_size == compressed_size
    ):
        return "compressed"
    raise SaveToolError(
        "source metadata size fields match neither the decoded nor compressed save size"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SaveToolError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _read_patch(path: Path) -> tuple[list[Any], bytes]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate object key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite number {value}")

    try:
        raw = path.read_bytes()
        operations = json.loads(
            raw.decode("utf-8"),
            parse_float=RawNumber,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise SaveToolError(f"cannot read JSON Patch {path}: {exc}") from exc
    if not isinstance(operations, list):
        raise SaveToolError("JSON Patch root must be an array")
    return operations, raw


def _workspace() -> Path:
    value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    return Path(value).resolve()


def _workspace_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(_workspace())
    except ValueError as exc:
        raise SaveToolError(f"{label} must be inside the selected tranche: {resolved}") from exc
    return resolved


def _new_stage_directory() -> Path:
    root = _workspace() / "no-mans-sky/save-edit/stages"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"{stamp}-{uuid.uuid4().hex[:12]}"
    path.mkdir(mode=0o700)
    return path


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write {path}: {exc}") from exc


def create_stage(
    source_path: Path,
    patch_path: Path,
    *,
    output_directory: Path | None = None,
    timestamp: int | None = None,
    metadata_save_name: str | None = None,
) -> dict[str, Any]:
    source = identity(source_path)
    require_pair(source)
    patch_path = _workspace_path(patch_path, "patch")
    try:
        original_data = source.path.read_bytes()
        original_meta = source.meta_path.read_bytes()
    except OSError as exc:
        raise SaveToolError(f"cannot read source pair: {exc}") from exc
    decoded = decode_bytes(original_data, source=str(source.path))
    original_meta_info = inspect_meta_bytes(original_meta, source.path)
    size_mode = _metadata_size_mode(
        original_meta_info, decoded.decompressed_size, len(original_data)
    )
    if (
        size_mode == "decoded"
        and original_meta_info.compressed_size is not None
        and original_meta_info.compressed_size != len(original_data)
    ):
        raise SaveToolError(
            "source metadata compressed size does not match the source save; refusing to stage"
        )

    operations, patch_bytes = _read_patch(patch_path)
    edited = apply_patch(decoded.document, operations)
    staged_data, decompressed_size = encode_document(edited)
    staged_meta, staged_meta_info = update_meta(
        original_meta,
        source.path,
        decompressed_size=decompressed_size,
        compressed_size=len(staged_data),
        timestamp=timestamp,
        size_mode=size_mode,
    )
    if metadata_save_name is not None:
        staged_meta = rename_meta(staged_meta, source.path, metadata_save_name)
        staged_meta_info = inspect_meta_bytes(staged_meta, source.path)

    round_trip = decode_bytes(staged_data, source="staged save")
    if not json_equal(edited, round_trip.document):
        raise SaveToolError("staged save failed semantic encode/decode verification")
    expected_primary_size = (
        round_trip.decompressed_size if size_mode == "decoded" else len(staged_data)
    )
    if staged_meta_info.decompressed_size != expected_primary_size:
        raise SaveToolError("staged metadata has the wrong decompressed size")
    if staged_meta_info.compressed_size is not None and staged_meta_info.compressed_size != len(
        staged_data
    ):
        raise SaveToolError("staged metadata has the wrong compressed size")
    if sha256_file(source.path) != sha256_bytes(original_data) or sha256_file(
        source.meta_path
    ) != sha256_bytes(original_meta):
        raise SaveToolError("source pair changed while staging; create a new stage")

    stage_dir = (
        _workspace_path(output_directory, "stage output")
        if output_directory
        else _new_stage_directory()
    )
    if output_directory:
        try:
            stage_dir.mkdir(parents=True, mode=0o700)
        except OSError as exc:
            raise SaveToolError(f"cannot create stage directory {stage_dir}: {exc}") from exc
        if any(stage_dir.iterdir()):
            raise SaveToolError(f"stage directory must be empty: {stage_dir}")

    data_name = source.path.name
    meta_name = source.meta_path.name
    _write_new(stage_dir / data_name, staged_data)
    _write_new(stage_dir / meta_name, staged_meta)
    manifest: dict[str, Any] = {
        "schema": STAGE_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(),
        "source": {
            "data": str(source.path),
            "meta": str(source.meta_path),
            "data_sha256": sha256_bytes(original_data),
            "meta_sha256": sha256_bytes(original_meta),
        },
        "patch": {
            "path": str(patch_path.expanduser().resolve()),
            "sha256": sha256_bytes(patch_bytes),
            "operations": [
                {key: operation[key] for key in ("op", "path", "from") if key in operation}
                for operation in operations
                if isinstance(operation, dict)
            ],
        },
        "metadata_save_name": metadata_save_name,
        "staged": {
            "data": data_name,
            "meta": meta_name,
            "data_sha256": sha256_bytes(staged_data),
            "meta_sha256": sha256_bytes(staged_meta),
            "compressed_size": len(staged_data),
            "decompressed_size": decompressed_size,
            "meta_format": staged_meta_info.format,
            "base_version": staged_meta_info.base_version,
            "size_mode": size_mode,
        },
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    _write_new(stage_dir / "manifest.json", manifest_bytes)
    return {"stage": str(stage_dir), "manifest": manifest}


def _load_manifest(stage_path: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = (
        stage_path if stage_path.name == "manifest.json" else stage_path / "manifest.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveToolError(f"cannot read stage manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != STAGE_SCHEMA:
        raise SaveToolError(f"unsupported stage manifest: {manifest_path}")
    return manifest_path.parent.resolve(), manifest


def verify_stage(stage_path: Path, *, verify_source: bool = True) -> dict[str, Any]:
    stage_dir, manifest = _load_manifest(stage_path)
    try:
        source = identity(Path(manifest["source"]["data"]))
        staged_data = (stage_dir / manifest["staged"]["data"]).resolve()
        staged_meta = (stage_dir / manifest["staged"]["meta"]).resolve()
    except (KeyError, TypeError, SaveToolError) as exc:
        raise SaveToolError(f"invalid stage manifest fields: {exc}") from exc
    if staged_data.parent != stage_dir or staged_meta.parent != stage_dir:
        raise SaveToolError("stage manifest points outside its stage directory")
    if staged_data.name != source.path.name or staged_meta.name != source.meta_path.name:
        raise SaveToolError("staged pair filenames do not match the source pair")
    if sha256_file(staged_data) != manifest["staged"].get("data_sha256"):
        raise SaveToolError("staged save hash does not match the manifest")
    if sha256_file(staged_meta) != manifest["staged"].get("meta_sha256"):
        raise SaveToolError("staged metadata hash does not match the manifest")

    decoded = decode_file(staged_data)
    meta_info = inspect_meta_bytes(staged_meta.read_bytes(), source.path)
    size_mode = manifest["staged"].get("size_mode", "decoded")
    expected_primary_size = (
        decoded.decompressed_size if size_mode == "decoded" else staged_data.stat().st_size
    )
    if expected_primary_size != meta_info.decompressed_size:
        raise SaveToolError("staged save and metadata decompressed sizes differ")
    if (
        meta_info.compressed_size is not None
        and staged_data.stat().st_size != meta_info.compressed_size
    ):
        raise SaveToolError("staged save and metadata compressed sizes differ")

    source_current = None
    if verify_source:
        require_pair(source)
        data_matches = sha256_file(source.path) == manifest["source"].get("data_sha256")
        meta_matches = sha256_file(source.meta_path) == manifest["source"].get("meta_sha256")
        if not data_matches or not meta_matches:
            raise SaveToolError("source pair changed after staging; create a new stage")
        source_current = True
    return {
        "stage": str(stage_dir),
        "valid": True,
        "source_current": source_current,
        "source": str(source.path),
        "compressed_size": staged_data.stat().st_size,
        "decompressed_size": decoded.decompressed_size,
        "meta_format": meta_info.format,
        "base_version": meta_info.base_version,
        "size_mode": size_mode,
    }


def _nms_processes() -> list[int]:
    matches: list[int] = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip().lower()
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            names = {comm, *(Path(arg.decode(errors="ignore")).name.lower() for arg in argv if arg)}
        except (OSError, UnicodeError):
            continue
        if "nms.exe" in names:
            matches.append(int(entry.name))
    return matches


def _copy_for_replace(source: Path, destination: Path, mode: int) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.squinch-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as output, source.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def apply_stage(
    stage_path: Path,
    *,
    apply: bool,
    backup_directory: Path | None = None,
) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to modify a save without the explicit --apply flag")
    running = _nms_processes()
    if running:
        raise SaveToolError(f"NMS.exe is running (PIDs {running}); stop the game before applying")
    verification = verify_stage(stage_path, verify_source=True)
    stage_dir, manifest = _load_manifest(stage_path)
    source = identity(Path(manifest["source"]["data"]))
    staged_data = stage_dir / manifest["staged"]["data"]
    staged_meta = stage_dir / manifest["staged"]["meta"]

    if backup_directory is None:
        root = _workspace() / "no-mans-sky/save-edit/backups"
        root.mkdir(parents=True, exist_ok=True)
        backup = root / f"{stage_dir.name}-{uuid.uuid4().hex[:8]}"
    else:
        backup = _workspace_path(backup_directory, "backup directory")
    try:
        backup.mkdir(parents=True, mode=0o700)
    except OSError as exc:
        raise SaveToolError(f"cannot create backup directory {backup}: {exc}") from exc
    if any(backup.iterdir()):
        raise SaveToolError(f"backup directory must be empty: {backup}")

    backup_data = backup / source.path.name
    backup_meta = backup / source.meta_path.name
    try:
        shutil.copy2(source.path, backup_data)
        shutil.copy2(source.meta_path, backup_meta)
    except OSError as exc:
        raise SaveToolError(f"cannot back up source pair: {exc}") from exc
    if (
        sha256_file(backup_data) != manifest["source"]["data_sha256"]
        or sha256_file(backup_meta) != manifest["source"]["meta_sha256"]
    ):
        raise SaveToolError("backup verification failed; source was not modified")
    if (
        sha256_file(source.path) != manifest["source"]["data_sha256"]
        or sha256_file(source.meta_path) != manifest["source"]["meta_sha256"]
    ):
        raise SaveToolError("source pair changed during backup; source was not modified")

    data_mode = source.path.stat().st_mode & 0o777
    meta_mode = source.meta_path.stat().st_mode & 0o777
    replaced_data = False
    replaced_meta = False
    try:
        _copy_for_replace(staged_data, source.path, data_mode)
        replaced_data = True
        _copy_for_replace(staged_meta, source.meta_path, meta_mode)
        replaced_meta = True
        directory_fd = os.open(source.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        rollback_errors: list[str] = []
        for was_replaced, saved, target, mode in (
            (replaced_data, backup_data, source.path, data_mode),
            (replaced_meta, backup_meta, source.meta_path, meta_mode),
        ):
            if was_replaced:
                try:
                    _copy_for_replace(saved, target, mode)
                except (
                    Exception
                ) as rollback_exc:  # pragma: no cover - catastrophic filesystem error
                    rollback_errors.append(str(rollback_exc))
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        raise SaveToolError(f"apply failed and rollback was attempted: {exc}{detail}") from exc

    if (
        sha256_file(source.path) != manifest["staged"]["data_sha256"]
        or sha256_file(source.meta_path) != manifest["staged"]["meta_sha256"]
    ):
        raise SaveToolError(f"post-apply verification failed; recover from backup {backup}")
    backup_manifest = {
        "schema": "squinch-nms-save-backup-v1",
        "source": str(source.path),
        "data_sha256": manifest["source"]["data_sha256"],
        "meta_sha256": manifest["source"]["meta_sha256"],
        "applied_stage": str(stage_dir),
    }
    _write_new(
        backup / "manifest.json",
        (json.dumps(backup_manifest, indent=2, sort_keys=True) + "\n").encode(),
    )
    verification.pop("source_current", None)
    return {
        **verification,
        "source_current_before_apply": True,
        "applied": True,
        "backup": str(backup),
    }


def apply_stage_batch(stage_paths: list[Path], *, apply: bool) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to modify saves without the explicit --apply flag")
    if len(stage_paths) < 2:
        raise SaveToolError("batch apply requires at least two stages")
    running = _nms_processes()
    if running:
        raise SaveToolError(f"NMS.exe is running (PIDs {running}); stop the game before applying")

    entries = []
    source_paths: set[Path] = set()
    for stage_path in stage_paths:
        verify_stage(stage_path, verify_source=True)
        stage_dir, manifest = _load_manifest(stage_path)
        source = identity(Path(manifest["source"]["data"]))
        if source.path in source_paths:
            raise SaveToolError(f"batch contains duplicate source: {source.path}")
        source_paths.add(source.path)
        entries.append(
            {
                "stage": stage_dir,
                "manifest": manifest,
                "source": source,
                "staged_data": stage_dir / manifest["staged"]["data"],
                "staged_meta": stage_dir / manifest["staged"]["meta"],
            }
        )

    backup_root = _workspace() / "no-mans-sky/save-edit/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"batch-{stamp}-{uuid.uuid4().hex[:8]}"
    backup.mkdir(mode=0o700)
    replaced: list[tuple[Path, Path, int]] = []
    backup_entries = []
    try:
        for index, entry in enumerate(entries):
            source = entry["source"]
            manifest = entry["manifest"]
            pair_backup = backup / f"{index + 1:02d}-{source.path.name}"
            pair_backup.mkdir(mode=0o700)
            backup_data = pair_backup / source.path.name
            backup_meta = pair_backup / source.meta_path.name
            shutil.copy2(source.path, backup_data)
            shutil.copy2(source.meta_path, backup_meta)
            if (
                sha256_file(backup_data) != manifest["source"]["data_sha256"]
                or sha256_file(backup_meta) != manifest["source"]["meta_sha256"]
            ):
                raise SaveToolError(f"batch backup verification failed for {source.path}")
            entry["backup_data"] = backup_data
            entry["backup_meta"] = backup_meta
            backup_entries.append(
                {
                    "source": str(source.path),
                    "source_meta": str(source.meta_path),
                    "data_sha256": manifest["source"]["data_sha256"],
                    "meta_sha256": manifest["source"]["meta_sha256"],
                    "stage": str(entry["stage"]),
                    "backup_directory": pair_backup.name,
                }
            )

        for entry in entries:
            source = entry["source"]
            manifest = entry["manifest"]
            if (
                sha256_file(source.path) != manifest["source"]["data_sha256"]
                or sha256_file(source.meta_path) != manifest["source"]["meta_sha256"]
            ):
                raise SaveToolError(f"batch source changed during backup: {source.path}")

        for entry in entries:
            source = entry["source"]
            data_mode = source.path.stat().st_mode & 0o777
            meta_mode = source.meta_path.stat().st_mode & 0o777
            _copy_for_replace(entry["staged_data"], source.path, data_mode)
            replaced.append((entry["backup_data"], source.path, data_mode))
            _copy_for_replace(entry["staged_meta"], source.meta_path, meta_mode)
            replaced.append((entry["backup_meta"], source.meta_path, meta_mode))

        for entry in entries:
            source = entry["source"]
            manifest = entry["manifest"]
            if (
                sha256_file(source.path) != manifest["staged"]["data_sha256"]
                or sha256_file(source.meta_path) != manifest["staged"]["meta_sha256"]
            ):
                raise SaveToolError(f"batch post-apply verification failed for {source.path}")
        for directory in {entry["source"].path.parent for entry in entries}:
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception as exc:
        rollback_errors = []
        for saved, target, mode in reversed(replaced):
            try:
                _copy_for_replace(saved, target, mode)
            except Exception as rollback_exc:  # pragma: no cover - catastrophic filesystem error
                rollback_errors.append(f"{target}: {rollback_exc}")
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        if isinstance(exc, SaveToolError):
            raise SaveToolError(f"batch apply failed; rollback attempted: {exc}{detail}") from exc
        raise SaveToolError(f"batch apply failed; rollback attempted: {exc}{detail}") from exc

    manifest = {
        "schema": "squinch-nms-save-batch-backup-v1",
        "applied_at": datetime.now(UTC).isoformat(),
        "entries": backup_entries,
    }
    _write_new(
        backup / "manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
    )
    return {
        "applied": True,
        "count": len(entries),
        "backup": str(backup),
        "sources": [str(entry["source"].path) for entry in entries],
    }
