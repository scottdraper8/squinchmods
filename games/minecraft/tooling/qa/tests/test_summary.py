from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from squinch_qa import cli
from squinch_qa.errors import SummaryError
from squinch_qa.executors.base import FailureDetail, JobResult
from squinch_qa.manifest import emit_all
from squinch_qa.models import (
    ExecutionPlan,
    PlannedJob,
    ResolvedProfile,
    Target,
    TestSpec,
)
from squinch_qa.summary import render_summary


def _target(id: str) -> Target:
    return Target(
        id=id,
        minecraft="1.20.1",
        loader="forge",
        loader_version="47.0.0",
        java=17,
        supported=True,
        capabilities=["server"],
    )


def _test_spec(id: str, required: bool = True) -> TestSpec:
    return TestSpec(
        id=id,
        required=required,
        requires=[],
        adapters={},
        expectations={},
        config={},
        origin_index=0,
    )


def _job(
    target_id: str,
    test_id: str,
    *,
    expected_failure: dict | None = None,
) -> PlannedJob:
    return PlannedJob(
        target=_target(target_id),
        test_spec=_test_spec(test_id),
        adapter=None,
        expected_failure=expected_failure,
        expectations={},
    )


def _build_run(
    tmp_path: Path,
    jobs_and_results: list[tuple[PlannedJob, JobResult]],
) -> Path:
    jobs = [j for j, _ in jobs_and_results]
    plan = ExecutionPlan(
        mod_id="redstone-backport",
        display_name="Redstone Backport",
        profile=ResolvedProfile(
            name="default",
            resolved_from=["default"],
            tests=[j.test_spec for j in jobs],
            max_parallel=4,
            max_jobs=32,
        ),
        jobs=jobs,
        skipped=[],
        skipped_targets=[],
    )
    job_results = {
        (j.target.id, j.test_spec.id): result for j, result in jobs_and_results
    }
    run_dir = tmp_path / "runs" / "1700000000000-deadbeef"
    emit_all(
        run_dir,
        plan,
        job_results,
        repo_root=tmp_path,
        mod_dir=tmp_path,
        run_id=run_dir.name,
        plan_bytes=b'{"schema":1}',
    )
    return run_dir


def _result(status: str, failure: FailureDetail | None = None) -> JobResult:
    return JobResult(
        status=status,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:05+00:00",
        duration_s=5.0,
        logs=[],
        artifacts=[],
        failure=failure,
    )


class TestRenderSummary:
    def test_header_has_run_id_mod_and_profile(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path, [(_job("forge-1.20.1", "build"), _result("pass"))]
        )
        text = render_summary(run_dir)
        assert "1700000000000-deadbeef" in text
        assert "redstone-backport" in text
        assert "default" in text

    def test_status_and_exit_code_reflect_all_pass(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path, [(_job("forge-1.20.1", "build"), _result("pass"))]
        )
        text = render_summary(run_dir)
        assert "PASS" in text
        assert "exit 0" in text

    def test_status_and_exit_code_reflect_a_failure(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path,
            [
                (_job("forge-1.20.1", "build"), _result("pass")),
                (
                    _job("forge-1.20.1", "pregen"),
                    _result(
                        "fail", FailureDetail(reason="tool-timeout", detail="900s")
                    ),
                ),
            ],
        )
        text = render_summary(run_dir)
        assert "FAIL" in text
        assert "exit 4" in text

    def test_counts_line_matches_actual_statuses(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path,
            [
                (_job("forge-1.20.1", "build"), _result("pass")),
                (_job("forge-1.20.1", "server-smoke"), _result("pass")),
                (
                    _job("forge-1.20.1", "pregen"),
                    _result("fail", FailureDetail(reason="tool-timeout")),
                ),
            ],
        )
        text = render_summary(run_dir)
        assert "pass: 2" in text
        assert "fail: 1" in text

    def test_job_line_includes_matrix_id_and_status(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path, [(_job("forge-1.20.1", "build"), _result("pass"))]
        )
        text = render_summary(run_dir)
        assert "forge-1.20.1/build" in text
        assert "pass" in text

    def test_failure_line_includes_reason_and_detail(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path,
            [
                (
                    _job("forge-1.20.1", "pregen"),
                    _result(
                        "fail",
                        FailureDetail(
                            reason="tool-timeout",
                            detail="chunksmith did not finish within 900s",
                        ),
                    ),
                )
            ],
        )
        text = render_summary(run_dir)
        assert "tool-timeout" in text
        assert "chunksmith did not finish within 900s" in text

    def test_expected_failure_line_includes_reason_and_expiry(self, tmp_path: Path):
        ef = {
            "reason": "Quilt menu sync not implemented yet",
            "expires": "2026-08-01",
            "expired": False,
        }
        run_dir = _build_run(
            tmp_path,
            [
                (
                    _job("quilt-1.20.1", "crafter-basic", expected_failure=ef),
                    _result(
                        "fail", FailureDetail(reason="menu_desync", detail="timeout")
                    ),
                )
            ],
        )
        text = render_summary(run_dir)
        assert "expected_failure" in text
        assert "Quilt menu sync not implemented yet" in text
        assert "2026-08-01" in text

    def test_passing_job_has_no_trailing_failure_detail(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path, [(_job("forge-1.20.1", "build"), _result("pass"))]
        )
        text = render_summary(run_dir)
        job_line = next(
            line for line in text.splitlines() if "forge-1.20.1/build" in line
        )
        assert job_line.rstrip().endswith("s")  # ends in the duration, no extra detail

    def test_missing_run_dir_raises_summary_error(self, tmp_path: Path):
        with pytest.raises(SummaryError, match="missing"):
            render_summary(tmp_path / "runs" / "no-such-run")

    def test_malformed_result_json_raises_summary_error(self, tmp_path: Path):
        run_dir = tmp_path / "runs" / "bad-run"
        run_dir.mkdir(parents=True)
        (run_dir / "result.json").write_text("{not valid json")
        with pytest.raises(SummaryError, match="malformed"):
            render_summary(run_dir)


def _run_summary_cli(qa_runs_dir: Path, run_id: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(
            [
                "summary",
                run_id,
                "--repo-root",
                str(qa_runs_dir),  # unused by _cmd_summary when --qa-runs-dir is set
                "--qa-runs-dir",
                str(qa_runs_dir),
            ]
        )
    return code, buf.getvalue()


class TestSummaryCLI:
    def test_exits_0_and_prints_summary_for_a_real_run(self, tmp_path: Path):
        run_dir = _build_run(
            tmp_path, [(_job("forge-1.20.1", "build"), _result("pass"))]
        )
        code, output = _run_summary_cli(run_dir.parent, run_dir.name)
        assert code == 0
        assert "forge-1.20.1/build" in output

    def test_exits_10_on_unknown_run_id(self, tmp_path: Path):
        qa_runs_dir = tmp_path / "runs"
        qa_runs_dir.mkdir()
        code, _ = _run_summary_cli(qa_runs_dir, "no-such-run")
        assert code == 10

    def test_rejects_path_traversal_run_id(self, tmp_path: Path):
        qa_runs_dir = tmp_path / "runs"
        qa_runs_dir.mkdir()
        code, _ = _run_summary_cli(qa_runs_dir, "../../etc")
        assert code == 6  # ReplaceError, from assert_within
