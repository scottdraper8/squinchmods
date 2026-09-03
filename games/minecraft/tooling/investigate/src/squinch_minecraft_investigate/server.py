from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .errors import CleanupError, InvestigationError
from .catalog import ResolvedArtifact
from .output import timestamp
from .owned_operation import Deadline, defer_termination_signals, terminate_owned_service
from .paths import (
    ENV_SH,
    RUNS_ROOT,
    active_path,
    lock_path,
    validate_loader,
)
from .processes import (
    confirm_uninterruptible,
    free_port,
    identity_matches,
    launch_service,
    listener_owners,
    port_is_available,
    port_is_free,
    proc_identity,
    process_kernel_diagnostics,
    signal_recorded_process,
    service_members,
    signal_service,
    stop_service,
)
from .probe_overlay import git_status, probe_overlay_command
from .rcon import RconError, execute
from .state import atomic_write_json, project_lock, read_json

OWNERSHIP = "squinch-minecraft-investigate"
DEVELOPMENT_PROBE_JAR = "squinch-investigate-probe.jar"
DEVELOPMENT_PROBE_MARKER = "META-INF/squinch-development-probe"
PRODUCTION_SERVER_JARS = (
    "architectury-production.jar",
    "reterraforged-production.jar",
)
STARTUP_TERMINAL_LOG_MARKERS = (
    "Failed to start the minecraft server",
    "FAILURE: Build failed with an exception.",
    "BUILD FAILED",
    "Exception in thread \"main\"",
    "finished with non-zero exit value",
)
STARTUP_LOG_TAIL_BYTES = 128 * 1024
STARTUP_LOG_EXCERPT_LINES = 40
PROTOCOL_READY_PATTERN = re.compile(
    r"\[squinch-investigate] protocol ready run=([A-Za-z0-9-]+) pid=(\d+)"
)


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


def _backup_file(
    path: Path, artifact_dir: Path, backup_relative: Path | None = None
) -> dict:
    record = {"path": str(path), "existed": path.exists(), "backup": None}
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "unsafe_managed_file", f"refusing to replace non-regular file: {path}"
            )
        relative = backup_relative or Path(path.name)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise InvestigationError(
                "unsafe_managed_file", f"invalid managed backup path: {relative}"
            )
        managed_root = (artifact_dir / "managed-files").resolve()
        backup = (managed_root / relative).resolve()
        if backup == managed_root or not backup.is_relative_to(managed_root):
            raise InvestigationError(
                "unsafe_managed_file", f"managed backup escapes its artifact directory: {backup}"
            )
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
        allowed_paths.update(
            Path(record["target"]) for record in state.get("runtime_files", [])
        )
        allowed_paths.update(
            Path(path) for path in state.get("runtime_absent_files", [])
        )
    for record in state.get("managed_files", []):
        path = Path(record["path"])
        try:
            if allowed_paths is not None and path not in allowed_paths:
                raise ValueError("managed path is outside the recorded file set")
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("managed target is not a regular file")
            if record["existed"]:
                backup = Path(record["backup"]).resolve()
                if "artifact_dir" in state:
                    managed_root = (Path(state["artifact_dir"]) / "managed-files").resolve()
                    if backup == managed_root or not backup.is_relative_to(managed_root):
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


def _remove_companion_artifacts(state: dict) -> list[str]:
    failures: list[str] = []
    mods_root = (Path(state["run_dir"]) / "mods").resolve()
    for artifact in state.get("companion_artifacts", []):
        mod_path = Path(artifact["materialized_path"])
        try:
            if mod_path.parent.resolve() != mods_root:
                raise ValueError("companion artifact is outside the run mods directory")
            if mod_path.is_symlink() or (mod_path.exists() and not mod_path.is_file()):
                raise ValueError("companion artifact is not a regular file")
            mod_path.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            failures.append(f"companion artifact removal: {mod_path}: {exc}")
    return failures


def _remove_development_probe_jar(run_dir: Path) -> list[str]:
    """Remove only the probe-overlay JAR identified by its embedded ownership marker."""
    path = run_dir / "mods" / DEVELOPMENT_PROBE_JAR
    if not path.exists():
        return []
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("development probe artifact is not a regular file")
        try:
            with zipfile.ZipFile(path) as archive:
                if DEVELOPMENT_PROBE_MARKER not in archive.namelist():
                    raise ValueError("reserved probe artifact lacks the ownership marker")
        except zipfile.BadZipFile as exc:
            raise ValueError("reserved probe artifact is not a valid JAR") from exc
        path.unlink()
    except (OSError, ValueError) as exc:
        return [f"development probe artifact removal: {path}: {exc}"]
    return []


def _unexpected_run_mods(run_dir: Path) -> list[Path]:
    mods = run_dir / "mods"
    if not mods.exists():
        return []
    if mods.is_symlink() or not mods.is_dir():
        return [mods]
    return sorted(mods.iterdir())


