from __future__ import annotations

import json

import pytest

from squinch_qa.errors import ConfigError, MatrixLimitExceeded, UnknownTarget
from squinch_qa.models import (
    ExpectedFailure,
    ModConfig,
    ResolvedProfile,
    Target,
    TestSpec,
)
from squinch_qa.planner import build_plan, emit_plan_json


def _target(
    id: str,
    loader: str = "forge",
    capabilities: list[str] | None = None,
    supported: bool = True,
) -> Target:
    return Target(
        id=id,
        minecraft="1.20.1",
        loader=loader,
        loader_version="47.0.0",
        java=17,
        supported=supported,
        capabilities=capabilities or [],
    )


def _test_spec(
    id: str,
    origin_index: int = 0,
    requires: list[str] | None = None,
    adapters: dict | None = None,
    expectations: dict | None = None,
    required: bool = True,
) -> TestSpec:
    return TestSpec(
        id=id,
        required=required,
        requires=requires or [],
        adapters=adapters or {},
        expectations=expectations or {},
        config={},
        origin_index=origin_index,
    )


def _profile(
    tests: list[TestSpec],
    max_parallel: int = 4,
    max_jobs: int = 32,
) -> ResolvedProfile:
    return ResolvedProfile(
        name="default",
        resolved_from=["default"],
        tests=tests,
        max_parallel=max_parallel,
        max_jobs=max_jobs,
    )


def _mod(
    targets: list[Target],
    tests: dict | None = None,
    expected_failures: list[ExpectedFailure] | None = None,
) -> ModConfig:
    return ModConfig(
        mod_id="test-mod",
        display_name="Test Mod",
        targets=targets,
        tests=tests or {},
        expected_failures=expected_failures or [],
    )


class TestCapabilityFilter:
    def test_missing_capability_produces_skip(self):
        fabric = _target(
            "fabric-1.20.1", loader="fabric", capabilities=["command-script", "server"]
        )
        gametest = _test_spec("gametest-test", requires=["gametest"])
        mod = _mod([fabric])
        resolved = _profile([gametest])

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 0
        assert len(plan.skipped) == 1
        entry = plan.skipped[0]
        assert entry.target_id == "fabric-1.20.1"
        assert entry.test_id == "gametest-test"
        assert "gametest" in entry.reason

    def test_sufficient_capabilities_produces_job(self):
        forge = _target("forge-1.20.1", capabilities=["gametest", "server"])
        gametest = _test_spec("gametest-test", requires=["gametest"])
        mod = _mod([forge])
        resolved = _profile([gametest])

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 1
        assert len(plan.skipped) == 0

    def test_skip_reason_lists_missing_capabilities(self):
        target = _target("forge-1.20.1", capabilities=[])
        test = _test_spec("multi-req", requires=["gametest", "worldgen"])
        mod = _mod([target])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        reason = plan.skipped[0].reason
        assert "gametest" in reason
        assert "worldgen" in reason


