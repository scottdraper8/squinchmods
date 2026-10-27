from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path, PurePosixPath

TRANCHE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
METADATA_NAME = ".tranche.json"
LOCK_NAME = ".lock"


class TrancheError(Exception):
    def __init__(self, code: str, message: str, **details: object):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def scratch_root(repository: Path) -> Path:
    return repository.resolve() / ".squinch" / "scratch" / "tranches"


def _validate_root(repository: Path, *, create: bool) -> Path:
    base = repository.resolve()
    root = scratch_root(base)
    current = base
    for part in root.relative_to(base).parts:
        current /= part
        if current.is_symlink():
            raise TrancheError(
                "unsafe_tranche", f"tranche ownership root contains a symbolic link: {current}"
            )
        if current.exists() and not current.is_dir():
            raise TrancheError(
                "unsafe_tranche", f"tranche ownership root is not a directory: {current}"
            )
        if create and not current.exists():
            current.mkdir()
    return root


def _validate_id(tranche_id: str) -> str:
    if TRANCHE_ID.fullmatch(tranche_id) is None:
        raise TrancheError(
            "invalid_tranche",
            "tranche ID must be 1-64 lowercase letters, digits, or hyphens",
            tranche=tranche_id,
        )
    return tranche_id


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_tranche(repository: Path, tranche_id: str) -> Path:
    root = _validate_root(repository, create=True)
    target = root / _validate_id(tranche_id)
    if os.path.lexists(target) and target.is_symlink():
        raise TrancheError("unsafe_tranche", "tranche ownership path is a symbolic link")
    try:
        target.mkdir()
    except FileExistsError as exc:
        raise TrancheError("tranche_exists", f"tranche already exists: {tranche_id}") from exc
    try:
        _atomic_json(
            target / METADATA_NAME,
            {
                "schema_version": 1,
                "tranche": tranche_id,
                "workspace": str(target),
            },
        )
        (target / LOCK_NAME).touch(exist_ok=False)
    except Exception:
        shutil.rmtree(target)
        raise
    return target


def _read_metadata(target: Path, tranche_id: str) -> dict:
    metadata_path = target / METADATA_NAME
    if target.is_symlink() or metadata_path.is_symlink() or not metadata_path.is_file():
        raise TrancheError("invalid_ownership", f"tranche metadata is missing or unsafe: {target}")
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrancheError(
            "invalid_ownership", f"tranche metadata is unreadable: {target}"
        ) from exc
    expected = {
        "schema_version": 1,
        "tranche": tranche_id,
        "workspace": str(target),
    }
    if value != expected:
        raise TrancheError("invalid_ownership", f"tranche metadata does not match: {target}")
    return value


def resolve_tranche(repository: Path, tranche_id: str, *, validate_owned: bool = False) -> Path:
    root = _validate_root(repository, create=False)
    target = root / _validate_id(tranche_id)
    if not target.is_dir() or target.is_symlink():
        raise TrancheError("tranche_not_found", f"tranche does not exist: {tranche_id}")
    _read_metadata(target, tranche_id)
    if target.resolve() != target:
        raise TrancheError("unsafe_tranche", f"tranche path is not canonical: {target}")
    if validate_owned:
        _validate_owned_tree(target)
    return target


