from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import time
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .errors import CleanupError, InvestigationError
from .catalog import ResolvedArtifact
from .output import timestamp
from .paths import (
    ENV_SH,
    PROBE_OVERLAY,
    PROBE_RUNTIME_ROOT,
    RUNS_ROOT,
    active_path,
    lock_path,
    validate_loader,
)
from .processes import (
    descendants,
    free_port,
    group_members,
    identity_matches,
    listener_owners,
    port_is_available,
    port_is_free,
    proc_identity,
    signal_recorded_process,
    signal_validated_group,
)
from .rcon import RconError, execute
from .state import atomic_write_json, project_lock, read_json

OWNERSHIP = "squinch-minecraft-investigate"


def new_run_id() -> str:
    prefix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def sourced_environment() -> dict[str, str]:
    try:
        result = subprocess.run(
            ["bash", "-c", 'source "$1" && env -0', "squinch-env", str(ENV_SH)],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise InvestigationError(
            "environment_failed", f"failed to source {ENV_SH}"
        ) from exc
    environment: dict[str, str] = {}
    for entry in result.stdout.split(b"\x00"):
        if not entry:
            continue
        key, separator, value = entry.partition(b"=")
        if separator:
            environment[key.decode(errors="replace")] = value.decode(errors="replace")
    return environment


def _backup_file(path: Path, artifact_dir: Path) -> dict:
    record = {"path": str(path), "existed": path.exists(), "backup": None}
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "unsafe_managed_file", f"refusing to replace non-regular file: {path}"
            )
        backup = artifact_dir / "managed-files" / path.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
        record["backup"] = str(backup)
    return record


def _restore_managed_files(state: dict) -> list[str]:
    failures: list[str] = []
    allowed_paths = None
    if "run_dir" in state:
        run_dir = Path(state["run_dir"])
        allowed_paths = {run_dir / "eula.txt", run_dir / "server.properties"}
    for record in state.get("managed_files", []):
        path = Path(record["path"])
        try:
            if allowed_paths is not None and path not in allowed_paths:
                raise ValueError("managed path is outside the recorded file set")
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("managed target is not a regular file")
            if record["existed"]:
                backup = Path(record["backup"])
                if "artifact_dir" in state:
                    expected = Path(state["artifact_dir"]) / "managed-files" / path.name
                    if backup != expected:
                        raise ValueError("managed backup is outside the artifact directory")
                if backup.is_symlink() or not backup.is_file():
                    raise FileNotFoundError(f"backup missing: {backup}")
                shutil.copy2(backup, path)
            else:
                path.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            failures.append(f"{path}: {exc}")
    return failures


