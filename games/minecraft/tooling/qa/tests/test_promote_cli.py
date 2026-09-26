from __future__ import annotations

from pathlib import Path

from squinch_qa.artifacts import default_qa_root
from squinch_qa.cli import main
from squinch_qa.replace.layout import current_job_dir


def _world_src(tmp_path: Path) -> Path:
    src = tmp_path / "world-src"
    (src / "region").mkdir(parents=True)
    (src / "region" / "r.0.0.mca").write_bytes(b"chunk data")
    return src


class TestPromoteCli:
    def test_dry_run_does_not_touch_current(
        self, tmp_path: Path, qa_run_factory, capsys
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
                "--dry-run",
            ]
        )

        assert exit_code == 0
        assert not current_job_dir(
            default_qa_root(qa_root), "fake-mod", "t", "pregen"
        ).exists()
        out = capsys.readouterr().out
        assert '"type": "promote_start"' in out
        assert '"type": "promote_done"' in out

    def test_real_promotion_populates_current(
        self, tmp_path: Path, qa_run_factory, capsys
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert exit_code == 0
        cur = current_job_dir(default_qa_root(qa_root), "fake-mod", "t", "pregen")
        assert (cur / "world" / "region" / "r.0.0.mca").read_bytes() == b"chunk data"

    def test_target_and_test_filters(self, tmp_path: Path, qa_run_factory) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
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
            ],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
                "--target",
                "t1",
            ]
        )

        assert exit_code == 0
        assert current_job_dir(
            default_qa_root(qa_root), "fake-mod", "t1", "pregen"
        ).exists()
        assert not current_job_dir(
            default_qa_root(qa_root), "fake-mod", "t2", "pregen"
        ).exists()

    def test_recovers_pending_before_promoting(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        """A leftover unfinished staging entry from a prior crash must be
        cleaned up/rolled-forward before this run's promotion proceeds."""
        from squinch_qa.replace.layout import staging_job_dir

        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        stale_staging = staging_job_dir(
            default_qa_root(qa_root), "fake-mod", "stale-target", "stale-test"
        )
        stale_staging.mkdir(parents=True)
        (stale_staging / "world").mkdir()
        # no sentinel: this is a crashed, incomplete stage and must be purged

        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                }
            ],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert exit_code == 0
        assert not stale_staging.exists()
        assert current_job_dir(
            default_qa_root(qa_root), "fake-mod", "t", "pregen"
        ).exists()

    def test_run_id_path_traversal_rejected(self, tmp_path: Path) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        qa_runs_dir.mkdir()
        secret = tmp_path / "secret-run"
        secret.mkdir()
        (secret / "qa-manifest.json").write_text("{}")

        exit_code = main(
            [
                "promote",
                "--run-id",
                "../secret-run",
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert exit_code == 6

    def test_promotion_failure_returns_nonzero_exit(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
            jobs=[
                {
                    "target_id": "t",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                    "world_sha256_override": "0" * 64,
                }
            ],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert exit_code == 6

    def test_benign_skip_still_exits_zero(self, tmp_path: Path, qa_run_factory) -> None:
        qa_root = tmp_path / "repo"
        qa_root.mkdir()
        qa_runs_dir = tmp_path / "qa-runs"
        run_dir = qa_run_factory(
            runs_root=qa_runs_dir,
            jobs=[{"target_id": "t", "test_id": "build", "status": "pass"}],
        )

        exit_code = main(
            [
                "promote",
                "--run-id",
                run_dir.name,
                "--repo-root",
                str(qa_root),
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )

        assert exit_code == 0
