from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from squinch_minecraft_investigate import cli
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.retention import load_protected_run_ids
from squinch_minecraft_investigate.server import OWNERSHIP

PROTECTED = "20260901T000000Z-0000000001"
DISPOSABLE = "20260901T000000Z-0000000002"


def _write_index(path: Path, *run_ids: str) -> None:
    values = ", ".join(json.dumps(run_id) for run_id in run_ids)
    path.write_text(
        f"schema_version = 1\nprotected_runs = [{values}]\n", encoding="utf-8"
    )


def _write_run(root: Path, run_id: str, *, project: Path | None = None) -> Path:
    artifact_dir = root / run_id
    artifact_dir.mkdir(parents=True)
    run_dir = root.parent / "project-run"
    level_name = f"squinch-{run_id.lower()}"
    manifest = {
        "ownership": OWNERSHIP,
        "run_id": run_id,
        "project": str(project) if project is not None else None,
        "run_dir": str(run_dir),
        "level_name": level_name,
        "retained_world": str(run_dir / level_name),
    }
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / level_name).mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _args(*, runs: list[str] | None = None, apply: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        runs=runs,
        older_than_days=None if runs else 0,
        project=None,
        apply=apply,
        include_protected=False,
    )


def test_age_cleanup_skips_cited_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    protected_dir = _write_run(runs_root, PROTECTED)
    disposable_dir = _write_run(runs_root, DISPOSABLE)
    index = tmp_path / "retention.toml"
    _write_index(index, PROTECTED)
    monkeypatch.setattr(cli, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(cli, "ACTIVE_ROOT", tmp_path / "active")
    monkeypatch.setattr(cli, "RETENTION_INDEX", index)

    value, _ = cli._clean(_args(apply=True))

    assert protected_dir.is_dir()
    assert not disposable_dir.exists()
    assert value["data"]["protected"] == [PROTECTED]
    assert [item["run_id"] for item in value["data"]["targets"]] == [DISPOSABLE]


def test_age_cleanup_can_be_restricted_to_one_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    selected_project = tmp_path / "selected-project"
    other_project = tmp_path / "other-project"
    selected_project.mkdir()
    other_project.mkdir()
    (selected_project / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    (other_project / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    selected = _write_run(runs_root, PROTECTED, project=selected_project)
    other = _write_run(runs_root, DISPOSABLE, project=other_project)
    index = tmp_path / "retention.toml"
    _write_index(index)
    monkeypatch.setattr(cli, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(cli, "ACTIVE_ROOT", tmp_path / "active")
    monkeypatch.setattr(cli, "RETENTION_INDEX", index)

    args = _args(apply=True)
    args.project = str(selected_project)
    value, _ = cli._clean(args)

    assert not selected.exists()
    assert other.is_dir()
    assert value["data"]["targets"][0]["project"] == str(selected_project.resolve())


def test_exact_cleanup_requires_explicit_protected_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root, PROTECTED)
    index = tmp_path / "retention.toml"
    _write_index(index, PROTECTED)
    monkeypatch.setattr(cli, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(cli, "ACTIVE_ROOT", tmp_path / "active")
    monkeypatch.setattr(cli, "RETENTION_INDEX", index)

    with pytest.raises(InvestigationError, match="protected"):
        cli._clean(_args(runs=[PROTECTED]))

    args = _args(runs=[PROTECTED], apply=True)
    args.include_protected = True
    cli._clean(args)
    assert not (runs_root / PROTECTED).exists()


def test_exact_benchmark_and_comparison_cleanup_validate_owned_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark_id = "20261024T000000Z-1234567890"
    comparison_id = "compare-20261024T000000Z-1234567890"
    benchmark_root = tmp_path / "benchmarks"
    comparison_root = tmp_path / "comparisons"
    worktrees_root = tmp_path / "worktrees"
    benchmark_dir = benchmark_root / benchmark_id
    comparison_dir = comparison_root / comparison_id
    benchmark_dir.mkdir(parents=True)
    comparison_dir.mkdir(parents=True)
    (benchmark_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "run_id": benchmark_id}), encoding="utf-8"
    )
    (benchmark_dir / "benchmark.toml").write_text(
        "schema_version = 1\n", encoding="utf-8"
    )
    (comparison_dir / "comparison-summary.json").write_text(
        json.dumps({"comparison_id": comparison_id, "preserved_worktrees": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "BENCHMARK_ROOT", benchmark_root)
    monkeypatch.setattr(cli, "COMPARISONS_ROOT", comparison_root)
    monkeypatch.setattr(cli, "WORKTREES_ROOT", worktrees_root)

    benchmark_args = argparse.Namespace(
        runs=None,
        benchmarks=[benchmark_id],
        comparisons=None,
        older_than_days=None,
        project=None,
        apply=True,
        include_protected=False,
    )
    comparison_args = argparse.Namespace(
        runs=None,
        benchmarks=None,
        comparisons=[comparison_id],
        older_than_days=None,
        project=None,
        apply=True,
        include_protected=False,
    )

    cli._clean(benchmark_args)
    cli._clean(comparison_args)

    assert not benchmark_dir.exists()
    assert not comparison_dir.exists()


def test_benchmark_cleanup_can_select_exact_base_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark_root = tmp_path / "benchmarks"
    selected_scenario = tmp_path / "selected.toml"
    other_scenario = tmp_path / "other.toml"
    selected_scenario.write_text("schema_version = 1\n", encoding="utf-8")
    other_scenario.write_text("schema_version = 1\n", encoding="utf-8")

    selected_id = "20261024T000000Z-1234567890"
    other_id = "20261024T000001Z-1234567890"
    for benchmark_id, scenario in (
        (selected_id, selected_scenario),
        (other_id, other_scenario),
    ):
        benchmark_dir = benchmark_root / benchmark_id
        benchmark_dir.mkdir(parents=True)
        (benchmark_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": benchmark_id,
                    "scenario_path": str(scenario),
                }
            ),
            encoding="utf-8",
        )
        (benchmark_dir / "benchmark.toml").write_text(
            "schema_version = 1\n", encoding="utf-8"
        )

    monkeypatch.setattr(cli, "BENCHMARK_ROOT", benchmark_root)
    args = argparse.Namespace(
        runs=None,
        benchmarks=None,
        benchmark_scenario=str(selected_scenario),
        comparisons=None,
        older_than_days=None,
        project=None,
        apply=True,
        include_protected=False,
    )

    value, _ = cli._clean(args)

    assert not (benchmark_root / selected_id).exists()
    assert (benchmark_root / other_id).is_dir()
    assert value["data"]["targets"][0]["benchmark_id"] == selected_id


def _write_benchmark_checkpoint(
    benchmark_root: Path, benchmark_id: str, run_id: str
) -> Path:
    benchmark_dir = benchmark_root / benchmark_id
    runs_dir = benchmark_dir / "runs"
    runs_dir.mkdir(parents=True)
    (benchmark_dir / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "run_id": benchmark_id}), encoding="utf-8"
    )
    (benchmark_dir / "benchmark.toml").write_text(
        "schema_version = 1\n", encoding="utf-8"
    )
    (runs_dir / "0001-control.json").write_text(
        json.dumps(
            {
                "state": "succeeded",
                "scenario_run_id": run_id,
                "plan": {"sequence": 1, "variant_id": "control"},
            }
        ),
        encoding="utf-8",
    )
    return benchmark_dir