@contextmanager
def _exclusive_lock(target: Path) -> Iterator[None]:
    lock_path = target / LOCK_NAME
    if lock_path.is_symlink() or not lock_path.is_file():
        raise TrancheError("invalid_ownership", f"tranche lock is missing or unsafe: {lock_path}")
    with lock_path.open("r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise TrancheError(
                "tranche_live", "a repository tool is still using this tranche"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _validate_owned_tree(root: Path) -> None:
    if os.path.ismount(root):
        raise TrancheError("unsafe_owned_path", f"tranche workspace is a mount point: {root}")
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                mode = entry.stat(follow_symlinks=False).st_mode
                path = Path(entry.path)
                if stat.S_ISLNK(mode):
                    raise TrancheError(
                        "unsafe_owned_path", f"tranche workspace contains a symbolic link: {path}"
                    )
                if stat.S_ISDIR(mode):
                    if os.path.ismount(path):
                        raise TrancheError(
                            "unsafe_owned_path",
                            f"tranche workspace contains a mount point: {path}",
                        )
                    pending.append(path)
                elif not stat.S_ISREG(mode):
                    raise TrancheError(
                        "unsafe_owned_path", f"tranche workspace contains a special file: {path}"
                    )


def _active_markers(target: Path) -> list[Path]:
    markers: list[Path] = []
    minecraft_active = target / "minecraft" / "investigate" / "active"
    if minecraft_active.is_dir() and not minecraft_active.is_symlink():
        markers.extend(path for path in minecraft_active.iterdir() if path.is_file())
    qa_active = target / "minecraft" / "qa" / "active.json"
    if qa_active.is_file():
        markers.append(qa_active)
    return sorted(markers)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    if not os.path.lexists(root):
        return {}
    if root.is_symlink() or not root.is_dir():
        raise TrancheError("unsafe_external_path", f"owned external path is unsafe: {root}")
    if os.path.ismount(root):
        raise TrancheError("unsafe_external_path", f"owned external path is a mount point: {root}")
    result: dict[str, str] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                mode = entry.stat(follow_symlinks=False).st_mode
                path = Path(entry.path)
                if stat.S_ISLNK(mode):
                    raise TrancheError(
                        "unsafe_external_path",
                        f"owned external path contains a symbolic link: {path}",
                    )
                if stat.S_ISDIR(mode):
                    if os.path.ismount(path):
                        raise TrancheError(
                            "unsafe_external_path",
                            f"owned external path contains a mount point: {path}",
                        )
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    result[path.relative_to(root).as_posix().casefold()] = _sha256_file(path)
                else:
                    raise TrancheError(
                        "unsafe_external_path",
                        f"owned external path contains a special file: {path}",
                    )
    return result


def _running_processes(name: str) -> list[int]:
    processes: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return processes
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            actual = (entry / "comm").read_text(encoding="utf-8", errors="replace").strip()
        except (OSError, PermissionError):
            continue
        if actual.casefold() == name.casefold():
            processes.append(int(entry.name))
    return sorted(processes)


def _nms_stage_manifests(target: Path) -> list[Path]:
    stages = target / "no-mans-sky" / "investigate" / "stages"
    if not stages.exists():
        return []
    if stages.is_symlink() or not stages.is_dir():
        raise TrancheError("unsafe_external_path", f"NMS stage metadata is unsafe: {stages}")
    return sorted(stages.glob("*.json"))


def _load_nms_stage(path: Path) -> tuple[dict, Path, Path]:
    if path.is_symlink() or not path.is_file():
        raise TrancheError("invalid_external_ownership", f"NMS stage metadata is unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrancheError(
            "invalid_external_ownership", f"NMS stage metadata is unreadable: {path}"
        ) from exc
    run_id = path.stem
    files = value.get("files")
    if (
        value.get("schema_version") != 2
        or value.get("run_id") != run_id
        or value.get("state") not in {"preparing", "ready", "active"}
        or not isinstance(files, dict)
        or any(
            not isinstance(name, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for name, digest in files.items()
        )
    ):
        raise TrancheError(
            "invalid_external_ownership", f"NMS stage metadata has invalid identity: {path}"
        )
    try:
        game_root = Path(value["game_root"])
        destination = Path(value["destination"])
        pending = Path(value["pending_destination"])
    except (KeyError, TypeError) as exc:
        raise TrancheError(
            "invalid_external_ownership", f"NMS stage metadata is incomplete: {path}"
        ) from exc
    if not game_root.is_absolute() or game_root.resolve() != game_root:
        raise TrancheError(
            "unsafe_external_path", f"NMS game root is not an absolute canonical path: {game_root}"
        )
    expected_destination = game_root / "GAMEDATA" / "MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    expected_pending = game_root / ".squinch-investigation-staging" / run_id
    if destination != expected_destination or pending != expected_pending:
        raise TrancheError(
            "unsafe_external_path", f"NMS stage paths do not match their ownership: {path}"
        )
    if game_root.is_symlink():
        raise TrancheError("unsafe_external_path", f"NMS game root is a symbolic link: {game_root}")
    normalized_names: set[str] = set()
    for name in files:
        logical = PurePosixPath(name)
        normalized = logical.as_posix().casefold()
        if (
            not name
            or logical.is_absolute()
            or ".." in logical.parts
            or normalized != name.casefold()
            or normalized in normalized_names
        ):
            raise TrancheError(
                "invalid_external_ownership",
                f"NMS stage metadata contains an unsafe file path: {path}",
            )
        normalized_names.add(normalized)
    for owned in (destination, pending):
        try:
            relative = owned.relative_to(game_root)
        except ValueError as exc:
            raise TrancheError(
                "unsafe_external_path", f"NMS stage path escapes the game root: {owned}"
            ) from exc
        current = game_root
        for part in relative.parts[:-1]:
            current /= part
            if current.is_symlink():
                raise TrancheError(
                    "unsafe_external_path",
                    f"NMS stage path has a symbolic-link ancestor: {current}",
                )
    return value, destination, pending


def _inspect_nms_stages(target: Path) -> list[dict]:
    records: list[dict] = []
    for manifest_path in _nms_stage_manifests(target):
        value, destination, pending = _load_nms_stage(manifest_path)
        expected = value["files"]
        for label, path in (("destination", destination), ("pending", pending)):
            current = _tree_hashes(path)
            if os.path.lexists(path) and current != expected:
                raise TrancheError(
                    "external_path_modified",
                    f"refusing to remove modified NMS {label}: {path}",
                    path=str(path),
                )
        records.append(
            {
                "run_id": value["run_id"],
                "manifest": str(manifest_path),
                "paths": [str(path) for path in (destination, pending) if os.path.lexists(path)],
            }
        )
    return records


def _remove_nms_stages(target: Path, records: list[dict]) -> None:
    current = _inspect_nms_stages(target)
    if current != records:
        raise TrancheError(
            "external_ownership_changed",
            "NMS stage ownership changed during tranche cleanup",
        )
    if records:
        running = _running_processes("NMS.exe")
        if running:
            raise TrancheError(
                "owned_process_live",
                "refusing tranche cleanup while NMS.exe is running",
                processes=running,
            )
    for record in records:
        manifest = Path(record["manifest"])
        _value, destination, pending = _load_nms_stage(manifest)
        for path in (destination, pending):
            if os.path.lexists(path):
                shutil.rmtree(path)
        manifest.unlink()
        with suppress(OSError):
            pending.parent.rmdir()


def clean_tranche(repository: Path, tranche_id: str, *, apply: bool = False) -> dict:
    root = _validate_root(repository, create=False)
    target = root / _validate_id(tranche_id)
    if not os.path.lexists(target):
        return {
            "action": "absent",
            "tranche": tranche_id,
            "workspace": str(target),
            "removed": False,
            "external": [],
        }
    target = resolve_tranche(repository, tranche_id)
    with _exclusive_lock(target):
        _validate_owned_tree(target)
        active = _active_markers(target)
        if active:
            raise TrancheError(
                "teardown_incomplete",
                "refusing to clean a tranche with incomplete owned work",
                paths=[str(path) for path in active],
            )
        external = _inspect_nms_stages(target)
        if external:
            running = _running_processes("NMS.exe")
            if running:
                raise TrancheError(
                    "owned_process_live",
                    "refusing tranche cleanup while NMS.exe is running",
                    processes=running,
                )
        result = {
            "action": "apply" if apply else "dry-run",
            "tranche": tranche_id,
            "workspace": str(target),
            "removed": False,
            "external": external,
        }
        if apply:
            _remove_nms_stages(target, external)
            shutil.rmtree(target)
            result["removed"] = True
        return result
