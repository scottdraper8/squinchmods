from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .cleanup import _replace
from .codec import RawNumber, decode_file, serialize_json
from .errors import SaveToolError
from .inventory import _text
from .jsonops import apply_patch
from .mapping import SaveMapping
from .meta import inspect_meta_file
from .paths import list_saves
from .stage import sha256_file
from .sync import _slot_pairs, _workspace_output

INVENTORY_TYPES = frozenset({"Product", "Substance"})
STATIC_INVENTORIES = {
    "exosuit": ("Inventory", "Inventory_TechOnly"),
    "freighter": ("FreighterInventory", "FreighterInventory_TechOnly"),
    "current-starship": ("ShipInventory", "ShipInventory_TechOnly"),
    "current-multitool": ("WeaponInventory", "WeaponInventory"),
}


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write inventory-edit artifact {path}: {exc}") from exc


def _definition(value: str) -> dict[str, Any]:
    parts = value.split(":")
    if len(parts) != 3:
        raise SaveToolError("item definitions must use ID:Product|Substance:STACK_MULTIPLIER")
    identifier, inventory_type, multiplier_text = parts
    if not identifier.startswith("^") or len(identifier) < 2:
        raise SaveToolError("item IDs must start with ^")
    if inventory_type not in INVENTORY_TYPES:
        raise SaveToolError("item type must be Product or Substance")
    try:
        multiplier = int(multiplier_text)
    except ValueError as exc:
        raise SaveToolError("item stack multipliers must be integers") from exc
    if not 1 <= multiplier <= 9999:
        raise SaveToolError("item stack multipliers must be between 1 and 9999")
    return {"id": identifier, "inventory_type": inventory_type, "stack_multiplier": multiplier}


def _quantity(value: str) -> tuple[str, int]:
    identifier, separator, quantity_text = value.rpartition(":")
    if not separator or not identifier.startswith("^"):
        raise SaveToolError("item quantity operations must use ID:QUANTITY")
    try:
        quantity = int(quantity_text)
    except ValueError as exc:
        raise SaveToolError("item quantities must be integers") from exc
    if quantity < 0 or quantity > 999_999_999:
        raise SaveToolError("item quantities must be between 0 and 999999999")
    return identifier, quantity


