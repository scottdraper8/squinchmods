from __future__ import annotations

from pathlib import Path

import pytest

from squinch_qa.executors.base import JobResult
from squinch_qa.manifest import emit_all
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    Target,
    TestSpec,
)
from squinch_qa.replace.layout import (
    INCOMING_READY,
    STAGING_READY,
    current_job_dir,
    incoming_dir,
    incoming_job_dir,
    staging_dir,
    staging_job_dir,
    trash_dir,
)
from squinch_qa.replace.pipeline import (
    PromotionResult,
    promote_job,
    promote_run,
    recover_pending,
)


def _world_src(tmp_path: Path, marker: bytes = b"chunk data") -> Path:
    src = tmp_path / "world-src"
    (src / "region").mkdir(parents=True)
    (src / "region" / "r.0.0.mca").write_bytes(marker)
    return src


def _manifest_run_dir(tmp_path: Path, marker: bytes = b"manifest world") -> Path:
    run_dir = tmp_path / "runs" / "1234567890-deadbeef"
    target = Target(
        id="forge-1.20.1",
        minecraft="1.20.1",
        loader="forge",
        loader_version="47.0.0",
        java=17,
        supported=True,
        capabilities=["server"],
    )
    test = TestSpec(
        id="pregen",
        required=True,
        requires=[],
        adapters={},
        expectations={},
        config={},
        origin_index=0,
    )
    job = PlannedJob(
        target=target,
        test_spec=test,
        adapter=None,
        expected_failure=None,
        expectations={},
    )
    plan = ExecutionPlan(
        mod_id="redstone-backport",
        display_name="Redstone Backport",
        profile=ResolvedProfile(
            name="default",
            resolved_from=["default"],
            tests=[test],
            max_parallel=1,
            max_jobs=1,
        ),
        jobs=[job],
        skipped=[],
        skipped_targets=[],
    )
    world = run_dir / "jobs" / target.id / test.id / "world"
    (world / "region").mkdir(parents=True)
    (world / "region" / "r.0.0.mca").write_bytes(marker)
    emit_all(
        run_dir,
        plan,
        {
            (target.id, test.id): JobResult(
                status="pass",
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:01+00:00",
                duration_s=1.0,
                logs=[],
                artifacts=["world"],
                failure=None,
            )
        },
        repo_root=tmp_path,
        mod_dir=tmp_path,
        run_id=run_dir.name,
        plan_bytes=b'{"schema":1}',
    )
    return run_dir


class TestPromoteJobHappyPath:
    def test_first_promotion_populates_current(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        world_src = _world_src(tmp_path)
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": world_src,
                }
            ]
        )

        recover_pending(qa_root)
        result = promote_job(qa_root, run_dir, "t", "pregen")

        assert result.promoted is True
        cur = current_job_dir(qa_root, "fake-mod", "t", "pregen")
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"chunk data"
        # no leftover incoming/staging entries after a clean promotion
        assert not incoming_job_dir(qa_root, "fake-mod", "t", "pregen").exists()
        assert not staging_job_dir(qa_root, "fake-mod", "t", "pregen").exists()

    def test_second_promotion_replaces_current_and_trashes_old(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run1 = qa_run_factory(
            run_id="run-1",
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "s1", b"v1"),
                }
            ],
        )
        recover_pending(qa_root)
        promote_job(qa_root, run1, "t", "pregen")

        run2 = qa_run_factory(
            run_id="run-2",
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "s2", b"v2"),
                }
            ],
        )
        recover_pending(qa_root)
        result = promote_job(qa_root, run2, "t", "pregen")

        assert result.promoted is True
        cur = current_job_dir(qa_root, "fake-mod", "t", "pregen")
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"v2"
        # old current was evicted to trash, not deleted outright
        trashed = list((trash_dir(qa_root) / "fake-mod" / "t" / "pregen").iterdir())
        assert len(trashed) == 1
        assert (trashed[0] / "world" / "region" / "r.0.0.mca").read_bytes() == b"v1"

    def test_validation_failure_does_not_touch_current(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[{"target_id": "t", "test_id": "pregen", "status": "fail"}]
        )

        recover_pending(qa_root)
        result = promote_job(qa_root, run_dir, "t", "pregen")

        assert result.promoted is False
        assert result.reason.startswith("status_not_promotable")
        assert not current_job_dir(qa_root, "fake-mod", "t", "pregen").exists()

    def test_no_world_artifact_skipped(self, tmp_path: Path, qa_run_factory) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[{"target_id": "t", "test_id": "build", "status": "pass"}]
        )

        recover_pending(qa_root)
        result = promote_job(qa_root, run_dir, "t", "build")

        assert result.promoted is False
        assert result.reason == "no_world_artifact"

    def test_dry_run_does_not_write(self, tmp_path: Path, qa_run_factory) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ]
        )

        result = promote_job(qa_root, run_dir, "t", "pregen", dry_run=True)

        assert result.promoted is True
        assert result.reason == "dry_run"
        assert not current_job_dir(qa_root, "fake-mod", "t", "pregen").exists()


