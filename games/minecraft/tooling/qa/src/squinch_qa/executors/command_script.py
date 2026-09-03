from __future__ import annotations

import datetime
import tempfile
import time
from pathlib import Path
from typing import Any

from squinch_qa.executors._forge_production import launch_forge_production_server
from squinch_qa.executors._gradle import (
    GradleEnvError,
    qa_gradle_args,
    resolve_gradle_env,
)
from squinch_qa.executors._server import (
    DEFAULT_SMOKE_TIMEOUT_S,
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
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult


def _loader_from_target_id(target_id: str) -> str:
    return target_id.split("-")[0]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _string_list(value: Any, *, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def _level_seed(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("level_seed must be a nonempty string or integer")
    seed = str(value)
    if not seed:
        raise ValueError("level_seed must be a nonempty string or integer")
    return seed


def _launch_command_server(
    *,
    loader: str,
    ctx: JobContext,
    env: dict[str, str],
    logs_dir: Path,
    temp_root: Path,
    level_name: str,
    level_seed: str | None,
    server_runtime: str,
):
    if server_runtime == "forge-production":
        if ctx.target is None or ctx.target.loader_version is None:
            raise ServerLaunchError(
                "Forge production command-script requires target loader_version"
            )
        return launch_forge_production_server(
            server_dir=temp_root / "server",
            mod_dir=ctx.mod_dir,
            tool_jar=None,
            minecraft_version=ctx.target.minecraft,
            forge_version=ctx.target.loader_version,
            java_major=ctx.target.java,
            env=env,
            logs_dir=logs_dir,
            server_properties={
                "level-name": level_name,
                **({"level-seed": level_seed} if level_seed is not None else {}),
            },
        )

    if server_runtime == "gradle-dev":
        proc, log_path = launch_server(
            loader,
            ctx.mod_dir,
            env,
            logs_dir,
            gradle_args=qa_gradle_args(ctx.repo_root),
        )
        return proc, log_path, ctx.mod_dir / loader / "run"

    raise ServerLaunchError(
        f"Unknown command-script server_runtime: {server_runtime!r}"
    )


class CommandScriptExecutor:
    def run(self, ctx: JobContext) -> JobResult:
        started_at = _now_iso()
        t0 = time.monotonic()

        cfg = dict(ctx.test_config)
        adapter = ctx.adapter or {}
        adapter_type = adapter.get("type")
        if adapter_type not in (None, "command-script"):
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                failure=FailureDetail(
                    reason="unsupported-adapter",
                    detail=f"{ctx.test_id} does not support adapter type {adapter_type!r}",
                ),
            )

        cfg.update({k: v for k, v in adapter.items() if k != "type"})

        try:
            commands = _string_list(cfg.get("commands"), key="commands")
            expect_output = _string_list(cfg.get("expect_output"), key="expect_output")
            level_seed = _level_seed(cfg.get("level_seed"))
        except ValueError as e:
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                failure=FailureDetail(
                    reason="invalid-command-script-config", detail=str(e)
                ),
            )

        if not commands or not expect_output:
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                failure=FailureDetail(
                    reason="invalid-command-script-config",
                    detail="commands and expect_output must both be non-empty",
                ),
            )

        timeout_s = float(cfg.get("timeout_s", DEFAULT_SMOKE_TIMEOUT_S))
        shutdown_timeout_s = float(cfg.get("shutdown_timeout_s", 15))
        loader = _loader_from_target_id(ctx.target_id)
        server_runtime = cfg.get("server_runtime")
        if server_runtime is None:
            server_runtime = "forge-production" if loader == "forge" else "gradle-dev"
        if server_runtime not in {"forge-production", "gradle-dev"}:
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                failure=FailureDetail(
                    reason="invalid-command-script-config",
                    detail=f"unknown server_runtime: {server_runtime!r}",
                ),
            )
        loader_run_dir = ctx.mod_dir / loader / "run"
        level_name = qa_level_name(ctx.run_id, ctx.target_id, ctx.test_id)
        logs_dir = ctx.job_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "server.stdout.log"
        crash_dir = ctx.job_dir / "crash-reports"
        existing_crashes = existing_crash_report_names(loader_run_dir)

        def _result(status: str, failure: FailureDetail | None) -> JobResult:
            return JobResult(
                status=status,
                started_at=started_at,
                finished_at=_now_iso(),
                duration_s=time.monotonic() - t0,
                logs=["logs/server.stdout.log"],
                artifacts=[],
                failure=failure,
                tool_used=None,
                jar_sha256=None,
            )

        if server_runtime == "gradle-dev":
            pre_write_eula(loader_run_dir)
            configure_qa_server_properties(
                loader_run_dir,
                level_name=level_name,
                properties=(
                    {"level-seed": level_seed} if level_seed is not None else None
                ),
            )

        try:
            env = resolve_gradle_env(ctx.repo_root)
        except GradleEnvError as e:
            return _result(
                "error", FailureDetail(reason="gradle-env-error", detail=str(e))
            )

        with tempfile.TemporaryDirectory(prefix=f"squinch-command-{ctx.run_id}-") as td:
            try:
                proc, log_path, server_run_dir = _launch_command_server(
                    loader=loader,
                    ctx=ctx,
                    env=env,
                    logs_dir=logs_dir,
                    temp_root=Path(td),
                    level_name=level_name,
                    level_seed=level_seed,
                    server_runtime=server_runtime,
                )
            except ServerLaunchError as e:
                return _result(
                    "error", FailureDetail(reason="launch-failed", detail=str(e))
                )

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
                return _result("fail", FailureDetail(reason=reason, detail=str(e)))

            try:
                for command in commands:
                    proc.stdin.write(f"{command}\n".encode())
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
                    FailureDetail(reason="command-delivery-failed", detail=str(e)),
                )

            try:
                for pattern in expect_output:
                    watch_for_tool_completion(proc, log_path, pattern, timeout_s)
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
                return _result(
                    "fail",
                    FailureDetail(reason="expected-output-not-seen", detail=str(e)),
                )

            send_stop(proc)
            wait_for_exit(proc, shutdown_timeout_s)
            drain_stdout(proc, log_path)
            close_pipes(proc)

            ignore_names = (
                existing_crashes if server_run_dir == loader_run_dir else set()
            )
            crashes = collect_new_crash_reports(
                server_run_dir, crash_dir, ignore_names=ignore_names
            )
            if crashes:
                names = ", ".join(p.name for p in crashes)
                return _result(
                    "fail", FailureDetail(reason="crash-reports", detail=names)
                )

        return _result("pass", None)
