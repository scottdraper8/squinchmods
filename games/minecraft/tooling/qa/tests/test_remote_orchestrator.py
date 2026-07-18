from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from squinch_qa.artifacts import default_qa_root, default_qa_runs_dir
from squinch_qa.remote import _gh, orchestrator
from squinch_qa.remote.orchestrator import _downloaded_exit_code
from squinch_qa.remote.poll import RunCompletion


def _write_result(run_dir: Path, exit_code: int) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "result.json").write_text(f'{{"exit_code": {exit_code}}}')
    return run_dir


def _world_src(tmp_path: Path) -> Path:
    src = tmp_path / "world-src"
    (src / "region").mkdir(parents=True)
    (src / "region" / "r.0.0.mca").write_bytes(b"chunk data")
    return src


@pytest.fixture
def stub_remote_calls(tmp_path: Path, monkeypatch):
    """
    Patches orchestrator.dispatch_run/wait_for_completion/download_run with
    thin trampolines that delegate to overridable attributes on the returned
    namespace. Tests only assign the attributes they care about; the rest
    keep their success-path defaults (dispatch does nothing, the run
    completes successfully, and download drops a passing result.json).
    """
    stubs = SimpleNamespace(
        dispatch_run=lambda **kw: None,
        wait_for_completion=lambda *a, **kw: RunCompletion(42, "completed", "success"),
        download_run=lambda **kw: _write_result(tmp_path / "run", 0),
    )

    monkeypatch.setattr(
        orchestrator, "dispatch_run", lambda **kw: stubs.dispatch_run(**kw)
    )
    monkeypatch.setattr(
        orchestrator,
        "wait_for_completion",
        lambda *a, **kw: stubs.wait_for_completion(*a, **kw),
    )
    monkeypatch.setattr(
        orchestrator, "download_run", lambda **kw: stubs.download_run(**kw)
    )

    return stubs


