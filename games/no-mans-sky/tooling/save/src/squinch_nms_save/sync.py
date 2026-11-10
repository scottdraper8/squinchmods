from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codec import decode_file, encode_document, serialize_json
from .errors import SaveToolError
from .inventory import _base_identity, _equipment_identity, _integer, _text
from .jsonops import apply_patch, escape_pointer
from .mapping import SaveMapping
from .meta import inspect_meta_bytes, inspect_meta_file, rekey_meta, rename_meta, update_meta
from .paths import SaveIdentity, list_saves, require_pair
from .slots import _replace_bytes
from .stage import _metadata_size_mode, _nms_processes, sha256_file

GROUPS = frozenset(
    {
        "everything",
        "player",
        "common",
        "discoveries",
        "bases",
        "freighter-base",
        "starships",
        "freighter",
        "frigates",
        "squadron",
        "multitools",
        "inventories",
    }
)
IDENTITY_COMMON_FIELDS = frozenset({"SaveName", "SaveUniversalId"})
BASE_FIELDS = frozenset(
    {
        "PersistentPlayerBases",
        "SettlementStatesV2",
        "SettlementStateRingBufferIndexV2",
        "SettlementHistory",
        "SettlementLocalSaveData",
        "TeleportEndpoints",
        "NPCWorkers",
        "TerrainEditData",
        "SeenBaseBuildingObjects",
        "BaseBuildingObjects",
    }
)
STARSHIP_FIELDS = frozenset(
    {
        "ShipInventory",
        "ShipLayout",
        "CurrentShip",
        "ShipHealth",
        "FirstShipPosition",
        "ShipOwnership",
        "ArchivedShipOwnership",
        "PrimaryShip",
        "ShipMoveableContents",
        "MultiShipEnabled",
        "StartGameShipPosition",
        "ShipNeedsTerrainPositioning",
        "ShipUsesLegacyColours",
        "CorvetteStorageLayout",
        "CorvetteStorageInventory",
        "CorvetteEditAssociatedShipIndex",
        "CorvetteEditShipName",
        "CorvetteDraftShipSeed",
    }
)
FREIGHTER_FIELDS = frozenset(
    {
        "CurrentFreighterHomeSystemSeed",
        "CurrentFreighter",
        "FreighterLayout",
        "FreighterCargoLayout",
        "FreighterInventory",
        "FreighterInventory_TechOnly",
        "FreighterInventory_Cargo",
        "FreighterLastSpawnTime",
        "FreighterUniverseAddress",
        "FreighterDismissed",
        "FreighterMatrixAt",
        "FreighterMatrixUp",
        "FreighterMatrixPos",
        "FreighterFleet",
        "CurrentFreighterNPC",
        "PlayerFreighterName",
        "FreighterEngineEffect",
    }
)
FRIGATE_FIELDS = frozenset(
    {
        "FleetSeed",
        "FleetFrigates",
        "FleetExpeditions",
        "ExpeditionSeedsSelectedToday",
    }
)
SQUADRON_FIELDS = frozenset({"SquadronUnlockedPilotSlots", "SquadronPilots"})
MULTITOOL_FIELDS = frozenset(
    {
        "WeaponInventory",
        "WeaponLayout",
        "CurrentWeapon",
        "Multitools",
        "ActiveMultioolIndex",
        "ArchivedMultitools",
        "StartingPrimaryWeapon",
        "StartingSecondaryWeapon",
    }
)


def _inventory_fields(keys: set[str]) -> set[str]:
    return {
        key
        for key in keys
        if "Inventory" in key
        or key.endswith("Layout")
        or key in {"V86", "ShipMoveableContents", "FoodUnitItem", "FoodUnitAccumulator"}
    }


def _workspace_output(path: Path) -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(Path(workspace_value).resolve())
    except ValueError as exc:
        raise SaveToolError(f"sync output must be inside the selected tranche: {resolved}") from exc
    return resolved


def _validate_groups(groups: list[str], label: str) -> set[str]:
    values = set(groups)
    unknown = values - GROUPS
    if unknown:
        raise SaveToolError(f"unknown {label}: {', '.join(sorted(unknown))}")
    return values


