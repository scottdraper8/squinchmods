from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.cli import main
from squinch_nms_save.codec import RawNumber, decode_file
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.jsonops import apply_patch
from squinch_nms_save.location import _system_address, create_location_rehome_patches


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


@pytest.mark.parametrize(
    ("active", "option", "value"),
    [
        ("Main", "--glyphs", "3100fefff002"),
        ("Season", "--coordinates", "0801:007D:07FE:0100"),
    ],
)
def test_transport_stages_and_applies_only_the_active_location(
    tmp_path, tranche, monkeypatch, capsys, active, option, value
):
    # Include obfuscated keys so the emitted patch is exercised on the actual wire shape.
    mapping = tranche / "mapping.json"
    keys = {"ActiveContext": "XTp", "BaseContext": "BC", "GalacticAddress": "GA"}
    mapping.write_text(
        json.dumps(
            {
                "libMBIN_version": "7.14.0.1",
                "Mapping": [{"Key": raw, "Value": name} for name, raw in keys.items()],
            }
        )
    )
    before = _address(7)
    before["GA"] = before.pop("GalacticAddress")
    context = {
        "PlayerStateData": {
            "UniverseAddress": before,
            "HomeRealityIteration": 5,
            "PreviousUniverseAddress": copy.deepcopy(before),
        },
        "SpawnStateData": {
            "LastKnownPlayerState": "InStation",
            "ShipPositionInSystem": [1, 2, 3, 1],
        },
    }
    document = {"F2P": 4746, "XTp": active, "BC": context, "ExpeditionContext": context}
    save, meta = write_save_pair(tmp_path / "profile", document=document)
    original = save.read_bytes(), meta.read_bytes()
    assert (
        main(["transport", str(save), "--mapping", str(mapping), "--galaxy", "256", option, value])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "staged"
    stage = Path(result["data"]["stage"])
    assert (save.read_bytes(), meta.read_bytes()) == original
    assert main(["verify-stage", str(stage)]) == 0
    monkeypatch.setattr("squinch_nms_save.stage._nms_processes", lambda: [])
    assert main(["apply", str(stage), "--apply"]) == 0
    expected = copy.deepcopy(document)
    key = "BC" if active == "Main" else "ExpeditionContext"
    # The two fixture contexts started with the same contents.
    expected[key] = copy.deepcopy(context)
    expected[key]["PlayerStateData"]["UniverseAddress"] = {
        "RealityIndex": 255,
        "GA": {"VoxelX": 2, "VoxelY": -2, "VoxelZ": -1, "SolarSystemIndex": 256, "PlanetIndex": 0},
    }
    expected[key]["SpawnStateData"]["LastKnownPlayerState"] = "InShip"
    assert decode_file(save).document == expected


@pytest.mark.parametrize(
    ("galaxy", "glyphs", "coordinates"),
    [
        (0, "000000000000", None),
        (257, "000000000000", None),
        (1, "0000GG000000", None),
        (1, "0000000000800", None),
        (1, "000080000000", None),
        (1, None, "0FFF:0000:0000:0000"),
        (1, None, "0000:00FF:0000:0000"),
        (1, None, "0000:0000:0000:1000"),
    ],
)
def test_transport_rejects_unrepresentable_destinations(galaxy, glyphs, coordinates):
    with pytest.raises(SaveToolError):
        _system_address(galaxy, glyphs=glyphs, coordinates=coordinates)


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
