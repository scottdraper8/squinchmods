from __future__ import annotations

import io
import json
import shutil
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from squinch_qa import cli

from conftest import FIXTURES, REAL_REPO_ROOT, _build_fake_repo


def _run_plan(repo_root: Path, *args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(["plan", *args, "--repo-root", str(repo_root)])
    return code, buf.getvalue()


PROFILES = ["dev", "default", "pre-pr", "release"]

# Expected test counts per profile (from parent config)
_BASE_PROFILE_TESTS = {
    "dev": ["build", "server-smoke"],
    "default": ["build", "server-smoke", "pregen"],
    "pre-pr": ["build", "server-smoke", "pregen"],  # extends default
    "release": ["build", "server-smoke", "pregen"],  # extends pre-pr
}

_MOD_PROFILE_TESTS = {
    "redstone-backport": {
        **_BASE_PROFILE_TESTS,
        "pre-pr": [
            "build",
            "server-smoke",
            "pregen",
            "tick-freeze",
            "crafter-basic",
        ],
        "release": [
            "build",
            "server-smoke",
            "pregen",
            "tick-freeze",
            "crafter-basic",
        ],
    },
    "ReTerraForged": _BASE_PROFILE_TESTS,
}

_MOD_TARGETS = {
    "redstone-backport": ["forge-1.20.1", "forge-1.21.4"],
    "ReTerraForged": ["neoforge-1.21.1", "fabric-1.21.1"],
}


class TestRedstoneBackport:
    @pytest.mark.parametrize("profile", PROFILES)
    def test_deterministic_output(self, fake_repo, profile):
        _, out1 = _run_plan(fake_repo, "redstone-backport", "--profile", profile)
        _, out2 = _run_plan(fake_repo, "redstone-backport", "--profile", profile)
        assert out1 == out2

    @pytest.mark.parametrize("profile", PROFILES)
    def test_structural_expectations(self, fake_repo, profile):
        code, output = _run_plan(fake_repo, "redstone-backport", "--profile", profile)
        data = json.loads(output)
        jobs = data["jobs"]

        assert code == 0
        assert data["schema"] == 1
        assert data["mod"]["id"] == "redstone-backport"
        assert data["profile"]["name"] == profile
        expected_targets = _MOD_TARGETS["redstone-backport"]
        expected_tests = _MOD_PROFILE_TESTS["redstone-backport"][profile]
        assert len(jobs) == len(expected_targets) * len(expected_tests)

        job_target_ids = {j["target"]["id"] for j in jobs}
        for tid in expected_targets:
            assert tid in job_target_ids

        job_test_ids = {j["test"]["id"] for j in jobs}
        for test_id in expected_tests:
            assert test_id in job_test_ids

    def test_target_filter_forge_1201(self, fake_repo):
        code, output = _run_plan(
            fake_repo,
            "redstone-backport",
            "--profile",
            "default",
            "--target",
            "forge-1.20.1",
        )
        assert code == 0
        data = json.loads(output)
        for job in data["jobs"]:
            assert job["target"]["id"] == "forge-1.20.1"
        assert len(data["jobs"]) == len(_BASE_PROFILE_TESTS["default"])


class TestReTerraForged:
    @pytest.mark.parametrize("profile", PROFILES)
    def test_deterministic_output(self, fake_repo, profile):
        _, out1 = _run_plan(fake_repo, "ReTerraForged", "--profile", profile)
        _, out2 = _run_plan(fake_repo, "ReTerraForged", "--profile", profile)
        assert out1 == out2

    @pytest.mark.parametrize("profile", PROFILES)
    def test_structural_expectations(self, fake_repo, profile):
        code, output = _run_plan(fake_repo, "ReTerraForged", "--profile", profile)
        data = json.loads(output)
        jobs = data["jobs"]

        assert code == 0
        assert data["schema"] == 1
        assert data["mod"]["id"] == "reterraforged"
        assert data["profile"]["name"] == profile
        expected_targets = _MOD_TARGETS["ReTerraForged"]
        expected_tests = _MOD_PROFILE_TESTS["ReTerraForged"][profile]
        assert len(jobs) == len(expected_targets) * len(expected_tests)

        job_target_ids = {j["target"]["id"] for j in jobs}
        for tid in expected_targets:
            assert tid in job_target_ids

    def test_pre_pr_pregen_uses_large_preset_without_changing_default(self, fake_repo):
        _, default_output = _run_plan(
            fake_repo,
            "ReTerraForged",
            "--profile",
            "default",
            "--target",
            "neoforge-1.21.1",
        )
        _, pre_pr_output = _run_plan(
            fake_repo,
            "ReTerraForged",
            "--profile",
            "pre-pr",
            "--target",
            "neoforge-1.21.1",
        )

        default = json.loads(default_output)
        pre_pr = json.loads(pre_pr_output)
        default_pregen = next(j for j in default["jobs"] if j["test"]["id"] == "pregen")
        pre_pr_pregen = next(j for j in pre_pr["jobs"] if j["test"]["id"] == "pregen")

        assert default_pregen["test"]["config"]["preset"] == "xs"
        assert pre_pr_pregen["test"]["config"]["preset"] == "l"
        assert pre_pr_pregen["test"]["config"]["timeout_s"] == 7200

    def test_mod_id_lookup_works(self, fake_repo):
        """Lookup by mod.id 'reterraforged' (not filesystem name 'ReTerraForged')."""
        code, output = _run_plan(fake_repo, "reterraforged", "--profile", "dev")
        assert code == 0
        data = json.loads(output)
        assert data["mod"]["id"] == "reterraforged"


class TestGametestSkip:
    def test_gametest_requiring_test_skipped_on_fabric(self, tmp_path):
        """Fixture with gametest-requiring test + fabric target lacking gametest capability.

        The real parent config's default profile includes 'pregen' and
        'server-smoke' but not 'tick-freeze-gametest'; use a custom parent
        config fixture that includes it.
        """
        repo = _build_fake_repo(
            tmp_path,
            mod_configs={"unsupported-combo": FIXTURES / "unsupported-combo-mod.yml"},
            parent_config=FIXTURES / "gametest-skip-parent.yml",
        )

        code, output = _run_plan(repo, "unsupported-combo", "--profile", "default")
        assert code == 0
        data = json.loads(output)

        # build has no requirements, so it should be a job
        job_test_ids = {j["test"]["id"] for j in data["jobs"]}
        assert "build" in job_test_ids

        # tick-freeze-gametest requires gametest, fabric lacks it → skipped
        skipped_pairs = {(s["target_id"], s["test_id"]) for s in data["skipped"]}
        assert ("fabric-1.20.1", "tick-freeze-gametest") in skipped_pairs

        # Check reason mentions the missing capability
        skipped_reason = next(
            s["reason"]
            for s in data["skipped"]
            if s["test_id"] == "tick-freeze-gametest"
        )
        assert "gametest" in skipped_reason


class TestExitCodes:
    def test_unknown_mod_exits_1(self, fake_repo):
        code, _ = _run_plan(fake_repo, "no-such-mod", "--profile", "default")
        assert code == 1

    def test_unknown_profile_exits_1(self, fake_repo):
        code, _ = _run_plan(fake_repo, "redstone-backport", "--profile", "nonexistent")
        assert code == 1

    def test_unknown_target_exits_1(self, fake_repo):
        code, _ = _run_plan(
            fake_repo,
            "redstone-backport",
            "--profile",
            "default",
            "--target",
            "no-such-target",
        )
        assert code == 1

    def test_matrix_limit_exceeded_exits_3(self, tmp_path):
        repo = _build_fake_repo(
            tmp_path,
            mod_configs={"two-target-mod": FIXTURES / "two-target-mod.yml"},
            parent_config=FIXTURES / "max-jobs-tight-parent.yml",
        )
        code, _ = _run_plan(repo, "two-target-mod", "--profile", "tiny")
        assert code == 3

    def test_no_subcommand_exits_1(self, capsys):
        code = cli.main([])
        assert code == 1
        err = capsys.readouterr().err
        assert "usage" in err.lower()

    def test_config_error_exits_2(self, fake_repo):
        # Break the parent config's schema validity (default_profile must be a
        # string) without touching mod configs, to trigger ConfigError instead
        # of one of the more specific config-loading errors.
        (fake_repo / ".squinch" / "config.yml").write_text(
            "schema: 1\n"
            "globals:\n"
            "  default_profile: 123\n"
            "  profiles:\n"
            "    default:\n"
            "      tests: [build]\n"
        )
        code, _ = _run_plan(fake_repo, "redstone-backport", "--profile", "default")
        assert code == 2

    def test_validation_error_exits_5(self, tmp_path):
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        qa_runs_dir.mkdir()

        code = cli.main(
            [
                "promote",
                "--run-id",
                "no-such-run",
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert code == 5


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")
class TestSubprocessSmoke:
    def test_squinch_qa_plan_via_subprocess(self, fake_repo):
        squinch_script = REAL_REPO_ROOT / "tooling" / "squinch"
        result = subprocess.run(
            [
                str(squinch_script),
                "qa",
                "plan",
                "redstone-backport",
                "--profile",
                "dev",
                "--repo-root",
                str(fake_repo),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["schema"] == 1
        assert data["mod"]["id"] == "redstone-backport"
        assert data["profile"]["name"] == "dev"
        assert {(j["target"]["id"], j["test"]["id"]) for j in data["jobs"]} == {
            ("forge-1.20.1", "build"),
            ("forge-1.20.1", "server-smoke"),
            ("forge-1.21.4", "build"),
            ("forge-1.21.4", "server-smoke"),
        }