class TestPromoteRun:
    def test_promotes_all_world_jobs_and_reports_skips(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w1"),
                },
                {
                    "target_id": "t2",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w2"),
                },
                {"target_id": "t1", "test_id": "build", "status": "pass"},
            ]
        )
        recover_pending(qa_root)
        results = promote_run(qa_root, run_dir)

        by_key = {(r.target_id, r.test_id): r for r in results}
        assert by_key[("t1", "pregen")].promoted is True
        assert by_key[("t2", "pregen")].promoted is True
        assert by_key[("t1", "build")].promoted is False

    def test_batch_is_all_or_nothing_on_real_failure(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w1"),
                },
                {
                    "target_id": "t2",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w2"),
                    "world_sha256_override": "0"
                    * 64,  # forces a real hash-mismatch failure
                },
            ]
        )
        recover_pending(qa_root)
        results = promote_run(qa_root, run_dir)

        by_key = {(r.target_id, r.test_id): r for r in results}
        # Neither job actually promoted, even though t1's world was valid on
        # its own — one real failure anywhere in the batch blocks all of it.
        assert by_key[("t1", "pregen")].promoted is False
        assert by_key[("t1", "pregen")].reason == "blocked_by_batch_failure"
        assert by_key[("t2", "pregen")].promoted is False
        assert by_key[("t2", "pregen")].is_failure is True
        assert not current_job_dir(qa_root, "fake-mod", "t1", "pregen").exists()
        assert not current_job_dir(qa_root, "fake-mod", "t2", "pregen").exists()

    def test_benign_skips_do_not_block_the_batch(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w1"),
                },
                {"target_id": "t1", "test_id": "build", "status": "pass"},
            ]
        )
        recover_pending(qa_root)
        results = promote_run(qa_root, run_dir)

        by_key = {(r.target_id, r.test_id): r for r in results}
        assert by_key[("t1", "pregen")].promoted is True
        assert by_key[("t1", "build")].promoted is False
        assert by_key[("t1", "build")].reason == "no_world_artifact"
        assert current_job_dir(qa_root, "fake-mod", "t1", "pregen").exists()

    def test_target_filter(self, tmp_path: Path, qa_run_factory) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w1"),
                },
                {
                    "target_id": "t2",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w2"),
                },
            ]
        )
        recover_pending(qa_root)
        results = promote_run(qa_root, run_dir, target_filter="t1")

        assert len(results) == 1
        assert results[0].target_id == "t1"

    def test_mods_with_same_target_and_test_do_not_collide(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        redstone_run = qa_run_factory(
            run_id="run-1",
            mod_id="redstone-backport",
            jobs=[
                {
                    "target_id": "forge-1.20.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "redstone", b"redstone"),
                }
            ],
        )
        rtf_run = qa_run_factory(
            run_id="run-2",
            mod_id="reterraforged",
            jobs=[
                {
                    "target_id": "forge-1.20.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "rtf", b"rtf"),
                }
            ],
        )

        recover_pending(qa_root)
        redstone_result = promote_run(qa_root, redstone_run)
        rtf_result = promote_run(qa_root, rtf_run)

        assert redstone_result[0].promoted is True
        assert rtf_result[0].promoted is True
        redstone_cur = current_job_dir(
            qa_root, "redstone-backport", "forge-1.20.1", "pregen"
        )
        rtf_cur = current_job_dir(qa_root, "reterraforged", "forge-1.20.1", "pregen")
        assert (
            redstone_cur / "world" / "region" / "r.0.0.mca"
        ).read_bytes() == b"redstone"
        assert (rtf_cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"rtf"

    def test_promotes_run_emitted_by_real_manifest_writer(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = _manifest_run_dir(tmp_path)

        results = promote_run(qa_root, run_dir)

        assert results[0].promoted is True
        cur = current_job_dir(qa_root, "redstone-backport", "forge-1.20.1", "pregen")
        assert (
            cur / "world" / "region" / "r.0.0.mca"
        ).read_bytes() == b"manifest world"


class TestRecoverPending:
    def test_orphan_incoming_without_sentinel_is_deleted(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        inc = incoming_job_dir(qa_root, "fake-mod", "t", "x")
        inc.mkdir(parents=True)
        (inc / "world").mkdir()
        (inc / "world" / "partial.dat").write_bytes(b"incomplete")
        # no INCOMING_READY sentinel written

        recover_pending(qa_root)

        assert not inc.exists()

    def test_incoming_with_sentinel_is_left_alone(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        inc = incoming_job_dir(qa_root, "fake-mod", "t", "x")
        inc.mkdir(parents=True)
        (inc / INCOMING_READY).touch()

        recover_pending(qa_root)

        assert inc.exists()
        assert (inc / INCOMING_READY).exists()

    def test_orphan_staging_without_sentinel_is_deleted(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        stg = staging_job_dir(qa_root, "fake-mod", "t", "x")
        stg.mkdir(parents=True)
        (stg / "world").mkdir()
        # no STAGING_READY sentinel

        recover_pending(qa_root)

        assert not stg.exists()

    def test_staging_with_sentinel_rolls_forward_to_current(
        self, tmp_path: Path
    ) -> None:
        qa_root = tmp_path / "repo"
        stg = staging_job_dir(qa_root, "fake-mod", "t", "x")
        stg.mkdir(parents=True)
        (stg / "world").mkdir()
        (stg / "world" / "level.dat").write_bytes(b"staged data")
        (stg / STAGING_READY).touch()

        recover_pending(qa_root)

        cur = current_job_dir(qa_root, "fake-mod", "t", "x")
        assert not stg.exists()
        assert (cur / "world" / "level.dat").read_bytes() == b"staged data"

    def test_staging_rollforward_evicts_existing_current(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        cur = current_job_dir(qa_root, "fake-mod", "t", "x")
        cur.mkdir(parents=True)
        (cur / "old.dat").write_bytes(b"old current")

        stg = staging_job_dir(qa_root, "fake-mod", "t", "x")
        stg.mkdir(parents=True)
        (stg / "new.dat").write_bytes(b"new staged")
        (stg / STAGING_READY).touch()

        recover_pending(qa_root)

        assert (cur / "new.dat").read_bytes() == b"new staged"
        trashed = list((trash_dir(qa_root) / "fake-mod" / "t" / "x").iterdir())
        assert len(trashed) == 1
        assert (trashed[0] / "old.dat").read_bytes() == b"old current"

    def test_recovers_multiple_concurrent_pending_identities(
        self, tmp_path: Path
    ) -> None:
        qa_root = tmp_path / "repo"

        # Three distinct (mod, target, test) identities left pending by a
        # crashed batch, each in a different terminal state, spread across
        # different mod/target/test dirs to catch cross-contamination in the
        # triple-nested iterdir walk.
        orphan_incoming = incoming_job_dir(qa_root, "mod-a", "target-a", "pregen")
        orphan_incoming.mkdir(parents=True)
        (orphan_incoming / "world").mkdir()
        (orphan_incoming / "world" / "partial.dat").write_bytes(b"incomplete-a")
        # no INCOMING_READY sentinel: this one should be discarded

        ready_staging = staging_job_dir(qa_root, "mod-a", "target-b", "build")
        ready_staging.mkdir(parents=True)
        (ready_staging / "world").mkdir()
        (ready_staging / "world" / "level.dat").write_bytes(b"staged-b")
        (ready_staging / STAGING_READY).touch()
        # sentinel present: this one should roll forward to current

        orphan_staging = staging_job_dir(qa_root, "mod-b", "target-a", "pregen")
        orphan_staging.mkdir(parents=True)
        (orphan_staging / "world").mkdir()
        # no STAGING_READY sentinel: this one should be discarded, not promoted

        recover_pending(qa_root)

        assert not orphan_incoming.exists()

        cur_b = current_job_dir(qa_root, "mod-a", "target-b", "build")
        assert not ready_staging.exists()
        assert (cur_b / "world" / "level.dat").read_bytes() == b"staged-b"

        assert not orphan_staging.exists()
        assert not current_job_dir(qa_root, "mod-b", "target-a", "pregen").exists()

        # no cross-contamination: identities that were never populated stay absent
        assert not current_job_dir(qa_root, "mod-a", "target-a", "pregen").exists()
        assert not current_job_dir(qa_root, "mod-b", "target-b", "build").exists()

    def test_idempotent_on_clean_state(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        recover_pending(qa_root)
        recover_pending(qa_root)  # no raise, no-op

        # a clean tree stays clean: recovery creates no incoming/staging dirs
        assert not incoming_dir(qa_root).exists()
        assert not staging_dir(qa_root).exists()

    def test_idempotent_after_recovery(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        stg = staging_job_dir(qa_root, "fake-mod", "t", "x")
        stg.mkdir(parents=True)
        (stg / STAGING_READY).touch()

        recover_pending(qa_root)
        recover_pending(qa_root)  # second call is a no-op, no raise

        cur = current_job_dir(qa_root, "fake-mod", "t", "x")
        assert cur.exists()


class TestPromoteJobFailureIsolation:
    def test_swap_failure_reported_not_raised(
        self, tmp_path: Path, qa_run_factory, monkeypatch
    ) -> None:
        from squinch_qa.replace import pipeline as pipeline_mod

        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ]
        )

        real_replace = pipeline_mod.os.replace

        def _fail_staging_swap(src, dst):
            if "staging" in Path(src).parts:
                raise OSError("boom")
            return real_replace(src, dst)

        monkeypatch.setattr(pipeline_mod.os, "replace", _fail_staging_swap)
        recover_pending(qa_root)
        result = promote_job(qa_root, run_dir, "t", "pregen")

        assert result.promoted is False
        assert result.reason.startswith("promote_failed")
        assert staging_job_dir(qa_root, "fake-mod", "t", "pregen").exists()
        assert not current_job_dir(qa_root, "fake-mod", "t", "pregen").exists()

    def test_batch_continues_past_a_failing_job(
        self, tmp_path: Path, qa_run_factory, monkeypatch
    ) -> None:
        from squinch_qa.replace import pipeline as pipeline_mod

        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "t1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w1"),
                },
                {
                    "target_id": "t2",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path / "w2"),
                },
            ]
        )

        real_replace = pipeline_mod.os.replace

        def _fail_only_t1_swap(src, dst):
            src_path = Path(src)
            if "staging" in src_path.parts and src_path.parent.name == "t1":
                raise OSError("boom")
            return real_replace(src, dst)

        monkeypatch.setattr(pipeline_mod.os, "replace", _fail_only_t1_swap)
        recover_pending(qa_root)
        results = promote_run(qa_root, run_dir)

        by_key = {(r.target_id, r.test_id): r for r in results}
        assert by_key[("t1", "pregen")].promoted is False
        assert by_key[("t2", "pregen")].promoted is True
        assert staging_job_dir(qa_root, "fake-mod", "t1", "pregen").exists()
        assert not current_job_dir(qa_root, "fake-mod", "t1", "pregen").exists()
        assert current_job_dir(qa_root, "fake-mod", "t2", "pregen").exists()


class TestPromotionResultIsFailure:
    @pytest.mark.parametrize(
        "promoted,reason,expected",
        [
            (True, None, False),
            (False, "no_world_artifact", False),
            (False, "status_not_promotable: bad", False),
            (False, "world_hash_mismatch: nope", True),
            (False, "promote_failed: boom", True),
        ],
        ids=[
            "promoted_is_never_a_failure",
            "no_world_artifact_is_benign",
            "status_not_promotable_is_benign",
            "hash_mismatch_is_a_real_failure",
            "promote_failed_is_a_real_failure",
        ],
    )
    def test_is_failure(
        self, promoted: bool, reason: str | None, expected: bool
    ) -> None:
        r = PromotionResult("t", "x", promoted=promoted, reason=reason)
        assert r.is_failure is expected
