from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import IO, Iterator

DEFAULT_SMOKE_TIMEOUT_S: float = 300.0  # 5 min for server-smoke
DEFAULT_PREGEN_TIMEOUT_S: float = 3600.0  # 1 hour for pregen

SERVER_READY_PATTERN = "Done ("  # matches Minecraft's "Done (X.XXXs)!"


class ServerLaunchError(Exception):
    """Raised when the server process cannot be started."""


class ServerNotReadyError(Exception):
    """Raised when the server didn't print Done( within timeout_s."""


class ToolNotDoneError(Exception):
    """Raised when the pregen tool completion line wasn't seen within timeout_s."""


def pre_write_eula(loader_run_dir: Path) -> None:
    """Write eula=true to <loader_run_dir>/eula.txt before server boot."""
    loader_run_dir.mkdir(parents=True, exist_ok=True)
    (loader_run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")


def qa_level_name(run_id: str, target_id: str, test_id: str) -> str:
    raw = f"qa-{run_id}-{target_id}-{test_id}"
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in raw)


def configure_qa_server_properties(loader_run_dir: Path, *, level_name: str) -> None:
    """
    Write the minimum server properties QA needs for Gradle-dev runs.

    Gradle run dirs are persistent developer workspace state. A unique
    level-name prevents stale session.lock files in `world/` from poisoning new
    QA jobs and avoids reusing a developer's manual test world.
    """
    loader_run_dir.mkdir(parents=True, exist_ok=True)
    properties = {
        "enable-rcon": "false",
        "level-name": level_name,
        "online-mode": "false",
        "server-port": "0",
    }
    lines = [f"{key}={value}" for key, value in sorted(properties.items())]
    (loader_run_dir / "server.properties").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _tee_watch(source: IO[bytes], *sinks: IO[bytes]) -> Iterator[str]:
    """
    Read `source` (binary, line-buffered) line by line.
    Write each raw line to every sink.
    Yield each line decoded as UTF-8 (errors=replace).
    """
    for raw in source:
        for sink in sinks:
            sink.write(raw)
            sink.flush()
        yield raw.decode("utf-8", errors="replace")


