from __future__ import annotations

import os
from pathlib import Path

import pytest

from squinch_qa.errors import ReplaceError
from squinch_qa.cleanup import CleanPolicy, clean_qa
from squinch_qa.replace.layout import (
    current_job_dir,
    incoming_job_dir,
    staging_job_dir,
    trash_dir,
)


def _run_id(ts: int, suffix: str) -> str:
    return f"{ts}-{suffix}"


def test_clean_runs_prunes_old_entries_beyond_keep(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    runs = qa_root / "runs"
    ids = [
        _run_id(1000, "aaaaaaaa"),
        _run_id(2000, "bbbbbbbb"),
        _run_id(3000, "cccccccc"),
    ]
    for run_id in ids:
        (runs / run_id).mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=0),
        states=("runs",),
        now_ms=4000,
    )

    assert [action.path.name for action in actions] == [ids[1], ids[0]]
    for action in actions:
        assert action.state == "runs"
        assert action.removed is True
        assert action.reason == "older_than_keep_runs:1"
    assert (runs / ids[2]).exists()
    assert not (runs / ids[1]).exists()
    assert not (runs / ids[0]).exists()


def test_clean_runs_survives_beyond_keep_but_not_old_enough(tmp_path: Path) -> None:
    """Runs beyond keep_runs must ALSO clear the age gate before pruning."""
    qa_root = tmp_path / "qa"
    runs = qa_root / "runs"
    ids = [
        _run_id(1000, "aaaaaaaa"),
        _run_id(2000, "bbbbbbbb"),
        _run_id(3000, "cccccccc"),
    ]
    for run_id in ids:
        (runs / run_id).mkdir(parents=True)

    # now_ms is only a few seconds past the oldest run, but max_run_age_days=1
    # means nothing clears the one-day age gate yet, even though two of the
    # three runs are already beyond keep_runs=1.
    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=1),
        states=("runs",),
        now_ms=4000,
    )

    assert actions == []
    assert (runs / ids[0]).exists()
    assert (runs / ids[1]).exists()
    assert (runs / ids[2]).exists()


def test_clean_runs_survives_within_keep_despite_being_old_enough(
    tmp_path: Path,
) -> None:
    """Runs within keep_runs must survive even once they clear the age gate."""
    qa_root = tmp_path / "qa"
    runs = qa_root / "runs"
    ids = [
        _run_id(1000, "aaaaaaaa"),
        _run_id(2000, "bbbbbbbb"),
        _run_id(3000, "cccccccc"),
    ]
    for run_id in ids:
        (runs / run_id).mkdir(parents=True)

    # now_ms is far beyond the one-day age gate for every run, so old_enough
    # is True across the board; only the run beyond keep_runs=2 gets pruned.
    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=2, max_run_age_days=1),
        states=("runs",),
        now_ms=200_000_000,
    )

    assert [action.path.name for action in actions] == [ids[0]]
    assert actions[0].removed is True
    assert actions[0].reason == "older_than_keep_runs:2"
    assert not (runs / ids[0]).exists()
    assert (runs / ids[1]).exists()
    assert (runs / ids[2]).exists()


def test_clean_runs_dry_run_reports_without_removing(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    old_run = qa_root / "runs" / _run_id(1000, "aaaaaaaa")
    new_run = qa_root / "runs" / _run_id(2000, "bbbbbbbb")
    old_run.mkdir(parents=True)
    new_run.mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=0),
        states=("runs",),
        dry_run=True,
        now_ms=3000,
    )

    assert len(actions) == 1
    assert actions[0].path == old_run.resolve()
    assert actions[0].removed is False
    assert old_run.exists()
    assert new_run.exists()


def test_clean_trash_prunes_per_mod_target_test(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    bucket = trash_dir(qa_root) / "redstone-backport" / "forge-1.20.1" / "pregen"
    entries = ["1000-run-a", "2000-run-b", "3000-run-c"]
    for entry in entries:
        (bucket / entry).mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_trash=2),
        states=("trash",),
    )

    assert [action.path.name for action in actions] == ["1000-run-a"]
    assert not (bucket / "1000-run-a").exists()
    assert (bucket / "2000-run-b").exists()
    assert (bucket / "3000-run-c").exists()


def test_clean_trash_uses_mtime_fallback_for_non_numeric_prefix(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    bucket = trash_dir(qa_root) / "redstone-backport" / "forge-1.20.1" / "pregen"
    numeric_entry = bucket / "5000-numeric-run"
    legacy_entry = bucket / "legacy-run"
    numeric_entry.mkdir(parents=True)
    legacy_entry.mkdir(parents=True)

    # Non-numeric prefix forces the mtime fallback; back-date it so it sorts
    # (and ages out) before the numeric-prefixed entry.
    old_mtime = 1.0  # 1970-01-01T00:00:01Z -> _trash_timestamp_ms == 1000
    os.utime(legacy_entry, (old_mtime, old_mtime))

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_trash=1),
        states=("trash",),
    )

    assert [action.path.name for action in actions] == ["legacy-run"]
    assert actions[0].removed is True
    assert not legacy_entry.exists()
    assert numeric_entry.exists()


