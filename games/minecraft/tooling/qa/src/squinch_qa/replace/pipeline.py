from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from squinch_qa.errors import ReplaceError, ValidationError
from squinch_qa.replace.layout import (
    INCOMING_READY,
    STAGING_READY,
    assert_same_device,
    current_dir,
    current_job_dir,
    identity_dir,
    incoming_dir,
    incoming_job_dir,
    staging_dir,
    staging_job_dir,
    trash_dir,
    trash_job_dir,
)
from squinch_qa.replace.validate import ValidatedJob, _load_json, validate

_BENIGN_SKIP_REASON_PREFIXES = ("no_world_artifact", "status_not_promotable")


@dataclass
class PromotionResult:
    target_id: str
    test_id: str
    promoted: bool
    reason: str | None = None
    mod_id: str | None = None

    @property
    def is_failure(self) -> bool:
        """True if this job was expected to be promotable but wasn't, for a
        reason beyond "nothing eligible here" (missing world artifact, or a
        status that was never going to qualify)."""
        if self.promoted:
            return False
        return not (self.reason or "").startswith(_BENIGN_SKIP_REASON_PREFIXES)


def _snapshot_local(world_src: Path, inc: Path) -> None:
    """Copy world_src into a fresh incoming world, sentinel written last."""
    if inc.exists():
        shutil.rmtree(inc)
    inc.mkdir(parents=True)
    shutil.copytree(world_src, inc / "world")
    (inc / INCOMING_READY).touch()


def _extract(inc: Path, stg: Path) -> None:
    """Move a ready incoming entry into staging, sentinel written last.

    Named to match a future remote bundle's unpack step (Phase 9); for a local
    run the data is already a plain directory, so this is just a move.
    """
    if not (inc / INCOMING_READY).is_file():
        raise ReplaceError(
            reason="incoming_not_ready",
            message=f"{inc} has no {INCOMING_READY} sentinel",
        )
    (inc / INCOMING_READY).unlink()
    if stg.exists():
        shutil.rmtree(stg)
    stg.parent.mkdir(parents=True, exist_ok=True)
    os.replace(inc, stg)
    (stg / STAGING_READY).touch()


def _swap(stg: Path, cur: Path, trash_dest: Path) -> None:
    """Atomically move staging into current, evicting any old current to trash first.

    If the process dies between the two os.replace calls, cur is already gone
    and stg still carries STAGING_READY — recover_pending completes the move
    on the next invocation.
    """
    if not (stg / STAGING_READY).is_file():
        raise ReplaceError(
            reason="staging_not_ready", message=f"{stg} has no {STAGING_READY} sentinel"
        )
    if cur.exists():
        trash_dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(cur, trash_dest)
    cur.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stg, cur)


def recover_pending(qa_root: Path) -> None:
    """Idempotent crash recovery.

    Deletes any incoming/staging entry that never reached its sentinel (a
    crash mid-write — safe to discard, nothing downstream has seen it), and
    rolls forward any staging entry that IS sentinel-complete but never made
    it into current (a crash between extract and swap).
    """
    inc_root = incoming_dir(qa_root)
    for mod_id, target_id, test_id, entry in _iter_identity_dirs(inc_root):
        if entry.is_dir() and not (entry / INCOMING_READY).is_file():
            shutil.rmtree(entry)

    stg_root = staging_dir(qa_root)
    for mod_id, target_id, test_id, entry in _iter_identity_dirs(stg_root):
        if not entry.is_dir():
            continue
        if not (entry / STAGING_READY).is_file():
            shutil.rmtree(entry)
            continue
        cur = identity_dir(current_dir(qa_root), mod_id, target_id, test_id)
        trash_dest = (
            identity_dir(trash_dir(qa_root), mod_id, target_id, test_id)
            / f"{int(time.time() * 1000)}-recovered"
        )
        _swap(entry, cur, trash_dest)


def _iter_identity_dirs(root: Path):
    if not root.is_dir():
        return
    for mod_dir in list(root.iterdir()):
        if not mod_dir.is_dir():
            continue
        for target_dir in list(mod_dir.iterdir()):
            if not target_dir.is_dir():
                continue
            for test_dir in list(target_dir.iterdir()):
                if test_dir.is_dir():
                    yield mod_dir.name, target_dir.name, test_dir.name, test_dir


