from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .codec import decode_file, serialize_json
from .errors import SaveToolError
from .jsonops import apply_patch, escape_pointer
from .mapping import SaveMapping
from .meta import inspect_meta_file
from .paths import list_saves
from .policy import SavePolicy
from .stage import sha256_file
from .sync import _slot_pairs, _workspace_output

INVENTORY_GROUPS = frozenset({"exosuit", "starships", "freighter", "exocraft"})
RACE_STANDING_IDS = frozenset({"^WAR_STANDING", "^TRA_STANDING", "^EXP_STANDING", "^BUI_STANDING"})
SYSTEM_ADDRESS_MASK = (1 << 52) - 1


def list_discovery_systems(save_path: Path, mapping_path: Path) -> dict[str, Any]:
    mapping = SaveMapping.load(mapping_path.expanduser().resolve())
    document = mapping.deobfuscate(decode_file(save_path.expanduser().resolve()).document)
    base = document.get("BaseContext")
    player = base.get("PlayerStateData") if isinstance(base, dict) else None
    manager = document.get("DiscoveryManagerData")
    data = manager.get("DiscoveryData-v1") if isinstance(manager, dict) else None
    store = data.get("Store") if isinstance(data, dict) else None
    records = store.get("Record") if isinstance(store, dict) else None
    available = data.get("Available") if isinstance(data, dict) else None
    enqueued = data.get("Enqueued") if isinstance(data, dict) else None
    if not isinstance(player, dict) or not all(
        isinstance(value, list) for value in (records, available, enqueued)
    ):
        raise SaveToolError("save has no complete player/discovery data")
    current = _current_system_address(player)
    visited_values = player.get("VisitedSystems")
    visited_values = visited_values if isinstance(visited_values, list) else []
    visited = {
        address & SYSTEM_ADDRESS_MASK
        for value in visited_values
        for address in [_integer_address(value)]
        if address not in (None, 0)
    }
    systems = []
    system_addresses = sorted(
        visited
        | {
            address
            for collection in (records, available, enqueued)
            for record in collection
            for address in [_system_address(record)]
            if address is not None
        }
    )
    for address in system_addresses:
        children = [record for record in records if _system_address(record) == address]
        available_children = [record for record in available if _system_address(record) == address]
        enqueued_children = [record for record in enqueued if _system_address(record) == address]
        names = sorted(
            {
                name
                for record in children
                if isinstance(record, dict) and isinstance(record.get("DM"), dict)
                for name in [record["DM"].get("CN")]
                if isinstance(name, str) and name
            }
        )
        systems.append(
            {
                "system_address": f"0x{address:X}",
                "galaxy": ((address >> 32) & 0xFF) + 1,
                "current": address == current,
                "in_visited_history": address in visited,
                "record_count": len(children),
                "available_record_count": len(available_children),
                "enqueued_record_count": len(enqueued_children),
                "solar_system_record_count": sum(
                    isinstance(record, dict)
                    and isinstance(record.get("DD"), dict)
                    and record["DD"].get("DT") == "SolarSystem"
                    for record in children
                ),
                "custom_names": names,
            }
        )
    common = document.get("CommonStateData")
    return {
        "save": str(save_path.expanduser().resolve()),
        "save_name": common.get("SaveName", "") if isinstance(common, dict) else "",
        "current_system_address": f"0x{current:X}",
        "system_count": len(systems),
        "systems": systems,
    }


def _raw_key(mapping: SaveMapping, semantic: str) -> str:
    return mapping.raw_names.get(semantic, semantic)


def _pointer(mapping: SaveMapping, *parts: str | int) -> str:
    return "/" + "/".join(
        str(part) if isinstance(part, int) else escape_pointer(_raw_key(mapping, part))
        for part in parts
    )


def _replace(
    operations: list[dict[str, Any]],
    mapping: SaveMapping,
    path: tuple[str | int, ...],
    old: Any,
    new: Any,
) -> bool:
    old_raw = mapping.obfuscate(old)
    new_raw = mapping.obfuscate(new)
    if old_raw == new_raw:
        return False
    pointer = _pointer(mapping, *path)
    operations.extend(
        [
            {"op": "test", "path": pointer, "value": old_raw},
            {"op": "replace", "path": pointer, "value": new_raw},
        ]
    )
    return True


