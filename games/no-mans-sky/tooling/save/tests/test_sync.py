from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.codec import decode_file
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.jsonops import apply_patch
from squinch_nms_save.mapping import MAPPING_VERSION, SaveMapping
from squinch_nms_save.meta import summarize_meta_file
from squinch_nms_save.sync import _compose_sync, _merge_entity_collections, clone_slot


def _mapping() -> SaveMapping:
    names = (
        "Version",
        "Platform",
        "ActiveContext",
        "CommonStateData",
        "SaveName",
        "SaveUniversalId",
        "BaseContext",
        "GameMode",
        "PlayerStateData",
        "SpawnStateData",
        "DiscoveryManagerData",
        "Inventory",
        "PersistentPlayerBases",
        "SettlementStatesV2",
        "ShipOwnership",
        "ArchivedShipOwnership",
        "Multitools",
        "ArchivedMultitools",
        "CurrentFreighter",
        "FreighterFleet",
        "FleetFrigates",
        "FleetExpeditions",
        "SquadronUnlockedPilotSlots",
        "SquadronPilots",
        "BaseType",
        "PersistentBaseTypes",
        "Units",
    )
    raw_names = {name: f"raw{index}" for index, name in enumerate(names)}
    return SaveMapping(
        MAPPING_VERSION,
        {raw: name for name, raw in raw_names.items()},
        {},
        raw_names,
    )


def _document(label: str) -> dict:
    return {
        "Version": 4746,
        "Platform": f"platform-{label}",
        "ActiveContext": "Main",
        "CommonStateData": {
            "SaveName": f"name-{label}",
            "SaveUniversalId": f"id-{label}",
            "TotalPlayTime": label,
        },
        "BaseContext": {
            "GameMode": label,
            "PlayerStateData": {
                "Inventory": {"owner": label},
                "PersistentPlayerBases": [{"base": label}],
                "SettlementStatesV2": [{"settlement": label}],
                "ShipOwnership": [{"ship": label}],
                "ArchivedShipOwnership": [],
                "Multitools": [{"tool": label}],
                "ArchivedMultitools": [],
                "CurrentFreighter": {"freighter": label},
                "FreighterFleet": [{"freighter-fleet": label}],
                "FleetFrigates": [{"frigate": label}],
                "FleetExpeditions": [{"expedition": label}],
                "SquadronUnlockedPilotSlots": f"slots-{label}",
                "SquadronPilots": [{"pilot": label}],
                "Units": label,
            },
            "SpawnStateData": {"spawn": label},
        },
        "DiscoveryManagerData": {"discoveries": label},
    }


def test_sync_everything_except_selected_groups_preserves_identity() -> None:
    mapping = _mapping()
    source = _document("source")
    target = _document("target")

    operations, fields = _compose_sync(
        source,
        target,
        mapping,
        {"everything"},
        {"bases", "starships", "multitools"},
        set(),
        set(),
    )
    result = mapping.deobfuscate(apply_patch(mapping.obfuscate(target), operations))
    player = result["BaseContext"]["PlayerStateData"]

    assert player["Inventory"] == {"owner": "source"}
    assert player["Units"] == "source"
    assert player["PersistentPlayerBases"] == [{"base": "target"}]
    assert player["SettlementStatesV2"] == [{"settlement": "target"}]
    assert player["ShipOwnership"] == [{"ship": "target"}]
    assert player["Multitools"] == [{"tool": "target"}]
    assert player["CurrentFreighter"] == {"freighter": "source"}
    assert player["FleetFrigates"] == [{"frigate": "source"}]
    assert player["SquadronPilots"] == [{"pilot": "source"}]
    assert result["CommonStateData"]["SaveName"] == "name-target"
    assert result["CommonStateData"]["SaveUniversalId"] == "id-target"
    assert result["CommonStateData"]["TotalPlayTime"] == "source"
    assert result["DiscoveryManagerData"] == {"discoveries": "source"}
    assert "Inventory" in fields
    assert "ShipOwnership" not in fields
    assert "CurrentFreighter" in fields
    assert "FleetFrigates" in fields
    assert "SquadronPilots" in fields


