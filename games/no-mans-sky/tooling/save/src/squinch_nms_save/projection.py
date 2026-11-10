from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .codec import RawNumber, decode_file, serialize_json
from .errors import SaveToolError
from .inventory import _base_identity, _enum, _galaxy, _hash_value
from .jsonops import apply_patch, escape_pointer, json_equal, resolve
from .mapping import SaveMapping
from .policy import SavePolicy

PROJECTION_SCHEMA = "squinch-nms-save-projection-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SaveToolError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_float=RawNumber)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SaveToolError(f"cannot read JSON {path}: {exc}") from exc


def _workspace_path(path: Path, label: str) -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(Path(workspace_value).resolve())
    except ValueError as exc:
        raise SaveToolError(f"{label} must be inside the selected tranche: {resolved}") from exc
    return resolved


def _write_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(serialize_json(value).encode("utf-8"))
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write {path}: {exc}") from exc


def _inventory_files(
    directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    saves_path = directory / "saves.json"
    bases_path = directory / "bases.json"
    audit_path = directory / "identity-audit.json"
    saves = _load_json(saves_path)
    bases = _load_json(bases_path)
    audit = _load_json(audit_path)
    if not all(isinstance(value, dict) for value in (saves, bases, audit)):
        raise SaveToolError("inventory saves, bases, and identity audit must be objects")
    if any(value.get("schema_version") != "2" for value in (saves, bases, audit)):
        raise SaveToolError("projection requires inventory schema version 2")
    if len({value.get("mapping_sha256") for value in (saves, bases, audit)}) != 1:
        raise SaveToolError("inventory artifacts disagree on mapping hash")
    return saves, bases, audit


def _selected_snapshots(snapshots: list[dict[str, Any]], selection: str) -> list[dict[str, Any]]:
    if selection not in {"all", "auto", "manual", "newest"}:
        raise SaveToolError("snapshot selection must be all, auto, manual, or newest")
    if selection in {"auto", "manual"}:
        return [snapshot for snapshot in snapshots if snapshot.get("kind") == selection]
    if selection == "all":
        return snapshots
    result = []
    for slot in sorted({snapshot["slot"] for snapshot in snapshots}):
        members = [snapshot for snapshot in snapshots if snapshot["slot"] == slot]
        result.append(
            max(
                members,
                key=lambda snapshot: (
                    snapshot.get("meta_timestamp") or 0,
                    snapshot.get("kind") == "auto",
                ),
            )
        )
    return result


def _active_context_name(document: dict[str, Any]) -> str:
    return "ExpeditionContext" if document.get("ActiveContext") == "Season" else "BaseContext"


def create_projection_plan(
    inventory_directory: Path,
    mapping_path: Path,
    output: Path,
    *,
    strategy: str,
    snapshot_selection: str,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    if strategy not in {"prune", "reconcile"}:
        raise SaveToolError("projection strategy must be prune or reconcile")
    inventory = inventory_directory.expanduser().resolve()
    target = _workspace_path(output, "projection plan output")
    if target.exists():
        raise SaveToolError(f"refusing to overwrite projection plan: {target}")
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    saves_artifact, bases_artifact, audit_artifact = _inventory_files(inventory)
    mapping_hash = _sha256(mapping_file)
    if saves_artifact.get("mapping_sha256") != mapping_hash:
        raise SaveToolError("mapping does not match the inventory mapping hash")
    inventory_policy = saves_artifact.get("policy")
    if not isinstance(inventory_policy, dict) or inventory_policy.get("sha256") != policy.sha256:
        raise SaveToolError("policy does not match the inventory policy hash")
    audit_summary = audit_artifact.get("summary")
    if not isinstance(audit_summary, dict):
        raise SaveToolError("inventory identity audit has no summary")
    if strategy == "reconcile" and (
        audit_summary.get("fixed_base_location_collisions") != 0
        or audit_summary.get("low_confidence_identities") != 0
    ):
        raise SaveToolError("reconciliation requires a clean high-confidence identity audit")

    canonical = {item["identity"]: item for item in bases_artifact.get("bases", [])}
    snapshots = saves_artifact.get("snapshots")
    if not isinstance(snapshots, list):
        raise SaveToolError("inventory saves.json has no snapshots array")
    targets = []
    skipped = []
    for snapshot in _selected_snapshots(snapshots, snapshot_selection):
        expected = snapshot.get("expected_galaxies")
        if not isinstance(expected, dict):
            skipped.append(
                {
                    "path": snapshot.get("path"),
                    "reason": "no galaxy policy applies",
                }
            )
            continue
        source = Path(snapshot["path"])
        if _sha256(source) != snapshot.get("data_sha256"):
            raise SaveToolError(f"inventory source changed: {source}")
        raw = decode_file(source, require_714=False).document
        semantic = mapping.deobfuscate(raw)
        context_name = _active_context_name(semantic)
        context = semantic.get(context_name)
        player = context.get("PlayerStateData") if isinstance(context, dict) else None
        if not isinstance(player, dict) or not isinstance(
            player.get("PersistentPlayerBases"), list
        ):
            skipped.append(
                {"path": str(source), "reason": f"active {context_name} has no base array"}
            )
            continue
        current = player["PersistentPlayerBases"]
        current_owned: dict[str, dict[str, Any]] = {}
        for base in current:
            if (
                not isinstance(base, dict)
                or _enum(base.get("BaseType")) not in policy.owned_base_types
            ):
                continue
            identity, _confidence = _base_identity(base)
            if identity in current_owned:
                raise SaveToolError(f"duplicate base identity {identity!r} in {source}")
            current_owned[identity] = base
        first, last = int(expected["first"]), int(expected["last"])
        desired = {
            identity: item
            for identity, item in canonical.items()
            if not item.get("portable")
            and isinstance(item.get("galaxy"), int)
            and first <= item["galaxy"] <= last
        }
        actions = []
        for identity, base in sorted(current_owned.items()):
            base_type = _enum(base.get("BaseType"))
            if base_type in policy.portable_base_types:
                continue
            galaxy = _galaxy(base.get("GalacticAddress"))
            name = base.get("Name") if isinstance(base.get("Name"), str) else ""
            if galaxy is not None and not first <= galaxy <= last:
                actions.append(
                    {
                        "action": "remove",
                        "identity": identity,
                        "name": name,
                        "galaxy": galaxy,
                        "from_revision_sha256": _hash_value(base),
                    }
                )
            elif strategy == "reconcile" and identity in desired:
                selected_hash = desired[identity]["selected_revision_sha256"]
                if _hash_value(base) != selected_hash:
                    actions.append(
                        {
                            "action": "update",
                            "identity": identity,
                            "name": desired[identity]["name"],
                            "galaxy": desired[identity]["galaxy"],
                            "from_revision_sha256": _hash_value(base),
                            "to_revision_sha256": selected_hash,
                        }
                    )
        if strategy == "reconcile":
            for identity, item in sorted(desired.items()):
                if identity not in current_owned:
                    actions.append(
                        {
                            "action": "import",
                            "identity": identity,
                            "name": item["name"],
                            "galaxy": item["galaxy"],
                            "to_revision_sha256": item["selected_revision_sha256"],
                        }
                    )
        targets.append(
            {
                "source": str(source),
                "meta": snapshot["meta_path"],
                "slot": snapshot["slot"],
                "kind": snapshot["kind"],
                "save_name": snapshot["effective_save_name"],
                "context": context_name,
                "expected_galaxies": {"first": first, "last": last},
                "source_data_sha256": snapshot["data_sha256"],
                "source_meta_sha256": snapshot["meta_sha256"],
                "actions": actions,
                "summary": {
                    "remove": sum(action["action"] == "remove" for action in actions),
                    "update": sum(action["action"] == "update" for action in actions),
                    "import": sum(action["action"] == "import" for action in actions),
                },
            }
        )
    inventory_files = {
        name: _sha256(inventory / name)
        for name in ("saves.json", "bases.json", "identity-audit.json")
    }
    plan = {
        "schema": PROJECTION_SCHEMA,
        "approved": False,
        "strategy": strategy,
        "snapshot_selection": snapshot_selection,
        "mapping": {"path": str(mapping_file), "sha256": mapping_hash},
        "policy": {"source": policy.source, "sha256": policy.sha256},
        "owned_base_types": sorted(policy.owned_base_types),
        "portable_base_types": sorted(policy.portable_base_types),
        "inventory": {"directory": str(inventory), "files": inventory_files},
        "targets": targets,
        "skipped": skipped,
        "summary": {
            "targets": len(targets),
            "skipped": len(skipped),
            "remove": sum(target["summary"]["remove"] for target in targets),
            "update": sum(target["summary"]["update"] for target in targets),
            "import": sum(target["summary"]["import"] for target in targets),
        },
    }
    _write_new(target, plan)
    return {"plan": str(target), **plan["summary"]}


def _verify_projection_inputs(
    plan: dict[str, Any], mapping_path: Path | None
) -> tuple[Path, SaveMapping, dict[str, Any]]:
    if plan.get("schema") != PROJECTION_SCHEMA:
        raise SaveToolError(f"projection plan must use schema {PROJECTION_SCHEMA!r}")
    if plan.get("approved") is not True:
        raise SaveToolError("projection plan is not approved; review it and set approved to true")
    mapping_info = plan.get("mapping")
    inventory_info = plan.get("inventory")
    if not isinstance(mapping_info, dict) or not isinstance(inventory_info, dict):
        raise SaveToolError("projection plan is missing mapping or inventory identity")
    mapping_file = (
        mapping_path.expanduser().resolve()
        if mapping_path
        else Path(mapping_info["path"]).resolve()
    )
    if _sha256(mapping_file) != mapping_info.get("sha256"):
        raise SaveToolError("projection mapping hash changed")
    mapping = SaveMapping.load(mapping_file)
    inventory = Path(inventory_info["directory"]).resolve()
    files = inventory_info.get("files")
    if not isinstance(files, dict) or set(files) != {
        "saves.json",
        "bases.json",
        "identity-audit.json",
    }:
        raise SaveToolError("projection plan has no inventory hashes")
    for name, expected_hash in files.items():
        if _sha256(inventory / name) != expected_hash:
            raise SaveToolError(f"projection inventory artifact changed: {name}")
    _saves, bases, _audit = _inventory_files(inventory)
    policy_info = plan.get("policy")
    artifact_policy = bases.get("policy")
    if (
        not isinstance(policy_info, dict)
        or not isinstance(artifact_policy, dict)
        or policy_info.get("sha256") != artifact_policy.get("sha256")
    ):
        raise SaveToolError("projection policy identity does not match the inventory")
    policy_source = policy_info.get("source")
    if policy_source != "builtin" and (
        not isinstance(policy_source, str)
        or _sha256(Path(policy_source)) != policy_info.get("sha256")
    ):
        raise SaveToolError("projection policy file changed")
    targets = plan.get("targets")
    if not isinstance(targets, list) or any(not isinstance(target, dict) for target in targets):
        raise SaveToolError("projection plan has no valid targets array")
    required = {
        "source",
        "meta",
        "context",
        "source_data_sha256",
        "source_meta_sha256",
        "actions",
        "summary",
    }
    for index, target in enumerate(targets):
        if not required <= target.keys():
            raise SaveToolError(f"projection target {index} is missing required fields")
        if not all(isinstance(target[key], str) for key in required - {"actions", "summary"}):
            raise SaveToolError(f"projection target {index} has invalid string fields")
        if not isinstance(target["actions"], list) or not isinstance(target["summary"], dict):
            raise SaveToolError(f"projection target {index} has invalid actions or summary")
    return inventory, mapping, bases


def approve_projection_plan(
    plan_path: Path,
    output: Path,
    *,
    approve: bool,
) -> dict[str, Any]:
    if not approve:
        raise SaveToolError("projection approval requires explicit --approve")
    source = _workspace_path(plan_path, "projection plan")
    target = _workspace_path(output, "approved projection plan output")
    if target.exists():
        raise SaveToolError(f"refusing to overwrite approved projection plan: {target}")
    plan = _load_json(source)
    if not isinstance(plan, dict) or plan.get("schema") != PROJECTION_SCHEMA:
        raise SaveToolError(f"projection plan must use schema {PROJECTION_SCHEMA!r}")
    if plan.get("approved") is not False:
        raise SaveToolError("projection plan is not in the unapproved review state")
    approved = copy.deepcopy(plan)
    approved["approved"] = True
    _verify_projection_inputs(approved, None)
    _write_new(target, approved)
    return {
        "source_plan": str(source),
        "source_plan_sha256": _sha256(source),
        "approved_plan": str(target),
        "approved_plan_sha256": _sha256(target),
        **approved.get("summary", {}),
    }


def emit_projection_patches(
    plan_path: Path,
    output_directory: Path,
    *,
    mapping_path: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    plan_file = _workspace_path(plan_path, "projection plan")
    plan = _load_json(plan_file)
    if not isinstance(plan, dict):
        raise SaveToolError("projection plan root must be an object")
    _inventory, mapping, bases_artifact = _verify_projection_inputs(plan, mapping_path)
    output = _workspace_path(output_directory, "projection output")
    if output.exists():
        raise SaveToolError(f"refusing to overwrite projection output: {output}")
    canonical = {item["identity"]: item for item in bases_artifact.get("bases", [])}
    owned_base_types = plan.get("owned_base_types")
    if not isinstance(owned_base_types, list) or not all(
        isinstance(item, str) for item in owned_base_types
    ):
        raise SaveToolError("projection plan has no owned base type contract")
    owned_types = set(owned_base_types)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True)
    manifest_targets = []
    try:
        for target in plan.get("targets", []):
            source = Path(target["source"])
            meta = Path(target["meta"])
            if _sha256(source) != target.get("source_data_sha256"):
                raise SaveToolError(f"projection source changed: {source}")
            if _sha256(meta) != target.get("source_meta_sha256"):
                raise SaveToolError(f"projection metadata changed: {meta}")
            raw = decode_file(source, require_714=False).document
            semantic = mapping.deobfuscate(raw)
            context_name = target["context"]
            context = semantic.get(context_name)
            player = context.get("PlayerStateData") if isinstance(context, dict) else None
            if not isinstance(player, dict) or not isinstance(
                player.get("PersistentPlayerBases"), list
            ):
                raise SaveToolError(f"projection target lost {context_name} base array: {source}")
            current = player["PersistentPlayerBases"]
            actions = target.get("actions")
            if not isinstance(actions, list):
                raise SaveToolError(f"projection target has no actions array: {source}")
            by_identity = {}
            for action in actions:
                if not isinstance(action, dict) or action.get("action") not in {
                    "remove",
                    "update",
                    "import",
                }:
                    raise SaveToolError(f"invalid projection action for {source}")
                identity = action.get("identity")
                if not isinstance(identity, str) or identity in by_identity:
                    raise SaveToolError(f"duplicate or invalid projection identity for {source}")
                by_identity[identity] = action
            action_summary = {
                name: sum(action["action"] == name for action in actions)
                for name in ("remove", "update", "import")
            }
            replacement = []
            seen = set()
            for base in current:
                if not isinstance(base, dict):
                    replacement.append(base)
                    continue
                if _enum(base.get("BaseType")) not in owned_types:
                    replacement.append(base)
                    continue
                identity, _confidence = _base_identity(base)
                action = by_identity.get(identity)
                if action is None or action["action"] == "import":
                    replacement.append(base)
                    continue
                seen.add(identity)
                if _hash_value(base) != action.get("from_revision_sha256"):
                    raise SaveToolError(f"base revision changed for {identity!r} in {source}")
                if action["action"] == "update":
                    item = canonical.get(identity)
                    if item is None or item.get("selected_revision_sha256") != action.get(
                        "to_revision_sha256"
                    ):
                        raise SaveToolError(f"canonical base revision changed for {identity!r}")
                    replacement.append(item["data"])
            for identity, action in by_identity.items():
                if action["action"] in {"remove", "update"} and identity not in seen:
                    raise SaveToolError(
                        f"projection base {identity!r} no longer exists in {source}"
                    )
                if action["action"] == "import":
                    if any(
                        isinstance(base, dict) and _base_identity(base)[0] == identity
                        for base in current
                    ):
                        raise SaveToolError(
                            f"projection import {identity!r} already exists in {source}"
                        )
                    item = canonical.get(identity)
                    if item is None or item.get("selected_revision_sha256") != action.get(
                        "to_revision_sha256"
                    ):
                        raise SaveToolError(f"canonical import revision changed for {identity!r}")
                    replacement.append(item["data"])
            raw_context = mapping.raw_key(context_name)
            raw_player = mapping.raw_key("PlayerStateData")
            raw_bases = mapping.raw_key("PersistentPlayerBases")
            pointer = "/" + "/".join(
                escape_pointer(key) for key in (raw_context, raw_player, raw_bases)
            )
            original_raw = resolve(raw, pointer)
            replacement_raw = mapping.obfuscate(replacement)
            operations = [
                {"op": "test", "path": pointer, "value": original_raw},
                {"op": "replace", "path": pointer, "value": replacement_raw},
            ]
            patched = apply_patch(raw, operations)
            if not json_equal(resolve(patched, pointer), replacement_raw):
                raise SaveToolError(f"projection patch self-verification failed for {source}")
            patch_name = f"{source.name}.patch.json"
            _write_new(temporary / patch_name, operations)
            manifest_targets.append(
                {
                    "source": str(source),
                    "patch": patch_name,
                    "patch_sha256": _sha256(temporary / patch_name),
                    "actions": actions,
                    "summary": action_summary,
                    "stage_command": (
                        f"tooling/squinch --tranche $SQUINCH_TRANCHE nms-save stage "
                        f"{source} --patch {output / patch_name}"
                    ),
                }
            )
        manifest = {
            "schema": PROJECTION_SCHEMA,
            "plan": str(plan_file),
            "plan_sha256": _sha256(plan_file),
            "targets": manifest_targets,
        }
        _write_new(temporary / "manifest.json", manifest)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    artifacts = [
        str(output / "manifest.json"),
        *[str(output / item["patch"]) for item in manifest_targets],
    ]
    return (
        {
            "output_directory": str(output),
            "targets": len(manifest_targets),
            "patches": len(manifest_targets),
        },
        artifacts,
    )
