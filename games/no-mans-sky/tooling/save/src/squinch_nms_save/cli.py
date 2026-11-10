from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from . import __version__
from .cleanup import INVENTORY_GROUPS, create_cleanup_patches, list_discovery_systems
from .codec import NMS_VERSION, decode_file
from .discovery import create_discovery_redistribution_patches
from .errors import SaveToolError
from .finalize import create_finalization_patches
from .inventory import build_inventory
from .jsonops import diff_values, find_matches, resolve, value_type
from .library import publish_library, publish_systems_library
from .location import LOCATION_FIELDS, create_location_rehome_patches
from .mapping import acquire_mapping, verify_mapping
from .meta import inspect_meta_file
from .output import emit, envelope
from .paths import discover_profile, identity, list_saves, require_pair
from .projection import (
    approve_projection_plan,
    create_projection_plan,
    emit_projection_patches,
)
from .slots import archive_slots, move_slot, swap_slots
from .stage import apply_stage, apply_stage_batch, create_stage, sha256_file, verify_stage
from .sync import GROUPS, clone_slot, create_merge_patches, create_sync_patches


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="squinch nms-save",
        description=f"Inspect and transactionally edit Steam/Proton saves up to NMS {NMS_VERSION}",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="List Auto/Manual save pairs")
    list_parser.add_argument("--directory", type=Path, help="Explicit NMS profile directory")
    list_parser.add_argument("--root", type=Path, help="Root searched for a single profile")

    inspect_parser = commands.add_parser("inspect", help="Validate one save pair through 7.14")
    inspect_parser.add_argument("save", type=Path)

    export_parser = commands.add_parser("export", help="Write exact decoded raw JSON")
    export_parser.add_argument("save", type=Path)
    export_parser.add_argument("--output", required=True, type=Path)

    get_parser = commands.add_parser("get", help="Read a value by RFC 6901 JSON Pointer")
    get_parser.add_argument("save", type=Path)
    get_parser.add_argument("pointer")

    find_parser = commands.add_parser("find", help="Find raw keys or scalar values by regex")
    find_parser.add_argument("save", type=Path)
    find_parser.add_argument("--key")
    find_parser.add_argument("--value")
    find_parser.add_argument("--limit", type=int, default=100)

    diff_parser = commands.add_parser("diff", help="Compare two raw save trees")
    diff_parser.add_argument("left", type=Path)
    diff_parser.add_argument("right", type=Path)
    diff_parser.add_argument("--path", default="", help="Optional JSON Pointer subtree")
    diff_parser.add_argument("--limit", type=int, default=1000)

    inventory_parser = commands.add_parser(
        "inventory", help="Combine named saves, owned bases, starships, and multitools"
    )
    inventory_parser.add_argument("--directory", required=True, type=Path)
    inventory_parser.add_argument("--mapping", required=True, type=Path)
    inventory_parser.add_argument("--output-directory", required=True, type=Path)
    inventory_parser.add_argument("--policy", type=Path)
    inventory_parser.add_argument(
        "--snapshots", choices=("all", "auto", "manual", "newest"), default="all"
    )
    inventory_parser.add_argument(
        "--archives", choices=("include", "exclude", "only"), default="include"
    )
    inventory_parser.add_argument("--cached", choices=("summary", "include"), default="summary")

    mapping_acquire = commands.add_parser(
        "mapping-acquire", help="Download and hash-verify the pinned 7.14 mapping"
    )
    mapping_acquire.add_argument("--output", required=True, type=Path)

    mapping_verify = commands.add_parser(
        "mapping-verify", help="Validate and describe a 7.14 mapping"
    )
    mapping_verify.add_argument("mapping", type=Path)

    slot_diff = commands.add_parser(
        "slot-diff", help="Read one semantic Auto/Manual slot comparison"
    )
    slot_diff.add_argument("--inventory-directory", required=True, type=Path)
    slot_diff.add_argument("--slot", required=True, type=int)

    identity_audit = commands.add_parser(
        "identity-audit", help="Read semantic identity collision and confidence evidence"
    )
    identity_audit.add_argument("--inventory-directory", required=True, type=Path)

    projection_plan = commands.add_parser(
        "projection-plan", help="Plan reviewed base removals, updates, and imports"
    )
    projection_plan.add_argument("--inventory-directory", required=True, type=Path)
    projection_plan.add_argument("--mapping", required=True, type=Path)
    projection_plan.add_argument("--policy", type=Path)
    projection_plan.add_argument("--output", required=True, type=Path)
    projection_plan.add_argument("--strategy", choices=("prune", "reconcile"), required=True)
    projection_plan.add_argument(
        "--snapshots", choices=("all", "auto", "manual", "newest"), default="all"
    )

    projection_emit = commands.add_parser(
        "projection-emit", help="Emit raw patches from an explicitly approved projection plan"
    )
    projection_emit.add_argument("--plan", required=True, type=Path)
    projection_emit.add_argument("--mapping", type=Path)
    projection_emit.add_argument("--output-directory", required=True, type=Path)

    projection_approve = commands.add_parser(
        "projection-approve", help="Explicitly approve a reviewed projection plan"
    )
    projection_approve.add_argument("--plan", required=True, type=Path)
    projection_approve.add_argument("--output", required=True, type=Path)
    projection_approve.add_argument("--approve", action="store_true")

    stage_parser = commands.add_parser(
        "stage", help="Apply RFC 6902 operations to a scratch save pair"
    )
    stage_parser.add_argument("save", type=Path)
    stage_parser.add_argument("--patch", required=True, type=Path)
    stage_parser.add_argument("--output-directory", type=Path)
    stage_parser.add_argument(
        "--timestamp", type=int, help="Fixed Unix metadata timestamp for reproducible fixtures"
    )
    stage_parser.add_argument(
        "--metadata-save-name",
        help="Set the companion metadata display name while staging",
    )

    verify_parser = commands.add_parser("verify-stage", help="Revalidate a staged pair")
    verify_parser.add_argument("stage", type=Path)
    verify_parser.add_argument(
        "--ignore-source", action="store_true", help="Validate artifacts without a freshness check"
    )

    apply_parser = commands.add_parser("apply", help="Back up and install a verified staged pair")
    apply_parser.add_argument("stage", type=Path)
    apply_parser.add_argument("--backup-directory", type=Path)
    apply_parser.add_argument(
        "--apply",
        action="store_true",
        help="Required acknowledgement that the source pair will be replaced",
    )

    batch_parser = commands.add_parser(
        "apply-batch", help="Atomically apply multiple verified stages with one backup"
    )
    batch_parser.add_argument("stages", nargs="+", type=Path)
    batch_parser.add_argument("--apply", action="store_true")

    archive_parser = commands.add_parser(
        "archive-slots", help="Recoverably remove complete Auto/Manual logical slots"
    )
    archive_parser.add_argument("--directory", required=True, type=Path)
    archive_parser.add_argument("--slot", required=True, action="append", type=int, dest="slots")
    archive_parser.add_argument("--output", required=True, type=Path)
    archive_parser.add_argument("--apply", action="store_true")

    swap_parser = commands.add_parser(
        "swap-slots", help="Transactionally exchange two complete Auto/Manual slots"
    )
    swap_parser.add_argument("--directory", required=True, type=Path)
    swap_parser.add_argument("--slot-a", required=True, type=int)
    swap_parser.add_argument("--slot-b", required=True, type=int)
    swap_parser.add_argument("--apply", action="store_true")

    move_parser = commands.add_parser(
        "move-slot", help="Transactionally move one complete slot into an empty slot"
    )
    move_parser.add_argument("--directory", required=True, type=Path)
    move_parser.add_argument("--source-slot", required=True, type=int)
    move_parser.add_argument("--destination-slot", required=True, type=int)
    move_parser.add_argument("--apply", action="store_true")

    finalize_parser = commands.add_parser(
        "finalize-layout", help="Number/sort fixed bases, route settlements, and clear teleports"
    )
    finalize_parser.add_argument("--directory", required=True, type=Path)
    finalize_parser.add_argument("--mapping", required=True, type=Path)
    finalize_parser.add_argument("--policy", type=Path)
    finalize_parser.add_argument("--target-slot", action="append", type=int, dest="target_slots")
    finalize_parser.add_argument("--output-directory", required=True, type=Path)

    library_parser = commands.add_parser(
        "library-publish", help="Publish combined entities to persistent local storage"
    )
    library_parser.add_argument("--inventory-directory", required=True, type=Path)
    library_parser.add_argument("--output-directory", required=True, type=Path)
    library_parser.add_argument("--replace", action="store_true")

    library_systems_parser = commands.add_parser(
        "library-publish-systems",
        help="Add an authoritative systems artifact to the persistent entity library",
    )
    library_systems_parser.add_argument("--systems", required=True, type=Path)
    library_systems_parser.add_argument("--output-directory", required=True, type=Path)

    sync_parser = commands.add_parser(
        "sync-plan", help="Emit guarded selective-sync patches for multiple slots"
    )
    sync_parser.add_argument("--directory", required=True, type=Path)
    sync_parser.add_argument("--mapping", required=True, type=Path)
    sync_parser.add_argument("--source-slot", required=True, type=int)
    sync_parser.add_argument(
        "--target-slot", required=True, action="append", type=int, dest="target_slots"
    )
    sync_parser.add_argument("--include-group", action="append", default=[], choices=sorted(GROUPS))
    sync_parser.add_argument("--exclude-group", action="append", default=[], choices=sorted(GROUPS))
    sync_parser.add_argument("--include-field", action="append", default=[])
    sync_parser.add_argument("--exclude-field", action="append", default=[])
    sync_parser.add_argument("--output-directory", required=True, type=Path)

    cleanup_parser = commands.add_parser(
        "cleanup-plan",
        help="Emit guarded inventory, standing, teleport, and discovery cleanup patches",
    )
    cleanup_parser.add_argument("--directory", required=True, type=Path)
    cleanup_parser.add_argument("--mapping", required=True, type=Path)
    cleanup_parser.add_argument(
        "--target-slot", required=True, action="append", type=int, dest="target_slots"
    )
    cleanup_parser.add_argument(
        "--clear-inventory", action="append", default=[], choices=sorted(INVENTORY_GROUPS)
    )
    cleanup_parser.add_argument("--reset-race-standing", action="store_true")
    cleanup_parser.add_argument("--clear-teleports", action="store_true")
    cleanup_parser.add_argument(
        "--discovery-operation",
        choices=("clear", "retain", "remove", "prune-range", "purge-removed"),
    )
    cleanup_parser.add_argument("--discovery-system", action="append", default=[])
    cleanup_parser.add_argument("--current-system", action="store_true")
    cleanup_parser.add_argument("--expected-discovery-name")
    cleanup_parser.add_argument("--policy", type=Path)
    cleanup_parser.add_argument("--output-directory", required=True, type=Path)

    discovery_list_parser = commands.add_parser(
        "discovery-list", help="List stored systems and canonical addresses for targeted edits"
    )
    discovery_list_parser.add_argument("save", type=Path)
    discovery_list_parser.add_argument("--mapping", required=True, type=Path)

    discovery_redistribute_parser = commands.add_parser(
        "discovery-redistribute-plan",
        help="Deduplicate and route combined discovery systems to their galaxy saves",
    )
    discovery_redistribute_parser.add_argument("--directory", required=True, type=Path)
    discovery_redistribute_parser.add_argument("--mapping", required=True, type=Path)
    discovery_redistribute_parser.add_argument(
        "--target-slot", required=True, action="append", type=int, dest="target_slots"
    )
    discovery_redistribute_parser.add_argument("--name-override", action="append", default=[])
    discovery_redistribute_parser.add_argument("--policy", type=Path)
    discovery_redistribute_parser.add_argument("--output-directory", required=True, type=Path)

    location_rehome_parser = commands.add_parser(
        "location-rehome-plan",
        help="Move out-of-range player/freighter locations to equivalent coordinates",
    )
    location_rehome_parser.add_argument("--directory", required=True, type=Path)
    location_rehome_parser.add_argument("--mapping", required=True, type=Path)
    location_rehome_parser.add_argument(
        "--target-slot", required=True, action="append", type=int, dest="target_slots"
    )
    location_rehome_parser.add_argument(
        "--location", action="append", default=[], choices=sorted(LOCATION_FIELDS)
    )
    location_rehome_parser.add_argument("--policy", type=Path)
    location_rehome_parser.add_argument("--output-directory", required=True, type=Path)

    clone_parser = commands.add_parser(
        "clone-slot", help="Create a new slot from a template with selected entities cleared"
    )
    clone_parser.add_argument("--directory", required=True, type=Path)
    clone_parser.add_argument("--mapping", required=True, type=Path)
    clone_parser.add_argument("--source-slot", required=True, type=int)
    clone_parser.add_argument("--destination-slot", required=True, type=int)
    clone_parser.add_argument("--name", required=True)
    clone_parser.add_argument(
        "--clear-group",
        action="append",
        default=[],
        choices=("bases", "starships", "multitools"),
    )
    clone_parser.add_argument("--apply", action="store_true")

    merge_parser = commands.add_parser(
        "merge-plan", help="Emit guarded patches that union selected entities from multiple slots"
    )
    merge_parser.add_argument("--directory", required=True, type=Path)
    merge_parser.add_argument("--mapping", required=True, type=Path)
    merge_parser.add_argument(
        "--source-slot", required=True, action="append", type=int, dest="source_slots"
    )
    merge_parser.add_argument("--template-slot", required=True, type=int)
    merge_parser.add_argument("--target-slot", required=True, type=int)
    merge_parser.add_argument(
        "--include-group", action="append", default=[], choices=sorted(GROUPS)
    )
    merge_parser.add_argument(
        "--exclude-group", action="append", default=[], choices=sorted(GROUPS)
    )
    merge_parser.add_argument("--include-field", action="append", default=[])
    merge_parser.add_argument("--exclude-field", action="append", default=[])
    merge_parser.add_argument("--capacity-policy", choices=("error", "template"), default="error")
    merge_parser.add_argument("--output-directory", required=True, type=Path)
    return parser


