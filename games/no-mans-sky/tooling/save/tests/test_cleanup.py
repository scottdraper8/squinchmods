from __future__ import annotations

import json
from pathlib import Path

from conftest import write_save_pair

from squinch_nms_save.cleanup import create_cleanup_patches, list_discovery_systems
from squinch_nms_save.codec import RawNumber, decode_file
from squinch_nms_save.jsonops import apply_patch


def _inventory(item: str) -> dict:
    return {"Slots": [{"Id": item}], "SpecialSlots": [], "ValidSlotIndices": []}


def _document() -> dict:
    current = 0x1B63A267FF7FD
    other = 0x100012345678
    return {
        "F2P": 4746,
        "CommonStateData": {"SaveName": "Galaxies 51-100"},
        "BaseContext": {
            "PlayerStateData": {
                "UniverseAddress": {
                    "RealityIndex": 58,
                    "GalacticAddress": {
                        "VoxelX": 2045,
                        "VoxelY": 38,
                        "VoxelZ": 2047,
                        "SolarSystemIndex": 438,
                        "PlanetIndex": 1,
                    },
                },
                "Inventory": _inventory("exosuit"),
                "Inventory_Cargo": _inventory("exosuit-cargo"),
                "Inventory_TechOnly": _inventory("exosuit-tech"),
                "ShipInventory": _inventory("legacy-ship"),
                "ShipOwnership": [
                    {
                        "Inventory": _inventory("ship"),
                        "Inventory_Cargo": _inventory("ship-cargo"),
                        "Inventory_TechOnly": _inventory("ship-tech"),
                    }
                ],
                "ArchivedShipOwnership": [],
                "FreighterInventory": _inventory("freighter"),
                "FreighterInventory_Cargo": _inventory("freighter-cargo"),
                "FreighterInventory_TechOnly": _inventory("freighter-tech"),
                "FreighterFleet": [],
                "VehicleOwnership": [
                    {
                        "Inventory": _inventory("vehicle"),
                        "Inventory_Cargo": _inventory("vehicle-cargo"),
                        "Inventory_TechOnly": _inventory("vehicle-tech"),
                        "VehicleCargo": [{"Id": "legacy-vehicle"}],
                    }
                ],
                "Stats": [
                    {
                        "GroupId": "^GLOBAL_STATS",
                        "Stats": [
                            {"Id": identifier, "Value": {"IntValue": index + 1}}
                            for index, identifier in enumerate(
                                (
                                    "^WAR_STANDING",
                                    "^TRA_STANDING",
                                    "^EXP_STANDING",
                                    "^BUI_STANDING",
                                )
                            )
                        ],
                    }
                ],
                "TeleportEndpoints": [{"Name": "old"}],
                "VisitedSystems": [current, other, 0, 0],
            }
        },
        "DiscoveryManagerData": {
            "DiscoveryData-v1": {
                "ReserveStore": 2,
                "ReserveManaged": 2,
                "Store": {
                    "Record": [
                        {"DD": {"UA": current, "DT": "SolarSystem"}},
                        {
                            "DD": {"UA": current | (1 << 52), "DT": "Planet"},
                            "DM": {"CN": "Apam Woods"},
                        },
                        {"DD": {"UA": other, "DT": "SolarSystem"}},
                    ]
                },
                "Available": [{"DD": {"UA": other, "DT": "SolarSystem"}}],
                "Enqueued": [],
            }
        },
    }


