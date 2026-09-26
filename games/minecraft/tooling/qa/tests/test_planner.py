from __future__ import annotations

import json

import pytest

from squinch_qa.errors import PlanLimitExceeded, UnknownTarget
from squinch_qa.models import ModConfig, ResolvedProfile, Target, TestSpec
from squinch_qa.planner import build_plan, emit_plan_json


def _target(id: str, loader: str = "forge") -> Target:
    return Target(
        id=id,
        minecraft="1.20.1",
        loader=loader,
        loader_version="47.0.0",
        java=17,
    )


def _test_spec(id: str, origin_index: int = 0) -> TestSpec:
    return TestSpec(id=id, config={}, origin_index=origin_index)


def _profile(tests: list[TestSpec], max_jobs: int = 32) -> ResolvedProfile:
    return ResolvedProfile(
        name="default",
        resolved_from=["default"],
        tests=tests,
        max_jobs=max_jobs,
    )


def _mod(targets: list[Target]) -> ModConfig:
    return ModConfig(mod_id="test-mod", display_name="Test Mod", targets=targets)


class TestPlanLimits:
    def test_plan_limit_exceeded_raises(self):
        targets = [_target(f"forge-{index}") for index in range(3)]
        tests = [_test_spec(f"test-{index}", origin_index=index) for index in range(3)]
        with pytest.raises(PlanLimitExceeded) as exc_info:
            build_plan(_mod(targets), _profile(tests, max_jobs=1), None)
        assert exc_info.value.count == 9
        assert exc_info.value.cap == 1

    def test_plan_limit_message_includes_count_and_limit(self):
        targets = [_target(f"forge-{index}") for index in range(2)]
        tests = [_test_spec(f"test-{index}", origin_index=index) for index in range(3)]
        with pytest.raises(PlanLimitExceeded) as exc_info:
            build_plan(_mod(targets), _profile(tests, max_jobs=1), None)
        message = str(exc_info.value)
        assert "planned 6 jobs" in message
        assert "limit is 1" in message

    def test_at_limit_does_not_raise(self):
        plan = build_plan(
            _mod([_target("forge-1.20.1")]),
            _profile([_test_spec("build")], max_jobs=1),
            None,
        )
        assert len(plan.jobs) == 1


class TestTargetSelection:
    def test_target_filter_unknown_raises(self):
        mod = _mod([_target("forge-1.20.1")])
        with pytest.raises(UnknownTarget, match="nonexistent"):
            build_plan(mod, _profile([_test_spec("build")]), "nonexistent")

    def test_target_filter_selects_only_matching(self):
        mod = _mod([_target("forge-1.20.1"), _target("forge-1.21.4")])
        plan = build_plan(mod, _profile([_test_spec("build")]), "forge-1.20.1")
        assert len(plan.jobs) == 1
        assert plan.jobs[0].target.id == "forge-1.20.1"


class TestJobSortOrder:
    def test_sort_by_target_then_origin_index(self):
        targets = [_target("forge-1.21.4"), _target("forge-1.20.1")]
        tests = [
            _test_spec("server-smoke", origin_index=2),
            _test_spec("pregen", origin_index=1),
            _test_spec("build", origin_index=0),
        ]
        plan = build_plan(_mod(targets), _profile(tests), None)
        jobs = json.loads(emit_plan_json(plan))["jobs"]
        assert [job["target"]["id"] for job in jobs] == [
            "forge-1.20.1",
            "forge-1.20.1",
            "forge-1.20.1",
            "forge-1.21.4",
            "forge-1.21.4",
            "forge-1.21.4",
        ]
        assert [job["test"]["id"] for job in jobs[:3]] == [
            "build",
            "pregen",
            "server-smoke",
        ]


class TestEmitPlanJson:
    def test_schema_field_is_1(self):
        plan = build_plan(
            _mod([_target("forge-1.20.1")]), _profile([_test_spec("build")]), None
        )
        assert json.loads(emit_plan_json(plan))["schema"] == 1

    def test_trailing_newline(self):
        plan = build_plan(
            _mod([_target("forge-1.20.1")]), _profile([_test_spec("build")]), None
        )
        assert emit_plan_json(plan).endswith("\n")

    def test_sort_keys(self):
        plan = build_plan(
            _mod([_target("forge-1.20.1")]), _profile([_test_spec("build")]), None
        )
        output = emit_plan_json(plan)
        data = json.loads(output)
        redumped = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        assert output == redumped