def _positive_limit(value: int) -> int:
    if value <= 0 or value > 100_000:
        raise SaveToolError("--limit must be between 1 and 100000")
    return value


def _inspect(path: Path) -> dict[str, Any]:
    save = identity(path)
    require_pair(save)
    decoded = decode_file(save.path)
    meta = inspect_meta_file(save.meta_path, save.path)
    if meta.decompressed_size == decoded.decompressed_size:
        size_mode = "decoded"
    elif (
        meta.decompressed_size == decoded.compressed_size
        and meta.compressed_size == decoded.compressed_size
    ):
        size_mode = "compressed"
    else:
        raise SaveToolError("save and metadata size fields differ")
    if (
        size_mode == "decoded"
        and meta.compressed_size is not None
        and decoded.compressed_size != meta.compressed_size
    ):
        raise SaveToolError("save and metadata compressed sizes differ")
    return {
        "path": str(save.path),
        "meta_path": str(save.meta_path),
        "slot": save.slot,
        "kind": save.kind,
        "ordinal": save.ordinal,
        "nms_version": NMS_VERSION,
        "blocks": decoded.block_count,
        "compressed_size": decoded.compressed_size,
        "decompressed_size": decoded.decompressed_size,
        "root_keys": len(decoded.document),
        "meta_format": meta.format,
        "base_version": meta.base_version,
        "timestamp": meta.timestamp,
        "metadata_size_mode": size_mode,
        "data_sha256": sha256_file(save.path),
        "meta_sha256": sha256_file(save.meta_path),
    }