def _slot_pairs(saves: list[SaveIdentity]) -> dict[int, dict[str, SaveIdentity]]:
    result: dict[int, dict[str, SaveIdentity]] = {}
    for save in saves:
        require_pair(save)
        result.setdefault(save.slot, {})[save.kind] = save
    for slot, pair in result.items():
        if set(pair) != {"auto", "manual"}:
            raise SaveToolError(f"slot {slot} is not a complete Auto/Manual pair")
    return result


def _selected_player_fields(
    source: dict[str, Any],
    target: dict[str, Any],
    include_groups: set[str],
    exclude_groups: set[str],
    include_fields: set[str],
    exclude_fields: set[str],
) -> set[str]:
    keys = set(source) | set(target)
    if not include_groups and not include_fields:
        include_groups = {"everything"}
    selected = set(include_fields)
    if include_groups & {"everything", "player"}:
        selected |= keys
    if "bases" in include_groups:
        selected |= BASE_FIELDS
    if "starships" in include_groups:
        selected |= STARSHIP_FIELDS
    if "freighter" in include_groups:
        selected |= FREIGHTER_FIELDS
    if "frigates" in include_groups:
        selected |= FRIGATE_FIELDS
    if "squadron" in include_groups:
        selected |= SQUADRON_FIELDS
    if "multitools" in include_groups:
        selected |= MULTITOOL_FIELDS
    if "inventories" in include_groups:
        selected |= _inventory_fields(keys)

    excluded = set(exclude_fields)
    if exclude_groups & {"everything", "player"}:
        excluded |= keys
    if "bases" in exclude_groups:
        excluded |= BASE_FIELDS
    if "starships" in exclude_groups:
        excluded |= STARSHIP_FIELDS
    if "freighter" in exclude_groups:
        excluded |= FREIGHTER_FIELDS
    if "frigates" in exclude_groups:
        excluded |= FRIGATE_FIELDS
    if "squadron" in exclude_groups:
        excluded |= SQUADRON_FIELDS
    if "multitools" in exclude_groups:
        excluded |= MULTITOOL_FIELDS
    if "inventories" in exclude_groups:
        excluded |= _inventory_fields(keys)
    return (selected - excluded) & keys


def _merge_fields(
    source: dict[str, Any], target: dict[str, Any], fields: set[str]
) -> dict[str, Any]:
    result = copy.deepcopy(target)
    for field in fields:
        if field in source:
            result[field] = copy.deepcopy(source[field])
        else:
            result.pop(field, None)
    return result


def _base_type(base: Any) -> str:
    if not isinstance(base, dict):
        return ""
    base_type = base.get("BaseType")
    if not isinstance(base_type, dict):
        return ""
    return _text(base_type.get("PersistentBaseTypes"))


def _replace_base_partition(
    container: list[Any], replacement: list[Any], base_type: str
) -> list[Any]:
    result: list[Any] = []
    inserted = False
    for row in container:
        if _base_type(row) == base_type:
            if not inserted:
                result.extend(copy.deepcopy(replacement))
                inserted = True
            continue
        result.append(copy.deepcopy(row))
    if not inserted:
        result.extend(copy.deepcopy(replacement))
    return result


def _selective_freighter_bases(
    source: dict[str, Any],
    target: dict[str, Any],
    result: dict[str, Any],
    include_groups: set[str],
    exclude_groups: set[str],
    include_fields: set[str],
    exclude_fields: set[str],
) -> bool:
    if "PersistentPlayerBases" in exclude_fields:
        return False
    effective_includes = include_groups
    if not effective_includes and not include_fields:
        effective_includes = {"everything"}
    base_parent_included = bool(effective_includes & {"everything", "player", "bases"})
    base_parent_excluded = bool(exclude_groups & {"everything", "player", "bases"})
    freighter_included = base_parent_included or "freighter-base" in effective_includes
    freighter_excluded = base_parent_excluded or "freighter-base" in exclude_groups
    if not freighter_included or base_parent_excluded:
        return False
    if freighter_excluded and not base_parent_included:
        return False

    source_rows = source.get("PersistentPlayerBases")
    target_rows = target.get("PersistentPlayerBases")
    if not isinstance(source_rows, list) or not isinstance(target_rows, list):
        raise SaveToolError("freighter-base selection requires base arrays in source and target")
    if base_parent_included and not base_parent_excluded:
        if freighter_excluded:
            target_freighter = [row for row in target_rows if _base_type(row) == "FreighterBase"]
            result["PersistentPlayerBases"] = _replace_base_partition(
                source_rows, target_freighter, "FreighterBase"
            )
    else:
        source_freighter = [row for row in source_rows if _base_type(row) == "FreighterBase"]
        result["PersistentPlayerBases"] = _replace_base_partition(
            target_rows, source_freighter, "FreighterBase"
        )
    return True


