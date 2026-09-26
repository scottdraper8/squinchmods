from __future__ import annotations

import datetime
import shutil
import time
from pathlib import Path

from squinch_qa.artifacts import sha256_file
from squinch_qa.executors._gradle import (
    GradleEnvError,
    qa_gradle_args,
    resolve_gradle_env,
    run_gradle,
)
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult


def _loader_from_target_id(target_id: str) -> str:
    """Extract loader name from target ID (e.g. 'forge-1.20.1' → 'forge')."""
    return target_id.split("-")[0]


def _find_primary_jar(libs_dir: Path) -> Path | None:
    """Return the primary jar, excluding -sources and -dev jars."""
    candidates = [
        p
        for p in libs_dir.glob("*.jar")
        if not (p.stem.endswith("-sources") or p.stem.endswith("-dev"))
    ]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class BuildExecutor:
    def run(self, ctx: JobContext) -> JobResult:
        started_at = _now_iso()
        t0 = time.monotonic()

        logs_dir = ctx.job_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir = ctx.job_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = logs_dir / "gradle.stdout.log"
        stderr_log = logs_dir / "gradle.stderr.log"

        log_paths = [
            f"logs/{stdout_log.name}",
            f"logs/{stderr_log.name}",
        ]

        loader = _loader_from_target_id(ctx.target_id)
        gradle_task = f":{loader}:build"

        try:
            env = resolve_gradle_env(ctx.repo_root)
        except GradleEnvError as exc:
            finished_at = _now_iso()
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                duration_s=time.monotonic() - t0,
                logs=log_paths,
                failure=FailureDetail(
                    reason="gradle_env_error",
                    detail=str(exc),
                ),
            )

        returncode = run_gradle(
            args=qa_gradle_args(ctx.repo_root) + [gradle_task],
            cwd=ctx.mod_dir,
            env=env,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )

        if returncode != 0:
            finished_at = _now_iso()
            return JobResult(
                status="fail",
                started_at=started_at,
                finished_at=finished_at,
                duration_s=time.monotonic() - t0,
                logs=log_paths,
                failure=FailureDetail(
                    reason="gradle_build_failed",
                    detail=f"./gradlew {gradle_task} exited with code {returncode}",
                ),
            )

        libs_dir = ctx.mod_dir / loader / "build" / "libs"
        primary_jar = _find_primary_jar(libs_dir)

        if primary_jar is None:
            finished_at = _now_iso()
            return JobResult(
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                duration_s=time.monotonic() - t0,
                logs=log_paths,
                failure=FailureDetail(
                    reason="jar_not_found",
                    detail=f"No primary jar found in {libs_dir}",
                ),
            )

        dest_jar = artifacts_dir / primary_jar.name
        shutil.copy2(primary_jar, dest_jar)
        jar_sha256 = sha256_file(dest_jar)

        finished_at = _now_iso()
        return JobResult(
            status="pass",
            started_at=started_at,
            finished_at=finished_at,
            duration_s=time.monotonic() - t0,
            logs=log_paths,
            artifacts=[f"artifacts/{dest_jar.name}"],
            jar_sha256=jar_sha256,
        )