def _promote_validated(
    qa_root: Path, run_dir: Path, validated: ValidatedJob, *, dry_run: bool = False
) -> PromotionResult:
    target_id, test_id = validated.target_id, validated.test_id

    if validated.world_dir is None:
        return PromotionResult(
            target_id,
            test_id,
            promoted=False,
            reason="no_world_artifact",
            mod_id=validated.mod_id,
        )

    if dry_run:
        return PromotionResult(
            target_id, test_id, promoted=True, reason="dry_run", mod_id=validated.mod_id
        )

    run_id = run_dir.name

    try:
        inc = incoming_job_dir(qa_root, validated.mod_id, target_id, test_id)
        stg = staging_job_dir(qa_root, validated.mod_id, target_id, test_id)
        cur = current_job_dir(qa_root, validated.mod_id, target_id, test_id)
        trash_dest = trash_job_dir(
            qa_root, validated.mod_id, target_id, test_id, run_id
        )

        assert_same_device(
            incoming_dir(qa_root),
            staging_dir(qa_root),
            current_dir(qa_root),
            trash_dir(qa_root),
        )
        _snapshot_local(validated.world_dir, inc)
        _extract(inc, stg)
        _swap(stg, cur, trash_dest)
    except (ReplaceError, OSError) as e:
        return PromotionResult(
            target_id,
            test_id,
            promoted=False,
            reason=f"promote_failed: {e}",
            mod_id=validated.mod_id,
        )

    return PromotionResult(target_id, test_id, promoted=True, mod_id=validated.mod_id)


def promote_job(
    qa_root: Path, run_dir: Path, target_id: str, test_id: str, *, dry_run: bool = False
) -> PromotionResult:
    """Validate a single completed job and, if it qualifies, atomically promote its world.

    Callers should run recover_pending(qa_root) once before promoting a batch
    of jobs, not once per job here — this function assumes that's already
    been done.
    """
    try:
        validated = validate(run_dir, target_id, test_id)
    except ValidationError as e:
        return PromotionResult(
            target_id, test_id, promoted=False, reason=f"{e.reason}: {e}"
        )
    return _promote_validated(qa_root, run_dir, validated, dry_run=dry_run)


def promote_run(
    qa_root: Path,
    run_dir: Path,
    *,
    target_filter: str | None = None,
    test_filter: str | None = None,
    dry_run: bool = False,
) -> list[PromotionResult]:
    """Promote every (target, test) job listed in run_dir's manifest, optionally filtered.

    All-or-nothing: every selected job is validated first (read-only, no
    filesystem changes) before any of them is actually promoted. If any
    selected job has a real validation failure — as opposed to a benign skip
    like "no world artifact" or "status not promotable" — nothing in the
    batch is promoted, so a partially-broken remote matrix run can never
    leave `current/` in a mix of old and new worlds.

    Does not call recover_pending itself — callers own that (see promote_job).
    """
    run_manifest = _load_json(
        run_dir / "qa-manifest.json", reason="missing_run_manifest", what="run manifest"
    )

    selected = [
        (job_ref["target"], job_ref["test"])
        for job_ref in run_manifest.get("jobs", [])
        if (target_filter is None or job_ref["target"] == target_filter)
        and (test_filter is None or job_ref["test"] == test_filter)
    ]

    prechecked: list[tuple[str, str, ValidatedJob | PromotionResult]] = []
    for target_id, test_id in selected:
        try:
            prechecked.append(
                (target_id, test_id, validate(run_dir, target_id, test_id))
            )
        except ValidationError as e:
            prechecked.append(
                (
                    target_id,
                    test_id,
                    PromotionResult(
                        target_id, test_id, promoted=False, reason=f"{e.reason}: {e}"
                    ),
                )
            )

    batch_blocked = any(
        isinstance(item, PromotionResult) and item.is_failure
        for _, _, item in prechecked
    )

    results = []
    for target_id, test_id, item in prechecked:
        if isinstance(item, PromotionResult):
            results.append(item)  # validate() raised; failure reason already set
        elif item.world_dir is None:
            results.append(
                PromotionResult(
                    target_id,
                    test_id,
                    promoted=False,
                    reason="no_world_artifact",
                    mod_id=item.mod_id,
                )
            )
        elif batch_blocked:
            results.append(
                PromotionResult(
                    target_id,
                    test_id,
                    promoted=False,
                    reason="blocked_by_batch_failure",
                    mod_id=item.mod_id,
                )
            )
        else:
            results.append(_promote_validated(qa_root, run_dir, item, dry_run=dry_run))
    return results
