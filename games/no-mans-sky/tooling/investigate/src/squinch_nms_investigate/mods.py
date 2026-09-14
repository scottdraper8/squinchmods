from __future__ import annotations

from pathlib import Path

from .errors import InvestigationError
from .mbin import inspect_mbin
from .paths import safe_logical_path, sha256_file
from .runs import write_json
from .toolchain import config as toolchain_config
from .xmlmodel import compare_xml, parse_xml, patch_paths, validate_patch, xml_summary

CONTENT_ROOTS = {
    "audio",
    "fonts",
    "globals",
    "language",
    "materials",
    "metadata",
    "models",
    "music",
    "scenes",
    "shaders",
    "textures",
    "ui",
}
RUNTIME_SUFFIXES = {".exml", ".mbin", ".mxml", ".dds", ".wem", ".bnk", ".ttf", ".otf", ".png"}
RESOURCE_SUFFIXES = (".mbin", ".dds", ".wem", ".bnk", ".ttf", ".otf", ".png")


def _compiler_versions_equal(left: str, right: str) -> bool:
    try:
        return tuple(int(part) for part in left.split(".")) == tuple(
            int(part) for part in right.split(".")
        )
    except ValueError:
        return left == right


def analysis_summary(result: dict) -> dict:
    return {
        "requested_root": result["requested_root"],
        "deployment_root": result["deployment_root"],
        "file_count": result["file_count"],
        "runtime_file_count": result["runtime_file_count"],
        "static_outcome": result["static_outcome"],
        "runtime_compatibility_proven": result["runtime_compatibility_proven"],
        "compatibility_authority": result["compatibility_authority"],
        "finding_counts": result["finding_counts"],
        "findings": result["findings"],
        "touched_path_count": len(result["touched_paths"]),
        "files": [
            {
                key: item[key]
                for key in (
                    "logical_path",
                    "suffix",
                    "classification",
                    "bytes",
                    "sha256",
                    "target_mbin",
                    "target_exists_in_current_game",
                    "full_replacement",
                    "custom_asset",
                )
                if key in item
            }
            for item in result["files"]
        ],
    }