def test_run_cleanup_preserves_accepted_benchmark_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    accepted_dir = _write_run(runs_root, DISPOSABLE)
    benchmark_root = tmp_path / "benchmarks"
    benchmark_id = "20261024T000000Z-1234567890"
    _write_benchmark_checkpoint(benchmark_root, benchmark_id, DISPOSABLE)
    index = tmp_path / "retention.toml"
    _write_index(index)
    monkeypatch.setattr(cli, "RUNS_ROOT", runs_root)
    monkeypatch.setattr(cli, "ACTIVE_ROOT", tmp_path / "active")
    monkeypatch.setattr(cli, "BENCHMARK_ROOT", benchmark_root)
    monkeypatch.setattr(cli, "RETENTION_INDEX", index)

    value, _ = cli._clean(_args(apply=True))

    assert accepted_dir.is_dir()
    assert value["data"]["targets"] == []
    assert value["data"]["checkpoint_protected"][0]["run_id"] == DISPOSABLE

    with pytest.raises(InvestigationError, match="accepted checkpoint"):
        cli._clean(_args(runs=[DISPOSABLE], apply=True))


def test_benchmark_cleanup_requires_deliberate_checkpoint_discard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark_root = tmp_path / "benchmarks"
    benchmark_id = "20261024T000000Z-1234567890"
    benchmark_dir = _write_benchmark_checkpoint(
        benchmark_root, benchmark_id, DISPOSABLE
    )
    monkeypatch.setattr(cli, "BENCHMARK_ROOT", benchmark_root)

    args = argparse.Namespace(
        runs=None,
        benchmarks=[benchmark_id],
        benchmark_scenario=None,
        comparisons=None,
        older_than_days=None,
        project=None,
        apply=True,
        include_protected=False,
        discard_checkpoints=False,
    )
    with pytest.raises(InvestigationError, match="accepted checkpoint"):
        cli._clean(args)
    assert benchmark_dir.is_dir()

    args.discard_checkpoints = True
    value, _ = cli._clean(args)
    assert not benchmark_dir.exists()
    assert value["data"]["targets"][0]["accepted_checkpoints"] == 1


def test_retention_index_rejects_duplicate_ids(tmp_path: Path) -> None:
    index = tmp_path / "retention.toml"
    _write_index(index, PROTECTED, PROTECTED)

    with pytest.raises(InvestigationError, match="duplicate"):
        load_protected_run_ids(index)
