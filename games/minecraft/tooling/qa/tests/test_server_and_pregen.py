from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from squinch_qa.executors._server import ServerLaunchError, launch_server
from squinch_qa.executors.command_script import CommandScriptExecutor
from squinch_qa.executors.server_smoke import ServerSmokeExecutor
from squinch_qa.executors.pregen import PregenExecutor
from squinch_qa.models import Target
from squinch_qa.pregen_tools import AcquiredJar, AcquisitionError, acquire_jar


# ── Shared env patch ──────────────────────────────────────────────────────────


def _fake_env(repo_root: Path) -> dict:
    return dict(os.environ)


# ── AcquiredJar factory ───────────────────────────────────────────────────────


def _make_fake_acquire(tmp_path: Path, *, tool_that_fails: str | None = None):
    """
    Factory: returns an acquire_jar stand-in.

    Every tool succeeds and writes a stub jar, except `tool_that_fails` (if
    given), which raises AcquisitionError -- exercising the pregen fallback
    path when a single tool in the preference list can't be acquired.
    """

    def _acquire(tool_name, mc_version, loader, *, pinned_sha256=None):
        if tool_name == tool_that_fails:
            raise AcquisitionError(f"{tool_name}: no release on Modrinth (test stub)")
        jar = tmp_path / f"{tool_name}-stub.jar"
        jar.write_bytes(b"PK\x03\x04" + b"\x00" * 26)
        from squinch_qa.artifacts import sha256_file

        return AcquiredJar(
            path=jar,
            sha256=sha256_file(jar),
            tool_name=tool_name,
            version="1.0.0-stub",
        )

    return _acquire


def _seed_crash_report(run_dir: Path, name: str = "crash-2026-01-01.txt") -> Path:
    """Pre-seed a fake crash report on disk, as a real crashed server would."""
    crash_dir = run_dir / "crash-reports"
    crash_dir.mkdir(parents=True, exist_ok=True)
    crash_file = crash_dir / name
    crash_file.write_text("fake crash for test\n")
    return crash_file


def _configure_fake_crash_writer(monkeypatch, run_dir: Path, *, mode: str) -> None:
    monkeypatch.setenv("FAKE_CRASH_REPORT_DIR", str(run_dir / "crash-reports"))
    if mode == "before-ready":
        monkeypatch.setenv("FAKE_WRITE_CRASH_BEFORE_READY", "1")
    elif mode == "on-stop":
        monkeypatch.setenv("FAKE_WRITE_CRASH_ON_STOP", "1")
    else:
        raise ValueError(f"unknown fake crash mode: {mode}")


