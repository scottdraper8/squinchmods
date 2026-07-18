from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from squinch_qa.remote import _gh
from squinch_qa.remote.dispatch import _current_ref, dispatch_run
from squinch_qa.remote.errors import DispatchError, GhError


def _init_git_repo_with_commit(repo: Path) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "qa@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QA Bot"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("test\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


class TestRemoteDispatch:
    def test_dispatches_workflow_with_required_inputs(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        calls = []

        def fake_run_gh(*args, timeout, cwd, check=True):
            calls.append((args, timeout, cwd, check))
            return _gh.GhResult(tuple(args), 0, "", "")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        dispatch_run(
            mod="redstone-backport",
            run_id="1234567890-deadbeef",
            repo_root=tmp_path,
            ref="feature/remote-qa",
        )

        args, timeout, cwd, check = calls[0]
        assert args == (
            "workflow",
            "run",
            "qa-remote.yml",
            "-f",
            "run_id=1234567890-deadbeef",
            "-f",
            "mod=redstone-backport",
            "--ref",
            "feature/remote-qa",
        )
        assert timeout == 30.0
        assert cwd == tmp_path
        assert check is True

    def test_dispatches_optional_target_and_profile(
        self, tmp_path, monkeypatch
    ) -> None:
        calls = []

        def fake_run_gh(*args, timeout, cwd, check=True):
            calls.append(args)
            return _gh.GhResult(tuple(args), 0, "", "")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        dispatch_run(
            mod="reterraforged",
            run_id="1234567890-deadbeef",
            target="neoforge-1.21.1",
            profile="pre-pr",
            repo_root=tmp_path,
            ref="main",
        )

        args = calls[0]
        assert "target=neoforge-1.21.1" in args
        assert "profile=pre-pr" in args
        assert "--ref" in args
        assert "main" in args

    def test_invalid_run_id_rejected_before_gh(self, monkeypatch) -> None:
        monkeypatch.setattr(
            _gh,
            "run_gh",
            lambda *a, **k: pytest.fail("gh should not be called"),
        )

        with pytest.raises(DispatchError):
            dispatch_run(mod="m", run_id="../evil")

    def test_gh_failure_wrapped_as_dispatch_error(self, monkeypatch) -> None:
        def fake_run_gh(*args, timeout, cwd, check=True):
            raise GhError("no auth")

        monkeypatch.setattr(_gh, "run_gh", fake_run_gh)

        with pytest.raises(DispatchError, match="no auth"):
            dispatch_run(mod="m", run_id="1234567890-deadbeef")


class TestCurrentRef:
    def test_symbolic_ref_succeeds_on_named_branch(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo_with_commit(repo)

        assert _current_ref(repo) == "main"

    def test_falls_back_to_rev_parse_when_head_is_detached(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo_with_commit(repo)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # symbolic-ref fails on a detached HEAD ("not a symbolic ref"), so
        # _current_ref must fall back to the resolved commit sha.
        subprocess.run(
            ["git", "checkout", "-q", "--detach", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        assert _current_ref(repo) == sha

    def test_raises_dispatch_error_when_neither_git_command_resolves(
        self, tmp_path: Path
    ) -> None:
        # A plain directory with no .git anywhere above it: both
        # `symbolic-ref` and `rev-parse` fail, so _current_ref must raise.
        not_a_repo = tmp_path / "not-a-repo"
        not_a_repo.mkdir()

        with pytest.raises(DispatchError, match="could not determine git ref"):
            _current_ref(not_a_repo)
