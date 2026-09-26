from __future__ import annotations

import datetime
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squinch_qa import manifest
from squinch_qa.artifacts import (
    default_qa_root,
    is_valid_run_id,
    make_run_id,
    job_dir,
    run_dir,
    sha256_bytes,
)
from squinch_qa.errors import PlanError
from squinch_qa.executors import get_executor
from squinch_qa.executors.base import FailureDetail, JobContext, JobResult
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    SkippedEntry,
    SkippedTarget,
    Target,
    TestSpec,
)

SUPPORTED_PLAN_SCHEMA = 1


@dataclass
class RunState:
    plan: ExecutionPlan
    plan_bytes: bytes
    plan_sha256: str
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
                required=j["test"]["required"],
                requires=j["test"].get("requires", []),
                adapters={},
                expectations={},
                config=j["test"].get("config", {}),
                origin_index=0,
            )

    profile = ResolvedProfile(
        name=profile_block["name"],
        resolved_from=profile_block["resolved_from"],
        tests=list(seen_tests.values()),
        max_parallel=profile_block["max_parallel"],
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
            supported=True,
            capabilities=t.get("capabilities", []),
        )
        jobs.append(
            PlannedJob(
                target=target,
                test_spec=seen_tests[j["test"]["id"]],
                adapter=j.get("adapter"),
                expected_failure=j.get("expected_failure"),
                expectations=j["test"].get("expectations", {}),
            )
        )

    skipped = [
        SkippedEntry(
            target_id=s["target_id"],
            test_id=s["test_id"],
            reason=s["reason"],
        )
        for s in doc.get("skipped", [])
    ]

    skipped_targets = [
        SkippedTarget(
            target_id=s["target_id"],
            reason=s["reason"],
        )
        for s in doc.get("skipped_targets", [])
    ]

    return ExecutionPlan(
        mod_id=mod_block["id"],
        display_name=mod_block.get("display_name") or None,
        profile=profile,
        jobs=jobs,
        skipped=skipped,
        skipped_targets=skipped_targets,
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
        plan_sha256=sha256_bytes(plan_bytes),
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
    dry_run: bool = False,
    promote: bool = False,
    clean: bool = True,
) -> int:
    """Execute all jobs in the plan serially. Returns exit code (0 or 4)."""
    plan = state.plan

    if dry_run:
        from squinch_qa.planner import emit_plan_json

        sys.stdout.write(emit_plan_json(plan))
        return 0

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
            adapter=job.adapter,
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
        except Exception as exc:
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

    if promote and exit_code == 0:
        from squinch_qa.replace import promote_run, recover_pending

        qa_root = default_qa_root(repo_root)
        recover_pending(qa_root)
        _emit({"type": "promote_start", "run_id": state.run_id})
        promote_results = promote_run(qa_root, rdir)
        for r in promote_results:
            _emit(
                {
                    "type": "promote_job",
                    "mod_id": r.mod_id,
                    "target": r.target_id,
                    "test": r.test_id,
                    "promoted": r.promoted,
                    "reason": r.reason,
                }
            )
        _emit({"type": "promote_done", "run_id": state.run_id})
        if any(r.is_failure for r in promote_results):
            exit_code = 6

    if clean:
        from squinch_qa.cleanup import clean_qa

        try:
            actions = clean_qa(default_qa_root(repo_root))
            _emit({"type": "clean_done", "count": len(actions), "dry_run": False})
        except Exception as exc:
            _emit({"type": "clean_error", "error": str(exc)})

    # Emitted after promotion (not right after emit_all) so status/exit_code
    # reflect promotion's outcome too, not just the test run's.
    _emit(
        {
            "type": "run_complete",
            "run_id": state.run_id,
            "status": "pass" if exit_code == 0 else "fail",
            "exit_code": exit_code,
        }
    )

    return exit_code
