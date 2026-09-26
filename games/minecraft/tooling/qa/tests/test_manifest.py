from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from squinch_qa.executors.base import FailureDetail, JobResult
from squinch_qa.manifest import _compute_exit_code, _git_head_sha, emit_all
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    Target,
    TestSpec,
)


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


def _profile(tests: list[TestSpec]) -> ResolvedProfile:
    return ResolvedProfile(
        name="default", resolved_from=["default"], tests=tests, max_jobs=32
    )


def _plan(jobs: list[PlannedJob]) -> ExecutionPlan:
    return ExecutionPlan(
        mod_id="test-mod",
        display_name="Test Mod",
        profile=_profile([job.test_spec for job in jobs]),
        jobs=jobs,
    )


def _job(target_id: str = "forge-1.20.1", test_id: str = "build") -> PlannedJob:
    return PlannedJob(target=_target(target_id), test_spec=_test_spec(test_id))


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


class TestComputeExitCode:
    @pytest.mark.parametrize(
        ("result_status", "expected_code"),
        [
            pytest.param("pass", 0, id="pass-returns-zero"),
            pytest.param("fail", 4, id="fail-returns-four"),
            pytest.param("error", 4, id="error-returns-four"),
            pytest.param(None, 4, id="missing-result-returns-four"),
        ],
    )
    def test_compute_exit_code(self, result_status, expected_code):
        job = _job()
        plan = _plan([job])
        key = (job.target.id, job.test_spec.id)
        results = {} if result_status is None else {key: _result(result_status)}
        assert _compute_exit_code(plan, results) == expected_code


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


class TestPerJobFileContent:
    def _run_emit(self, tmp_path: Path, job: PlannedJob, result: JobResult) -> Path:
        emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): result},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="test-run-1",
            plan_bytes=b'{"schema":1}',
        )
        return tmp_path / "jobs" / job.target.id / job.test_spec.id

    def test_manifest_has_schema_1(self, tmp_path: Path):
        job_dir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((job_dir / "manifest.json").read_text())
        assert doc["schema"] == 1

    def test_manifest_has_correct_matrix_id(self, tmp_path: Path):
        job_dir = self._run_emit(tmp_path, _job(), _result())
        doc = json.loads((job_dir / "manifest.json").read_text())
        assert doc["matrix_id"] == "forge-1.20.1/build"

    def test_manifest_has_target_and_mod_info(self, tmp_path: Path):
        job_dir = self._run_emit(tmp_path, _job(), _result(jar_sha256="deadbeef" * 8))
        doc = json.loads((job_dir / "manifest.json").read_text())
        assert doc["target"] == {
            "id": "forge-1.20.1",
            "java": 17,
            "loader": "forge",
            "loader_version": "47.0.0",
            "minecraft": "1.20.1",
        }
        assert doc["mod"]["id"] == "test-mod"
        assert doc["mod"]["jar_sha256"] == "deadbeef" * 8

    def test_manifest_records_check_status(self, tmp_path: Path):
        job_dir = self._run_emit(tmp_path, _job(), _result("fail"))
        doc = json.loads((job_dir / "manifest.json").read_text())
        assert doc["test"] == {"id": "build", "status": "fail"}

    def test_result_includes_failure_detail(self, tmp_path: Path):
        failure = FailureDetail(reason="build_error", detail="exit 1")
        job_dir = self._run_emit(tmp_path, _job(), _result("fail", failure=failure))
        doc = json.loads((job_dir / "result.json").read_text())
        assert doc["failure"] == {"reason": "build_error", "detail": "exit 1"}


