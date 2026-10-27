from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.presets import (
    FTF_PRESET_PATH,
    archive_generated_datapack,
    load_preset,
)


def _write_preset_snapshot(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    preset_path = root / "preset.json"
    preset = {
        "world": {"properties": {"worldDepth": 624, "oceanDepth": 677}},
        "island": {"enableArchipelago": False},
    }
    preset_bytes = json.dumps(preset, sort_keys=True).encode()
    preset_path.write_bytes(preset_bytes)
    metadata_path = root / "preset.toml"
    metadata_path.write_text(
        "\n".join(
            [
                "schema_version = 2",
                'id = "temporary-test-preset"',
                'classification = "feature-specific"',
                'purpose = "Exercise preset snapshot validation."',
                'applicable_questions = ["Does the exporter accept the resolved input?"]',
                'known_limitations = ["Synthetic test data only."]',
                'minecraft_version = "1.21.1"',
                'ftf_version = "test"',
                'preset = "preset.json"',
                f'preset_sha256 = "{hashlib.sha256(preset_bytes).hexdigest()}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return metadata_path, preset_path


def test_preset_snapshot_resolves_explicit_settings_and_checks_hash(
    tmp_path: Path,
) -> None:
    metadata_path, preset_path = _write_preset_snapshot(tmp_path / "source")

    manifest = load_preset(metadata_path)

    properties = manifest["resolved_preset"]["world"]["properties"]
    assert properties == {"worldDepth": 624, "oceanDepth": 677}
    assert manifest["resolved_preset"]["island"]["enableArchipelago"] is False
    assert Path(manifest["preset_path"]) == preset_path
    assert manifest["preset_sha256"] == manifest["resolved_preset_sha256"]

    preset_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(InvestigationError, match="hash does not match"):
        load_preset(metadata_path)


def test_generated_datapack_archive_is_byte_deterministic_and_decodable(
    tmp_path: Path,
) -> None:
    """Catches timestamp/order-dependent output or a missing registry path."""
    source = tmp_path / "source"
    preset = source / FTF_PRESET_PATH
    preset.parent.mkdir(parents=True)
    preset.write_text("{}\n", encoding="utf-8")
    (source / "pack.mcmeta").write_text("{}\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_manifest = archive_generated_datapack(source, first)
    second_manifest = archive_generated_datapack(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest["archive_sha256"] == second_manifest["archive_sha256"]
    assert (
        first_manifest["archive_sha256"]
        == hashlib.sha256(first.read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(
            item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist()
        )
        assert FTF_PRESET_PATH in archive.namelist()


def test_datapack_overlay_is_in_exported_archive(tmp_path: Path) -> None:
    source = tmp_path / "source"
    preset = source / FTF_PRESET_PATH
    preset.parent.mkdir(parents=True)
    preset.write_text("{}\n", encoding="utf-8")
    overlay = tmp_path / "overlay"
    (overlay / "data/squinch/lithostitched/biome_injector").mkdir(parents=True)
    (overlay / "data/squinch/lithostitched/region").mkdir(parents=True)
    (
        overlay / "data/squinch/lithostitched/biome_injector/declarative_replace.json"
    ).write_text("{}\n", encoding="utf-8")
    (overlay / "data/squinch/lithostitched/region/declarative_region.json").write_text(
        "{}\n", encoding="utf-8"
    )
    output = tmp_path / "with-lithostitched.zip"

    manifest = archive_generated_datapack(source, output, overlay=overlay)

    assert len(manifest["overlay_files"]) == 2
    with zipfile.ZipFile(output) as archive:
        paths = archive.namelist()
        assert FTF_PRESET_PATH in paths
        assert (
            "data/squinch/lithostitched/biome_injector/declarative_replace.json"
            in paths
        )
        assert "data/squinch/lithostitched/region/declarative_region.json" in paths
