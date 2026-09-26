from __future__ import annotations

from pathlib import Path

import pytest

from squinch_qa import cli
from squinch_qa.artifacts import default_qa_root
from squinch_qa.replace.layout import trash_dir


class TestCleanCli:
    def test_dry_run_reports_without_removing(self, tmp_path: Path, capsys) -> None:
        qa_root = default_qa_root(tmp_path)
        old_run = qa_root / "runs" / "1000-aaaaaaaa"
        new_run = qa_root / "runs" / "2000-bbbbbbbb"
        old_run.mkdir(parents=True)
        new_run.mkdir(parents=True)

        code = cli.main(
            [
                "clean",
                "--repo-root",
                str(tmp_path),
                "--runs",
                "--keep-runs",
                "1",
                "--max-run-age-days",
                "0",
                "--dry-run",
            ]
        )

        assert code == 0
        assert old_run.exists()
        assert new_run.exists()
        out = capsys.readouterr().out
        assert '"type": "clean_item"' in out
        assert '"removed": false' in out

    def test_real_clean_removes_old_run(self, tmp_path: Path) -> None:
        qa_root = default_qa_root(tmp_path)
        old_run = qa_root / "runs" / "1000-aaaaaaaa"
        new_run = qa_root / "runs" / "2000-bbbbbbbb"
        old_run.mkdir(parents=True)
        new_run.mkdir(parents=True)

        code = cli.main(
            [
                "clean",
                "--repo-root",
                str(tmp_path),
                "--runs",
                "--keep-runs",
                "1",
                "--max-run-age-days",
                "0",
            ]
        )

        assert code == 0
        assert not old_run.exists()
        assert new_run.exists()

    def test_repo_root_from_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With --repo-root omitted, the SQUINCHMODS_ROOT env var is used instead."""
        monkeypatch.setenv("SQUINCHMODS_ROOT", str(tmp_path))
        qa_root = default_qa_root(tmp_path)
        old_run = qa_root / "runs" / "1000-aaaaaaaa"
        old_run.mkdir(parents=True)

        code = cli.main(
            ["clean", "--runs", "--keep-runs", "0", "--max-run-age-days", "0"]
        )

        assert code == 0
        assert not old_run.exists()

    def test_negative_keep_runs_rejected(self, tmp_path: Path) -> None:
        """The --keep-runs/--max-run-age-days/--keep-trash validator rejects negatives."""
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["clean", "--repo-root", str(tmp_path), "--keep-runs", "-1"])
        assert exc_info.value.code == 2

    def test_default_prunes_both_runs_and_trash(self, tmp_path: Path) -> None:
        """Omitting both --runs and --trash prunes both states (the default)."""
        qa_root = default_qa_root(tmp_path)
        old_run = qa_root / "runs" / "1000-aaaaaaaa"
        new_run = qa_root / "runs" / "2000-bbbbbbbb"
        old_run.mkdir(parents=True)
        new_run.mkdir(parents=True)

        bucket = trash_dir(qa_root) / "some-mod" / "some-target" / "some-test"
        old_trash = bucket / "1000-run-a"
        new_trash = bucket / "2000-run-b"
        old_trash.mkdir(parents=True)
        new_trash.mkdir(parents=True)

        code = cli.main(
            [
                "clean",
                "--repo-root",
                str(tmp_path),
                "--keep-runs",
                "1",
                "--max-run-age-days",
                "0",
                "--keep-trash",
                "1",
            ]
        )

        assert code == 0
        assert not old_run.exists()
        assert new_run.exists()
        assert not old_trash.exists()
        assert new_trash.exists()