def _pointer(mapping: SaveMapping, *semantic: str) -> str:
    return "/" + "/".join(escape_pointer(mapping.raw_key(field)) for field in semantic)


def _replace_operation(
    operations: list[dict[str, Any]], pointer: str, old: Any, new: Any, mapping: SaveMapping
) -> None:
    old_raw = mapping.obfuscate(old)
    new_raw = mapping.obfuscate(new)
    if old_raw != new_raw:
        operations.extend(
            [
                {"op": "test", "path": pointer, "value": old_raw},
                {"op": "replace", "path": pointer, "value": new_raw},
            ]
        )


def _compose_sync(
    source: dict[str, Any],
    target: dict[str, Any],
    mapping: SaveMapping,
    include_groups: set[str],
    exclude_groups: set[str],
    include_fields: set[str],
    exclude_fields: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    source_base = source.get("BaseContext")
    target_base = target.get("BaseContext")
    if not isinstance(source_base, dict) or not isinstance(target_base, dict):
        raise SaveToolError("sync source and target require BaseContext objects")
    source_player = source_base.get("PlayerStateData")
    target_player = target_base.get("PlayerStateData")
    if not isinstance(source_player, dict) or not isinstance(target_player, dict):
        raise SaveToolError("sync source and target require PlayerStateData objects")
    fields = _selected_player_fields(
        source_player,
        target_player,
        include_groups,
        exclude_groups,
        include_fields,
        exclude_fields,
    )
    operations: list[dict[str, Any]] = []
    new_player = _merge_fields(source_player, target_player, fields)
    if _selective_freighter_bases(
        source_player,
        target_player,
        new_player,
        include_groups,
        exclude_groups,
        include_fields,
        exclude_fields,
    ):
        fields.add("PersistentPlayerBases")
    _replace_operation(
        operations,
        _pointer(mapping, "BaseContext", "PlayerStateData"),
        target_player,
        new_player,
        mapping,
    )

    sync_all = not include_groups and not include_fields or "everything" in include_groups
    if sync_all and "everything" not in exclude_groups:
        source_common = source.get("CommonStateData")
        target_common = target.get("CommonStateData")
        if isinstance(source_common, dict) and isinstance(target_common, dict):
            common_fields = (set(source_common) | set(target_common)) - IDENTITY_COMMON_FIELDS
            new_common = _merge_fields(source_common, target_common, common_fields)
            _replace_operation(
                operations,
                _pointer(mapping, "CommonStateData"),
                target_common,
                new_common,
                mapping,
            )
        for field in ("Version", "Platform", "ActiveContext"):
            if field in source and field in target:
                _replace_operation(
                    operations,
                    _pointer(mapping, field),
                    target[field],
                    source[field],
                    mapping,
                )
        for field in ("GameMode", "SpawnStateData"):
            if field in source_base and field in target_base:
                _replace_operation(
                    operations,
                    _pointer(mapping, "BaseContext", field),
                    target_base[field],
                    source_base[field],
                    mapping,
                )
    if (sync_all or "discoveries" in include_groups) and (
        "discoveries" not in exclude_groups
        and "everything" not in exclude_groups
        and "DiscoveryManagerData" in source
        and "DiscoveryManagerData" in target
    ):
        _replace_operation(
            operations,
            _pointer(mapping, "DiscoveryManagerData"),
            target["DiscoveryManagerData"],
            source["DiscoveryManagerData"],
            mapping,
        )
    return operations, sorted(fields)


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write sync artifact {path}: {exc}") from exc


def create_sync_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    source_slot: int,
    target_slots: list[int],
    include_groups: list[str],
    exclude_groups: list[str],
    include_fields: list[str],
    exclude_fields: list[str],
) -> tuple[dict[str, Any], list[str]]:
    if not 1 <= source_slot <= 10:
        raise SaveToolError("source slot must be between 1 and 10")
    if (
        not target_slots
        or len(set(target_slots)) != len(target_slots)
        or any(not 1 <= slot <= 10 for slot in target_slots)
        or source_slot in target_slots
    ):
        raise SaveToolError("target slots must be unique existing slots other than the source")
    includes = _validate_groups(include_groups, "include groups")
    excludes = _validate_groups(exclude_groups, "exclude groups")
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite sync output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if source_slot not in pairs or any(slot not in pairs for slot in target_slots):
        raise SaveToolError("source and target slots must exist as complete pairs")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    targets = []
    try:
        source_docs = {}
        for kind, save in pairs[source_slot].items():
            inspect_meta_file(save.meta_path, save.path)
            source_docs[kind] = mapping.deobfuscate(decode_file(save.path).document)
        for target_slot in target_slots:
            for kind in ("auto", "manual"):
                save = pairs[target_slot][kind]
                inspect_meta_file(save.meta_path, save.path)
                raw = decode_file(save.path).document
                semantic = mapping.deobfuscate(raw)
                operations, fields = _compose_sync(
                    source_docs[kind],
                    semantic,
                    mapping,
                    includes,
                    excludes,
                    set(include_fields),
                    set(exclude_fields),
                )
                apply_patch(raw, operations)
                patch_name = f"slot-{target_slot}-{kind}.patch.json"
                patch_raw = (serialize_json(operations) + "\n").encode()
                _write_new(temporary / patch_name, patch_raw)
                common = semantic.get("CommonStateData")
                common = common if isinstance(common, dict) else {}
                targets.append(
                    {
                        "slot": target_slot,
                        "kind": kind,
                        "save_name": _text(common.get("SaveName")),
                        "source": str(save.path),
                        "source_data_sha256": sha256_file(save.path),
                        "source_meta_sha256": sha256_file(save.meta_path),
                        "patch": patch_name,
                        "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                        "selected_player_fields": fields,
                        "operation_count": len(operations),
                    }
                )
        manifest = {
            "schema": "squinch-nms-save-sync-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "source_slot": source_slot,
            "target_slots": target_slots,
            "selection": {
                "include_groups": sorted(includes),
                "exclude_groups": sorted(excludes),
                "include_fields": sorted(set(include_fields)),
                "exclude_fields": sorted(set(exclude_fields)),
                "identity_preserved": True,
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
            "source_slot": source_slot,
            "target_slots": target_slots,
            "target_snapshots": len(targets),
            "patch_operations": sum(target["operation_count"] for target in targets),
        },
        artifacts,
    )


