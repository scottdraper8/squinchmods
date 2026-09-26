from __future__ import annotations

import stat
from pathlib import Path

import pytest

from squinch_qa.remote._gh import run_gh
from squinch_qa.remote.errors import GhError


def _write_fake_gh(bin_dir: Path, body: str) -> None:
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\n" + body)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)


class TestRunGhBoundary:
    def test_runs_gh_from_path_and_captures_output(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _write_fake_gh(
            bin_dir,
            'printf "args:%s %s\\n" "$1" "$2"\nprintf "warn\\n" >&2\nexit 0\n',
        )
        monkeypatch.setenv("PATH", str(bin_dir))

        result = run_gh("run", "list", cwd=tmp_path)

        assert result.args == ("run", "list")
        assert result.returncode == 0
        assert result.stdout == "args:run list\n"
        assert result.stderr == "warn\n"

    def test_nonzero_exit_raises_by_default(self, tmp_path: Path, monkeypatch) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _write_fake_gh(bin_dir, 'printf "bad auth\\n" >&2\nexit 7\n')
        monkeypatch.setenv("PATH", str(bin_dir))

        with pytest.raises(GhError, match="exit 7: bad auth"):
            run_gh("auth", "status", cwd=tmp_path)

    def test_check_false_returns_nonzero_result(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _write_fake_gh(bin_dir, 'printf "missing\\n" >&2\nexit 4\n')
        monkeypatch.setenv("PATH", str(bin_dir))

        result = run_gh("run", "view", "42", cwd=tmp_path, check=False)

        assert result.returncode == 4
        assert result.stderr == "missing\n"
