from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest
from squinch_minecraft_third_party.catalog import load_catalog
from squinch_minecraft_third_party.errors import AcquisitionError


@pytest.mark.parametrize(
    "loader,filename,valid",
    [
        ("datapack", "official.zip", True),
        ("fabric", "official.zip", False),
        ("datapack", "official.jar", False),
        ("datapack", "../official.zip", False),
    ],
)
def test_catalog_archive_format(tmp_path, loader, filename, valid):
    path = tmp_path / "catalog.toml"
    path.write_text(f'''schema_version = 1
[[artifacts]]
id = "pack"
project_slug = "example"
project_id = "project"
minecraft_version = "1.21.1"
loader = "{loader}"
version_number = "1"
version_id = "version"
filename = "{filename}"
sha256 = "{"0" * 64}"
status = "diagnostic-only"
reason = "test"
source_id = "source"
[[sources]]
id = "source"
status = "unavailable"
repository = ""
requested_ref = ""
resolved_commit = ""
minecraft_version = "1.21.1"
checkout = ""
shallow = false
blob_filter = false
sparse_paths = []
''')
    if valid:
        assert load_catalog(path)[0]["pack"].filename == filename
    else:
        with pytest.raises(AcquisitionError, match="invalid filename"):
            load_catalog(path)


class CatalogTests(unittest.TestCase):
    def test_duplicate_artifact_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifacts.toml"
            path.write_text(
                """schema_version = 1
[[artifacts]]
id = "same"
project_slug = "example"
project_id = "id"
minecraft_version = "1.21.1"
loader = "fabric"
version_number = "1.0"
version_id = "version"
filename = "example.jar"
sha256 = "{hash}"
status = "approved"
reason = "test"
required_dependencies = []
source_id = "source"
[[artifacts]]
id = "same"
project_slug = "other"
project_id = "other-id"
minecraft_version = "1.21.1"
loader = "fabric"
version_number = "1.0"
version_id = "other-version"
filename = "other.jar"
sha256 = "{hash}"
status = "approved"
reason = "test"
required_dependencies = []
source_id = "source"
[[sources]]
id = "source"
status = "unavailable"
""".format(hash="0" * 64),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Exception, "duplicate catalog artifact ID"):
                load_catalog(path)


if __name__ == "__main__":
    unittest.main()
