from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.source import snapshot_source


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "investigation@example.invalid")
    _git(repository, "config", "user.name", "Investigation Test")
    (repository / "README.md").write_text("target symbol\n", encoding="utf-8")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "-qm", "fixture")
    return repository


def test_source_snapshot_records_clean_identity_files_and_matches(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    result = snapshot_source(
        repository,
        ["README.md"],
        tmp_path / "snapshot",
        patterns=["target", "symbol"],
    )
    assert result["revision"] == _git(repository, "rev-parse", "HEAD")
    assert not result["dirty"]
    assert result["all_patterns_matched"]
    assert result["pattern_counts"] == {"symbol": 1, "target": 1}
    assert result["files"][0]["logical_path"] == "README.md"
    assert Path(result["files"][0]["snapshot_path"]).read_text() == "target symbol\n"
    assert result["upstream"] is None
    assert result["upstream_revision"] is None
    assert result["ahead_behind"] is None


def test_source_snapshot_records_local_upstream_identity(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    remote = tmp_path / "remote.git"
    _git(remote.parent, "init", "--bare", "-q", str(remote))
    _git(repository, "remote", "add", "origin", str(remote))
    branch = _git(repository, "branch", "--show-current")
    _git(repository, "push", "-qu", "origin", branch)

    result = snapshot_source(repository, ["README.md"], tmp_path / "snapshot")

    assert result["upstream"] == f"origin/{branch}"
    assert result["upstream_revision"] == result["revision"]
    assert result["ahead_behind"] == {"ahead": 0, "behind": 0}


def test_source_snapshot_rejects_dirty_tree_by_default(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "README.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(InvestigationError, match="working-tree changes") as caught:
        snapshot_source(repository, ["README.md"], tmp_path / "snapshot")
    assert caught.value.code == "dirty_source_repository"


def test_source_snapshot_rejects_escape_and_untracked_file(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    with pytest.raises(InvestigationError) as escaped:
        snapshot_source(repository, ["../outside"], tmp_path / "escaped")
    assert escaped.value.code == "invalid_source_path"

    (repository / "untracked.py").write_text("pass\n", encoding="utf-8")
    with pytest.raises(InvestigationError) as untracked:
        snapshot_source(
            repository,
            ["untracked.py"],
            tmp_path / "untracked-snapshot",
            allow_dirty=True,
        )
    assert untracked.value.code == "git_failed"
