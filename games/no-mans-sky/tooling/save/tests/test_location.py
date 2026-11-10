from __future__ import annotations

import copy
import json
from pathlib import Path

from conftest import write_save_pair

from squinch_nms_save.codec import RawNumber, decode_file
from squinch_nms_save.jsonops import apply_patch
from squinch_nms_save.location import create_location_rehome_patches


def _address(reality: int) -> dict:
    return {
        "RealityIndex": reality,
        "GalacticAddress": {
            "VoxelX": -12,
            "VoxelY": 34,
            "VoxelZ": 56,
            "SolarSystemIndex": 78,
            "PlanetIndex": 4,
        },
    }


def test_location_rehome_changes_only_out_of_range_reality_indices(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = {
        "F2P": 4746,
        "CommonStateData": {"SaveName": "Galaxies 51-100"},
        "BaseContext": {
            "PlayerStateData": {
                "UniverseAddress": _address(0),
                "PreviousUniverseAddress": _address(58),
                "FreighterUniverseAddress": _address(255),
            }
        },
    }
    write_save_pair(profile, name="save.hg", document=copy.deepcopy(document))
    write_save_pair(profile, name="save2.hg", document=copy.deepcopy(document))
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/locations"

    create_location_rehome_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        locations=[],
        policy_path=None,
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    assert player["UniverseAddress"]["RealityIndex"] == 50
    assert player["PreviousUniverseAddress"]["RealityIndex"] == 58
    assert player["FreighterUniverseAddress"]["RealityIndex"] == 50
    assert (
        player["UniverseAddress"]["GalacticAddress"]
        == document["BaseContext"]["PlayerStateData"]["UniverseAddress"]["GalacticAddress"]
    )
