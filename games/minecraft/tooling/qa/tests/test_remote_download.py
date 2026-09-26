from __future__ import annotations

from pathlib import Path

import pytest

from squinch_qa.remote import _gh
from squinch_qa.remote.download import download_run
from squinch_qa.remote.errors import DownloadError, GhError


class TestRemoteDownload:
    def test_downloads_named_artifact_into_run_dir(self, tmp_path: Path, monkeypatch):
        calls = []

        def fake_run_gh(*args, timeout, cwd, check=True):
            calls.append((args, timeout, cwd))
            out_dir = Path(args[args.index("--dir") + 1])
            (out_dir / "qa-manifest.json").write_text("{}")
            return _gh.GhResult(tuple(args), 0, "", "")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        run_dir = download_run(
            database_id=42,
            run_id="1234567890-deadbeef",
            qa_runs_dir=tmp_path / "qa-runs",
            repo_root=tmp_path,
        )

        assert run_dir == (tmp_path / "qa-runs" / "1234567890-deadbeef").resolve()
        args, timeout, cwd = calls[0]
        assert args == (
            "run",
            "download",
            "42",
            "--name",
            "qa-1234567890-deadbeef",
            "--dir",
            str(run_dir),
        )
        assert timeout == 120.0
        assert cwd == tmp_path

    def test_refuses_to_merge_into_nonempty_run_dir(self, tmp_path, monkeypatch):
        run_dir = tmp_path / "qa-runs" / "1234567890-deadbeef"
        run_dir.mkdir(parents=True)
        (run_dir / "old.txt").write_text("stale")
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: pytest.fail("gh should not be called"),
        )

        with pytest.raises(DownloadError, match="not empty"):
            download_run(
                database_id=42,
                run_id="1234567890-deadbeef",
                qa_runs_dir=tmp_path / "qa-runs",
            )

    def test_missing_manifest_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: _gh.GhResult(tuple(a), 0, "", ""),
        )

        with pytest.raises(DownloadError, match="qa-manifest"):
            download_run(
                database_id=42,
                run_id="1234567890-deadbeef",
                qa_runs_dir=tmp_path / "qa-runs",
            )

    def test_gh_failure_wrapped_as_download_error(self, tmp_path, monkeypatch):
        def fake_run_gh(*args, timeout, cwd, check=True):
            raise GhError("artifact missing")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        with pytest.raises(DownloadError, match="artifact missing"):
            download_run(
                database_id=42,
                run_id="1234567890-deadbeef",
                qa_runs_dir=tmp_path / "qa-runs",
            )
