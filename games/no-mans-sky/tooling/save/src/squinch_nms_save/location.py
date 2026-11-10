from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from .cleanup import _replace
from .codec import decode_file, serialize_json
from .errors import SaveToolError
from .inventory import _text
from .jsonops import apply_patch
from .mapping import SaveMapping
from .meta import inspect_meta_file
from .paths import list_saves
from .policy import SavePolicy
from .stage import sha256_file
from .sync import _slot_pairs, _workspace_output

LOCATION_FIELDS = {
    "player": "UniverseAddress",
    "previous": "PreviousUniverseAddress",
    "freighter": "FreighterUniverseAddress",
}


def _write_new(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write location artifact {path}: {exc}") from exc


def create_location_rehome_patches(
    directory: Path,
    mapping_path: Path,
    output_directory: Path,
    *,
    target_slots: list[int],
    locations: list[str],
    policy_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    if (
        not target_slots
        or len(set(target_slots)) != len(target_slots)
        or any(not 1 <= slot <= 10 for slot in target_slots)
    ):
        raise SaveToolError("target slots must be unique values between 1 and 10")
    selected = set(locations or LOCATION_FIELDS)
    unknown = selected - LOCATION_FIELDS.keys()
    if unknown:
        raise SaveToolError(f"unknown location groups: {', '.join(sorted(unknown))}")
    profile = directory.expanduser().resolve()
    mapping_file = mapping_path.expanduser().resolve()
    mapping = SaveMapping.load(mapping_file)
    policy = SavePolicy.load(policy_path)
    output = _workspace_output(output_directory)
    if output.exists():
        raise SaveToolError(f"refusing to overwrite location output: {output}")
    pairs = _slot_pairs(list_saves(profile))
    if any(slot not in pairs for slot in target_slots):
        raise SaveToolError("location target slots must exist as complete pairs")

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
                classified = policy.classify(save_name)
                if classified.galaxies is None:
                    raise SaveToolError(f"slot {slot} is not galaxy-classified")
                first, last = classified.galaxies
                base = document.get("BaseContext")
                player = base.get("PlayerStateData") if isinstance(base, dict) else None
                if not isinstance(player, dict):
                    raise SaveToolError(f"{save.path} has no PlayerStateData")
                operations: list[dict[str, Any]] = []
                changes = []
                for group in sorted(selected):
                    field = LOCATION_FIELDS[group]
                    address = player.get(field)
                    reality = address.get("RealityIndex") if isinstance(address, dict) else None
                    galactic = address.get("GalacticAddress") if isinstance(address, dict) else None
                    if (
                        not isinstance(reality, int)
                        or isinstance(reality, bool)
                        or not 0 <= reality <= 255
                        or not isinstance(galactic, dict)
                    ):
                        raise SaveToolError(f"{save.path} has an invalid {field}")
                    galaxy = reality + 1
                    if first <= galaxy <= last:
                        continue
                    _replace(
                        operations,
                        mapping,
                        ("BaseContext", "PlayerStateData", field, "RealityIndex"),
                        reality,
                        first - 1,
                    )
                    changes.append(
                        {
                            "group": group,
                            "field": field,
                            "from_galaxy": galaxy,
                            "to_galaxy": first,
                            "galactic_coordinates": galactic,
                        }
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
                        "expected_galaxies": {"first": first, "last": last},
                        "source": str(save.path),
                        "source_data_sha256": sha256_file(save.path),
                        "source_meta_sha256": sha256_file(save.meta_path),
                        "patch": patch_name,
                        "patch_sha256": hashlib.sha256(patch_raw).hexdigest(),
                        "operation_count": len(operations),
                        "changes": changes,
                    }
                )
        manifest = {
            "schema": "squinch-nms-location-rehome-v1",
            "profile": str(profile),
            "mapping": {"path": str(mapping_file), "sha256": sha256_file(mapping_file)},
            "policy": {"source": policy.source, "sha256": policy.sha256},
            "target_slots": target_slots,
            "locations": sorted(selected),
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
            "location_changes": sum(len(target["changes"]) for target in targets),
            "patch_operations": sum(target["operation_count"] for target in targets),
        },
        artifacts,
    )
