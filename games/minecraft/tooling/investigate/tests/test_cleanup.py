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
    path.write_text(f"schema_version = 1\nprotected_runs = [{values}]\n", encoding="utf-8")


def _write_run(root: Path, run_id: str) -> Path:
    artifact_dir = root / run_id
    artifact_dir.mkdir(parents=True)
    run_dir = root.parent / "project-run"
    level_name = f"squinch-{run_id.lower()}"
    manifest = {
        "ownership": OWNERSHIP,
        "run_id": run_id,
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


def test_retention_index_rejects_duplicate_ids(tmp_path: Path) -> None:
    index = tmp_path / "retention.toml"
    _write_index(index, PROTECTED, PROTECTED)

    with pytest.raises(InvestigationError, match="duplicate"):
        load_protected_run_ids(index)
