from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .cleanup import SYSTEM_ADDRESS_MASK, _integer_address, _replace, _system_address
from .codec import decode_file, serialize_json
from .errors import SaveToolError
from .inventory import _hash_value, _integer, _text
from .jsonops import apply_patch
from .mapping import SaveMapping
from .meta import inspect_meta_file, summarize_meta_file
from .paths import list_saves
from .policy import SavePolicy
from .stage import sha256_file
from .sync import _slot_pairs, _workspace_output

COLLECTIONS = {
    "stored": ("DiscoveryManagerData", "DiscoveryData-v1", "Store", "Record"),
    "available": ("DiscoveryManagerData", "DiscoveryData-v1", "Available"),
    "enqueued": ("DiscoveryManagerData", "DiscoveryData-v1", "Enqueued"),
}


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write discovery artifact {path}: {exc}") from exc


def _nested(document: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = document
    for field in path:
        if not isinstance(value, dict):
            return None
        value = value.get(field)
    return value


def _record_identity(record: Any) -> str:
    discovery = record.get("DD") if isinstance(record, dict) else None
    if not isinstance(discovery, dict) or _system_address(record) is None:
        raise SaveToolError("discovery record has no valid DD identity/system address")
    return f"discovery:{_hash_value(discovery)}"


def _record_timestamp(record: Any) -> int:
    owner = record.get("OWS") if isinstance(record, dict) else None
    return _integer(owner.get("TS")) or 0 if isinstance(owner, dict) else 0


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(source["path"]),
        "slot": source["slot"],
        "kind": source["kind"],
        "ordinal": source["ordinal"],
        "meta_timestamp": source["meta_timestamp"],
    }


def _owner_slots(
    ranges: dict[int, tuple[int, int]],
) -> tuple[dict[int, int], dict[int, list[int]]]:
    owners: dict[int, int] = {}
    candidates_by_galaxy: dict[int, list[int]] = {}
    for galaxy in range(1, 257):
        candidates = [slot for slot, (first, last) in ranges.items() if first <= galaxy <= last]
        candidates_by_galaxy[galaxy] = sorted(candidates)
        if not candidates:
            continue
        widths = {slot: ranges[slot][1] - ranges[slot][0] for slot in candidates}
        narrowest = min(widths.values())
        winners = [slot for slot in candidates if widths[slot] == narrowest]
        if len(winners) != 1:
            raise SaveToolError(
                f"galaxy {galaxy} has ambiguous equally specific save slots: {winners}"
            )
        owners[galaxy] = winners[0]
    return owners, candidates_by_galaxy


