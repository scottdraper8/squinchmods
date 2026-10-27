from __future__ import annotations

import datetime
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squinch_qa import manifest
from squinch_qa.artifacts import (
    is_valid_run_id,
    job_dir,
    make_run_id,
    run_dir,
)
from squinch_qa.errors import PlanError
from squinch_qa.executors import get_executor
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    Target,
    TestSpec,
)

SUPPORTED_PLAN_SCHEMA = 1


@dataclass
class RunState:
    plan: ExecutionPlan
    plan_bytes: bytes
    run_id: str
    qa_runs_dir: Path


def parse_plan_json(data: bytes) -> ExecutionPlan:
    """Reconstruct ExecutionPlan from the JSON produced by emit_plan_json."""
    doc = json.loads(data)

    schema = doc.get("schema")
    if schema != SUPPORTED_PLAN_SCHEMA:
        raise PlanError(
            f"unsupported plan schema {schema!r} (expected {SUPPORTED_PLAN_SCHEMA})"
        )

    mod_block = doc["mod"]
    profile_block = doc["profile"]

    # Build test specs from jobs list; deduplicate by id, preserving first-seen order
    seen_tests: dict[str, TestSpec] = {}
    for j in doc.get("jobs", []):
        tid = j["test"]["id"]
        if tid not in seen_tests:
            seen_tests[tid] = TestSpec(
                id=tid,
                config=j["test"].get("config", {}),
                origin_index=0,
            )

    profile = ResolvedProfile(
        name=profile_block["name"],
        resolved_from=profile_block["resolved_from"],
        tests=list(seen_tests.values()),
        max_jobs=profile_block["max_jobs"],
    )

    jobs: list[PlannedJob] = []
    for j in doc.get("jobs", []):
        t = j["target"]
        target = Target(
            id=t["id"],
            minecraft=t["minecraft"],
            loader=t["loader"],
            loader_version=t.get("loader_version"),
            java=t["java"],
        )
        jobs.append(
            PlannedJob(
                target=target,
                test_spec=seen_tests[j["test"]["id"]],
            )
        )

    return ExecutionPlan(
        mod_id=mod_block["id"],
        display_name=mod_block.get("display_name") or None,
        profile=profile,
        jobs=jobs,
    )


def create_run_state(
    plan_bytes: bytes,
    qa_runs_dir: Path,
    *,
    run_id: str | None = None,
) -> RunState:
    plan = parse_plan_json(plan_bytes)
    if run_id is not None and not is_valid_run_id(run_id):
        raise PlanError(f"invalid run_id {run_id!r}; expected <unix_ms>-<hex8>")
    return RunState(
        plan=plan,
        plan_bytes=plan_bytes,
        run_id=run_id or make_run_id(),
        qa_runs_dir=qa_runs_dir,
    )


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run_plan(
    state: RunState,
    repo_root: Path,
    mod_dir: Path,
) -> int:
    """Execute all jobs in the plan serially. Returns exit code (0 or 4)."""
    plan = state.plan

    qa_root = state.qa_runs_dir.parent
    qa_root.mkdir(parents=True, exist_ok=True)
    active_path = qa_root / "active.json"
    try:
        descriptor = os.open(active_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise PlanError(
            f"incomplete QA work must be resolved before another run: {active_path}"
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as active:
        json.dump({"schema_version": 1, "run_id": state.run_id}, active, sort_keys=True)
        active.write("\n")

    rdir = run_dir(state.qa_runs_dir, state.run_id)
    rdir.mkdir(parents=True, exist_ok=True)

    plan_path = rdir / "plan.json"
    plan_path.write_bytes(state.plan_bytes)

    _emit(
        {
            "type": "run_start",
            "run_id": state.run_id,
            "mod_id": plan.mod_id,
            "profile": plan.profile.name,
            "job_count": len(plan.jobs),
        }
    )

    job_results: dict[tuple[str, str], JobResult] = {}

    for job in plan.jobs:
        target_id = job.target.id
        test_id = job.test_spec.id
        jdir = job_dir(state.qa_runs_dir, state.run_id, target_id, test_id)
        jdir.mkdir(parents=True, exist_ok=True)

        ctx = JobContext(
            run_id=state.run_id,
            target_id=target_id,
            test_id=test_id,
            job_dir=jdir,
            test_config=job.test_spec.config,
            repo_root=repo_root,
            mod_dir=mod_dir,
            target=job.target,
        )

        started_at = _now_iso()
        try:
            executor_cls = get_executor(test_id)
            result = executor_cls().run(ctx)
        except NotImplementedError as exc:
            finished_at = _now_iso()
            result = JobResult(
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                duration_s=0.0,
                failure=FailureDetail(
                    reason="executor_not_implemented",
                    detail=str(exc),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - executor failures become job results
            finished_at = _now_iso()
            result = JobResult(
                status="error",
                started_at=started_at,
                finished_at=finished_at,
                duration_s=0.0,
                failure=FailureDetail(
                    reason="executor_exception",
                    detail=repr(exc),
                ),
            )

        job_results[(target_id, test_id)] = result

        _emit(
            {
                "type": "job_complete",
                "run_id": state.run_id,
                "target": target_id,
                "test": test_id,
                "status": result.status,
                "duration_s": result.duration_s,
            }
        )

    exit_code = manifest.emit_all(
        rdir,
        plan,
        job_results,
        repo_root=repo_root,
        mod_dir=mod_dir,
        run_id=state.run_id,
        plan_bytes=state.plan_bytes,
    )

    _emit(
        {
            "type": "run_complete",
            "run_id": state.run_id,
            "status": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
        }
    )
    active_path.unlink()

    return exit_code
