from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.codec import decode_file
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.inventory import build_inventory
from squinch_nms_save.jsonops import apply_patch
from squinch_nms_save.projection import (
    approve_projection_plan,
    create_projection_plan,
    emit_projection_patches,
)


def _base(created: int, name: str, galaxy: int, updated: int) -> dict:
    return {
        "Owner": {"UID": "player", "TS": created},
        "BaseType": {"PersistentBaseTypes": "HomePlanetBase"},
        "Name": name,
        "GalacticAddress": ((galaxy - 1) << 32) | created,
        "Position": [created, 2, 3],
        "LastUpdateTimestamp": updated,
        "Objects": [],
    }


def _document(bases: list[dict]) -> dict:
    return {
        "Version": 4746,
        "ActiveContext": "Main",
        "CommonStateData": {"SaveName": "Galaxies 1-50"},
        "BaseContext": {
            "PlayerStateData": {
                "PersistentPlayerBases": bases,
                "ShipOwnership": [],
                "ArchivedShipOwnership": [],
                "Multitools": [],
                "ArchivedMultitools": [],
            }
        },
    }


def _mapping(path: Path) -> Path:
    names = [
        "BaseContext",
        "PlayerStateData",
        "PersistentPlayerBases",
        "ActiveContext",
        "CommonStateData",
        "SaveName",
        "Version",
    ]
    path.write_text(
        json.dumps(
            {
                "libMBIN_version": "7.14.0.1",
                "Mapping": [{"Key": name, "Value": name} for name in names],
            }
        )
    )
    return path


def test_projection_requires_review_and_emits_verified_patch(tmp_path: Path, tranche: Path) -> None:
    profile = tmp_path / "profile"
    newest_a = _base(100, "A newest", 1, 20)
    base_b = _base(101, "B", 2, 20)
    old_a = _base(100, "A old", 1, 10)
    wrong_c = _base(102, "C wrong galaxy", 51, 10)
    write_save_pair(profile, name="save.hg", document=_document([newest_a, base_b]))
    save2, _meta2 = write_save_pair(profile, name="save2.hg", document=_document([old_a, wrong_c]))
    inputs = tranche / "inputs"
    inputs.mkdir()
    mapping = _mapping(inputs / "mapping.json")
    inventory = tranche / "outputs/inventory"
    build_inventory(profile, mapping, inventory)
    plan_path = tranche / "outputs/plan.json"

    planned = create_projection_plan(
        inventory,
        mapping,
        plan_path,
        strategy="reconcile",
        snapshot_selection="all",
    )

    assert planned["remove"] == 1
    assert planned["update"] == 1
    assert planned["import"] == 1
    with pytest.raises(SaveToolError, match="not approved"):
        emit_projection_patches(plan_path, tranche / "outputs/patches")

    approved_path = tranche / "outputs/approved.json"
    with pytest.raises(SaveToolError, match="explicit --approve"):
        approve_projection_plan(plan_path, approved_path, approve=False)
    approve_projection_plan(plan_path, approved_path, approve=True)
    result, artifacts = emit_projection_patches(approved_path, tranche / "outputs/patches")

    assert result["patches"] == 2
    assert len(artifacts) == 3
    operations = json.loads((tranche / "outputs/patches/save2.hg.patch.json").read_text())
    patched = apply_patch(decode_file(save2, require_714=False).document, operations)
    bases = patched["BaseContext"]["PlayerStateData"]["PersistentPlayerBases"]
    assert [base["Name"] for base in bases] == ["A newest", "B"]