def _group_selected(
    group: str,
    include_groups: set[str],
    exclude_groups: set[str],
    include_fields: set[str],
    exclude_fields: set[str],
) -> bool:
    group_fields = {
        "bases": {"PersistentPlayerBases"},
        "starships": {"ShipOwnership", "ArchivedShipOwnership"},
        "multitools": {"Multitools", "ArchivedMultitools"},
    }[group]
    included = (
        not include_groups
        and not include_fields
        or bool(include_groups & {"everything", "player", group})
        or bool(group_fields & include_fields)
    )
    excluded = bool(exclude_groups & {"everything", "player", group}) or bool(
        group_fields & exclude_fields
    )
    return included and not excluded


def _merge_bases(players: list[dict[str, Any]]) -> list[Any]:
    order = []
    selected: dict[str, tuple[int, dict[str, Any]]] = {}
    unkeyed = []
    for player in players:
        rows = player.get("PersistentPlayerBases")
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                unkeyed.append(copy.deepcopy(row))
                continue
            identity, _confidence = _base_identity(row)
            updated = _integer(row.get("LastUpdateTimestamp")) or 0
            if identity not in selected:
                order.append(identity)
            if identity not in selected or updated >= selected[identity][0]:
                selected[identity] = (updated, copy.deepcopy(row))
    return [selected[identity][1] for identity in order] + unkeyed


def _merge_equipment_rows(
    players: list[dict[str, Any]],
    field: str,
    *,
    kind: str,
    archived: bool,
    capacity: int,
    capacity_policy: str,
) -> tuple[list[Any], list[str]]:
    ordered = []
    selected = {}
    template_rows = players[0].get(field)
    template_rows = template_rows if isinstance(template_rows, list) else []
    for player in players:
        rows = player.get(field)
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            identity, _confidence = _equipment_identity(row, kind=kind, archived=archived)
            if identity is None:
                continue
            if identity not in selected:
                ordered.append(identity)
            selected[identity] = copy.deepcopy(row)
    skipped = []
    if len(ordered) > capacity:
        if capacity_policy == "error":
            raise SaveToolError(
                f"merging {field} produces {len(ordered)} entities, above capacity {capacity}"
            )
        skipped = ordered[capacity:]
        ordered = ordered[:capacity]
    values = [selected[identity] for identity in ordered]
    if archived and template_rows:
        empty = next(
            (
                copy.deepcopy(row)
                for row in template_rows
                if isinstance(row, dict)
                and _equipment_identity(row, kind=kind, archived=True)[0] is None
            ),
            None,
        )
        if empty is not None:
            values.extend(copy.deepcopy(empty) for _ in range(len(template_rows) - len(values)))
    return values, skipped


