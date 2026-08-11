from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from squinch_minecraft_investigate import catalog
from squinch_minecraft_investigate.errors import InvestigationError


def test_catalog_resolution_verifies_manifest_and_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog_path = tmp_path / "artifacts.toml"
    catalog_path.write_text(
        '''schema_version = 1
catalog_version = 1

[[artifacts]]
id = "example"
project_slug = "example-mod"
project_id = "project-id"
minecraft_version = "1.21.1"
loader = "fabric"
version_number = "1.0.0"
version_id = "version-id"
filename = "example.jar"
sha256 = "{sha256}"
status = "approved"
reason = "test"
required_dependencies = []
source_id = "source-example"
'''.format(sha256=hashlib.sha256(b"jar").hexdigest()),
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog, "CATALOG_PATH", catalog_path)
    monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path / "cache"))
    artifact_dir = tmp_path / "cache" / "third-party" / "modrinth" / "1.21.1" / "fabric" / "example-mod" / "1.0.0"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "example.jar").write_bytes(b"jar")
    (artifact_dir / "acquisition.json").write_text(json.dumps({
        "project": {"slug": "example-mod", "id": "project-id"},
        "version": {"id": "version-id", "version_number": "1.0.0"},
        "requested": {"minecraft_version": "1.21.1", "loader": "fabric"},
        "selected_file": {"filename": "example.jar"},
        "sha256": hashlib.sha256(b"jar").hexdigest(),
    }), encoding="utf-8")

    resolved = catalog.resolve_artifacts(("example",), expected_loader="fabric")

    assert resolved[0].id == "example"
    assert resolved[0].path == artifact_dir / "example.jar"


def test_catalog_resolution_rejects_tampered_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog_path = tmp_path / "artifacts.toml"
    catalog_path.write_text(
        '''schema_version = 1
[[artifacts]]
id = "example"
project_slug = "example-mod"
project_id = "project-id"
minecraft_version = "1.21.1"
loader = "fabric"
version_number = "1.0.0"
version_id = "version-id"
filename = "example.jar"
sha256 = "{sha256}"
status = "approved"
reason = "test"
required_dependencies = []
source_id = "source-example"
'''.format(sha256="0" * 64),
        encoding="utf-8",
    )
    monkeypatch.setattr(catalog, "CATALOG_PATH", catalog_path)
    monkeypatch.setenv("SQINCHMODS_CACHE_HOME", str(tmp_path / "cache"))
    artifact_dir = tmp_path / "cache" / "third-party" / "modrinth" / "1.21.1" / "fabric" / "example-mod" / "1.0.0"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "example.jar").write_bytes(b"tampered")

    with pytest.raises(InvestigationError, match="catalog artifact hash mismatch"):
        catalog.resolve_artifacts(("example",), expected_loader="fabric")
