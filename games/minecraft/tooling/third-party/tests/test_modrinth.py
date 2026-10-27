import hashlib
import json
import zipfile

import pytest
from squinch_minecraft_third_party import modrinth
from squinch_minecraft_third_party.catalog import CatalogArtifact
from squinch_minecraft_third_party.errors import AcquisitionError


def artifact(artifact_id: str, version_id: str, version_number: str) -> CatalogArtifact:
    return CatalogArtifact(
        id=artifact_id,
        project_slug="example",
        project_id="project",
        minecraft_version="1.21.1",
        loader="fabric",
        version_number=version_number,
        version_id=version_id,
        filename=f"{artifact_id}.jar",
        sha256="0" * 64,
        status="diagnostic-only",
        reason="test",
        required_dependencies=(),
        source_id="source",
    )


def test_audit_latest_catalog_marks_current_and_control_pins(monkeypatch) -> None:
    monkeypatch.setattr(
        modrinth,
        "_versions",
        lambda *_args, **_kwargs: [
            {
                "id": "latest-id",
                "version_number": "2.0",
                "version_type": "release",
                "date_published": "2026-01-01T00:00:00Z",
            }
        ],
    )

    result = modrinth.audit_latest_catalog(
        [
            artifact("latest", "latest-id", "2.0"),
            artifact("control", "old-id", "1.0"),
        ]
    )

    pins = {value["artifact_id"]: value for value in result["groups"][0]["pins"]}
    assert pins["latest"]["is_latest"] is True
    assert pins["control"]["is_latest"] is False
    assert result["groups"][0]["channel_policy"] == "release"


def test_release_selection_keeps_mod_and_datapack_formats_separate():
    jar = {"filename": "content.jar", "primary": True}
    pack = {"filename": "content.zip", "primary": False}
    version = {"id": "test", "files": [jar, pack]}
    assert modrinth._release_files(version, "fabric") == [jar]
    assert modrinth._release_files(version, "datapack") == [pack]
    with pytest.raises(AcquisitionError, match="no .zip file"):
        modrinth._release_files({"files": [jar]}, "datapack")


@pytest.mark.parametrize(
    "metadata,resources,valid",
    [
        (
            '{"pack":{"pack_format":128,"description":"legacy format"}}',
            [("data/example/worldgen/biome/example.json", "{}")],
            True,
        ),
        (
            '{"pack":{"pack_format":42,"supported_formats":{"min_inclusive":40,"max_inclusive":45},"description":{"text":"legacy range"}}}',
            [("data/example/loot_tables/example.json", "{}")],
            True,
        ),
        (
            '{"pack":{"pack_format":42,"supported_formats":[40,45],"description":"legacy array range"}}',
            [("data/example/loot_tables/example.json", "{}")],
            True,
        ),
        (
            '{"pack":{"pack_format":42,"supported_formats":42,"description":"legacy single format"}}',
            [("data/example/loot_tables/example.json", "{}")],
            True,
        ),
        (
            '{"pack":{"min_format":[100,1],"max_format":[101,0],"description":[{"text":"new format"}]}}',
            [("data/example/function/load.mcfunction", "say ready")],
            True,
        ),
        ('{"pack":{}}', [("data/example/worldgen/biome/example.json", "{}")], False),
        (
            '{"pack":{"pack_format":128,"description":"   "}}',
            [("data/example/worldgen/biome/example.json", "{}")],
            False,
        ),
        (
            '{"pack":{"pack_format":128}}',
            [("data/example/worldgen/biome/example.json", "{}")],
            False,
        ),
        (
            '{"pack":{"min_format":[100,1],"description":"partial range"}}',
            [("data/example/worldgen/biome/example.json", "{}")],
            False,
        ),
        (
            '{"pack":{"pack_format":128,"description":"test"}}',
            [("data/", "")],
            False,
        ),
        (
            '{"pack":{"pack_format":128,"description":"test"}}',
            [("data/Example/worldgen/biome/example.json", "{}")],
            False,
        ),
        (
            '{"pack":{"pack_format":128,"description":"test"}}',
            [("data/example/example.json", "{}")],
            False,
        ),
        ("broken json", [("data/example/worldgen/biome/example.json", "{}")], False),
    ],
)
def test_datapack_requires_meaningful_metadata_and_namespaced_resources(
    tmp_path, metadata, resources, valid
):
    archive_path = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("pack.mcmeta", metadata)
        for name, contents in resources:
            archive.writestr(name, contents)
    assert modrinth._supports_loader(archive_path, "datapack") is valid
    assert not modrinth._supports_loader(archive_path, "fabric")


def test_acquire_datapack_preserves_release_bytes_and_manifest(tmp_path, monkeypatch):
    source = tmp_path / "official.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "pack.mcmeta",
            '{"pack":{"min_format":88,"max_format":90,"description":"official"}}',
        )
        archive.writestr("data/example/loot_tables/test.json", "{}")
    contents = source.read_bytes()
    version = {
        "id": "release-id",
        "version_number": "1.0",
        "dependencies": [],
        "files": [
            {
                "filename": "official.zip",
                "url": "https://example.invalid/file",
                "hashes": {"sha512": hashlib.sha512(contents).hexdigest()},
            }
        ],
    }
    monkeypatch.setattr(
        modrinth, "project", lambda _: {"id": "project", "slug": "example"}
    )
    monkeypatch.setattr(modrinth, "_versions", lambda *a, **kw: [version])
    monkeypatch.setattr(
        modrinth,
        "_download",
        lambda url, destination: destination.write_bytes(contents),
    )
    release = modrinth.acquire_release(
        "example",
        "1.21.1",
        "datapack",
        version_id="release-id",
        pinned_sha256=hashlib.sha256(contents).hexdigest(),
        destination_root=tmp_path / "cache",
    )
    assert release.path.read_bytes() == contents
    manifest = json.loads((release.path.parent / "acquisition.json").read_text())
    assert manifest["requested"]["loader"] == "datapack"
    assert manifest["selected_file"]["filename"] == "official.zip"
    version["files"][0]["hashes"]["sha512"] = "0" * 128
    with pytest.raises(AcquisitionError, match="SHA-512 mismatch"):
        modrinth.acquire_release(
            "example",
            "1.21.1",
            "datapack",
            version_id="release-id",
            destination_root=tmp_path / "cache",
        )


def test_acquire_release_rejects_platform_independent_path_traversal(
    tmp_path, monkeypatch
):
    contents = b"unused archive bytes"
    version = {
        "id": "release-id",
        "version_number": "1.0",
        "dependencies": [],
        "files": [
            {
                "filename": "..\\outside.zip",
                "url": "https://example.invalid/file",
                "hashes": {},
            }
        ],
    }
    monkeypatch.setattr(
        modrinth, "project", lambda _: {"id": "project", "slug": "example"}
    )
    monkeypatch.setattr(modrinth, "_versions", lambda *a, **kw: [version])
    monkeypatch.setattr(
        modrinth,
        "_download",
        lambda _url, destination: destination.write_bytes(contents),
    )

    with pytest.raises(AcquisitionError, match="Unsafe release filename"):
        modrinth.acquire_release(
            "example",
            "1.21.1",
            "datapack",
            version_id="release-id",
            destination_root=tmp_path / "cache",
        )