def _clear_inventory(
    operations: list[dict[str, Any]],
    mapping: SaveMapping,
    inventory: Any,
    path: tuple[str | int, ...],
) -> int:
    if not isinstance(inventory, dict):
        return 0
    slots = inventory.get("Slots")
    if not isinstance(slots, list):
        raise SaveToolError(f"inventory at {_pointer(mapping, *path)} has no Slots array")
    if not slots:
        return 0
    _replace(operations, mapping, (*path, "Slots"), slots, [])
    return len(slots)


def _clear_named_inventories(
    operations: list[dict[str, Any]],
    mapping: SaveMapping,
    owner: dict[str, Any],
    path: tuple[str | int, ...],
) -> int:
    return sum(
        _clear_inventory(operations, mapping, owner.get(field), (*path, field))
        for field in ("Inventory", "Inventory_Cargo")
    )


def _clear_inventory_groups(
    player: dict[str, Any],
    mapping: SaveMapping,
    groups: set[str],
    operations: list[dict[str, Any]],
) -> dict[str, int]:
    root = ("BaseContext", "PlayerStateData")
    removed = {group: 0 for group in sorted(groups)}
    if "exosuit" in groups:
        removed["exosuit"] += sum(
            _clear_inventory(operations, mapping, player.get(field), (*root, field))
            for field in ("Inventory", "Inventory_Cargo")
        )
    if "starships" in groups:
        removed["starships"] += _clear_inventory(
            operations, mapping, player.get("ShipInventory"), (*root, "ShipInventory")
        )
        for field, archived in (("ShipOwnership", False), ("ArchivedShipOwnership", True)):
            rows = player.get(field)
            if rows is None:
                continue
            if not isinstance(rows, list):
                raise SaveToolError(f"{field} is not an array")
            for index, row in enumerate(rows):
                owner = row.get("Ownership") if archived and isinstance(row, dict) else row
                if not isinstance(owner, dict):
                    continue
                owner_path = (
                    (*root, field, index, "Ownership") if archived else (*root, field, index)
                )
                removed["starships"] += _clear_named_inventories(
                    operations, mapping, owner, owner_path
                )
    if "freighter" in groups:
        removed["freighter"] += sum(
            _clear_inventory(operations, mapping, player.get(field), (*root, field))
            for field in ("FreighterInventory", "FreighterInventory_Cargo")
        )
        fleet = player.get("FreighterFleet")
        if fleet is None:
            fleet = []
        if not isinstance(fleet, list):
            raise SaveToolError("FreighterFleet is not an array")
        for index, freighter in enumerate(fleet):
            if isinstance(freighter, dict):
                removed["freighter"] += _clear_named_inventories(
                    operations,
                    mapping,
                    freighter,
                    (*root, "FreighterFleet", index),
                )
    if "exocraft" in groups:
        vehicles = player.get("VehicleOwnership")
        if vehicles is None:
            vehicles = []
        if not isinstance(vehicles, list):
            raise SaveToolError("VehicleOwnership is not an array")
        for index, vehicle in enumerate(vehicles):
            if not isinstance(vehicle, dict):
                continue
            vehicle_path = (*root, "VehicleOwnership", index)
            removed["exocraft"] += _clear_named_inventories(
                operations, mapping, vehicle, vehicle_path
            )
            cargo = vehicle.get("VehicleCargo")
            if (
                isinstance(cargo, list)
                and cargo
                and _replace(
                    operations,
                    mapping,
                    (*vehicle_path, "VehicleCargo"),
                    cargo,
                    [],
                )
            ):
                removed["exocraft"] += len(cargo)
    return removed