def _write_loader_marker_jar(path: Path, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(marker, "{}\n")


# ── Class 1: Server-smoke pass path ──────────────────────────────────────────


class TestServerSmoke:
    @pytest.mark.slow
    def test_server_smoke_pass(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        result = ServerSmokeExecutor().run(ctx)
        assert result.status == "pass"

    @pytest.mark.slow
    def test_server_logs_created(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        ServerSmokeExecutor().run(ctx)
        assert (ctx.job_dir / "logs" / "server.stdout.log").exists()

    @pytest.mark.slow
    def test_no_crash_reports_on_pass(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        result = ServerSmokeExecutor().run(ctx)
        crash_dir = ctx.job_dir / "crash-reports"
        assert result.status == "pass"
        assert not crash_dir.exists() or not any(crash_dir.iterdir())

    @pytest.mark.slow
    def test_stale_crash_reports_do_not_fail_new_run(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        _seed_crash_report(ctx.mod_dir / "forge" / "run", name="stale-crash.txt")

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "pass"
        assert not (ctx.job_dir / "crash-reports" / "stale-crash.txt").exists()

    @pytest.mark.slow
    def test_server_smoke_uses_qa_specific_level_name(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "pass"
        properties = (ctx.mod_dir / "forge" / "run" / "server.properties").read_text()
        assert "level-name=qa-test-run-forge-1.20.1-server-smoke" in properties
        assert "server-port=0" in properties

    @pytest.mark.slow
    def test_server_smoke_does_not_hang_when_stop_is_ignored(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setenv("FAKE_IGNORE_STOP", "1")
        ctx = make_job_context(
            test_id="server-smoke",
            target_id="forge-1.20.1",
            config={"shutdown_timeout_s": 0.2},
        )
        result = ServerSmokeExecutor().run(ctx)
        assert result.status == "pass"


# ── Class 1b: Server-smoke error/failure classification branches ────────────
#
# server_smoke.py's run() has 6 result-classification branches. These drive
# each one for real via the stub gradlew/fake_server.py boundary (or, for
# gradle-env-error, the real .sdkmanrc-missing boundary) rather than
# monkeypatching the classification function itself.


class TestServerSmokeErrorClassification:
    def test_gradle_env_error_when_sdkmanrc_missing(self, make_job_context):
        # runner_repo never creates games/minecraft/tooling/.sdkmanrc, so the
        # *real* resolve_gradle_env fails deterministically -- no monkeypatch
        # needed, and no subprocess is ever launched.
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        result = ServerSmokeExecutor().run(ctx)
        assert result.status == "error"
        assert result.failure.reason == "gradle-env-error"
        assert ".sdkmanrc" in result.failure.detail

    def test_launch_failed_when_gradlew_missing(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        (ctx.mod_dir / "gradlew").unlink()  # real subprocess exec failure

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "error"
        assert result.failure.reason == "launch-failed"

    @pytest.mark.slow
    def test_server_not_ready_times_out(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setenv("FAKE_NO_READY", "1")
        ctx = make_job_context(
            test_id="server-smoke",
            target_id="forge-1.20.1",
            config={"timeout_s": 0.3, "shutdown_timeout_s": 0.2},
        )

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "server-not-ready"

    @pytest.mark.slow
    def test_crash_before_ready_when_crash_report_present(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setenv("FAKE_NO_READY", "1")
        ctx = make_job_context(
            test_id="server-smoke",
            target_id="forge-1.20.1",
            config={"timeout_s": 0.3, "shutdown_timeout_s": 0.2},
        )
        loader_run_dir = ctx.mod_dir / "forge" / "run"
        _configure_fake_crash_writer(monkeypatch, loader_run_dir, mode="before-ready")

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "crash-before-ready"
        assert (ctx.job_dir / "crash-reports" / "crash-before-ready.txt").exists()

    @pytest.mark.slow
    def test_crash_reports_after_clean_shutdown(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.server_smoke.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(test_id="server-smoke", target_id="forge-1.20.1")
        loader_run_dir = ctx.mod_dir / "forge" / "run"
        _configure_fake_crash_writer(monkeypatch, loader_run_dir, mode="on-stop")

        result = ServerSmokeExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "crash-reports"
        assert "crash-on-stop.txt" in result.failure.detail
        assert (ctx.job_dir / "crash-reports" / "crash-on-stop.txt").exists()


# ── Class 1c: Command-script behavior tests ─────────────────────────────────


class TestCommandScript:
    @pytest.mark.slow
    def test_command_script_passes_when_commands_emit_expected_output(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.command_script.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(
            test_id="tick-freeze",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "commands": ["tick freeze", "tick step 1", "tick query"],
                "expect_output": [
                    "The game is frozen",
                    "Stepping 1 tick",
                    "The game runs normally",
                ],
            },
        )
        ctx.adapter = {"type": "command-script"}

        result = CommandScriptExecutor().run(ctx)

        assert result.status == "pass"
        log = (ctx.job_dir / "logs" / "server.stdout.log").read_text()
        assert "The game is frozen" in log

    @pytest.mark.slow
    def test_command_script_fails_when_expected_output_is_missing(
        self, monkeypatch, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.command_script.resolve_gradle_env",
            _fake_env,
        )
        ctx = make_job_context(
            test_id="crafter-basic",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "commands": ["setblock 0 64 0 redstone_backport:crafter"],
                "expect_output": ["pattern that the server never prints"],
                "timeout_s": 0.2,
                "shutdown_timeout_s": 0.2,
            },
        )
        ctx.adapter = {"type": "command-script"}

        result = CommandScriptExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "expected-output-not-seen"

    def test_command_script_rejects_empty_assertions(self, make_job_context):
        ctx = make_job_context(
            test_id="tick-freeze",
            target_id="forge-1.20.1",
            config={"commands": ["tick query"], "expect_output": []},
        )
        ctx.adapter = {"type": "command-script"}

        result = CommandScriptExecutor().run(ctx)

        assert result.status == "error"
        assert result.failure.reason == "invalid-command-script-config"

    def test_command_script_rejects_unknown_adapter_type(self, make_job_context):
        ctx = make_job_context(
            test_id="tick-freeze",
            target_id="forge-1.20.1",
            config={"commands": ["tick query"], "expect_output": ["The game"]},
        )
        ctx.adapter = {"type": "gametest"}

        result = CommandScriptExecutor().run(ctx)

        assert result.status == "error"
        assert result.failure.reason == "unsupported-adapter"

    @pytest.mark.slow
    def test_forge_defaults_to_production_runtime(self, monkeypatch, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.command_script.resolve_gradle_env",
            _fake_env,
        )
        calls = []
        ctx = make_job_context(
            test_id="tick-freeze",
            target_id="forge-1.20.1",
            config={
                "commands": ["tick freeze"],
                "expect_output": ["The game is frozen"],
            },
            target=Target(
                id="forge-1.20.1",
                minecraft="1.20.1",
                loader="forge",
                loader_version="47.4.0",
                java=17,
                supported=True,
                capabilities=["server", "command-script"],
            ),
        )
        ctx.adapter = {"type": "command-script"}

        def _fake_forge_production(**kwargs):
            calls.append(kwargs)
            proc, log_path = launch_server(
                "forge",
                ctx.mod_dir,
                _fake_env(ctx.repo_root),
                kwargs["logs_dir"],
            )
            return proc, log_path, ctx.mod_dir / "forge" / "run"

        monkeypatch.setattr(
            "squinch_qa.executors.command_script.launch_forge_production_server",
            _fake_forge_production,
        )

        result = CommandScriptExecutor().run(ctx)

        assert result.status == "pass"
        assert calls
        assert calls[0]["tool_jar"] is None
        assert calls[0]["forge_version"] == "47.4.0"


# ── Class 2: Pregen success/fallback paths ───────────────────────────────────


class TestPregen:
    @pytest.mark.slow
    def test_pregen_with_stub_chunksmith(self, monkeypatch, tmp_path, make_job_context):
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "preset": "xs",
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith", "chunky"],
            },
        )
        result = PregenExecutor().run(ctx)
        assert result.status == "pass"
        assert result.tool_used == "chunksmith"

    @pytest.mark.slow
    def test_chunky_fallback_when_chunksmith_acquisition_raises(
        self, monkeypatch, tmp_path, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path, tool_that_fails="chunksmith"),
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "preset": "xs",
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith", "chunky"],
            },
        )
        result = PregenExecutor().run(ctx)
        assert result.status == "pass"
        assert result.tool_used == "chunky"

    @pytest.mark.slow
    def test_executed_tool_error_is_not_fallback_trigger(
        self, monkeypatch, tmp_path, make_job_context
    ):
        """A tool jar successfully placed but timed-out in-game → fail, no fallback."""
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        monkeypatch.setenv("FAKE_SUPPRESS_TOOL_COMPLETION", "1")
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "preset": "xs",
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith", "chunky"],
                "timeout_s": 10,
            },
        )
        result = PregenExecutor().run(ctx)
        assert result.status == "fail"
        assert result.tool_used == "chunksmith"


# ── Class 2b: Pregen error/failure classification branches ──────────────────


class TestPregenErrorClassification:
    def test_all_tools_acquisition_failed(self, monkeypatch, make_job_context):
        def _always_fail(tool_name, mc_version, loader, *, pinned_sha256=None):
            raise AcquisitionError(f"{tool_name}: no release on Modrinth (test stub)")

        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _always_fail,
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith", "chunky"],
            },
        )

        result = PregenExecutor().run(ctx)

        assert result.status == "error"
        assert result.failure.reason == "all-tools-acquisition-failed"
        assert "chunksmith" in result.failure.detail
        assert "chunky" in result.failure.detail
        assert result.tool_used is None

    def test_gradle_env_error_when_sdkmanrc_missing(
        self, monkeypatch, tmp_path, make_job_context
    ):
        # Real resolve_gradle_env is exercised (no monkeypatch): runner_repo
        # never creates .sdkmanrc, so this fails deterministically after a
        # successful (stubbed) jar acquisition.
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith"],
            },
        )

        result = PregenExecutor().run(ctx)

        assert result.status == "error"
        assert result.failure.reason == "gradle-env-error"
        assert result.tool_used == "chunksmith"
        assert result.jar_sha256 is not None

    def test_launch_failed_when_gradlew_missing(
        self, monkeypatch, tmp_path, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith"],
            },
        )
        (ctx.mod_dir / "gradlew").unlink()  # real subprocess exec failure

        result = PregenExecutor().run(ctx)

        assert result.status == "fail"  # tool jar was placed; failure, not error
        assert result.failure.reason == "launch-failed"
        assert result.tool_used == "chunksmith"

    @pytest.mark.slow
    def test_tool_command_delivery_failed(
        self, monkeypatch, tmp_path, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        monkeypatch.setenv("FAKE_CLOSE_STDIN_AFTER_READY", "1")
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith"],
                # Safety net: if the write ever doesn't fail as expected, fail
                # fast instead of hanging on DEFAULT_PREGEN_TIMEOUT_S (3600s).
                "timeout_s": 15,
            },
        )

        result = PregenExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "tool-command-delivery-failed"
        assert result.tool_used == "chunksmith"

    @pytest.mark.slow
    def test_crash_reports_after_successful_pregen_run(
        self, monkeypatch, tmp_path, make_job_context
    ):
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "server_runtime": "gradle-dev",
                "tool_preference": ["chunksmith"],
            },
        )
        loader_run_dir = ctx.mod_dir / "forge" / "run"
        _configure_fake_crash_writer(monkeypatch, loader_run_dir, mode="on-stop")

        result = PregenExecutor().run(ctx)

        assert result.status == "fail"
        assert result.failure.reason == "crash-reports"
        assert result.tool_used == "chunksmith"


