from __future__ import annotations

import datetime
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable

from squinch_qa.executors._gradle import (
    GradleEnvError,
    qa_gradle_args,
    resolve_gradle_env,
)
from squinch_qa.executors._server import (
    DEFAULT_PREGEN_TIMEOUT_S,
    ServerLaunchError,
    ServerNotReadyError,
    ToolNotDoneError,
    close_pipes,
    collect_new_crash_reports,
    configure_qa_server_properties,
    drain_stdout,
    existing_crash_report_names,
    launch_server,
    pre_write_eula,
    qa_level_name,
    send_stop,
    wait_for_exit,
    wait_for_ready,
    watch_for_tool_completion,
)
from squinch_qa.executors._forge_production import launch_forge_production_server
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult
from squinch_qa.pregen_tools import AcquisitionError, acquire_jar

# Maps preset name → chunk radius in blocks
PRESET_RADII: dict[str, int] = {
    "xs": 128,
    "s": 256,
    "m": 512,
    "l": 1024,
    "xl": 2048,
}


def _chunksmith_commands(preset: str) -> list[bytes]:
    r = PRESET_RADII.get(preset, 128)
    return [f"pregen add radius {r}\n".encode()]


def _chunky_commands(preset: str) -> list[bytes]:
    r = PRESET_RADII.get(preset, 128)
    return [f"chunky radius {r}\n".encode(), b"chunky start\n"]


TOOL_COMMANDS: dict[str, Callable[[str], list[bytes]]] = {
    "chunksmith": _chunksmith_commands,
    "chunky": _chunky_commands,
}

# These patterns must match the actual tool log output.
# Chunksmith emits "Pregeneration complete"; Chunky 1.3.x emits "Task finished".
TOOL_COMPLETION_PATTERNS: dict[str, str] = {
    "chunksmith": "Pregeneration complete",
    "chunky": "Task finished",
}


def _loader_from_target_id(target_id: str) -> str:
    return target_id.split("-")[0]


def _mc_version_from_target_id(target_id: str) -> str:
    return target_id.split("-", 1)[1]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _launch_pregen_server(
    *,
    loader: str,
    ctx: JobContext,
    env: dict[str, str],
    logs_dir: Path,
    tool_jar: Path,
    temp_root: Path,
) -> tuple:
    runtime = ctx.test_config.get("server_runtime")
    if runtime is None:
        runtime = "forge-production" if loader == "forge" else "gradle-dev"

    if runtime == "forge-production":
        if ctx.target is None or ctx.target.loader_version is None:
            raise ServerLaunchError(
                "Forge production pregen requires target loader_version"
            )
        return launch_forge_production_server(
            server_dir=temp_root / "server",
            mod_dir=ctx.mod_dir,
            tool_jar=tool_jar,
            minecraft_version=ctx.target.minecraft,
            forge_version=ctx.target.loader_version,
            java_major=ctx.target.java,
            env=env,
            logs_dir=logs_dir,
        )

    if runtime == "gradle-dev":
        proc, log_path = launch_server(
            loader,
            ctx.mod_dir,
            env,
            logs_dir,
            gradle_args=qa_gradle_args(ctx.repo_root),
        )
        return proc, log_path, ctx.mod_dir / loader / "run"

    raise ServerLaunchError(f"Unknown pregen server_runtime: {runtime!r}")