class TestEmitAll:
    def test_creates_per_job_and_run_files(self, tmp_path: Path):
        job = _job()
        emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result()},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        job_dir = tmp_path / "jobs" / "forge-1.20.1" / "build"
        assert (job_dir / "manifest.json").is_file()
        assert (job_dir / "result.json").is_file()
        manifest = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert manifest["schema"] == 1
        assert manifest["run_id"] == "r1"
        assert manifest["mod_id"] == "test-mod"
        assert (
            manifest["jobs"][0]["manifest"] == "jobs/forge-1.20.1/build/manifest.json"
        )

    def test_creates_top_level_result(self, tmp_path: Path):
        job = _job()
        emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result(duration_s=1.0)},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        result = json.loads((tmp_path / "result.json").read_text())
        assert result["run_id"] == "r1"
        assert result["status"] == "pass"
        assert result["exit_code"] == 0
        assert result["duration_s"] == 1.0

    def test_returns_0_when_all_pass(self, tmp_path: Path):
        job = _job()
        code = emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result("pass")},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        assert code == 0

    def test_returns_4_when_a_check_fails(self, tmp_path: Path):
        job = _job()
        code = emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result("fail")},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        assert code == 4

    def test_plan_sha256_matches_plan_bytes(self, tmp_path: Path):
        plan_bytes = b'{"schema":1,"mod":"test"}'
        job = _job()
        emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result()},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=plan_bytes,
        )
        manifest = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert manifest["plan_sha256"] == hashlib.sha256(plan_bytes).hexdigest()

    def test_counts_are_correct(self, tmp_path: Path):
        jobs = [_job("forge-1.20.1"), _job("fabric-1.20.1")]
        emit_all(
            tmp_path,
            _plan(jobs),
            {
                (jobs[0].target.id, jobs[0].test_spec.id): _result("pass"),
                (jobs[1].target.id, jobs[1].test_spec.id): _result("fail"),
            },
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        result = json.loads((tmp_path / "result.json").read_text())
        assert result["counts"]["pass"] == 1
        assert result["counts"]["fail"] == 1

    def test_repo_and_mod_commits_in_run_manifest(self, tmp_path: Path):
        job = _job()
        repo_root = tmp_path / "repo"
        mod_dir = tmp_path / "mod"
        repo_sha = _git_repo_with_empty_commit(repo_root)
        mod_sha = _git_repo_with_empty_commit(mod_dir)
        run_dir = tmp_path / "run"
        emit_all(
            run_dir,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result()},
            repo_root=repo_root,
            mod_dir=mod_dir,
            run_id="r1",
            plan_bytes=b"{}",
        )
        manifest = json.loads((run_dir / "qa-manifest.json").read_text())
        assert manifest["repo_commit"] == repo_sha
        assert manifest["mod_commit"] == mod_sha

    def test_null_commits_when_git_unavailable(self, tmp_path: Path):
        job = _job()
        emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result()},
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        manifest = json.loads((tmp_path / "qa-manifest.json").read_text())
        assert manifest["repo_commit"] is None
        assert manifest["mod_commit"] is None


class TestPlanHashStability:
    def _emit(self, run_dir: Path, plan_bytes: bytes) -> str:
        job = _job()
        emit_all(
            run_dir,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result()},
            repo_root=run_dir,
            mod_dir=run_dir,
            run_id="r1",
            plan_bytes=plan_bytes,
        )
        return json.loads((run_dir / "qa-manifest.json").read_text())["plan_sha256"]

    def test_plan_sha256_stability(self, tmp_path: Path):
        plan_bytes = b'{"schema":1,"mod":"test-mod"}'
        run1 = tmp_path / "run1"
        run1.mkdir()
        run2 = tmp_path / "run2"
        run2.mkdir()
        assert self._emit(run1, plan_bytes) == self._emit(run2, plan_bytes)


class TestWorldValidationFailure:
    def _emit_with_bad_world(self, tmp_path: Path) -> tuple[int, dict]:
        job = _job(test_id="pregen")
        world = tmp_path / "jobs" / "forge-1.20.1" / "pregen" / "world"
        world.mkdir(parents=True)
        (world / "level.dat").write_bytes(b"real file")
        (world / "evil").symlink_to(world / "level.dat")
        exit_code = emit_all(
            tmp_path,
            _plan([job]),
            {(job.target.id, job.test_spec.id): _result("pass", artifacts=["world"])},
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
        _, manifest = self._emit_with_bad_world(tmp_path)
        assert manifest["test"]["status"] == "error"
        assert manifest["world_sha256"] is None

    def test_bad_world_fails_run(self, tmp_path: Path):
        exit_code, _ = self._emit_with_bad_world(tmp_path)
        assert exit_code == 4

    def test_top_level_results_record_world_error(self, tmp_path: Path):
        self._emit_with_bad_world(tmp_path)
        manifest = json.loads((tmp_path / "qa-manifest.json").read_text())
        result = json.loads((tmp_path / "result.json").read_text())
        assert manifest["jobs"][0]["status"] == "error"
        assert result["status"] == "fail"
        assert result["counts"]["error"] == 1

    def test_other_jobs_in_same_run_are_recorded(self, tmp_path: Path):
        good_job = _job(test_id="build")
        bad_job = _job(test_id="pregen")
        world = tmp_path / "jobs" / "forge-1.20.1" / "pregen" / "world"
        world.mkdir(parents=True)
        (world / "level.dat").write_bytes(b"real file")
        (world / "evil").symlink_to(world / "level.dat")
        jobs = [good_job, bad_job]
        emit_all(
            tmp_path,
            _plan(jobs),
            {
                (good_job.target.id, good_job.test_spec.id): _result("pass"),
                (bad_job.target.id, bad_job.test_spec.id): _result(
                    "pass", artifacts=["world"]
                ),
            },
            repo_root=tmp_path,
            mod_dir=tmp_path,
            run_id="r1",
            plan_bytes=b"{}",
        )
        manifest = json.loads(
            (tmp_path / "jobs" / "forge-1.20.1" / "build" / "manifest.json").read_text()
        )
        assert manifest["matrix_id"] == "forge-1.20.1/build"
        assert manifest["test"]["status"] == "pass"
