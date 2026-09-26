from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
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


def _gradle_property(project: Path, name: str) -> str:
    for path in (project / "gradle.properties", project.parent / "gradle.properties"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip()
    raise InvestigationError("client_invalid", f"Gradle property {name!r} is missing")


def _cache_home(environment: dict[str, str]) -> Path:
    configured = environment.get("SQINCHMODS_CACHE_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = environment.get("XDG_CACHE_HOME")
    return (Path(xdg) / "squinchmods" if xdg else Path.home() / ".cache" / "squinchmods").resolve()


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


def _results_complete(state: dict) -> bool:
    paths = [Path(value) for value in state["result_files"].values()]
    if not all(path.is_file() and not path.is_symlink() for path in paths):
        return False
    _inspect_results(state)
    return True


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


def _detect_terminal_failure(state: dict) -> BaseException | None:
    crash_root = Path(state["run_dir"]) / "crash-reports"
    if crash_root.is_dir() and not crash_root.is_symlink():
        reports = sorted(
            path for path in crash_root.glob("*.txt") if path.is_file() and not path.is_symlink()
        )
        if reports:
            return InvestigationError(
                "client_crashed",
                "client wrote a crash report before producing its required result",
                details={"crash_reports": [str(path) for path in reports]},
            )
    for variable, path_value in state.get("result_files", {}).items():
        path = Path(path_value)
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return InvestigationError(
                "client_result_invalid", f"client result is invalid: {variable}={path}: {exc}"
            )
        if path.is_symlink() or not path.is_file() or not isinstance(payload, dict) \
                or payload.get("status") != "pass":
            return InvestigationError(
                "client_result_failed",
                f"client result {variable} reported "
                f"{payload.get('status') if isinstance(payload, dict) else 'non-object'}",
                details={"variable": variable, "path": str(path), "result": payload},
            )
    exit_path_value = state.get("application_exit")
    if exit_path_value is None or _results_complete(state):
        return None
    exit_path = Path(exit_path_value)
    if not exit_path.exists():
        return None
    try:
        payload = json.loads(exit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return InvestigationError(
            "client_application_exit_invalid", f"client exit sentinel is invalid: {exit_path}: {exc}"
        )
    if (
        exit_path.is_symlink()
        or not exit_path.is_file()
        or not isinstance(payload, dict)
        or payload.get("status") != "exited"
        or not isinstance(payload.get("exit_code"), int)
    ):
        return InvestigationError(
            "client_application_exit_invalid", f"client exit sentinel is invalid: {exit_path}"
        )
    return InvestigationError(
        "client_application_exited",
        "client application exited before producing all required results",
        details={"path": str(exit_path), **payload},
    )


def run_client(
    project: Path,
    loader: str,
    *,
    probe_packs: tuple[Path, ...],
    runtime_artifacts: tuple[ResolvedArtifact, ...],
    compile_artifacts: tuple[tuple[ResolvedArtifact, str], ...],
    probe_environment: dict[str, str],
    result_files: dict[str, str],
    runtime_files: tuple[tuple[Path, str], ...] = (),
    production: bool = False,
    cpu_list: str | None = None,
    timeout: float,
) -> dict:
    if loader not in {"fabric", "neoforge"}:
        raise InvestigationError("client_unsupported", "client supports Fabric and NeoForge")
    if cpu_list is not None:
        if re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", cpu_list) is None:
            raise InvestigationError("client_invalid", "client CPU list has invalid syntax")
        available = os.cpu_count() or 1
        for item in cpu_list.split(","):
            bounds = [int(value) for value in item.split("-")]
            if bounds[0] >= available or (len(bounds) == 2 and bounds[0] > bounds[1]) \
                    or bounds[-1] >= available:
                raise InvestigationError("client_invalid", "client CPU list is outside the host CPU set")
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
    application_exit = artifact_dir / "application-exit.json"
    config_root = (run_dir / "config").resolve()
    resolved_runtime_files: list[dict[str, str]] = []
    targets: set[Path] = set()
    for source_value, target_value in runtime_files:
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
        if target in targets:
            raise InvestigationError("duplicate_runtime_file", "runtime file targets must be unique")
        targets.add(target)
        resolved_runtime_files.append({
            "source": str(source),
            "target": str(target),
            "sha256": _hash(source),
        })
    resolved_results = {
        variable: str(results_dir / filename)
        for variable, filename in result_files.items()
    }
    environment = sourced_environment()
    cache_home = _cache_home(environment)
    neoforge_version = _gradle_property(project, "neoforge_version") \
            if production and loader == "neoforge" else None
    neoforge_client_home = cache_home / "neoforge-client" / neoforge_version \
            if neoforge_version is not None else None
    launcher_profile_template = Path(__file__).resolve().parents[2] / "assets" / "empty-launcher-profiles.json"
    overlay_arguments, overlay = probe_overlay_command(
        loader,
        probe_packs,
        compile_artifacts,
        runtime_artifacts,
        mods_dir,
        run_dir,
        run_dir / "runtime-artifacts.json",
        project=project,
        production=production,
        neoforge_client_home=neoforge_client_home,
        launcher_profile_template=launcher_profile_template if neoforge_client_home else None,
    )
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
        "SQUINCH_INVESTIGATE_RUN_ID": run_id,
    })
    launch_task = "squinchProdClient" if production else "runClient"
    gradle_command = [
        "bash", "./gradlew", f":{loader}:{launch_task}",
        "--console=plain", "--no-daemon", *overlay_arguments,
    ]
    if production and loader == "neoforge":
        java_home = environment.get("JAVA_HOME")
        if not java_home:
            raise InvestigationError("client_invalid", "JAVA_HOME is required for NeoForge production client")
        assets_dir = Path(environment.get("GRADLE_USER_HOME", str(Path.home() / ".gradle"))) \
                / "caches" / "fabric-loom" / "assets"
        application_command = [sys.executable, "-m",
            "squinch_minecraft_investigate.neoforge_client",
            "--project", str(project),
            "--client-home", str(neoforge_client_home),
            "--assets-dir", str(assets_dir),
            "--run-dir", str(run_dir),
            "--version", neoforge_version,
            "--java", str(Path(java_home) / "bin" / "java"),
            "--", *gradle_command,
        ]
    else:
        application_command = gradle_command
    command = ([] if cpu_list is None else ["taskset", "-c", cpu_list]) + [
        "cage", "-d", "--", sys.executable, "-m",
        "squinch_minecraft_investigate.application_exit",
        "--output", str(application_exit), "--", *application_command,
    ]

    def prepare() -> None:
        for directory in (mods_dir, results_dir, display_runtime):
            directory.mkdir(parents=True, exist_ok=False)
        display_runtime.chmod(0o700)
        for record in resolved_runtime_files:
            target = Path(record["target"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(record["source"]), target)
        (run_dir / "options.txt").write_text(
            "narrator:0\nonboardAccessibility:false\n", encoding="utf-8"
        )

    def validate(state: dict) -> dict:
        runtime_mods = _inspect_runtime_mods(state)
        results = _inspect_results(state)
        state["runtime_mods"] = runtime_mods
        state["results"] = results
        for record in state["runtime_files"]:
            target = Path(record["target"])
            if not target.is_file() or target.is_symlink():
                raise InvestigationError(
                    "client_runtime_file_missing",
                    f"client runtime file is no longer a regular file: {target}",
                )
            record["final_sha256"] = _hash(target)
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
        poll_failure=_detect_terminal_failure,
        poll_complete=_results_complete,
        cleanup=_remove_display_runtime,
        state_fields={
            "display": {
                "backend": "headless",
                "runtime_root": str(display_root),
                "runtime_dir": str(display_runtime),
                "wayland_display": display_name,
            },
            "probe_environment": probe_environment,
            "launch_task": launch_task,
            "cpu_list": cpu_list,
            "result_files": resolved_results,
            "application_exit": str(application_exit),
            "runtime_files": resolved_runtime_files,
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