class PregenExecutor:
    def run(self, ctx: JobContext) -> JobResult:
        started_at = _now_iso()
        t0 = time.monotonic()

        cfg = ctx.test_config
        tool_preference: list[str] = cfg.get(
            "tool_preference", ["chunksmith", "chunky"]
        )
        preset: str = cfg.get("preset", "xs")
        timeout_s: float = float(cfg.get("timeout_s", DEFAULT_PREGEN_TIMEOUT_S))
        shutdown_timeout_s: float = float(cfg.get("shutdown_timeout_s", 15))

        loader = _loader_from_target_id(ctx.target_id)
        mc_version = _mc_version_from_target_id(ctx.target_id)
        loader_run_dir = ctx.mod_dir / loader / "run"
        level_name = qa_level_name(ctx.run_id, ctx.target_id, ctx.test_id)
        loader_run_mods = loader_run_dir / "mods"
        logs_dir = ctx.job_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "server.stdout.log"
        crash_dir = ctx.job_dir / "crash-reports"
        existing_crashes = existing_crash_report_names(loader_run_dir)

        def _result(
            status: str,
            failure: FailureDetail | None,
            tool_used: str | None = None,
            jar_sha256: str | None = None,
            artifacts: list[str] | None = None,
        ) -> JobResult:
            return JobResult(
                status=status,
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                logs=["logs/server.stdout.log"],
                artifacts=artifacts or [],
                failure=failure,
                tool_used=tool_used,
                jar_sha256=jar_sha256,
            )

        # ── Phase 1: Jar acquisition (fallback triggers here only) ───────────────
        acquired = None
        exhausted_tools: list[str] = []
        for tool_name in tool_preference:
            try:
                acquired = acquire_jar(tool_name, mc_version, loader)
                break
            except AcquisitionError as e:
                exhausted_tools.append(f"{tool_name}: {e}")

        if acquired is None:
            detail = "; ".join(exhausted_tools)
            return _result(
                "error",
                FailureDetail(reason="all-tools-acquisition-failed", detail=detail),
            )

        tool_used = acquired.tool_name
        jar_sha256 = acquired.sha256

        server_run_dir = loader_run_dir

        # ── Phase 2: Place jar for Gradle-dev runtimes ───────────────────────────
        if ctx.test_config.get("server_runtime") == "gradle-dev" or loader != "forge":
            loader_run_mods.mkdir(parents=True, exist_ok=True)
            jar_dest = loader_run_mods / acquired.path.name
            shutil.copy2(acquired.path, jar_dest)
            pre_write_eula(loader_run_dir)
            configure_qa_server_properties(loader_run_dir, level_name=level_name)

        # ── Phase 3: Resolve env ─────────────────────────────────────────────────
        try:
            env = resolve_gradle_env(ctx.repo_root)
        except GradleEnvError as e:
            return _result(
                "error",
                FailureDetail(reason="gradle-env-error", detail=str(e)),
                tool_used=tool_used,
                jar_sha256=jar_sha256,
            )

        with tempfile.TemporaryDirectory(prefix=f"squinch-pregen-{ctx.run_id}-") as td:
            # ── Phase 4: Launch server ───────────────────────────────────────────
            try:
                proc, log_path, server_run_dir = _launch_pregen_server(
                    loader=loader,
                    ctx=ctx,
                    env=env,
                    logs_dir=logs_dir,
                    tool_jar=acquired.path,
                    temp_root=Path(td),
                )
            except ServerLaunchError as e:
                # Tool jar was placed but server failed to start → test failure, not fallback
                return _result(
                    "fail",
                    FailureDetail(reason="launch-failed", detail=str(e)),
                    tool_used=tool_used,
                    jar_sha256=jar_sha256,
                )

            # ── Phase 5: Wait for server ready ───────────────────────────────────
            try:
                wait_for_ready(proc, log_path, timeout_s)
            except ServerNotReadyError as e:
                proc.kill()
                drain_stdout(proc, log_path)
                proc.wait()
                close_pipes(proc)
                ignore_names = (
                    existing_crashes if server_run_dir == loader_run_dir else set()
                )
                crashes = collect_new_crash_reports(
                    server_run_dir, crash_dir, ignore_names=ignore_names
                )
                reason = "crash-before-ready" if crashes else "server-not-ready"
                return _result(
                    "fail",
                    FailureDetail(reason=reason, detail=str(e)),
                    tool_used=tool_used,
                    jar_sha256=jar_sha256,
                )

            # ── Phase 6: Drive pregen tool via stdin ─────────────────────────────
            commands = TOOL_COMMANDS[tool_used](preset)
            try:
                for cmd in commands:
                    proc.stdin.write(cmd)
                    proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                proc.kill()
                drain_stdout(proc, log_path)
                proc.wait()
                close_pipes(proc)
                ignore_names = (
                    existing_crashes if server_run_dir == loader_run_dir else set()
                )
                collect_new_crash_reports(
                    server_run_dir, crash_dir, ignore_names=ignore_names
                )
                return _result(
                    "fail",
                    FailureDetail(reason="tool-command-delivery-failed", detail=str(e)),
                    tool_used=tool_used,
                    jar_sha256=jar_sha256,
                )

            completion_pattern = TOOL_COMPLETION_PATTERNS[tool_used]
            try:
                watch_for_tool_completion(proc, log_path, completion_pattern, timeout_s)
            except ToolNotDoneError as e:
                proc.kill()
                drain_stdout(proc, log_path)
                proc.wait()
                close_pipes(proc)
                ignore_names = (
                    existing_crashes if server_run_dir == loader_run_dir else set()
                )
                collect_new_crash_reports(
                    server_run_dir, crash_dir, ignore_names=ignore_names
                )
                # Tool was loaded but timed out / server exited → test failure, not fallback
                return _result(
                    "fail",
                    FailureDetail(reason="tool-timeout", detail=str(e)),
                    tool_used=tool_used,
                    jar_sha256=jar_sha256,
                )

            # ── Phase 7: Stop server, drain, copy world ──────────────────────────
            send_stop(proc)
            wait_for_exit(proc, shutdown_timeout_s)
            drain_stdout(proc, log_path)
            close_pipes(proc)

            world_dir_name = level_name if server_run_dir == loader_run_dir else "world"
            world_src = server_run_dir / world_dir_name
            world_dst = ctx.job_dir / "world"
            artifacts: list[str] = []
            if world_src.exists() and any(world_src.iterdir()):
                shutil.copytree(world_src, world_dst)
                artifacts.append("world")

            ignore_names = (
                existing_crashes if server_run_dir == loader_run_dir else set()
            )
            crashes = collect_new_crash_reports(
                server_run_dir, crash_dir, ignore_names=ignore_names
            )
            if crashes:
                names = ", ".join(p.name for p in crashes)
                return _result(
                    "fail",
                    FailureDetail(reason="crash-reports", detail=names),
                    tool_used=tool_used,
                    jar_sha256=jar_sha256,
                    artifacts=artifacts,
                )

        return _result(
            "pass",
            None,
            tool_used=tool_used,
            jar_sha256=jar_sha256,
            artifacts=artifacts,
        )