def _remove_launch_artifacts(state: dict) -> list[str]:
    failures = _remove_development_probe_jar(Path(state["run_dir"]))
    if state.get("launch_task") != "prodServer":
        return failures
    mods = Path(state["run_dir"]) / "mods"
    for name in PRODUCTION_SERVER_JARS:
        path = mods / name
        try:
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("production launch artifact is not a regular file")
            path.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            failures.append(f"production launch artifact removal: {path}: {exc}")
    return failures


def _property_text(properties: dict[str, str]) -> str:
    for key, value in properties.items():
        if not key or "=" in key or any(character in key for character in "\r\n"):
            raise InvestigationError("invalid_property", f"invalid server property key: {key!r}")
        if any(character in str(value) for character in "\r\n"):
            raise InvestigationError(
                "invalid_property", f"server property {key!r} contains a newline"
            )
    return "".join(f"{key}={value}\n" for key, value in sorted(properties.items()))


def load_owned_active(project: Path, loader: str) -> dict:
    expected_active = active_path(project, loader)
    state = read_json(expected_active)
    if state.get("ownership") != OWNERSHIP:
        raise InvestigationError("invalid_state", "active state has unknown ownership")
    if state.get("schema_version") != 3:
        raise InvestigationError("invalid_state", "active state schema is not current")
    operation = state.get("operation")
    if operation not in {"server", "client", "cell-scan", "preset-fixture"}:
        raise InvestigationError("invalid_state", "active state operation is invalid")
    if Path(state.get("project", "")) != project or state.get("loader") != loader:
        raise InvestigationError("invalid_state", "active state identity does not match request")
    run_id = state.get("run_id")
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id:
        raise InvestigationError("invalid_state", "active state has an invalid run ID")
    expected_artifact = RUNS_ROOT / run_id
    if operation == "server":
        expected_run_dir = project / loader / "run"
    elif operation == "client":
        expected_run_dir = expected_artifact / "client-run"
    else:
        expected_run_dir = expected_artifact
    expected_paths = {
        "active_path": expected_active,
        "artifact_dir": expected_artifact,
        "log_path": expected_artifact / f"{operation}.log",
        "run_dir": expected_run_dir,
    }
    for field, expected in expected_paths.items():
        if Path(state.get(field, "")) != expected:
            raise InvestigationError(
                "invalid_state", f"active state {field} is outside its owned path"
            )
    service = state.get("service")
    expected_unit = f"squinch-mc-{run_id.lower()}.service"
    launching = state.get("lifecycle") == "launching"
    wrapper = service.get("wrapper") if isinstance(service, dict) else None
    if (
        not isinstance(service, dict)
        or service.get("unit") != expected_unit
        or not isinstance(service.get("cgroup"), str)
        or not (service["cgroup"].startswith("/") or (launching and not service["cgroup"]))
        or not (
            launching and wrapper is None
            or isinstance(wrapper, dict) and _valid_process_identity(wrapper)
        )
    ):
        raise InvestigationError("invalid_state", "active state process service is invalid")
    launcher = state.get("launcher")
    if not isinstance(launcher, dict) or not _valid_process_identity(launcher):
        raise InvestigationError("invalid_state", "active state launcher identity is invalid")
    process = state.get("process")
    if not (
        launching and process is None
        or isinstance(process, dict) and _valid_process_identity(process)
    ):
        raise InvestigationError("invalid_state", "active state process identity is invalid")
    owned_processes = state.get("owned_processes")
    if (
        not isinstance(owned_processes, list)
        or (not launching and not owned_processes)
        or not all(isinstance(item, dict) and _valid_process_identity(item) for item in owned_processes)
    ):
        raise InvestigationError("invalid_state", "active state owned process identities are invalid")
    if operation == "client":
        display = state.get("display")
        if (
            not isinstance(display, dict)
            or Path(display.get("runtime_dir", "")) != expected_artifact / "display-runtime"
            or display.get("backend") != "headless"
            or not isinstance(display.get("wayland_display"), str)
            or not display["wayland_display"]
        ):
            raise InvestigationError("invalid_state", "active client display ownership is invalid")
    return state


def load_active(project: Path, loader: str) -> dict:
    state = load_owned_active(project, loader)
    if state["operation"] != "server":
        raise InvestigationError(
            "operation_mismatch", f"active operation is {state['operation']}, not server"
        )
    expected_level_name = f"squinch-{state['run_id'].lower()}"
    expected_world = Path(state["run_dir"]) / expected_level_name
    if state.get("level_name") != expected_level_name:
        raise InvestigationError("invalid_state", "active state level name is invalid")
    if Path(state.get("world_dir", "")) != expected_world:
        raise InvestigationError("invalid_state", "active state world directory is invalid")
    if state.get("retention") not in {"discard", "keep-on-failure", "keep"}:
        raise InvestigationError("invalid_state", "active state retention is invalid")
    return state


