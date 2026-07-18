from __future__ import annotations

from pathlib import Path

import pytest

from squinch_qa.executors.build import BuildExecutor
from squinch_qa.executors.base import JobContext


# ── Fake gradle helpers ───────────────────────────────────────────────────────


def _fake_resolve_gradle_env(repo_root: Path) -> dict:
    import os

    return dict(os.environ)


def _fake_run_gradle_success(args, cwd, env, stdout_log, stderr_log, tee_fn=None):
    task = next(arg for arg in args if arg.endswith(":build"))
    loader = task.split(":")[1]
    jar_dir = cwd / loader / "build" / "libs"
    jar_dir.mkdir(parents=True, exist_ok=True)
    (jar_dir / "mymod-1.0.0.jar").write_bytes(b"PK\x03\x04" + b"\x00" * 26)
    Path(stdout_log).write_text("BUILD SUCCESSFUL\n")
    Path(stderr_log).write_text("")
    return 0


def _fake_run_gradle_fail(args, cwd, env, stdout_log, stderr_log, tee_fn=None):
    Path(stdout_log).write_text("BUILD FAILED\nSee the compiler error output.\n")
    Path(stderr_log).write_text("error: compilation failed\n")
    return 1


def _fake_run_gradle_success_no_jar(
    args, cwd, env, stdout_log, stderr_log, tee_fn=None
):
    """Gradle reports success but doesn't leave a jar in build/libs (edge case)."""
    task = next(arg for arg in args if arg.endswith(":build"))
    loader = task.split(":")[1]
    jar_dir = cwd / loader / "build" / "libs"
    jar_dir.mkdir(parents=True, exist_ok=True)
    Path(stdout_log).write_text("BUILD SUCCESSFUL\n")
    Path(stderr_log).write_text("")
    return 0


# ── Class 1: BuildExecutor success ───────────────────────────────────────────


class TestBuildExecutorSuccess:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.build.resolve_gradle_env",
            _fake_resolve_gradle_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.build.run_gradle",
            _fake_run_gradle_success,
        )
        self.ctx: JobContext = make_job_context(
            test_id="build", target_id="forge-1.20.1"
        )
        self.result = BuildExecutor().run(self.ctx)

    def test_status_passed(self):
        assert self.result.status == "pass"

    def test_jar_copied_to_artifacts(self):
        artifacts_dir = self.ctx.job_dir / "artifacts"
        jars = list(artifacts_dir.glob("*.jar"))
        assert len(jars) == 1

    def test_sha256_populated(self):
        assert self.result.jar_sha256 is not None
        assert len(self.result.jar_sha256) == 64
        assert all(c in "0123456789abcdef" for c in self.result.jar_sha256)

    def test_logs_created(self):
        logs_dir = self.ctx.job_dir / "logs"
        assert (logs_dir / "gradle.stdout.log").exists()
        assert (logs_dir / "gradle.stderr.log").exists()

    def test_uses_parent_qa_init_script(self, monkeypatch, make_job_context):
        calls = []

        def _capture(args, cwd, env, stdout_log, stderr_log, tee_fn=None):
            calls.append(args)
            return _fake_run_gradle_success(
                args, cwd, env, stdout_log, stderr_log, tee_fn
            )

        monkeypatch.setattr(
            "squinch_qa.executors.build.resolve_gradle_env",
            _fake_resolve_gradle_env,
        )
        monkeypatch.setattr("squinch_qa.executors.build.run_gradle", _capture)
        ctx = make_job_context(test_id="build", target_id="forge-1.20.1")
        script = (
            ctx.repo_root
            / "games"
            / "minecraft"
            / "tooling"
            / "qa"
            / "gradle"
            / "squinchmods-qa.gradle"
        )
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("// test init script\n")
        result = BuildExecutor().run(ctx)
        assert result.status == "pass"
        assert calls[0][:2] == ["--init-script", str(script)]


# ── Class 2: BuildExecutor failure ───────────────────────────────────────────


class TestBuildExecutorFailure:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.build.resolve_gradle_env",
            _fake_resolve_gradle_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.build.run_gradle",
            _fake_run_gradle_fail,
        )
        self.ctx: JobContext = make_job_context(
            test_id="build", target_id="forge-1.20.1"
        )
        self.result = BuildExecutor().run(self.ctx)

    def test_status_failed(self):
        assert self.result.status == "fail"

    def test_logs_preserved(self):
        log = self.ctx.job_dir / "logs" / "gradle.stdout.log"
        assert "BUILD FAILED" in log.read_text()

    def test_failure_reason_set(self):
        assert self.result.failure is not None
        assert self.result.failure.reason

    def test_no_jar_in_artifacts(self):
        artifacts_dir = self.ctx.job_dir / "artifacts"
        jars = list(artifacts_dir.glob("*.jar")) if artifacts_dir.exists() else []
        assert len(jars) == 0


# ── Class 3: BuildExecutor gradle-env-error ──────────────────────────────────
#
# runner_repo (via _build_fake_repo) never creates
# games/minecraft/tooling/.sdkmanrc, so calling the *real* resolve_gradle_env
# against it fails deterministically. No monkeypatching of resolve_gradle_env
# is needed here -- this exercises the real .sdkmanrc-not-found boundary.


class TestBuildExecutorGradleEnvError:
    @pytest.fixture(autouse=True)
    def _setup(self, make_job_context):
        self.ctx: JobContext = make_job_context(
            test_id="build", target_id="forge-1.20.1"
        )
        self.result = BuildExecutor().run(self.ctx)

    def test_status_error(self):
        assert self.result.status == "error"

    def test_failure_reason_is_gradle_env_error(self):
        assert self.result.failure is not None
        assert self.result.failure.reason == "gradle_env_error"

    def test_failure_detail_mentions_sdkmanrc(self):
        assert ".sdkmanrc" in self.result.failure.detail

    def test_no_jar_in_artifacts(self):
        artifacts_dir = self.ctx.job_dir / "artifacts"
        jars = list(artifacts_dir.glob("*.jar")) if artifacts_dir.exists() else []
        assert len(jars) == 0


# ── Class 4: BuildExecutor jar_not_found ─────────────────────────────────────


class TestBuildExecutorJarNotFound:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.build.resolve_gradle_env",
            _fake_resolve_gradle_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.build.run_gradle",
            _fake_run_gradle_success_no_jar,
        )
        self.ctx: JobContext = make_job_context(
            test_id="build", target_id="forge-1.20.1"
        )
        self.result = BuildExecutor().run(self.ctx)

    def test_status_error(self):
        assert self.result.status == "error"

    def test_failure_reason_is_jar_not_found(self):
        assert self.result.failure is not None
        assert self.result.failure.reason == "jar_not_found"

    def test_failure_detail_mentions_libs_dir(self):
        assert "build" in self.result.failure.detail
        assert "libs" in self.result.failure.detail

    def test_no_jar_in_artifacts(self):
        artifacts_dir = self.ctx.job_dir / "artifacts"
        jars = list(artifacts_dir.glob("*.jar")) if artifacts_dir.exists() else []
        assert len(jars) == 0