def test_sync_inventory_group_changes_only_inventory_fields() -> None:
    mapping = _mapping()
    source = _document("source")
    target = _document("target")

    operations, fields = _compose_sync(
        source,
        target,
        mapping,
        {"inventories"},
        set(),
        set(),
        set(),
    )
    result = mapping.deobfuscate(apply_patch(mapping.obfuscate(target), operations))

    assert fields == ["Inventory"]
    assert result["BaseContext"]["PlayerStateData"]["Inventory"] == {"owner": "source"}
    assert result["BaseContext"]["PlayerStateData"]["Units"] == "target"


@pytest.mark.parametrize(
    ("group", "changed", "preserved"),
    (
        (
            "freighter",
            {"CurrentFreighter", "FreighterFleet"},
            {"FleetFrigates", "SquadronPilots"},
        ),
        (
            "frigates",
            {"FleetFrigates", "FleetExpeditions"},
            {"CurrentFreighter", "SquadronPilots"},
        ),
        (
            "squadron",
            {"SquadronPilots", "SquadronUnlockedPilotSlots"},
            {"CurrentFreighter", "FleetFrigates"},
        ),
    ),
)
def test_sync_fleet_subgroups_are_independent(
    group: str, changed: set[str], preserved: set[str]
) -> None:
    mapping = _mapping()
    source = _document("source")
    target = _document("target")

    operations, fields = _compose_sync(source, target, mapping, {group}, set(), set(), set())
    player = mapping.deobfuscate(apply_patch(mapping.obfuscate(target), operations))["BaseContext"][
        "PlayerStateData"
    ]

    for field in changed:
        assert player[field] == source["BaseContext"]["PlayerStateData"][field]
        assert field in fields
    for field in preserved:
        assert player[field] == target["BaseContext"]["PlayerStateData"][field]
        assert field not in fields


def test_sync_freighter_base_preserves_every_other_base() -> None:
    mapping = _mapping()
    source = _document("source")
    target = _document("target")

    def base(name: str, base_type: str) -> dict:
        return {
            "Name": name,
            "BaseType": {"PersistentBaseTypes": base_type},
        }

    source_player = source["BaseContext"]["PlayerStateData"]
    target_player = target["BaseContext"]["PlayerStateData"]
    source_player["PersistentPlayerBases"] = [
        base("source-home", "HomePlanetBase"),
        base("source-freighter", "FreighterBase"),
    ]
    target_player["PersistentPlayerBases"] = [
        base("target-home", "HomePlanetBase"),
        base("target-freighter", "FreighterBase"),
        base("target-ship", "PlayerShipBase"),
    ]

    operations, fields = _compose_sync(
        source, target, mapping, {"freighter-base"}, set(), set(), set()
    )
    player = mapping.deobfuscate(apply_patch(mapping.obfuscate(target), operations))["BaseContext"][
        "PlayerStateData"
    ]

    assert [row["Name"] for row in player["PersistentPlayerBases"]] == [
        "target-home",
        "source-freighter",
        "target-ship",
    ]
    assert player["SettlementStatesV2"] == [{"settlement": "target"}]
    assert fields == ["PersistentPlayerBases"]


def test_sync_everything_can_exclude_only_freighter_base() -> None:
    mapping = _mapping()
    source = _document("source")
    target = _document("target")

    def base(name: str, base_type: str) -> dict:
        return {"Name": name, "BaseType": {"PersistentBaseTypes": base_type}}

    source["BaseContext"]["PlayerStateData"]["PersistentPlayerBases"] = [
        base("source-home", "HomePlanetBase"),
        base("source-freighter", "FreighterBase"),
    ]
    target["BaseContext"]["PlayerStateData"]["PersistentPlayerBases"] = [
        base("target-home", "HomePlanetBase"),
        base("target-freighter", "FreighterBase"),
    ]

    operations, _fields = _compose_sync(
        source, target, mapping, {"everything"}, {"freighter-base"}, set(), set()
    )
    bases = mapping.deobfuscate(apply_patch(mapping.obfuscate(target), operations))["BaseContext"][
        "PlayerStateData"
    ]["PersistentPlayerBases"]

    assert [row["Name"] for row in bases] == ["source-home", "target-freighter"]