def test_clean_trash_dry_run_reports_without_removing(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    bucket = trash_dir(qa_root) / "redstone-backport" / "forge-1.20.1" / "pregen"
    old_entry = bucket / "1000-run-a"
    new_entry = bucket / "2000-run-b"
    old_entry.mkdir(parents=True)
    new_entry.mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_trash=1),
        states=("trash",),
        dry_run=True,
    )

    assert len(actions) == 1
    assert actions[0].path == old_entry.resolve()
    assert actions[0].removed is False
    assert old_entry.exists()
    assert new_entry.exists()


def test_clean_never_touches_current(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    cur = current_job_dir(qa_root, "redstone-backport", "forge-1.20.1", "pregen")
    cur.mkdir(parents=True)
    (cur / "world").mkdir()
    (cur / "world" / "level.dat").write_bytes(b"keep")
    old_run = qa_root / "runs" / "1000-aaaaaaaa"
    new_run = qa_root / "runs" / "2000-bbbbbbbb"
    old_run.mkdir(parents=True)
    new_run.mkdir(parents=True)
    old_trash = (
        trash_dir(qa_root)
        / "redstone-backport"
        / "forge-1.20.1"
        / "pregen"
        / "1000-run-a"
    )
    old_trash.mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=0, keep_trash=0),
        states=("runs", "trash"),
        now_ms=3000,
    )

    assert {action.state for action in actions} == {"runs", "trash"}
    assert not old_run.exists()
    assert new_run.exists()
    assert not old_trash.exists()
    assert (cur / "world" / "level.dat").read_bytes() == b"keep"


def test_clean_never_touches_incoming_or_staging(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    incoming = incoming_job_dir(qa_root, "redstone-backport", "forge-1.20.1", "pregen")
    staging = staging_job_dir(qa_root, "redstone-backport", "forge-1.20.1", "pregen")
    incoming.mkdir(parents=True)
    staging.mkdir(parents=True)
    (incoming / "world").mkdir()
    (incoming / "world" / "level.dat").write_bytes(b"incoming-data")
    (staging / "world").mkdir()
    (staging / "world" / "level.dat").write_bytes(b"staging-data")
    old_run = qa_root / "runs" / "1000-aaaaaaaa"
    new_run = qa_root / "runs" / "2000-bbbbbbbb"
    old_run.mkdir(parents=True)
    new_run.mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=0, keep_trash=0),
        states=("runs", "trash"),
        now_ms=3000,
    )

    assert [action.path.name for action in actions] == ["1000-aaaaaaaa"]
    assert not old_run.exists()
    assert new_run.exists()
    assert (incoming / "world" / "level.dat").read_bytes() == b"incoming-data"
    assert (staging / "world" / "level.dat").read_bytes() == b"staging-data"


def test_clean_runs_ignores_invalid_run_ids(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    invalid = qa_root / "runs" / "not-a-run-id"
    old_valid = qa_root / "runs" / "1000-aaaaaaaa"
    new_valid = qa_root / "runs" / "2000-bbbbbbbb"
    invalid.mkdir(parents=True)
    old_valid.mkdir(parents=True)
    new_valid.mkdir(parents=True)

    actions = clean_qa(
        qa_root,
        policy=CleanPolicy(keep_runs=1, max_run_age_days=0),
        states=("runs",),
        now_ms=3000,
    )

    assert [action.path.name for action in actions] == ["1000-aaaaaaaa"]
    assert invalid.exists()
    assert not old_valid.exists()
    assert new_valid.exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"keep_runs": -1},
        {"max_run_age_days": -1},
        {"keep_trash": -1},
    ],
)
def test_clean_policy_rejects_negative_values(kwargs: dict) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        CleanPolicy(**kwargs)


def test_clean_runs_rejects_symlink_escape(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    outside = tmp_path / "outside-run"
    outside.mkdir()
    runs = qa_root / "runs"
    runs.mkdir(parents=True)
    (runs / "1000-aaaaaaaa").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ReplaceError, match="outside"):
        clean_qa(
            qa_root,
            policy=CleanPolicy(keep_runs=0, max_run_age_days=0),
            states=("runs",),
            now_ms=2000,
        )


def test_clean_trash_rejects_symlink_escape(tmp_path: Path) -> None:
    qa_root = tmp_path / "qa"
    outside = tmp_path / "outside-trash"
    outside.mkdir()
    bucket = trash_dir(qa_root) / "m" / "t" / "x"
    bucket.mkdir(parents=True)
    (bucket / "1000-run-a").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ReplaceError, match="outside"):
        clean_qa(
            qa_root,
            policy=CleanPolicy(keep_trash=0),
            states=("trash",),
        )
