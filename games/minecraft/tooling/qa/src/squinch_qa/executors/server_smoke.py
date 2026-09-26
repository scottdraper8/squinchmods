from __future__ import annotations

import datetime
import time

from squinch_qa.executors._gradle import (
    GradleEnvError,
    qa_gradle_args,
    resolve_gradle_env,
)
from squinch_qa.executors._server import (
    DEFAULT_SMOKE_TIMEOUT_S,
    ServerLaunchError,
    ServerNotReadyError,
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
)
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult


def _loader_from_target_id(target_id: str) -> str:
    return target_id.split("-")[0]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ServerSmokeExecutor:
    def run(self, ctx: JobContext) -> JobResult:
        started_at = _now_iso()
        t0 = time.monotonic()

        timeout_s: float = float(
            ctx.test_config.get("timeout_s", DEFAULT_SMOKE_TIMEOUT_S)
        )
        shutdown_timeout_s: float = float(ctx.test_config.get("shutdown_timeout_s", 15))
        loader = _loader_from_target_id(ctx.target_id)
        loader_run_dir = ctx.mod_dir / loader / "run"
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

        pre_write_eula(loader_run_dir)
        configure_qa_server_properties(
            loader_run_dir,
            level_name=qa_level_name(ctx.run_id, ctx.target_id, ctx.test_id),
        )

        try:
            env = resolve_gradle_env(ctx.repo_root)
        except GradleEnvError as e:
            return _result(
                "error", FailureDetail(reason="gradle-env-error", detail=str(e))
            )

        try:
            proc, log_path = launch_server(
                loader,
                ctx.mod_dir,
                env,
                logs_dir,
                gradle_args=qa_gradle_args(ctx.repo_root),
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
            crashes = collect_new_crash_reports(
                loader_run_dir, crash_dir, ignore_names=existing_crashes
            )
            if crashes:
                return _result(
                    "fail", FailureDetail(reason="crash-before-ready", detail=str(e))
                )
            return _result(
                "fail", FailureDetail(reason="server-not-ready", detail=str(e))
            )

        send_stop(proc)
        wait_for_exit(proc, shutdown_timeout_s)
        drain_stdout(proc, log_path)
        close_pipes(proc)

        crashes = collect_new_crash_reports(
            loader_run_dir, crash_dir, ignore_names=existing_crashes
        )
        if crashes:
            names = ", ".join(p.name for p in crashes)
            return _result("fail", FailureDetail(reason="crash-reports", detail=names))

        return _result("pass", None)