class TestRemoteOrchestrator:
    def test_success_dispatches_polls_downloads_and_returns_zero(
        self, tmp_path: Path, stub_remote_calls
    ) -> None:
        events = []
        calls = []
        downloads = []

        stub_remote_calls.dispatch_run = lambda **kw: calls.append(("dispatch", kw))
        stub_remote_calls.download_run = lambda **kw: downloads.append(
            kw
        ) or _write_result(default_qa_runs_dir(tmp_path) / "1234567890-deadbeef", 0)

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            target="forge-1.20.1",
            profile="dev",
            run_id="1234567890-deadbeef",
            emit=events.append,
        )

        assert code == 0
        assert calls[0][1]["run_id"] == "1234567890-deadbeef"
        assert downloads[0]["qa_runs_dir"] == default_qa_runs_dir(tmp_path)
        assert events[0]["type"] == "remote_run_start"
        assert events[-1] == {
            "type": "remote_run_complete",
            "run_id": "1234567890-deadbeef",
            "status": "pass",
            "exit_code": 0,
        }

    def test_remote_failure_still_downloads_and_returns_qa_failure(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        downloaded = []
        promoted = []

        stub_remote_calls.wait_for_completion = lambda *a, **kw: RunCompletion(
            42, "completed", "failure"
        )
        stub_remote_calls.download_run = lambda **kw: downloaded.append(
            kw
        ) or _write_result(tmp_path / "run", 4)
        monkeypatch.setattr(
            orchestrator,
            "promote_run",
            lambda *a, **kw: promoted.append((a, kw)),
        )

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            promote=True,
        )

        assert code == 4
        assert downloaded
        assert promoted == []

    def test_remote_failure_preserves_downloaded_exit_code(
        self, tmp_path: Path, stub_remote_calls
    ) -> None:
        stub_remote_calls.wait_for_completion = lambda *a, **kw: RunCompletion(
            42, "completed", "failure"
        )
        stub_remote_calls.download_run = lambda **kw: _write_result(tmp_path / "run", 6)

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
        )

        assert code == 6

    def test_promotion_failure_returns_replace_exit_code(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        monkeypatch.setattr(orchestrator, "recover_pending", lambda *a, **kw: None)
        monkeypatch.setattr(
            orchestrator,
            "promote_run",
            lambda *a, **kw: [
                SimpleNamespace(
                    mod_id="fake-mod",
                    target_id="t",
                    test_id="pregen",
                    promoted=False,
                    reason="promote_failed",
                    is_failure=True,
                )
            ],
        )

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            promote=True,
        )

        assert code == 6

    def test_promotion_validation_failure_does_not_recover_pending(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        recovered = []

        monkeypatch.setattr(
            orchestrator,
            "recover_pending",
            lambda *a, **kw: recovered.append(a),
        )
        monkeypatch.setattr(
            orchestrator,
            "promote_run",
            lambda *a, **kw: [
                SimpleNamespace(
                    mod_id="fake-mod",
                    target_id="t",
                    test_id="pregen",
                    promoted=False,
                    reason="hash_mismatch",
                    is_failure=True,
                )
            ],
        )

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            promote=True,
        )

        assert code == 6
        # promote_run is itself all-or-nothing (validates every job before
        # promoting any of them), so recovering prior interrupted state ahead
        # of it is always safe and now happens unconditionally.
        assert recovered == [(default_qa_root(tmp_path),)]

    def test_valid_promotion_recovers_then_promotes(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        recovered = []
        promote_calls = []

        monkeypatch.setattr(
            orchestrator,
            "recover_pending",
            lambda *a, **kw: recovered.append(a),
        )

        def fake_promote_run(*args, **kwargs):
            promote_calls.append(kwargs)
            return [
                SimpleNamespace(
                    mod_id="fake-mod",
                    target_id="t",
                    test_id="pregen",
                    promoted=True,
                    reason=None,
                    is_failure=False,
                )
            ]

        monkeypatch.setattr(orchestrator, "promote_run", fake_promote_run)

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            promote=True,
        )

        assert code == 0
        assert recovered == [(default_qa_root(tmp_path),)]
        # promote_run's own all-or-nothing gating replaces the old
        # dry-run-then-real two-call dance — a single real call now.
        assert promote_calls == [{}]

    def test_remote_promote_writes_default_minecraft_qa_current(
        self, tmp_path: Path, stub_remote_calls, qa_run_factory
    ) -> None:
        from squinch_qa.replace.layout import current_job_dir

        run_dir = qa_run_factory(
            runs_root=default_qa_runs_dir(tmp_path),
            run_id="1234567890-deadbeef",
            mod_id="redstone-backport",
            jobs=[
                {
                    "target_id": "forge-1.20.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ],
        )
        (run_dir / "result.json").write_text('{"exit_code": 0}')
        stub_remote_calls.download_run = lambda **kw: run_dir

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            promote=True,
        )

        assert code == 0
        cur = current_job_dir(
            default_qa_root(tmp_path), "redstone-backport", "forge-1.20.1", "pregen"
        )
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"chunk data"

    def test_remote_promote_through_gh_boundary_downloads_real_artifact(
        self, tmp_path: Path, monkeypatch, qa_run_factory
    ) -> None:
        # This test exercises the real gh boundary end to end, so it does not
        # use stub_remote_calls (which patches dispatch_run/wait_for_completion/
        # download_run themselves out of the picture).
        from squinch_qa.replace.layout import current_job_dir

        run_id = "1234567890-deadbeef"
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init"], cwd=repo_root, capture_output=True, check=True)
        artifact_src = qa_run_factory(
            runs_root=tmp_path / "artifacts",
            run_id=run_id,
            mod_id="redstone-backport",
            jobs=[
                {
                    "target_id": "forge-1.20.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ],
        )
        (artifact_src / "result.json").write_text('{"exit_code": 0}')

        def fake_run_gh(*args, timeout, cwd, check=True):
            if args[:3] == ("workflow", "run", "qa-remote.yml"):
                return _gh.GhResult(tuple(args), 0, "", "")
            if args[:2] == ("run", "list"):
                return _gh.GhResult(
                    tuple(args),
                    0,
                    json.dumps(
                        [
                            {
                                "databaseId": 42,
                                "displayTitle": f"qa-{run_id}",
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ]
                    ),
                    "",
                )
            if args[:2] == ("run", "view"):
                return _gh.GhResult(
                    tuple(args), 0, '{"status":"completed","conclusion":"success"}', ""
                )
            if args[:2] == ("run", "download"):
                out_dir = Path(args[args.index("--dir") + 1])
                for child in artifact_src.iterdir():
                    dest = out_dir / child.name
                    if child.is_dir():
                        shutil.copytree(child, dest)
                    else:
                        shutil.copy2(child, dest)
                return _gh.GhResult(tuple(args), 0, "", "")
            raise AssertionError(f"unexpected gh args: {args!r}")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=repo_root,
            run_id=run_id,
            promote=True,
            poll_interval=0.0,
            clean=False,
        )

        assert code == 0
        downloaded = default_qa_runs_dir(repo_root) / run_id
        assert (downloaded / "qa-manifest.json").exists()
        cur = current_job_dir(
            default_qa_root(repo_root), "redstone-backport", "forge-1.20.1", "pregen"
        )
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"chunk data"

    def test_remote_cleans_after_download_by_default(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        from squinch_qa.cleanup import CleanAction

        calls = []
        stub_remote_calls.download_run = lambda **kw: _write_result(
            default_qa_runs_dir(tmp_path) / kw["run_id"], 0
        )

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

        monkeypatch.setattr("squinch_qa.cleanup.clean_qa", fake_clean_qa)

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
        )

        assert code == 0
        assert calls == [default_qa_root(tmp_path)]

    def test_remote_clean_false_skips_cleanup(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        stub_remote_calls.download_run = lambda **kw: _write_result(
            default_qa_runs_dir(tmp_path) / kw["run_id"], 0
        )
        monkeypatch.setattr(
            "squinch_qa.cleanup.clean_qa",
            lambda *a, **k: pytest.fail("cleanup should be disabled"),
        )

        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            clean=False,
        )

        assert code == 0

    def test_clean_error_is_captured_as_event_and_does_not_crash_run(
        self, tmp_path: Path, monkeypatch, stub_remote_calls
    ) -> None:
        stub_remote_calls.download_run = lambda **kw: _write_result(
            default_qa_runs_dir(tmp_path) / kw["run_id"], 0
        )

        def failing_clean_qa(qa_root):
            raise RuntimeError("disk full")

        monkeypatch.setattr("squinch_qa.cleanup.clean_qa", failing_clean_qa)

        events = []
        code = orchestrator.remote_run(
            mod="redstone-backport",
            repo_root=tmp_path,
            run_id="1234567890-deadbeef",
            emit=events.append,
        )

        # A clean_qa failure must not crash the overall run: the exit code
        # still reflects the QA result, and the failure is surfaced as an
        # event rather than propagating.
        assert code == 0
        clean_error_events = [e for e in events if e["type"] == "clean_error"]
        assert len(clean_error_events) == 1
        assert clean_error_events[0]["error"] == "disk full"
        assert events[-1]["type"] == "remote_run_complete"


class TestDownloadedExitCode:
    def test_missing_result_file_returns_default(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        assert _downloaded_exit_code(run_dir, default=4) == 4

    def test_malformed_json_returns_default(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "result.json").write_text("not json at all")

        assert _downloaded_exit_code(run_dir, default=4) == 4

    def test_unreadable_result_file_returns_default(self, tmp_path: Path) -> None:
        # Make result.json a directory rather than a file so read_text()
        # raises IsADirectoryError (an OSError subclass) instead of
        # returning content, without depending on filesystem permission
        # semantics (which differ when tests run as root).
        run_dir = tmp_path / "run"
        (run_dir / "result.json").mkdir(parents=True)

        assert _downloaded_exit_code(run_dir, default=4) == 4

    def test_negative_exit_code_rejected_and_falls_back_to_default(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "result.json").write_text('{"exit_code": -1}')

        assert _downloaded_exit_code(run_dir, default=4) == 4

    def test_out_of_range_exit_code_rejected_and_falls_back_to_default(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "result.json").write_text('{"exit_code": 256}')

        assert _downloaded_exit_code(run_dir, default=4) == 4

    def test_valid_boundary_exit_codes_are_accepted(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        (run_dir / "result.json").write_text('{"exit_code": 0}')
        assert _downloaded_exit_code(run_dir, default=9) == 0

        (run_dir / "result.json").write_text('{"exit_code": 255}')
        assert _downloaded_exit_code(run_dir, default=9) == 255
