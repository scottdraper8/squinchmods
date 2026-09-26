from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from squinch_qa.executors.base import FailureDetail, JobResult
from squinch_qa.manifest import (
    _compute_exit_code,
    _effective_status,
    _git_head_sha,
    emit_all,
)
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    Target,
    TestSpec,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _target(id: str, loader: str = "forge") -> Target:
    return Target(
        id=id,
        minecraft="1.20.1",
        loader=loader,
        loader_version="47.0.0",
        java=17,
        supported=True,
        capabilities=["server"],
    )


def _test_spec(id: str, required: bool = True, origin_index: int = 0) -> TestSpec:
    return TestSpec(
        id=id,
        required=required,
        requires=[],
        adapters={},
        expectations={},
        config={},
        origin_index=origin_index,
    )


def _profile(tests: list[TestSpec]) -> ResolvedProfile:
    return ResolvedProfile(
        name="default",
        resolved_from=["default"],
        tests=tests,
        max_parallel=4,
        max_jobs=32,
    )


def _plan(
    jobs: list[PlannedJob], profile: ResolvedProfile | None = None
) -> ExecutionPlan:
    if profile is None:
        profile = _profile([j.test_spec for j in jobs])
    return ExecutionPlan(
        mod_id="test-mod",
        display_name="Test Mod",
        profile=profile,
        jobs=jobs,
        skipped=[],
        skipped_targets=[],
    )


def _job(
    target_id: str = "forge-1.20.1",
    test_id: str = "build",
    required: bool = True,
    expected_failure: dict | None = None,
    adapter: dict | None = None,
    expectations: dict | None = None,
) -> PlannedJob:
    return PlannedJob(
        target=_target(target_id),
        test_spec=_test_spec(test_id, required=required),
        adapter=adapter,
        expected_failure=expected_failure,
        expectations=expectations or {},
    )


def _result(
    status: str = "pass",
    duration_s: float = 1.0,
    logs: list[str] | None = None,
    artifacts: list[str] | None = None,
    failure: FailureDetail | None = None,
    jar_sha256: str | None = None,
    tool_used: str | None = None,
) -> JobResult:
    return JobResult(
        status=status,
        started_at="2026-07-15T00:00:00+00:00",
        finished_at="2026-07-15T00:00:01+00:00",
        duration_s=duration_s,
        logs=logs or [],
        artifacts=artifacts or [],
        failure=failure,
        tool_used=tool_used,
        jar_sha256=jar_sha256,
    )


def _git_repo_with_empty_commit(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    git_bin = shutil.which("git")
    assert git_bin is not None, "git executable not found on PATH"
    env = {
        "HOME": str(path),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t.com",
        # Preserve the real PATH so git resolves on any install layout
        # (Homebrew, Nix, /usr/local/bin, ...); fall back to git's own
        # directory if the environment somehow lacks PATH entirely.
        "PATH": os.environ.get("PATH", str(Path(git_bin).parent)),
    }
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True, env=env)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=path,
        capture_output=True,
        check=True,
        env=env,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        check=True,
        text=True,
        env=env,
    ).stdout.strip()


# ── Class 1: Status conversion ────────────────────────────────────────────────


class TestEffectiveStatus:
    @pytest.mark.parametrize(
        "raw_status, expected_failure, expected",
        [
            pytest.param(
                "fail",
                {"reason": "known", "expires": "2026-12-01", "expired": False},
                "expected_failure",
                id="fail_with_unexpired_ef_becomes_expected_failure",
            ),
            pytest.param(
                "fail",
                {"reason": "known", "expires": "2025-01-01", "expired": True},
                "fail",
                id="fail_with_expired_ef_stays_fail",
            ),
            pytest.param(
                "fail",
                None,
                "fail",
                id="fail_with_no_ef_stays_fail",
            ),
            pytest.param(
                "pass",
                {"reason": "known", "expires": "2026-12-01", "expired": False},
                "pass",
                id="pass_with_unexpired_ef_stays_pass",
            ),
            pytest.param(
                "error",
                {"reason": "known", "expires": "2026-12-01", "expired": False},
                "error",
                id="error_with_unexpired_ef_stays_error",
            ),
        ],
    )
    def test_effective_status(self, raw_status, expected_failure, expected):
        job = _job(expected_failure=expected_failure)
        assert _effective_status(raw_status, job) == expected


