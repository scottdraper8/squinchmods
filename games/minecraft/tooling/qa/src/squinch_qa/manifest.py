from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from squinch_qa.errors import ValidationError
from squinch_qa.executors.base import FailureDetail, JobResult
from squinch_qa.models import ExecutionPlan, PlannedJob


def _git_head_sha(path: Path) -> str | None:
    """Return HEAD SHA for the git repo containing path; None on any failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _effective_status(raw_status: str, planned_job: PlannedJob) -> str:
    """Promote 'fail' → 'expected_failure' when plan carries an unexpired EF."""
    if (
        raw_status == "fail"
        and planned_job.expected_failure is not None
        and not planned_job.expected_failure.get("expired", True)
    ):
        return "expected_failure"
    return raw_status


def _compute_exit_code(
    plan: ExecutionPlan,
    job_results: dict[tuple[str, str], JobResult],
    status_overrides: dict[tuple[str, str], str] | None = None,
) -> int:
    """Return 0 if all required jobs pass or expected_failure, else 4."""
    status_overrides = status_overrides or {}
    for job in plan.jobs:
        if not job.test_spec.required:
            continue
        key = (job.target.id, job.test_spec.id)
        result = job_results.get(key)
        if result is None:
            return 4
        eff = status_overrides.get(key, _effective_status(result.status, job))
        if eff in ("fail", "error"):
            return 4
    return 0


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )


def _build_per_job_manifest(
    run_id: str,
    plan: ExecutionPlan,
    job: PlannedJob,
    result: JobResult,
    status: str,
    world_sha256: str | None,
) -> dict:
    target = job.target
    return {
        "schema": 1,
        "run_id": run_id,
        "profile": plan.profile.name,
        "matrix_id": f"{target.id}/{job.test_spec.id}",
        "target": {
            "id": target.id,
            "java": target.java,
            "loader": target.loader,
            "loader_version": target.loader_version,
            "minecraft": target.minecraft,
        },
        "mod": {
            "id": plan.mod_id,
            "jar_sha256": result.jar_sha256,
        },
        "test": {
            "adapter": job.adapter,
            "expectations": job.expectations,
            "expected_failure": job.expected_failure,
            "id": job.test_spec.id,
            "required": job.test_spec.required,
            "status": status,
        },
        "world_sha256": world_sha256,
    }


def _build_per_job_result(
    status: str, result: JobResult, failure: FailureDetail | None
) -> dict:
    doc: dict = {
        "status": status,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_s": result.duration_s,
        "logs": result.logs,
        "artifacts": result.artifacts,
        "failure": (
            {"reason": failure.reason, "detail": failure.detail}
            if failure is not None
            else None
        ),
    }
    if result.tool_used is not None:
        doc["tool_used"] = result.tool_used
    return doc


def emit_all(
    run_dir: Path,
    plan: ExecutionPlan,
    job_results: dict[tuple[str, str], JobResult],
    *,
    repo_root: Path,
    mod_dir: Path,
    run_id: str,
    plan_bytes: bytes,
) -> int:
    """Write all manifest and result files for a completed run. Returns exit code."""
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    repo_commit = _git_head_sha(repo_root)
    mod_commit = _git_head_sha(mod_dir)

    job_refs: list[dict] = []
    counts: dict[str, int] = {"pass": 0, "fail": 0, "error": 0, "expected_failure": 0}
    total_duration = 0.0
    status_overrides: dict[tuple[str, str], str] = {}

    for job in plan.jobs:
        key = (job.target.id, job.test_spec.id)
        result = job_results.get(key)
        if result is None:
            continue

        jdir = run_dir / "jobs" / job.target.id / job.test_spec.id
        jdir.mkdir(parents=True, exist_ok=True)

        eff = _effective_status(result.status, job)
        failure = result.failure

        world_sha256 = None
        if "world" in result.artifacts:
            # Lazy import: only jobs that actually produced a world pay for this,
            # and it keeps replace/ out of the manifest module's own import graph.
            from squinch_qa.replace.world_hash import world_hash

            try:
                world_sha256 = world_hash(jdir / "world")
            except ValidationError as e:
                eff = "error"
                failure = FailureDetail(reason="world_validation_failed", detail=str(e))
                status_overrides[key] = eff

        _write_json(
            jdir / "manifest.json",
            _build_per_job_manifest(run_id, plan, job, result, eff, world_sha256),
        )
        _write_json(jdir / "result.json", _build_per_job_result(eff, result, failure))

        counts[eff] = counts.get(eff, 0) + 1
        total_duration += result.duration_s

        job_refs.append(
            {
                "manifest": f"jobs/{job.target.id}/{job.test_spec.id}/manifest.json",
                "matrix_id": f"{job.target.id}/{job.test_spec.id}",
                "result": f"jobs/{job.target.id}/{job.test_spec.id}/result.json",
                "status": eff,
                "target": job.target.id,
                "test": job.test_spec.id,
            }
        )

    exit_code = _compute_exit_code(plan, job_results, status_overrides)

    _write_json(
        run_dir / "qa-manifest.json",
        {
            "schema": 1,
            "run_id": run_id,
            "profile": plan.profile.name,
            "mod_id": plan.mod_id,
            "plan_sha256": plan_sha256,
            "repo_commit": repo_commit,
            "mod_commit": mod_commit,
            "jobs": job_refs,
        },
    )

    _write_json(
        run_dir / "result.json",
        {
            "run_id": run_id,
            "status": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
            "counts": counts,
            "duration_s": total_duration,
        },
    )

    return exit_code
