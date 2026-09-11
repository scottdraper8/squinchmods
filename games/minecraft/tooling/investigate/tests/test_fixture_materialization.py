from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from squinch_minecraft_investigate.fixtures import (
    FTF_PRESET_PATH,
    archive_generated_fixture,
    load_fixture,
)
from squinch_minecraft_investigate.paths import REPOSITORY_ROOT

FIXTURES = REPOSITORY_ROOT / "games/minecraft/investigations/freeterraforged/fixtures"


def test_fixture_catalog_resolves_semantic_boundary_conditions() -> None:
    """Catches a compact preset selecting the wrong resolved FTF boundary input."""
    expected = {
        "vanilla-depth-maximum-ocean": (None, 117, False),
        "deep-world-ocean-stress": (624, 677, False),
        "shallow-depth-mountain-control": (16, None, False),
        "maximum-vertical-range-cave-decoration-stress": (1024, 900, False),
    }
    for relative, (world_depth, ocean_depth, archipelago) in expected.items():
        manifest = load_fixture(FIXTURES / relative / "fixture.toml")
        properties = manifest["resolved_preset"]["world"]["properties"]
        assert properties.get("worldDepth") == world_depth
        if ocean_depth is not None:
            assert properties["oceanDepth"] == ocean_depth
        assert manifest["resolved_preset"]["island"]["enableArchipelago"] is archipelago
        assert Path(manifest["preset_path"]).name == "preset.json"


def test_generated_archive_is_byte_deterministic_and_decodable(tmp_path: Path) -> None:
    """Catches timestamp/order-dependent output or an archive missing the real registry path."""
    source = tmp_path / "source"
    preset = source / FTF_PRESET_PATH
    preset.parent.mkdir(parents=True)
    preset.write_text("{}\n", encoding="utf-8")
    (source / "pack.mcmeta").write_text("{}\n", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_manifest = archive_generated_fixture(source, first)
    second_manifest = archive_generated_fixture(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest["archive_sha256"] == second_manifest["archive_sha256"]
    assert first_manifest["archive_sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        assert FTF_PRESET_PATH in archive.namelist()


def test_fixture_catalog_is_compact_and_hash_checked() -> None:
    metadata_paths = sorted(FIXTURES.rglob("fixture.toml"))

    assert len(metadata_paths) == 29
    for metadata in metadata_paths:
        manifest = load_fixture(metadata)
        assert metadata.parent.joinpath("preset.json").is_file()
        assert sorted(path.name for path in metadata.parent.iterdir()) == [
            "fixture.toml",
            "preset.json",
        ]
        assert manifest["schema_version"] == 2
        assert manifest["preset_sha256"] == manifest["resolved_preset_sha256"]