# ── Class 2: Exit code logic ──────────────────────────────────────────────────


class TestComputeExitCode:
    @pytest.mark.parametrize(
        "required, expected_failure, result_status, expected_code",
        [
            pytest.param(True, None, "pass", 0, id="all_required_pass_returns_0"),
            pytest.param(True, None, "fail", 4, id="required_fail_returns_4"),
            pytest.param(True, None, "error", 4, id="required_error_returns_4"),
            pytest.param(
                True,
                {"reason": "known", "expires": "2026-12-01", "expired": False},
                "fail",
                0,
                id="required_expected_failure_returns_0",
            ),
            pytest.param(False, None, "fail", 0, id="advisory_fail_returns_0"),
            pytest.param(True, None, None, 4, id="missing_required_result_returns_4"),
        ],
    )
    def test_compute_exit_code(
        self, required, expected_failure, result_status, expected_code
    ):
        j = _job(required=required, expected_failure=expected_failure)
        p = _plan([j])
        key = (j.target.id, j.test_spec.id)
        job_results = {} if result_status is None else {key: _result(result_status)}
        assert _compute_exit_code(p, job_results) == expected_code


# ── Class 3: Git SHA extraction ───────────────────────────────────────────────


class TestGitHeadSha:
    def test_valid_git_repo_returns_sha(self, tmp_path: Path):
        _git_repo_with_empty_commit(tmp_path)
        sha = _git_head_sha(tmp_path)
        assert sha is not None
        assert len(sha) == 40

    def test_non_git_directory_returns_none(self, tmp_path: Path):
        assert _git_head_sha(tmp_path) is None

    def test_subprocess_exception_returns_none(self, tmp_path: Path, monkeypatch):
        from squinch_qa import manifest as manifest_mod

        def fake_run(*args, **kwargs):
            raise OSError("no git")

        monkeypatch.setattr(manifest_mod.subprocess, "run", fake_run)
        assert _git_head_sha(tmp_path) is None


# ── Class 4: Per-job file content ─────────────────────────────────────────────