def _reset_race_standing(
    player: dict[str, Any], mapping: SaveMapping, operations: list[dict[str, Any]]
) -> dict[str, int]:
    groups = player.get("Stats")
    if not isinstance(groups, list):
        raise SaveToolError("Stats is not an array")
    global_groups = [
        (index, group)
        for index, group in enumerate(groups)
        if isinstance(group, dict) and group.get("GroupId") == "^GLOBAL_STATS"
    ]
    if len(global_groups) != 1:
        raise SaveToolError("expected exactly one ^GLOBAL_STATS group")
    group_index, group = global_groups[0]
    stats = group.get("Stats")
    if not isinstance(stats, list):
        raise SaveToolError("^GLOBAL_STATS has no Stats array")
    found: dict[str, tuple[int, int]] = {}
    for stat_index, stat in enumerate(stats):
        if not isinstance(stat, dict) or stat.get("Id") not in RACE_STANDING_IDS:
            continue
        identifier = stat["Id"]
        value = stat.get("Value")
        integer = value.get("IntValue") if isinstance(value, dict) else None
        if not isinstance(integer, int) or isinstance(integer, bool) or identifier in found:
            raise SaveToolError(f"invalid or duplicate race standing {identifier}")
        found[identifier] = (stat_index, integer)
    if set(found) != RACE_STANDING_IDS:
        missing = ", ".join(sorted(RACE_STANDING_IDS - set(found)))
        raise SaveToolError(f"missing race standings: {missing}")
    previous = {}
    for identifier, (stat_index, integer) in found.items():
        previous[identifier] = integer
        _replace(
            operations,
            mapping,
            (
                "BaseContext",
                "PlayerStateData",
                "Stats",
                group_index,
                "Stats",
                stat_index,
                "Value",
                "IntValue",
            ),
            integer,
            0,
        )
    return dict(sorted(previous.items()))


