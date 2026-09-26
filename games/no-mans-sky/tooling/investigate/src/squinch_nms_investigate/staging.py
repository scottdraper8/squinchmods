from __future__ import annotations

import json
import secrets
import shutil
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from .errors import InvestigationError
from .game import running_processes
from .mods import inventory_mod, resolve_deployment_root
from .paths import STAGES_ROOT, sha256_file
from .runs import RUN_ID, resolve_run


def _manifest_path(run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise InvestigationError("invalid_run_id", f"Invalid run ID: {run_id}")
    return STAGES_ROOT / f"{run_id}.json"


def _write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}-{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    if not root.is_dir() or root.is_symlink():
        raise InvestigationError("unsafe_stage_tree", f"Stage tree is not a directory: {root}")
    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise InvestigationError("unsafe_stage_tree", f"Stage tree contains a symlink: {path}")
        if path.is_file():
            files[path.relative_to(root).as_posix().casefold()] = sha256_file(path)
        elif not path.is_dir():
            raise InvestigationError(
                "unsafe_stage_tree", f"Stage tree contains a special file: {path}"
            )
    return files


def _manifest_locations(manifest: dict, run_id: str) -> tuple[Path, Path]:
    try:
        game_root = Path(manifest["game_root"])
        destination = Path(manifest["destination"])
        pending = Path(manifest["pending_destination"])
    except (KeyError, TypeError) as exc:
        raise InvestigationError("invalid_stage_manifest", "Stage manifest is incomplete") from exc
    expected_destination = game_root / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    expected_pending = game_root / ".squinch-investigation-staging" / run_id
    if destination != expected_destination or pending != expected_pending:
        raise InvestigationError(
            "unsafe_stage_destination", "Stage manifest contains an unexpected destination"
        )
    _reject_symlink_ancestors(game_root, destination)
    _reject_symlink_ancestors(game_root, pending)
    return destination, pending


def _reject_symlink_ancestors(game_root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(game_root)
    except ValueError as exc:
        raise InvestigationError(
            "unsafe_stage_destination", f"Stage path escapes the game root: {target}"
        ) from exc
    current = game_root
    if current.is_symlink():
        raise InvestigationError(
            "unsafe_stage_destination", f"Game root is a symbolic link: {game_root}"
        )
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise InvestigationError(
                "unsafe_stage_destination", f"Stage path has a symbolic-link ancestor: {current}"
            )


def _load_manifest(path: Path, run_id: str) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvestigationError(
            "invalid_stage_manifest", f"Stage manifest cannot be read: {path}"
        ) from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 2
        or manifest.get("run_id") != run_id
        or manifest.get("state") not in {"preparing", "ready", "active"}
    ):
        raise InvestigationError(
            "invalid_stage_manifest", f"Stage manifest identity or schema is invalid: {path}"
        )
    files = manifest.get("files")
    if not isinstance(files, dict) or any(
        not isinstance(name, str)
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        for name, digest in files.items()
    ):
        raise InvestigationError(
            "invalid_stage_manifest", f"Stage manifest file hashes are invalid: {path}"
        )
    _manifest_locations(manifest, run_id)
    return manifest


def _remove_empty_pending_parent(pending: Path) -> None:
    with suppress(OSError):
        pending.parent.rmdir()


def stage(mod_root: Path, game_root: Path, run_id: str, *, apply: bool) -> dict:
    deployment = resolve_deployment_root(mod_root)
    source_files = inventory_mod(deployment)
    destination = game_root / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    result = {
        "apply": apply,
        "source": str(deployment),
        "destination": str(destination),
        "file_count": len(source_files),
        "disablemods_present": (game_root / "GAMEDATA/PCBANKS/DISABLEMODS.TXT").exists(),
        "launch_performed": False,
    }
    if not apply:
        return result
    processes = running_processes()
    if processes:
        raise InvestigationError(
            "game_running", "Refusing to stage files while NMS.exe is running", processes=processes
        )
    if destination.exists() or destination.is_symlink():
        raise InvestigationError(
            "stage_destination_exists", f"Stage destination already exists: {destination}"
        )
    manifest_path = _manifest_path(run_id)
    if manifest_path.exists():
        raise InvestigationError(
            "stage_manifest_exists", f"Stage manifest already exists: {manifest_path}"
        )
    pending = game_root / ".squinch-investigation-staging" / run_id
    _reject_symlink_ancestors(game_root, destination)
    _reject_symlink_ancestors(game_root, pending)
    if pending.exists() or pending.is_symlink():
        raise InvestigationError(
            "stage_pending_exists", f"Pending stage destination already exists: {pending}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = {item["logical_path"]: item["sha256"] for item in source_files}
    manifest = {
        "schema_version": 2,
        "state": "preparing",
        "run_id": run_id,
        "game_root": str(game_root),
        "source": str(deployment),
        "destination": str(destination),
        "pending_destination": str(pending),
        "files": expected,
    }
    _write_manifest(manifest_path, manifest)
    try:
        pending.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(deployment, pending, symlinks=False)
        deployed = inventory_mod(pending)
        actual = {item["logical_path"]: item["sha256"] for item in deployed}
        if actual != expected:
            raise InvestigationError(
                "stage_copy_mismatch", "Staged files did not hash-match their source"
            )
        manifest["state"] = "ready"
        _write_manifest(manifest_path, manifest)
        pending.replace(destination)
        manifest["state"] = "active"
        _write_manifest(manifest_path, manifest)
    except Exception as exc:
        for owned in (destination, pending):
            if owned.is_dir() and not owned.is_symlink():
                current = _tree_hashes(owned)
                if not set(current) - set(expected) and all(
                    current[path] == expected[path] for path in current
                ):
                    shutil.rmtree(owned)
        remaining = [str(path) for path in (destination, pending) if path.exists()]
        if remaining:
            raise InvestigationError(
                "stage_rollback_incomplete",
                "Stage failed and an owned tree could not be safely rolled back",
                paths=remaining,
            ) from exc
        manifest_path.unlink(missing_ok=True)
        _remove_empty_pending_parent(pending)
        raise
    _remove_empty_pending_parent(pending)
    result["manifest"] = str(manifest_path)
    return result


def collect_evidence(run_id: str, screenshots: list[Path]) -> dict:
    status = stage_status(run_id)
    if not status["staged"] or not status.get("content_matches"):
        raise InvestigationError(
            "stage_not_ready",
            "Runtime evidence requires an intact, active owned stage",
            status=status,
        )
    if running_processes():
        raise InvestigationError(
            "game_running", "Stop NMS.exe before collecting a complete runtime evidence snapshot"
        )
    manifest_path = _manifest_path(run_id)
    manifest = _load_manifest(manifest_path, run_id)
    game_root = Path(manifest["game_root"])
    run_path = resolve_run(run_id)
    collection_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = run_path / "runtime-evidence" / collection_id
    if destination.exists():
        raise InvestigationError(
            "collection_exists", f"Runtime evidence collection already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    sources: list[tuple[str, Path]] = [
        ("FullLog.txt", game_root / "GAMEDATA/FullLog.txt"),
        (
            "GCMODSETTINGS.MXML",
            game_root / "Binaries/SETTINGS/GCMODSETTINGS.MXML",
        ),
    ]
    exported = game_root / "GAMEDATA/MODS/EXPORTED"
    if exported.is_dir() and not exported.is_symlink():
        for path in sorted(exported.rglob("*")):
            if path.is_symlink():
                raise InvestigationError(
                    "unsafe_evidence_source", f"Exported metadata contains a symlink: {path}"
                )
            if path.is_file():
                sources.append((f"EXPORTED/{path.relative_to(exported).as_posix()}", path))
            elif not path.is_dir():
                raise InvestigationError(
                    "unsafe_evidence_source", f"Exported metadata contains a special file: {path}"
                )
    for index, screenshot in enumerate(screenshots):
        path = screenshot.expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "invalid_screenshot", f"Screenshot is not a regular file: {path}"
            )
        sources.append((f"screenshots/{index:03d}-{path.name}", path))
    with tempfile.TemporaryDirectory(prefix=f".{collection_id}-", dir=destination.parent) as temp:
        payload = Path(temp) / "payload"
        payload.mkdir()
        records: list[dict] = []
        for relative, source in sources:
            if not source.exists():
                continue
            if not source.is_file() or source.is_symlink():
                raise InvestigationError(
                    "unsafe_evidence_source", f"Evidence source is not a regular file: {source}"
                )
            target = payload.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            records.append(
                {
                    "source": str(source),
                    "path": str(destination / relative),
                    "bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                }
            )
        if not records:
            raise InvestigationError(
                "no_runtime_evidence",
                "No FullLog, mod settings, exported metadata, or screenshots exist",
            )
        result = {
            "schema_version": 1,
            "run_id": run_id,
            "collection_id": collection_id,
            "game_root": str(game_root),
            "stage_status": status,
            "files": records,
        }
        (payload / "collection.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        payload.replace(destination)
    result["artifact_path"] = str(destination)
    return result


def stage_status(run_id: str) -> dict:
    manifest_path = _manifest_path(run_id)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return {"run_id": run_id, "staged": False}
    manifest = _load_manifest(manifest_path, run_id)
    destination, pending = _manifest_locations(manifest, run_id)
    current = _tree_hashes(destination)
    pending_current = _tree_hashes(pending)
    try:
        expected = manifest["files"]
    except KeyError as exc:
        raise InvestigationError(
            "invalid_stage_manifest", "Stage manifest has no file set"
        ) from exc
    return {
        "run_id": run_id,
        "staged": destination.is_dir(),
        "manifest_state": manifest.get("state"),
        "destination": str(destination),
        "pending_destination": str(pending),
        "pending": pending.is_dir(),
        "content_matches": current == expected,
        "missing": sorted(set(expected) - set(current)),
        "extra": sorted(set(current) - set(expected)),
        "changed": sorted(
            path for path in set(current) & set(expected) if current[path] != expected[path]
        ),
        "pending_missing": sorted(set(expected) - set(pending_current)),
        "pending_extra": sorted(set(pending_current) - set(expected)),
        "pending_changed": sorted(
            path
            for path in set(pending_current) & set(expected)
            if pending_current[path] != expected[path]
        ),
    }


def unstage(run_id: str, *, apply: bool) -> dict:
    status = stage_status(run_id)
    result = {**status, "apply": apply}
    if not apply:
        return result
    manifest_path = _manifest_path(run_id)
    if not status["staged"]:
        if manifest_path.is_file() and not manifest_path.is_symlink():
            manifest = _load_manifest(manifest_path, run_id)
            destination, pending = _manifest_locations(manifest, run_id)
            if destination.exists() or destination.is_symlink():
                raise InvestigationError(
                    "unsafe_stage_destination",
                    f"Refusing unsafe pending-stage cleanup: {destination}",
                )
            if pending.exists() or pending.is_symlink():
                if (
                    status["pending_extra"]
                    or status["pending_changed"]
                    or not pending.is_dir()
                    or pending.is_symlink()
                ):
                    raise InvestigationError(
                        "stage_modified",
                        "Refusing to remove a pending staged tree whose content changed",
                        status=status,
                    )
                shutil.rmtree(pending)
                _remove_empty_pending_parent(pending)
            manifest_path.unlink()
            result["removed_manifest"] = True
        return result
    if running_processes():
        raise InvestigationError(
            "game_running", "Refusing to unstage files while NMS.exe is running"
        )
    if not status["content_matches"]:
        raise InvestigationError(
            "stage_modified",
            "Refusing to remove a staged tree whose content changed",
            status=status,
        )
    manifest = _load_manifest(manifest_path, run_id)
    destination, pending = _manifest_locations(manifest, run_id)
    if destination.is_symlink():
        raise InvestigationError(
            "unsafe_stage_destination", f"Refusing unsafe stage removal: {destination}"
        )
    shutil.rmtree(destination)
    manifest_path.unlink()
    _remove_empty_pending_parent(pending)
    result["removed"] = True
    return result
