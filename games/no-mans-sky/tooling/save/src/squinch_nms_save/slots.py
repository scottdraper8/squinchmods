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

from .codec import decode_bytes
from .errors import SaveToolError
from .meta import inspect_meta_bytes, rekey_meta
from .paths import identity, require_pair
from .stage import _copy_for_replace, _nms_processes, sha256_file


def _workspace() -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    return Path(workspace_value).resolve()


def _workspace_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(_workspace())
    except ValueError as exc:
        raise SaveToolError(
            f"slot archive must be inside the selected tranche: {resolved}"
        ) from exc
    return resolved


def _save_name(ordinal: int) -> str:
    return "save.hg" if ordinal == 1 else f"save{ordinal}.hg"


def _write_new(path: Path, value: dict[str, Any]) -> None:
    try:
        with path.open("xb") as stream:
            stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write slot archive manifest {path}: {exc}") from exc


def _replace_bytes(value: bytes, destination: Path, mode: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.squinch-", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def archive_slots(
    directory: Path,
    slots: list[int],
    output: Path,
    *,
    apply: bool,
) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to remove save slots without the explicit --apply flag")
    if not slots or len(set(slots)) != len(slots) or any(not 1 <= slot <= 10 for slot in slots):
        raise SaveToolError("slots must be unique values between 1 and 10")
    running = _nms_processes()
    if running:
        raise SaveToolError(
            f"NMS.exe is running (PIDs {running}); stop the game before removing slots"
        )
    profile = directory.expanduser().resolve()
    if not profile.is_dir():
        raise SaveToolError(f"save directory does not exist: {profile}")
    archive = _workspace_path(output)
    if archive.exists():
        raise SaveToolError(f"refusing to overwrite slot archive: {archive}")

    entries = []
    for slot in sorted(slots):
        for ordinal in (slot * 2 - 1, slot * 2):
            save = identity(profile / _save_name(ordinal))
            require_pair(save)
            entries.append(
                {
                    "slot": slot,
                    "kind": save.kind,
                    "save": save.path,
                    "meta": save.meta_path,
                    "save_sha256": sha256_file(save.path),
                    "meta_sha256": sha256_file(save.meta_path),
                    "save_mode": save.path.stat().st_mode & 0o777,
                    "meta_mode": save.meta_path.stat().st_mode & 0o777,
                }
            )

    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.parent / f".{archive.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    manifest_entries = []
    try:
        for entry in entries:
            pair = temporary / f"slot-{entry['slot']}-{entry['kind']}"
            pair.mkdir(mode=0o700)
            archived_save = pair / entry["save"].name
            archived_meta = pair / entry["meta"].name
            shutil.copy2(entry["save"], archived_save)
            shutil.copy2(entry["meta"], archived_meta)
            if (
                sha256_file(archived_save) != entry["save_sha256"]
                or sha256_file(archived_meta) != entry["meta_sha256"]
            ):
                raise SaveToolError(f"slot archive verification failed for {entry['save']}")
            entry["archived_save"] = archived_save
            entry["archived_meta"] = archived_meta
            manifest_entries.append(
                {
                    "slot": entry["slot"],
                    "kind": entry["kind"],
                    "source_save": str(entry["save"]),
                    "source_meta": str(entry["meta"]),
                    "save_sha256": entry["save_sha256"],
                    "meta_sha256": entry["meta_sha256"],
                    "archive_directory": pair.name,
                }
            )
        manifest = {
            "schema": "squinch-nms-save-slot-archive-v1",
            "archived_at": datetime.now(UTC).isoformat(),
            "profile": str(profile),
            "slots": sorted(slots),
            "entries": manifest_entries,
        }
        _write_new(temporary / "manifest.json", manifest)
        os.replace(temporary, archive)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    removed: list[dict[str, Any]] = []
    try:
        for entry in entries:
            entry["save"].unlink()
            removed.append(entry)
            entry["meta"].unlink()
        directory_fd = os.open(profile, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        rollback_errors = []
        for entry in entries:
            for archived_name, target_name, mode_name in (
                ("archived_save", "save", "save_mode"),
                ("archived_meta", "meta", "meta_mode"),
            ):
                target = entry[target_name]
                if not target.exists():
                    try:
                        archived = archive / entry[archived_name].parent.name / target.name
                        _copy_for_replace(archived, target, entry[mode_name])
                    except Exception as rollback_exc:  # pragma: no cover
                        rollback_errors.append(f"{target}: {rollback_exc}")
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        raise SaveToolError(f"slot removal failed; rollback attempted: {exc}{detail}") from exc

    for entry in entries:
        if entry["save"].exists() or entry["meta"].exists():
            raise SaveToolError(f"slot removal verification failed for {entry['save']}")
    return {
        "removed": True,
        "slots": sorted(slots),
        "pairs": len(entries),
        "files": len(entries) * 2,
        "archive": str(archive),
        "manifest": str(archive / "manifest.json"),
    }


def swap_slots(
    directory: Path,
    slot_a: int,
    slot_b: int,
    *,
    apply: bool,
) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to swap save slots without the explicit --apply flag")
    if not 1 <= slot_a <= 10 or not 1 <= slot_b <= 10 or slot_a == slot_b:
        raise SaveToolError("swap slots must be distinct values between 1 and 10")
    running = _nms_processes()
    if running:
        raise SaveToolError(
            f"NMS.exe is running (PIDs {running}); stop the game before swapping slots"
        )
    profile = directory.expanduser().resolve()
    if not profile.is_dir():
        raise SaveToolError(f"save directory does not exist: {profile}")

    entries = []
    by_slot_kind = {}
    for slot in (slot_a, slot_b):
        for ordinal in (slot * 2 - 1, slot * 2):
            save = identity(profile / _save_name(ordinal))
            require_pair(save)
            data = save.path.read_bytes()
            meta = save.meta_path.read_bytes()
            decoded = decode_bytes(data, source=str(save.path))
            info = inspect_meta_bytes(meta, save.path)
            if info.encrypted_slot != info.storage_slot:
                raise SaveToolError(f"metadata encryption slot mismatch for {save.meta_path}")
            if info.decompressed_size not in {decoded.decompressed_size, len(data)}:
                raise SaveToolError(f"metadata size does not match {save.path}")
            if info.compressed_size is not None and info.compressed_size != len(data):
                raise SaveToolError(f"metadata compressed size does not match {save.path}")
            entry = {
                "slot": slot,
                "kind": save.kind,
                "save": save.path,
                "meta": save.meta_path,
                "data": data,
                "meta_data": meta,
                "data_sha256": sha256_file(save.path),
                "meta_sha256": sha256_file(save.meta_path),
                "data_mode": save.path.stat().st_mode & 0o777,
                "meta_mode": save.meta_path.stat().st_mode & 0o777,
            }
            entries.append(entry)
            by_slot_kind[(slot, save.kind)] = entry

    backup_root = _workspace_path(_workspace() / "no-mans-sky/save-edit/backups")
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / f"slot-swap-{slot_a}-{slot_b}-{stamp}-{uuid.uuid4().hex[:8]}"
    backup.mkdir(mode=0o700)
    manifest_entries = []
    replaced = []
    try:
        for entry in entries:
            pair_backup = backup / f"slot-{entry['slot']}-{entry['kind']}"
            pair_backup.mkdir(mode=0o700)
            backup_save = pair_backup / entry["save"].name
            backup_meta = pair_backup / entry["meta"].name
            shutil.copy2(entry["save"], backup_save)
            shutil.copy2(entry["meta"], backup_meta)
            if (
                sha256_file(backup_save) != entry["data_sha256"]
                or sha256_file(backup_meta) != entry["meta_sha256"]
            ):
                raise SaveToolError(f"slot-swap backup verification failed for {entry['save']}")
            entry["backup_save"] = backup_save
            entry["backup_meta"] = backup_meta

        prepared = []
        for destination in entries:
            source_slot = slot_b if destination["slot"] == slot_a else slot_a
            source = by_slot_kind[(source_slot, destination["kind"])]
            destination_meta = rekey_meta(source["meta_data"], source["save"], destination["save"])
            decoded = decode_bytes(source["data"], source=f"swap for {destination['save']}")
            info = inspect_meta_bytes(destination_meta, destination["save"])
            primary_matches = info.decompressed_size in {
                decoded.decompressed_size,
                len(source["data"]),
            }
            if not primary_matches:
                raise SaveToolError(
                    f"rekeyed metadata size does not match {destination['save'].name}"
                )
            if info.compressed_size is not None and info.compressed_size != len(source["data"]):
                raise SaveToolError(
                    f"rekeyed metadata compressed size does not match {destination['save'].name}"
                )
            prepared.append(
                {
                    "destination": destination,
                    "source": source,
                    "data": source["data"],
                    "meta": destination_meta,
                }
            )
            manifest_entries.append(
                {
                    "source_slot": source["slot"],
                    "destination_slot": destination["slot"],
                    "kind": destination["kind"],
                    "source_save": str(source["save"]),
                    "destination_save": str(destination["save"]),
                    "original_data_sha256": destination["data_sha256"],
                    "original_meta_sha256": destination["meta_sha256"],
                    "installed_data_sha256": sha256_file(source["backup_save"]),
                    "installed_meta_sha256": hashlib.sha256(destination_meta).hexdigest(),
                    "backup_directory": destination["backup_save"].parent.name,
                }
            )

        for entry in entries:
            if (
                sha256_file(entry["save"]) != entry["data_sha256"]
                or sha256_file(entry["meta"]) != entry["meta_sha256"]
            ):
                raise SaveToolError(f"slot changed during swap backup: {entry['save']}")

        for item in prepared:
            destination = item["destination"]
            _replace_bytes(item["data"], destination["save"], destination["data_mode"])
            replaced.append(
                (destination["backup_save"], destination["save"], destination["data_mode"])
            )
            _replace_bytes(item["meta"], destination["meta"], destination["meta_mode"])
            replaced.append(
                (destination["backup_meta"], destination["meta"], destination["meta_mode"])
            )

        for item in prepared:
            destination = item["destination"]
            expected_data = item["source"]["data_sha256"]
            expected_meta = hashlib.sha256(item["meta"]).hexdigest()
            if (
                sha256_file(destination["save"]) != expected_data
                or sha256_file(destination["meta"]) != expected_meta
            ):
                raise SaveToolError(
                    f"slot-swap post-apply verification failed for {destination['save']}"
                )
            decode_bytes(destination["save"].read_bytes(), source=str(destination["save"]))
            info = inspect_meta_bytes(destination["meta"].read_bytes(), destination["save"])
            if info.encrypted_slot != info.storage_slot:
                raise SaveToolError(
                    f"slot-swap metadata verification failed for {destination['meta']}"
                )

        directory_fd = os.open(profile, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        rollback_errors = []
        for saved, target, mode in reversed(replaced):
            try:
                _copy_for_replace(saved, target, mode)
            except Exception as rollback_exc:  # pragma: no cover
                rollback_errors.append(f"{target}: {rollback_exc}")
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        raise SaveToolError(f"slot swap failed; rollback attempted: {exc}{detail}") from exc

    manifest = {
        "schema": "squinch-nms-save-slot-swap-v1",
        "applied_at": datetime.now(UTC).isoformat(),
        "profile": str(profile),
        "slots": [slot_a, slot_b],
        "entries": manifest_entries,
    }
    _write_new(backup / "manifest.json", manifest)
    return {
        "swapped": True,
        "slots": [slot_a, slot_b],
        "pairs": len(entries),
        "backup": str(backup),
        "manifest": str(backup / "manifest.json"),
    }


def move_slot(
    directory: Path,
    source_slot: int,
    destination_slot: int,
    *,
    apply: bool,
) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to move a save slot without the explicit --apply flag")
    if (
        not 1 <= source_slot <= 10
        or not 1 <= destination_slot <= 10
        or source_slot == destination_slot
    ):
        raise SaveToolError("source and destination must be distinct slots between 1 and 10")
    running = _nms_processes()
    if running:
        raise SaveToolError(
            f"NMS.exe is running (PIDs {running}); stop the game before moving slots"
        )
    profile = directory.expanduser().resolve()
    if not profile.is_dir():
        raise SaveToolError(f"save directory does not exist: {profile}")

    entries = []
    for offset, kind in enumerate(("auto", "manual")):
        source_ordinal = source_slot * 2 - 1 + offset
        destination_ordinal = destination_slot * 2 - 1 + offset
        source = identity(profile / _save_name(source_ordinal))
        destination = identity(profile / _save_name(destination_ordinal))
        require_pair(source)
        destination_paths = (destination.path, destination.meta_path)
        if any(path.exists() or path.is_symlink() for path in destination_paths):
            raise SaveToolError(
                f"destination slot {destination_slot} is not empty: {destination.path}"
            )
        data = source.path.read_bytes()
        meta = source.meta_path.read_bytes()
        decoded = decode_bytes(data, source=str(source.path))
        info = inspect_meta_bytes(meta, source.path)
        if info.encrypted_slot != info.storage_slot:
            raise SaveToolError(f"metadata encryption slot mismatch for {source.meta_path}")
        if info.decompressed_size not in {decoded.decompressed_size, len(data)}:
            raise SaveToolError(f"metadata size does not match {source.path}")
        if info.compressed_size is not None and info.compressed_size != len(data):
            raise SaveToolError(f"metadata compressed size does not match {source.path}")
        entries.append(
            {
                "kind": kind,
                "source": source,
                "destination": destination,
                "data": data,
                "meta": meta,
                "destination_meta": rekey_meta(meta, source.path, destination.path),
                "data_sha256": sha256_file(source.path),
                "meta_sha256": sha256_file(source.meta_path),
                "data_mode": source.path.stat().st_mode & 0o777,
                "meta_mode": source.meta_path.stat().st_mode & 0o777,
            }
        )

    backup_root = _workspace() / "no-mans-sky/save-edit/backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_root / (
        f"slot-move-{source_slot}-{destination_slot}-{stamp}-{uuid.uuid4().hex[:8]}"
    )
    backup.mkdir(mode=0o700)
    installed: list[Path] = []
    manifest_entries = []
    try:
        for entry in entries:
            pair_backup = backup / f"slot-{source_slot}-{entry['kind']}"
            pair_backup.mkdir(mode=0o700)
            source = entry["source"]
            backup_save = pair_backup / source.path.name
            backup_meta = pair_backup / source.meta_path.name
            shutil.copy2(source.path, backup_save)
            shutil.copy2(source.meta_path, backup_meta)
            if (
                sha256_file(backup_save) != entry["data_sha256"]
                or sha256_file(backup_meta) != entry["meta_sha256"]
            ):
                raise SaveToolError(f"slot-move backup verification failed for {source.path}")
            entry["backup_save"] = backup_save
            entry["backup_meta"] = backup_meta
            destination = entry["destination"]
            manifest_entries.append(
                {
                    "kind": entry["kind"],
                    "source_save": str(source.path),
                    "destination_save": str(destination.path),
                    "original_data_sha256": entry["data_sha256"],
                    "original_meta_sha256": entry["meta_sha256"],
                    "installed_data_sha256": hashlib.sha256(entry["data"]).hexdigest(),
                    "installed_meta_sha256": hashlib.sha256(entry["destination_meta"]).hexdigest(),
                    "backup_directory": pair_backup.name,
                }
            )

        for entry in entries:
            source = entry["source"]
            if (
                sha256_file(source.path) != entry["data_sha256"]
                or sha256_file(source.meta_path) != entry["meta_sha256"]
            ):
                raise SaveToolError(f"source changed during slot-move backup: {source.path}")

        for entry in entries:
            destination = entry["destination"]
            _replace_bytes(entry["data"], destination.path, entry["data_mode"])
            installed.append(destination.path)
            _replace_bytes(entry["destination_meta"], destination.meta_path, entry["meta_mode"])
            installed.append(destination.meta_path)
            if (
                sha256_file(destination.path) != hashlib.sha256(entry["data"]).hexdigest()
                or sha256_file(destination.meta_path)
                != hashlib.sha256(entry["destination_meta"]).hexdigest()
            ):
                raise SaveToolError(
                    f"slot-move destination verification failed for {destination.path}"
                )
            decode_bytes(destination.path.read_bytes(), source=str(destination.path))
            info = inspect_meta_bytes(destination.meta_path.read_bytes(), destination.path)
            if info.encrypted_slot != info.storage_slot:
                raise SaveToolError(
                    f"slot-move metadata verification failed for {destination.meta_path}"
                )

        for entry in entries:
            source = entry["source"]
            source.path.unlink()
            source.meta_path.unlink()

        directory_fd = os.open(profile, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception as exc:
        rollback_errors = []
        for path in reversed(installed):
            try:
                path.unlink(missing_ok=True)
            except Exception as rollback_exc:  # pragma: no cover
                rollback_errors.append(f"{path}: {rollback_exc}")
        for entry in entries:
            source = entry["source"]
            for backup_key, target, mode_key in (
                ("backup_save", source.path, "data_mode"),
                ("backup_meta", source.meta_path, "meta_mode"),
            ):
                if not target.exists() and backup_key in entry:
                    try:
                        _copy_for_replace(entry[backup_key], target, entry[mode_key])
                    except Exception as rollback_exc:  # pragma: no cover
                        rollback_errors.append(f"{target}: {rollback_exc}")
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        raise SaveToolError(f"slot move failed; rollback attempted: {exc}{detail}") from exc

    for entry in entries:
        source = entry["source"]
        if source.path.exists() or source.meta_path.exists():
            raise SaveToolError(f"slot-move source removal failed for {source.path}")
    manifest = {
        "schema": "squinch-nms-save-slot-move-v1",
        "applied_at": datetime.now(UTC).isoformat(),
        "profile": str(profile),
        "source_slot": source_slot,
        "destination_slot": destination_slot,
        "entries": manifest_entries,
    }
    _write_new(backup / "manifest.json", manifest)
    return {
        "moved": True,
        "source_slot": source_slot,
        "destination_slot": destination_slot,
        "pairs": len(entries),
        "backup": str(backup),
        "manifest": str(backup / "manifest.json"),
    }
