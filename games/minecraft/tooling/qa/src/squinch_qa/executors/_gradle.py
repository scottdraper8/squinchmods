from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path


class GradleEnvError(Exception):
    pass


def qa_init_script(repo_root: Path) -> Path:
    return (
        repo_root
        / "games"
        / "minecraft"
        / "tooling"
        / "qa"
        / "gradle"
        / "squinchmods-qa.gradle"
    )


def qa_gradle_args(repo_root: Path, job_dir: Path) -> list[str]:
    script = qa_init_script(repo_root)
    run_root = job_dir.parents[2]
    build_root = run_root / "gradle-build" / job_dir.parent.name
    project_cache = run_root / "gradle-project-cache"
    return [
        "--project-cache-dir",
        str(project_cache),
        "--init-script",
        str(script),
        f"-PsquinchQaBuildRoot={build_root}",
        f"-PsquinchQaRunDir={job_dir / 'runtime'}",
    ]


def qa_loader_build_dir(job_dir: Path, loader: str) -> Path:
    return job_dir.parents[2] / "gradle-build" / job_dir.parent.name / loader


def resolve_gradle_env(repo_root: Path) -> dict[str, str]:
    """Build an explicit env dict with JAVA_HOME and GRADLE_USER_HOME set.

    Reads tooling/.sdkmanrc to find the pinned Java candidate under SDKMAN_DIR.
    Never mutates os.environ and never logs the returned dict.
    """
    sdkmanrc = repo_root / "games" / "minecraft" / "tooling" / ".sdkmanrc"
    if not sdkmanrc.is_file():
        raise GradleEnvError(f".sdkmanrc not found at {sdkmanrc}")

    java_version: str | None = None
    for line in sdkmanrc.read_text().splitlines():
        line = line.strip()
        if line.startswith("java="):
            java_version = line[len("java=") :].strip()

    if not java_version:
        raise GradleEnvError(f"No java= entry in {sdkmanrc}")

    sdkman_dir = Path(os.environ.get("SDKMAN_DIR", Path.home() / ".sdkman"))
    java_home = sdkman_dir / "candidates" / "java" / java_version

    if not java_home.is_dir():
        raise GradleEnvError(
            f"SDKMAN Java candidate not found: {java_home} (java={java_version})"
        )

    sqinchmods_cache = Path(
        os.environ.get(
            "SQINCHMODS_CACHE_HOME",
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "squinchmods",
        )
    )
    gradle_user_home = str(sqinchmods_cache / "gradle")

    env = dict(os.environ)
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    env["GRADLE_USER_HOME"] = gradle_user_home

    return env


def run_gradle(
    args: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_log: Path,
    stderr_log: Path,
    tee_fn: Callable[[bytes], None] | None = None,
) -> int:
    """Run ./gradlew <args> in cwd, teeing output to log files.

    Returns the process exit code.
    """

    cmd = ["./gradlew"] + args

    with (
        stdout_log.open("wb") as out_f,
        stderr_log.open("wb") as err_f,
        subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc,
    ):
        assert proc.stdout is not None
        assert proc.stderr is not None

        def _tee_stdout(line: bytes) -> None:
            out_f.write(line)
            out_f.flush()
            if tee_fn is not None:
                tee_fn(line)

        def _tee_stderr(line: bytes) -> None:
            err_f.write(line)
            err_f.flush()

        def drain_stdout() -> None:
            for line in proc.stdout:  # type: ignore[union-attr]
                _tee_stdout(line)

        def drain_stderr() -> None:
            for line in proc.stderr:  # type: ignore[union-attr]
                _tee_stderr(line)

        t_out = threading.Thread(target=drain_stdout, daemon=True)
        t_err = threading.Thread(target=drain_stderr, daemon=True)
        t_out.start()
        t_err.start()
        t_out.join()
        t_err.join()

        proc.wait()
        return proc.returncode