def _integer_address(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _current_system_address(player: dict[str, Any]) -> int:
    universe = player.get("UniverseAddress")
    address = universe.get("GalacticAddress") if isinstance(universe, dict) else None
    reality = universe.get("RealityIndex") if isinstance(universe, dict) else None
    required = ("VoxelX", "VoxelY", "VoxelZ", "SolarSystemIndex")
    if (
        not isinstance(address, dict)
        or not isinstance(reality, int)
        or any(not isinstance(address.get(field), int) for field in required)
    ):
        raise SaveToolError("current UniverseAddress is incomplete")
    x = address["VoxelX"] & 0xFFF
    y = address["VoxelY"] & 0xFF
    z = address["VoxelZ"] & 0xFFF
    solar = address["SolarSystemIndex"] & 0xFFF
    system = (solar << 40) | ((reality & 0xFF) << 32) | (y << 24) | (z << 12) | x
    return system


def _system_address(record: Any) -> int | None:
    discovery = record.get("DD") if isinstance(record, dict) else None
    address = _integer_address(discovery.get("UA")) if isinstance(discovery, dict) else None
    return address & SYSTEM_ADDRESS_MASK if address is not None else None


def _edit_discovery_systems(
    document: dict[str, Any],
    player: dict[str, Any],
    mapping: SaveMapping,
    operations: list[dict[str, Any]],
    operation: str,
    requested_systems: set[int],
    include_current: bool,
    expected_name: str | None,
    galaxy_range: tuple[int, int] | None,
) -> dict[str, Any]:
    systems = {address & SYSTEM_ADDRESS_MASK for address in requested_systems}
    current = _current_system_address(player)
    if include_current:
        systems.add(current)
    manager = document.get("DiscoveryManagerData")
    data = manager.get("DiscoveryData-v1") if isinstance(manager, dict) else None
    store = data.get("Store") if isinstance(data, dict) else None
    records = store.get("Record") if isinstance(store, dict) else None
    available = data.get("Available") if isinstance(data, dict) else None
    enqueued = data.get("Enqueued") if isinstance(data, dict) else None
    if not all(isinstance(value, list) for value in (records, available, enqueued)):
        raise SaveToolError("DiscoveryData-v1 store is incomplete")
    if operation == "prune-range" and galaxy_range is None:
        raise SaveToolError("prune-range requires a galaxy-classified save")
    removed_systems = {
        address
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("DD"), dict)
        and record["DD"].get("DT") == "SolarSystem"
        and isinstance(record.get("FL"), dict)
        and record["FL"].get("F") == 1
        for address in [_system_address(record)]
        if address is not None
    }
    if operation == "purge-removed":
        systems = removed_systems

    def keep(record: Any) -> bool:
        address = _system_address(record)
        if address is None:
            return False
        if operation == "clear":
            return False
        if operation == "retain":
            return address in systems
        if operation == "remove":
            return address not in systems
        if operation == "prune-range" and galaxy_range is not None:
            galaxy = ((address >> 32) & 0xFF) + 1
            return galaxy_range[0] <= galaxy <= galaxy_range[1]
        if operation == "purge-removed":
            return address not in removed_systems
        raise SaveToolError(f"unsupported discovery operation: {operation}")

    retained = [copy.deepcopy(record) for record in records if keep(record)]
    retained_available = [copy.deepcopy(record) for record in available if keep(record)]
    retained_enqueued = [copy.deepcopy(record) for record in enqueued if keep(record)]
    selected_records = [record for record in records if _system_address(record) in systems]
    if include_current:
        system_records = [
            record
            for record in selected_records
            if isinstance(record.get("DD"), dict)
            and record["DD"].get("DT") == "SolarSystem"
            and _system_address(record) == current
        ]
        if len(system_records) != 1:
            raise SaveToolError("current system does not have exactly one SolarSystem discovery")
    names = sorted(
        {
            name
            for record in selected_records
            if isinstance(record, dict)
            for name in [
                record.get("DM", {}).get("CN") if isinstance(record.get("DM"), dict) else None
            ]
            if isinstance(name, str) and name
        }
    )
    if expected_name and expected_name not in names:
        raise SaveToolError(
            f"current discovery system does not contain expected name {expected_name!r}"
        )
    _replace(
        operations,
        mapping,
        ("DiscoveryManagerData", "DiscoveryData-v1", "Store", "Record"),
        records,
        retained,
    )
    _replace(
        operations,
        mapping,
        ("DiscoveryManagerData", "DiscoveryData-v1", "Available"),
        available,
        retained_available,
    )
    _replace(
        operations,
        mapping,
        ("DiscoveryManagerData", "DiscoveryData-v1", "Enqueued"),
        enqueued,
        retained_enqueued,
    )
    old_visited = player.get("VisitedSystems")
    if not isinstance(old_visited, list) or not old_visited:
        raise SaveToolError("VisitedSystems is not a nonempty array")
    if operation == "purge-removed":
        new_visited = [
            0
            if (address := _integer_address(value)) not in (None, 0)
            and address & SYSTEM_ADDRESS_MASK in removed_systems
            else value
            for value in old_visited
        ]
        retained_visited_count = sum(
            _integer_address(value) not in (None, 0) for value in new_visited
        )
    else:
        kept_visited = []
        for address_value in old_visited:
            address = _integer_address(address_value)
            if address in (None, 0):
                continue
            synthetic = {"DD": {"UA": address}}
            if keep(synthetic):
                kept_visited.append(address_value)
        if len(kept_visited) > len(old_visited):
            raise SaveToolError("retained visited systems exceed the original fixed capacity")
        new_visited = [*kept_visited, *([0] * (len(old_visited) - len(kept_visited)))]
        retained_visited_count = len(kept_visited)
    _replace(
        operations,
        mapping,
        ("BaseContext", "PlayerStateData", "VisitedSystems"),
        old_visited,
        new_visited,
    )
    return {
        "operation": operation,
        "system_addresses": [f"0x{address:X}" for address in sorted(systems)],
        "current_system_address": f"0x{current:X}",
        "galaxy_range": (
            {"first": galaxy_range[0], "last": galaxy_range[1]} if galaxy_range else None
        ),
        "retained_records": len(retained),
        "removed_records": len(records) - len(retained),
        "retained_available": len(retained_available),
        "retained_enqueued": len(retained_enqueued),
        "retained_visited_systems": retained_visited_count,
        "custom_names": names,
    }


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write cleanup artifact {path}: {exc}") from exc


