from __future__ import annotations

import json
from pathlib import Path

import pytest
from squinch_nms_third_party.catalog import load_catalog, validate_catalog
from squinch_nms_third_party.errors import AcquisitionError


def catalog_text(
    *, status: str = "pending-authentication", filename: str = "", sha256: str = ""
) -> str:
    return f'''schema_version = 1
[[artifacts]]
id = "test-artifact"
game_domain = "nomanssky"
mod_id = 42
mod_name = "Example"
mod_slug = "example"
file_id = 99
file_display_name = "Example Main"
file_name = "{filename}"
file_version = "1.0"
nms_version = "6.45"
uploaded_at = "2026-01-01T00:00:00Z"
category = "MAIN"
sha256 = "{sha256}"
status = "{status}"
reason = "test"
distribution = "nexus-only"
source_url = "https://www.nexusmods.com/nomanssky/mods/42?file_id=99"
compatibility_claim = "test only"
'''


def test_pending_catalog_entry_can_be_bootstrapped(tmp_path: Path) -> None:
    catalog = tmp_path / "artifacts.toml"
    catalog.write_text(catalog_text(), encoding="utf-8")
    artifact = load_catalog(catalog)["test-artifact"]
    assert not artifact.pinned
    assert validate_catalog(catalog, cache_root=tmp_path / "cache")["artifacts"] == [
        {"id": "test-artifact", "status": "pending-authentication", "pinned": False}
    ]


def test_active_entry_requires_filename_and_hash(tmp_path: Path) -> None:
    catalog = tmp_path / "artifacts.toml"
    catalog.write_text(catalog_text(status="approved"), encoding="utf-8")
    with pytest.raises(AcquisitionError, match="must pin file_name and SHA-256"):
        load_catalog(catalog)


def test_active_cache_is_hash_and_manifest_verified(tmp_path: Path) -> None:
    archive_bytes = b"example archive"
    import hashlib

    digest = hashlib.sha256(archive_bytes).hexdigest()
    catalog = tmp_path / "artifacts.toml"
    catalog.write_text(
        catalog_text(status="approved", filename="example.zip", sha256=digest),
        encoding="utf-8",
    )
    directory = tmp_path / "cache/nomanssky/42/99"
    directory.mkdir(parents=True)
    (directory / "example.zip").write_bytes(archive_bytes)
    (directory / "acquisition.json").write_text(
        json.dumps(
            {
                "artifact_id": "test-artifact",
                "game_domain": "nomanssky",
                "mod_id": 42,
                "file_id": 99,
                "file_name": "example.zip",
                "sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    result = validate_catalog(catalog, cache_root=tmp_path / "cache")
    assert result["artifacts"][0]["sha256"] == digest