def _merge_entity_collections(
    template: dict[str, Any],
    sources: list[dict[str, Any]],
    include_groups: set[str],
    exclude_groups: set[str],
    include_fields: set[str],
    exclude_fields: set[str],
    capacity_policy: str,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    result = copy.deepcopy(template)
    result_player = result["BaseContext"]["PlayerStateData"]
    players = [source["BaseContext"]["PlayerStateData"] for source in sources]
    skipped: dict[str, list[str]] = {}
    if _group_selected("bases", include_groups, exclude_groups, include_fields, exclude_fields):
        result_player["PersistentPlayerBases"] = _merge_bases(players)
    for group, fields, kind, active_capacity, archive_capacity in (
        (
            "starships",
            ("ShipOwnership", "ArchivedShipOwnership"),
            "ship",
            12,
            18,
        ),
        (
            "multitools",
            ("Multitools", "ArchivedMultitools"),
            "multitool",
            6,
            18,
        ),
    ):
        if not _group_selected(
            group, include_groups, exclude_groups, include_fields, exclude_fields
        ):
            continue
        for field, archived, capacity in (
            (fields[0], False, active_capacity),
            (fields[1], True, archive_capacity),
        ):
            values, overflow = _merge_equipment_rows(
                players,
                field,
                kind=kind,
                archived=archived,
                capacity=capacity,
                capacity_policy=capacity_policy,
            )
            result_player[field] = values
            if overflow:
                skipped[field] = overflow
    return result, skipped


def create_merge_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    source_slots: list[int],
    template_slot: int,
    target_slot: int,
    include_groups: list[str],
    exclude_groups: list[str],
    include_fields: list[str],
    exclude_fields: list[str],
    capacity_policy: str,
) -> tuple[dict[str, Any], list[str]]:
    if (
        len(source_slots) < 2
        or len(set(source_slots)) != len(source_slots)
        or any(not 1 <= slot <= 10 for slot in source_slots)
        or template_slot not in source_slots
        or not 1 <= target_slot <= 10
    ):
        raise SaveToolError(
            "merge requires at least two unique sources, a template among them, and a valid target"
        )
    if capacity_policy not in {"error", "template"}:
        raise SaveToolError("capacity policy must be error or template")
    includes = _validate_groups(include_groups, "include groups")
    excludes = _validate_groups(exclude_groups, "exclude groups")
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite merge output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if any(slot not in pairs for slot in [*source_slots, target_slot]):
        raise SaveToolError("merge source and target slots must exist as complete pairs")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    targets = []
    try:
        for kind in ("auto", "manual"):
            source_documents = []
            for slot in source_slots:
                save = pairs[slot][kind]
                inspect_meta_file(save.meta_path, save.path)
                source_documents.append(mapping.deobfuscate(decode_file(save.path).document))
            template_index = source_slots.index(template_slot)
            template = source_documents[template_index]
            ordered_sources = [
                template,
                *[
                    document
                    for index, document in enumerate(source_documents)
                    if index != template_index
                ],
            ]
            merged_template, skipped = _merge_entity_collections(
                template,
                ordered_sources,
                includes,
                excludes,
                set(include_fields),
                set(exclude_fields),
                capacity_policy,
            )
            target = pairs[target_slot][kind]
            raw = decode_file(target.path).document
            semantic = mapping.deobfuscate(raw)
            operations, fields = _compose_sync(
                merged_template,
                semantic,
                mapping,
                includes,
                excludes,
                set(include_fields),
                set(exclude_fields),
            )
            apply_patch(raw, operations)
            patch_name = f"slot-{target_slot}-{kind}.patch.json"
            patch_raw = (serialize_json(operations) + "\n").encode()
            _write_new(temporary / patch_name, patch_raw)
            targets.append(
                {
                    "slot": target_slot,
                    "kind": kind,
                    "source": str(target.path),
                    "source_data_sha256": sha256_file(target.path),
                    "source_meta_sha256": sha256_file(target.meta_path),
                    "patch": patch_name,
                    "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                    "selected_player_fields": fields,
                    "capacity_skipped": skipped,
                    "operation_count": len(operations),
                }
            )
        manifest = {
            "schema": "squinch-nms-save-merge-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "source_slots": source_slots,
            "template_slot": template_slot,
            "target_slot": target_slot,
            "capacity_policy": capacity_policy,
            "selection": {
                "include_groups": sorted(includes),
                "exclude_groups": sorted(excludes),
                "include_fields": sorted(set(include_fields)),
                "exclude_fields": sorted(set(exclude_fields)),
                "identity_preserved": True,
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
            "source_slots": source_slots,
            "template_slot": template_slot,
            "target_slot": target_slot,
            "target_snapshots": len(targets),
            "capacity_skipped": {target["kind"]: target["capacity_skipped"] for target in targets},
        },
        artifacts,
    )


