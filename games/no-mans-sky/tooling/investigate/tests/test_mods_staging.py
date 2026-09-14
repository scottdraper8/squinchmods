from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_nms_investigate import staging
from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.mods import (
    _compiler_versions_equal,
    analyze_mod,
    conflict_report,
    resolve_deployment_root,
    write_analysis_report,
)


def test_compiler_version_comparison_normalizes_zero_padded_components() -> None:
    assert _compiler_versions_equal("7.1.0.1", "7.01.0.1")
    assert not _compiler_versions_equal("7.1.0.0", "7.01.0.1")


def mod_tree(tmp_path: Path, name: str = "mod", value: str = "X") -> Path:
    root = tmp_path / name
    file = root / "METADATA/REALITY/TABLE.EXML"
    file.parent.mkdir(parents=True)
    file.write_text(
        '<Data template="cTable"><Property name="Items">'
        f'<Property name="Items" value="{value}" /></Property></Data>',
        encoding="utf-8",
    )
    return root


def test_wrapper_root_resolution_and_conflict_detection(tmp_path: Path) -> None:
    root = mod_tree(tmp_path / "wrapper", "Nested")
    assert resolve_deployment_root(root.parent) == root.resolve()
    left = analyze_mod(root, tmp_path / "left")
    right = analyze_mod(root, tmp_path / "right")
    result = conflict_report([left, right])
    assert result["conflict_count"] > 0
    assert result["potential_conflict_count"] > 0
    assert not result["conflict_free"]
    report_path = tmp_path / "report/analysis.json"
    write_analysis_report(left, report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    retained = json.loads(Path(report["touched_paths_report"]).read_text(encoding="utf-8"))
    assert report["touched_path_count"] == len(left["touched_paths"])
    assert retained == left["touched_paths"]
    assert "patch_paths" not in report["files"][0]


def test_stage_lifecycle_and_modified_tree_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = mod_tree(tmp_path)
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    state = tmp_path / "stage-state"
    monkeypatch.setattr(staging, "STAGES_ROOT", state)
    monkeypatch.setattr(staging, "running_processes", lambda: [])
    run_id = "20260911T120000Z-stage-1234abcd"
    dry = staging.stage(root, game, run_id, apply=False)
    assert not Path(dry["destination"]).exists()
    applied = staging.stage(root, game, run_id, apply=True)
    assert Path(applied["destination"]).is_dir()
    assert staging.stage_status(run_id)["content_matches"]
    staged_file = Path(applied["destination"]) / "METADATA/REALITY/TABLE.EXML"
    staged_file.write_text("changed", encoding="utf-8")
    with pytest.raises(InvestigationError, match="content changed"):
        staging.unstage(run_id, apply=True)
    staged_file.write_text(
        (root / "METADATA/REALITY/TABLE.EXML").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = staging.unstage(run_id, apply=True)
    assert result["removed"]
    assert not Path(applied["destination"]).exists()


def test_mod_analysis_rejects_missing_file_reference(tmp_path: Path) -> None:
    root = tmp_path / "referencing-mod"
    patch = root / "METADATA/TEST.EXML"
    patch.parent.mkdir(parents=True)
    patch.write_text(
        '<Data template="c"><Property name="Filename" value="TEXTURES/MISSING.DDS" /></Data>',
        encoding="utf-8",
    )
    result = analyze_mod(root, tmp_path / "reference-analysis", current_inventory=set())
    assert result["static_outcome"] == "failed"
    assert result["findings"][0]["code"] == "missing_resource_reference"


def test_runtime_evidence_collection_is_hash_backed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = mod_tree(tmp_path)
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    (game / "GAMEDATA/FullLog.txt").write_text("loaded", encoding="utf-8")
    (game / "Binaries/SETTINGS").mkdir(parents=True)
    (game / "Binaries/SETTINGS/GCMODSETTINGS.MXML").write_text(
        '<Data template="cGcModSettingsInfo" />', encoding="utf-8"
    )
    stages = tmp_path / "stage-state"
    runs = tmp_path / "runs"
    run_id = "20260911T120000Z-stage-1234abcd"
    run = runs / run_id
    run.mkdir(parents=True)
    (run / "request.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(staging, "STAGES_ROOT", stages)
    monkeypatch.setattr(staging, "running_processes", lambda: [])
    monkeypatch.setattr("squinch_nms_investigate.runs.RUNS_ROOT", runs)
    staging.stage(root, game, run_id, apply=True)
    result = staging.collect_evidence(run_id, [])
    assert len(result["files"]) == 2
    assert all(len(record["sha256"]) == 64 for record in result["files"])
    assert Path(result["artifact_path"], "collection.json").is_file()


def test_stage_refuses_running_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = mod_tree(tmp_path)
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    monkeypatch.setattr(staging, "STAGES_ROOT", tmp_path / "state")
    monkeypatch.setattr(staging, "running_processes", lambda: [{"pid": 42}])
    with pytest.raises(InvestigationError, match="while NMS.exe is running"):
        staging.stage(root, game, "20260911T120000Z-stage-1234abcd", apply=True)


def test_stage_rejects_symlinked_mod_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = mod_tree(tmp_path)
    (root / "linked.EXML").symlink_to(root / "METADATA/REALITY/TABLE.EXML")
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    monkeypatch.setattr(staging, "STAGES_ROOT", tmp_path / "state")
    monkeypatch.setattr(staging, "running_processes", lambda: [])
    with pytest.raises(InvestigationError, match="symbolic link"):
        staging.stage(root, game, "20260911T120000Z-stage-1234abcd", apply=True)


def test_stage_rejects_symlinked_game_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = mod_tree(tmp_path)
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    external = tmp_path / "external-mods"
    external.mkdir()
    (game / "GAMEDATA/MODS").symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(staging, "STAGES_ROOT", tmp_path / "state")
    monkeypatch.setattr(staging, "running_processes", lambda: [])
    with pytest.raises(InvestigationError, match="symbolic-link ancestor"):
        staging.stage(root, game, "20260911T120000Z-stage-1234abcd", apply=True)


def test_stage_rename_failure_removes_pending_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = mod_tree(tmp_path)
    game = tmp_path / "game"
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    stages = tmp_path / "state"
    run_id = "20260911T120000Z-stage-1234abcd"
    monkeypatch.setattr(staging, "STAGES_ROOT", stages)
    monkeypatch.setattr(staging, "running_processes", lambda: [])
    original_replace = Path.replace

    def fail_payload_replace(path: Path, target: Path) -> Path:
        if path.name == run_id:
            raise OSError("simulated rename failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_payload_replace)
    with pytest.raises(OSError, match="simulated rename failure"):
        staging.stage(root, game, run_id, apply=True)
    assert not (stages / f"{run_id}.json").exists()
    assert not (game / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}").exists()


def test_unstage_removes_interrupted_pending_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stages = tmp_path / "state"
    run_id = "20260911T120000Z-stage-1234abcd"
    game = tmp_path / "game"
    destination = game / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    pending = game / ".squinch-investigation-staging" / run_id
    stages.mkdir()
    pending.mkdir(parents=True)
    (stages / f"{run_id}.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": run_id,
                "game_root": str(game),
                "destination": str(destination),
                "pending_destination": str(pending),
                "files": {"metadata/incomplete.exml": "0" * 64},
                "state": "preparing",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(staging, "STAGES_ROOT", stages)
    result = staging.unstage(run_id, apply=True)
    assert result["removed_manifest"]
    assert not (stages / f"{run_id}.json").exists()
    assert not pending.exists()


def test_unstage_refuses_changed_pending_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stages = tmp_path / "state"
    run_id = "20260911T120000Z-stage-1234abcd"
    game = tmp_path / "game"
    destination = game / "GAMEDATA/MODS" / f"SQUINCH_INVESTIGATION_{run_id}"
    pending = game / ".squinch-investigation-staging" / run_id
    stages.mkdir()
    pending.mkdir(parents=True)
    (pending / "unexpected.exml").write_text("changed", encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "run_id": run_id,
        "game_root": str(game),
        "destination": str(destination),
        "pending_destination": str(pending),
        "files": {},
        "state": "preparing",
    }
    (stages / f"{run_id}.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(staging, "STAGES_ROOT", stages)
    with pytest.raises(InvestigationError, match="content changed"):
        staging.unstage(run_id, apply=True)
    assert pending.exists()
    assert (stages / f"{run_id}.json").exists()
