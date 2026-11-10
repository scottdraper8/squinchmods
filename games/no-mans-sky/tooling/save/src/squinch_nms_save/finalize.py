from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .codec import decode_file, serialize_json
from .errors import SaveToolError
from .inventory import _base_identity, _enum, _galaxy, _hash_value, _integer, _text
from .jsonops import apply_patch, escape_pointer
from .mapping import SaveMapping
from .meta import inspect_meta_file, summarize_meta_file
from .paths import list_saves, require_pair
from .policy import SavePolicy
from .stage import sha256_file

NUMBER_PREFIX = re.compile(r"^(\d+)(?:\.(\d+))?\.?\s+")


def _workspace_output(path: Path) -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(Path(workspace_value).resolve())
    except ValueError as exc:
        raise SaveToolError(f"finalization output must be inside the tranche: {resolved}") from exc
    return resolved


def _write_new(path: Path, value: str) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(value.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write finalization artifact {path}: {exc}") from exc


def _strip_number(name: str) -> str:
    match = NUMBER_PREFIX.match(name)
    return name[match.end() :] if match else name


def _old_order(name: str, galaxy: int) -> tuple[int, str]:
    match = NUMBER_PREFIX.match(name)
    if match and int(match.group(1)) == galaxy:
        return (int(match.group(2) or 0), _strip_number(name).casefold())
    return (1_000_000, _strip_number(name).casefold())


def _numbered(galaxy: int, index: int, title: str) -> str:
    prefix = f"{galaxy}." if index == 0 else f"{galaxy}.{index}"
    return f"{prefix} {title}".rstrip()


def _settlement_identity(value: dict[str, Any]) -> str | None:
    unique = _text(value.get("UniqueId"))
    return f"settlement:{unique}" if unique else None


def _owner_id(documents: list[dict[str, Any]], policy: SavePolicy) -> str:
    owners: Counter[str] = Counter()
    for document in documents:
        for context in document.values():
            if not isinstance(context, dict) or not isinstance(
                context.get("PlayerStateData"), dict
            ):
                continue
            player = context["PlayerStateData"]
            bases = player.get("PersistentPlayerBases")
            for base in bases if isinstance(bases, list) else []:
                if (
                    not isinstance(base, dict)
                    or _enum(base.get("BaseType")) not in policy.owned_base_types
                ):
                    continue
                owner = base.get("Owner") if isinstance(base.get("Owner"), dict) else {}
                uid = _text(owner.get("UID")) or _text(owner.get("LID"))
                if uid:
                    owners[uid] += 1
    if not owners:
        raise SaveToolError("cannot infer the player owner ID from owned bases")
    return owners.most_common(1)[0][0]


def _settlement_template(documents: list[dict[str, Any]]) -> dict[str, Any]:
    for document in documents:
        for context in document.values():
            if not isinstance(context, dict) or not isinstance(
                context.get("PlayerStateData"), dict
            ):
                continue
            rows = context["PlayerStateData"].get("SettlementStatesV2")
            for row in rows if isinstance(rows, list) else []:
                if (
                    isinstance(row, dict)
                    and not _text(row.get("UniqueId"))
                    and (_integer(row.get("UniverseAddress")) or 0) == 0
                ):
                    return copy.deepcopy(row)
    raise SaveToolError("profile has no empty settlement template slot")


def _canonical_settlements(
    documents: list[dict[str, Any]], owner_id: str
) -> dict[str, dict[str, Any]]:
    candidates: dict[str, list[tuple[tuple[int, int], dict[str, Any]]]] = {}
    for ordinal, document in enumerate(documents, start=1):
        for context in document.values():
            if not isinstance(context, dict) or not isinstance(
                context.get("PlayerStateData"), dict
            ):
                continue
            rows = context["PlayerStateData"].get("SettlementStatesV2")
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                owner = row.get("Owner") if isinstance(row.get("Owner"), dict) else {}
                if (_text(owner.get("UID")) or _text(owner.get("LID"))) != owner_id:
                    continue
                identity = _settlement_identity(row)
                galaxy = _galaxy(row.get("UniverseAddress"))
                if identity is None or galaxy is None:
                    continue
                rank = (_integer(row.get("DbTimestamp")) or 0, ordinal)
                candidates.setdefault(identity, []).append((rank, row))
    return {
        identity: copy.deepcopy(max(values, key=lambda item: item[0])[1])
        for identity, values in candidates.items()
    }


def _desired_settlements(
    canonical: dict[str, dict[str, Any]], first: int, last: int
) -> list[tuple[str, dict[str, Any], int]]:
    result = []
    for identity, value in canonical.items():
        galaxy = _galaxy(value.get("UniverseAddress"))
        if galaxy is not None and first <= galaxy <= last:
            result.append((identity, copy.deepcopy(value), galaxy))
    return sorted(result, key=lambda item: (item[2], _strip_number(_text(item[1].get("Name")))))


def _rewrite_settlements(
    rows: list[Any],
    desired: list[tuple[str, dict[str, Any], int]],
    owner_id: str,
    template: dict[str, Any],
) -> tuple[list[Any], dict[int, int], list[dict[str, Any]]]:
    result = copy.deepcopy(rows)
    existing_indices: dict[str, int] = {}
    reusable = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        owner = row.get("Owner") if isinstance(row.get("Owner"), dict) else {}
        row_owner = _text(owner.get("UID")) or _text(owner.get("LID"))
        identity = _settlement_identity(row)
        if row_owner == owner_id:
            if identity:
                existing_indices[identity] = index
            result[index] = copy.deepcopy(template)
            reusable.append(index)
        elif identity is None and (_integer(row.get("UniverseAddress")) or 0) == 0:
            reusable.append(index)
    available = iter(sorted(set(reusable)))
    used: set[int] = set()
    per_galaxy: dict[int, list[tuple[str, dict[str, Any], int]]] = {}
    for item in desired:
        per_galaxy.setdefault(item[2], []).append(item)
    galaxy_counts: dict[int, int] = {}
    changes = []
    for galaxy in sorted(per_galaxy):
        settlements = per_galaxy[galaxy]
        galaxy_counts[galaxy] = len(settlements)
        for number, (identity, value, _galaxy_number) in enumerate(settlements):
            index = existing_indices.get(identity)
            if index is None or index in used:
                try:
                    index = next(candidate for candidate in available if candidate not in used)
                except StopIteration as exc:
                    raise SaveToolError(
                        "settlement array has too few reusable slots for routed settlements"
                    ) from exc
            used.add(index)
            old_name = _text(value.get("Name"))
            new_name = _numbered(galaxy, number, _strip_number(old_name))
            value["Name"] = new_name
            result[index] = value
            changes.append(
                {
                    "identity": identity,
                    "galaxy": galaxy,
                    "old_name": old_name,
                    "new_name": new_name,
                    "index": index,
                }
            )
    return result, galaxy_counts, changes


def _rewrite_bases(
    rows: list[Any],
    policy: SavePolicy,
    settlement_counts: dict[int, int],
) -> tuple[list[Any], list[dict[str, Any]]]:
    fixed: dict[int, list[tuple[dict[str, Any], tuple[int, str], int]]] = {}
    portable = []
    cached = []
    for original_index, row in enumerate(rows):
        if not isinstance(row, dict):
            cached.append(row)
            continue
        base_type = _enum(row.get("BaseType"))
        if base_type not in policy.owned_base_types:
            cached.append(row)
            continue
        if base_type in policy.portable_base_types:
            portable.append(row)
            continue
        galaxy = _galaxy(row.get("GalacticAddress"))
        if galaxy is None:
            cached.append(row)
            continue
        fixed.setdefault(galaxy, []).append(
            (row, _old_order(_text(row.get("Name")), galaxy), original_index)
        )
    ordered = []
    changes = []
    for galaxy in sorted(fixed):
        values = sorted(fixed[galaxy], key=lambda item: (item[1], item[2]))
        offset = settlement_counts.get(galaxy, 0)
        for position, (row, _order, _original_index) in enumerate(values):
            value = copy.deepcopy(row)
            old_name = _text(value.get("Name"))
            new_name = _numbered(galaxy, offset + position, _strip_number(old_name))
            value["Name"] = new_name
            ordered.append(value)
            identity, _confidence = _base_identity(value)
            changes.append(
                {
                    "identity": identity,
                    "galaxy": galaxy,
                    "old_name": old_name,
                    "new_name": new_name,
                }
            )
    return [*ordered, *portable, *cached], changes


def _pointer(mapping: SaveMapping, context: str, field: str) -> str:
    keys = (
        mapping.raw_key(context),
        mapping.raw_key("PlayerStateData"),
        mapping.raw_key(field),
    )
    return "/" + "/".join(escape_pointer(key) for key in keys)


def create_finalization_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    policy_path: Path | None = None,
    target_slots: list[int] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite finalization output: {output}")
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    saves = list_saves(profile)
    selected_slots = set(target_slots or [])
    if selected_slots and (
        len(selected_slots) != len(target_slots or [])
        or any(not 1 <= slot <= 10 for slot in selected_slots)
    ):
        raise SaveToolError("finalization target slots must be unique values between 1 and 10")
    existing_slots = {save.slot for save in saves}
    if selected_slots - existing_slots:
        raise SaveToolError("finalization target slots must exist")
    raw_documents = []
    semantic_documents = []
    metadata = []
    for save in saves:
        require_pair(save)
        inspect_meta_file(save.meta_path, save.path)
        raw = decode_file(save.path).document
        raw_documents.append(raw)
        semantic_documents.append(mapping.deobfuscate(raw))
        metadata.append(summarize_meta_file(save.meta_path, save.path))
    owner_id = _owner_id(semantic_documents, policy)
    canonical_settlements = _canonical_settlements(semantic_documents, owner_id)
    settlement_template = _settlement_template(semantic_documents)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir()
    manifest_targets = []
    try:
        for save, raw, semantic, meta in zip(
            saves, raw_documents, semantic_documents, metadata, strict=True
        ):
            if selected_slots and save.slot not in selected_slots:
                continue
            common = semantic.get("CommonStateData")
            common = common if isinstance(common, dict) else {}
            name = _text(common.get("SaveName")) or meta.save_name or ""
            classified = policy.classify(name)
            if classified.galaxies is None:
                continue
            first, last = classified.galaxies
            desired = _desired_settlements(canonical_settlements, first, last)
            operations = []
            target_changes = []
            for context_name, context in semantic.items():
                if not isinstance(context, dict) or not isinstance(
                    context.get("PlayerStateData"), dict
                ):
                    continue
                player = context["PlayerStateData"]
                settlements = player.get("SettlementStatesV2")
                if isinstance(settlements, list):
                    new_settlements, settlement_counts, settlement_changes = _rewrite_settlements(
                        settlements, desired, owner_id, settlement_template
                    )
                    pointer = _pointer(mapping, context_name, "SettlementStatesV2")
                    operations.extend(
                        [
                            {
                                "op": "test",
                                "path": pointer,
                                "value": mapping.obfuscate(settlements),
                            },
                            {
                                "op": "replace",
                                "path": pointer,
                                "value": mapping.obfuscate(new_settlements),
                            },
                        ]
                    )
                else:
                    settlement_counts = {}
                    settlement_changes = []
                bases = player.get("PersistentPlayerBases")
                if isinstance(bases, list):
                    new_bases, base_changes = _rewrite_bases(bases, policy, settlement_counts)
                    pointer = _pointer(mapping, context_name, "PersistentPlayerBases")
                    operations.extend(
                        [
                            {"op": "test", "path": pointer, "value": mapping.obfuscate(bases)},
                            {
                                "op": "replace",
                                "path": pointer,
                                "value": mapping.obfuscate(new_bases),
                            },
                        ]
                    )
                else:
                    base_changes = []
                endpoints = player.get("TeleportEndpoints")
                removed_endpoints = len(endpoints) if isinstance(endpoints, list) else 0
                if isinstance(endpoints, list):
                    pointer = _pointer(mapping, context_name, "TeleportEndpoints")
                    operations.extend(
                        [
                            {"op": "test", "path": pointer, "value": mapping.obfuscate(endpoints)},
                            {"op": "replace", "path": pointer, "value": []},
                        ]
                    )
                target_changes.append(
                    {
                        "context": context_name,
                        "settlements": settlement_changes,
                        "bases": base_changes,
                        "teleport_endpoints_removed": removed_endpoints,
                    }
                )
            patched = apply_patch(raw, operations)
            patch_name = f"{save.path.name}.patch.json"
            patch_path = temporary / patch_name
            _write_new(patch_path, serialize_json(operations) + "\n")
            manifest_targets.append(
                {
                    "source": str(save.path),
                    "source_data_sha256": sha256_file(save.path),
                    "source_meta_sha256": sha256_file(save.meta_path),
                    "save_name": name,
                    "expected_galaxies": {"first": first, "last": last},
                    "patch": patch_name,
                    "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                    "patched_sha256": _hash_value(patched),
                    "changes": target_changes,
                }
            )
        manifest = {
            "schema": "squinch-nms-save-finalization-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "policy": {"source": policy.source, "sha256": policy.sha256},
            "owner_id": owner_id,
            "canonical_settlement_count": len(canonical_settlements),
            "targets": manifest_targets,
        }
        _write_new(
            temporary / "manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    artifacts = [
        str(output / "manifest.json"),
        *[str(output / target["patch"]) for target in manifest_targets],
    ]
    return (
        {
            "output_directory": str(output),
            "owner_id": owner_id,
            "settlements": len(canonical_settlements),
            "targets": len(manifest_targets),
            "teleport_endpoints_removed": sum(
                context["teleport_endpoints_removed"]
                for target in manifest_targets
                for context in target["changes"]
            ),
        },
        artifacts,
    )
