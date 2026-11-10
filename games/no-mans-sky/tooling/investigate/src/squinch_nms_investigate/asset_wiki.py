from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import InvestigationError
from .hgpak import extract
from .mbin import inspect_mbin

TABLE_PATHS = (
    "metadata/reality/tables/nms_reality_gcproducttable.mbin",
    "metadata/reality/tables/nms_reality_gcsubstancetable.mbin",
    "metadata/reality/tables/nms_reality_gctechnologytable.mbin",
    "metadata/reality/tables/nms_reality_gcproceduraltechnologytable.mbin",
    "metadata/reality/tables/proceduralproducttable.mbin",
)
LOCALISATION = re.compile(r"^language/nms_(?:loc|update)\d+_english\.mbin$")


def is_catalog_icon(path: str) -> bool:
    parts = path.casefold().split("/")
    if not parts or not parts[-1].endswith(".dds"):
        return False
    return (
        "icon" in parts
        or "icons" in parts
        or (parts[:2] == ["textures", "ui"] and "icon" in path.casefold())
    )


def select_mbin_sources(members: set[str]) -> list[str]:
    normalized = {member.casefold(): member for member in members}
    missing = [path for path in TABLE_PATHS if path not in normalized]
    if missing:
        raise InvestigationError(
            "asset_wiki_sources_missing",
            "Required Asset Wiki tables are absent from the installed game",
            paths=missing,
        )
    localization = sorted(member for member in members if LOCALISATION.fullmatch(member.casefold()))
    if not localization:
        raise InvestigationError(
            "asset_wiki_localisation_missing",
            "No installed English localisation banks were found",
        )
    return [normalized[path] for path in TABLE_PATHS] + localization


def referenced_dds_paths(documents: list[Path]) -> set[str]:
    paths: set[str] = set()
    for document in documents:
        root = ET.parse(document).getroot()
        for node in root.iter("Property"):
            value = re.sub(r"/+", "/", node.attrib.get("value", "").replace("\\", "/").casefold())
            if value.endswith(".dds"):
                paths.add(value)
    return paths


def extract_sources(
    catalog: dict[str, list[str]],
    members: set[str],
    destination: Path,
    *,
    game: dict | None = None,
) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    mbin_paths = select_mbin_sources(members)
    mbin_records = extract(mbin_paths, catalog, destination / "mbin")
    inspections: list[dict] = []
    documents: list[Path] = []
    for index, record in enumerate(mbin_records):
        inspection = inspect_mbin(Path(record["path"]), destination / "decompiled" / f"{index:04d}")
        inspection["logical_path"] = record["logical_path"]
        inspections.append(inspection)
        if not inspection["decompiled"]:
            raise InvestigationError(
                "asset_wiki_decompile_failed",
                f"Could not decompile Asset Wiki source: {record['logical_path']}",
            )
        documents.append(Path(inspection["decompiled"]))

    referenced = referenced_dds_paths(documents)
    member_by_case = {member.casefold(): member for member in members}
    missing_references = sorted(path for path in referenced if path not in member_by_case)
    if missing_references:
        raise InvestigationError(
            "asset_wiki_icons_missing",
            "Asset Wiki tables reference icons absent from the installed archives",
            paths=missing_references,
        )
    catalog_icons = {member for member in members if is_catalog_icon(member)}
    icon_paths = sorted(catalog_icons | {member_by_case[path] for path in referenced})
    icon_records = extract(icon_paths, catalog, destination / "icons")
    for record in icon_records:
        record["catalog_icon"] = record["logical_path"] in catalog_icons

    manifest = {
        "schema_version": 1,
        "game": game,
        "decompiled_root": str((destination / "decompiled").resolve()),
        "icon_root": str((destination / "icons").resolve()),
        "mbin_sources": mbin_records,
        "decompilations": inspections,
        "icon_sources": icon_records,
        "catalog_icon_count": len(catalog_icons),
        "table_icon_count": len(referenced),
    }
    manifest_path = destination / "asset-wiki-source-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "source_manifest": str(manifest_path),
        "decompiled_root": manifest["decompiled_root"],
        "icon_root": manifest["icon_root"],
        "mbin_count": len(mbin_records),
        "catalog_icon_count": len(catalog_icons),
        "table_icon_count": len(referenced),
        "extracted_icon_count": len(icon_records),
    }
