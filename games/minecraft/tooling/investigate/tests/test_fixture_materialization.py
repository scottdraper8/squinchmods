from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from squinch_minecraft_investigate.fixtures import (
    RTF_PRESET_PATH,
    load_fixture,
    materialize_fixture,
)
from squinch_minecraft_investigate.paths import REPOSITORY_ROOT

FIXTURES = REPOSITORY_ROOT / "games/minecraft/investigations/reterraforged/fixtures"


def test_fixture_catalog_resolves_semantic_boundary_conditions() -> None:
    """Catches an overlay or metadata path selecting the wrong resolved RTF boundary input."""
    expected = {
        "vanilla-depth-maximum-ocean": (None, 117, False),
        "deep-world-ocean-stress": (624, 677, False),
        "shallow-depth-mountain-control": (16, None, False),
        "maximum-vertical-range-cave-decoration-stress": (1024, 900, False),
        "archipelago/vanilla-depth-maximum-ocean": (None, 117, True),
        "archipelago/deep-world-ocean-stress": (624, 677, True),
        "archipelago/shallow-depth-mountain-control": (16, None, True),
    }
    for relative, (world_depth, ocean_depth, archipelago) in expected.items():
        manifest, files = load_fixture(FIXTURES / relative / "fixture.toml")
        properties = manifest["resolved_preset"]["world"]["properties"]
        assert properties.get("worldDepth") == world_depth
        if ocean_depth is not None:
            assert properties["oceanDepth"] == ocean_depth
        assert manifest["resolved_preset"]["island"]["enableArchipelago"] is archipelago
        assert RTF_PRESET_PATH in files
        assert manifest["source_file_count"] >= 193


def test_materialized_fixture_zip_is_byte_deterministic_and_decodable(tmp_path: Path) -> None:
    """Catches timestamp/order-dependent ZIP output or an archive missing the real registry path."""
    metadata = FIXTURES / "vanilla-depth-maximum-ocean/fixture.toml"
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_manifest = materialize_fixture(metadata, first)
    second_manifest = materialize_fixture(metadata, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest["archive_sha256"] == second_manifest["archive_sha256"]
    assert first_manifest["archive_sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        assert RTF_PRESET_PATH in archive.namelist()
        assert archive.read(RTF_PRESET_PATH).startswith(b"{\n")


def test_generated_fixture_catalog_has_complete_provenance() -> None:
    metadata_paths = sorted((FIXTURES / "generated").glob("*/fixture.toml"))

    assert len(metadata_paths) == 22
    for metadata in metadata_paths:
        manifest, files = load_fixture(metadata)
        assert manifest["historical_archive_sha256"] is None
        assert manifest["generator"]["file_count"] == len(files)
        assert manifest["generator"]["resolved_preset_sha256"] == manifest[
            "resolved_preset_sha256"
        ]
