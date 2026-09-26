from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from squinch_qa.artifacts import RUN_ID_RE
from squinch_qa.replace._pathsafe import assert_within
from squinch_qa.replace.layout import trash_dir


@dataclass(frozen=True)
class CleanPolicy:
    keep_runs: int = 20
    max_run_age_days: int | None = 30
    keep_trash: int = 2

    def __post_init__(self) -> None:
        if self.keep_runs < 0:
            raise ValueError("keep_runs must be >= 0")
        if self.max_run_age_days is not None and self.max_run_age_days < 0:
            raise ValueError("max_run_age_days must be >= 0")
        if self.keep_trash < 0:
            raise ValueError("keep_trash must be >= 0")


@dataclass(frozen=True)
class CleanAction:
    state: str
    path: Path
    reason: str
    removed: bool


def _run_timestamp_ms(run_id: str) -> int | None:
    if RUN_ID_RE.fullmatch(run_id) is None:
        return None
    try:
        return int(run_id.split("-", 1)[0])
    except ValueError:
        return None


def _remove_dir(path: Path, *, dry_run: bool) -> bool:
    if dry_run:
        return False
    shutil.rmtree(path)
    return True


def _clean_runs(
    qa_root: Path, policy: CleanPolicy, *, dry_run: bool, now_ms: int
) -> list[CleanAction]:
    runs_root = qa_root / "runs"
    if not runs_root.is_dir():
        return []

    runs: list[tuple[int, Path]] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        ts = _run_timestamp_ms(entry.name)
        if ts is None:
            continue
        runs.append((ts, assert_within(runs_root, entry)))

    runs.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    max_age_ms = (
        policy.max_run_age_days * 24 * 60 * 60 * 1000
        if policy.max_run_age_days is not None
        else None
    )

    actions: list[CleanAction] = []
    for index, (ts, path) in enumerate(runs):
        beyond_keep = index >= policy.keep_runs
        old_enough = max_age_ms is None or now_ms - ts >= max_age_ms
        if not beyond_keep or not old_enough:
            continue
        removed = _remove_dir(path, dry_run=dry_run)
        actions.append(
            CleanAction(
                state="runs",
                path=path,
                reason=f"older_than_keep_runs:{policy.keep_runs}",
                removed=removed,
            )
        )
    return actions


def _trash_timestamp_ms(path: Path) -> int:
    prefix = path.name.split("-", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return int(path.stat().st_mtime * 1000)


def _clean_trash(
    qa_root: Path, policy: CleanPolicy, *, dry_run: bool
) -> list[CleanAction]:
    root = trash_dir(qa_root)
    if not root.is_dir():
        return []

    actions: list[CleanAction] = []
    for mod_dir in root.iterdir():
        if not mod_dir.is_dir():
            continue
        for target_dir in mod_dir.iterdir():
            if not target_dir.is_dir():
                continue
            for test_dir in target_dir.iterdir():
                if not test_dir.is_dir():
                    continue
                entries = [
                    assert_within(test_dir, entry)
                    for entry in test_dir.iterdir()
                    if entry.is_dir()
                ]
                entries.sort(
                    key=lambda entry: (_trash_timestamp_ms(entry), entry.name),
                    reverse=True,
                )
                for entry in entries[policy.keep_trash :]:
                    removed = _remove_dir(entry, dry_run=dry_run)
                    actions.append(
                        CleanAction(
                            state="trash",
                            path=entry,
                            reason=f"older_than_keep_trash:{policy.keep_trash}",
                            removed=removed,
                        )
                    )
    return actions


def clean_qa(
    qa_root: Path,
    *,
    policy: CleanPolicy | None = None,
    states: tuple[str, ...] = ("runs", "trash"),
    dry_run: bool = False,
    now_ms: int | None = None,
) -> list[CleanAction]:
    policy = policy or CleanPolicy()
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)

    actions: list[CleanAction] = []
    selected = set(states)
    if "runs" in selected:
        actions.extend(_clean_runs(qa_root, policy, dry_run=dry_run, now_ms=now_ms))
    if "trash" in selected:
        actions.extend(_clean_trash(qa_root, policy, dry_run=dry_run))
    return actions
