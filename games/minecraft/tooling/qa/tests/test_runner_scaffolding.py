from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from squinch_qa.artifacts import (
    default_qa_runs_dir,
    job_dir,
    make_run_id,
    run_dir,
    sha256_bytes,
    sha256_file,
)
from squinch_qa.errors import PlanError
from squinch_qa.runner import create_run_state, parse_plan_json

# ── Minimal plan fixture ──────────────────────────────────────────────────────

MINIMAL_PLAN_BYTES = json.dumps(
    {
        "schema": 1,
        "mod": {"id": "test-mod", "display_name": "Test Mod"},
        "profile": {
            "name": "dev",
            "resolved_from": ["dev"],
            "max_parallel": 1,
            "max_jobs": 256,
        },
        "jobs": [],
        "skipped": [],
        "skipped_targets": [],
    }
).encode()


# ── Class 1: make_run_id ──────────────────────────────────────────────────────


class TestMakeRunId:
    def test_shape(self):
        rid = make_run_id()
        # Format: <unix_ms>-<hex8>
        assert re.match(r"^\d+-[a-f0-9]{8}$", rid), f"Unexpected run_id shape: {rid!r}"

    def test_uniqueness(self):
        ids = [make_run_id() for _ in range(20)]
        assert len(set(ids)) == 20


# ── Class 2: Artifact path construction ──────────────────────────────────────


class TestArtifactPaths:
    def test_run_dir_structure(self, tmp_path: Path):
        rid = "12345-abcd1234"
        assert run_dir(tmp_path, rid) == tmp_path / rid

    def test_job_dir_layout(self, tmp_path: Path):
        rid = "12345-abcd1234"
        result = job_dir(tmp_path, rid, "forge-1.20.1", "build")
        assert result == tmp_path / rid / "jobs" / "forge-1.20.1" / "build"


# ── Class 3: SHA-256 helpers ──────────────────────────────────────────────────


class TestSha256:
    def test_sha256_bytes_matches_hashlib(self):
        data = b"hello world"
        assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()

    def test_sha256_file(self, tmp_path: Path):
        content = b"file content here"
        f = tmp_path / "test.bin"
        f.write_bytes(content)
        assert sha256_file(f) == hashlib.sha256(content).hexdigest()


# ── Class 4: parse_plan_json ──────────────────────────────────────────────────


class TestParsePlanJson:
    def test_minimal_plan_parses(self):
        plan = parse_plan_json(MINIMAL_PLAN_BYTES)
        assert plan.mod_id == "test-mod"

    def test_unknown_schema_raises(self):
        data = json.dumps(
            {
                "schema": 99,
                "mod": {"id": "test-mod", "display_name": ""},
                "profile": {
                    "name": "dev",
                    "resolved_from": ["dev"],
                    "max_parallel": 1,
                    "max_jobs": 256,
                },
                "jobs": [],
                "skipped": [],
                "skipped_targets": [],
            }
        ).encode()
        with pytest.raises(PlanError):
            parse_plan_json(data)

    def test_supported_true_in_parsed_jobs(self, fake_repo: Path):
        from squinch_qa.config import load_mod_config, load_parent_config
        from squinch_qa.planner import build_plan, emit_plan_json
        from squinch_qa.resolve import resolve_profile

        parent = load_parent_config(fake_repo)
        mod, _ = load_mod_config(fake_repo, "redstone-backport")
        resolved = resolve_profile(parent, mod, "dev")
        plan = build_plan(mod, resolved, None)
        plan_bytes = emit_plan_json(plan).encode()
        reparsed = parse_plan_json(plan_bytes)
        assert all(j.target.supported is True for j in reparsed.jobs)

    def test_rich_plan_fields_round_trip(self) -> None:
        data = json.dumps(
            {
                "schema": 1,
                "mod": {"id": "rich-mod", "display_name": "Rich Mod"},
                "profile": {
                    "name": "pre-pr",
                    "resolved_from": ["default", "pre-pr"],
                    "max_parallel": 2,
                    "max_jobs": 16,
                },
                "jobs": [
                    {
                        "target": {
                            "id": "neoforge-1.21.1",
                            "minecraft": "1.21.1",
                            "loader": "neoforge",
                            "loader_version": "21.1.1",
                            "java": 21,
                            "capabilities": ["server", "worldgen"],
                        },
                        "test": {
                            "id": "pregen",
                            "required": False,
                            "requires": ["server"],
                            "config": {"radius": 8, "tool_preference": ["chunky"]},
                        },
                        "adapter": "neoforge-server",
                        "expected_failure": {
                            "reason": "known bug",
                            "expires": "2026-12-31",
                            "expired": False,
                        },
                    }
                ],
                "skipped": [
                    {
                        "target_id": "fabric-1.21.1",
                        "test_id": "pregen",
                        "reason": "missing server",
                    }
                ],
                "skipped_targets": [
                    {"target_id": "forge-1.20.1", "reason": "unsupported"}
                ],
            }
        ).encode()

        plan = parse_plan_json(data)
        job = plan.jobs[0]

        assert plan.mod_id == "rich-mod"
        assert plan.display_name == "Rich Mod"
        assert plan.profile.name == "pre-pr"
        assert plan.profile.resolved_from == ["default", "pre-pr"]
        assert plan.profile.max_parallel == 2
        assert job.target.id == "neoforge-1.21.1"
        assert job.target.loader == "neoforge"
        assert job.target.java == 21
        assert job.target.capabilities == ["server", "worldgen"]
        assert job.test_spec.id == "pregen"
        assert job.test_spec.required is False
        assert job.test_spec.requires == ["server"]
        assert job.test_spec.config == {"radius": 8, "tool_preference": ["chunky"]}
        assert job.adapter == "neoforge-server"
        assert job.expected_failure == {
            "reason": "known bug",
            "expires": "2026-12-31",
            "expired": False,
        }
        assert plan.skipped[0].reason == "missing server"
        assert plan.skipped_targets[0].reason == "unsupported"


