from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from squinch_qa.errors import ConfigError, MatrixLimitExceeded, UnknownProfile
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
from squinch_qa.config import load_parent_config


@pytest.fixture
def stable_parent() -> ParentConfig:
    """
    Dedicated, stable parent config fixture that mirrors the shape of the real
    .squinch/config.yml (extends chain default -> pre-pr -> release, a dev
    profile with no explicit limits, and a test-config default for "pregen")
    without depending on the production file. Future edits to the real repo
    config (renaming a test, changing max_jobs) must not silently change what
    these tests assert.
    """
    return ParentConfig(
        default_profile="default",
        profiles={
            "dev": ProfileDef(tests=["build", "server-smoke"]),
            "default": ProfileDef(
                tests=["build", "server-smoke", "pregen"],
                max_parallel=4,
                max_jobs=32,
            ),
            "pre-pr": ProfileDef(extends="default", max_parallel=2, max_jobs=64),
            "release": ProfileDef(extends="pre-pr", max_parallel=2, max_jobs=128),
        },
        tests={
            "pregen": {
                "config": {"preset": "xs", "tool_preference": ["chunksmith", "chunky"]},
            },
        },
    )


def _load_fixture_parent(tmp_path: Path, fixture_name: str) -> ParentConfig:
    """
    Copy an on-disk fixture parent config plus the real schema into a temp
    repo root and load it through the full load_parent_config pipeline (YAML
    parse + schema validation). Used to prove these fixtures are genuinely
    schema-valid-but-semantically-rejected configs, end to end.
    """
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
                supported=True,
                capabilities=[],
            )
        ],
        display_name="Test Mod",
    )
    defaults.update(kwargs)
    return ModConfig(**defaults)


class TestExtendsChain:
    def test_default_profile_direct(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "default")
        assert resolved.name == "default"
        assert resolved.resolved_from == ["default"]
        test_ids = [t.id for t in resolved.tests]
        assert test_ids == ["build", "server-smoke", "pregen"]

    def test_pre_pr_extends_default(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "pre-pr")
        assert resolved.resolved_from == ["default", "pre-pr"]
        # pre-pr inherits default's tests
        test_ids = [t.id for t in resolved.tests]
        assert test_ids == ["build", "server-smoke", "pregen"]
        assert resolved.max_parallel == 2
        assert resolved.max_jobs == 64

    def test_release_extends_pre_pr_extends_default(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "release")
        assert resolved.resolved_from == ["default", "pre-pr", "release"]
        assert resolved.max_jobs == 128

    def test_resolved_from_is_root_first(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "release")
        assert resolved.resolved_from[0] == "default"
        assert resolved.resolved_from[-1] == "release"

    def test_default_profile_used_when_none(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, None)
        assert resolved.name == "default"


