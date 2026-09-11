from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .errors import InvestigationError
from .paths import sha256_file

AMUMSS_ANNOTATION = re.compile(r"\s+!#.*$")
NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
NONFINITE = {"nan", "+nan", "-nan", "infinity", "+infinity", "-infinity", "inf", "+inf", "-inf"}


def parse_xml(path: Path, *, allow_amumss_annotations: bool = True) -> tuple[ET.Element, dict]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise InvestigationError("xml_read_failed", f"Could not read XML {path}: {exc}") from exc
    cleaned_lines: list[str] = []
    annotation_count = 0
    for line in text.splitlines():
        cleaned = AMUMSS_ANNOTATION.sub("", line) if allow_amumss_annotations else line
        annotation_count += cleaned != line
        cleaned_lines.append(cleaned)
    try:
        root = ET.fromstring("\n".join(cleaned_lines))
    except ET.ParseError as exc:
        raise InvestigationError("invalid_xml", f"Invalid XML in {path}: {exc}") from exc
    if root.tag != "Data":
        raise InvestigationError("invalid_nms_xml", f"NMS XML root must be Data: {path}")
    return root, {"amumss_annotation_count": annotation_count}


def _node_key(element: ET.Element, index: int) -> str:
    name = element.attrib.get("name", element.tag)
    selector = next(
        (
            f"{key}={element.attrib[key]}"
            for key in ("_id", "_index", "_name")
            if key in element.attrib
        ),
        None,
    )
    value_type = element.attrib.get("value") if list(element) else None
    identity = selector or (f"type={value_type}" if value_type else "unselected")
    qualifier = f"{identity},occurrence={index}"
    return f"{name}[{qualifier}]"


def flatten(root: ET.Element) -> dict[str, dict]:
    records: dict[str, dict] = {}

    def visit(element: ET.Element, parent: str) -> None:
        children = list(element)
        sibling_counts: Counter[str] = Counter()
        for child in children:
            base = child.attrib.get("name", child.tag)
            index = sibling_counts[base]
            sibling_counts[base] += 1
            segment = _node_key(child, index)
            path = f"{parent}/{segment}"
            records[path] = {
                "tag": child.tag,
                "attributes": dict(sorted(child.attrib.items())),
                "text": (child.text or "").strip(),
            }
            visit(child, path)

    records["Data"] = {
        "tag": root.tag,
        "attributes": dict(sorted(root.attrib.items())),
        "text": (root.text or "").strip(),
    }
    visit(root, "Data")
    return records


def schema_paths(root: ET.Element) -> set[tuple[str, ...]]:
    result: set[tuple[str, ...]] = set()

    def visit(element: ET.Element, parents: tuple[str, ...]) -> None:
        for child in element:
            name = child.attrib.get("name", child.tag)
            current = (*parents, name)
            result.add(current)
            visit(child, current)

    visit(root, ())
    return result


def patch_paths(root: ET.Element) -> list[dict]:
    result: list[dict] = []

    def visit(
        element: ET.Element,
        parents: tuple[str, ...],
        identity_parents: tuple[str, ...],
    ) -> None:
        for child in element:
            name = child.attrib.get("name", child.tag)
            current = (*parents, name)
            selectors = {key: value for key, value in child.attrib.items() if key.startswith("_")}
            qualifier = ",".join(f"{key}={value}" for key, value in sorted(selectors.items()))
            if not qualifier:
                identifier = next(
                    (
                        descendant
                        for descendant in child
                        if len(descendant) == 0
                        and descendant.attrib.get("value")
                        and descendant.attrib.get("name", "").casefold().endswith("id")
                    ),
                    None,
                )
                if identifier is not None:
                    qualifier = f"inferred:{identifier.attrib['name']}={identifier.attrib['value']}"
            identity = (*identity_parents, f"{name}[{qualifier}]" if qualifier else name)
            result.append(
                {
                    "path": "/".join(current),
                    "name_path": list(current),
                    "identity_path": list(identity),
                    "value": child.attrib.get("value"),
                    "selector": selectors,
                    "leaf": len(child) == 0,
                }
            )
            visit(child, current, identity)

    visit(root, (), ())
    return result


