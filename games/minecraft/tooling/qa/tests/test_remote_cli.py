from __future__ import annotations

from pathlib import Path

from squinch_qa.artifacts import default_qa_runs_dir
from squinch_qa import cli
from squinch_qa.remote.errors import DispatchError, DownloadError, PollTimeoutError


class TestRemoteCli:
    def test_remote_run_plumbs_arguments(self, fake_repo: Path, monkeypatch) -> None:
        calls = []

        def fake_remote_run(**kwargs):
            calls.append(kwargs)
            kwargs["emit"]({"type": "fake", "run_id": kwargs["run_id"]})
            return 0

        monkeypatch.setattr("squinch_qa.remote.remote_run", fake_remote_run)

        code = cli.main(
            [
                "remote-run",
                "redstone-backport",
                "--repo-root",
                str(fake_repo),
                "--qa-runs-dir",
                str(fake_repo / "runs"),
                "--target",
                "forge-1.20.1",
                "--profile",
                "dev",
                "--promote",
                "--poll-interval",
                "0.5",
                "--timeout",
                "10",
                "--run-id",
                "1234567890-deadbeef",
            ]
        )

        assert code == 0
        assert calls[0]["mod"] == "redstone-backport"
        assert calls[0]["repo_root"] == fake_repo
        assert calls[0]["qa_runs_dir"] == fake_repo / "runs"
        assert calls[0]["target"] == "forge-1.20.1"
        assert calls[0]["profile"] == "dev"
        assert calls[0]["promote"] is True
        assert calls[0]["poll_interval"] == 0.5
        assert calls[0]["timeout"] == 10
        assert calls[0]["run_id"] == "1234567890-deadbeef"
        assert calls[0]["clean"] is True

    def test_remote_run_plumbs_no_clean(self, fake_repo: Path, monkeypatch) -> None:
        calls = []

        def fake_remote_run(**kwargs):
            calls.append(kwargs)
            return 0

        monkeypatch.setattr("squinch_qa.remote.remote_run", fake_remote_run)

        code = cli.main(
            [
                "remote-run",
                "redstone-backport",
                "--repo-root",
                str(fake_repo),
                "--no-clean",
            ]
        )

        assert code == 0
        assert calls[0]["clean"] is False

    def test_remote_run_defaults_to_minecraft_qa_runs_dir(
        self, fake_repo: Path, monkeypatch
    ) -> None:
        calls = []

        def fake_remote_run(**kwargs):
            calls.append(kwargs)
            return 0

        monkeypatch.setattr("squinch_qa.remote.remote_run", fake_remote_run)

        code = cli.main(
            ["remote-run", "redstone-backport", "--repo-root", str(fake_repo)]
        )

        assert code == 0
        assert calls[0]["qa_runs_dir"] == default_qa_runs_dir(fake_repo)

    def test_unknown_mod_exits_before_dispatch(self, fake_repo, monkeypatch) -> None:
        monkeypatch.setattr(
            "squinch_qa.remote.remote_run",
            lambda **kw: (_ for _ in ()).throw(AssertionError("should not dispatch")),
        )

        code = cli.main(["remote-run", "missing-mod", "--repo-root", str(fake_repo)])

        assert code == 1

    def test_remote_dispatch_error_exits_7(self, fake_repo, monkeypatch) -> None:
        monkeypatch.setattr(
            "squinch_qa.remote.remote_run",
            lambda **kw: (_ for _ in ()).throw(DispatchError("no auth")),
        )

        code = cli.main(
            ["remote-run", "redstone-backport", "--repo-root", str(fake_repo)]
        )

        assert code == 7

    def test_remote_poll_timeout_exits_8(self, fake_repo, monkeypatch) -> None:
        monkeypatch.setattr(
            "squinch_qa.remote.remote_run",
            lambda **kw: (_ for _ in ()).throw(PollTimeoutError("slow")),
        )

        code = cli.main(
            ["remote-run", "redstone-backport", "--repo-root", str(fake_repo)]
        )

        assert code == 8

    def test_remote_download_error_exits_9(self, fake_repo, monkeypatch) -> None:
        monkeypatch.setattr(
            "squinch_qa.remote.remote_run",
            lambda **kw: (_ for _ in ()).throw(DownloadError("missing artifact")),
        )

        code = cli.main(
            ["remote-run", "redstone-backport", "--repo-root", str(fake_repo)]
        )

        assert code == 9
