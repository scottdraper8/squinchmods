from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from squinch_minecraft_third_party.cleanup import remove_acquired
from squinch_minecraft_third_party.errors import AcquisitionError


class RemoveAcquiredTests(unittest.TestCase):
    def _populate(self, root: Path) -> Path:
        version_dir = root / "1.21.1" / "neoforge" / "example-mod" / "1.0.0"
        version_dir.mkdir(parents=True)
        (version_dir / "example-mod.jar").write_bytes(b"test")
        (version_dir / "acquisition.json").write_text(
            json.dumps({
                "project": {"slug": "example-mod"},
                "requested": {"minecraft_version": "1.21.1", "loader": "neoforge"},
            }),
            encoding="utf-8",
        )
        return version_dir

    def test_dry_run_then_apply_removes_validated_cache_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            version_dir = self._populate(root)
            source = Path(temporary) / "games/minecraft/reference/sources/1.21.1/mods/example-mod"
            source.mkdir(parents=True)
            (source / "source-acquisition.json").write_text("{}", encoding="utf-8")

            plan = remove_acquired(
                "example-mod", "1.21.1", "neoforge", version_number="1.0.0", source=source,
                destination_root=root,
            )
            self.assertFalse(plan["apply"])
            self.assertTrue(version_dir.exists())
            self.assertTrue(source.exists())

            result = remove_acquired(
                "example-mod", "1.21.1", "neoforge", version_number="1.0.0", source=source,
                destination_root=root, apply=True,
            )
            self.assertEqual(result["cache"]["removed"], [str(version_dir)])
            self.assertFalse(version_dir.exists())
            self.assertFalse(version_dir.parent.exists())
            self.assertFalse(source.exists())

    def test_mismatched_manifest_is_not_removable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "cache"
            version_dir = self._populate(root)
            manifest = json.loads((version_dir / "acquisition.json").read_text(encoding="utf-8"))
            manifest["project"]["slug"] = "different-mod"
            (version_dir / "acquisition.json").write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(AcquisitionError):
                remove_acquired(
                    "example-mod", "1.21.1", "neoforge", version_number="1.0.0",
                    destination_root=root, apply=True,
                )
            self.assertTrue(version_dir.exists())

    def test_source_must_be_under_reference_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(AcquisitionError):
                remove_acquired(
                    "example-mod", "1.21.1", "neoforge", source=Path(temporary) / "elsewhere",
                )


if __name__ == "__main__":
    unittest.main()
