from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .catalog import ResolvedArtifact
from .errors import InvestigationError
from .owned_operation import (
    recover_finite_service,
    run_finite_service,
)
from .paths import RUNS_ROOT, active_path, lock_path, validate_loader
from .probe_overlay import git_status, probe_overlay_command
from .server import (
    OWNERSHIP,
    load_owned_active,
    new_run_id,
    sourced_environment,
    uninterruptible_owned_processes,
)
from .state import atomic_write_json


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_results(state: dict) -> list[dict]:
    results: list[dict] = []
    for variable, path_value in state["result_files"].items():
        path = Path(path_value)
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "client_result_missing", f"client result was not written: {variable}={path}"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvestigationError(
                "client_result_invalid", f"client result is invalid: {variable}={path}: {exc}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("status") != "pass":
            raise InvestigationError(
                "client_result_failed",
                f"client result {variable} reported {payload.get('status') if isinstance(payload, dict) else 'non-object'}",
                details={"variable": variable, "path": str(path), "result": payload},
            )
        results.append({
            "environment": variable,
            "path": str(path),
            "sha256": _hash(path),
            "result": payload,
        })
    return results


def _inspect_runtime_mods(state: dict) -> list[dict]:
    mods_dir = Path(state["run_dir"]) / "mods"
    expected = state["probe_overlay"]["runtime_artifacts"]
    evidence_path = state["probe_overlay"].get("runtime_evidence")
    evidence = None
    if evidence_path is not None and Path(evidence_path).is_file():
        try:
            evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvestigationError(
                "client_runtime_artifact_invalid",
                f"client runtime artifact evidence is invalid: {evidence_path}: {exc}",
            ) from exc
    remapped = {
        item["source_path"]: item
        for item in evidence or []
        if isinstance(item, dict)
        and isinstance(item.get("source_path"), str)
        and isinstance(item.get("runtime_path"), str)
    }
    values = []
    for artifact in expected:
        record = remapped.get(artifact["path"])
        path = Path(record["runtime_path"]) if record is not None else mods_dir / artifact["filename"]
        if not path.is_file() or path.is_symlink():
            raise InvestigationError(
                "client_runtime_artifact_missing",
                f"client did not stage runtime artifact {artifact['id']}: {path}",
            )
        values.append({
            "id": artifact["id"],
            "source_path": artifact["path"],
            "source_sha256": artifact["sha256"],
            "runtime_path": str(path),
            "runtime_sha256": _hash(path),
            "size": path.stat().st_size,
        })
    return values


def _remove_display_runtime(state: dict) -> list[str]:
    path = Path(state["display"]["runtime_dir"])
    root = Path(state["display"]["runtime_root"])
    expected = root / f"squinch-{state['run_id'][-10:]}"
    if path != expected:
        return [f"display runtime ownership failed: {path}"]
    if not path.exists():
        return []
    try:
        if path.is_symlink() or not path.is_dir():
            raise ValueError("display runtime is not an owned directory")
        shutil.rmtree(path)
    except (OSError, ValueError) as exc:
        return [f"display runtime cleanup: {exc}"]
    return []


def _display_runtime_root(environment: dict[str, str]) -> Path:
    configured = environment.get("XDG_RUNTIME_DIR")
    if not configured:
        raise InvestigationError("display_runtime_invalid", "XDG_RUNTIME_DIR is not configured")
    root = Path(configured)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise InvestigationError(
            "display_runtime_invalid", f"XDG_RUNTIME_DIR is not a regular absolute directory: {root}"
        )
    if root.stat().st_uid != os.getuid():
        raise InvestigationError("display_runtime_invalid", f"XDG_RUNTIME_DIR is not user-owned: {root}")
    return root


def run_client(
    project: Path,
    loader: str,
    *,
    probe_packs: tuple[Path, ...],
    runtime_artifacts: tuple[ResolvedArtifact, ...],
    compile_artifacts: tuple[tuple[ResolvedArtifact, str], ...],
    probe_environment: dict[str, str],
    result_files: dict[str, str],
    timeout: float,
) -> dict:
    if loader not in {"fabric", "neoforge"}:
        raise InvestigationError("client_unsupported", "client supports Fabric and NeoForge")
    validate_loader(project, loader)
    if timeout <= 0:
        raise InvestigationError("client_invalid", "client timeout must be positive")
    if not result_files:
        raise InvestigationError("client_invalid", "client requires at least one result environment")
    active = active_path(project, loader)
    blocked = uninterruptible_owned_processes(active.parent)
    if blocked:
        raise InvestigationError(
            "host_degraded",
            "refusing to launch while an investigation-owned process is in uninterruptible sleep",
            details={"processes": blocked},
        )
    tracked_before = git_status(project)

    run_id = new_run_id()
    artifact_dir = RUNS_ROOT / run_id
    run_dir = artifact_dir / "client-run"
    mods_dir = run_dir / "mods"
    results_dir = artifact_dir / "results"
    log_path = artifact_dir / "client.log"
    resolved_results = {
        variable: str(results_dir / filename)
        for variable, filename in result_files.items()
    }
    overlay_arguments, overlay = probe_overlay_command(
        loader,
        probe_packs,
        compile_artifacts,
        runtime_artifacts,
        mods_dir,
        run_dir,
        run_dir / "runtime-artifacts.json",
    )
    environment = sourced_environment()
    display_root = _display_runtime_root(environment)
    display_runtime = display_root / f"squinch-{run_id[-10:]}"
    display_name = f"squinch-{run_id[-10:]}"
    environment.update({
        "ALSOFT_DRIVERS": "null",
        "WLR_BACKENDS": "headless",
        "WLR_HEADLESS_OUTPUTS": "1",
        "WLR_LIBINPUT_NO_DEVICES": "1",
        "WLR_RENDERER": "pixman",
        "XDG_RUNTIME_DIR": str(display_runtime),
        "WAYLAND_DISPLAY": display_name,
        **probe_environment,
        **resolved_results,
    })
    command = [
        "cage", "-d", "--", "bash", "./gradlew", f":{loader}:runClient",
        "--console=plain", "--no-daemon", *overlay_arguments,
    ]

    def prepare() -> None:
        for directory in (mods_dir, results_dir, display_runtime):
            directory.mkdir(parents=True, exist_ok=False)
        display_runtime.chmod(0o700)
        (run_dir / "options.txt").write_text(
            "narrator:0\nonboardAccessibility:false\n", encoding="utf-8"
        )

    def validate(state: dict) -> dict:
        runtime_mods = _inspect_runtime_mods(state)
        results = _inspect_results(state)
        state["runtime_mods"] = runtime_mods
        state["results"] = results
        tracked_after = git_status(project)
        state["probe_overlay"]["tracked_status_after_build"] = tracked_after
        state["probe_overlay"]["tracked_source_unchanged"] = tracked_before == tracked_after
        if tracked_before != tracked_after:
            raise InvestigationError(
                "probe_overlay_modified_worktree",
                "client probe-overlay build changed the target worktree status",
            )
        return {"runtime_mods": runtime_mods, "results": results}

    state, validated = run_finite_service(
        project=project,
        loader=loader,
        operation="client",
        ownership=OWNERSHIP,
        run_id=run_id,
        artifact_dir=artifact_dir,
        run_dir=run_dir,
        log_path=log_path,
        active_path=active,
        lock_path=lock_path(project, loader),
        command=command,
        environment=environment,
        timeout=timeout,
        load_active=load_owned_active,
        prepare=prepare,
        validate=validate,
        cleanup=_remove_display_runtime,
        state_fields={
            "display": {
                "backend": "headless",
                "runtime_root": str(display_root),
                "runtime_dir": str(display_runtime),
                "wayland_display": display_name,
            },
            "probe_environment": probe_environment,
            "result_files": resolved_results,
            "probe_overlay": {
                **overlay,
                "tracked_status_before": tracked_before,
                "tracked_status_after_build": None,
                "tracked_source_unchanged": None,
            },
        },
    )
    atomic_write_json(
        artifact_dir / "summary.json",
        {
            "ownership": OWNERSHIP,
            "operation": "client",
            "run_id": run_id,
            "state": state["lifecycle"],
            "started_at": state["started_at"],
            "finished_at": state["finished_at"],
            "cleanup": state["cleanup"],
            "results": validated["results"],
        },
    )
    return state


def recover_client(project: Path, loader: str, timeout: float) -> dict:
    return recover_finite_service(
        project=project,
        loader=loader,
        timeout=timeout,
        lock_path=lock_path(project, loader),
        load_active=load_owned_active,
        operations={"client"},
        cleanup=_remove_display_runtime,
    )
