from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from squinch_nms_third_party import nexus
from squinch_nms_third_party.archive import inspect_archive
from squinch_nms_third_party.catalog import CatalogArtifact
from squinch_nms_third_party.errors import AcquisitionError
from squinch_nms_third_party.nexus import (
    _public_url,
    artifact_freshness,
    import_archive,
)


def artifact() -> CatalogArtifact:
    return CatalogArtifact(
        id="test-artifact",
        game_domain="nomanssky",
        mod_id=42,
        mod_name="Example",
        mod_slug="example",
        file_id=99,
        file_display_name="Example Main",
        file_name="",
        file_version="1.0",
        nms_version="6.45",
        uploaded_at="2026-01-01T00:00:00Z",
        category="MAIN",
        sha256="",
        status="pending-authentication",
        reason="test",
        distribution="nexus-only",
        source_url="https://example.invalid",
        compatibility_claim="test",
    )


def test_manual_import_and_safe_inspection(tmp_path: Path) -> None:
    source = tmp_path / "download/example.zip"
    source.parent.mkdir()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("Example/METADATA/REALITY/TABLE.EXML", "<Data />")
        archive.writestr("Example/README.txt", "notes")

    acquired = import_archive(artifact(), source, destination_root=tmp_path / "cache")
    archive = Path(acquired["path"])
    assert archive.is_file()
    assert acquired["catalog_pin_required"] is True
    manifest = json.loads(
        (archive.parent / "acquisition.json").read_text(encoding="utf-8")
    )
    assert manifest["acquisition_method"] == "manual-browser-import"

    report = inspect_archive(
        artifact(), archive, reference_root=tmp_path / "reference/sources"
    )
    assert report["runtime_file_count"] == 1
    assert report["authoring_or_documentation_file_count"] == 1
    assert report["candidate_deployment_roots"] == ["Example"]
    assert Path(report["report"]).is_file()

    acquired_again = import_archive(
        artifact(), source, destination_root=tmp_path / "cache"
    )
    report_again = inspect_archive(
        artifact(), archive, reference_root=tmp_path / "reference/sources"
    )
    assert acquired_again["sha256"] == acquired["sha256"]
    assert report_again["archive_sha256"] == report["archive_sha256"]
    assert report_again["inspection_root"] == report["inspection_root"]


def test_inspection_rejects_parent_traversal(tmp_path: Path) -> None:
    source = tmp_path / "malicious.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("../escape.EXML", "bad")
    with pytest.raises(AcquisitionError, match="unsafe path"):
        inspect_archive(
            artifact(), source, reference_root=tmp_path / "reference/sources"
        )


def test_archive_root_is_the_deployment_root_when_metadata_is_top_level(
    tmp_path: Path,
) -> None:
    source = tmp_path / "root-layout.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("METADATA/REALITY/TABLE.EXML", "<Data />")
    report = inspect_archive(
        artifact(), source, reference_root=tmp_path / "reference/sources"
    )
    assert report["candidate_deployment_roots"] == ["."]


def test_short_lived_download_parameters_are_redacted() -> None:
    assert (
        _public_url("https://api.nexusmods.com/path?key=secret&expires=123")
        == "https://api.nexusmods.com/path"
    )


def test_freshness_uses_newest_visible_main_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nexus,
        "files_metadata",
        lambda _artifact: [
            {
                "file_id": 99,
                "category_name": "MAIN",
                "uploaded_timestamp": 100,
            },
            {
                "file_id": 100,
                "category_name": "OPTIONAL",
                "uploaded_timestamp": 300,
            },
            {
                "file_id": 101,
                "category_name": "MAIN",
                "uploaded_timestamp": 200,
            },
        ],
    )
    result = artifact_freshness(artifact())
    assert not result["fresh"]
    assert result["latest_eligible"]["file_id"] == 101
    assert result["release_channel_policy"] == "newest visible non-deleted MAIN file"


def test_freshness_rejects_missing_catalog_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nexus,
        "files_metadata",
        lambda _artifact: [{"file_id": 101, "category_name": "MAIN"}],
    )
    with pytest.raises(AcquisitionError, match="is not visible"):
        artifact_freshness(artifact())


def test_freshness_requires_a_main_release_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        nexus,
        "files_metadata",
        lambda _artifact: [{"file_id": 99, "category_name": "OPTIONAL"}],
    )
    with pytest.raises(AcquisitionError, match="no MAIN-channel"):
        artifact_freshness(artifact())