def create_cleanup_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    target_slots: list[int],
    clear_inventory: list[str],
    reset_race_standing: bool,
    clear_teleports: bool,
    discovery_operation: str | None,
    discovery_systems: list[str],
    include_current_system: bool,
    expected_discovery_name: str | None,
    policy_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    groups = set(clear_inventory)
    unknown = groups - INVENTORY_GROUPS
    if unknown:
        raise SaveToolError(f"unknown inventory groups: {', '.join(sorted(unknown))}")
    if (
        not target_slots
        or len(set(target_slots)) != len(target_slots)
        or any(not 1 <= slot <= 10 for slot in target_slots)
    ):
        raise SaveToolError("target slots must be unique values between 1 and 10")
    if not any((groups, reset_race_standing, clear_teleports, discovery_operation)):
        raise SaveToolError("cleanup plan requires at least one action")
    if discovery_operation not in {
        None,
        "clear",
        "retain",
        "remove",
        "prune-range",
        "purge-removed",
    }:
        raise SaveToolError("invalid discovery operation")
    if (
        discovery_systems or include_current_system or expected_discovery_name
    ) and not discovery_operation:
        raise SaveToolError("discovery selectors require a discovery operation")
    if discovery_operation in {"retain", "remove"} and not (
        discovery_systems or include_current_system
    ):
        raise SaveToolError("retain/remove requires a system address or --current-system")
    if discovery_operation in {"clear", "prune-range", "purge-removed"} and (
        discovery_systems or include_current_system
    ):
        raise SaveToolError("clear/prune-range does not accept system selectors")
    try:
        requested_systems = {_integer_address(value) for value in discovery_systems}
    except TypeError as exc:
        raise SaveToolError("invalid discovery system address") from exc
    if None in requested_systems:
        raise SaveToolError("discovery system addresses must be decimal or 0x-prefixed integers")
    requested_systems = {int(value) for value in requested_systems}
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite cleanup output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if any(slot not in pairs for slot in target_slots):
        raise SaveToolError("cleanup target slots must exist as complete pairs")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    targets = []
    try:
        for slot in target_slots:
            for kind in ("auto", "manual"):
                save = pairs[slot][kind]
                inspect_meta_file(save.meta_path, save.path)
                raw = decode_file(save.path).document
                document = mapping.deobfuscate(raw)
                base = document.get("BaseContext")
                player = base.get("PlayerStateData") if isinstance(base, dict) else None
                if not isinstance(player, dict):
                    raise SaveToolError("cleanup target has no PlayerStateData")
                operations: list[dict[str, Any]] = []
                removed = _clear_inventory_groups(player, mapping, groups, operations)
                standings = (
                    _reset_race_standing(player, mapping, operations) if reset_race_standing else {}
                )
                teleport_count = 0
                endpoints = player.get("TeleportEndpoints")
                if clear_teleports:
                    if not isinstance(endpoints, list):
                        raise SaveToolError("TeleportEndpoints is not an array")
                    teleport_count = len(endpoints)
                    _replace(
                        operations,
                        mapping,
                        ("BaseContext", "PlayerStateData", "TeleportEndpoints"),
                        endpoints,
                        [],
                    )
                common = document.get("CommonStateData")
                save_name = common.get("SaveName", "") if isinstance(common, dict) else ""
                classified = policy.classify(save_name if isinstance(save_name, str) else "")
                discovery = (
                    _edit_discovery_systems(
                        document,
                        player,
                        mapping,
                        operations,
                        discovery_operation,
                        requested_systems,
                        include_current_system,
                        expected_discovery_name,
                        classified.galaxies,
                    )
                    if discovery_operation
                    else None
                )
                apply_patch(raw, operations)
                patch_name = f"slot-{slot}-{kind}.patch.json"
                patch_raw = (serialize_json(operations) + "\n").encode()
                _write_new(temporary / patch_name, patch_raw)
                targets.append(
                    {
                        "slot": slot,
                        "kind": kind,
                        "source": str(save.path),
                        "source_data_sha256": sha256_file(save.path),
                        "source_meta_sha256": sha256_file(save.meta_path),
                        "patch": patch_name,
                        "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                        "operation_count": len(operations),
                        "removed_inventory_slots": removed,
                        "previous_race_standing": standings,
                        "removed_teleport_endpoints": teleport_count,
                        "discovery": discovery,
                    }
                )
        manifest = {
            "schema": "squinch-nms-save-cleanup-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "target_slots": target_slots,
            "actions": {
                "clear_inventory": sorted(groups),
                "reset_race_standing": reset_race_standing,
                "clear_teleports": clear_teleports,
                "discovery_operation": discovery_operation,
                "discovery_systems": [f"0x{address:X}" for address in sorted(requested_systems)],
                "include_current_system": include_current_system,
                "expected_discovery_name": expected_discovery_name,
                "policy": {"source": policy.source, "sha256": policy.sha256},
            },
            "targets": targets,
        }
        _write_new(
            temporary / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    artifacts = [str(output / "manifest.json"), *[str(output / t["patch"]) for t in targets]]
    return (
        {
            "output_directory": str(output),
            "target_slots": target_slots,
            "target_snapshots": len(targets),
            "patch_operations": sum(target["operation_count"] for target in targets),
        },
        artifacts,
    )
