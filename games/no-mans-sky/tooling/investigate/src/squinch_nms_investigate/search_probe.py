from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from search_probes.adapter import (
    compose_adapter,
)
from search_probes.adapter_errors import AdapterError

from .errors import InvestigationError
from .mbin import convert, inspect_mbin
from .paths import sha256_file
from .xmlmodel import compare_xml, parse_xml, verify_export, xml_summary


def _write(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def build_native_search_probe(
    wiki: Path,
    missions: Path,
    reference_missions: Path,
    destination: Path,
    *,
    probe_tag: str | None = None,
    guide_preset_slots: int = 0,
) -> dict:
    wiki_root, _ = parse_xml(wiki)
    mission_root, _ = parse_xml(missions)
    reference_root, _ = parse_xml(reference_missions)
    if destination.exists():
        raise InvestigationError("probe_destination_exists", f"Destination exists: {destination}")
    destination.mkdir(parents=True)
    try:
        composition = compose_adapter(
            wiki_root,
            mission_root,
            reference_root,
            probe_tag=probe_tag,
            guide_preset_slots=guide_preset_slots,
        )
    except AdapterError as exc:
        raise InvestigationError(exc.code, exc.message, **exc.details) from exc
    outputs = [(destination / relative, root) for relative, root in composition.files]
    for path, root in outputs:
        _write(root, path)
    return {
        "deployment_root": str(destination),
        "source_mission_id": composition.source_mission_id,
        "mission_id": composition.mission_id,
        "scan_event_id": composition.scan_event_id,
        "form_navigation_target_mission_id": composition.form_navigation_target_mission_id,
        "form_navigation_target_event_id": composition.form_navigation_target_event_id,
        "probe_tag": probe_tag,
        "guide_preset_slots": guide_preset_slots,
        "predicate": composition.predicate,
        "search_policy": composition.search_policy,
        "quick_warp_present": composition.quick_warp_present,
        "sources": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in (wiki, missions, reference_missions)
        ],
        "targeting_reference": composition.targeting_reference,
        "location_references": list(composition.location_references),
        "files": [
            {"path": str(path), "sha256": sha256_file(path), "xml": xml_summary(path)}
            for path, _ in outputs
        ],
    }


def verify_probe_patch_compile(patch: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / f"{patch.stem}.MXML"
    shutil.copy2(patch, source)
    compiled, compile_result = convert(source, work_dir=destination)
    if not compiled:
        return {"passed": False, "compile": compile_result}
    inspection = inspect_mbin(compiled, destination / "verify")
    decompiled = inspection.get("decompiled")
    if not decompiled:
        return {"passed": False, "compile": compile_result, "inspection": inspection}
    comparison = compare_xml(source, Path(decompiled))
    leaf_verification = verify_export(source, Path(decompiled))
    compiler_default_expansion_only = comparison["equal"] or all(
        difference["kind"] == "added" for difference in comparison["differences"]
    )
    return {
        "passed": leaf_verification["passed"],
        "exact_roundtrip": comparison["equal"],
        "compiler_default_expansion_only": (
            compiler_default_expansion_only and not comparison["equal"]
        ),
        "authored_leaf_verification": leaf_verification,
        "compile": compile_result,
        "compiled": {"path": str(compiled), "sha256": sha256_file(compiled)},
        "inspection": inspection,
        "semantic_comparison": comparison,
    }


def verify_probe_mission_compile(mission_patch: Path, destination: Path) -> dict:
    return verify_probe_patch_compile(mission_patch, destination)
