from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .codec import RawNumber, decode_file, serialize_document, serialize_json
from .errors import SaveToolError
from .mapping import MAPPING_VERSION, SaveMapping
from .meta import inspect_meta_file, summarize_meta_file
from .paths import SaveIdentity, list_saves, require_pair
from .policy import SavePolicy

INVENTORY_SCHEMA_VERSION = "2"


@dataclass
class _Occurrence:
    value: dict[str, Any]
    source: dict[str, Any]
    rank: tuple[int, int, int]
    revision_hash: str


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, RawNumber):
        try:
            return int(value.text, 0)
        except ValueError:
            return None
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _enum(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("PersistentBaseTypes", "BaseType", "value", "Value"):
            if isinstance(value.get(key), str):
                return value[key]
    return "Unknown"


def _hash_value(value: Any) -> str:
    return hashlib.sha256(serialize_document({"value": value})).hexdigest()


def _seed(value: Any) -> str | None:
    if not isinstance(value, list) or len(value) < 2 or value[0] is not True:
        return None
    seed = _text(value[1])
    return seed if seed and seed.lower() not in {"0", "0x0"} else None


def _galaxy(address: Any) -> int | None:
    packed = _integer(address)
    if packed is None or packed == 0:
        return None
    return ((packed >> 32) & 0xFF) + 1


def _contexts(document: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result = []
    for name, value in document.items():
        if isinstance(value, dict) and isinstance(value.get("PlayerStateData"), dict):
            result.append((name, value["PlayerStateData"]))
    return result


def _base_identity(base: dict[str, Any]) -> tuple[str, str]:
    base_type = _enum(base.get("BaseType"))
    owner = base.get("Owner") if isinstance(base.get("Owner"), dict) else {}
    owner_id = _text(owner.get("UID")) or _text(owner.get("LID"))
    created = _integer(owner.get("TS"))
    if owner_id and created is not None and created > 0:
        return f"owner:{owner_id}:created:{created}:type:{base_type}", "high"
    fallback = {
        "owner": owner_id,
        "type": base_type,
        "galactic_address": base.get("GalacticAddress"),
        "position": base.get("Position"),
    }
    return f"location:{_hash_value(fallback)}", "medium"


def _ship_payload(value: dict[str, Any], archived: bool) -> dict[str, Any]:
    if archived and isinstance(value.get("Ownership"), dict):
        return value["Ownership"]
    return value


def _tool_payload(value: dict[str, Any], archived: bool) -> dict[str, Any]:
    if archived and isinstance(value.get("MultitoolData"), dict):
        return value["MultitoolData"]
    return value


def _equipment_identity(
    value: dict[str, Any], *, kind: str, archived: bool
) -> tuple[str | None, str]:
    payload = _ship_payload(value, archived) if kind == "ship" else _tool_payload(value, archived)
    resource = payload.get("Resource") if isinstance(payload.get("Resource"), dict) else {}
    seed = _seed(resource.get("Seed")) if kind == "ship" else _seed(payload.get("Seed"))
    filename = _text(resource.get("Filename"))
    if seed:
        return f"seed:{seed}:resource:{filename}", "high"
    if filename:
        return f"resource-hash:{_hash_value(payload)}", "low"
    return None, "empty"


def _source(save: SaveIdentity, context: str, meta_timestamp: int | None) -> dict[str, Any]:
    return {
        "path": str(save.path),
        "ordinal": save.ordinal,
        "slot": save.slot,
        "kind": save.kind,
        "context": context,
        "meta_timestamp": meta_timestamp,
    }


def _record(
    records: dict[str, list[_Occurrence]],
    identity: str,
    value: dict[str, Any],
    source: dict[str, Any],
    *,
    updated: int = 0,
) -> None:
    timestamp = source.get("meta_timestamp")
    meta_timestamp = timestamp if isinstance(timestamp, int) else 0
    records.setdefault(identity, []).append(
        _Occurrence(
            value=value,
            source=source,
            rank=(updated, meta_timestamp, int(source["ordinal"])),
            revision_hash=_hash_value(value),
        )
    )


def _combine(
    records: dict[str, list[_Occurrence]],
    details: dict[str, dict[str, Any]],
    *,
    portable_base_types: frozenset[str],
) -> list[dict[str, Any]]:
    result = []
    for identity in sorted(records):
        occurrences = records[identity]
        latest = max(occurrences, key=lambda item: item.rank)
        detail = dict(details[identity])
        entity_kind = detail.pop("entity_kind")
        if entity_kind == "base":
            base_type = _enum(latest.value.get("BaseType"))
            detail.update(
                {
                    "name": _text(latest.value.get("Name")),
                    "base_type": base_type,
                    "portable": base_type in portable_base_types,
                    "galaxy": _galaxy(latest.value.get("GalacticAddress")),
                    "galactic_address": latest.value.get("GalacticAddress"),
                }
            )
        else:
            archived = latest.source.get("storage") == "archived"
            payload = (
                _ship_payload(latest.value, archived)
                if entity_kind == "ship"
                else _tool_payload(latest.value, archived)
            )
            resource = payload.get("Resource")
            resource = resource if isinstance(resource, dict) else {}
            detail.update(
                {
                    "name": _text(
                        latest.value.get("ArchivedName") if archived else payload.get("Name")
                    ),
                    "resource": _text(resource.get("Filename")),
                    "selected_storage": "archived" if archived else "active",
                }
            )
        sources = sorted(
            (item.source for item in occurrences),
            key=lambda item: (item["ordinal"], item["context"]),
        )
        occurrence_details = []
        for item in sorted(occurrences, key=lambda occurrence: occurrence.rank):
            occurrence = {
                **item.source,
                "revision_sha256": item.revision_hash,
                "update_timestamp": item.rank[0],
            }
            if entity_kind == "base":
                occurrence.update(
                    {
                        "name": _text(item.value.get("Name")),
                        "galaxy": _galaxy(item.value.get("GalacticAddress")),
                        "galactic_address": item.value.get("GalacticAddress"),
                        "position_sha256": _hash_value(item.value.get("Position")),
                    }
                )
            occurrence_details.append(occurrence)
        result.append(
            {
                "identity": identity,
                **detail,
                "revision_count": len({item.revision_hash for item in occurrences}),
                "occurrence_count": len(occurrences),
                "selected_revision_sha256": latest.revision_hash,
                "selected_source": latest.source,
                "sources": sources,
                "occurrences": occurrence_details,
                "data": latest.value,
            }
        )
    return result


def _workspace_output(path: Path) -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    workspace = Path(workspace_value).resolve()
    output = path.expanduser().resolve()
    try:
        output.relative_to(workspace)
    except ValueError as exc:
        raise SaveToolError(
            f"inventory output must be inside the selected tranche: {output}"
        ) from exc
    return output


def _write_artifacts(output: Path, values: dict[str, dict[str, Any]]) -> list[str]:
    if output.exists():
        raise SaveToolError(f"refusing to overwrite inventory output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        for name, value in values.items():
            path = temporary / name
            with path.open("xb") as stream:
                stream.write(serialize_json(value).encode("utf-8"))
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(temporary, output)
    except (OSError, SaveToolError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        if isinstance(exc, SaveToolError):
            raise
        raise SaveToolError(f"cannot write inventory artifacts: {exc}") from exc
    return [str(output / name) for name in values]


def _slot_diffs(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for slot in sorted({snapshot["slot"] for snapshot in snapshots}):
        members = [snapshot for snapshot in snapshots if snapshot["slot"] == slot]
        newest = max(
            members,
            key=lambda snapshot: (
                snapshot["meta_timestamp"] or 0,
                snapshot["kind"] == "auto",
            ),
        )
        by_kind = {snapshot["kind"]: snapshot for snapshot in members}
        entity_diffs = {}
        if "auto" in by_kind and "manual" in by_kind:
            for entity in ("bases", "starships", "multitools"):
                auto = set(by_kind["auto"]["entity_identities"][entity])
                manual = set(by_kind["manual"]["entity_identities"][entity])
                auto_revisions = by_kind["auto"]["entity_revisions"][entity]
                manual_revisions = by_kind["manual"]["entity_revisions"][entity]
                changed = [
                    {
                        "identity": identity,
                        "auto_revision_sha256": auto_revisions[identity],
                        "manual_revision_sha256": manual_revisions[identity],
                    }
                    for identity in sorted(auto & manual)
                    if auto_revisions[identity] != manual_revisions[identity]
                ]
                entity_diffs[entity] = {
                    "shared": sorted(auto & manual),
                    "auto_only": sorted(auto - manual),
                    "manual_only": sorted(manual - auto),
                    "changed_revisions": changed,
                    "equal": auto == manual and not changed,
                }
        result.append(
            {
                "slot": slot,
                "newest": {
                    "path": newest["path"],
                    "kind": newest["kind"],
                    "meta_timestamp": newest["meta_timestamp"],
                },
                "members": [
                    {
                        "path": snapshot["path"],
                        "kind": snapshot["kind"],
                        "meta_timestamp": snapshot["meta_timestamp"],
                        "effective_save_name": snapshot["effective_save_name"],
                    }
                    for snapshot in members
                ],
                "pair_available": "auto" in by_kind and "manual" in by_kind,
                "entities": entity_diffs,
            }
        )
    return result


def _identity_audit(
    bases: list[dict[str, Any]],
    starships: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    location_collisions = []
    for base in bases:
        locations = {
            (str(item.get("galactic_address")), item.get("position_sha256"))
            for item in base["occurrences"]
        }
        if not base["portable"] and len(locations) > 1:
            location_collisions.append(
                {
                    "identity": base["identity"],
                    "name": base["name"],
                    "locations": [
                        {"galactic_address": address, "position_sha256": position}
                        for address, position in sorted(locations)
                    ],
                }
            )
    low_confidence = [
        {"kind": kind, "identity": item["identity"], "name": item["name"]}
        for kind, collection in (
            ("base", bases),
            ("starship", starships),
            ("multitool", tools),
        )
        for item in collection
        if item["identity_confidence"] != "high"
    ]
    return {
        "fixed_base_location_collisions": location_collisions,
        "low_confidence_identities": low_confidence,
        "summary": {
            "fixed_base_location_collisions": len(location_collisions),
            "low_confidence_identities": len(low_confidence),
            "bases_with_multiple_revisions": sum(item["revision_count"] > 1 for item in bases),
            "starships_with_multiple_revisions": sum(
                item["revision_count"] > 1 for item in starships
            ),
            "multitools_with_multiple_revisions": sum(item["revision_count"] > 1 for item in tools),
        },
    }


def build_inventory(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    policy_path: Path | None = None,
    snapshot_selection: str = "all",
    archives: str = "include",
    cached: str = "summary",
) -> tuple[dict[str, Any], list[str]]:
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite inventory output: {output}")
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    saves = list_saves(profile)
    if not saves:
        raise SaveToolError(f"no NMS saves found in {profile}")

    if snapshot_selection not in {"all", "auto", "manual", "newest"}:
        raise SaveToolError("snapshot selection must be all, auto, manual, or newest")
    if archives not in {"include", "exclude", "only"}:
        raise SaveToolError("archives must be include, exclude, or only")
    if cached not in {"summary", "include"}:
        raise SaveToolError("cached bases must be summary or include")
    meta_by_path = {}
    for save in saves:
        require_pair(save)
        inspect_meta_file(save.meta_path, save.path)
        meta_by_path[save.path] = summarize_meta_file(save.meta_path, save.path)
    if snapshot_selection in {"auto", "manual"}:
        saves = [save for save in saves if save.kind == snapshot_selection]
    elif snapshot_selection == "newest":
        selected = []
        for slot in sorted({save.slot for save in saves}):
            members = [save for save in saves if save.slot == slot]
            selected.append(
                max(
                    members,
                    key=lambda save: (
                        meta_by_path[save.path].timestamp or 0,
                        save.kind == "auto",
                    ),
                )
            )
        saves = selected

    base_records: dict[str, list[_Occurrence]] = {}
    base_details: dict[str, dict[str, Any]] = {}
    ship_records: dict[str, list[_Occurrence]] = {}
    ship_details: dict[str, dict[str, Any]] = {}
    tool_records: dict[str, list[_Occurrence]] = {}
    tool_details: dict[str, dict[str, Any]] = {}
    cached_records: dict[str, list[_Occurrence]] = {}
    cached_details: dict[str, dict[str, Any]] = {}
    snapshots: list[dict[str, Any]] = []
    excluded_base_types: Counter[str] = Counter()
    total_owned_occurrences = 0
    total_ship_occurrences = 0
    total_tool_occurrences = 0

    for save in saves:
        decoded = decode_file(save.path, require_714=False)
        meta = meta_by_path[save.path]
        document = mapping.deobfuscate(decoded.document)
        common = document.get("CommonStateData")
        common = common if isinstance(common, dict) else {}
        payload_name = _text(common.get("SaveName"))
        effective_name = payload_name or meta.save_name or ""
        classified = policy.classify(effective_name)
        classification, expected = classified.category, classified.galaxies
        context_summaries = []
        violations = []
        snapshot_base_ids: set[str] = set()
        snapshot_ship_ids: set[str] = set()
        snapshot_tool_ids: set[str] = set()
        snapshot_base_revisions: dict[str, str] = {}
        snapshot_ship_revisions: dict[str, str] = {}
        snapshot_tool_revisions: dict[str, str] = {}

        for context_name, player in _contexts(document):
            source = _source(save, context_name, meta.timestamp)
            bases = player.get("PersistentPlayerBases")
            bases = bases if isinstance(bases, list) else []
            owned_count = 0
            excluded_count = 0
            for base in bases:
                if not isinstance(base, dict):
                    continue
                base_type = _enum(base.get("BaseType"))
                if base_type not in policy.owned_base_types:
                    excluded_base_types[base_type] += 1
                    excluded_count += 1
                    if cached == "include":
                        identity, confidence = _base_identity(base)
                        _record(cached_records, identity, base, source)
                        cached_details.setdefault(
                            identity,
                            {
                                "entity_kind": "base",
                                "identity_confidence": confidence,
                                "name": _text(base.get("Name")),
                                "base_type": base_type,
                                "portable": False,
                                "galaxy": _galaxy(base.get("GalacticAddress")),
                                "galactic_address": base.get("GalacticAddress"),
                            },
                        )
                    continue
                owned_count += 1
                total_owned_occurrences += 1
                identity, confidence = _base_identity(base)
                address = base.get("GalacticAddress")
                galaxy = _galaxy(address)
                updated = _integer(base.get("LastUpdateTimestamp")) or 0
                portable = base_type in policy.portable_base_types
                _record(base_records, identity, base, source, updated=updated)
                snapshot_base_ids.add(identity)
                snapshot_base_revisions[identity] = _hash_value(base)
                base_details.setdefault(
                    identity,
                    {
                        "entity_kind": "base",
                        "identity_confidence": confidence,
                        "name": _text(base.get("Name")),
                        "base_type": base_type,
                        "portable": portable,
                        "galaxy": galaxy,
                        "galactic_address": address,
                    },
                )
                if expected and not portable and galaxy is not None:
                    low, high = expected
                    if not low <= galaxy <= high:
                        violations.append(
                            {
                                "identity": identity,
                                "name": _text(base.get("Name")),
                                "base_type": base_type,
                                "galaxy": galaxy,
                                "expected": {"first": low, "last": high},
                                "context": context_name,
                            }
                        )

            ship_counts = {"active": 0, "archived": 0}
            ship_fields = []
            if archives != "only":
                ship_fields.append(("ShipOwnership", False))
            if archives != "exclude":
                ship_fields.append(("ArchivedShipOwnership", True))
            for field, archived in ship_fields:
                rows = player.get(field)
                rows = rows if isinstance(rows, list) else []
                for value in rows:
                    if not isinstance(value, dict):
                        continue
                    identity, confidence = _equipment_identity(
                        value, kind="ship", archived=archived
                    )
                    if identity is None:
                        continue
                    total_ship_occurrences += 1
                    snapshot_ship_ids.add(identity)
                    snapshot_ship_revisions[identity] = _hash_value(value)
                    ship_counts["archived" if archived else "active"] += 1
                    equipment_source = {
                        **source,
                        "storage": "archived" if archived else "active",
                    }
                    _record(ship_records, identity, value, equipment_source)
                    payload = _ship_payload(value, archived)
                    resource = payload.get("Resource")
                    resource = resource if isinstance(resource, dict) else {}
                    ship_details.setdefault(
                        identity,
                        {
                            "entity_kind": "ship",
                            "identity_confidence": confidence,
                            "name": _text(
                                value.get("ArchivedName") if archived else payload.get("Name")
                            ),
                            "resource": _text(resource.get("Filename")),
                            "selected_storage": "archived" if archived else "active",
                        },
                    )

            tool_counts = {"active": 0, "archived": 0}
            tool_fields = []
            if archives != "only":
                tool_fields.append(("Multitools", False))
            if archives != "exclude":
                tool_fields.append(("ArchivedMultitools", True))
            for field, archived in tool_fields:
                rows = player.get(field)
                rows = rows if isinstance(rows, list) else []
                for value in rows:
                    if not isinstance(value, dict):
                        continue
                    identity, confidence = _equipment_identity(
                        value, kind="multitool", archived=archived
                    )
                    if identity is None:
                        continue
                    total_tool_occurrences += 1
                    snapshot_tool_ids.add(identity)
                    snapshot_tool_revisions[identity] = _hash_value(value)
                    tool_counts["archived" if archived else "active"] += 1
                    equipment_source = {
                        **source,
                        "storage": "archived" if archived else "active",
                    }
                    _record(tool_records, identity, value, equipment_source)
                    payload = _tool_payload(value, archived)
                    resource = payload.get("Resource")
                    resource = resource if isinstance(resource, dict) else {}
                    tool_details.setdefault(
                        identity,
                        {
                            "entity_kind": "multitool",
                            "identity_confidence": confidence,
                            "name": _text(
                                value.get("ArchivedName") if archived else payload.get("Name")
                            ),
                            "resource": _text(resource.get("Filename")),
                            "selected_storage": "archived" if archived else "active",
                        },
                    )
            context_summaries.append(
                {
                    "name": context_name,
                    "owned_bases": owned_count,
                    "excluded_cached_bases": excluded_count,
                    "starships": ship_counts,
                    "multitools": tool_counts,
                }
            )

        snapshots.append(
            {
                "path": str(save.path),
                "meta_path": str(save.meta_path),
                "ordinal": save.ordinal,
                "slot": save.slot,
                "kind": save.kind,
                "payload_version": document.get("Version"),
                "active_context": document.get("ActiveContext"),
                "payload_save_name": payload_name,
                "metadata_save_name": meta.save_name or "",
                "effective_save_name": effective_name,
                "classification": classification,
                "policy_rule": classified.rule,
                "expected_galaxies": (
                    {"first": expected[0], "last": expected[1]} if expected else None
                ),
                "range_status": (
                    "not-applicable"
                    if expected is None
                    else ("violations" if violations else "clean")
                ),
                "range_violations": violations,
                "contexts": context_summaries,
                "meta_timestamp": meta.timestamp,
                "data_sha256": hashlib.sha256(save.path.read_bytes()).hexdigest(),
                "meta_sha256": hashlib.sha256(save.meta_path.read_bytes()).hexdigest(),
                "entity_identities": {
                    "bases": sorted(snapshot_base_ids),
                    "starships": sorted(snapshot_ship_ids),
                    "multitools": sorted(snapshot_tool_ids),
                },
                "entity_revisions": {
                    "bases": dict(sorted(snapshot_base_revisions.items())),
                    "starships": dict(sorted(snapshot_ship_revisions.items())),
                    "multitools": dict(sorted(snapshot_tool_revisions.items())),
                },
            }
        )

    slots = []
    for slot in sorted({snapshot["slot"] for snapshot in snapshots}):
        members = [snapshot for snapshot in snapshots if snapshot["slot"] == slot]
        payload_names = sorted(
            {snapshot["payload_save_name"] for snapshot in members if snapshot["payload_save_name"]}
        )
        metadata_names = sorted(
            {
                snapshot["metadata_save_name"]
                for snapshot in members
                if snapshot["metadata_save_name"]
            }
        )
        effective_names = sorted({snapshot["effective_save_name"] for snapshot in members})
        classifications = sorted({snapshot["classification"] for snapshot in members})
        slots.append(
            {
                "slot": slot,
                "payload_names": payload_names,
                "metadata_names": metadata_names,
                "effective_names": effective_names,
                "classifications": classifications,
                "snapshot_ordinals": [snapshot["ordinal"] for snapshot in members],
                "pair_consistent": len(effective_names) == 1 and len(classifications) == 1,
            }
        )

    bases = _combine(base_records, base_details, portable_base_types=policy.portable_base_types)
    starships = _combine(ship_records, ship_details, portable_base_types=policy.portable_base_types)
    tools = _combine(tool_records, tool_details, portable_base_types=policy.portable_base_types)
    cached_bases = _combine(
        cached_records, cached_details, portable_base_types=policy.portable_base_types
    )
    unique_base_types = Counter(item["base_type"] for item in bases)
    selected_ship_storage = Counter(item["selected_storage"] for item in starships)
    selected_tool_storage = Counter(item["selected_storage"] for item in tools)
    header = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "mapping_version": MAPPING_VERSION,
        "mapping_path": str(mapping_file),
        "mapping_sha256": hashlib.sha256(mapping_file.read_bytes()).hexdigest(),
        "profile": str(profile),
        "policy": {"source": policy.source, "sha256": policy.sha256},
        "selection": {
            "snapshots": snapshot_selection,
            "archives": archives,
            "cached": cached,
        },
    }
    non_galaxy_slots = [
        slot
        for slot in slots
        if any(value in {"non-galaxy-centric", "unnamed"} for value in slot["classifications"])
    ]
    violated = [snapshot for snapshot in snapshots if snapshot["range_violations"]]
    slot_diffs = _slot_diffs(snapshots)
    identity_audit = _identity_audit(bases, starships, tools)
    artifacts = {
        "saves.json": {
            **header,
            "snapshot_count": len(snapshots),
            "slot_count": len(slots),
            "snapshots": snapshots,
            "slots": slots,
        },
        "bases.json": {
            **header,
            "scope": "player-owned persistent bases",
            "owned_base_types": sorted(policy.owned_base_types),
            "unique_count": len(bases),
            "occurrence_count": total_owned_occurrences,
            "unique_types": dict(sorted(unique_base_types.items())),
            "excluded_cached_occurrence_count": sum(excluded_base_types.values()),
            "excluded_cached_types": dict(sorted(excluded_base_types.items())),
            "bases": bases,
        },
        "starships.json": {
            **header,
            "scope": "active and archived owned starships",
            "unique_count": len(starships),
            "occurrence_count": total_ship_occurrences,
            "selected_storage": dict(sorted(selected_ship_storage.items())),
            "starships": starships,
        },
        "multitools.json": {
            **header,
            "scope": "active and archived owned multitools",
            "unique_count": len(tools),
            "occurrence_count": total_tool_occurrences,
            "selected_storage": dict(sorted(selected_tool_storage.items())),
            "multitools": tools,
        },
        "report.json": {
            **header,
            "summary": {
                "save_snapshots": len(snapshots),
                "logical_slots": len(slots),
                "unique_bases": len(bases),
                "unique_starships": len(starships),
                "unique_multitools": len(tools),
                "snapshots_with_range_violations": len(violated),
                "non_galaxy_centric_slots": len(non_galaxy_slots),
            },
            "range_violations": [
                {
                    "path": snapshot["path"],
                    "slot": snapshot["slot"],
                    "kind": snapshot["kind"],
                    "save_name": snapshot["effective_save_name"],
                    "violations": snapshot["range_violations"],
                }
                for snapshot in violated
            ],
            "non_galaxy_centric_slots": non_galaxy_slots,
            "special_galaxy_slots": [
                slot for slot in slots if "single-galaxy-special" in slot["classifications"]
            ],
            "inconsistent_pairs": [slot for slot in slots if not slot["pair_consistent"]],
            "deduplication": {
                "base_occurrences": total_owned_occurrences,
                "unique_bases": len(bases),
                "starship_occurrences": total_ship_occurrences,
                "unique_starships": len(starships),
                "multitool_occurrences": total_tool_occurrences,
                "unique_multitools": len(tools),
            },
        },
        "slot-diffs.json": {
            **header,
            "slots": slot_diffs,
        },
        "identity-audit.json": {
            **header,
            **identity_audit,
        },
    }
    if cached == "include":
        artifacts["cached-bases.json"] = {
            **header,
            "scope": "cached non-owned persistent bases",
            "unique_count": len(cached_bases),
            "occurrence_count": sum(excluded_base_types.values()),
            "bases": cached_bases,
        }
    artifact_paths = _write_artifacts(output, artifacts)
    result = {
        "profile": str(profile),
        "output_directory": str(output),
        **artifacts["report.json"]["summary"],
    }
    return result, artifact_paths