# ── Class 2c: Pregen default server_runtime selection ───────────────────────


class TestPregenServerRuntimeDefault:
    def test_defaults_to_forge_production_when_loader_is_forge(
        self, monkeypatch, tmp_path, make_job_context
    ):
        """
        server_runtime omitted from config + loader 'forge' must select
        'forge-production' (pregen.py: _launch_pregen_server's default). The
        real forge-production download/install flow is out of scope here --
        the production launcher is monkeypatched at the boundary just to
        prove *which* runtime got selected.
        """
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.resolve_gradle_env",
            _fake_env,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.acquire_jar",
            _make_fake_acquire(tmp_path),
        )

        calls = []

        def _fake_forge_production(**kwargs):
            calls.append(kwargs)
            raise ServerLaunchError("forge-production-selected-marker")

        def _fail_if_gradle_dev_used(*args, **kwargs):
            pytest.fail("gradle-dev launch_server should not run for forge default")

        monkeypatch.setattr(
            "squinch_qa.executors.pregen.launch_forge_production_server",
            _fake_forge_production,
        )
        monkeypatch.setattr(
            "squinch_qa.executors.pregen.launch_server",
            _fail_if_gradle_dev_used,
        )

        target = Target(
            id="forge-1.20.1",
            minecraft="1.20.1",
            loader="forge",
            loader_version="47.4.0",
            java=17,
            supported=True,
            capabilities=[],
        )
        ctx = make_job_context(
            test_id="pregen",
            target_id="forge-1.20.1",
            config={
                "preset": "xs",
                "tool_preference": ["chunksmith"],
                # server_runtime intentionally omitted
            },
            target=target,
        )

        result = PregenExecutor().run(ctx)

        assert len(calls) == 1
        assert result.status == "fail"
        assert result.failure.reason == "launch-failed"
        assert "forge-production-selected-marker" in result.failure.detail