def _empty_fixed_rows(rows: list[Any], identity_field: str) -> list[Any]:
    template = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and not _text(row.get(identity_field))
            and not _text(
                (row.get("Ownership") or {}).get("Resource", {}).get("Filename")
                if isinstance(row.get("Ownership"), dict)
                else ""
            )
        ),
        None,
    )
    if template is None:
        return []
    return [copy.deepcopy(template) for _ in rows]


def _clear_clone_groups(document: dict[str, Any], groups: set[str]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    player = result["BaseContext"]["PlayerStateData"]
    if "bases" in groups:
        player["PersistentPlayerBases"] = []
        settlements = player.get("SettlementStatesV2")
        if isinstance(settlements, list):
            player["SettlementStatesV2"] = _empty_fixed_rows(settlements, "UniqueId")
        for field in ("SettlementHistory", "SettlementLocalSaveData", "TeleportEndpoints"):
            if isinstance(player.get(field), list):
                player[field] = []
        if "SettlementStateRingBufferIndexV2" in player:
            player["SettlementStateRingBufferIndexV2"] = 0
    if "starships" in groups:
        player["ShipOwnership"] = []
        archived = player.get("ArchivedShipOwnership")
        if isinstance(archived, list):
            player["ArchivedShipOwnership"] = _empty_fixed_rows(archived, "ArchivedName")
        if "PrimaryShip" in player:
            player["PrimaryShip"] = 0
        if isinstance(player.get("ShipUsesLegacyColours"), list):
            player["ShipUsesLegacyColours"] = []
    if "multitools" in groups:
        player["Multitools"] = []
        archived = player.get("ArchivedMultitools")
        if isinstance(archived, list):
            player["ArchivedMultitools"] = _empty_fixed_rows(archived, "ArchivedName")
        if "ActiveMultioolIndex" in player:
            player["ActiveMultioolIndex"] = 0
    return result


def _save_name(ordinal: int) -> str:
    return "save.hg" if ordinal == 1 else f"save{ordinal}.hg"


def clone_slot(
    directory: Path,
    mapping_path: Path,
    source_slot: int,
    destination_slot: int,
    save_name: str,
    clear_groups: list[str],
    *,
    apply: bool,
) -> dict[str, Any]:
    if not apply:
        raise SaveToolError("refusing to create a slot without the explicit --apply flag")
    groups = _validate_groups(clear_groups, "clear groups")
    if groups - {"bases", "starships", "multitools"}:
        raise SaveToolError("clone clearing supports bases, starships, and multitools")
    if (
        not 1 <= source_slot <= 10
        or not 1 <= destination_slot <= 10
        or source_slot == destination_slot
    ):
        raise SaveToolError("source and destination must be distinct slots between 1 and 10")
    if not save_name.strip():
        raise SaveToolError("new save name must be nonempty")
    running = _nms_processes()
    if running:
        raise SaveToolError(
            f"NMS.exe is running (PIDs {running}); stop the game before creating a slot"
        )
    profile = directory.expanduser().resolve()
    mapping = SaveMapping.load(mapping_path.expanduser().resolve())
    pairs = _slot_pairs(list_saves(profile))
    if source_slot not in pairs:
        raise SaveToolError(f"source slot {source_slot} does not exist")
    destination_names = [
        _save_name(destination_slot * 2 - 1),
        _save_name(destination_slot * 2),
    ]
    for name in destination_names:
        for path in (profile / name, profile / f"mf_{name}"):
            if path.exists() or path.is_symlink():
                raise SaveToolError(f"destination slot {destination_slot} is not empty: {path}")

    universal_id = f"0x{uuid.uuid4().int & ((1 << 64) - 1):016X}"
    prepared = []
    for kind, destination_name in zip(("auto", "manual"), destination_names, strict=True):
        source = pairs[source_slot][kind]
        raw_data = source.path.read_bytes()
        raw_meta = source.meta_path.read_bytes()
        decoded = decode_file(source.path)
        meta_info = inspect_meta_bytes(raw_meta, source.path)
        size_mode = _metadata_size_mode(meta_info, decoded.decompressed_size, len(raw_data))
        semantic = mapping.deobfuscate(decoded.document)
        desired = _clear_clone_groups(semantic, groups)
        desired["CommonStateData"]["SaveName"] = save_name
        desired["CommonStateData"]["SaveUniversalId"] = universal_id
        new_raw = mapping.obfuscate(desired)
        data, decompressed_size = encode_document(new_raw)
        meta, _info = update_meta(
            raw_meta,
            source.path,
            decompressed_size=decompressed_size,
            compressed_size=len(data),
            size_mode=size_mode,
        )
        meta = rename_meta(meta, source.path, save_name)
        destination = profile / destination_name
        meta = rekey_meta(meta, source.path, destination)
        prepared.append(
            {
                "kind": kind,
                "source": source,
                "destination": destination,
                "destination_meta": destination.with_name(f"mf_{destination.name}"),
                "data": data,
                "meta": meta,
                "data_mode": source.path.stat().st_mode & 0o777,
                "meta_mode": source.meta_path.stat().st_mode & 0o777,
            }
        )

    workspace = Path(os.environ["SQUINCH_TRANCHE_WORKSPACE"]).resolve()
    evidence_root = workspace / "no-mans-sky/save-edit/created-slots"
    evidence_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence = evidence_root / (f"slot-{destination_slot}-{stamp}-{uuid.uuid4().hex[:8]}")
    evidence.mkdir(mode=0o700)
    installed = []
    try:
        entries = []
        for item in prepared:
            _write_new(evidence / item["destination"].name, item["data"])
            _write_new(evidence / item["destination_meta"].name, item["meta"])
            entries.append(
                {
                    "kind": item["kind"],
                    "source": str(item["source"].path),
                    "destination": str(item["destination"]),
                    "data_sha256": hashlib.sha256(item["data"]).hexdigest(),
                    "meta_sha256": hashlib.sha256(item["meta"]).hexdigest(),
                }
            )
        manifest = {
            "schema": "squinch-nms-save-clone-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "profile": str(profile),
            "source_slot": source_slot,
            "destination_slot": destination_slot,
            "save_name": save_name,
            "save_universal_id": universal_id,
            "cleared_groups": sorted(groups),
            "entries": entries,
        }
        _write_new(
            evidence / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )
        for item in prepared:
            _replace_bytes(item["data"], item["destination"], item["data_mode"])
            installed.append(item["destination"])
            _replace_bytes(item["meta"], item["destination_meta"], item["meta_mode"])
            installed.append(item["destination_meta"])
        for item in prepared:
            if (
                sha256_file(item["destination"]) != hashlib.sha256(item["data"]).hexdigest()
                or sha256_file(item["destination_meta"]) != hashlib.sha256(item["meta"]).hexdigest()
            ):
                raise SaveToolError(f"created slot verification failed: {item['destination']}")
            decode_file(item["destination"])
            info = inspect_meta_file(item["destination_meta"], item["destination"])
            if info.storage_slot != info.encrypted_slot:
                raise SaveToolError(
                    f"created metadata uses wrong slot key: {item['destination_meta']}"
                )
    except Exception as exc:
        for path in reversed(installed):
            path.unlink(missing_ok=True)
        raise SaveToolError(
            f"slot creation failed and installed files were removed: {exc}"
        ) from exc
    return {
        "created": True,
        "source_slot": source_slot,
        "destination_slot": destination_slot,
        "save_name": save_name,
        "cleared_groups": sorted(groups),
        "evidence": str(evidence),
        "manifest": str(evidence / "manifest.json"),
    }