class TestModOverrides:
    def test_add_appends_without_replacing(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(add=["integration-test"]),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        test_ids = [t.id for t in resolved.tests]
        # Original tests preserved, new one appended
        assert "build" in test_ids
        assert "server-smoke" in test_ids
        assert "pregen" in test_ids
        assert test_ids[-1] == "integration-test"

    def test_add_deduplicates(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(add=["build", "new-test"]),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        test_ids = [t.id for t in resolved.tests]
        assert test_ids.count("build") == 1
        assert "new-test" in test_ids

    def test_tests_replaces_list(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(
                    tests=[{"id": "only-this", "required": True}]
                ),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        test_ids = [t.id for t in resolved.tests]
        assert test_ids == ["only-this"]

    def test_tests_sets_required_flag(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(
                    tests=[
                        {"id": "required-test", "required": True},
                        {"id": "advisory-test", "required": False},
                    ]
                ),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        by_id = {t.id: t for t in resolved.tests}
        assert by_id["required-test"].required is True
        assert by_id["advisory-test"].required is False

    def test_tests_can_override_config_for_one_profile(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "pre-pr": ProfileOverride(
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
        pre_pr = resolve_profile(stable_parent, mod, "pre-pr")

        default_pregen = next(t for t in default.tests if t.id == "pregen")
        pre_pr_pregen = next(t for t in pre_pr.tests if t.id == "pregen")
        assert default_pregen.config["preset"] == "xs"
        assert pre_pr_pregen.config["preset"] == "l"
        assert pre_pr_pregen.config["timeout_s"] == 7200
        assert pre_pr_pregen.config["tool_preference"] == ["chunksmith", "chunky"]

    def test_mod_override_in_parent_chain_flows_to_release(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "pre-pr": ProfileOverride(add=["behavior-test"]),
            }
        )

        pre_pr = resolve_profile(stable_parent, mod, "pre-pr")
        release = resolve_profile(stable_parent, mod, "release")

        assert [t.id for t in pre_pr.tests] == [
            "build",
            "server-smoke",
            "pregen",
            "behavior-test",
        ]
        assert [t.id for t in release.tests] == [
            "build",
            "server-smoke",
            "pregen",
            "behavior-test",
        ]

    def test_both_add_and_tests_raises(self, stable_parent):
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(
                    add=["extra"],
                    tests=[{"id": "only-this", "required": True}],
                ),
            }
        )
        with pytest.raises(ConfigError, match="both 'add' and 'tests'"):
            resolve_profile(stable_parent, mod, "default")


class TestCycleDetection:
    def test_parent_side_cycle(self):
        cyclic_parent = ParentConfig(
            default_profile="alpha",
            profiles={
                "alpha": ProfileDef(tests=["build"], extends="beta"),
                "beta": ProfileDef(tests=["build"], extends="alpha"),
            },
        )
        mod = _empty_mod()
        with pytest.raises(ConfigError, match="cycle"):
            resolve_profile(cyclic_parent, mod, "alpha")

    def test_cycle_message_includes_chain(self):
        cyclic_parent = ParentConfig(
            default_profile="alpha",
            profiles={
                "alpha": ProfileDef(tests=["build"], extends="beta"),
                "beta": ProfileDef(tests=["build"], extends="alpha"),
            },
        )
        mod = _empty_mod()
        with pytest.raises(ConfigError) as exc_info:
            resolve_profile(cyclic_parent, mod, "alpha")
        msg = str(exc_info.value)
        assert "alpha" in msg
        assert "beta" in msg

    def test_missing_extends_target(self):
        parent = ParentConfig(
            default_profile="base",
            profiles={
                "base": ProfileDef(tests=["build"], extends="nonexistent"),
            },
        )
        mod = _empty_mod()
        with pytest.raises(ConfigError, match="nonexistent"):
            resolve_profile(parent, mod, "base")


class TestDevProfileDefaults:
    def test_dev_resolves_with_defaults(self, stable_parent):
        # dev declares neither max_parallel nor max_jobs
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "dev")
        assert resolved.max_parallel == 1  # built-in default
        assert resolved.max_jobs == 256  # built-in default

    def test_dev_test_list(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "dev")
        test_ids = [t.id for t in resolved.tests]
        assert test_ids == ["build", "server-smoke"]


class TestUnknownProfile:
    def test_raises_with_available_listed(self, stable_parent):
        mod = _empty_mod()
        with pytest.raises(UnknownProfile) as exc_info:
            resolve_profile(stable_parent, mod, "nonexistent-profile")
        msg = str(exc_info.value)
        assert "nonexistent-profile" in msg
        assert "default" in msg


class TestTestConfigMerge:
    def test_parent_config_used_when_no_mod_override(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "default")
        pregen = next(t for t in resolved.tests if t.id == "pregen")
        # Parent defines config.preset=xs
        assert pregen.config.get("preset") == "xs"

    def test_mod_config_wins_over_parent(self, stable_parent):
        mod = _empty_mod(
            tests={
                "pregen": TestDef(config={"preset": "large", "extra": "value"}),
            }
        )
        resolved = resolve_profile(stable_parent, mod, "default")
        pregen = next(t for t in resolved.tests if t.id == "pregen")
        # Mod wins on overlapping key
        assert pregen.config["preset"] == "large"
        # Mod's extra key is present
        assert pregen.config["extra"] == "value"
        # Parent's other keys are preserved (shallow merge)
        assert "tool_preference" in pregen.config

    def test_origin_index_preserved(self, stable_parent):
        mod = _empty_mod()
        resolved = resolve_profile(stable_parent, mod, "default")
        for i, spec in enumerate(resolved.tests):
            assert spec.origin_index == i


class TestModChainExtends:
    """
    Coverage for the mod-side `extends` resolution path (resolve._resolve_mod_chain),
    reached when a mod ProfileOverride declares its own `extends` target. This
    path is entirely separate from the parent-side chain walk in
    _resolve_parent_chain / TestCycleDetection above.
    """

    def test_mod_chain_cycle_detection(self):
        parent = ParentConfig(
            default_profile="default",
            profiles={"default": ProfileDef(tests=["build"])},
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="a"),
                "a": ProfileOverride(extends="b"),
                "b": ProfileOverride(extends="a"),
            }
        )
        with pytest.raises(ConfigError, match="cycle detected in mod extends chain"):
            resolve_profile(parent, mod, "default")

    def test_mod_chain_cycle_message_includes_chain(self):
        parent = ParentConfig(
            default_profile="default",
            profiles={"default": ProfileDef(tests=["build"])},
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="a"),
                "a": ProfileOverride(extends="b"),
                "b": ProfileOverride(extends="a"),
            }
        )
        with pytest.raises(ConfigError) as exc_info:
            resolve_profile(parent, mod, "default")
        msg = str(exc_info.value)
        assert "a" in msg
        assert "b" in msg

    def test_mod_chain_dedup_across_links(self):
        # "test-a" is declared both by the parent-side "base" profile (reached
        # via the mod's extends chain) and by the mod's own "add" list on
        # "child"; it must appear exactly once in the resolved test list.
        parent = ParentConfig(
            default_profile="default",
            profiles={
                "default": ProfileDef(tests=["something-else"]),
                "base": ProfileDef(tests=["build", "test-a"]),
            },
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="child"),
                "child": ProfileOverride(extends="base", add=["test-a", "test-b"]),
            }
        )
        resolved = resolve_profile(parent, mod, "default")
        test_ids = [t.id for t in resolved.tests]
        assert test_ids == ["build", "test-a", "test-b"]
        assert test_ids.count("test-a") == 1

    def test_mod_chain_both_add_and_tests_raises(self):
        # The top-level override ("default") only has `extends`, so this
        # exercises the add/tests conflict check for a link further down the
        # mod chain ("mid"), not the top-level check in resolve_profile itself.
        parent = ParentConfig(
            default_profile="default",
            profiles={"default": ProfileDef(tests=["build"])},
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="mid"),
                "mid": ProfileOverride(
                    add=["extra"],
                    tests=[{"id": "only-this", "required": True}],
                ),
            }
        )
        with pytest.raises(ConfigError, match="both 'add' and 'tests'"):
            resolve_profile(parent, mod, "default")

    def test_mod_chain_extends_target_not_found(self):
        parent = ParentConfig(
            default_profile="default",
            profiles={"default": ProfileDef(tests=["build"])},
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="ghost"),
            }
        )
        with pytest.raises(
            ConfigError, match="'ghost' not found in mod or parent config"
        ):
            resolve_profile(parent, mod, "default")

    def test_mod_chain_referenced_extends_target_not_found(self):
        # Unlike the previous test, here "link1" itself resolves fine and it
        # is *its* extends target ("ghost2") that is missing -- a different
        # raise site (mid-loop) than the entry-point check above.
        parent = ParentConfig(
            default_profile="default",
            profiles={"default": ProfileDef(tests=["build"])},
        )
        mod = _empty_mod(
            profiles={
                "default": ProfileOverride(extends="link1"),
                "link1": ProfileOverride(extends="ghost2"),
            }
        )
        with pytest.raises(
            ConfigError,
            match="'ghost2' referenced via extends from 'link1' not found",
        ):
            resolve_profile(parent, mod, "default")


class TestFixtureParentEndToEnd:
    """
    End-to-end coverage for the on-disk fixture parent configs under
    tests/fixtures/: load_parent_config -> schema validation -> resolve (and,
    for the max-jobs fixture, planning). This proves the full pipeline
    rejects these configs, not just hand-built dataclasses.
    """

    def test_cyclic_extends_parent_rejected_end_to_end(self, tmp_path):
        parent = _load_fixture_parent(tmp_path, "cyclic-extends-parent.yml")
        mod = _empty_mod()
        with pytest.raises(
            ConfigError, match="cycle detected in profile extends chain"
        ):
            resolve_profile(parent, mod, "alpha")

    def test_max_jobs_tight_parent_rejected_end_to_end(self, tmp_path):
        parent = _load_fixture_parent(tmp_path, "max-jobs-tight-parent.yml")
        mod = _empty_mod()
        resolved = resolve_profile(parent, mod, "tiny")
        assert resolved.max_jobs == 1
        assert resolved.max_parallel == 1

        with pytest.raises(MatrixLimitExceeded) as exc_info:
            build_plan(mod, resolved, None)
        assert exc_info.value.count == 2  # 2 tests x 1 target
        assert exc_info.value.cap == 1