# ── Class 5: create_run_state ─────────────────────────────────────────────────


class TestCreateRunState:
    def test_plan_sha256_populated(self, tmp_path: Path):
        state = create_run_state(MINIMAL_PLAN_BYTES, tmp_path / "qa-runs")
        assert state.plan_sha256 == sha256_bytes(MINIMAL_PLAN_BYTES)

    def test_run_id_populated(self, tmp_path: Path):
        state = create_run_state(MINIMAL_PLAN_BYTES, tmp_path / "qa-runs")
        assert re.match(r"^\d+-[a-f0-9]{8}$", state.run_id)

    def test_plan_mod_id_matches(self, tmp_path: Path):
        state = create_run_state(MINIMAL_PLAN_BYTES, tmp_path / "qa-runs")
        assert state.plan.mod_id == "test-mod"

    def test_run_id_override_accepted(self, tmp_path: Path):
        state = create_run_state(
            MINIMAL_PLAN_BYTES,
            tmp_path / "qa-runs",
            run_id="1234567890-deadbeef",
        )
        assert state.run_id == "1234567890-deadbeef"

    def test_invalid_run_id_override_rejected(self, tmp_path: Path):
        with pytest.raises(PlanError):
            create_run_state(
                MINIMAL_PLAN_BYTES,
                tmp_path / "qa-runs",
                run_id="../evil",
            )


# ── Class 6: plan determinism ─────────────────────────────────────────────────