class TestAdapterFilter:
    def test_adapter_found_attached_to_job(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec("adapter-test", adapters={"forge": {"type": "forge-runner"}})
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 1
        assert plan.jobs[0].adapter == {"type": "forge-runner"}

    def test_no_adapter_for_loader_produces_skip(self):
        fabric = _target("fabric-1.20.1", loader="fabric")
        test = _test_spec("adapter-test", adapters={"forge": {"type": "forge-runner"}})
        mod = _mod([fabric])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 0
        assert len(plan.skipped) == 1
        entry = plan.skipped[0]
        assert "fabric" in entry.reason
        assert "adapter-test" in entry.reason

    def test_no_adapters_on_test_passes_through(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec("plain-test")
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 1
        assert plan.jobs[0].adapter is None


class TestExpectationResolution:
    def test_no_expectations_declared_resolves_empty(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec("plain-test")
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.jobs[0].expectations == {}

    def test_default_only_applies_when_no_by_target_override(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec(
            "terrain-sanity",
            expectations={"default": {"min_biomes_seen": 8}},
        )
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.jobs[0].expectations == {"min_biomes_seen": 8}

    def test_by_target_override_wins_for_matching_target(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec(
            "terrain-sanity",
            expectations={
                "default": {"min_biomes_seen": 8},
                "by_target": {"forge-1.20.1": {"min_biomes_seen": 6}},
            },
        )
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.jobs[0].expectations == {"min_biomes_seen": 6}

    def test_by_target_override_for_other_target_does_not_apply(self):
        fabric = _target("fabric-1.20.1", loader="fabric")
        test = _test_spec(
            "terrain-sanity",
            expectations={
                "default": {"min_biomes_seen": 8},
                "by_target": {"forge-1.20.1": {"min_biomes_seen": 6}},
            },
        )
        mod = _mod([fabric])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.jobs[0].expectations == {"min_biomes_seen": 8}

    def test_by_target_adds_keys_not_present_in_default(self):
        forge = _target("forge-1.20.1", loader="forge")
        test = _test_spec(
            "terrain-sanity",
            expectations={
                "default": {"min_biomes_seen": 8},
                "by_target": {"forge-1.20.1": {"max_ticks": 500}},
            },
        )
        mod = _mod([forge])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.jobs[0].expectations == {"min_biomes_seen": 8, "max_ticks": 500}


class TestMatrixLimits:
    def test_matrix_limit_exceeded_raises(self):
        targets = [_target(f"forge-{i}") for i in range(3)]
        tests = [_test_spec(f"test-{i}", origin_index=i) for i in range(3)]
        mod = _mod(targets)
        resolved = _profile(tests, max_parallel=1, max_jobs=1)

        with pytest.raises(MatrixLimitExceeded) as exc_info:
            build_plan(mod, resolved, None)
        err = exc_info.value
        assert err.count == 9
        assert err.cap == 1

    def test_matrix_limit_message_includes_count_and_cap(self):
        targets = [_target(f"forge-{i}") for i in range(2)]
        tests = [_test_spec(f"test-{i}", origin_index=i) for i in range(3)]
        mod = _mod(targets)
        resolved = _profile(tests, max_parallel=1, max_jobs=1)

        with pytest.raises(MatrixLimitExceeded) as exc_info:
            build_plan(mod, resolved, None)
        msg = str(exc_info.value)
        assert "planned 6 jobs" in msg
        assert "cap is 1" in msg

    def test_at_limit_does_not_raise(self):
        targets = [_target("forge-1.20.1")]
        tests = [_test_spec("build")]
        mod = _mod(targets)
        resolved = _profile(tests, max_parallel=1, max_jobs=1)

        plan = build_plan(mod, resolved, None)
        assert len(plan.jobs) == 1

    def test_invalid_max_parallel_raises(self):
        targets = [_target("forge-1.20.1")]
        tests = [_test_spec("build")]
        mod = _mod(targets)
        resolved = _profile(tests, max_parallel=10, max_jobs=1)

        with pytest.raises(ConfigError, match="max_parallel"):
            build_plan(mod, resolved, None)


class TestUnsupportedTargets:
    def test_unsupported_target_goes_to_skipped_targets(self):
        supported = _target("forge-1.20.1", supported=True)
        unsupported = _target("forge-old", supported=False)
        test = _test_spec("build")
        mod = _mod([supported, unsupported])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        job_target_ids = {j.target.id for j in plan.jobs}
        assert "forge-1.20.1" in job_target_ids
        assert "forge-old" not in job_target_ids
        assert any(s.target_id == "forge-old" for s in plan.skipped_targets)

    def test_skipped_target_reason(self):
        unsupported = _target("forge-old", supported=False)
        test = _test_spec("build")
        mod = _mod([unsupported])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        assert plan.skipped_targets[0].reason == "target marked supported: false"

    def test_target_filter_on_unsupported_raises(self):
        unsupported = _target("forge-old", supported=False)
        test = _test_spec("build")
        mod = _mod([unsupported])
        resolved = _profile([test])

        with pytest.raises(UnknownTarget, match="supported: false"):
            build_plan(mod, resolved, "forge-old")

    def test_target_filter_unknown_raises(self):
        target = _target("forge-1.20.1")
        test = _test_spec("build")
        mod = _mod([target])
        resolved = _profile([test])

        with pytest.raises(UnknownTarget, match="nonexistent"):
            build_plan(mod, resolved, "nonexistent")

    def test_target_filter_selects_only_matching(self):
        t1 = _target("forge-1.20.1")
        t2 = _target("forge-1.21.4")
        test = _test_spec("build")
        mod = _mod([t1, t2])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, "forge-1.20.1")
        assert len(plan.jobs) == 1
        assert plan.jobs[0].target.id == "forge-1.20.1"


class TestExpectedFailures:
    @pytest.mark.parametrize(
        ("expires", "expected_expired"),
        [
            pytest.param(None, False, id="no-expiry"),
            pytest.param("2020-01-01", True, id="expired"),
            pytest.param("2099-12-31", False, id="not-yet-expired"),
        ],
    )
    def test_expected_failure_expiry_flagged(self, expires, expected_expired):
        target = _target("forge-1.20.1")
        test = _test_spec("flaky-test")
        ef = ExpectedFailure(
            target="forge-1.20.1",
            test="flaky-test",
            reason="known flakey in CI",
            expires=expires,
        )
        mod = _mod([target], expected_failures=[ef])
        resolved = _profile([test])

        plan = build_plan(mod, resolved, None)
        job = plan.jobs[0]
        assert job.expected_failure is not None
        assert job.expected_failure["reason"] == "known flakey in CI"
        assert job.expected_failure["expired"] is expected_expired
        # Expected-failure jobs stay in the plan, not skipped, regardless of expiry
        assert len(plan.jobs) == 1
        assert len(plan.skipped) == 0


class TestJobSortOrder:
    def test_sort_by_target_then_origin_index_not_alphabetical(self):
        """Jobs sorted by (target_id, origin_index): profile order preserved per target."""
        t1 = _target("forge-1.20.1")
        t2 = _target("forge-1.21.4")
        # Tests in profile order: build(0), pregen(1), server-smoke(2)
        # "server-smoke" < "build" alphabetically but should appear after "build"
        build = _test_spec("build", origin_index=0)
        pregen = _test_spec("pregen", origin_index=1)
        server_smoke = _test_spec("server-smoke", origin_index=2)
        mod = _mod([t1, t2])
        resolved = _profile([build, pregen, server_smoke])

        plan = build_plan(mod, resolved, None)
        json_str = emit_plan_json(plan)
        data = json.loads(json_str)
        jobs = data["jobs"]

        # All forge-1.20.1 jobs come before forge-1.21.4 (target_id sort)
        forge_120_indices = [
            i for i, j in enumerate(jobs) if j["target"]["id"] == "forge-1.20.1"
        ]
        forge_214_indices = [
            i for i, j in enumerate(jobs) if j["target"]["id"] == "forge-1.21.4"
        ]
        assert max(forge_120_indices) < min(forge_214_indices)

        # Within forge-1.20.1: profile order (build, pregen, server-smoke), not alphabetical
        forge_120_tests = [jobs[i]["test"]["id"] for i in forge_120_indices]
        assert forge_120_tests == ["build", "pregen", "server-smoke"]
        # Note: alphabetical would be ["build", "pregen", "server-smoke"] in this case,
        # so verify that if we had pregen before build in profile, that order is preserved
        rev_build = _test_spec("build", origin_index=2)
        rev_pregen = _test_spec("pregen", origin_index=0)
        rev_server = _test_spec("server-smoke", origin_index=1)
        mod2 = _mod([t1])
        resolved2 = _profile([rev_pregen, rev_server, rev_build])
        plan2 = build_plan(mod2, resolved2, None)
        data2 = json.loads(emit_plan_json(plan2))
        test_ids2 = [j["test"]["id"] for j in data2["jobs"]]
        # origin_index order: pregen(0), server-smoke(1), build(2)
        assert test_ids2 == ["pregen", "server-smoke", "build"]


class TestEmitPlanJson:
    def test_schema_field_is_1(self):
        target = _target("forge-1.20.1")
        test = _test_spec("build")
        mod = _mod([target])
        resolved = _profile([test])
        plan = build_plan(mod, resolved, None)
        data = json.loads(emit_plan_json(plan))
        assert data["schema"] == 1

    def test_trailing_newline(self):
        target = _target("forge-1.20.1")
        test = _test_spec("build")
        mod = _mod([target])
        resolved = _profile([test])
        plan = build_plan(mod, resolved, None)
        output = emit_plan_json(plan)
        assert output.endswith("\n")

    def test_sort_keys(self):
        target = _target("forge-1.20.1")
        test = _test_spec("build")
        mod = _mod([target])
        resolved = _profile([test])
        plan = build_plan(mod, resolved, None)
        output = emit_plan_json(plan)
        # Re-parse and re-dump with sort_keys to verify keys are sorted
        data = json.loads(output)
        import json as _json

        re_dumped = (
            _json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        )
        assert output == re_dumped

    def test_capabilities_sorted_in_output(self):
        target = _target(
            "forge-1.20.1", capabilities=["worldgen", "command-script", "server"]
        )
        test = _test_spec("build")
        mod = _mod([target])
        resolved = _profile([test])
        plan = build_plan(mod, resolved, None)
        data = json.loads(emit_plan_json(plan))
        caps = data["jobs"][0]["target"]["capabilities"]
        assert caps == sorted(caps)

    def test_resolved_expectations_surfaced_in_job_test_block(self):
        target = _target("forge-1.20.1")
        test = _test_spec(
            "terrain-sanity",
            expectations={
                "default": {"min_biomes_seen": 8},
                "by_target": {"forge-1.20.1": {"min_biomes_seen": 6}},
            },
        )
        mod = _mod([target])
        resolved = _profile([test])
        plan = build_plan(mod, resolved, None)
        data = json.loads(emit_plan_json(plan))
        assert data["jobs"][0]["test"]["expectations"] == {"min_biomes_seen": 6}
