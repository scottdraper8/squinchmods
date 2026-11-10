from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.codec import decode_file
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.meta import inspect_meta_file
from squinch_nms_save.slots import archive_slots, move_slot, swap_slots


def test_archive_slots_preserves_then_removes_complete_pairs(tmp_path: Path, tranche: Path) -> None:
    profile = tmp_path / "profile"
    paths = [
        *write_save_pair(profile, name="save9.hg"),
        *write_save_pair(profile, name="save10.hg"),
    ]
    archive = tranche / "outputs/slot-5"

    with pytest.raises(SaveToolError, match="explicit --apply"):
        archive_slots(profile, [5], archive, apply=False)
    result = archive_slots(profile, [5], archive, apply=True)

    assert result["files"] == 4
    assert all(not path.exists() for path in paths)
    manifest = json.loads((archive / "manifest.json").read_text())
    assert manifest["schema"] == "squinch-nms-save-slot-archive-v1"
    assert manifest["slots"] == [5]
    assert len(manifest["entries"]) == 2


def test_swap_slots_moves_both_snapshots_and_rekeys_metadata(tmp_path: Path, tranche: Path) -> None:
    profile = tmp_path / "profile"
    expected = {}
    for name, marker in (
        ("save11.hg", "slot-6-auto"),
        ("save12.hg", "slot-6-manual"),
        ("save13.hg", "slot-7-auto"),
        ("save14.hg", "slot-7-manual"),
    ):
        save, meta = write_save_pair(profile, name=name, document={"F2P": 4746, "marker": marker})
        expected[name] = (save.read_bytes(), meta.read_bytes())

    with pytest.raises(SaveToolError, match="explicit --apply"):
        swap_slots(profile, 6, 7, apply=False)
    result = swap_slots(profile, 6, 7, apply=True)

    assert result["swapped"] is True
    assert result["pairs"] == 4
    assert decode_file(profile / "save11.hg").document["marker"] == "slot-7-auto"
    assert decode_file(profile / "save12.hg").document["marker"] == "slot-7-manual"
    assert decode_file(profile / "save13.hg").document["marker"] == "slot-6-auto"
    assert decode_file(profile / "save14.hg").document["marker"] == "slot-6-manual"
    for name in expected:
        info = inspect_meta_file(profile / f"mf_{name}", profile / name)
        assert info.encrypted_slot == info.storage_slot

    backup = Path(result["backup"])
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["schema"] == "squinch-nms-save-slot-swap-v1"
    assert manifest["slots"] == [6, 7]
    assert len(manifest["entries"]) == 4
    for entry in manifest["entries"]:
        destination_name = Path(entry["destination_save"]).name
        original_save, original_meta = expected[destination_name]
        pair = backup / entry["backup_directory"]
        assert (pair / destination_name).read_bytes() == original_save
        assert (pair / f"mf_{destination_name}").read_bytes() == original_meta


def test_move_slot_rekeys_pairs_and_removes_source(tmp_path: Path, tranche: Path) -> None:
    profile = tmp_path / "profile"
    original = {}
    for name, marker in (("save7.hg", "auto"), ("save8.hg", "manual")):
        save, meta = write_save_pair(profile, name=name, document={"F2P": 4746, "marker": marker})
        original[name] = (save.read_bytes(), meta.read_bytes())

    with pytest.raises(SaveToolError, match="explicit --apply"):
        move_slot(profile, 4, 3, apply=False)
    result = move_slot(profile, 4, 3, apply=True)

    assert result["moved"] is True
    assert not (profile / "save7.hg").exists()
    assert not (profile / "mf_save7.hg").exists()
    assert not (profile / "save8.hg").exists()
    assert not (profile / "mf_save8.hg").exists()
    assert decode_file(profile / "save5.hg").document["marker"] == "auto"
    assert decode_file(profile / "save6.hg").document["marker"] == "manual"
    for name in ("save5.hg", "save6.hg"):
        info = inspect_meta_file(profile / f"mf_{name}", profile / name)
        assert info.encrypted_slot == info.storage_slot
    manifest = json.loads((Path(result["manifest"])).read_text())
    assert manifest["schema"] == "squinch-nms-save-slot-move-v1"
    assert manifest["source_slot"] == 4
    assert manifest["destination_slot"] == 3
    for entry in manifest["entries"]:
        source_name = Path(entry["source_save"]).name
        pair = Path(result["backup"]) / entry["backup_directory"]
        assert (pair / source_name).read_bytes() == original[source_name][0]
        assert (pair / f"mf_{source_name}").read_bytes() == original[source_name][1]