def xml_summary(path: Path) -> dict:
    root, parse = parse_xml(path)
    flat = flatten(root)
    nonfinite: list[dict] = []
    numeric_count = 0
    for record_path, record in flat.items():
        for key, value in record["attributes"].items():
            normalized = value.casefold()
            if normalized in NONFINITE:
                nonfinite.append({"path": record_path, "attribute": key, "value": value})
            elif NUMERIC.fullmatch(value):
                numeric_count += 1
                try:
                    if not math.isfinite(float(value)):
                        nonfinite.append({"path": record_path, "attribute": key, "value": value})
                except ValueError:
                    pass
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "template": root.attrib.get("template"),
        "node_count": len(flat),
        "numeric_value_count": numeric_count,
        "nonfinite_values": nonfinite,
        **parse,
    }


def compare_xml(left: Path, right: Path, *, limit: int = 200) -> dict:
    left_root, _ = parse_xml(left)
    right_root, _ = parse_xml(right)
    left_flat = flatten(left_root)
    right_flat = flatten(right_root)
    differences: list[dict] = []
    for path in sorted(left_flat.keys() | right_flat.keys()):
        if path not in left_flat:
            differences.append({"kind": "added", "path": path, "right": right_flat[path]})
        elif path not in right_flat:
            differences.append({"kind": "removed", "path": path, "left": left_flat[path]})
        elif left_flat[path] != right_flat[path]:
            differences.append(
                {
                    "kind": "changed",
                    "path": path,
                    "left": left_flat[path],
                    "right": right_flat[path],
                }
            )
    return {
        "equal": not differences,
        "left": {"path": str(left), "sha256": sha256_file(left), "nodes": len(left_flat)},
        "right": {"path": str(right), "sha256": sha256_file(right), "nodes": len(right_flat)},
        "difference_count": len(differences),
        "differences": differences[:limit],
        "differences_truncated": len(differences) > limit,
    }


def validate_patch(patch: Path, vanilla: Path) -> dict:
    patch_root, parse = parse_xml(patch)
    vanilla_root, _ = parse_xml(vanilla)
    touched = patch_paths(patch_root)
    known = schema_paths(vanilla_root)
    unknown = [item for item in touched if tuple(item["name_path"]) not in known]
    template_match = patch_root.attrib.get("template") == vanilla_root.attrib.get("template")
    return {
        "patch": str(patch),
        "vanilla": str(vanilla),
        "patch_template": patch_root.attrib.get("template"),
        "vanilla_template": vanilla_root.attrib.get("template"),
        "template_match": template_match,
        "touched_paths": touched,
        "paths_absent_from_vanilla_instance": unknown,
        "all_paths_present_in_vanilla_instance": not unknown,
        "structurally_compatible": template_match,
        "path_authority": (
            "The current decompiled object is an instance, not a complete template schema; "
            "absent paths are diagnostic and cannot alone prove incompatibility."
        ),
        **parse,
    }


def verify_export(patch: Path, exported: Path, vanilla: Path | None = None) -> dict:
    patch_root, _ = parse_xml(patch)
    exported_root, _ = parse_xml(exported)
    exported_leaves: dict[tuple[str, ...], set[str | None]] = {}
    for item in patch_paths(exported_root):
        if item["leaf"]:
            exported_leaves.setdefault(tuple(item["name_path"]), set()).add(item["value"])
    checks: list[dict] = []
    for item in patch_paths(patch_root):
        if not item["leaf"] or item["value"] is None:
            continue
        operation = item["selector"].get("_remove")
        present = item["value"] in exported_leaves.get(tuple(item["name_path"]), set())
        passed = not present if operation is not None else present
        checks.append(
            {
                "path": item["path"],
                "value": item["value"],
                "operation": "remove" if operation is not None else "set-or-add",
                "passed": passed,
            }
        )
    result = {
        "verified_leaf_count": len(checks),
        "failed_checks": [check for check in checks if not check["passed"]],
        "checks": checks,
        "passed": bool(checks) and all(check["passed"] for check in checks),
        "scope": "intended-leaf-presence",
    }
    if vanilla:
        result["export_vs_vanilla"] = compare_xml(vanilla, exported)
    return result
