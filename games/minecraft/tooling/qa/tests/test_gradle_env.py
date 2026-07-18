from __future__ import annotations

import os
import stat as _stat
from pathlib import Path

import pytest

from squinch_qa.executors._gradle import (
    GradleEnvError,
    resolve_gradle_env,
    run_gradle,
)


# ── resolve_gradle_env: real .sdkmanrc parsing ───────────────────────────────
#
# These drive the real filesystem-reading implementation (no monkeypatching of
# resolve_gradle_env itself) against a temp repo tree, per the project's
# real-I/O-boundary testing convention.


def _write_sdkmanrc(repo_root: Path, contents: str) -> Path:
    tooling_dir = repo_root / "games" / "minecraft" / "tooling"
    tooling_dir.mkdir(parents=True, exist_ok=True)
    sdkmanrc = tooling_dir / ".sdkmanrc"
    sdkmanrc.write_text(contents)
    return sdkmanrc


class TestResolveGradleEnv:
    def test_missing_sdkmanrc_raises(self, tmp_path: Path):
        with pytest.raises(GradleEnvError, match=r"\.sdkmanrc not found"):
            resolve_gradle_env(tmp_path)

    def test_sdkmanrc_without_java_entry_raises(self, tmp_path: Path):
        _write_sdkmanrc(tmp_path, "# no java= line here\n")
        with pytest.raises(GradleEnvError, match="No java= entry"):
            resolve_gradle_env(tmp_path)

    def test_sdkmanrc_java_candidate_missing_raises(self, tmp_path: Path, monkeypatch):
        _write_sdkmanrc(tmp_path, "java=21.0.11-tem\n")
        monkeypatch.setenv("SDKMAN_DIR", str(tmp_path / "sdkman"))
        with pytest.raises(GradleEnvError, match="SDKMAN Java candidate not found"):
            resolve_gradle_env(tmp_path)

    def test_resolves_java_home_from_real_sdkmanrc_and_sdkman_dir(
        self, tmp_path: Path, monkeypatch
    ):
        _write_sdkmanrc(tmp_path, "# comment\njava=21.0.11-tem\n")
        sdkman_dir = tmp_path / "sdkman"
        java_home = sdkman_dir / "candidates" / "java" / "21.0.11-tem"
        java_home.mkdir(parents=True)
        monkeypatch.setenv("SDKMAN_DIR", str(sdkman_dir))
        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path / "cache"))

        env = resolve_gradle_env(tmp_path)

        assert env["JAVA_HOME"] == str(java_home)
        assert env["PATH"].startswith(str(java_home / "bin") + os.pathsep)
        assert env["GRADLE_USER_HOME"] == str(tmp_path / "cache" / "gradle")

    def test_does_not_mutate_os_environ(self, tmp_path: Path, monkeypatch):
        _write_sdkmanrc(tmp_path, "java=21.0.11-tem\n")
        sdkman_dir = tmp_path / "sdkman"
        (sdkman_dir / "candidates" / "java" / "21.0.11-tem").mkdir(parents=True)
        monkeypatch.setenv("SDKMAN_DIR", str(sdkman_dir))
        before = dict(os.environ)

        resolve_gradle_env(tmp_path)

        assert dict(os.environ) == before


# ── run_gradle: real subprocess teeing/threading ─────────────────────────────
#
# Drives the real subprocess.Popen + tee-thread machinery against a trivial
# executable stub script named 'gradlew' (matching the './gradlew' command
# run_gradle hardcodes), following this project's real-stub-subprocess
# convention instead of mocking subprocess internals.


def _write_stub_gradlew(cwd: Path, script: str) -> None:
    gradlew = cwd / "gradlew"
    gradlew.write_text(script)
    mode = gradlew.stat().st_mode
    gradlew.chmod(mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)


class TestRunGradle:
    def test_returns_real_exit_code(self, tmp_path: Path):
        _write_stub_gradlew(
            tmp_path,
            "#!/bin/sh\necho out-line\necho err-line 1>&2\nexit 7\n",
        )
        returncode = run_gradle(
            args=[],
            cwd=tmp_path,
            env=dict(os.environ),
            stdout_log=tmp_path / "out.log",
            stderr_log=tmp_path / "err.log",
        )
        assert returncode == 7

    def test_tees_stdout_and_stderr_to_log_files(self, tmp_path: Path):
        _write_stub_gradlew(
            tmp_path,
            "#!/bin/sh\necho hello-stdout\necho hello-stderr 1>&2\nexit 0\n",
        )
        stdout_log = tmp_path / "out.log"
        stderr_log = tmp_path / "err.log"
        run_gradle(
            args=[],
            cwd=tmp_path,
            env=dict(os.environ),
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )
        assert stdout_log.read_text() == "hello-stdout\n"
        assert stderr_log.read_text() == "hello-stderr\n"

    def test_passes_args_through_to_gradlew(self, tmp_path: Path):
        _write_stub_gradlew(
            tmp_path,
            '#!/bin/sh\necho "args:$@"\nexit 0\n',
        )
        stdout_log = tmp_path / "out.log"
        run_gradle(
            args=["--init-script", "foo.gradle", ":forge:build"],
            cwd=tmp_path,
            env=dict(os.environ),
            stdout_log=stdout_log,
            stderr_log=tmp_path / "err.log",
        )
        assert (
            stdout_log.read_text().strip()
            == "args:--init-script foo.gradle :forge:build"
        )

    def test_tee_fn_receives_stdout_lines(self, tmp_path: Path):
        _write_stub_gradlew(
            tmp_path,
            "#!/bin/sh\necho line-one\necho line-two\nexit 0\n",
        )
        captured: list[bytes] = []
        run_gradle(
            args=[],
            cwd=tmp_path,
            env=dict(os.environ),
            stdout_log=tmp_path / "out.log",
            stderr_log=tmp_path / "err.log",
            tee_fn=captured.append,
        )
        assert captured == [b"line-one\n", b"line-two\n"]

    def test_tee_fn_not_called_for_stderr(self, tmp_path: Path):
        _write_stub_gradlew(
            tmp_path,
            "#!/bin/sh\necho only-stderr 1>&2\nexit 0\n",
        )
        captured: list[bytes] = []
        run_gradle(
            args=[],
            cwd=tmp_path,
            env=dict(os.environ),
            stdout_log=tmp_path / "out.log",
            stderr_log=tmp_path / "err.log",
            tee_fn=captured.append,
        )
        assert captured == []
