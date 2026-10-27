from __future__ import annotations

from pathlib import Path

import pytest
import squinch_minecraft_investigate.benchmark as benchmark_module
import squinch_minecraft_investigate.scenario as scenario_module
from squinch_minecraft_investigate.benchmark import (
    build_plan,
    load_benchmark,
    run_benchmark,
)
from squinch_minecraft_investigate.errors import InvestigationError


def _write_files(tmp_path: Path) -> Path:
    scenario = tmp_path / ".squinch/base.toml"
    scenario.parent.mkdir()
    scenario.write_text(
        """schema_version = 1
name = "base"
project = "games/minecraft/project"
loader = "fabric"
seed = 123
retention = "discard"

[expectations]
required_mods = ["minecraft"]

[[steps]]
id = "benchmark"
type = "command"
command = "benchmark run"
""",
        encoding="utf-8",
    )
    benchmark = tmp_path / ".squinch/matrix.toml"
    benchmark.write_text(
        """schema_version = 1
name = "matrix"
scenario = "base.toml"
repetitions = 2
order = "bracketed"
random_seed = 7
control_variant = "control"
continue_on_failure = true
retention = "keep"

[host]
enabled = false

[[variants]]
id = "control"
required_mods = []

[[variants]]
id = "treatment"
companion_artifacts = ["artifact-a"]
required_mods = ["examplemod"]
""",
        encoding="utf-8",
    )
    return benchmark


def test_bracketed_plan_has_start_and_end_controls(tmp_path: Path, monkeypatch) -> None:
    path = _write_files(tmp_path)

    matrix = load_benchmark(path)
    plan = build_plan(matrix)

    assert [entry["variant_id"] for entry in plan] == [
        "control",
        "treatment",
        "control",
        "control",
        "treatment",
        "control",
    ]
    assert plan[0]["bracket"] == "start"
    assert plan[2]["bracket"] == "end"


def test_variant_expected_startup_failure_removes_workload_steps(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    path.write_text(
        path.read_text().replace(
            'required_mods = ["examplemod"]\n',
            'required_mods = ["examplemod"]\n'
            'startup_failure = { code = "startup_exited", '
            'log_contains = ["Feature order cycle found"] }\n',
        )
    )
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)

    matrix = load_benchmark(path)
    entry = next(
        item for item in build_plan(matrix) if item["variant_id"] == "treatment"
    )
    base = scenario_module.load_scenario(matrix.scenario_path)
    effective = benchmark_module._effective_scenario(base, matrix, entry)

    assert effective.steps == ()
    assert effective.probes == {}
    assert effective.expectations["startup_failure"] == {
        "code": "startup_exited",
        "log_contains": ["Feature order cycle found"],
    }