def _remove_protocol_files(state: dict) -> list[str]:
    failures: list[str] = []
    root = Path(state["run_dir"]) / ".squinch-investigate"
    if not root.exists():
        return failures
    if root.is_symlink() or not root.is_dir():
        return [f"{root}: protocol root is not a regular directory"]
    allowed_directories = {root / "requests", root / "processing", root / "results"}
    candidates: list[Path] = []
    for directory in allowed_directories:
        if directory.exists():
            if directory.is_symlink() or not directory.is_dir():
                failures.append(f"{directory}: protocol child is not a regular directory")
                continue
            candidates.extend(sorted(directory.iterdir()))
    for path in candidates:
        try:
            relative = path.relative_to(root)
            if len(relative.parts) != 2 or root / relative.parts[0] not in allowed_directories:
                raise ValueError("unexpected protocol path shape")
            if path.is_symlink() or not path.is_file():
                raise ValueError("protocol target is not a regular file")
            if path.name.endswith(".json"):
                payload = read_json(path)
                payloads = [payload]
            elif ".jsonl" in path.name:
                payloads = [
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if not payloads:
                    raise ValueError("empty protocol transcript")
            else:
                raise ValueError("unexpected protocol filename")
            if any(payload.get("run_id") != state["run_id"] for payload in payloads):
                raise ValueError("protocol run identity does not match")
            path.unlink()
        except (OSError, ValueError, InvestigationError, json.JSONDecodeError) as exc:
            failures.append(f"{path}: {exc}")
    for directory in (*allowed_directories, root):
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            # A non-empty protocol directory can contain another run's active files.
            pass
    return failures


def _git_status(project: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain=v2", "-z", "--untracked-files=no"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def _probe_pack_details(root: Path) -> dict:
    resolved = root.expanduser().resolve()
    manifest = resolved / "probe-pack.toml"
    if not manifest.is_file():
        raise InvestigationError(
            "probe_pack_invalid", f"probe pack manifest is missing: {manifest}"
        )
    try:
        value = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InvestigationError(
            "probe_pack_invalid", f"cannot read probe pack manifest {manifest}: {exc}"
        ) from exc
    if value.get("schema_version") != 1:
        raise InvestigationError("probe_pack_invalid", f"unsupported probe pack: {manifest}")
    pack_id = value.get("id")
    if not isinstance(pack_id, str) or not pack_id:
        raise InvestigationError("probe_pack_invalid", f"probe pack id is missing: {manifest}")
    sources = value.get("sources", [])
    resources = value.get("resources", [])
    mixins = value.get("mixins", [])
    if not all(
        isinstance(items, list) and all(isinstance(item, str) and item for item in items)
        for items in (sources, resources, mixins)
    ):
        raise InvestigationError(
            "probe_pack_invalid", f"sources, resources, and mixins must be string arrays: {manifest}"
        )
    source_paths = [(resolved / item).resolve() for item in sources]
    resource_paths = [(resolved / item).resolve() for item in resources]
    paths = [*source_paths, *resource_paths]
    if any(path != resolved and resolved not in path.parents for path in paths):
        raise InvestigationError("probe_pack_invalid", f"probe pack path escapes its root: {manifest}")
    missing = next((path for path in paths if not path.is_dir()), None)
    if missing is not None:
        raise InvestigationError("probe_pack_invalid", f"probe pack input is missing: {missing}")
    input_files = []
    content = hashlib.sha256()
    for path in sorted(
        item for directory in paths for item in directory.rglob("*") if item.is_file()
    ):
        relative = path.relative_to(resolved).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        content.update(relative.encode())
        content.update(file_hash.encode())
        input_files.append(
            {"path": relative, "sha256": file_hash, "size": path.stat().st_size}
        )
    return {
        "id": pack_id,
        "version": str(value.get("version", "")),
        "root": str(resolved),
        "manifest": str(manifest),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "content_sha256": content.hexdigest(),
        "inputs": input_files,
        "sources": [str(path) for path in source_paths],
        "resources": [str(path) for path in resource_paths],
        "mixins": mixins,
        "capabilities": value.get("capabilities", []),
    }


def _probe_overlay_command(loader: str, probe_packs: tuple[Path, ...] = ()) -> tuple[list[str], dict]:
    if loader not in {"fabric", "neoforge"}:
        raise InvestigationError(
            "probe_overlay_unsupported", f"the probe overlay does not support loader {loader!r}"
        )
    missing = next((path for path in (PROBE_OVERLAY,) if not path.is_file()), None)
    if missing is not None:
        raise InvestigationError("probe_overlay_missing", f"probe overlay input is missing: {missing}")
    packs = [_probe_pack_details(PROBE_RUNTIME_ROOT)]
    packs.extend(_probe_pack_details(path) for path in probe_packs)
    pack_ids = [pack["id"] for pack in packs]
    if len(pack_ids) != len(set(pack_ids)):
        raise InvestigationError("probe_pack_invalid", "probe pack IDs must be unique")
    mixins = list(dict.fromkeys(mixin for pack in packs for mixin in pack["mixins"]))
    details = {
        "overlay": str(PROBE_OVERLAY),
        "runtime": str(PROBE_RUNTIME_ROOT),
        "manifest": packs[0]["manifest"],
        "manifest_sha256": packs[0]["manifest_sha256"],
        "packs": packs,
        "mixins": mixins,
        "sentinel": "SQUINCH_DEVELOPMENT_PROBE",
    }
    arguments = [
        "--init-script",
        str(PROBE_OVERLAY),
        f"-PsquinchProbeRuntime={PROBE_RUNTIME_ROOT}",
        f"-PsquinchProbeLoader={loader}",
        f"-PsquinchProbePacksJson={json.dumps(packs, separators=(',', ':'))}",
        f"-PsquinchProbeMixinsJson={json.dumps(mixins, separators=(',', ':'))}",
    ]
    return arguments, details


def _property_text(properties: dict[str, str]) -> str:
    for key, value in properties.items():
        if not key or "=" in key or any(character in key for character in "\r\n"):
            raise InvestigationError("invalid_property", f"invalid server property key: {key!r}")
        if any(character in str(value) for character in "\r\n"):
            raise InvestigationError(
                "invalid_property", f"server property {key!r} contains a newline"
            )
    return "".join(f"{key}={value}\n" for key, value in sorted(properties.items()))


def load_active(project: Path, loader: str) -> dict:
    expected_active = active_path(project, loader)
    state = read_json(expected_active)
    if state.get("ownership") != OWNERSHIP:
        raise InvestigationError("invalid_state", "active state has unknown ownership")
    if Path(state.get("project", "")) != project or state.get("loader") != loader:
        raise InvestigationError("invalid_state", "active state identity does not match request")
    run_id = state.get("run_id")
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id:
        raise InvestigationError("invalid_state", "active state has an invalid run ID")
    expected_artifact = RUNS_ROOT / run_id
    expected_run_dir = project / loader / "run"
    expected_level_name = f"squinch-{run_id.lower()}"
    expected_world = expected_run_dir / expected_level_name
    expected_paths = {
        "active_path": expected_active,
        "artifact_dir": expected_artifact,
        "log_path": expected_artifact / "server.log",
        "run_dir": expected_run_dir,
        "world_dir": expected_world,
    }
    for field, expected in expected_paths.items():
        if Path(state.get(field, "")) != expected:
            raise InvestigationError(
                "invalid_state", f"active state {field} is outside its owned path"
            )
    if state.get("level_name") != expected_level_name:
        raise InvestigationError("invalid_state", "active state level name is invalid")
    if state.get("retention") not in {"discard", "keep-on-failure", "keep"}:
        raise InvestigationError("invalid_state", "active state retention is invalid")
    return state


def _write_manifest(state: dict) -> None:
    atomic_write_json(Path(state["artifact_dir"]) / "manifest.json", state)


def _write_active(state: dict) -> None:
    atomic_write_json(Path(state["active_path"]), state)
    _write_manifest(state)


def _record_command(state: dict, command: str, response: str | None = None) -> None:
    stream = Path(state["artifact_dir"]) / "commands.jsonl"
    event = {"timestamp": timestamp(), "command": command, "response": response}
    with stream.open("a", encoding="utf-8") as output:
        output.write(json.dumps(event, sort_keys=True) + "\n")


def persist_active(state: dict) -> None:
    """Persist a mutation to the currently owned active state and run manifest."""
    _write_active(state)


def _refresh_owned_processes(state: dict) -> list[dict]:
    recorded = {int(item["pid"]): item for item in state.get("owned_processes", [])}
    discovered = descendants(list(recorded.values()))
    for member in group_members(int(state["process"]["pgrp"])):
        if member["start_ticks"] >= int(state["process"]["start_ticks"]):
            discovered.append(member)
    for identity in discovered:
        recorded[identity["pid"]] = identity
    state["owned_processes"] = sorted(recorded.values(), key=lambda value: value["pid"])
    return [item for item in state["owned_processes"] if identity_matches(item)]


def _signal_owned_processes(state: dict, sig: signal.Signals) -> None:
    pgrp = int(state["process"]["pgrp"])
    signal_validated_group(state, sig)
    for expected in state.get("owned_processes", []):
        if int(expected["pgrp"]) == pgrp:
            continue
        with contextlib.suppress(ProcessLookupError):
            signal_recorded_process(expected, sig)


def _wait_owned_exit(state: dict, timeout: float, *, signal_new: signal.Signals | None = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        before = len(state.get("owned_processes", []))
        live = _refresh_owned_processes(state)
        if len(state["owned_processes"]) != before:
            _write_active(state)
            if signal_new is not None:
                _signal_owned_processes(state, signal_new)
        if not live:
            return True
        time.sleep(0.2)
    return not _refresh_owned_processes(state)


def _wait_graceful_server_exit(state: dict, timeout: float) -> bool:
    """Wait for Minecraft saves/listeners, but not a stale wrapper after all listeners close."""
    deadline = time.monotonic() + timeout
    listener_free_since: float | None = None
    while time.monotonic() < deadline:
        before = len(state.get("owned_processes", []))
        live = _refresh_owned_processes(state)
        if len(state["owned_processes"]) != before:
            _write_active(state)
        if not live:
            return True
        bound = [
            int(port) for port in state["ports"].values() if not port_is_free(int(port))
        ]
        if bound:
            listener_free_since = None
        elif listener_free_since is None:
            listener_free_since = time.monotonic()
        elif time.monotonic() - listener_free_since >= 5.0:
            # Minecraft no longer owns either listener and has had a short process-exit grace.
            # Let the validated TERM/KILL path handle a lingering Gradle boundary.
            return False
        time.sleep(0.2)
    return not _refresh_owned_processes(state)


def start_server(
    project: Path,
    loader: str,
    *,
    seed: str | None,
    datapacks: list[Path],
    companion_artifacts: list[ResolvedArtifact] | None = None,
    properties: dict[str, str],
    timeout: float,
    retention: str,
    probe_packs: tuple[Path, ...] = (),
    server_port: int | None = None,
    rcon_port: int | None = None,
) -> dict:
    startup_started = time.monotonic()
    loader_dir = validate_loader(project, loader)
    overlay_arguments, overlay_details = _probe_overlay_command(loader, probe_packs)
    tracked_status_before = _git_status(project)
    active = active_path(project, loader)
    with project_lock(lock_path(project, loader)):
        if active.exists():
            existing = load_active(project, loader)
            if identity_matches(existing["process"]) or group_members(
                int(existing["process"]["pgrp"])
            ):
                raise InvestigationError(
                    "already_active",
                    f"an investigation is already active for {project}/{loader}",
                    details={"run_id": existing["run_id"], "state": str(active)},
                )
            raise InvestigationError(
                "recovery_required",
                f"stale or incompletely cleaned state requires doctor --recover: {active}",
            )

        run_id = new_run_id()
        artifact_dir = RUNS_ROOT / run_id
        run_dir = loader_dir / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        level_name = f"squinch-{run_id.lower()}"
        world_dir = run_dir / level_name
        log_path = artifact_dir / "server.log"
        chosen_server_port = server_port or free_port()
        chosen_rcon_port = rcon_port or free_port()
        if chosen_server_port == chosen_rcon_port:
            chosen_rcon_port = free_port()
        for port in (chosen_server_port, chosen_rcon_port):
            if not port_is_available(port):
                raise InvestigationError("port_in_use", f"port is already bound: {port}")

        password = secrets.token_hex(24)
        effective_properties = {
            "enable-rcon": "true",
            "level-name": level_name,
            "online-mode": "false",
            "rcon.password": password,
            "rcon.port": str(chosen_rcon_port),
            "server-port": str(chosen_server_port),
            "spawn-protection": "0",
        }
        if seed is not None:
            effective_properties["level-seed"] = seed
        effective_properties.update(properties)
        # Ownership-critical settings cannot be overridden by arbitrary properties.
        effective_properties.update(
            {
                "enable-rcon": "true",
                "level-name": level_name,
                "rcon.password": password,
                "rcon.port": str(chosen_rcon_port),
                "server-port": str(chosen_server_port),
            }
        )
        property_text = _property_text(effective_properties)
        resolved_datapacks = [source.expanduser().resolve() for source in datapacks]
        missing = [source for source in resolved_datapacks if not source.is_file()]
        if missing:
            raise InvestigationError("datapack_not_found", f"datapack not found: {missing[0]}")
        names = [source.name for source in resolved_datapacks]
        if len(names) != len(set(names)):
            raise InvestigationError("duplicate_datapack", "two datapacks have the same filename")

        artifact_dir.mkdir(parents=True, exist_ok=False)
        managed_files = [
            _backup_file(run_dir / "eula.txt", artifact_dir),
            _backup_file(run_dir / "server.properties", artifact_dir),
        ]
        try:
            (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            (run_dir / "server.properties").write_text(property_text, encoding="utf-8")
            if resolved_datapacks:
                target_dir = world_dir / "datapacks"
                target_dir.mkdir(parents=True, exist_ok=False)
                for source in resolved_datapacks:
                    shutil.copy2(source, target_dir / source.name)
            installed_companion_artifacts: list[dict[str, str]] = []
            if companion_artifacts:
                mods_dir = run_dir / "mods"
                mods_dir.mkdir(parents=True, exist_ok=True)
                for artifact in companion_artifacts:
                    source = artifact.path
                    target = mods_dir / artifact.filename
                    if target.exists():
                        raise InvestigationError(
                            "companion_artifact_conflict",
                            f"companion artifact target already exists: {target}",
                        )
                    shutil.copy2(source, target)
                    installed_companion_artifacts.append({
                        "id": artifact.id,
                        "source_path": str(source),
                        "materialized_path": str(target),
                        "sha256": artifact.sha256,
                    })
        except BaseException:
            for artifact in installed_companion_artifacts:
                with contextlib.suppress(FileNotFoundError):
                    Path(artifact["materialized_path"]).unlink()
            _restore_managed_files(
                {
                    "run_dir": str(run_dir),
                    "artifact_dir": str(artifact_dir),
                    "managed_files": managed_files,
                }
            )
            if world_dir.exists() and world_dir.is_dir() and not world_dir.is_symlink():
                shutil.rmtree(world_dir)
            raise

        command = [
            "bash",
            "./gradlew",
            f":{loader}:runServer",
            "--console=plain",
            "--no-daemon",
            *overlay_arguments,
        ]
        started_at = timestamp()
        process: subprocess.Popen[bytes] | None = None
        try:
            with log_path.open("wb") as log_file:
                process = subprocess.Popen(
                    command,
                    cwd=project,
                    env=sourced_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            identity = proc_identity(process.pid)
            if identity is None:
                raise InvestigationError(
                    "process_identity_unavailable",
                    f"could not read identity for launched process {process.pid}",
                )
            state = {
                "ownership": OWNERSHIP,
                "schema_version": 1,
                "run_id": run_id,
                "lifecycle": "starting",
                "started_at": started_at,
                "finished_at": None,
                "project": str(project),
                "loader": loader,
                "level_name": level_name,
                "world_dir": str(world_dir),
                "run_dir": str(run_dir),
                "artifact_dir": str(artifact_dir),
                "log_path": str(log_path),
                "active_path": str(active),
                "retention": retention,
                "ports": {"server": chosen_server_port, "rcon": chosen_rcon_port},
                "rcon": {"host": "127.0.0.1", "password": password},
                "process": identity,
                "owned_processes": [identity],
                "managed_files": managed_files,
                "command": command,
                "effective_properties": effective_properties,
                "datapacks": [str(path.expanduser().resolve()) for path in datapacks],
                "companion_artifacts": installed_companion_artifacts,
                "probe_overlay": {
                    **overlay_details,
                    "tracked_status_before": tracked_status_before,
                    "tracked_status_after_build": None,
                    "tracked_source_unchanged": None,
                },
                "protocol_root": str(run_dir / ".squinch-investigate"),
                "forceload_regions": [],
                "protocol_files": [],
                "cleanup": {"complete": False, "failures": []},
            }
            # Provisional state is durable immediately after launch, before readiness.
            _write_active(state)
        except BaseException:
            # If launch failed before state became durable, restore the files directly.
            if process is not None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=5)
            for artifact in installed_companion_artifacts:
                with contextlib.suppress(FileNotFoundError):
                    Path(artifact["materialized_path"]).unlink()
            provisional = {
                "run_dir": str(run_dir),
                "artifact_dir": str(artifact_dir),
                "managed_files": managed_files,
            }
            _restore_managed_files(provisional)
            if world_dir.exists() and world_dir.is_dir() and not world_dir.is_symlink():
                shutil.rmtree(world_dir)
            raise

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            before = len(state["owned_processes"])
            _refresh_owned_processes(state)
            if len(state["owned_processes"]) != before:
                _write_active(state)
            if process.poll() is not None:
                raise InvestigationError(
                    "startup_exited",
                    f"server process exited with code {process.returncode} before RCON readiness",
                    details={"log_path": str(log_path)},
                )
            try:
                execute(
                    "127.0.0.1",
                    chosen_rcon_port,
                    password,
                    ["list"],
                    timeout=min(2.0, max(0.2, deadline - time.monotonic())),
                )
                break
            except RconError:
                time.sleep(0.5)
        else:
            raise InvestigationError(
                "startup_timeout",
                f"server did not authenticate over RCON within {timeout:g}s",
                details={"log_path": str(log_path)},
            )

        owned = {item["pid"]: item for item in state["owned_processes"]}
        for item in _refresh_owned_processes(state):
            owned[item["pid"]] = item
        for port in (chosen_server_port, chosen_rcon_port):
            for owner in listener_owners(port):
                owned[owner["pid"]] = owner
        state["owned_processes"] = list(owned.values())
        state["lifecycle"] = "ready"
        state["ready_at"] = timestamp()
        state.setdefault("timings", {})["startup_seconds"] = time.monotonic() - startup_started
        tracked_status_after = _git_status(project)
        state["probe_overlay"]["tracked_status_after_build"] = tracked_status_after
        state["probe_overlay"]["tracked_source_unchanged"] = (
            tracked_status_before == tracked_status_after
        )
        _write_active(state)
        if tracked_status_before != tracked_status_after:
            raise InvestigationError(
                "probe_overlay_modified_worktree",
                "probe-overlay build changed the target worktree status",
                details={
                    "before": tracked_status_before,
                    "after": tracked_status_after,
                    "overlay": str(PROBE_OVERLAY),
                },
            )
        return state
    except BaseException as original:
        state["lifecycle"] = "startup_failed"
        state["failure"] = str(original)
        _write_active(state)
        try:
            stop_server(project, loader, successful=False, timeout=15.0)
        except InvestigationError as cleanup:
            raise CleanupError(
                f"startup failed and cleanup was incomplete: {original}",
                details={
                    "startup_error": str(original),
                    "cleanup_error": str(cleanup),
                    "run_id": run_id,
                    "artifact_dir": str(artifact_dir),
                    "log_path": str(log_path),
                    "cleanup_complete": False,
                },
            ) from original
        if isinstance(original, InvestigationError):
            original.details.update(
                {
                    "run_id": run_id,
                    "artifact_dir": str(artifact_dir),
                    "log_path": str(log_path),
                    "cleanup_complete": True,
                }
            )
        raise


def run_commands(state: dict, commands: list[str], timeout: float) -> list[dict]:
    responses = execute(
        state["rcon"]["host"],
        int(state["ports"]["rcon"]),
        state["rcon"]["password"],
        commands,
        timeout=timeout,
    )
    values: list[dict] = []
    for command, response in zip(commands, responses, strict=True):
        _record_command(state, command, response)
        values.append({"command": command, "response": response})
    return values


def _cleanup_world(state: dict, successful: bool) -> str | None:
    retention = state["retention"]
    keep = retention == "keep" or (retention == "keep-on-failure" and not successful)
    world = Path(state["world_dir"])
    run_dir = Path(state["run_dir"])
    if world.parent != run_dir:
        raise CleanupError(f"world is outside its recorded run directory: {world}")
    if world.name != state["level_name"] or not world.name.startswith("squinch-"):
        raise CleanupError(f"world ownership validation failed: {world}")
    if keep or not world.exists():
        return str(world) if world.exists() else None
    if world.is_symlink() or not world.is_dir():
        raise CleanupError(f"refusing to recursively remove non-directory world: {world}")
    shutil.rmtree(world)
    return None


def stop_server(
    project: Path, loader: str, *, successful: bool, timeout: float
) -> dict:
    active = active_path(project, loader)
    with project_lock(lock_path(project, loader)):
        cleanup_started = time.monotonic()
        state = load_active(project, loader)
        if state["lifecycle"] == "starting":
            raise InvestigationError(
                "startup_in_progress",
                "server startup is still owned by the launching command",
            )
        was_ready = state["lifecycle"] == "ready"
        state["lifecycle"] = "stopping"
        _write_active(state)
        failures: list[str] = []
        diagnostics: list[str] = []
        for region in reversed(state.get("forceload_regions", [])):
            command = (
                f"forceload remove {region['block_min_x']} {region['block_min_z']} "
                f"{region['block_max_x']} {region['block_max_z']}"
            )
            try:
                run_commands(state, [command], min(timeout, 10.0))
            except InvestigationError as exc:
                failures.append(f"owned forceload removal: {exc}")
        save_started = time.monotonic()
        if was_ready:
            try:
                run_commands(state, ["save-all flush"], min(timeout, 30.0))
            except InvestigationError as exc:
                failures.append(f"world save: {exc}")
        state.setdefault("timings", {})["save_seconds"] = time.monotonic() - save_started
        shutdown_started = time.monotonic()
        rcon_stop_sent = False
        try:
            run_commands(state, ["stop"], min(timeout, 10.0))
            rcon_stop_sent = True
        except InvestigationError as exc:
            # The server often closes RCON before replying to `stop`. Process and
            # socket ownership checks below decide whether cleanup really failed.
            diagnostics.append(f"RCON stop: {exc}")

        pgrp = int(state["process"]["pgrp"])
        _refresh_owned_processes(state)
        graceful = rcon_stop_sent and _wait_graceful_server_exit(state, timeout)
        if not graceful:
            try:
                _signal_owned_processes(state, signal.SIGTERM)
                if not _wait_owned_exit(state, 5.0, signal_new=signal.SIGTERM):
                    _signal_owned_processes(state, signal.SIGKILL)
                    _wait_owned_exit(state, 3.0, signal_new=signal.SIGKILL)
            except InvestigationError as exc:
                failures.append(str(exc))

        # A wrapper may have moved the real listener into another process group. Only
        # signal identities captured after authenticated readiness.
        recorded = {int(item["pid"]): item for item in state.get("owned_processes", [])}
        for port in state["ports"].values():
            for owner in listener_owners(int(port)):
                expected = recorded.get(owner["pid"])
                if expected is None or not identity_matches(expected):
                    failures.append(
                        f"port {port} remains owned by unvalidated pid {owner['pid']}"
                    )
                    continue
                try:
                    signal_recorded_process(expected, signal.SIGTERM)
                except OSError as exc:
                    failures.append(f"failed to signal listener pid {owner['pid']}: {exc}")

        port_deadline = time.monotonic() + 10.0
        bound: list[int] = []
        while time.monotonic() < port_deadline:
            bound = [int(port) for port in state["ports"].values() if not port_is_free(int(port))]
            if not bound:
                break
            time.sleep(0.2)
        if bound:
            failures.append(f"ports remain bound: {bound}")
        remaining = group_members(pgrp)
        if remaining:
            failures.append(f"process group remains alive: {[item['pid'] for item in remaining]}")
        remaining_owned = [
            item["pid"]
            for item in state.get("owned_processes", [])
            if identity_matches(item)
        ]
        if remaining_owned:
            failures.append(f"recorded owned processes remain alive: {remaining_owned}")
        state["timings"]["shutdown_seconds"] = time.monotonic() - shutdown_started

        failures.extend(_remove_protocol_files(state))
        failures.extend(_restore_managed_files(state))
        for artifact in state.get("companion_artifacts", []):
            mod_path = Path(artifact["materialized_path"])
            try:
                if mod_path.exists():
                    mod_path.unlink()
            except OSError as exc:
                failures.append(f"companion artifact removal: {exc}")
        retained_world: str | None = None
        try:
            retained_world = _cleanup_world(state, successful and not failures)
        except CleanupError as exc:
            failures.append(str(exc))

        state["finished_at"] = timestamp()
        state["timings"]["cleanup_seconds"] = time.monotonic() - cleanup_started
        state["cleanup"] = {"complete": not failures, "failures": failures}
        state["cleanup"]["diagnostics"] = diagnostics
        state["lifecycle"] = "failed" if failures or not successful else "succeeded"
        state["retained_world"] = retained_world
        _write_manifest(state)
        atomic_write_json(
            Path(state["artifact_dir"]) / "summary.json",
            {
                "ownership": OWNERSHIP,
                "run_id": state["run_id"],
                "state": state["lifecycle"],
                "started_at": state["started_at"],
                "finished_at": state["finished_at"],
                "cleanup": state["cleanup"],
                "retained_world": retained_world,
            },
        )
        if failures:
            state["lifecycle"] = "cleanup_failed"
            _write_active(state)
            raise CleanupError(
                "server cleanup did not complete",
                details={"failures": failures, "state": str(active)},
            )
        active.unlink()
        return state


def status(project: Path, loader: str) -> dict | None:
    active = active_path(project, loader)
    if not active.exists():
        return None
    state = load_active(project, loader)
    state = dict(state)
    state["leader_identity_valid"] = identity_matches(state["process"])
    state["group_pids"] = [
        item["pid"] for item in group_members(int(state["process"]["pgrp"]))
    ]
    state["bound_ports"] = [
        int(port) for port in state["ports"].values() if not port_is_free(int(port))
    ]
    return state


def recover(project: Path, loader: str, timeout: float) -> dict:
    state = load_active(project, loader)
    process_alive = any(identity_matches(item) for item in state.get("owned_processes", [])) or bool(
        group_members(int(state["process"]["pgrp"]))
    )
    ports_bound = any(not port_is_free(int(port)) for port in state["ports"].values())
    if process_alive or ports_bound:
        return stop_server(project, loader, successful=False, timeout=timeout)
    with project_lock(lock_path(project, loader)):
        state = load_active(project, loader)
        if any(identity_matches(item) for item in state.get("owned_processes", [])) or any(
            not port_is_free(int(port)) for port in state["ports"].values()
        ):
            raise InvestigationError(
                "recovery_state_changed",
                "process or listener state changed while recovery acquired its lock; retry doctor",
            )
        failures = _remove_protocol_files(state)
        failures.extend(_restore_managed_files(state))
        try:
            retained_world = _cleanup_world(state, successful=False)
        except CleanupError as exc:
            failures.append(str(exc))
            retained_world = None
        state["finished_at"] = timestamp()
        state["retained_world"] = retained_world
        state["cleanup"] = {"complete": not failures, "failures": failures}
        state["lifecycle"] = "failed" if not failures else "cleanup_failed"
        _write_manifest(state)
        if failures:
            _write_active(state)
            raise CleanupError("recovery was incomplete", details={"failures": failures})
        Path(state["active_path"]).unlink()
        return state
