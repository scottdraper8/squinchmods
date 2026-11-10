from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.inventory import build_inventory


def _address(galaxy: int, suffix: int) -> int:
    return ((galaxy - 1) << 32) | suffix


def _base(
    *,
    created: int,
    name: str,
    galaxy: int,
    updated: int,
    base_type: str = "HomePlanetBase",
) -> dict:
    return {
        "Owner": {"UID": "player", "LID": "player", "TS": created},
        "BaseType": {"PersistentBaseTypes": base_type},
        "Name": name,
        "GalacticAddress": _address(galaxy, 42),
        "Position": [1.0, 2.0, 3.0],
        "LastUpdateTimestamp": updated,
        "Objects": [{"ObjectID": name}],
    }


def _document(bases: list[dict]) -> dict:
    return {
        "Version": 4746,
        "ActiveContext": "Main",
        "CommonStateData": {"SaveName": "Galaxies 1-50"},
        "BaseContext": {
            "PlayerStateData": {
                "PersistentPlayerBases": bases,
                "ShipOwnership": [
                    {
                        "Name": "Étoile",
                        "Resource": {
                            "Filename": "ship.scene.mbin",
                            "Seed": [True, "0x123"],
                        },
                    }
                ],
                "ArchivedShipOwnership": [],
                "Multitools": [
                    {
                        "Name": "Tool",
                        "Seed": [True, "0x456"],
                        "Resource": {"Filename": "tool.scene.mbin"},
                    }
                ],
                "ArchivedMultitools": [],
            }
        },
    }


def test_inventory_deduplicates_revisions_and_checks_fixed_galaxies(
    tmp_path: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    old = _base(created=100, name="Old name", galaxy=1, updated=10)
    second_same_planet = _base(created=101, name="Second base", galaxy=1, updated=10)
    portable = _base(
        created=102,
        name="Freighter",
        galaxy=256,
        updated=10,
        base_type="FreighterBase",
    )
    external = _base(
        created=900,
        name="Cached visitor",
        galaxy=99,
        updated=10,
        base_type="ExternalPlanetBase",
    )
    first_save, first_meta = write_save_pair(
        profile,
        name="save.hg",
        document=_document([old, second_same_planet, portable, external]),
    )
    new = _base(created=100, name="New name", galaxy=51, updated=20)
    second_save, second_meta = write_save_pair(
        profile,
        name="save2.hg",
        document=_document([new, second_same_planet, portable]),
    )
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (first_save, first_meta, second_save, second_meta)
    }
    mapping = tranche / "inputs/mapping.json"
    mapping.parent.mkdir()
    mapping.write_text(json.dumps({"libMBIN_version": "7.14.0.1", "Mapping": []}))

    result, artifacts = build_inventory(profile, mapping, tranche / "outputs/inventory")

    assert len(artifacts) == 7
    assert result["unique_bases"] == 3
    assert result["unique_starships"] == 1
    assert result["unique_multitools"] == 1
    bases = json.loads((tranche / "outputs/inventory/bases.json").read_text())
    revised = next(item for item in bases["bases"] if ":created:100:" in item["identity"])
    assert revised["name"] == "New name"
    assert revised["data"]["Name"] == "New name"
    assert revised["revision_count"] == 2
    assert bases["excluded_cached_types"] == {"ExternalPlanetBase": 1}
    starships = json.loads((tranche / "outputs/inventory/starships.json").read_text())
    assert starships["starships"][0]["name"] == "Étoile"
    assert not (tranche / "outputs/inventory/ships.json").exists()
    report = json.loads((tranche / "outputs/inventory/report.json").read_text())
    violations = report["range_violations"]
    assert len(violations) == 1
    assert [item["name"] for item in violations[0]["violations"]] == ["New name"]
    slot_diffs = json.loads((tranche / "outputs/inventory/slot-diffs.json").read_text())
    assert slot_diffs["slots"][0]["entities"]["bases"]["equal"] is False
    assert "starships" in slot_diffs["slots"][0]["entities"]
    assert "ships" not in slot_diffs["slots"][0]["entities"]
    audit = json.loads((tranche / "outputs/inventory/identity-audit.json").read_text())
    assert audit["summary"]["fixed_base_location_collisions"] == 1
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert after == before
    with pytest.raises(SaveToolError, match="refusing to overwrite"):
        build_inventory(profile, mapping, tranche / "outputs/inventory")

    selected, selected_artifacts = build_inventory(
        profile,
        mapping,
        tranche / "outputs/newest",
        snapshot_selection="newest",
        archives="exclude",
        cached="include",
    )
    assert selected["save_snapshots"] == 1
    assert len(selected_artifacts) == 8
    cached = json.loads((tranche / "outputs/newest/cached-bases.json").read_text())
    assert cached["unique_count"] == 1
