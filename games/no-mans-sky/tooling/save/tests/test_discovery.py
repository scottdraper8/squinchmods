from __future__ import annotations

import copy
import json
from pathlib import Path

from conftest import write_save_pair

from squinch_nms_save.codec import RawNumber, decode_file
from squinch_nms_save.discovery import create_discovery_redistribution_patches
from squinch_nms_save.jsonops import apply_patch


def _record(address: int, name: str, timestamp: int) -> dict:
    return {
        "DD": {"UA": address, "DT": "SolarSystem", "VP": ["seed"]},
        "DM": {"CN": name},
        "OWS": {"TS": timestamp},
    }


def _document(name: str, records: list[dict], visited: list[int]) -> dict:
    return {
        "F2P": 4746,
        "CommonStateData": {"SaveName": name},
        "BaseContext": {"PlayerStateData": {"VisitedSystems": visited}},
        "DiscoveryManagerData": {
            "DiscoveryData-v1": {
                "ReserveStore": 20,
                "ReserveManaged": 20,
                "Store": {"Record": records},
                "Available": [],
                "Enqueued": [],
            }
        },
    }


def test_discovery_redistribution_deduplicates_and_uses_narrowest_range_owner(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    galaxy_one = (1 << 40) | 0x12345
    galaxy_256 = (2 << 40) | (255 << 32) | 0x67890
    broad = _document(
        "Galaxies 1-256",
        [_record(galaxy_one, "old", 10), _record(galaxy_256, "special", 10)],
        [galaxy_one, galaxy_one, galaxy_256, 0],
    )
    special = _document(
        "Galaxy 256 Special",
        [_record(galaxy_one, "new", 20), _record(galaxy_256, "special", 10)],
        [galaxy_256, 0, 0, 0],
    )
    write_save_pair(profile, name="save.hg", document=copy.deepcopy(broad))
    write_save_pair(profile, name="save2.hg", document=copy.deepcopy(broad))
    write_save_pair(profile, name="save3.hg", document=copy.deepcopy(special))
    write_save_pair(profile, name="save4.hg", document=copy.deepcopy(special))
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))
    output = tranche / "outputs/redistributed"

    create_discovery_redistribution_patches(
        profile,
        mapping,
        output,
        target_slots=[1, 2],
        name_overrides=[],
        policy_path=None,
    )

    slot_one_patch = json.loads(
        (output / "slot-1-auto.patch.json").read_text(), parse_float=RawNumber
    )
    slot_two_patch = json.loads(
        (output / "slot-2-auto.patch.json").read_text(), parse_float=RawNumber
    )
    slot_one = apply_patch(decode_file(profile / "save.hg").document, slot_one_patch)
    slot_two = apply_patch(decode_file(profile / "save3.hg").document, slot_two_patch)
    one_records = slot_one["DiscoveryManagerData"]["DiscoveryData-v1"]["Store"]["Record"]
    two_records = slot_two["DiscoveryManagerData"]["DiscoveryData-v1"]["Store"]["Record"]
    assert [row["DM"]["CN"] for row in one_records] == ["new"]
    assert [row["DM"]["CN"] for row in two_records] == ["special"]
    assert slot_one["BaseContext"]["PlayerStateData"]["VisitedSystems"] == [
        galaxy_one,
        0,
        0,
        0,
    ]
    assert slot_two["BaseContext"]["PlayerStateData"]["VisitedSystems"] == [
        galaxy_256,
        0,
        0,
        0,
    ]

    systems = json.loads((output / "systems.json").read_text())
    assert systems["unique_count"] == 2
    assert systems["ownership"]["overlaps"] == {"256": [1, 2]}
    assert systems["ownership"]["slots"]["2"]["owned_galaxies"] == [256]
    assert sum(len(system["records"]["stored"]) for system in systems["systems"]) == 2
