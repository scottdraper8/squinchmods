from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from conftest import write_save_pair

from squinch_nms_save.codec import RawNumber, decode_file
from squinch_nms_save.inventory_edit import create_inventory_edit_patches
from squinch_nms_save.jsonops import apply_patch


def _inventory(slots: list[dict], *, technology: bool = False) -> dict:
    return {
        "Slots": slots,
        "ValidSlotIndices": [
            {"X": 0, "Y": 0},
            {"X": 1, "Y": 0},
            {"X": 0, "Y": 1},
            {"X": 1, "Y": 1},
        ],
        "Width": 2,
        "Height": 2,
        "SpecialSlots": ([{"Type": "Tech"}] * 4) if technology else [],
    }


def _slot(identifier: str, amount: int, maximum: int, x: int, y: int, kind: str) -> dict:
    return {
        "Type": {"InventoryType": kind},
        "Id": identifier,
        "Amount": amount,
        "MaxAmount": maximum,
        "DamageFactor": RawNumber("0.0"),
        "FullyInstalled": True,
        "AddedAutomatically": False,
        "Index": {"X": x, "Y": y},
    }


def _document() -> dict:
    return {
        "F2P": 4746,
        "CommonStateData": {"SaveName": "Dev Testing"},
        "BaseContext": {
            "PlayerStateData": {
                "DifficultyState": {
                    "Settings": {
                        "InventoryStackLimits": {"InventoryStackLimitsDifficulty": "Restricted"}
                    }
                },
                "Inventory": _inventory(
                    [
                        _slot("^OLD_PRODUCT", 5, 5, 0, 0, "Product"),
                        _slot("^OLD_RESOURCE", 250, 250, 1, 0, "Substance"),
                    ]
                ),
                "Inventory_TechOnly": _inventory(
                    [_slot("^KNOWN_TECH", 100, 100, 0, 0, "Technology")], technology=True
                ),
                "FreighterInventory_TechOnly": _inventory(
                    [_slot("^NEW_TECH", 40, 100, 0, 0, "Technology")], technology=True
                ),
            }
        },
    }


def test_inventory_fill_uses_saved_restricted_stack_units_and_preserves_technology(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/fill"

    create_inventory_edit_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        inventory_selector="exosuit",
        definitions=["^GIFT:Product:1", "^RESOURCE:Substance:1"],
        add_items=[],
        remove_items=[],
        set_items=[],
        fill_items=["^GIFT", "^RESOURCE"],
        install_technology=[],
        expected_save_name="Dev Testing",
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    slots = player["Inventory"]["Slots"]
    assert Counter((row["Id"], row["Amount"], row["MaxAmount"]) for row in slots) == {
        ("^GIFT", 5, 5): 2,
        ("^RESOURCE", 250, 250): 2,
    }
    assert (
        player["Inventory_TechOnly"]
        == document["BaseContext"]["PlayerStateData"]["Inventory_TechOnly"]
    )


def test_quantity_edits_and_technology_install_use_open_valid_slots(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/edit"

    create_inventory_edit_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        inventory_selector="exosuit",
        definitions=["^NEW:Product:1"],
        add_items=["^NEW:7"],
        remove_items=["^OLD_RESOURCE:100"],
        set_items=[],
        fill_items=[],
        install_technology=["^NEW_TECH"],
        expected_save_name="Dev Testing",
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    general = player["Inventory"]["Slots"]
    assert sum(row["Amount"] for row in general if row["Id"] == "^NEW") == 7
    assert next(row for row in general if row["Id"] == "^OLD_RESOURCE")["Amount"] == 150
    installed = next(
        row for row in player["Inventory_TechOnly"]["Slots"] if row["Id"] == "^NEW_TECH"
    )
    assert installed["Amount"] == 100
    assert installed["Index"] == {"X": 1, "Y": 0}