def launch_server(
    loader: str,
    mod_dir: Path,
    env: dict[str, str],
    logs_dir: Path,
    gradle_args: list[str] | None = None,
) -> tuple[subprocess.Popen, Path]:
    """
    Launch ./gradlew :<loader>:runServer with piped stdin/stdout.

    Returns (proc, stdout_log_path).
    stdout and stderr are merged (stderr=STDOUT) so a single log captures both.
    Raises ServerLaunchError if the process cannot be started.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "server.stdout.log"

    try:
        proc = subprocess.Popen(
            ["./gradlew"] + (gradle_args or []) + [f":{loader}:runServer"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=mod_dir,
            env=env,
        )
    except OSError as e:
        raise ServerLaunchError(f"Failed to launch gradlew for {loader}: {e}") from e

    return proc, log_path


def wait_for_ready(
    proc: subprocess.Popen,
    log_path: Path,
    timeout_s: float,
) -> None:
    """
    Watch proc.stdout until SERVER_READY_PATTERN appears.
    Writes all output to log_path (appending).

    Raises ServerNotReadyError if timeout_s elapses or process exits before ready.
    """
    deadline = time.monotonic() + timeout_s
    # Watchdog forces stdout EOF if the process produces no output before the
    # deadline (otherwise the tee loop blocks indefinitely on proc.stdout).
    watchdog = threading.Timer(timeout_s, proc.kill)
    watchdog.daemon = True
    watchdog.start()
    try:
        with log_path.open("ab") as log_file:
            for line in _tee_watch(proc.stdout, log_file):
                if SERVER_READY_PATTERN in line:
                    return
                if time.monotonic() > deadline:
                    raise ServerNotReadyError(
                        f"Server did not print {SERVER_READY_PATTERN!r} within {timeout_s}s"
                    )
                if proc.poll() is not None and SERVER_READY_PATTERN not in line:
                    raise ServerNotReadyError(
                        "Server process exited before printing ready line"
                    )
        if time.monotonic() > deadline:
            raise ServerNotReadyError(
                f"Server did not print {SERVER_READY_PATTERN!r} within {timeout_s}s"
            )
        raise ServerNotReadyError("Server stdout closed before printing ready line")
    finally:
        watchdog.cancel()


def drain_stdout(proc: subprocess.Popen, log_path: Path) -> None:
    """
    Consume and log remaining proc.stdout after the server has been told to stop.
    Called after send_stop() so we don't leave an unread pipe buffer.
    """
    with log_path.open("ab") as log_file:
        for _ in _tee_watch(proc.stdout, log_file):
            pass


def send_stop(proc: subprocess.Popen) -> None:
    """Write 'stop\\n' to proc.stdin."""
    if proc.stdin and not proc.stdin.closed:
        proc.stdin.write(b"stop\n")
        proc.stdin.flush()


def wait_for_exit(proc: subprocess.Popen, timeout_s: float = 60.0) -> int:
    """
    Wait for proc to exit. Returns returncode.
    Kills proc if it doesn't exit within timeout_s.
    """
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    return proc.returncode


def close_pipes(proc: subprocess.Popen) -> None:
    """
    Explicitly close proc's stdin/stdout after it has exited.

    Popen.wait() does not close the pipe file objects, so leaving this to GC
    lets the interpreter flush a stdin write buffer against an already-dead
    child at finalization time — that raises BrokenPipeError somewhere
    unraisable instead of here, where it's expected and safe to ignore.
    """
    for pipe in (proc.stdin, proc.stdout):
        if pipe is not None and not pipe.closed:
            try:
                pipe.close()
            except OSError:
                pass


def watch_for_tool_completion(
    proc: subprocess.Popen,
    log_path: Path,
    pattern: str,
    timeout_s: float,
) -> None:
    """
    Continue reading proc.stdout, watching for `pattern` in a line.
    Called after server is ready and tool commands have been sent.

    Raises ToolNotDoneError if pattern not seen within timeout_s or process exits early.
    """
    deadline = time.monotonic() + timeout_s
    watchdog = threading.Timer(timeout_s, proc.kill)
    watchdog.daemon = True
    watchdog.start()
    try:
        with log_path.open("ab") as log_file:
            for line in _tee_watch(proc.stdout, log_file):
                if pattern in line:
                    return
                if time.monotonic() > deadline:
                    raise ToolNotDoneError(
                        f"Tool completion pattern {pattern!r} not seen within {timeout_s}s"
                    )
                if proc.poll() is not None and pattern not in line:
                    raise ToolNotDoneError(
                        "Server process exited before tool completion"
                    )
        if time.monotonic() > deadline:
            raise ToolNotDoneError(
                f"Tool completion pattern {pattern!r} not seen within {timeout_s}s"
            )
        raise ToolNotDoneError("Server stdout closed before tool completion")
    finally:
        watchdog.cancel()


def collect_crash_reports(loader_run_dir: Path, crash_dst_dir: Path) -> list[Path]:
    """
    Copy crash-reports/ from the server run dir into job_dir/crash-reports/.
    Returns list of copied destination paths (empty if no crash reports found).
    """
    return collect_new_crash_reports(loader_run_dir, crash_dst_dir, ignore_names=set())


def existing_crash_report_names(loader_run_dir: Path) -> set[str]:
    crash_src = loader_run_dir / "crash-reports"
    if not crash_src.exists():
        return set()
    return {f.name for f in crash_src.glob("*") if f.is_file()}


def collect_new_crash_reports(
    loader_run_dir: Path,
    crash_dst_dir: Path,
    *,
    ignore_names: set[str],
) -> list[Path]:
    """
    Copy crash reports created during this job.

    Gradle run dirs are persistent local state and may already contain old
    crash reports. Those are useful to keep locally, but they are not evidence
    that the current job crashed.
    """
    crash_src = loader_run_dir / "crash-reports"
    if not crash_src.exists():
        return []
    files = [
        f for f in crash_src.glob("*") if f.is_file() and f.name not in ignore_names
    ]
    if not files:
        return []
    crash_dst_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in files:
        dst = crash_dst_dir / f.name
        shutil.copy2(f, dst)
        copied.append(dst)
    return copied