def test_clone_slot_clears_entities_and_creates_new_identity(tmp_path: Path, tranche: Path) -> None:
    profile = tmp_path / "profile"
    document = {
        "F2P": 4746,
        "CommonStateData": {"SaveName": "Source", "SaveUniversalId": "0x1"},
        "BaseContext": {
            "PlayerStateData": {
                "PersistentPlayerBases": [{"Name": "Base"}],
                "SettlementStatesV2": [
                    {"UniqueId": "owned", "UniverseAddress": 1},
                    {"UniqueId": "", "UniverseAddress": 0},
                ],
                "ShipOwnership": [{"Name": "Ship"}],
                "ArchivedShipOwnership": [],
                "Multitools": [{"Name": "Tool"}],
                "ArchivedMultitools": [],
            }
        },
    }
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": MAPPING_VERSION, "Mapping": []}))

    with pytest.raises(SaveToolError, match="explicit --apply"):
        clone_slot(
            profile,
            mapping,
            1,
            7,
            "Dev Testing",
            ["bases", "starships", "multitools"],
            apply=False,
        )
    result = clone_slot(
        profile,
        mapping,
        1,
        7,
        "Dev Testing",
        ["bases", "starships", "multitools"],
        apply=True,
    )

    auto = decode_file(profile / "save13.hg").document
    manual = decode_file(profile / "save14.hg").document
    for value, name in ((auto, "save13.hg"), (manual, "save14.hg")):
        assert value["CommonStateData"]["SaveName"] == "Dev Testing"
        assert value["CommonStateData"]["SaveUniversalId"] != "0x1"
        player = value["BaseContext"]["PlayerStateData"]
        assert player["PersistentPlayerBases"] == []
        assert all(row["UniqueId"] == "" for row in player["SettlementStatesV2"])
        assert player["ShipOwnership"] == []
        assert player["Multitools"] == []
        assert summarize_meta_file(profile / f"mf_{name}", profile / name).save_name == (
            "Dev Testing"
        )
    assert (
        auto["CommonStateData"]["SaveUniversalId"] == manual["CommonStateData"]["SaveUniversalId"]
    )
    assert Path(result["manifest"]).exists()


def test_merge_unions_entities_and_selects_newest_base_revision() -> None:
    def base(name: str, updated: int) -> dict:
        return {
            "Owner": {"UID": "player", "TS": 10},
            "BaseType": {"PersistentBaseTypes": "HomePlanetBase"},
            "Name": name,
            "LastUpdateTimestamp": updated,
            "GalacticAddress": 1,
            "Position": [1, 2, 3],
        }

    def ship(seed: str) -> dict:
        return {
            "Name": seed,
            "Resource": {"Filename": "ship.scene.mbin", "Seed": [True, seed]},
        }

    def tool(seed: str) -> dict:
        return {
            "Name": seed,
            "Resource": {"Filename": "tool.scene.mbin"},
            "Seed": [True, seed],
        }

    first = _document("first")
    second = _document("second")
    first_player = first["BaseContext"]["PlayerStateData"]
    second_player = second["BaseContext"]["PlayerStateData"]
    first_player["PersistentPlayerBases"] = [base("old", 1)]
    second_player["PersistentPlayerBases"] = [base("new", 2)]
    first_player["ShipOwnership"] = [ship("0x1")]
    second_player["ShipOwnership"] = [ship("0x2")]
    first_player["ArchivedShipOwnership"] = []
    second_player["ArchivedShipOwnership"] = []
    first_player["Multitools"] = [tool("0x3")]
    second_player["Multitools"] = [tool("0x4")]
    first_player["ArchivedMultitools"] = []
    second_player["ArchivedMultitools"] = []

    merged, skipped = _merge_entity_collections(
        first,
        [first, second],
        {"everything"},
        set(),
        set(),
        set(),
        "error",
    )
    player = merged["BaseContext"]["PlayerStateData"]

    assert [row["Name"] for row in player["PersistentPlayerBases"]] == ["new"]
    assert [row["Name"] for row in player["ShipOwnership"]] == ["0x1", "0x2"]
    assert [row["Name"] for row in player["Multitools"]] == ["0x3", "0x4"]
    assert skipped == {}
