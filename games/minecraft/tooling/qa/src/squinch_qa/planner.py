from __future__ import annotations

import dataclasses
import datetime
import json
from typing import TYPE_CHECKING

from squinch_qa.errors import ConfigError, MatrixLimitExceeded, UnknownTarget
from squinch_qa.models import ExecutionPlan, PlannedJob, SkippedEntry, SkippedTarget

if TYPE_CHECKING:
    from squinch_qa.models import ModConfig, ResolvedProfile


def build_plan(
    mod: ModConfig,
    resolved: ResolvedProfile,
    selected_target: str | None,
) -> ExecutionPlan:
    """Expand matrix, apply capability filter, enforce limits; return ExecutionPlan."""
    target_by_id = {t.id: t for t in mod.targets}

    if selected_target is not None:
        if selected_target not in target_by_id:
            raise UnknownTarget(
                f"unknown target '{selected_target}'; available: {sorted(target_by_id)}"
            )
        t = target_by_id[selected_target]
        if not t.supported:
            raise UnknownTarget(f"target '{selected_target}' has supported: false")
        active_targets = [t]
        skipped_targets: list[SkippedTarget] = []
    else:
        active_targets = [t for t in mod.targets if t.supported]
        skipped_targets = [
            SkippedTarget(target_id=t.id, reason="target marked supported: false")
            for t in mod.targets
            if not t.supported
        ]

    today = datetime.date.today()
    ef_lookup: dict[tuple[str, str], dict] = {}
    for ef in mod.expected_failures:
        expires_str = ef.expires
        expires_date = datetime.date.fromisoformat(expires_str) if expires_str else None
        ef_lookup[(ef.target, ef.test)] = {
            "expires": expires_str,
            "expired": expires_date is not None and expires_date < today,
            "reason": ef.reason,
        }

    jobs: list[PlannedJob] = []
    skipped: list[SkippedEntry] = []

    for target in active_targets:
        for test_spec in resolved.tests:
            missing = sorted(set(test_spec.requires) - set(target.capabilities))
            if missing:
                skipped.append(
                    SkippedEntry(
                        target_id=target.id,
                        test_id=test_spec.id,
                        reason=(
                            f"test '{test_spec.id}' requires capabilities {missing} "
                            f"not provided by target '{target.id}'"
                        ),
                    )
                )
                continue

            adapter: dict | None = None
            if test_spec.adapters:
                adapter = test_spec.adapters.get(target.loader)
                if adapter is None:
                    skipped.append(
                        SkippedEntry(
                            target_id=target.id,
                            test_id=test_spec.id,
                            reason=(
                                f"no adapter for loader '{target.loader}' "
                                f"on target '{target.id}' for test '{test_spec.id}'"
                            ),
                        )
                    )
                    continue

            ef = ef_lookup.get((target.id, test_spec.id))

            expectations = {
                **test_spec.expectations.get("default", {}),
                **test_spec.expectations.get("by_target", {}).get(target.id, {}),
            }

            jobs.append(
                PlannedJob(
                    target=target,
                    test_spec=test_spec,
                    adapter=adapter,
                    expected_failure=ef,
                    expectations=expectations,
                )
            )

    if len(jobs) > resolved.max_jobs:
        raise MatrixLimitExceeded(count=len(jobs), cap=resolved.max_jobs)

    if not (1 <= resolved.max_parallel <= resolved.max_jobs):
        raise ConfigError(
            f"max_parallel={resolved.max_parallel} must satisfy "
            f"1 <= max_parallel <= max_jobs={resolved.max_jobs}"
        )

    return ExecutionPlan(
        mod_id=mod.mod_id,
        display_name=mod.display_name,
        profile=resolved,
        jobs=jobs,
        skipped=skipped,
        skipped_targets=skipped_targets,
    )


def emit_plan_json(plan: ExecutionPlan) -> str:
    """Serialize ExecutionPlan to deterministic JSON string (with trailing newline)."""
    sorted_jobs = sorted(
        plan.jobs,
        key=lambda j: (j.target.id, j.test_spec.origin_index),
    )
    sorted_skipped = sorted(plan.skipped, key=lambda s: (s.target_id, s.test_id))
    sorted_skipped_targets = sorted(plan.skipped_targets, key=lambda s: s.target_id)

    def _job_dict(job: PlannedJob) -> dict:
        t, ts = job.target, job.test_spec
        return {
            "adapter": job.adapter,
            "expected_failure": job.expected_failure,
            "target": {
                "capabilities": sorted(t.capabilities),
                "id": t.id,
                "java": t.java,
                "loader": t.loader,
                "loader_version": t.loader_version,
                "minecraft": t.minecraft,
            },
            "test": {
                "config": ts.config,
                "expectations": job.expectations,
                "id": ts.id,
                "required": ts.required,
                "requires": sorted(ts.requires),
            },
        }

    plan_dict = {
        "schema": 1,
        "mod": {
            "display_name": plan.display_name or "",
            "id": plan.mod_id,
        },
        "profile": {
            "max_jobs": plan.profile.max_jobs,
            "max_parallel": plan.profile.max_parallel,
            "name": plan.profile.name,
            "resolved_from": plan.profile.resolved_from,
        },
        "jobs": [_job_dict(j) for j in sorted_jobs],
        "skipped": [dataclasses.asdict(s) for s in sorted_skipped],
        "skipped_targets": [dataclasses.asdict(s) for s in sorted_skipped_targets],
    }

    return json.dumps(plan_dict, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