def _list(args: argparse.Namespace) -> dict[str, Any]:
    if args.directory and args.root:
        raise SaveToolError("choose --directory or --root, not both")
    directory = (
        args.directory.expanduser().resolve() if args.directory else discover_profile(args.root)
    )
    entries = []
    for save in list_saves(directory):
        try:
            entries.append({"state": "supported", **_inspect(save.path)})
        except SaveToolError as exc:
            entries.append(
                {
                    "state": "unsupported",
                    "path": str(save.path),
                    "meta_path": str(save.meta_path),
                    "slot": save.slot,
                    "kind": save.kind,
                    "ordinal": save.ordinal,
                    "error": str(exc),
                }
            )
    return {"directory": str(directory), "nms_version": NMS_VERSION, "saves": entries}


def _export(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    decoded = decode_file(identity(args.save).path)
    output = args.output.expanduser().resolve()
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    try:
        output.relative_to(Path(workspace_value).resolve())
    except ValueError as exc:
        raise SaveToolError(f"export must be inside the selected tranche: {output}") from exc
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(decoded.json_bytes)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise SaveToolError(f"refusing to overwrite export: {output}") from exc
    except OSError as exc:
        raise SaveToolError(f"cannot write export {output}: {exc}") from exc
    return (
        {
            "save": str(args.save.expanduser().resolve()),
            "output": str(output),
            "bytes": output.stat().st_size,
        },
        [str(output)],
    )


def _read_artifact(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SaveToolError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaveToolError(f"{label} root must be an object")
    return value


def _run(args: argparse.Namespace) -> tuple[str, dict[str, Any], list[str], str | None]:
    if args.command == "list":
        return "succeeded", _list(args), [], None
    if args.command == "inspect":
        return "succeeded", _inspect(args.save), [], None
    if args.command == "export":
        data, artifacts = _export(args)
        return "succeeded", data, artifacts, None
    if args.command == "get":
        decoded = decode_file(identity(args.save).path)
        value = resolve(decoded.document, args.pointer)
        return (
            "succeeded",
            {
                "save": str(args.save.expanduser().resolve()),
                "path": args.pointer,
                "type": value_type(value),
                "value": value,
            },
            [],
            None,
        )
    if args.command == "find":
        limit = _positive_limit(args.limit)
        decoded = decode_file(identity(args.save).path)
        matches, truncated = find_matches(
            decoded.document, key_pattern=args.key, value_pattern=args.value, limit=limit
        )
        return (
            "succeeded",
            {
                "save": str(args.save.expanduser().resolve()),
                "matches": matches,
                "truncated": truncated,
            },
            [],
            None,
        )
    if args.command == "diff":
        limit = _positive_limit(args.limit)
        left_doc = decode_file(identity(args.left).path).document
        right_doc = decode_file(identity(args.right).path).document
        left_value = resolve(left_doc, args.path)
        right_value = resolve(right_doc, args.path)
        result = diff_values(left_value, right_value, pointer=args.path, limit=limit)
        return (
            "succeeded",
            {
                "left": str(args.left.expanduser().resolve()),
                "right": str(args.right.expanduser().resolve()),
                "path": args.path,
                "changes": result.changes,
                "truncated": result.truncated,
            },
            [],
            None,
        )
    if args.command == "inventory":
        result, artifacts = build_inventory(
            args.directory,
            args.mapping,
            args.output_directory,
            policy_path=args.policy,
            snapshot_selection=args.snapshots,
            archives=args.archives,
            cached=args.cached,
        )
        return "succeeded", result, artifacts, None
    if args.command == "mapping-acquire":
        result = acquire_mapping(args.output)
        return "succeeded", result, [result["path"]], None
    if args.command == "mapping-verify":
        return "succeeded", verify_mapping(args.mapping), [], None
    if args.command == "slot-diff":
        if not 1 <= args.slot <= 10:
            raise SaveToolError("--slot must be between 1 and 10")
        artifact = _read_artifact(
            args.inventory_directory / "slot-diffs.json", "slot diff artifact"
        )
        matches = [item for item in artifact.get("slots", []) if item.get("slot") == args.slot]
        if len(matches) != 1:
            raise SaveToolError(f"inventory has no unique slot {args.slot} comparison")
        return "succeeded", matches[0], [], None
    if args.command == "identity-audit":
        artifact = _read_artifact(
            args.inventory_directory / "identity-audit.json", "identity audit artifact"
        )
        return "succeeded", artifact, [], None
    if args.command == "projection-plan":
        result = create_projection_plan(
            args.inventory_directory,
            args.mapping,
            args.output,
            strategy=args.strategy,
            snapshot_selection=args.snapshots,
            policy_path=args.policy,
        )
        return "planned", result, [result["plan"]], Path(result["plan"]).stem
    if args.command == "projection-emit":
        result, artifacts = emit_projection_patches(
            args.plan, args.output_directory, mapping_path=args.mapping
        )
        return "succeeded", result, artifacts, Path(result["output_directory"]).name
    if args.command == "projection-approve":
        result = approve_projection_plan(args.plan, args.output, approve=args.approve)
        return "succeeded", result, [result["approved_plan"]], Path(result["approved_plan"]).stem
    if args.command == "stage":
        result = create_stage(
            args.save,
            args.patch,
            output_directory=args.output_directory,
            timestamp=args.timestamp,
            metadata_save_name=args.metadata_save_name,
        )
        stage_path = result["stage"]
        return "staged", result, [stage_path], Path(stage_path).name
    if args.command == "verify-stage":
        result = verify_stage(args.stage, verify_source=not args.ignore_source)
        return "succeeded", result, [result["stage"]], Path(result["stage"]).name
    if args.command == "apply":
        result = apply_stage(args.stage, apply=args.apply, backup_directory=args.backup_directory)
        return "succeeded", result, [result["stage"], result["backup"]], Path(result["stage"]).name
    if args.command == "apply-batch":
        result = apply_stage_batch(args.stages, apply=args.apply)
        return "succeeded", result, [result["backup"]], Path(result["backup"]).name
    if args.command == "archive-slots":
        result = archive_slots(args.directory, args.slots, args.output, apply=args.apply)
        return "succeeded", result, [result["archive"]], Path(result["archive"]).name
    if args.command == "swap-slots":
        result = swap_slots(args.directory, args.slot_a, args.slot_b, apply=args.apply)
        return "succeeded", result, [result["backup"]], Path(result["backup"]).name
    if args.command == "move-slot":
        result = move_slot(
            args.directory,
            args.source_slot,
            args.destination_slot,
            apply=args.apply,
        )
        return "succeeded", result, [result["backup"]], Path(result["backup"]).name
    if args.command == "finalize-layout":
        result, artifacts = create_finalization_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            policy_path=args.policy,
            target_slots=args.target_slots,
        )
        return "succeeded", result, artifacts, Path(result["output_directory"]).name
    if args.command == "library-publish":
        result = publish_library(
            args.inventory_directory,
            args.output_directory,
            replace=args.replace,
        )
        return "succeeded", result, [result["library"]], Path(result["library"]).name
    if args.command == "library-publish-systems":
        result = publish_systems_library(args.systems, args.output_directory)
        return "succeeded", result, [result["library"]], Path(result["library"]).name
    if args.command == "sync-plan":
        result, artifacts = create_sync_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            source_slot=args.source_slot,
            target_slots=args.target_slots,
            include_groups=args.include_group,
            exclude_groups=args.exclude_group,
            include_fields=args.include_field,
            exclude_fields=args.exclude_field,
        )
        return "planned", result, artifacts, Path(result["output_directory"]).name
    if args.command == "cleanup-plan":
        result, artifacts = create_cleanup_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            target_slots=args.target_slots,
            clear_inventory=args.clear_inventory,
            reset_race_standing=args.reset_race_standing,
            clear_teleports=args.clear_teleports,
            discovery_operation=args.discovery_operation,
            discovery_systems=args.discovery_system,
            include_current_system=args.current_system,
            expected_discovery_name=args.expected_discovery_name,
            policy_path=args.policy,
        )
        return "planned", result, artifacts, Path(result["output_directory"]).name
    if args.command == "discovery-list":
        return "succeeded", list_discovery_systems(args.save, args.mapping), [], None
    if args.command == "discovery-redistribute-plan":
        result, artifacts = create_discovery_redistribution_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            target_slots=args.target_slots,
            name_overrides=args.name_override,
            policy_path=args.policy,
        )
        return "planned", result, artifacts, Path(result["output_directory"]).name
    if args.command == "location-rehome-plan":
        result, artifacts = create_location_rehome_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            target_slots=args.target_slots,
            locations=args.location,
            policy_path=args.policy,
        )
        return "planned", result, artifacts, Path(result["output_directory"]).name
    if args.command == "clone-slot":
        result = clone_slot(
            args.directory,
            args.mapping,
            args.source_slot,
            args.destination_slot,
            args.name,
            args.clear_group,
            apply=args.apply,
        )
        return "succeeded", result, [result["evidence"]], Path(result["evidence"]).name
    if args.command == "merge-plan":
        result, artifacts = create_merge_patches(
            args.directory,
            args.mapping,
            args.output_directory,
            source_slots=args.source_slots,
            template_slot=args.template_slot,
            target_slot=args.target_slot,
            include_groups=args.include_group,
            exclude_groups=args.exclude_group,
            include_fields=args.include_field,
            exclude_fields=args.exclude_field,
            capacity_policy=args.capacity_policy,
        )
        return "planned", result, artifacts, Path(result["output_directory"]).name
    raise SaveToolError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        state, data, artifacts, run_id = _run(args)
        emit(envelope(args.command, state, data=data, artifact_paths=artifacts, run_id=run_id))
        return 0
    except SaveToolError as exc:
        emit(
            envelope(
                args.command,
                "error",
                error={"code": "save_tool_error", "message": str(exc), "details": {}},
            ),
            error=True,
        )
        return 1