class TestRunPlanWiring:
    """End-to-end: run_plan must call manifest.emit_all and return its exit code."""

    def _stub_executor(self, tmp_path: Path, monkeypatch, status: str):
        from squinch_qa.executors import base as base_mod
        from squinch_qa import runner as runner_mod

        class _StubExec:
            def run(self, ctx):
                return base_mod.JobResult(
                    status=status,
                    started_at="2026-01-01T00:00:00+00:00",
                    finished_at="2026-01-01T00:00:01+00:00",
                    duration_s=1.0,
                    logs=[],
                    artifacts=[],
                    failure=None
                    if status == "pass"
                    else base_mod.FailureDetail("x", "y"),
                )

        monkeypatch.setattr(runner_mod, "get_executor", lambda _tid: _StubExec)

    def _plan_bytes_one_job(self) -> bytes:
        return json.dumps(
            {
                "schema": 1,
                "mod": {"id": "test-mod", "display_name": "Test Mod"},
                "profile": {
                    "name": "dev",
                    "resolved_from": ["dev"],
                    "max_parallel": 1,
                    "max_jobs": 256,
                },
                "jobs": [
                    {
                        "target": {
                            "id": "forge-1.20.1",
                            "minecraft": "1.20.1",
                            "loader": "forge",
                            "loader_version": "47.0.0",
                            "java": 17,
                            "capabilities": ["server"],
                        },
                        "test": {"id": "build", "required": True, "config": {}},
                        "adapter": None,
                        "expected_failure": None,
                    }
                ],
                "skipped": [],
                "skipped_targets": [],
            }
        ).encode()

    def test_run_writes_top_level_manifest_and_result(
        self, tmp_path, monkeypatch, capsys
    ):
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_executor(tmp_path, monkeypatch, status="pass")
        plan_bytes = self._plan_bytes_one_job()
        state = create_run_state(plan_bytes, tmp_path / "qa-runs")
        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, clean=False)
        rdir = tmp_path / "qa-runs" / state.run_id
        manifest = json.loads((rdir / "qa-manifest.json").read_text())
        result = json.loads((rdir / "result.json").read_text())
        events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

        assert exit_code == 0
        assert (rdir / "plan.json").read_bytes() == plan_bytes
        assert manifest["run_id"] == state.run_id
        assert manifest["mod_id"] == "test-mod"
        assert manifest["jobs"][0]["matrix_id"] == "forge-1.20.1/build"
        assert result["run_id"] == state.run_id
        assert result["status"] == "pass"
        assert result["counts"]["pass"] == 1
        assert events[0]["type"] == "run_start"
        assert events[0]["mod_id"] == "test-mod"
        assert events[-1]["type"] == "run_complete"
        assert events[-1]["exit_code"] == 0

    def test_run_writes_per_job_files(self, tmp_path, monkeypatch):
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_executor(tmp_path, monkeypatch, status="pass")
        state = create_run_state(self._plan_bytes_one_job(), tmp_path / "qa-runs")
        run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, clean=False)
        jdir = tmp_path / "qa-runs" / state.run_id / "jobs" / "forge-1.20.1" / "build"
        manifest = json.loads((jdir / "manifest.json").read_text())
        result = json.loads((jdir / "result.json").read_text())

        assert manifest["run_id"] == state.run_id
        assert manifest["mod"]["id"] == "test-mod"
        assert manifest["target"]["id"] == "forge-1.20.1"
        assert manifest["test"]["id"] == "build"
        assert manifest["test"]["status"] == "pass"
        assert result["status"] == "pass"
        assert result["duration_s"] == 1.0

    def test_run_returns_4_on_required_failure(self, tmp_path, monkeypatch):
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_executor(tmp_path, monkeypatch, status="fail")
        state = create_run_state(self._plan_bytes_one_job(), tmp_path / "qa-runs")
        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path)
        assert exit_code == 4

    def test_run_cleans_after_execution_by_default(self, tmp_path, monkeypatch):
        from squinch_qa.cleanup import CleanAction
        from squinch_qa.runner import create_run_state, run_plan

        calls = []

        def fake_clean_qa(qa_root):
            calls.append(qa_root)
            return [
                CleanAction(
                    state="runs",
                    path=qa_root / "runs" / "old",
                    reason="test",
                    removed=True,
                )
            ]

        self._stub_executor(tmp_path, monkeypatch, status="pass")
        monkeypatch.setattr("squinch_qa.cleanup.clean_qa", fake_clean_qa)
        state = create_run_state(self._plan_bytes_one_job(), tmp_path / "qa-runs")

        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path)

        assert exit_code == 0
        assert calls == [tmp_path / "games" / "minecraft" / "qa"]

    def test_run_clean_false_skips_cleanup(self, tmp_path, monkeypatch):
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_executor(tmp_path, monkeypatch, status="pass")
        monkeypatch.setattr(
            "squinch_qa.cleanup.clean_qa",
            lambda *a, **k: pytest.fail("cleanup should be disabled"),
        )
        state = create_run_state(self._plan_bytes_one_job(), tmp_path / "qa-runs")

        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, clean=False)

        assert exit_code == 0

    def test_run_converts_executor_exception_to_error_result(
        self, tmp_path, monkeypatch
    ):
        """
        A generic exception raised out of executor_cls().run(ctx) must be
        caught by run_plan and converted into a per-job "error" result rather
        than crashing the whole run.
        """
        from squinch_qa import runner as runner_mod
        from squinch_qa.runner import create_run_state, run_plan

        class _RaisingExec:
            def run(self, ctx):
                raise RuntimeError("boom: executor blew up")

        monkeypatch.setattr(runner_mod, "get_executor", lambda _tid: _RaisingExec)
        state = create_run_state(self._plan_bytes_one_job(), tmp_path / "qa-runs")

        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, clean=False)

        jdir = tmp_path / "qa-runs" / state.run_id / "jobs" / "forge-1.20.1" / "build"
        result = json.loads((jdir / "result.json").read_text())

        assert exit_code == 4
        assert result["status"] == "error"
        assert result["failure"]["reason"] == "executor_exception"
        assert "boom: executor blew up" in result["failure"]["detail"]

    def test_run_converts_not_implemented_error_from_real_registry(self, tmp_path):
        """
        Uses the real (un-monkeypatched) get_executor registry with a test id
        that has no registered executor, exercising executors/__init__.py's
        NotImplementedError branch through run_plan end-to-end.
        """
        from squinch_qa.runner import create_run_state, run_plan

        plan_bytes = self._plan_bytes_one_job().replace(
            b'"id": "build"', b'"id": "no-such-test"'
        )
        state = create_run_state(plan_bytes, tmp_path / "qa-runs")

        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, clean=False)

        jdir = (
            tmp_path
            / "qa-runs"
            / state.run_id
            / "jobs"
            / "forge-1.20.1"
            / "no-such-test"
        )
        result = json.loads((jdir / "result.json").read_text())

        assert exit_code == 4
        assert result["status"] == "error"
        assert result["failure"]["reason"] == "executor_not_implemented"
        assert "no-such-test" in result["failure"]["detail"]