class TestPerJobFileContent:
    def _run_emit(self, tmp_path: Path, job: PlannedJob, result: JobResult) -> Path:
        plan = _plan([job])
        plan_bytes = b'{"schema":1}'
        emit_all(
            tmp_path,
            plan,
            {(job.target.id, job.test_spec.id): result},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="test-run-1",
            plan_bytes=plan_bytes,
        )
        return tmp_path / "jobs" / job.target.id / job.test_spec.id

    def test_manifest_has_schema_1(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["schema"] == 1

    def test_manifest_has_correct_matrix_id(self, tmp_path: Path):
        jdir = self._run_emit(
            tmp_path, _job(target_id="forge-1.20.1", test_id="build"), _result()
        )
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["matrix_id"] == "forge-1.20.1/build"

    def test_manifest_has_target_info(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["target"]["id"] == "forge-1.20.1"
        assert doc["target"]["minecraft"] == "1.20.1"
        assert doc["target"]["java"] == 17
        assert doc["target"]["loader"] == "forge"
        assert doc["target"]["loader_version"] == "47.0.0"

    def test_manifest_has_mod_info(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result(jar_sha256="deadbeef" * 8))
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["mod"]["id"] == "test-mod"
        assert doc["mod"]["jar_sha256"] == "deadbeef" * 8

    def test_manifest_has_adapter(self, tmp_path: Path):
        adapter = {"type": "gametest"}
        jdir = self._run_emit(tmp_path, _job(adapter=adapter), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["adapter"] == adapter

    def test_manifest_adapter_is_none_when_not_applicable(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["adapter"] is None

    def test_manifest_has_resolved_expectations(self, tmp_path: Path):
        expectations = {"min_biomes_seen": 6}
        jdir = self._run_emit(tmp_path, _job(expectations=expectations), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["expectations"] == expectations

    def test_manifest_expectations_empty_dict_when_none_declared(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["expectations"] == {}

    def test_manifest_has_expected_failure_detail(self, tmp_path: Path):
        ef = {"reason": "known flake", "expires": "2026-12-01", "expired": False}
        jdir = self._run_emit(
            tmp_path, _job(expected_failure=ef), _result(status="fail")
        )
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["expected_failure"] == ef

    def test_manifest_expected_failure_is_none_when_not_declared(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((jdir / "manifest.json").read_text())
        assert doc["test"]["expected_failure"] is None

    def test_result_reflects_effective_status(self, tmp_path: Path):
        ef = {"reason": "known", "expires": "2026-12-01", "expired": False}
        job = _job(expected_failure=ef)
        jdir = self._run_emit(tmp_path, job, _result(status="fail"))
        doc = json.loads((jdir / "result.json").read_text())
        assert doc["status"] == "expected_failure"

    def test_result_failure_is_none_when_no_failure(self, tmp_path: Path):
        jdir = self._run_emit(tmp_path, _job(), _result(status="pass"))
        doc = json.loads((jdir / "result.json").read_text())
        assert doc["failure"] is None

    def test_result_includes_failure_detail(self, tmp_path: Path):
        failure = FailureDetail(reason="build_error", detail="exit 1")
        jdir = self._run_emit(tmp_path, _job(), _result(status="fail", failure=failure))
        doc = json.loads((jdir / "result.json").read_text())
        assert doc["failure"]["reason"] == "build_error"
        assert doc["failure"]["detail"] == "exit 1"


# ── Class 5: End-to-end emit_all ──────────────────────────────────────────────


class TestEmitAll:
    def _make_plan_and_results(
        self,
        jobs_and_results: list[tuple[PlannedJob, JobResult]],
    ) -> tuple[ExecutionPlan, dict[tuple[str, str], JobResult]]:
        jobs = [j for j, _ in jobs_and_results]
        results = {(j.target.id, j.test_spec.id): r for j, r in jobs_and_results}
        plan = _plan(jobs)
        return plan, results

    def test_creates_per_job_files(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        plan_bytes = b'{"schema":1}'
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=plan_bytes,
        )
        jdir = tmp_path / "jobs" / "forge-1.20.1" / "build"
        manifest = json.loads((jdir / "manifest.json").read_text())
        result = json.loads((jdir / "result.json").read_text())
        assert manifest["run_id"] == "r1"
        assert manifest["matrix_id"] == "forge-1.20.1/build"
        assert result["status"] == "pass"

    def test_creates_top_level_qa_manifest(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert doc["schema"] == 1
        assert doc["run_id"] == "r1"
        assert doc["mod_id"] == "test-mod"
        assert doc["jobs"][0]["manifest"] == "jobs/forge-1.20.1/build/manifest.json"

    def test_creates_top_level_result(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads((tmp_path / "result.json").read_text())
        assert doc["run_id"] == "r1"
        assert doc["status"] == "pass"
        assert doc["exit_code"] == 0
        assert doc["duration_s"] == 1.0

    def test_returns_0_when_all_pass(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result("pass"))])
        code = emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        assert code == 0

    def test_returns_4_when_required_fails(self, tmp_path: Path):
        job = _job(required=True)
        plan, results = self._make_plan_and_results([(job, _result("fail"))])
        code = emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        assert code == 4

    def test_plan_sha256_matches_plan_bytes(self, tmp_path: Path):
        plan_bytes = b'{"schema":1,"mod":"test"}'
        expected_sha = hashlib.sha256(plan_bytes).hexdigest()
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=plan_bytes,
        )
        doc = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert doc["plan_sha256"] == expected_sha

    def test_counts_are_correct(self, tmp_path: Path):
        j1 = _job(target_id="forge-1.20.1", test_id="build", required=True)
        j2 = _job(target_id="fabric-1.20.1", test_id="build", required=False)
        plan, results = self._make_plan_and_results(
            [
                (j1, _result("pass")),
                (j2, _result("fail")),
            ]
        )
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads((tmp_path / "result.json").read_text())
        assert doc["counts"]["pass"] == 1
        assert doc["counts"]["fail"] == 1

    def test_repo_and_mod_commits_in_qa_manifest(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        repo_root = tmp_path / "repo"
        mod_dir = tmp_path / "mod"
        repo_sha = _git_repo_with_empty_commit(repo_root)
        mod_sha = _git_repo_with_empty_commit(mod_dir)
        run_dir = tmp_path / "run"
        emit_all(
            run_dir,
            plan,
            results,
            repo_root=repo_root,
            mod_dir=mod_dir,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads((run_dir / "qa-manifest.json").read_text())
        assert doc["repo_commit"] == repo_sha
        assert doc["mod_commit"] == mod_sha

    def test_null_commits_when_git_unavailable(self, tmp_path: Path):
        job = _job()
        plan, results = self._make_plan_and_results([(job, _result())])
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert doc["repo_commit"] is None
        assert doc["mod_commit"] is None


# ── Class 6: plan_sha256 stability ───────────────────────────────────────────


class TestPlanHashStability:
    def _emit(self, run_dir: Path, plan_bytes: bytes) -> str:
        job = _job()
        plan = _plan([job])
        results = {("forge-1.20.1", "build"): _result()}
        emit_all(
            run_dir,
            plan,
            results,
            repo_root=run_dir,
            mod_dir=run_dir,
            run_id="r1",
            plan_bytes=plan_bytes,
        )
        return json.loads((run_dir / "qa-manifest.json").read_text())["plan_sha256"]

    def test_plan_sha256_stability(self, tmp_path: Path):
        plan_bytes = b'{"schema":1,"mod":"test-mod"}'
        d1 = tmp_path / "run1"
        d1.mkdir()
        d2 = tmp_path / "run2"
        d2.mkdir()
        sha1 = self._emit(d1, plan_bytes)
        sha2 = self._emit(d2, plan_bytes)
        assert sha1 == sha2


# ── Class 7: world validation failures don't abort the run ──────────────────


class TestWorldValidationFailure:
    def _emit_with_bad_world(self, tmp_path: Path, required: bool) -> tuple[int, dict]:
        job = _job(test_id="pregen", required=required)
        plan = _plan([job])
        results = {("forge-1.20.1", "pregen"): _result("pass", artifacts=["world"])}
        world = tmp_path / "jobs" / "forge-1.20.1" / "pregen" / "world"
        world.mkdir(parents=True)
        (world / "level.dat").write_bytes(b"real file")
        (world / "evil").symlink_to(world / "level.dat")
        exit_code = emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        manifest = json.loads(
            (
                tmp_path / "jobs" / "forge-1.20.1" / "pregen" / "manifest.json"
            ).read_text()
        )
        return exit_code, manifest

    def test_bad_world_job_recorded_as_error(self, tmp_path: Path):
        _, manifest = self._emit_with_bad_world(tmp_path, required=True)
        assert manifest["test"]["status"] == "error"
        assert manifest["world_sha256"] is None

    def test_required_bad_world_fails_run(self, tmp_path: Path):
        exit_code, _ = self._emit_with_bad_world(tmp_path, required=True)
        assert exit_code == 4

    def test_advisory_bad_world_does_not_fail_run(self, tmp_path: Path):
        exit_code, _ = self._emit_with_bad_world(tmp_path, required=False)
        assert exit_code == 0

    def test_top_level_manifest_still_written(self, tmp_path: Path):
        self._emit_with_bad_world(tmp_path, required=True)
        manifest = json.loads((tmp_path / "qa-manifest.json").read_text())
        result = json.loads((tmp_path / "result.json").read_text())
        assert manifest["jobs"][0]["status"] == "error"
        assert result["status"] == "fail"
        assert result["counts"]["error"] == 1

    def test_other_jobs_in_same_run_still_recorded(self, tmp_path: Path):
        good_job = _job(target_id="forge-1.20.1", test_id="build")
        bad_job = _job(target_id="forge-1.20.1", test_id="pregen")
        plan = _plan([good_job, bad_job])
        results = {
            ("forge-1.20.1", "build"): _result("pass"),
            ("forge-1.20.1", "pregen"): _result("pass", artifacts=["world"]),
        }
        world = tmp_path / "jobs" / "forge-1.20.1" / "pregen" / "world"
        world.mkdir(parents=True)
        (world / "level.dat").write_bytes(b"real file")
        (world / "evil").symlink_to(world / "level.dat")
        emit_all(
            tmp_path,
            plan,
            results,
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        doc = json.loads(
            (tmp_path / "jobs" / "forge-1.20.1" / "build" / "manifest.json").read_text()
        )
        assert doc["matrix_id"] == "forge-1.20.1/build"
        assert doc["test"]["status"] == "pass"
