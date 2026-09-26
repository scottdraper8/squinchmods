from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from squinch_qa.config import load_parent_config
from squinch_qa.errors import ConfigError, PlanLimitExceeded, UnknownProfile
from squinch_qa.models import (
    ModConfig,
    ParentConfig,
    ProfileDef,
    ProfileOverride,
    Target,
    TestDef,
)
from squinch_qa.planner import build_plan
from squinch_qa.resolve import resolve_profile

from conftest import FIXTURES, REAL_REPO_ROOT


@pytest.fixture
def stable_parent() -> ParentConfig:
    """Stable profile/config fixture for profile and test-setting resolution."""
    return ParentConfig(
        default_profile="default",
        profiles={
            "quick": ProfileDef(tests=["build", "server-smoke"]),
            "default": ProfileDef(
                tests=["build", "server-smoke", "pregen"], max_jobs=32
            ),
            "extended": ProfileDef(extends="default", max_jobs=64),
        },
        tests={
            "pregen": {
                "config": {"preset": "xs", "tool_preference": ["chunksmith", "chunky"]},
            },
        },
    )


def _load_fixture_parent(tmp_path: Path, fixture_name: str) -> ParentConfig:
    """Load an on-disk parent fixture through parsing and schema validation."""
    squinch_dir = tmp_path / ".squinch"
    schema_dir = squinch_dir / "schema"
    schema_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / fixture_name, squinch_dir / "config.yml")
    shutil.copy(
        REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
        schema_dir / "global-config.schema.json",
    )
    return load_parent_config(tmp_path)


def _empty_mod(**kwargs) -> ModConfig:
    defaults = dict(
        mod_id="test-mod",
        targets=[
            Target(
                id="forge-1.20.1",
                minecraft="1.20.1",
                loader="forge",
                loader_version="47.4.0",
                java=17,
            )
        ],
        display_name="Test Mod",
    )
    defaults.update(kwargs)
    return ModConfig(**defaults)


class TestExtendsChain:
    def test_default_profile_direct(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "default")
        assert resolved.name == "default"
        assert resolved.resolved_from == ["default"]
        assert [test.id for test in resolved.tests] == [
            "build",
            "server-smoke",
            "pregen",
        ]

    def test_extended_extends_default(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "extended")
        assert resolved.resolved_from == ["default", "extended"]
        assert [test.id for test in resolved.tests] == [
            "build",
            "server-smoke",
            "pregen",
        ]
        assert resolved.max_jobs == 64

    def test_resolved_from_is_root_first(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "extended")
        assert resolved.resolved_from[0] == "default"
        assert resolved.resolved_from[-1] == "extended"

    def test_default_profile_used_when_none(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), None)
        assert resolved.name == "default"