def _layout(inventory: dict[str, Any]) -> list[tuple[int, int]]:
    valid = inventory.get("ValidSlotIndices")
    width = inventory.get("Width")
    height = inventory.get("Height")
    if (
        not isinstance(valid, list)
        or not valid
        or isinstance(width, bool)
        or not isinstance(width, int)
        or isinstance(height, bool)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise SaveToolError("inventory has no valid slot layout")
    coordinates: list[tuple[int, int]] = []
    for index in valid:
        x = index.get("X") if isinstance(index, dict) else None
        y = index.get("Y") if isinstance(index, dict) else None
        if (
            isinstance(x, bool)
            or not isinstance(x, int)
            or isinstance(y, bool)
            or not isinstance(y, int)
            or not 0 <= x < width
            or not 0 <= y < height
        ):
            raise SaveToolError("inventory contains an invalid slot index")
        coordinates.append((x, y))
    if len(set(coordinates)) != len(coordinates):
        raise SaveToolError("inventory contains duplicate valid slots")
    return sorted(coordinates, key=lambda value: (value[1], value[0]))


def _slot_type(slot: Any) -> str | None:
    type_value = slot.get("Type") if isinstance(slot, dict) else None
    value = type_value.get("InventoryType") if isinstance(type_value, dict) else None
    return value if isinstance(value, str) else None


def _stack_capacity(slots: list[Any], definition: dict[str, Any], difficulty: str) -> int:
    exact = {
        slot.get("MaxAmount")
        for slot in slots
        if isinstance(slot, dict)
        and slot.get("Id") == definition["id"]
        and _slot_type(slot) == definition["inventory_type"]
        and isinstance(slot.get("MaxAmount"), int)
        and not isinstance(slot.get("MaxAmount"), bool)
        and slot["MaxAmount"] > 0
    }
    if len(exact) == 1:
        return exact.pop()
    if len(exact) > 1:
        raise SaveToolError(f"inventory has inconsistent stack limits for {definition['id']}")
    if definition["inventory_type"] == "Substance":
        samples = [
            slot["MaxAmount"]
            for slot in slots
            if _slot_type(slot) == "Substance"
            and isinstance(slot.get("MaxAmount"), int)
            and not isinstance(slot.get("MaxAmount"), bool)
            and slot["MaxAmount"] > 1
        ]
        base = min(samples) if samples else None
    else:
        samples = [
            slot["MaxAmount"]
            for slot in slots
            if _slot_type(slot) == "Product"
            and isinstance(slot.get("MaxAmount"), int)
            and not isinstance(slot.get("MaxAmount"), bool)
            and 1 < slot["MaxAmount"] < 9999
        ]
        base = math.gcd(*samples) if samples else None
    if base is None or base <= 1:
        raise SaveToolError(
            f"cannot infer the {definition['inventory_type']} stack unit from the target "
            f"inventory under {difficulty!r} limits"
        )
    return min(9999, base * definition["stack_multiplier"])


def _new_item_slot(
    definition: dict[str, Any], amount: int, maximum: int, coordinate: tuple[int, int]
) -> dict[str, Any]:
    return {
        "Type": {"InventoryType": definition["inventory_type"]},
        "Id": definition["id"],
        "Amount": amount,
        "MaxAmount": maximum,
        "DamageFactor": RawNumber("0.0"),
        "FullyInstalled": True,
        "AddedAutomatically": False,
        "Index": {"X": coordinate[0], "Y": coordinate[1]},
    }


def _difficulty(player: dict[str, Any]) -> str:
    state = player.get("DifficultyState")
    settings = state.get("Settings") if isinstance(state, dict) else None
    limits = settings.get("InventoryStackLimits") if isinstance(settings, dict) else None
    value = limits.get("InventoryStackLimitsDifficulty") if isinstance(limits, dict) else None
    if not isinstance(value, str) or not value:
        raise SaveToolError("save has no inventory stack-limit difficulty")
    return value


def _resolve_inventory(
    player: dict[str, Any], selector: str
) -> tuple[dict[str, Any], tuple[str | int, ...], dict[str, Any], tuple[str | int, ...]]:
    base: tuple[str | int, ...] = ("BaseContext", "PlayerStateData")
    if selector in STATIC_INVENTORIES:
        general_name, technology_name = STATIC_INVENTORIES[selector]
        general = player.get(general_name)
        technology = player.get(technology_name)
        general_path = (*base, general_name)
        technology_path = (*base, technology_name)
    else:
        prefix, separator, index_text = selector.partition(":")
        collection_name = {"starship": "ShipOwnership", "exocraft": "VehicleOwnership"}.get(prefix)
        if not separator or collection_name is None:
            raise SaveToolError(
                "inventory must be exosuit, freighter, current-starship, current-multitool, "
                "starship:N, or exocraft:N"
            )
        try:
            index = int(index_text)
        except ValueError as exc:
            raise SaveToolError("inventory ownership index must be an integer") from exc
        collection = player.get(collection_name)
        if not isinstance(collection, list) or not 0 <= index < len(collection):
            raise SaveToolError(f"{selector} does not exist")
        owner = collection[index]
        if not isinstance(owner, dict):
            raise SaveToolError(f"{selector} has invalid ownership data")
        general = owner.get("Inventory")
        technology = owner.get("Inventory_TechOnly")
        general_path = (*base, collection_name, index, "Inventory")
        technology_path = (*base, collection_name, index, "Inventory_TechOnly")
    if not isinstance(general, dict) or not isinstance(technology, dict):
        raise SaveToolError(f"{selector} does not have complete general and technology inventories")
    return general, general_path, technology, technology_path


def _item_edit(
    inventory: dict[str, Any],
    definitions: dict[str, dict[str, Any]],
    operations: dict[str, tuple[str, int]],
    fill_ids: list[str],
    difficulty: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old_slots = inventory.get("Slots")
    if not isinstance(old_slots, list) or any(not isinstance(slot, dict) for slot in old_slots):
        raise SaveToolError("general inventory has invalid slots")
    layout = _layout(inventory)
    if fill_ids:
        capacities = {
            identifier: _stack_capacity(old_slots, definitions[identifier], difficulty)
            for identifier in fill_ids
        }
        slots = [
            _new_item_slot(
                definitions[identifier],
                capacities[identifier],
                capacities[identifier],
                coordinate,
            )
            for ordinal, coordinate in enumerate(layout)
            for identifier in [fill_ids[ordinal % len(fill_ids)]]
        ]
        return slots, {
            "mode": "fill",
            "stack_capacities": capacities,
            "item_totals": dict(sorted(Counter(slot["Id"] for slot in slots).items())),
        }

    slots = copy.deepcopy(old_slots)
    valid = set(layout)
    occupied = {
        (slot.get("Index", {}).get("X"), slot.get("Index", {}).get("Y"))
        for slot in slots
        if isinstance(slot.get("Index"), dict)
    }
    if not occupied <= valid:
        raise SaveToolError("general inventory contains an occupied invalid slot")
    capacities: dict[str, int] = {}
    for identifier, (action, quantity) in operations.items():
        matching = [slot for slot in slots if slot.get("Id") == identifier]
        if action == "remove":
            available = sum(slot.get("Amount", 0) for slot in matching)
            if quantity > available:
                raise SaveToolError(
                    f"cannot remove {quantity} {identifier}; only {available} exist"
                )
            remaining = quantity
            for slot in reversed(matching):
                take = min(remaining, slot["Amount"])
                slot["Amount"] -= take
                remaining -= take
            slots = [slot for slot in slots if slot.get("Amount") != 0]
            continue
        definition = definitions.get(identifier)
        if definition is None:
            raise SaveToolError(f"{action} requires --define-item for {identifier}")
        maximum = _stack_capacity(old_slots, definition, difficulty)
        capacities[identifier] = maximum
        if action == "set":
            slots = [slot for slot in slots if slot.get("Id") != identifier]
            matching = []
        remaining = quantity
        if action == "add":
            matching = [slot for slot in slots if slot.get("Id") == identifier]
            for slot in matching:
                space = maximum - slot["Amount"]
                if space < 0:
                    raise SaveToolError(
                        f"existing {identifier} stack exceeds its inferred capacity"
                    )
                added = min(space, remaining)
                slot["Amount"] += added
                slot["MaxAmount"] = maximum
                remaining -= added
        occupied = {
            (slot["Index"]["X"], slot["Index"]["Y"])
            for slot in slots
            if isinstance(slot.get("Index"), dict)
        }
        open_slots = [coordinate for coordinate in layout if coordinate not in occupied]
        while remaining:
            if not open_slots:
                raise SaveToolError(
                    f"inventory has no room for {remaining} additional {identifier}"
                )
            amount = min(maximum, remaining)
            slots.append(_new_item_slot(definition, amount, maximum, open_slots.pop(0)))
            remaining -= amount
    return slots, {"mode": "quantities", "stack_capacities": capacities}


def _walk_technology(value: Any, identifier: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("Id") == identifier and _slot_type(value) == "Technology":
            matches.append(value)
        for child in value.values():
            matches.extend(_walk_technology(child, identifier))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_walk_technology(child, identifier))
    return matches


def _technology_template(documents: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    templates = []
    for document in documents:
        for source in _walk_technology(document, identifier):
            template = copy.deepcopy(source)
            template.pop("Index", None)
            template["FullyInstalled"] = True
            template["AddedAutomatically"] = False
            maximum = template.get("MaxAmount")
            if isinstance(maximum, int) and maximum > 0:
                template["Amount"] = maximum
            templates.append(template)
    unique = {serialize_json(template): template for template in templates}
    if not unique:
        raise SaveToolError(f"no installed {identifier} template exists in the profile")
    if len(unique) != 1:
        raise SaveToolError(f"installed {identifier} templates disagree across the profile")
    return next(iter(unique.values()))


def _install_technology(
    inventory: dict[str, Any], identifiers: list[str], documents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    old_slots = inventory.get("Slots")
    if not isinstance(old_slots, list) or any(not isinstance(slot, dict) for slot in old_slots):
        raise SaveToolError("technology inventory has invalid slots")
    slots = copy.deepcopy(old_slots)
    layout = _layout(inventory)
    occupied = {
        (slot["Index"]["X"], slot["Index"]["Y"])
        for slot in slots
        if isinstance(slot.get("Index"), dict)
    }
    open_slots = [coordinate for coordinate in layout if coordinate not in occupied]
    for identifier in identifiers:
        if any(slot.get("Id") == identifier for slot in slots):
            raise SaveToolError(f"technology {identifier} is already installed")
        if not open_slots:
            raise SaveToolError("technology inventory has no open valid slot")
        template = _technology_template(documents, identifier)
        coordinate = open_slots.pop(0)
        template["Index"] = {"X": coordinate[0], "Y": coordinate[1]}
        slots.append(template)
    return slots


def create_inventory_edit_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    target_slots: list[int],
    inventory_selector: str,
    definitions: list[str],
    add_items: list[str],
    remove_items: list[str],
    set_items: list[str],
    fill_items: list[str],
    install_technology: list[str],
    expected_save_name: str | None,
) -> tuple[dict[str, Any], list[str]]:
    if (
        not target_slots
        or len(set(target_slots)) != len(target_slots)
        or any(not 1 <= slot <= 10 for slot in target_slots)
    ):
        raise SaveToolError("target slots must be unique values between 1 and 10")
    definition_rows = [_definition(value) for value in definitions]
    definition_map = {row["id"]: row for row in definition_rows}
    if len(definition_map) != len(definition_rows):
        raise SaveToolError("item definitions must have unique IDs")
    quantity_rows = (
        [("add", value) for value in add_items]
        + [("remove", value) for value in remove_items]
        + [("set", value) for value in set_items]
    )
    quantity_operations: dict[str, tuple[str, int]] = {}
    for action, value in quantity_rows:
        identifier, quantity = _quantity(value)
        if identifier in quantity_operations:
            raise SaveToolError(f"item {identifier} has more than one quantity operation")
        quantity_operations[identifier] = (action, quantity)
    if len(set(fill_items)) != len(fill_items) or any(
        not item.startswith("^") for item in fill_items
    ):
        raise SaveToolError("fill item IDs must be unique and start with ^")
    if fill_items and quantity_operations:
        raise SaveToolError("fill operations cannot be combined with add/remove/set operations")
    if any(identifier not in definition_map for identifier in fill_items):
        raise SaveToolError("every fill item requires a matching --define-item")
    if len(set(install_technology)) != len(install_technology) or any(
        not item.startswith("^") for item in install_technology
    ):
        raise SaveToolError("technology IDs must be unique and start with ^")
    if not quantity_operations and not fill_items and not install_technology:
        raise SaveToolError("at least one item or technology operation is required")
    if inventory_selector == "current-multitool" and (quantity_operations or fill_items):
        raise SaveToolError("current-multitool supports technology installation only")

    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite inventory-edit output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if any(slot not in pairs for slot in target_slots):
        raise SaveToolError("inventory-edit target slots must exist as complete pairs")
    semantic_documents = [
        mapping.deobfuscate(decode_file(save.path).document)
        for save in list_saves(profile)
        if save.path.exists() and save.meta_path.exists()
    ]

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
                common = document.get("CommonStateData")
                save_name = _text(common.get("SaveName")) if isinstance(common, dict) else ""
                if expected_save_name is not None and save_name != expected_save_name:
                    raise SaveToolError(
                        f"slot {slot} {kind} is named {save_name!r}, "
                        f"expected {expected_save_name!r}"
                    )
                base = document.get("BaseContext")
                player = base.get("PlayerStateData") if isinstance(base, dict) else None
                if not isinstance(player, dict):
                    raise SaveToolError(f"{save.path} has no PlayerStateData")
                general, general_path, technology, technology_path = _resolve_inventory(
                    player, inventory_selector
                )
                operations: list[dict[str, Any]] = []
                edit_summary = None
                if quantity_operations or fill_items:
                    old_general = general.get("Slots")
                    new_general, edit_summary = _item_edit(
                        general,
                        definition_map,
                        quantity_operations,
                        fill_items,
                        _difficulty(player),
                    )
                    _replace(
                        operations, mapping, (*general_path, "Slots"), old_general, new_general
                    )
                if install_technology:
                    old_technology = technology.get("Slots")
                    new_technology = _install_technology(
                        technology, install_technology, semantic_documents
                    )
                    _replace(
                        operations,
                        mapping,
                        (*technology_path, "Slots"),
                        old_technology,
                        new_technology,
                    )
                apply_patch(raw, operations)
                patch_name = f"slot-{slot}-{kind}.patch.json"
                patch_raw = (serialize_json(operations) + "\n").encode()
                _write_new(temporary / patch_name, patch_raw)
                targets.append(
                    {
                        "slot": slot,
                        "kind": kind,
                        "save_name": save_name,
                        "inventory": inventory_selector,
                        "inventory_stack_limits": _difficulty(player),
                        "source": str(save.path),
                        "source_data_sha256": sha256_file(save.path),
                        "source_meta_sha256": sha256_file(save.meta_path),
                        "patch": patch_name,
                        "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                        "operation_count": len(operations),
                        "item_edit": edit_summary,
                        "installed_technology": install_technology,
                    }
                )
        manifest = {
            "schema": "squinch-nms-inventory-edit-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "target_slots": target_slots,
            "inventory": inventory_selector,
            "expected_save_name": expected_save_name,
            "definitions": definition_rows,
            "quantity_operations": quantity_operations,
            "fill_items": fill_items,
            "install_technology": install_technology,
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
    artifacts = [
        str(output / "manifest.json"),
        *[str(output / target["patch"]) for target in targets],
    ]
    return (
        {
            "output_directory": str(output),
            "target_slots": target_slots,
            "target_snapshots": len(targets),
            "patch_operations": sum(target["operation_count"] for target in targets),
        },
        artifacts,
    )
