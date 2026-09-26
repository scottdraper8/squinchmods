from __future__ import annotations

from pathlib import Path

import pytest

from squinch_minecraft_investigate import probe_overlay
from squinch_minecraft_investigate.errors import InvestigationError


def _pack(root: Path, *, source: str = "src/main/java", resource: str = "src/main/resources") -> None:
    (root / source).mkdir(parents=True, exist_ok=True)
    (root / resource).mkdir(parents=True, exist_ok=True)
    (root / "probe-pack.toml").write_text(
        "\n".join(
            (
                "schema_version = 1",
                'id = "squinch:test-pack"',
                'version = "1"',
                f'sources = ["{source}"]',
                f'resources = ["{resource}"]',
                "mixins = []",
            )
        )
        + "\n"
    )


def test_probe_pack_fingerprint_changes_with_source_or_resource(tmp_path: Path) -> None:
    """Catches provenance that records a pack manifest but misses the injected implementation."""
    root = tmp_path / "pack"
    _pack(root)
    source = root / "src/main/java/Probe.java"
    resource = root / "src/main/resources/service.txt"
    source.write_text("class Probe {}\n")
    resource.write_text("provider.One\n")

    first = probe_overlay._probe_pack_details(root)
    source.write_text("class Probe { int version = 2; }\n")
    second = probe_overlay._probe_pack_details(root)
    resource.write_text("provider.Two\n")
    third = probe_overlay._probe_pack_details(root)

    assert first["content_sha256"] != second["content_sha256"]
    assert second["content_sha256"] != third["content_sha256"]
    assert [item["path"] for item in third["inputs"]] == [
        "src/main/java/Probe.java",
        "src/main/resources/service.txt",
    ]


def test_probe_pack_required_source_paths_returned(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    _pack(root)
    (root / "probe-pack.toml").write_text(
        'schema_version = 1\nid = "test"\nversion = "1"\n'
        'sources = ["src/main/java"]\nresources = ["src/main/resources"]\nmixins = []\n'
        'required_source_paths = ["common/src/main/java/some/package"]\n'
    )
    details = probe_overlay._probe_pack_details(root)
    assert details["required_source_paths"] == ["common/src/main/java/some/package"]


def test_probe_pack_required_source_paths_defaults_to_empty(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    _pack(root)
    details = probe_overlay._probe_pack_details(root)
    assert details["required_source_paths"] == []


def test_validate_required_source_paths_rejects_missing_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    packs = [{"id": "test-pack", "required_source_paths": ["common/src/missing/package"]}]
    with pytest.raises(InvestigationError, match="does not exist"):
        probe_overlay._validate_required_source_paths(project, packs)


def test_validate_required_source_paths_passes_when_directory_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "common/src/existing/package").mkdir(parents=True)
    packs = [{"id": "test-pack", "required_source_paths": ["common/src/existing/package"]}]
    probe_overlay._validate_required_source_paths(project, packs)


def test_probe_pack_rejects_input_directory_outside_its_root(tmp_path: Path) -> None:
    """Catches a pack manifest smuggling unrelated host files into the overlay and provenance."""
    root = tmp_path / "pack"
    outside = tmp_path / "outside"
    outside.mkdir()
    _pack(root, source="../outside")

    with pytest.raises(InvestigationError, match="escapes its root"):
        probe_overlay._probe_pack_details(root)