class TestRunCliDefaults:
    def test_run_defaults_to_minecraft_qa_runs_dir(
        self, fake_repo: Path, monkeypatch
    ) -> None:
        from squinch_qa import cli as cli_mod
        from squinch_qa import runner as runner_mod

        captured = []

        def fake_run_plan(state, **kwargs):
            captured.append((state, kwargs))
            return 0

        monkeypatch.setattr(runner_mod, "run_plan", fake_run_plan)

        code = cli_mod.main(
            [
                "run",
                "redstone-backport",
                "--profile",
                "dev",
                "--repo-root",
                str(fake_repo),
                "--run-id",
                "1234567890-deadbeef",
            ]
        )

        assert code == 0
        assert captured[0][0].qa_runs_dir == default_qa_runs_dir(fake_repo)
        assert not (fake_repo / ".qa-runs").exists()

    def test_run_plan_mod_id_must_match_selected_mod(
        self, fake_repo: Path, tmp_path: Path, monkeypatch
    ) -> None:
        from squinch_qa import cli as cli_mod
        from squinch_qa import runner as runner_mod

        monkeypatch.setattr(
            runner_mod,
            "run_plan",
            lambda *a, **k: pytest.fail("should not run mismatched plan"),
        )
        plan_path = tmp_path / "rtf-plan.json"
        plan_path.write_bytes(
            MINIMAL_PLAN_BYTES.replace(b'"test-mod"', b'"reterraforged"')
        )

        code = cli_mod.main(
            [
                "run",
                "redstone-backport",
                "--plan",
                str(plan_path),
                "--repo-root",
                str(fake_repo),
            ]
        )

        assert code == 2