def test_matrix_run_is_resumable_and_aggregates_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    calls: list[str] = []

    def fake_runner(scenario):
        calls.append(scenario.name)
        assert scenario.retention == "keep"
        return {
            "state": {"run_id": f"run-{len(calls)}"},
            "scenario_summary": f"summary-{len(calls)}.json",
            "scenario_progress": f"progress-{len(calls)}.jsonl",
            "steps": [
                {
                    "id": "benchmark",
                    "result": {
                        "metrics": {
                            "wall_seconds": {
                                "value": float(len(calls)),
                                "unit": "seconds",
                            }
                        }
                    },
                }
            ],
        }

    summary = run_benchmark(
        matrix,
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert summary["state"] == "succeeded"
    assert summary["completed_runs"] == 6
    assert len(calls) == 6
    assert (
        summary["aggregate_metrics"]["control"]["benchmark.wall_seconds"]["count"] == 4
    )

    result_to_repeat = Path(summary["run_dir"]) / "runs/0006-control.json"
    result_to_repeat.unlink()
    resumed = run_benchmark(
        matrix,
        resume_run_id=summary["run_id"],
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert resumed["state"] == "succeeded"
    assert len(calls) == 7


def test_matrix_can_pause_after_bounded_new_runs_and_resume(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    calls = 0

    def fake_runner(_scenario):
        nonlocal calls
        calls += 1
        return {
            "state": {"run_id": f"run-{calls}"},
            "scenario_summary": f"summary-{calls}.json",
            "scenario_progress": f"progress-{calls}.jsonl",
            "steps": [],
        }

    first = run_benchmark(
        matrix,
        max_new_runs=2,
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert first["state"] == "running"
    assert first["completed_runs"] == 2
    assert first["new_runs"] == 2

    second = run_benchmark(
        matrix,
        resume_run_id=first["run_id"],
        max_new_runs=2,
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert second["state"] == "running"
    assert second["completed_runs"] == 4
    assert second["new_runs"] == 2

    final = run_benchmark(
        matrix,
        resume_run_id=first["run_id"],
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert final["state"] == "succeeded"
    assert final["completed_runs"] == 6
    assert final["new_runs"] == 2
    assert calls == 6


def test_resume_rejects_changed_base_scenario(tmp_path: Path, monkeypatch) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)

    def fake_runner(_scenario):
        return {"state": {"run_id": "run"}, "steps": []}

    summary = run_benchmark(
        matrix,
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    matrix.scenario_path.write_text(matrix.scenario_path.read_text() + "\n# changed\n")

    with pytest.raises(InvestigationError, match="base scenario changed"):
        run_benchmark(
            matrix,
            resume_run_id=summary["run_id"],
            scenario_runner=fake_runner,
            benchmark_root=tmp_path / "benchmark-runs",
        )


def test_resume_retries_lifecycle_blocker_before_continuing(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    calls = 0

    def blocked_runner(_scenario):
        nonlocal calls
        calls += 1
        return {
            "state": {"run_id": "blocked-run"},
            "steps": [],
            "cleanup_failed": {
                "code": "cleanup_failed",
                "message": "owned process remains alive",
                "details": {},
            },
        }

    first = run_benchmark(
        matrix,
        scenario_runner=blocked_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert first["completed_runs"] == 1
    assert first["failed_runs"] == 1
    assert calls == 1

    def recovered_runner(_scenario):
        nonlocal calls
        calls += 1
        return {
            "state": {"run_id": f"recovered-{calls}"},
            "scenario_summary": f"summary-{calls}.json",
            "scenario_progress": f"progress-{calls}.jsonl",
            "steps": [],
        }

    resumed = run_benchmark(
        matrix,
        resume_run_id=first["run_id"],
        scenario_runner=recovered_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert resumed["state"] == "succeeded"
    assert resumed["completed_runs"] == 6
    assert resumed["failed_runs"] == 0
    assert calls == 7


def test_host_not_quiet_stops_and_is_retried_on_resume(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)

    def blocked_host(_policy):
        raise InvestigationError("host_not_quiet", "host stayed busy")

    monkeypatch.setattr(benchmark_module, "wait_for_quiet_host", blocked_host)
    first = run_benchmark(
        matrix,
        scenario_runner=lambda _scenario: pytest.fail("scenario must not start"),
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert first["completed_runs"] == 1
    assert first["failed_runs"] == 1
    assert first["records"][0]["error"]["code"] == "host_not_quiet"

    monkeypatch.setattr(
        benchmark_module,
        "wait_for_quiet_host",
        lambda _policy: {"enabled": False},
    )
    resumed = run_benchmark(
        matrix,
        resume_run_id=first["run_id"],
        scenario_runner=lambda _scenario: {
            "state": {"run_id": "recovered"},
            "scenario_summary": "summary.json",
            "scenario_progress": "progress.jsonl",
            "steps": [],
        },
        benchmark_root=tmp_path / "benchmark-runs",
    )
    assert resumed["state"] == "succeeded"
    assert resumed["failed_runs"] == 0
    assert resumed["completed_runs"] == 6


def test_auto_resume_preserves_clean_checkpoints_across_lifecycle_failure(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    calls = 0

    def initially_blocked(_scenario):
        nonlocal calls
        calls += 1
        if calls == 3:
            return {
                "state": {"run_id": "blocked-run"},
                "scenario_summary": "blocked-summary.json",
                "scenario_progress": "blocked-progress.jsonl",
                "steps": [],
                "cleanup_failed": {
                    "code": "cleanup_failed",
                    "message": "owned process remains alive",
                    "details": {},
                },
            }
        return {
            "state": {"run_id": f"accepted-{calls}"},
            "scenario_summary": f"summary-{calls}.json",
            "scenario_progress": f"progress-{calls}.jsonl",
            "steps": [],
        }

    benchmark_root = tmp_path / "benchmark-runs"
    first = run_benchmark(
        matrix,
        scenario_runner=initially_blocked,
        benchmark_root=benchmark_root,
    )
    assert first["state"] == "failed"
    assert first["accepted_runs"] == 2
    assert first["retryable_runs"] == 1
    assert first["attempted_runs"] == 3

    run_dir = Path(first["run_dir"])
    accepted_paths = sorted((run_dir / "runs").glob("*.json"))[:2]
    accepted_before = [path.read_bytes() for path in accepted_paths]
    checkpoint_before = [
        path.with_suffix(path.suffix + ".sha256").read_bytes()
        for path in accepted_paths
    ]

    def recovered(_scenario):
        nonlocal calls
        calls += 1
        return {
            "state": {"run_id": f"recovered-{calls}"},
            "scenario_summary": f"summary-{calls}.json",
            "scenario_progress": f"progress-{calls}.jsonl",
            "steps": [],
        }

    resumed = run_benchmark(
        matrix,
        scenario_runner=recovered,
        benchmark_root=benchmark_root,
    )

    assert resumed["run_id"] == first["run_id"]
    assert resumed["auto_resumed"] is True
    assert resumed["state"] == "succeeded"
    assert resumed["accepted_runs"] == 6
    assert resumed["failed_runs"] == 0
    assert resumed["new_runs"] == 4
    assert calls == 7
    assert [path.read_bytes() for path in accepted_paths] == accepted_before
    assert [
        path.with_suffix(path.suffix + ".sha256").read_bytes()
        for path in accepted_paths
    ] == checkpoint_before
    assert len(list((run_dir / "attempts" / "0003-control").glob("*.json"))) == 2


def test_rejected_attempt_requires_explicit_retry_and_completed_campaign_requires_new(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    calls = 0

    def one_rejected(_scenario):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InvestigationError("measurement_failed", "bad sample")
        return {"state": {"run_id": f"run-{calls}"}, "steps": []}

    benchmark_root = tmp_path / "benchmark-runs"
    first = run_benchmark(
        matrix,
        scenario_runner=one_rejected,
        benchmark_root=benchmark_root,
    )
    assert first["accepted_runs"] == 5
    assert first["rejected_runs"] == 1
    assert calls == 6

    unchanged = run_benchmark(
        matrix,
        scenario_runner=one_rejected,
        benchmark_root=benchmark_root,
    )
    assert unchanged["run_id"] == first["run_id"]
    assert unchanged["new_runs"] == 0
    assert unchanged["rejected_runs"] == 1
    assert calls == 6

    completed = run_benchmark(
        matrix,
        retry_failed=True,
        scenario_runner=one_rejected,
        benchmark_root=benchmark_root,
    )
    assert completed["run_id"] == first["run_id"]
    assert completed["state"] == "succeeded"
    assert completed["new_runs"] == 1
    assert calls == 7

    with pytest.raises(InvestigationError, match="already completed"):
        run_benchmark(
            matrix,
            scenario_runner=one_rejected,
            benchmark_root=benchmark_root,
        )

    repeated = run_benchmark(
        matrix,
        new_campaign=True,
        scenario_runner=one_rejected,
        benchmark_root=benchmark_root,
    )
    assert repeated["run_id"] != first["run_id"]


def test_resume_rejects_modified_accepted_checkpoint(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    matrix = load_benchmark(path)
    summary = run_benchmark(
        matrix,
        scenario_runner=lambda _scenario: {"state": {"run_id": "run"}, "steps": []},
        benchmark_root=tmp_path / "benchmark-runs",
    )
    checkpoint = Path(summary["run_dir"]) / "runs/0001-control.json"
    checkpoint.write_text(
        checkpoint.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )

    with pytest.raises(InvestigationError, match="digest changed"):
        run_benchmark(
            matrix,
            resume_run_id=summary["run_id"],
            scenario_runner=lambda _scenario: pytest.fail("must not rerun"),
            benchmark_root=tmp_path / "benchmark-runs",
        )


def _write_paired_files(tmp_path: Path) -> Path:
    scenario = tmp_path / ".squinch/paired-base.toml"
    scenario.parent.mkdir(exist_ok=True)
    scenario.write_text(
        """schema_version = 1
name = "paired base"
project = "games/minecraft/project"
loader = "fabric"
seed = 123
retention = "discard"

[expectations]
required_mods = ["minecraft"]

[[steps]]
id = "benchmark"
type = "command"
command = "benchmark run"
""",
        encoding="utf-8",
    )
    matrix = tmp_path / ".squinch/paired-matrix.toml"
    matrix.write_text(
        """schema_version = 1
name = "paired matrix"
scenario = "paired-base.toml"
repetitions = 1
order = "paired-bracketed"
random_seed = 11
control_pair = "control"
retention = "keep"

[host]
enabled = false

[[variants]]
id = "fabric-control"
loader = "fabric"
comparison_group = "fabric"
pair_id = "control"

[[variants]]
id = "neoforge-control"
loader = "neoforge"
comparison_group = "neoforge"
pair_id = "control"

[[variants]]
id = "fabric-treatment"
loader = "fabric"
comparison_group = "fabric"
pair_id = "treatment"

[[variants]]
id = "neoforge-treatment"
loader = "neoforge"
comparison_group = "neoforge"
pair_id = "treatment"
""",
        encoding="utf-8",
    )
    return matrix


def test_paired_bracketed_plan_pairs_loaders_between_controls(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_paired_files(tmp_path)

    plan = build_plan(load_benchmark(path))

    assert len(plan) == 6
    assert {entry["comparison_group"] for entry in plan[:2]} == {"fabric", "neoforge"}
    assert {entry["comparison_group"] for entry in plan[2:4]} == {"fabric", "neoforge"}
    assert {entry["pair_id"] for entry in plan[2:4]} == {"treatment"}
    assert {entry["comparison_group"] for entry in plan[4:]} == {"fabric", "neoforge"}
    assert all(entry["bracket"] == "start" for entry in plan[:2])
    assert all(entry["bracket"] is None for entry in plan[2:4])
    assert all(entry["bracket"] == "end" for entry in plan[4:])


def test_paired_matrix_overrides_loader_and_normalizes_each_group(
    tmp_path: Path, monkeypatch
) -> None:
    path = _write_paired_files(tmp_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(benchmark_module, "LOCKS_ROOT", tmp_path / "locks")
    seen: list[tuple[str, str]] = []

    def fake_runner(scenario):
        seen.append((scenario.name, scenario.loader))
        treatment = "treatment" in scenario.name
        value = {
            ("fabric", False): 10.0,
            ("fabric", True): 5.0,
            ("neoforge", False): 20.0,
            ("neoforge", True): 8.0,
        }[(scenario.loader, treatment)]
        return {
            "state": {"run_id": f"run-{len(seen)}"},
            "steps": [
                {
                    "id": "benchmark",
                    "result": {
                        "metrics": {
                            "throughput": {"value": value, "unit": "chunks/second"}
                        }
                    },
                }
            ],
        }

    summary = run_benchmark(
        load_benchmark(path),
        scenario_runner=fake_runner,
        benchmark_root=tmp_path / "benchmark-runs",
    )

    assert {loader for _, loader in seen} == {"fabric", "neoforge"}
    comparison = summary["paired_comparison"]
    fabric = comparison["groups"]["fabric"]["treatment"]["benchmark.throughput"]
    neoforge = comparison["groups"]["neoforge"]["treatment"]["benchmark.throughput"]
    assert fabric["median_relative_to_control"] == pytest.approx(0.5)
    assert neoforge["median_relative_to_control"] == pytest.approx(0.4)
    assert comparison["pairs"]["treatment"]["benchmark.throughput"]["group_ratios"][
        "neoforge/fabric"
    ] == pytest.approx(0.8)


def test_paired_comparison_uses_controls_from_the_same_repetition() -> None:
    def record(pair_id: str, repetition: int, value: float) -> dict:
        return {
            "state": "succeeded",
            "plan": {
                "comparison_group": "fabric",
                "pair_id": pair_id,
                "repetition": repetition,
            },
            "metrics": {"benchmark.throughput": {"value": value}},
        }

    records = [
        record("control", 1, 10.0),
        record("control", 1, 10.0),
        record("treatment", 1, 10.0),
        record("control", 2, 100.0),
        record("control", 2, 100.0),
        record("treatment", 2, 50.0),
    ]

    comparison = benchmark_module._paired_comparison(records, "control")
    treatment = comparison["groups"]["fabric"]["treatment"]["benchmark.throughput"]
    assert treatment["relative_to_control_values"] == [1.0, 0.5]
    assert treatment["median_relative_to_control"] == pytest.approx(0.75)
