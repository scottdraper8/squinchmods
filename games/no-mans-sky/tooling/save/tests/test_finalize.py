from __future__ import annotations

import json
from pathlib import Path

from conftest import write_save_pair

from squinch_nms_save.codec import decode_file
from squinch_nms_save.finalize import create_finalization_patches
from squinch_nms_save.jsonops import apply_patch
from squinch_nms_save.mapping import SaveMapping


def _address(galaxy: int, suffix: int) -> int:
    return ((galaxy - 1) << 32) | suffix


def _base(
    name: str,
    galaxy: int,
    created: int,
    *,
    base_type: str = "HomePlanetBase",
    owner: str = "player",
) -> dict:
    return {
        "Owner": {"UID": owner, "LID": owner, "TS": created},
        "BaseType": {"PersistentBaseTypes": base_type},
        "Name": name,
        "GalacticAddress": _address(galaxy, created),
        "Position": [1.0, 2.0, 3.0],
        "LastUpdateTimestamp": created,
        "Objects": [],
    }


def _settlement(name: str, galaxy: int, unique: str, *, owner: str = "player") -> dict:
    return {
        "Owner": {"UID": owner, "LID": owner},
        "Name": name,
        "UniqueId": unique,
        "UniverseAddress": _address(galaxy, 99),
        "DbTimestamp": 10,
    }


def _empty_settlement() -> dict:
    return {
        "Owner": {"UID": "", "LID": ""},
        "Name": "",
        "UniqueId": "",
        "UniverseAddress": 0,
        "DbTimestamp": 0,
    }


def _mapping(path: Path) -> SaveMapping:
    names = (
        "CommonStateData",
        "SaveName",
        "BaseContext",
        "PlayerStateData",
        "SettlementStatesV2",
        "PersistentPlayerBases",
        "TeleportEndpoints",
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "libMBIN_version": "7.14.0.1",
                "Mapping": [
                    {"Key": f"raw{index}", "Value": name} for index, name in enumerate(names)
                ],
            }
        )
    )
    return SaveMapping.load(path)


def test_finalize_routes_settlements_sorts_bases_and_clears_teleports(
    tmp_path: Path, tranche: Path
) -> None:
    mapping_path = tranche / "inputs/mapping.json"
    mapping = _mapping(mapping_path)
    cached_settlement = _settlement("Visitor", 25, "cached", owner="visitor")
    settlements = [
        _settlement("Old Settlement", 1, "owned-one"),
        cached_settlement,
        _settlement("Wrong Range", 59, "owned-other"),
    ]
    portable = _base("Freighter", 256, 30, base_type="FreighterBase")
    cached_base = _base("Cached", 25, 40, base_type="ExternalPlanetBase", owner="visitor")
    semantic = {
        "F2P": 4746,
        "CommonStateData": {"SaveName": "Galaxies 1-50"},
        "BaseContext": {
            "PlayerStateData": {
                "SettlementStatesV2": settlements,
                "PersistentPlayerBases": [
                    _base("10. Tenth", 10, 10),
                    _base("1.10 Later", 1, 11),
                    portable,
                    _base("1.2 Earlier", 1, 12),
                    cached_base,
                ],
                "TeleportEndpoints": [{"Name": "Old teleporter"}],
            }
        },
    }
    profile = tmp_path / "profile"
    save, _meta = write_save_pair(profile, document=mapping.obfuscate(semantic))
    write_save_pair(
        profile,
        name="save3.hg",
        document=mapping.obfuscate(
            {
                "F2P": 4746,
                "CommonStateData": {"SaveName": ""},
                "BaseContext": {"PlayerStateData": {"SettlementStatesV2": [_empty_settlement()]}},
            }
        ),
    )

    result, _artifacts = create_finalization_patches(
        profile, mapping_path, tranche / "outputs/finalize"
    )

    assert result == {
        "output_directory": str((tranche / "outputs/finalize").resolve()),
        "owner_id": "player",
        "settlements": 2,
        "targets": 1,
        "teleport_endpoints_removed": 1,
    }
    operations = json.loads((tranche / "outputs/finalize/save.hg.patch.json").read_text())
    raw = decode_file(save).document
    patched = mapping.deobfuscate(apply_patch(raw, operations))
    player = patched["BaseContext"]["PlayerStateData"]

    final_settlements = player["SettlementStatesV2"]
    assert len(final_settlements) == len(settlements)
    assert cached_settlement in final_settlements
    owned = [row for row in final_settlements if row["Owner"]["UID"] == "player"]
    assert [(row["UniqueId"], row["Name"]) for row in owned] == [("owned-one", "1. Old Settlement")]

    bases = player["PersistentPlayerBases"]
    assert [base["Name"] for base in bases] == [
        "1.1 Earlier",
        "1.2 Later",
        "10. Tenth",
        "Freighter",
        "Cached",
    ]
    assert bases[-2] == portable
    assert bases[-1] == cached_base
    assert player["TeleportEndpoints"] == []