def _valid_process_identity(value: dict) -> bool:
    typed = all(
        isinstance(value.get(field), int) and not isinstance(value.get(field), bool)
        for field in ("pid", "ppid", "pgrp", "session", "start_ticks")
    )
    return typed and value["pid"] > 0 and value["start_ticks"] > 0 and all(
        value[field] >= 0 for field in ("ppid", "pgrp", "session")
    )


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


def _refresh_owned_processes(state: dict, *, timeout: float = 5.0) -> list[dict]:
    recorded = {int(item["pid"]): item for item in state.get("owned_processes", [])}
    for identity in service_members(state["service"], timeout=timeout):
        recorded[identity["pid"]] = identity
    state["owned_processes"] = sorted(recorded.values(), key=lambda value: value["pid"])
    return [item for item in state["owned_processes"] if identity_matches(item)]


def uninterruptible_owned_processes(
    active_root: Path, *, timeout: float = 5.0
) -> list[dict]:
    """Find exact investigation-owned processes blocked in kernel disk sleep."""
    if timeout <= 0:
        raise InvestigationError(
            "host_health_inconclusive", "owned-process health scan has no time budget"
        )
    deadline = time.monotonic() + timeout
    blocked: list[dict] = []
    if not active_root.is_dir():
        return blocked
    for path in active_root.glob("*.json"):
        try:
            state = read_json(path)
        except InvestigationError:
            continue
        if state.get("ownership") != OWNERSHIP:
            continue
        for expected in state.get("owned_processes", []):
            if not isinstance(expected, dict) or "pid" not in expected:
                continue
            if time.monotonic() >= deadline:
                raise InvestigationError(
                    "host_health_inconclusive",
                    "owned-process health scan exceeded its global time budget",
                    details={"active_root": str(active_root), "timeout_seconds": timeout},
                )
            actual = proc_identity(int(expected["pid"]))
            if actual is None or actual["state"] != "D":
                continue
            if all(
                actual.get(field) == expected.get(field)
                for field in ("pid", "start_ticks", "pgrp", "session")
            ):
                blocked.append({
                    "active_path": str(path),
                    "run_id": state.get("run_id"),
                    "project": state.get("project"),
                    "loader": state.get("loader"),
                    "process": actual,
                })
    return blocked


def _signal_owned_processes(
    state: dict, sig: signal.Signals, *, timeout: float = 5.0
) -> None:
    service_failure: InvestigationError | None = None
    try:
        signal_service(state["service"], sig, timeout=timeout)
    except InvestigationError as exc:
        service_failure = exc
    for expected in state.get("owned_processes", []):
        with contextlib.suppress(ProcessLookupError):
            signal_recorded_process(expected, sig)
    if service_failure is not None and service_members(state["service"]):
        raise service_failure