class TestModOverrides:
    def test_add_appends_without_replacing(self, stable_parent):
        mod = _empty_mod(
            profiles={"default": ProfileOverride(add=["integration-test"])}
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        test_ids = [test.id for test in resolved.tests]
        assert test_ids == ["build", "server-smoke", "pregen", "integration-test"]

    def test_add_deduplicates(self, stable_parent):
        mod = _empty_mod(
            profiles={"default": ProfileOverride(add=["build", "new-test"])}
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        test_ids = [test.id for test in resolved.tests]
        assert test_ids.count("build") == 1
        assert "new-test" in test_ids

    def test_tests_replaces_list(self, stable_parent):
        mod = _empty_mod(
            profiles={"default": ProfileOverride(tests=[{"id": "only-this"}])}
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        assert [test.id for test in resolved.tests] == ["only-this"]

    def test_tests_can_override_config_for_one_profile(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "extended": ProfileOverride(
                    tests=[
                        {"id": "build"},
                        {
                            "id": "pregen",
                            "config": {"preset": "l", "timeout_s": 7200},
                        },
                    ]
                ),
            }
        )
        default = resolve_profile(stable_parent, mod, "default")
        extended = resolve_profile(stable_parent, mod, "extended")
        default_pregen = next(test for test in default.tests if test.id == "pregen")
        extended_pregen = next(test for test in extended.tests if test.id == "pregen")
        assert default_pregen.config["preset"] == "xs"
        assert extended_pregen.config["preset"] == "l"
        assert extended_pregen.config["timeout_s"] == 7200
        assert extended_pregen.config["tool_preference"] == ["chunksmith", "chunky"]

    def test_mod_override_in_parent_chain_flows_to_extended(self, stable_parent):
        mod = _empty_mod(profiles={"default": ProfileOverride(add=["behavior-test"])})
        default = resolve_profile(stable_parent, mod, "default")
        extended = resolve_profile(stable_parent, mod, "extended")
        expected = ["build", "server-smoke", "pregen", "behavior-test"]
        assert [test.id for test in default.tests] == expected
        assert [test.id for test in extended.tests] == expected

    def test_both_add_and_tests_raises(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(add=["extra"], tests=[{"id": "only-this"}]),
            }
        )
        with pytest.raises(ConfigError, match="both 'add' and 'tests'"):
            resolve_profile(stable_parent, mod, "default")


class TestCycleDetection:
    def test_parent_side_cycle(self):
        parent = ParentConfig(
            default_profile="alpha",
            profiles={
                "alpha": ProfileDef(tests=["build"], extends="beta"),
                "beta": ProfileDef(tests=["build"], extends="alpha"),
            },
        )
        with pytest.raises(ConfigError, match="cycle"):
            resolve_profile(parent, _empty_mod(), "alpha")

    def test_cycle_message_includes_chain(self):
        parent = ParentConfig(
            default_profile="alpha",
            profiles={
                "alpha": ProfileDef(tests=["build"], extends="beta"),
                "beta": ProfileDef(tests=["build"], extends="alpha"),
            },
        )
        with pytest.raises(ConfigError) as exc_info:
            resolve_profile(parent, _empty_mod(), "alpha")
        assert "alpha" in str(exc_info.value)
        assert "beta" in str(exc_info.value)

    def test_missing_extends_target(self):
        parent = ParentConfig(
            default_profile="base",
            profiles={"base": ProfileDef(tests=["build"], extends="nonexistent")},
        )
        with pytest.raises(ConfigError, match="nonexistent"):
            resolve_profile(parent, _empty_mod(), "base")


class TestQuickProfile:
    def test_uses_default_job_limit(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "quick")
        assert resolved.max_jobs == 256

    def test_check_list(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "quick")
        assert [test.id for test in resolved.tests] == ["build", "server-smoke"]


class TestUnknownProfile:
    def test_raises_with_available_profiles(self, stable_parent):
        with pytest.raises(UnknownProfile) as exc_info:
            resolve_profile(stable_parent, _empty_mod(), "nonexistent-profile")
        assert "nonexistent-profile" in str(exc_info.value)
        assert "default" in str(exc_info.value)


class TestTestConfigMerge:
    def test_parent_config_used_when_no_mod_override(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "default")
        pregen = next(test for test in resolved.tests if test.id == "pregen")
        assert pregen.config.get("preset") == "xs"

    def test_mod_config_wins_over_parent(self, stable_parent):
        mod = _empty_mod(
            tests={
                "pregen": TestDef(config={"preset": "large", "extra": "value"}),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        pregen = next(test for test in resolved.tests if test.id == "pregen")
        assert pregen.config["preset"] == "large"
        assert pregen.config["extra"] == "value"
        assert "tool_preference" in pregen.config

    def test_origin_index_preserved(self, stable_parent):
        resolved = resolve_profile(stable_parent, _empty_mod(), "default")
        for index, spec in enumerate(resolved.tests):
            assert spec.origin_index == index


class TestFixtureParentEndToEnd:
    def test_cyclic_extends_parent_rejected_end_to_end(self, tmp_path):
        parent = _load_fixture_parent(tmp_path, "cyclic-extends-parent.yml")
        with pytest.raises(
            ConfigError, match="cycle detected in profile extends chain"
        ):
            resolve_profile(parent, _empty_mod(), "alpha")

    def test_max_jobs_tight_parent_exceeds_plan_limit(self, tmp_path):
        parent = _load_fixture_parent(tmp_path, "max-jobs-tight-parent.yml")
        mod = _empty_mod()
        resolved = resolve_profile(parent, mod, "tiny")
        assert resolved.max_jobs == 1
        with pytest.raises(PlanLimitExceeded) as exc_info:
            build_plan(mod, resolved, None)
        assert exc_info.value.count == 2
        assert exc_info.value.cap == 1