def write_analysis_report(result: dict, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    touched_path = target.parent / "touched-paths.json"
    write_json(touched_path, result["touched_paths"])
    report = {key: value for key, value in result.items() if key not in {"files", "touched_paths"}}
    report["touched_path_count"] = len(result["touched_paths"])
    report["touched_paths_report"] = str(touched_path)
    files: list[dict] = []
    for index, item in enumerate(result["files"]):
        record = {key: value for key, value in item.items() if key != "patch_paths"}
        if "patch_paths" in item:
            record["patch_path_count"] = len(item["patch_paths"])
        validation = record.get("schema_validation")
        if validation:
            validation = dict(validation)
            validation["touched_path_count"] = len(validation.pop("touched_paths"))
            absent = validation.pop("paths_absent_from_vanilla_instance")
            validation["paths_absent_from_vanilla_instance_count"] = len(absent)
            if absent:
                absent_path = target.parent / f"schema-absent-paths-{index:04d}.json"
                write_json(absent_path, absent)
                validation["paths_absent_from_vanilla_instance_report"] = str(absent_path)
            record["schema_validation"] = validation
        files.append(record)
    report["files"] = files
    write_json(target, report)
    return target


def resolve_deployment_root(value: Path) -> Path:
    root = value.expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise InvestigationError("invalid_mod_root", f"Mod root is not a regular directory: {root}")
    if (
        any(child.is_dir() and child.name.casefold() in CONTENT_ROOTS for child in root.iterdir())
        or (root / "LocTable.MXML").is_file()
    ):
        return root
    candidates = [
        directory
        for directory in root.iterdir()
        if directory.is_dir()
        and not directory.is_symlink()
        and (
            any(
                child.is_dir() and child.name.casefold() in CONTENT_ROOTS
                for child in directory.iterdir()
            )
            or (directory / "LocTable.MXML").is_file()
        )
    ]
    if len(candidates) == 1:
        return candidates[0].resolve()
    raise InvestigationError(
        "deployment_root_ambiguous",
        f"Could not identify one NMS deployment root below {root}",
        candidates=[str(path) for path in candidates],
    )


def inventory_mod(root: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise InvestigationError(
                "unsafe_mod_tree", f"Mod tree contains a symbolic link: {relative}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise InvestigationError(
                "unsafe_mod_tree", f"Mod tree contains a special file: {relative}"
            )
        suffix = path.suffix.casefold()
        records.append(
            {
                "logical_path": safe_logical_path(relative),
                "path": str(path),
                "suffix": suffix,
                "classification": "runtime"
                if suffix in RUNTIME_SUFFIXES
                else "authoring-or-documentation",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not any(record["classification"] == "runtime" for record in records):
        raise InvestigationError("empty_mod", f"No recognized NMS runtime files below {root}")
    return records


def target_mbin(logical_exml: str) -> str:
    return logical_exml[:-5] + ".mbin"


def analyze_mod(
    root: Path,
    destination: Path,
    *,
    current_inventory: set[str] | None = None,
    vanilla_xml: dict[str, Path] | None = None,
) -> dict:
    deployment = resolve_deployment_root(root)
    records = inventory_mod(deployment)
    mod_paths = {record["logical_path"] for record in records}
    destination.mkdir(parents=True, exist_ok=False)
    findings: list[dict] = []
    touched: list[dict] = []
    file_results: list[dict] = []
    for index, record in enumerate(records):
        if record["classification"] != "runtime":
            continue
        path = Path(record["path"])
        logical = record["logical_path"]
        suffix = record["suffix"]
        item = dict(record)
        if suffix == ".exml":
            target = target_mbin(logical)
            item["target_mbin"] = target
            item["target_exists_in_current_game"] = (
                current_inventory is None or target in current_inventory
            )
            try:
                root_node, parse = parse_xml(path)
                item["xml"] = xml_summary(path)
                item["patch_paths"] = patch_paths(root_node)
                resource_references: list[dict] = []
                for entry in item["patch_paths"]:
                    raw_value = entry["value"]
                    if not isinstance(raw_value, str) or not raw_value.casefold().endswith(
                        RESOURCE_SUFFIXES
                    ):
                        continue
                    reference = safe_logical_path(raw_value)
                    exists_in_mod = reference in mod_paths
                    exists_in_game = current_inventory is None or reference in current_inventory
                    resource_references.append(
                        {
                            "property_path": entry["path"],
                            "logical_path": reference,
                            "exists_in_mod": exists_in_mod,
                            "exists_in_current_game": exists_in_game,
                        }
                    )
                    if not exists_in_mod and not exists_in_game:
                        findings.append(
                            {
                                "severity": "error",
                                "code": "missing_resource_reference",
                                "path": logical,
                                "message": f"Referenced resource is absent: {reference}",
                            }
                        )
                item["resource_references"] = resource_references
                item.update(parse)
                touched.extend({"target": target, **entry} for entry in item["patch_paths"])
                if vanilla_xml and target in vanilla_xml:
                    item["schema_validation"] = validate_patch(path, vanilla_xml[target])
                    if not item["schema_validation"]["template_match"]:
                        findings.append(
                            {
                                "severity": "error",
                                "code": "patch_schema_mismatch",
                                "path": logical,
                                "message": (
                                    "EXML template or property paths do not match the "
                                    "current vanilla target"
                                ),
                            }
                        )
                    elif not item["schema_validation"]["all_paths_present_in_vanilla_instance"]:
                        findings.append(
                            {
                                "severity": "warning",
                                "code": "patch_paths_absent_from_vanilla_instance",
                                "path": logical,
                                "message": (
                                    "Some patch paths are absent from the current vanilla object. "
                                    "This needs merged-export verification; an instance is not "
                                    "a schema."
                                ),
                            }
                        )
                elif current_inventory is not None and target not in current_inventory:
                    findings.append(
                        {
                            "severity": "error",
                            "code": "patch_target_missing",
                            "path": logical,
                            "message": "EXML target is absent from the current game archives",
                        }
                    )
            except InvestigationError as exc:
                item["xml_error"] = {"code": exc.code, "message": exc.message}
                findings.append(
                    {"severity": "error", "code": exc.code, "path": logical, "message": exc.message}
                )
        elif suffix == ".mbin":
            item["full_replacement"] = logical in (current_inventory or set())
            item["custom_asset"] = (
                current_inventory is not None and logical not in current_inventory
            )
            inspection = inspect_mbin(path, destination / f"mbin-{index:04d}")
            item["mbin"] = inspection
            touched.append(
                {
                    "target": logical,
                    "path": "*",
                    "name_path": ["*"],
                    "identity_path": ["*"],
                    "value": None,
                    "selector": {},
                    "leaf": False,
                }
            )
            if not inspection["decompiled"]:
                findings.append(
                    {
                        "severity": "error",
                        "code": "mbin_decompile_failed",
                        "path": logical,
                        "message": "Current pinned MBINCompiler could not decompile this MBIN",
                    }
                )
            elif vanilla_xml and logical in vanilla_xml:
                current_summary = xml_summary(vanilla_xml[logical])
                item["current_vanilla_xml"] = current_summary
                item["current_comparison"] = compare_xml(
                    vanilla_xml[logical], Path(inspection["decompiled"])
                )
                candidate_nonfinite = inspection.get("xml", {}).get("nonfinite_values", [])
                current_nonfinite = current_summary.get("nonfinite_values", [])
                if len(candidate_nonfinite) > len(current_nonfinite):
                    findings.append(
                        {
                            "severity": "error",
                            "code": "nonfinite_full_replacement_drift",
                            "path": logical,
                            "message": (
                                "Full replacement introduces non-finite numeric values not present "
                                "at the same count in the current vanilla asset"
                            ),
                        }
                    )
            elif (
                inspection["version"].get("version")
                and not _compiler_versions_equal(
                    inspection["version"]["version"],
                    toolchain_config()["mbincompiler"]["reported_version"],
                )
            ):
                findings.append(
                    {
                        "severity": "warning",
                        "code": "stale_mbin_version",
                        "path": logical,
                        "message": (
                            f"MBIN was built with {inspection['version']['version']}, "
                            "not the pinned current compiler"
                        ),
                    }
                )
            if inspection.get("xml", {}).get("nonfinite_values") and not (
                vanilla_xml and logical in vanilla_xml
            ):
                findings.append(
                    {
                        "severity": "warning",
                        "code": "nonfinite_numeric_values",
                        "path": logical,
                        "message": (
                            "Decompiled MBIN contains non-finite numeric values; "
                            "inspect for schema drift"
                        ),
                    }
                )
        elif suffix == ".mxml":
            try:
                item["xml"] = xml_summary(path)
            except InvestigationError as exc:
                item["xml_error"] = {"code": exc.code, "message": exc.message}
                findings.append(
                    {"severity": "error", "code": exc.code, "path": logical, "message": exc.message}
                )
            if path.name.casefold() != "loctable.mxml":
                findings.append(
                    {
                        "severity": "warning",
                        "code": "uncompiled_mxml",
                        "path": logical,
                        "message": (
                            "MXML is normally an authoring input; only LocTable.MXML "
                            "is a conventional runtime exception"
                        ),
                    }
                )
        file_results.append(item)
    errors = sum(finding["severity"] == "error" for finding in findings)
    warnings = sum(finding["severity"] == "warning" for finding in findings)
    return {
        "requested_root": str(root.expanduser().resolve()),
        "deployment_root": str(deployment),
        "file_count": len(records),
        "runtime_file_count": sum(record["classification"] == "runtime" for record in records),
        "files": file_results,
        "touched_paths": touched,
        "findings": findings,
        "finding_counts": {"error": errors, "warning": warnings},
        "static_outcome": "failed" if errors else "succeeded",
        "compatibility_authority": "static-structural-only",
        "runtime_compatibility_proven": False,
    }


def conflict_report(mods: list[dict]) -> dict:
    conflicts: list[dict] = []
    for left_index, left in enumerate(mods):
        for right in mods[left_index + 1 :]:
            for left_touch in left["touched_paths"]:
                for right_touch in right["touched_paths"]:
                    if left_touch["target"] != right_touch["target"]:
                        continue
                    full = left_touch["path"] == "*" or right_touch["path"] == "*"
                    if not full and (not left_touch["leaf"] or not right_touch["leaf"]):
                        continue
                    same_path = left_touch["name_path"] == right_touch["name_path"]
                    if full or same_path:
                        identity_match = left_touch["identity_path"] == right_touch["identity_path"]
                        has_identity = any("[" in part for part in left_touch["identity_path"])
                        confirmed = full or (identity_match and has_identity)
                        conflicts.append(
                            {
                                "left": left["deployment_root"],
                                "right": right["deployment_root"],
                                "target": left_touch["target"],
                                "kind": "full-replacement-overlap"
                                if full
                                else (
                                    "selected-property-overlap"
                                    if confirmed
                                    else "potential-property-overlap"
                                ),
                                "certainty": "confirmed" if confirmed else "potential",
                                "left_path": left_touch["path"],
                                "right_path": right_touch["path"],
                            }
                        )
    unique = {
        (
            item["left"],
            item["right"],
            item["target"],
            item["kind"],
            item["left_path"],
            item["right_path"],
        ): item
        for item in conflicts
    }
    values = list(unique.values())
    confirmed = sum(item["certainty"] == "confirmed" for item in values)
    potential = len(values) - confirmed
    return {
        "conflict_count": len(values),
        "confirmed_conflict_count": confirmed,
        "potential_conflict_count": potential,
        "conflicts": values,
        "conflict_free": not values,
    }
