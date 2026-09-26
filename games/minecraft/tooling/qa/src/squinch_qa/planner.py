from __future__ import annotations

import json
from typing import TYPE_CHECKING

from squinch_qa.errors import PlanLimitExceeded, UnknownTarget
from squinch_qa.models import ExecutionPlan, PlannedJob

if TYPE_CHECKING:
    from squinch_qa.models import ModConfig, ResolvedProfile


def build_plan(
    mod: ModConfig,
    resolved: ResolvedProfile,
    selected_target: str | None,
) -> ExecutionPlan:
    """Build the selected target-by-test run plan."""
    target_by_id = {target.id: target for target in mod.targets}
    if selected_target is not None:
        if selected_target not in target_by_id:
            raise UnknownTarget(
                f"unknown target '{selected_target}'; available: {sorted(target_by_id)}"
            )
        targets = [target_by_id[selected_target]]
    else:
        targets = mod.targets

    jobs = [
        PlannedJob(target=target, test_spec=test)
        for target in targets
        for test in resolved.tests
    ]
    jobs.sort(key=lambda job: (job.target.id, job.test_spec.origin_index))
    if len(jobs) > resolved.max_jobs:
        raise PlanLimitExceeded(count=len(jobs), cap=resolved.max_jobs)

    return ExecutionPlan(
        mod_id=mod.mod_id,
        display_name=mod.display_name,
        profile=resolved,
        jobs=jobs,
    )


def emit_plan_json(plan: ExecutionPlan) -> str:
    """Serialize an execution plan deterministically."""
    sorted_jobs = sorted(
        plan.jobs,
        key=lambda job: (job.target.id, job.test_spec.origin_index),
    )

    def job_dict(job: PlannedJob) -> dict:
        target, test = job.target, job.test_spec
        return {
            "target": {
                "id": target.id,
                "java": target.java,
                "loader": target.loader,
                "loader_version": target.loader_version,
                "minecraft": target.minecraft,
            },
            "test": {"config": test.config, "id": test.id},
        }

    plan_dict = {
        "schema": 1,
        "mod": {
            "display_name": plan.display_name or "",
            "id": plan.mod_id,
        },
        "profile": {
            "max_jobs": plan.profile.max_jobs,
            "name": plan.profile.name,
            "resolved_from": plan.profile.resolved_from,
        },
        "jobs": [job_dict(job) for job in sorted_jobs],
    }
    return json.dumps(plan_dict, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