class TestRunPlanPromote:
    """End-to-end: run_plan(promote=True) must promote a passing world into .qa-current."""

    def _stub_world_executor(self, monkeypatch):
        from squinch_qa.executors import base as base_mod
        from squinch_qa import runner as runner_mod

        class _StubExec:
            def run(self, ctx):
                world = ctx.job_dir / "world"
                (world / "region").mkdir(parents=True)
                (world / "region" / "r.0.0.mca").write_bytes(b"chunk data")
                return base_mod.JobResult(
                    status="pass",
                    started_at="2026-01-01T00:00:00+00:00",
                    finished_at="2026-01-01T00:00:01+00:00",
                    duration_s=1.0,
                    logs=[],
                    artifacts=["world"],
                    failure=None,
                )

        monkeypatch.setattr(runner_mod, "get_executor", lambda _tid: _StubExec)

    def _plan_bytes_pregen_job(self) -> bytes:
        return json.dumps(
            {
                "schema": 1,
                "mod": {"id": "test-mod", "display_name": "Test Mod"},
                "profile": {
                    "name": "dev",
                    "resolved_from": ["dev"],
                    "max_parallel": 1,
                    "max_jobs": 256,
                },
                "jobs": [
                    {
                        "target": {
                            "id": "forge-1.20.1",
                            "minecraft": "1.20.1",
                            "loader": "forge",
                            "loader_version": "47.0.0",
                            "java": 17,
                            "capabilities": ["server"],
                        },
                        "test": {"id": "pregen", "required": True, "config": {}},
                        "adapter": None,
                        "expected_failure": None,
                    }
                ],
                "skipped": [],
                "skipped_targets": [],
            }
        ).encode()

    def test_promote_true_populates_qa_current(self, tmp_path, monkeypatch):
        from squinch_qa.artifacts import default_qa_root
        from squinch_qa.replace.layout import current_job_dir
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_world_executor(monkeypatch)
        state = create_run_state(self._plan_bytes_pregen_job(), tmp_path / "qa-runs")
        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, promote=True)

        assert exit_code == 0
        cur = current_job_dir(
            default_qa_root(tmp_path), "test-mod", "forge-1.20.1", "pregen"
        )
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"chunk data"

    def test_promote_false_leaves_qa_current_untouched(self, tmp_path, monkeypatch):
        from squinch_qa.artifacts import default_qa_root
        from squinch_qa.replace.layout import current_job_dir
        from squinch_qa.runner import create_run_state, run_plan

        self._stub_world_executor(monkeypatch)
        state = create_run_state(self._plan_bytes_pregen_job(), tmp_path / "qa-runs")
        run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, promote=False)

        assert not current_job_dir(
            default_qa_root(tmp_path), "test-mod", "forge-1.20.1", "pregen"
        ).exists()

    def test_promote_skipped_on_failing_run(self, tmp_path, monkeypatch):
        from squinch_qa.executors import base as base_mod
        from squinch_qa import runner as runner_mod
        from squinch_qa.artifacts import default_qa_root
        from squinch_qa.replace.layout import current_job_dir
        from squinch_qa.runner import create_run_state, run_plan

        class _FailingExec:
            def run(self, ctx):
                return base_mod.JobResult(
                    status="fail",
                    started_at="2026-01-01T00:00:00+00:00",
                    finished_at="2026-01-01T00:00:01+00:00",
                    duration_s=1.0,
                    logs=[],
                    artifacts=[],
                    failure=base_mod.FailureDetail("x", "y"),
                )

        monkeypatch.setattr(runner_mod, "get_executor", lambda _tid: _FailingExec)
        state = create_run_state(self._plan_bytes_pregen_job(), tmp_path / "qa-runs")
        exit_code = run_plan(state, repo_root=tmp_path, mod_dir=tmp_path, promote=True)

        assert exit_code == 4
        assert not current_job_dir(
            default_qa_root(tmp_path), "test-mod", "forge-1.20.1", "pregen"
        ).exists()


class TestExecutorRegistry:
    """Direct unit tests for the real executors/__init__.py registry."""

    def test_get_executor_returns_registered_class(self):
        from squinch_qa.executors import get_executor
        from squinch_qa.executors.build import BuildExecutor

        assert get_executor("build") is BuildExecutor

    def test_get_executor_raises_not_implemented_for_unknown_test_id(self):
        from squinch_qa.executors import get_executor

        with pytest.raises(NotImplementedError, match="no-such-test"):
            get_executor("no-such-test")


class TestPlanDeterminism:
    def test_parse_then_emit_preserves_job_identity(self, fake_repo: Path):
        from squinch_qa.config import load_mod_config, load_parent_config
        from squinch_qa.planner import build_plan, emit_plan_json
        from squinch_qa.resolve import resolve_profile

        parent = load_parent_config(fake_repo)
        mod, _ = load_mod_config(fake_repo, "redstone-backport")
        resolved = resolve_profile(parent, mod, "dev")
        plan = build_plan(mod, resolved, None)
        plan_bytes = emit_plan_json(plan).encode()
        reparsed = parse_plan_json(plan_bytes)
        assert len(reparsed.jobs) == len(plan.jobs)
        assert [(j.target.id, j.test_spec.id) for j in reparsed.jobs] == [
            (j.target.id, j.test_spec.id) for j in plan.jobs
        ]
        assert reparsed.mod_id == plan.mod_id
