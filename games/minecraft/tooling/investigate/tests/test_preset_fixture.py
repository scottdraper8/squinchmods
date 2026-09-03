from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_minecraft_investigate.cli import parser
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.fixtures import RTF_PRESET_PATH
from squinch_minecraft_investigate.preset_fixture import _inspect_generated_fixture


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_generated_fixture_requires_complete_derived_registry_boundary(tmp_path: Path) -> None:
    preset = {
        "world": {"properties": {"worldHeight": 1024, "worldDepth": 64, "seaLevel": 63}},
        "caves": {"largeOreVeins": True},
    }
    canonical = tmp_path.with_name(f"{tmp_path.name}-canonical-preset.json")
    _write_json(canonical, preset)
    _write_json(tmp_path / RTF_PRESET_PATH, preset)
    _write_json(tmp_path / "pack.mcmeta", {"pack": {"pack_format": 48}})
    _write_json(
        tmp_path / "data/minecraft/dimension_type/overworld.json",
        {"min_y": -64, "height": 1088, "logical_height": 1088},
    )
    _write_json(
        tmp_path / "data/minecraft/worldgen/noise_settings/overworld.json",
        {
            "noise": {
                "min_y": -64,
                "height": 1088,
                "size_horizontal": 1,
                "size_vertical": 2,
            },
            "sea_level": 63,
            "ore_veins_enabled": True,
        },
    )
    _write_json(
        tmp_path / "data/minecraft/worldgen/density_function/overworld/depth.json",
        {
            "type": "minecraft:add",
            "argument1": {
                "type": "minecraft:y_clamped_gradient",
                "from_y": -64,
                "to_y": 1024,
                "from_value": 1.5,
                "to_value": -7.0,
            },
        },
    )
    _write_json(tmp_path / "data/minecraft/worldgen/world_preset/normal.json", {})
    _write_json(
        tmp_path / "data/reterraforged/tags/worldgen/density_function/additional_noise_router_functions.json",
        {"values": []},
    )
    _write_json(tmp_path / "data/reterraforged/worldgen/configured_feature/test.json", {})
    _write_json(tmp_path / "data/reterraforged/worldgen/placed_feature/test.json", {})
    _write_json(tmp_path / "data/reterraforged/reterraforged/worldgen/noise/test.json", {})

    result = _inspect_generated_fixture(tmp_path, canonical)

    assert result["file_count"] == 10
    assert result["density_function_count"] == 1
    assert len(result["content_sha256"]) == 64

    (tmp_path / "data/minecraft/worldgen/noise_settings/overworld.json").unlink()
    with pytest.raises(InvestigationError, match="missing"):
        _inspect_generated_fixture(tmp_path, canonical)


def test_preset_fixture_cli_requires_explicit_project_and_preset() -> None:
    arguments = parser().parse_args([
        "preset-fixture",
        "--project", "worktree",
        "--preset", "fixture.toml",
        "--json",
    ])
    assert arguments.command == "preset-fixture"
    assert arguments.project == "worktree"
    assert arguments.preset == Path("fixture.toml")