# ── Class 3: acquire_jar offline guard ───────────────────────────────────────


class TestAcquireJarOffline:
    def test_offline_raises_when_not_cached(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SQINCHMODS_QA_OFFLINE", "1")
        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path))
        with pytest.raises(AcquisitionError):
            acquire_jar("chunksmith", "1.20.1", "forge")

    def test_offline_returns_cached_jar(self, monkeypatch, tmp_path):
        cache_root = tmp_path / "qa" / "pregen-tools" / "chunksmith" / "forge" / "1.0.0"
        jar = cache_root / "chunksmith-1.0.0.jar"
        _write_loader_marker_jar(jar, "META-INF/mods.toml")

        monkeypatch.setenv("SQINCHMODS_QA_OFFLINE", "1")
        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path))
        result = acquire_jar("chunksmith", "1.20.1", "forge")
        assert result.path == jar
        assert result.tool_name == "chunksmith"
        assert result.loader == "forge"

    def test_offline_rejects_cached_jar_for_wrong_loader(self, monkeypatch, tmp_path):
        cache_root = tmp_path / "qa" / "pregen-tools" / "chunky" / "forge" / "1.3.146"
        jar = cache_root / "Chunky-1.3.146.jar"
        _write_loader_marker_jar(jar, "META-INF/mods.toml")

        monkeypatch.setenv("SQINCHMODS_QA_OFFLINE", "1")
        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path))

        with pytest.raises(AcquisitionError, match="no cached 'fabric' jar"):
            acquire_jar("chunky", "1.20.1", "fabric")

    def test_download_cache_is_scoped_by_effective_loader(self, monkeypatch, tmp_path):
        forge_cache = (
            tmp_path
            / "qa"
            / "pregen-tools"
            / "chunky"
            / "forge"
            / "1.3.146"
            / "Chunky-1.3.146.jar"
        )
        _write_loader_marker_jar(forge_cache, "META-INF/mods.toml")

        def fake_modrinth_get(path):
            assert "loaders=%5B%22fabric%22%5D" in path
            return [
                {
                    "id": "fabric-version",
                    "version_number": "1.3.146",
                    "files": [
                        {
                            "filename": "Chunky-1.3.146.jar",
                            "primary": True,
                            "url": "https://example.invalid/fabric-chunky.jar",
                        }
                    ],
                }
            ]

        def fake_download_file(url, dest):
            assert url == "https://example.invalid/fabric-chunky.jar"
            _write_loader_marker_jar(dest, "fabric.mod.json")

        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path))
        monkeypatch.setattr("squinch_qa.pregen_tools._modrinth_get", fake_modrinth_get)
        monkeypatch.setattr(
            "squinch_qa.pregen_tools._download_file", fake_download_file
        )

        result = acquire_jar("chunky", "1.20.1", "fabric")

        assert result.loader == "fabric"
        assert result.path == (
            tmp_path
            / "qa"
            / "pregen-tools"
            / "chunky"
            / "fabric"
            / "1.3.146"
            / "Chunky-1.3.146.jar"
        )
        with zipfile.ZipFile(result.path) as zf:
            assert "fabric.mod.json" in zf.namelist()

    def test_quilt_can_use_fabric_compatible_tool_when_no_quilt_file_exists(
        self, monkeypatch, tmp_path
    ):
        requested_loaders: list[str] = []

        def fake_modrinth_get(path):
            if "loaders=%5B%22quilt%22%5D" in path:
                requested_loaders.append("quilt")
                return []
            if "loaders=%5B%22fabric%22%5D" in path:
                requested_loaders.append("fabric")
                return [
                    {
                        "id": "fabric-version",
                        "version_number": "1.3.146",
                        "files": [
                            {
                                "filename": "Chunky-1.3.146.jar",
                                "primary": True,
                                "url": "https://example.invalid/fabric-chunky.jar",
                            }
                        ],
                    }
                ]
            raise AssertionError(f"unexpected Modrinth path: {path}")

        def fake_download_file(url, dest):
            _write_loader_marker_jar(dest, "fabric.mod.json")

        monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path))
        monkeypatch.setattr("squinch_qa.pregen_tools._modrinth_get", fake_modrinth_get)
        monkeypatch.setattr(
            "squinch_qa.pregen_tools._download_file", fake_download_file
        )

        result = acquire_jar("chunky", "1.20.1", "quilt")

        assert requested_loaders == ["quilt", "fabric"]
        assert result.loader == "fabric"
        assert result.path.parent.parent.name == "fabric"