def create_discovery_redistribution_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    target_slots: list[int],
    name_overrides: list[str],
    policy_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    if (
        not target_slots
        or len(set(target_slots)) != len(target_slots)
        or any(not 1 <= slot <= 10 for slot in target_slots)
    ):
        raise SaveToolError("target slots must be unique values between 1 and 10")
    overrides: dict[int, str] = {}
    for value in name_overrides:
        slot_text, separator, name = value.partition("=")
        try:
            slot = int(slot_text)
        except ValueError as exc:
            raise SaveToolError("name overrides must use SLOT=NAME") from exc
        if not separator or slot not in target_slots or not name.strip() or slot in overrides:
            raise SaveToolError("name overrides must be unique target SLOT=NAME values")
        overrides[slot] = name.strip()
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite discovery output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if any(slot not in pairs for slot in target_slots):
        raise SaveToolError("discovery target slots must exist as complete pairs")

    sources: list[dict[str, Any]] = []
    ranges: dict[int, tuple[int, int]] = {}
    for slot in target_slots:
        names = set()
        for kind in ("auto", "manual"):
            save = pairs[slot][kind]
            inspect_meta_file(save.meta_path, save.path)
            raw = decode_file(save.path).document
            semantic = mapping.deobfuscate(raw)
            common = semantic.get("CommonStateData")
            name = _text(common.get("SaveName")) if isinstance(common, dict) else ""
            names.add(name)
            meta = summarize_meta_file(save.meta_path, save.path)
            sources.append(
                {
                    "path": save.path,
                    "meta_path": save.meta_path,
                    "slot": slot,
                    "kind": kind,
                    "ordinal": save.ordinal,
                    "meta_timestamp": meta.timestamp,
                    "raw": raw,
                    "semantic": semantic,
                }
            )
        if len(names) != 1:
            raise SaveToolError(f"slot {slot} Auto/Manual save names differ")
        effective_name = overrides.get(slot, next(iter(names)))
        effective = policy.classify(effective_name)
        if effective.galaxies is None:
            raise SaveToolError(f"slot {slot} is not one galaxy-classified save pair")
        ranges[slot] = effective.galaxies

    owner_by_galaxy, candidates_by_galaxy = _owner_slots(ranges)
    missing = [galaxy for galaxy in range(1, 257) if galaxy not in owner_by_galaxy]
    if missing:
        raise SaveToolError(
            "target slots do not cover every galaxy; missing "
            + ", ".join(str(value) for value in missing)
        )

    candidates: dict[str, dict[str, list[dict[str, Any]]]] = {
        collection: {} for collection in COLLECTIONS
    }
    visited_sources: dict[int, set[tuple[int, str, int]]] = {}
    for source in sources:
        semantic = source["semantic"]
        for collection, path in COLLECTIONS.items():
            rows = _nested(semantic, path)
            if not isinstance(rows, list):
                raise SaveToolError(f"{source['path']} has no complete {collection} records")
            for record in rows:
                identity = _record_identity(record)
                candidates[collection].setdefault(identity, []).append(
                    {
                        "record": record,
                        "revision": _hash_value(record),
                        "rank": (
                            _record_timestamp(record),
                            source["meta_timestamp"],
                            source["ordinal"],
                        ),
                        "source": source,
                    }
                )
        player = _nested(semantic, ("BaseContext", "PlayerStateData"))
        history = player.get("VisitedSystems") if isinstance(player, dict) else None
        if not isinstance(history, list) or not history:
            raise SaveToolError(f"{source['path']} has no fixed VisitedSystems history")
        for value in history:
            address = _integer_address(value)
            if address in (None, 0):
                continue
            canonical = address & SYSTEM_ADDRESS_MASK
            visited_sources.setdefault(canonical, set()).add(
                (source["slot"], source["kind"], source["ordinal"])
            )

    selected: dict[str, dict[str, dict[str, Any]]] = {}
    systems: dict[int, dict[str, Any]] = {}
    for collection, identities in candidates.items():
        selected[collection] = {}
        for identity, values in identities.items():
            winner = max(values, key=lambda item: (*item["rank"], item["revision"]))
            record = copy.deepcopy(winner["record"])
            address = _system_address(record)
            assert address is not None
            galaxy = ((address >> 32) & 0xFF) + 1
            revisions = sorted({item["revision"] for item in values})
            source_rows = sorted(
                {
                    (
                        item["source"]["slot"],
                        item["source"]["kind"],
                        item["source"]["ordinal"],
                        str(item["source"]["path"]),
                        item["source"]["meta_timestamp"],
                    )
                    for item in values
                }
            )
            authority_record = {
                "identity": identity,
                "data": record,
                "selected_revision_sha256": winner["revision"],
                "revision_count": len(revisions),
                "occurrence_count": len(values),
                "selected_source": _source_summary(winner["source"]),
                "sources": [
                    {
                        "slot": slot,
                        "kind": kind,
                        "ordinal": ordinal,
                        "path": path,
                        "meta_timestamp": timestamp,
                    }
                    for slot, kind, ordinal, path, timestamp in source_rows
                ],
            }
            selected[collection][identity] = {
                "record": record,
                "address": address,
                "galaxy": galaxy,
                "authority": authority_record,
            }
            system = systems.setdefault(
                address,
                {
                    "identity": f"system:0x{address:X}",
                    "system_address": f"0x{address:X}",
                    "galaxy": galaxy,
                    "visited": False,
                    "visited_sources": [],
                    "records": {name: [] for name in COLLECTIONS},
                },
            )
            system["records"][collection].append(authority_record)

    for address, provenance in visited_sources.items():
        galaxy = ((address >> 32) & 0xFF) + 1
        system = systems.setdefault(
            address,
            {
                "identity": f"system:0x{address:X}",
                "system_address": f"0x{address:X}",
                "galaxy": galaxy,
                "visited": False,
                "visited_sources": [],
                "records": {name: [] for name in COLLECTIONS},
            },
        )
        system["visited"] = True
        system["visited_sources"] = [
            {"slot": slot, "kind": kind, "ordinal": ordinal}
            for slot, kind, ordinal in sorted(provenance)
        ]

    for system in systems.values():
        for records in system["records"].values():
            records.sort(key=lambda item: item["identity"])

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(mode=0o700)
    targets = []
    try:
        for source in sources:
            slot = source["slot"]
            semantic = source["semantic"]
            operations: list[dict[str, Any]] = []
            common = semantic.get("CommonStateData")
            if not isinstance(common, dict):
                raise SaveToolError(f"{source['path']} has no CommonStateData")
            old_name = common.get("SaveName")
            if not isinstance(old_name, str):
                raise SaveToolError(f"{source['path']} has no SaveName")
            metadata_save_name = overrides.get(slot)
            if metadata_save_name is not None:
                _replace(
                    operations,
                    mapping,
                    ("CommonStateData", "SaveName"),
                    old_name,
                    metadata_save_name,
                )
            counts = {}
            for collection, path in COLLECTIONS.items():
                current = _nested(semantic, path)
                desired_items = [
                    value
                    for value in selected[collection].values()
                    if owner_by_galaxy[value["galaxy"]] == slot
                ]
                desired_items.sort(
                    key=lambda item: (
                        item["address"],
                        _text(item["record"].get("DD", {}).get("DT")),
                        _record_identity(item["record"]),
                    )
                )
                desired = [copy.deepcopy(item["record"]) for item in desired_items]
                _replace(operations, mapping, path, current, desired)
                counts[collection] = len(desired)
            player = _nested(semantic, ("BaseContext", "PlayerStateData"))
            history = player.get("VisitedSystems") if isinstance(player, dict) else None
            assert isinstance(history, list)
            routed_history = sorted(
                address
                for address in visited_sources
                if owner_by_galaxy[((address >> 32) & 0xFF) + 1] == slot
            )
            if len(routed_history) > len(history):
                raise SaveToolError(
                    f"slot {slot} needs {len(routed_history)} visited systems but has capacity "
                    f"{len(history)}"
                )
            desired_history = [*routed_history, *([0] * (len(history) - len(routed_history)))]
            _replace(
                operations,
                mapping,
                ("BaseContext", "PlayerStateData", "VisitedSystems"),
                history,
                desired_history,
            )
            apply_patch(source["raw"], operations)
            patch_name = f"slot-{slot}-{source['kind']}.patch.json"
            patch_raw = (serialize_json(operations) + "\n").encode()
            _write_new(temporary / patch_name, patch_raw)
            targets.append(
                {
                    "slot": slot,
                    "kind": source["kind"],
                    "source": str(source["path"]),
                    "source_data_sha256": sha256_file(source["path"]),
                    "source_meta_sha256": sha256_file(source["meta_path"]),
                    "patch": patch_name,
                    "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                    "operation_count": len(operations),
                    "old_save_name": old_name,
                    "new_save_name": metadata_save_name,
                    "metadata_save_name": metadata_save_name,
                    "owned_galaxies": [
                        galaxy for galaxy, owner in sorted(owner_by_galaxy.items()) if owner == slot
                    ],
                    "record_counts": counts,
                    "visited_system_count": len(routed_history),
                }
            )

        authority = {
            "schema": "squinch-nms-systems-library-v1",
            "profile": str(profile),
            "mapping": {
                "path": str(mapping_file),
                "sha256": sha256_file(mapping_file),
                "version": mapping.version,
            },
            "policy": {"source": policy.source, "sha256": policy.sha256},
            "source_snapshots": [
                {
                    **_source_summary(source),
                    "data_sha256": sha256_file(source["path"]),
                    "meta_sha256": sha256_file(source["meta_path"]),
                }
                for source in sources
            ],
            "unique_count": len(systems),
            "record_counts": {collection: len(values) for collection, values in selected.items()},
            "visited_system_count": len(visited_sources),
            "ownership": {
                "rule": "narrowest-galaxy-range-wins",
                "slots": {
                    str(slot): {
                        "declared_range": {"first": first, "last": last},
                        "owned_galaxies": [
                            galaxy
                            for galaxy, owner in sorted(owner_by_galaxy.items())
                            if owner == slot
                        ],
                    }
                    for slot, (first, last) in sorted(ranges.items())
                },
                "overlaps": {
                    str(galaxy): candidates
                    for galaxy, candidates in candidates_by_galaxy.items()
                    if len(candidates) > 1
                },
            },
            "systems": sorted(
                systems.values(), key=lambda item: (item["galaxy"], item["system_address"])
            ),
        }
        systems_raw = (serialize_json(authority) + "\n").encode()
        _write_new(temporary / "systems.json", systems_raw)
        manifest = {
            "schema": "squinch-nms-discovery-redistribution-v1",
            "profile": str(profile),
            "mapping": authority["mapping"],
            "policy": authority["policy"],
            "target_slots": target_slots,
            "ownership": authority["ownership"],
            "systems": {
                "file": "systems.json",
                "sha256": hashlib.sha256(systems_raw).hexdigest(),
                "unique_count": len(systems),
                "record_counts": authority["record_counts"],
                "visited_system_count": len(visited_sources),
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

    artifacts = [
        str(output / "manifest.json"),
        str(output / "systems.json"),
        *[str(output / target["patch"]) for target in targets],
    ]
    return (
        {
            "output_directory": str(output),
            "target_slots": target_slots,
            "target_snapshots": len(targets),
            "unique_systems": len(systems),
            "record_counts": authority["record_counts"],
            "visited_systems": len(visited_sources),
            "patch_operations": sum(target["operation_count"] for target in targets),
        },
        artifacts,
    )
