from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import InvestigationError
from .processes import identity_matches


@dataclass(frozen=True)
class JfrRecording:
    name: str
    pid: int
    path: Path
    start_output: str


def _jcmd(java_home: str | None) -> Path:
    command = Path(java_home) / "bin" / "jcmd" if java_home else Path("jcmd")
    if command.is_absolute() and not command.is_file():
        raise InvestigationError("jfr_unavailable", f"jcmd is missing: {command}")
    return command


def _run_jcmd(command: Path, pid: int, *arguments: str) -> str:
    try:
        result = subprocess.run(
            [str(command), str(pid), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        output = getattr(exc, "stdout", None) or str(exc)
        raise InvestigationError(
            "jfr_command_failed", f"jcmd failed for pid {pid}: {output.strip()}"
        ) from exc
    return result.stdout.strip()


def _minecraft_jvm(state: dict, command: Path) -> int:
    candidates: list[tuple[int, str]] = []
    for identity in state.get("owned_processes", []):
        if not identity_matches(identity):
            continue
        pid = int(identity["pid"])
        try:
            line = _run_jcmd(command, pid, "VM.command_line")
        except InvestigationError:
            continue
        lowered = line.lower()
        if "gradledaemon" in lowered or "gradlewrappermain" in lowered:
            continue
        if any(
            marker in lowered
            for marker in (
                "devlaunchinjector",
                "knotserver",
                "fabricserverlauncher",
                "net.fabricmc.installer.serverlauncher",
                "net.minecraft.server.main",
                "neoforge",
                "bootstraplauncher",
            )
        ):
            candidates.append((pid, line))
    if len(candidates) != 1:
        raise InvestigationError(
            "jfr_jvm_ambiguous",
            f"expected one owned Minecraft JVM, found {len(candidates)}",
            details={"candidates": [{"pid": pid, "command_line": line} for pid, line in candidates]},
        )
    return candidates[0][0]


def start_jfr(state: dict, step_id: str, java_home: str | None) -> JfrRecording:
    safe_id = re.sub(r"[^A-Za-z0-9_]", "_", step_id)
    name = f"SQ_{safe_id}_{state['run_id'][-10:]}"
    profile_dir = Path(state["artifact_dir"]) / "profiles"
    profile_dir.mkdir(exist_ok=True)
    path = profile_dir / f"{safe_id}.jfr"
    if path.exists() or path.is_symlink():
        raise InvestigationError("jfr_artifact_exists", f"JFR artifact already exists: {path}")
    command = _jcmd(java_home)
    pid = _minecraft_jvm(state, command)
    output = _run_jcmd(
        command,
        pid,
        "JFR.start",
        f"name={name}",
        "settings=profile",
    )
    if "started recording" not in output.lower():
        raise InvestigationError(
            "jfr_start_unconfirmed", f"JFR.start did not confirm recording: {output}"
        )
    return JfrRecording(name, pid, path, output)


def stop_jfr(recording: JfrRecording, java_home: str | None) -> dict:
    command = _jcmd(java_home)
    output = _run_jcmd(
        command,
        recording.pid,
        "JFR.stop",
        f"name={recording.name}",
        f"filename={recording.path}",
    )
    if "stopped recording" not in output.lower():
        raise InvestigationError(
            "jfr_stop_unconfirmed", f"JFR.stop did not confirm recording: {output}"
        )
    if recording.path.is_symlink() or not recording.path.is_file():
        raise InvestigationError(
            "jfr_artifact_missing", f"JFR artifact was not created: {recording.path}"
        )
    size = recording.path.stat().st_size
    if size <= 0:
        raise InvestigationError("jfr_artifact_empty", f"JFR artifact is empty: {recording.path}")
    return {
        "name": recording.name,
        "pid": recording.pid,
        "path": str(recording.path),
        "size": size,
        "sha256": hashlib.sha256(recording.path.read_bytes()).hexdigest(),
        "settings": "profile",
        "scope": "scenario-step",
        "start_output": recording.start_output,
        "stop_output": output,
    }
