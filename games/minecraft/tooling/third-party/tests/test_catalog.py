from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from squinch_minecraft_third_party.catalog import load_catalog, validate_catalog


class CatalogTests(unittest.TestCase):
    def test_duplicate_artifact_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifacts.toml"
            path.write_text(
                '''schema_version = 1
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
'''.format(hash="0" * 64), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "duplicate catalog artifact ID"):
                load_catalog(path)

    def test_committed_catalog_matches_the_cache(self) -> None:
        root = Path(__file__).parents[5]
        catalog = root / ".squinch/games/minecraft/third-party/artifacts.toml"
        cache = Path.home() / ".cache/squinchmods/third-party/modrinth"
        result = validate_catalog(catalog, cache_root=cache)
        self.assertGreater(len(result["artifacts"]), 0)


if __name__ == "__main__":
    unittest.main()