def _wait_owned_exit(state: dict, timeout: float, *, signal_new: signal.Signals | None = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        before = len(state.get("owned_processes", []))
        live = _refresh_owned_processes(
            state, timeout=max(0.0, deadline - time.monotonic())
        )
        if len(state["owned_processes"]) != before:
            _write_active(state)
            if signal_new is not None:
                _signal_owned_processes(state, signal_new)
        if not live:
            return True
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
    return not _refresh_owned_processes(state, timeout=0.0)


def _wait_graceful_server_exit(state: dict, timeout: float) -> bool:
    """Wait for Minecraft saves/listeners, but not a stale wrapper after all listeners close."""
    deadline = time.monotonic() + timeout
    listener_free_since: float | None = None
    while time.monotonic() < deadline:
        before = len(state.get("owned_processes", []))
        live = _refresh_owned_processes(
            state, timeout=max(0.0, deadline - time.monotonic())
        )
        if len(state["owned_processes"]) != before:
            _write_active(state)
        if not live:
            return True
        bound = []
        for port in state["ports"].values():
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not port_is_free(int(port), timeout=remaining):
                bound.append(int(port))
        if bound:
            listener_free_since = None
        elif listener_free_since is None:
            listener_free_since = time.monotonic()
        elif time.monotonic() - listener_free_since >= 5.0:
            # Minecraft no longer owns either listener and has had a short process-exit grace.
            # Let the validated TERM/KILL path handle a lingering Gradle boundary.
            return False
        time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
    return not _refresh_owned_processes(state, timeout=0.0)


def _startup_terminal_log(log_path: Path) -> str | None:
    """Return a bounded terminal excerpt when launch output proves startup has failed."""
    try:
        with log_path.open("rb") as log_file:
            size = log_file.seek(0, os.SEEK_END)
            log_file.seek(max(0, size - STARTUP_LOG_TAIL_BYTES))
            tail = log_file.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None
    if not any(marker in tail for marker in STARTUP_TERMINAL_LOG_MARKERS):
        return None
    lines = tail.splitlines()
    return "\n".join(lines[-STARTUP_LOG_EXCERPT_LINES:])


def _protocol_process_pid(log_path: Path, run_id: str) -> int | None:
    try:
        with log_path.open("rb") as log_file:
            size = log_file.seek(0, os.SEEK_END)
            log_file.seek(max(0, size - STARTUP_LOG_TAIL_BYTES))
            tail = log_file.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None
    matches = PROTOCOL_READY_PATTERN.findall(tail)
    return next((int(pid) for marker_run, pid in reversed(matches) if marker_run == run_id), None)


def _rollback_server_files(
    *,
    run_dir: Path,
    world_dir: Path,
    artifact_dir: Path,
    managed_files: list[dict],
    runtime_files: list[dict[str, str]],
    runtime_absent_files: list[str],
    companion_artifacts: list[dict[str, str]],
    remove_artifact_dir: bool,
) -> list[str]:
    """Attempt every reversible preparation cleanup and report the complete result."""
    failures: list[str] = []
    for artifact in companion_artifacts:
        target = Path(artifact["materialized_path"])
        try:
            target.unlink(missing_ok=True)
        except OSError as failure:
            failures.append(f"companion {target}: {failure}")
    failures.extend(_restore_managed_files({
        "run_dir": str(run_dir),
        "artifact_dir": str(artifact_dir),
        "managed_files": managed_files,
        "runtime_files": runtime_files,
        "runtime_absent_files": runtime_absent_files,
    }))
    if world_dir.exists():
        try:
            if world_dir.is_symlink() or not world_dir.is_dir():
                raise ValueError("owned world path is not a regular directory")
            shutil.rmtree(world_dir)
        except (OSError, ValueError) as failure:
            failures.append(f"world {world_dir}: {failure}")
    if remove_artifact_dir and not failures:
        try:
            shutil.rmtree(artifact_dir)
        except OSError as failure:
            failures.append(f"artifact directory {artifact_dir}: {failure}")
    return failures


def start_server(
    project: Path,
    loader: str,
    *,
    seed: str | None,
    datapacks: list[Path],
    runtime_files: list[tuple[Path, str]] | None = None,
    runtime_absent_files: list[str] | None = None,
    companion_artifacts: list[ResolvedArtifact] | None = None,
    probe_compile_artifacts: list[tuple[ResolvedArtifact, str]] | None = None,
    properties: dict[str, str],
    timeout: float,
    retention: str,
    probe_packs: tuple[Path, ...] = (),
    server_port: int | None = None,
    rcon_port: int | None = None,
    launch_task: str = "runServer",
) -> dict:
    startup_started = time.monotonic()
    loader_dir = validate_loader(project, loader)
    if launch_task not in {"runServer", "prodServer"}:
        raise InvestigationError(
            "invalid_launch_task", f"unsupported Gradle launch task: {launch_task}"
        )
    if launch_task == "prodServer" and loader not in {"fabric", "neoforge"}:
        raise InvestigationError(
            "invalid_launch_task", "prodServer requires Fabric or NeoForge"
        )
    active = active_path(project, loader)
    blocked = uninterruptible_owned_processes(active.parent)
    if blocked:
        raise InvestigationError(
            "host_degraded",
            "refusing to launch while an investigation-owned process is in uninterruptible sleep",
            details={"processes": blocked},
        )
    launcher = proc_identity(os.getpid())
    if launcher is None:
        raise InvestigationError(
            "process_identity_failed", "could not retain server launcher identity"
        )
    compile_artifacts = probe_compile_artifacts or []
    if any(mapping not in {"named", "loader"} for _artifact, mapping in compile_artifacts):
        raise InvestigationError(
            "probe_compile_artifact_invalid", "probe compile artifact mapping must be named or loader"
        )
    overlay_arguments, overlay_details = probe_overlay_command(
        loader, probe_packs, tuple(compile_artifacts)
    )
    tracked_status_before = git_status(project)
    with project_lock(lock_path(project, loader)):
        if active.exists():
            existing = load_owned_active(project, loader)
            process = existing["process"]
            if (
                isinstance(process, dict) and identity_matches(process)
                or service_members(existing["service"])
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
        probe_cleanup_failures = _remove_development_probe_jar(run_dir)
        if probe_cleanup_failures:
            raise InvestigationError(
                "probe_artifact_conflict",
                probe_cleanup_failures[0],
            )
        unexpected_mods = _unexpected_run_mods(run_dir)
        if unexpected_mods:
            raise InvestigationError(
                "run_mods_not_isolated",
                f"run mods directory contains undeclared entries: {unexpected_mods}",
            )
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
        resolved_runtime_files: list[dict[str, str]] = []
        config_root = (run_dir / "config").resolve()
        for source_value, target_value in runtime_files or []:
            source = source_value.expanduser().resolve()
            target = (run_dir / target_value).resolve()
            if not source.is_file() or source.is_symlink():
                raise InvestigationError(
                    "runtime_file_not_found", f"runtime file is not a regular file: {source}"
                )
            if not target.is_relative_to(config_root) or target == config_root:
                raise InvestigationError(
                    "unsafe_runtime_file", f"runtime file target escapes config directory: {target_value}"
                )
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise InvestigationError(
                    "unsafe_runtime_file", f"runtime file target is not a regular file: {target}"
                )
            resolved_runtime_files.append({
                "source": str(source),
                "target": str(target),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            })
        resolved_runtime_absent_files: list[str] = []
        for target_value in runtime_absent_files or []:
            target = (run_dir / target_value).resolve()
            if not target.is_relative_to(config_root) or target == config_root:
                raise InvestigationError(
                    "unsafe_runtime_file", f"absent runtime file target escapes config directory: {target_value}"
                )
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise InvestigationError(
                    "unsafe_runtime_file", f"absent runtime file target is not a regular file: {target}"
                )
            resolved_runtime_absent_files.append(str(target))
        managed_targets = [record["target"] for record in resolved_runtime_files]
        managed_targets.extend(resolved_runtime_absent_files)
        if len(set(managed_targets)) != len(managed_targets):
            raise InvestigationError("duplicate_runtime_file", "runtime file targets must be unique")

        artifact_dir.mkdir(parents=True, exist_ok=False)
        managed_files: list[dict] = []
        installed_companion_artifacts: list[dict[str, str]] = []
        try:
            managed_files.append(_backup_file(run_dir / "eula.txt", artifact_dir))
            managed_files.append(_backup_file(run_dir / "server.properties", artifact_dir))
            for record in resolved_runtime_files:
                target = Path(record["target"])
                managed_files.append(
                    _backup_file(target, artifact_dir, target.relative_to(run_dir))
                )
            for target_value in resolved_runtime_absent_files:
                target = Path(target_value)
                managed_files.append(
                    _backup_file(target, artifact_dir, target.relative_to(run_dir))
                )
            (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            (run_dir / "server.properties").write_text(property_text, encoding="utf-8")
            for record in resolved_runtime_files:
                target = Path(record["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(Path(record["source"]), target)
            for target in resolved_runtime_absent_files:
                Path(target).unlink(missing_ok=True)
            if resolved_datapacks:
                target_dir = world_dir / "datapacks"
                target_dir.mkdir(parents=True, exist_ok=False)
                for source in resolved_datapacks:
                    shutil.copy2(source, target_dir / source.name)
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
                    installed = {
                        "id": artifact.id,
                        "source_path": str(source),
                        "materialized_path": str(target),
                        "sha256": artifact.sha256,
                    }
                    installed_companion_artifacts.append(installed)
                    shutil.copy2(source, target)
        except BaseException as original:
            cleanup_failures = _rollback_server_files(
                run_dir=run_dir,
                world_dir=world_dir,
                artifact_dir=artifact_dir,
                managed_files=managed_files,
                runtime_files=resolved_runtime_files,
                runtime_absent_files=resolved_runtime_absent_files,
                companion_artifacts=installed_companion_artifacts,
                remove_artifact_dir=True,
            )
            if cleanup_failures:
                raise CleanupError(
                    "server preparation failed and rollback did not complete",
                    details={
                        "preparation_error": str(original),
                        "failures": cleanup_failures,
                        "run_id": run_id,
                        "artifact_dir": str(artifact_dir),
                    },
                ) from original
            raise

        command = [
            "bash",
            "./gradlew",
            f":{loader}:{launch_task}",
            "--console=plain",
            "--no-daemon",
            *overlay_arguments,
        ]
        started_at = timestamp()
        process: subprocess.Popen[bytes] | None = None
        service: dict | None = None
        identity: dict | None = None
        state: dict | None = None
        launch_owned = False

        def publish_start(
            launched_process: subprocess.Popen[bytes] | None,
            launched_service: dict,
            wrapper_identity: dict | None,
        ) -> None:
            nonlocal state, launch_owned
            state = {
                "ownership": OWNERSHIP,
                "schema_version": 3,
                "operation": "server",
                "run_id": run_id,
                "lifecycle": "launching",
                "started_at": started_at,
                "finished_at": None,
                "project": str(project),
                "loader": loader,
                "launch_task": launch_task,
                "level_name": level_name,
                "world_dir": str(world_dir),
                "run_dir": str(run_dir),
                "artifact_dir": str(artifact_dir),
                "log_path": str(log_path),
                "active_path": str(active),
                "retention": retention,
                "ports": {"server": chosen_server_port, "rcon": chosen_rcon_port},
                "rcon": {"host": "127.0.0.1", "password": password},
                "process": wrapper_identity,
                "service": launched_service,
                "launcher": launcher,
                "owned_processes": [wrapper_identity] if wrapper_identity is not None else [],
                "managed_files": managed_files,
                "runtime_files": resolved_runtime_files,
                "runtime_absent_files": resolved_runtime_absent_files,
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
                "protocol_process": None,
                "forceload_regions": [],
                "protocol_files": [],
                "cleanup": {"complete": False, "failures": []},
            }
            launch_owned = True
            _write_active(state)

        try:
            with log_path.open("wb") as log_file:
                launch_environment = sourced_environment()
                launch_environment["SQUINCH_INVESTIGATE_RUN_ID"] = run_id
                process, service, identity = launch_service(
                    unit=f"squinch-mc-{run_id.lower()}.service",
                    command=command,
                    cwd=project,
                    environment=launch_environment,
                    output=log_file,
                    publish_start=publish_start,
                )
            assert state is not None
            state["lifecycle"] = "starting"
            state["process"] = identity
            state["service"] = service
            state["owned_processes"] = [identity, service["wrapper"]]
            _write_active(state)
        except BaseException as original:
            cleanup_failures: list[str] = []
            owned_process_alive = False
            if launch_owned and state is not None:
                try:
                    cleanup_failures.extend(
                        terminate_owned_service(state, 15.0, label="server")
                    )
                except BaseException as failure:
                    cleanup_failures.append(f"server launch cleanup failed: {failure}")
                owned_process_alive = bool(state.get("remaining_owned_processes"))
            if not owned_process_alive:
                if state is not None:
                    cleanup_failures.extend(_remove_launch_artifacts(state))
                if launch_owned and active.exists():
                    try:
                        active.unlink()
                    except OSError as failure:
                        cleanup_failures.append(f"active state {active}: {failure}")
                cleanup_failures.extend(_rollback_server_files(
                    run_dir=run_dir,
                    world_dir=world_dir,
                    artifact_dir=artifact_dir,
                    managed_files=managed_files,
                    runtime_files=resolved_runtime_files,
                    runtime_absent_files=resolved_runtime_absent_files,
                    companion_artifacts=installed_companion_artifacts,
                    remove_artifact_dir=not cleanup_failures,
                ))
            elif state is not None:
                state["lifecycle"] = "cleanup_failed"
                state["failure"] = str(original)
                state["cleanup"] = {"complete": False, "failures": cleanup_failures}
                try:
                    _write_active(state)
                except OSError as failure:
                    cleanup_failures.append(f"could not retain active recovery state: {failure}")
                    with contextlib.suppress(OSError):
                        _write_manifest(state)
            if cleanup_failures:
                raise CleanupError(
                    "server launch failed and rollback did not complete",
                    details={
                        "launch_error": str(original),
                        "failures": cleanup_failures,
                        "run_id": run_id,
                        "artifact_dir": str(artifact_dir),
                        "recovery_required": owned_process_alive,
                    },
                ) from original
            raise

    deadline = time.monotonic() + timeout
    probe_deadline: float | None = None
    try:
        while time.monotonic() < deadline:
            before = len(state["owned_processes"])
            live = _refresh_owned_processes(state)
            if len(state["owned_processes"]) != before:
                _write_active(state)
            if process.poll() is not None:
                raise InvestigationError(
                    "startup_exited",
                    f"server process exited with code {process.returncode} before RCON readiness",
                    details={"log_path": str(log_path)},
                )
            terminal_log = _startup_terminal_log(log_path)
            if terminal_log is not None:
                raise InvestigationError(
                    "startup_exited",
                    "launch output reported a terminal failure before RCON readiness",
                    details={"log_path": str(log_path), "terminal_log": terminal_log},
                )
            uninterruptible = [
                confirmed
                for item in live
                if item.get("state") == "D"
                and (confirmed := confirm_uninterruptible(item)) is not None
            ]
            if uninterruptible:
                _write_active(state)
                raise InvestigationError(
                    "host_degraded",
                    "an investigation-owned process entered uninterruptible sleep during startup",
                    details={"processes": uninterruptible, "log_path": str(log_path)},
                )
            protocol_pid = _protocol_process_pid(log_path, run_id)
            protocol_process = state.get("protocol_process")
            if protocol_process is None and protocol_pid is not None:
                protocol_process = next(
                    (item for item in live if item["pid"] == protocol_pid), None
                )
                if protocol_process is None:
                    raise InvestigationError(
                        "startup_exited",
                        "Minecraft initialized the probe boundary and exited before RCON readiness",
                        details={"log_path": str(log_path)},
                    )
                state["protocol_process"] = protocol_process
                _write_active(state)
            elif protocol_process is not None and not identity_matches(protocol_process):
                raise InvestigationError(
                    "startup_exited",
                    "Minecraft initialized the probe boundary and exited before RCON readiness",
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
                if state.get("protocol_process") is None:
                    now = time.monotonic()
                    if probe_deadline is None:
                        probe_deadline = min(deadline, now + 5.0)
                    if now >= probe_deadline:
                        raise InvestigationError(
                            "startup_probe_boundary_missing",
                            "server reached RCON readiness without the investigation probe boundary",
                            details={"log_path": str(log_path)},
                        )
                    time.sleep(min(0.1, probe_deadline - now))
                    continue
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
        tracked_status_after = git_status(project)
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
                    "overlay": overlay_details["overlay"],
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
            if cleanup.code == "interrupted" and cleanup.details.get("cleanup_complete") is True:
                raise cleanup from original
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
        if isinstance(original, KeyboardInterrupt):
            raise InvestigationError(
                "interrupted",
                "server startup interrupted by signal",
                details={
                    "run_id": run_id,
                    "artifact_dir": str(artifact_dir),
                    "log_path": str(log_path),
                    "cleanup_complete": True,
                },
            ) from original
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


def _remove_forceload_regions(
    state: dict, deadline: Deadline, *, reserve_seconds: float = 0.0
) -> list[str]:
    """Remove only this run's regions and durably forget each acknowledged removal."""
    failures: list[str] = []
    for region in reversed(list(state.get("forceload_regions", []))):
        remaining = min(10.0, max(0.0, deadline.remaining() - reserve_seconds))
        if remaining <= 0:
            failures.append("shutdown timeout expired before owned forceload cleanup completed")
            break
        command = (
            f"forceload remove {region['block_min_x']} {region['block_min_z']} "
            f"{region['block_max_x']} {region['block_max_z']}"
        )
        try:
            run_commands(state, [command], remaining)
        except InvestigationError as exc:
            failures.append(f"owned forceload removal: {exc}")
        else:
            state["forceload_regions"].remove(region)
            _write_active(state)
    return failures


def _stop_server(
    project: Path, loader: str, *, successful: bool, timeout: float, allow_orphaned_starting: bool = False
) -> dict:
    active = active_path(project, loader)
    with project_lock(lock_path(project, loader)):
        cleanup_started = time.monotonic()
        deadline = Deadline(timeout)
        forced_teardown_reserve = min(10.0, timeout / 2.0)
        state = load_active(project, loader)
        if state["lifecycle"] == "starting" and not allow_orphaned_starting:
            raise InvestigationError(
                "startup_in_progress",
                "server startup is still owned by the launching command",
            )
        was_ready = state["lifecycle"] == "ready"
        state["lifecycle"] = "stopping"
        _write_active(state)
        failures: list[str] = []
        diagnostics: list[str] = []
        failures.extend(
            _remove_forceload_regions(
                state, deadline, reserve_seconds=forced_teardown_reserve
            )
        )
        save_started = time.monotonic()
        if was_ready:
            remaining = max(0.0, deadline.remaining() - forced_teardown_reserve)
            try:
                if remaining <= 0:
                    raise InvestigationError(
                        "shutdown_timeout", "shutdown timeout expired before world save"
                    )
                # Large worldgen evidence windows can legitimately need more than thirty seconds
                # to flush. The caller already supplies the bounded shutdown budget; imposing a
                # smaller hidden cap turns a healthy, still-saving server into a forced teardown.
                run_commands(state, ["save-all flush"], remaining)
            except InvestigationError as exc:
                failures.append(f"world save: {exc}")
        state.setdefault("timings", {})["save_seconds"] = time.monotonic() - save_started
        shutdown_started = time.monotonic()
        try:
            remaining = min(
                10.0, max(0.0, deadline.remaining() - forced_teardown_reserve)
            )
            if remaining <= 0:
                raise InvestigationError(
                    "shutdown_timeout", "shutdown timeout expired before RCON stop"
                )
            run_commands(state, ["stop"], remaining)
        except InvestigationError as exc:
            # The server often closes RCON before replying to `stop`. Process and
            # socket ownership checks below decide whether cleanup really failed.
            diagnostics.append(f"RCON stop: {exc}")

        _refresh_owned_processes(state, timeout=deadline.remaining(1.0))
        remaining = deadline.remaining()
        escalation_reserve = (
            remaining if timeout < 1.0 else min(5.0, remaining / 2.0)
        )
        graceful = _wait_graceful_server_exit(
            state, max(0.0, remaining - escalation_reserve)
        )
        if not graceful:
            state["teardown_process_diagnostics"] = [
                process_kernel_diagnostics(item)
                for item in state.get("owned_processes", [])
            ]
            _write_active(state)
            remaining = deadline.remaining()
            kill_reserve = remaining if remaining < 1.0 else min(1.0, remaining / 2.0)
            try:
                _signal_owned_processes(
                    state,
                    signal.SIGTERM,
                    timeout=min(1.0, max(0.0, deadline.remaining() - kill_reserve)),
                )
            except InvestigationError as exc:
                diagnostics.append(f"owned TERM: {exc}")
            if not _wait_owned_exit(
                state,
                max(0.0, deadline.remaining() - kill_reserve),
                signal_new=signal.SIGTERM,
            ):
                try:
                    _signal_owned_processes(
                        state, signal.SIGKILL, timeout=deadline.remaining(1.0)
                    )
                except InvestigationError as exc:
                    diagnostics.append(f"owned KILL: {exc}")
                remaining = deadline.remaining()
                verification_reserve = min(0.25, remaining / 2.0)
                _wait_owned_exit(
                    state,
                    max(0.0, remaining - verification_reserve),
                    signal_new=signal.SIGKILL,
                )

        try:
            stop_service(
                state["service"], timeout=min(0.1, deadline.remaining() / 2.0)
            )
        except InvestigationError as exc:
            diagnostics.append(f"service stop: {exc}")

        recorded = {int(item["pid"]): item for item in state.get("owned_processes", [])}
        for port in state["ports"].values():
            for owner in listener_owners(int(port), timeout=deadline.remaining(5.0)):
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

        bound: list[int] = []
        ports_verified = False
        while not deadline.expired():
            bound = []
            for port in state["ports"].values():
                remaining = deadline.remaining()
                if remaining <= 0 or not port_is_free(int(port), timeout=remaining):
                    bound.append(int(port))
            if not bound:
                ports_verified = True
                break
            time.sleep(0.2)
        if bound:
            failures.append(f"ports remain bound: {bound}")
        elif not ports_verified:
            failures.append("shutdown timeout expired before listener cleanup was verified")
        remaining = service_members(state["service"], timeout=deadline.remaining(1.0))
        if remaining:
            failures.append(f"owned cgroup remains alive: {[item['pid'] for item in remaining]}")
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
        failures.extend(_remove_companion_artifacts(state))
        failures.extend(_remove_launch_artifacts(state))
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


def stop_server(
    project: Path,
    loader: str,
    *,
    successful: bool,
    timeout: float,
    allow_orphaned_starting: bool = False,
) -> dict:
    with defer_termination_signals() as pending_signals:
        state = _stop_server(
            project,
            loader,
            successful=successful,
            timeout=timeout,
            allow_orphaned_starting=allow_orphaned_starting,
        )
    if pending_signals:
        raise InvestigationError(
            "interrupted",
            "server teardown interrupted by signal after cleanup completed",
            details={
                "run_id": state["run_id"],
                "artifact_dir": state["artifact_dir"],
                "log_path": state["log_path"],
                "cleanup_complete": True,
            },
        )
    return state


def status(project: Path, loader: str) -> dict | None:
    active = active_path(project, loader)
    if not active.exists():
        return None
    state = load_owned_active(project, loader)
    state = dict(state)
    process = state["process"]
    state["leader_identity_valid"] = (
        isinstance(process, dict) and identity_matches(process)
    )
    state["owned_pids"] = [item["pid"] for item in service_members(state["service"])]
    state["bound_ports"] = [
        int(port)
        for port in state.get("ports", {}).values()
        if not port_is_free(int(port))
    ]
    return state


def recover(project: Path, loader: str, timeout: float) -> dict:
    state = load_owned_active(project, loader)
    if state["operation"] == "client":
        from .client import recover_client

        return recover_client(project, loader, timeout)
    if state["operation"] in {"cell-scan", "preset-fixture"}:
        from .cell_scan import recover_standalone

        return recover_standalone(project, loader, timeout)
    process_alive = any(identity_matches(item) for item in state.get("owned_processes", [])) or bool(
        service_members(state["service"])
    )
    ports_bound = any(not port_is_free(int(port)) for port in state["ports"].values())
    if process_alive or ports_bound:
        if state["lifecycle"] == "starting":
            if not _starting_run_is_orphaned(state):
                raise InvestigationError(
                    "startup_in_progress",
                    "server startup is still owned by a live launching command",
                )
            return stop_server(
                project,
                loader,
                successful=False,
                timeout=timeout,
                allow_orphaned_starting=True,
            )
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
        failures.extend(_remove_companion_artifacts(state))
        failures.extend(_remove_launch_artifacts(state))
        try:
            stop_service(state["service"])
        except InvestigationError as exc:
            failures.append(str(exc))
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


def _starting_run_is_orphaned(state: dict) -> bool:
    """Whether a doctor recovery can safely take over a stranded startup."""
    return not identity_matches(state["launcher"])