def test_cleanup_plan_clears_cargo_preserves_tech_and_retains_current_system(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/cleanup"

    create_cleanup_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        clear_inventory=["exosuit", "starships", "freighter", "exocraft"],
        reset_race_standing=True,
        clear_teleports=True,
        discovery_operation="retain",
        discovery_systems=[],
        include_current_system=True,
        expected_discovery_name="Apam Woods",
        policy_path=None,
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    assert player["Inventory"]["Slots"] == []
    assert player["Inventory_TechOnly"]["Slots"] == [{"Id": "exosuit-tech"}]
    assert player["ShipOwnership"][0]["Inventory"]["Slots"] == []
    assert player["ShipOwnership"][0]["Inventory_TechOnly"]["Slots"] == [{"Id": "ship-tech"}]
    assert player["FreighterInventory"]["Slots"] == []
    assert player["FreighterInventory_TechOnly"]["Slots"] == [{"Id": "freighter-tech"}]
    assert player["VehicleOwnership"][0]["Inventory"]["Slots"] == []
    assert player["VehicleOwnership"][0]["Inventory_TechOnly"]["Slots"] == [{"Id": "vehicle-tech"}]
    assert player["VehicleOwnership"][0]["VehicleCargo"] == []
    assert {stat["Id"]: stat["Value"]["IntValue"] for stat in player["Stats"][0]["Stats"]} == {
        "^WAR_STANDING": 0,
        "^TRA_STANDING": 0,
        "^EXP_STANDING": 0,
        "^BUI_STANDING": 0,
    }
    assert player["TeleportEndpoints"] == []
    assert player["VisitedSystems"] == [0x1B63A267FF7FD, 0, 0, 0]
    discovery = result["DiscoveryManagerData"]["DiscoveryData-v1"]
    assert len(discovery["Store"]["Record"]) == 2
    assert discovery["Available"] == []


def test_cleanup_plan_prunes_discoveries_to_the_named_galaxy_range(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    current = 0x1B63A267FF7FD
    in_range = 0xABC << 40 | 99 << 32 | 0x1234567
    outside_range = 0xDEF << 40 | 100 << 32 | 0x7654321
    data = document["DiscoveryManagerData"]["DiscoveryData-v1"]
    data["Store"]["Record"].extend(
        [
            {"DD": {"UA": in_range, "DT": "SolarSystem"}},
            {"DD": {"UA": outside_range, "DT": "SolarSystem"}},
        ]
    )
    document["BaseContext"]["PlayerStateData"]["VisitedSystems"] = [
        current,
        in_range,
        outside_range,
        0,
    ]
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/prune"

    create_cleanup_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        clear_inventory=[],
        reset_race_standing=False,
        clear_teleports=False,
        discovery_operation="prune-range",
        discovery_systems=[],
        include_current_system=False,
        expected_discovery_name=None,
        policy_path=None,
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    records = result["DiscoveryManagerData"]["DiscoveryData-v1"]["Store"]["Record"]
    record_galaxies = {((row["DD"]["UA"] >> 32) & 0xFF) + 1 for row in records}
    visited_galaxies = {
        ((address >> 32) & 0xFF) + 1 for address in player["VisitedSystems"] if address
    }
    assert record_galaxies <= set(range(51, 101))
    assert visited_galaxies <= set(range(51, 101))
    assert in_range in {row["DD"]["UA"] for row in records}
    assert outside_range not in {row["DD"]["UA"] for row in records}


def test_targeted_discovery_remove_and_listing_use_canonical_system_addresses(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    removed = 0x100012345678
    history_only = 0xABC6300123456
    document["BaseContext"]["PlayerStateData"]["VisitedSystems"][-1] = history_only
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/remove"

    listed = list_discovery_systems(profile / "save.hg", mapping)
    assert listed["current_system_address"] == "0x1B63A267FF7FD"
    assert {row["system_address"] for row in listed["systems"]} == {
        "0x100012345678",
        "0xABC6300123456",
        "0x1B63A267FF7FD",
    }
    history_row = next(
        row for row in listed["systems"] if row["system_address"] == "0xABC6300123456"
    )
    assert history_row["record_count"] == 0
    assert history_row["in_visited_history"] is True

    create_cleanup_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        clear_inventory=[],
        reset_race_standing=False,
        clear_teleports=False,
        discovery_operation="remove",
        discovery_systems=[hex(removed)],
        include_current_system=False,
        expected_discovery_name=None,
        policy_path=None,
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    records = result["DiscoveryManagerData"]["DiscoveryData-v1"]["Store"]["Record"]
    assert removed not in {row["DD"]["UA"] & ((1 << 52) - 1) for row in records}
    assert removed not in player["VisitedSystems"]


def test_cleanup_plan_purges_complete_removed_system_subtrees(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    document = _document()
    removed = 0x100012345678
    retained = 0x1B63A267FF7FD
    data = document["DiscoveryManagerData"]["DiscoveryData-v1"]
    data["Store"]["Record"] = [
        {"DD": {"UA": retained, "DT": "SolarSystem"}},
        {"DD": {"UA": retained | (1 << 52), "DT": "Planet"}},
        {"DD": {"UA": removed, "DT": "SolarSystem"}, "FL": {"F": 1}},
        {"DD": {"UA": removed | (1 << 52), "DT": "Planet"}},
    ]
    data["Available"] = [{"DD": {"UA": removed | (1 << 52), "DT": "Planet"}}]
    data["Enqueued"] = [{"DD": {"UA": removed, "DT": "SolarSystem"}}]
    document["BaseContext"]["PlayerStateData"]["VisitedSystems"] = [
        retained,
        removed,
        0,
        0,
    ]
    write_save_pair(profile, name="save.hg", document=document)
    write_save_pair(profile, name="save2.hg", document=document)
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/purge-removed"

    create_cleanup_patches(
        profile,
        mapping,
        output,
        target_slots=[1],
        clear_inventory=[],
        reset_race_standing=False,
        clear_teleports=False,
        discovery_operation="purge-removed",
        discovery_systems=[],
        include_current_system=False,
        expected_discovery_name=None,
        policy_path=None,
    )

    patch = json.loads((output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber)
    result = apply_patch(decode_file(profile / "save.hg").document, patch)
    player = result["BaseContext"]["PlayerStateData"]
    discovery = result["DiscoveryManagerData"]["DiscoveryData-v1"]
    remaining = {row["DD"]["UA"] & ((1 << 52) - 1) for row in discovery["Store"]["Record"]}
    assert remaining == {retained}
    assert discovery["Available"] == []
    assert discovery["Enqueued"] == []
    assert player["VisitedSystems"] == [retained, 0, 0, 0]
