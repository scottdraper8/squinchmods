#!/usr/bin/env python3
"""Generate the local item and technology glossary from decompiled NMS tables."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

TABLE_TEMPLATES = {
    "cGcProductTable": "products",
    "cGcSubstanceTable": "substances",
    "cGcTechnologyTable": "technologies",
    "cGcProceduralTechnologyTable": "procedural_technologies",
    "cGcProceduralProductTable": "procedural_products",
}


def child(node: ET.Element, name: str) -> ET.Element | None:
    return node.find(f"./Property[@name='{name}']")


def value(node: ET.Element, name: str, default: str = "") -> str:
    result = child(node, name)
    return result.attrib.get("value", default) if result is not None else default


def nested_value(node: ET.Element, name: str, default: str = "") -> str:
    result = child(node, name)
    if result is None:
        return default
    nested = result.find("./Property")
    return nested.attrib.get("value", default) if nested is not None else default


def as_bool(node: ET.Element, name: str) -> bool:
    return value(node, name).casefold() == "true"


def as_number(node: ET.Element, name: str) -> int | float | None:
    raw = value(node, name)
    if not raw:
        return None
    try:
        number = float(raw)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def clean_text(text: str) -> str:
    text = re.sub(r"<IMG>[^<]*<>", "", text)
    text = re.sub(r"<[^>]*>", "", text)
    text = text.replace("\\n", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def humanize(text: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return text.replace("_", " ").strip().title()


def colour(node: ET.Element) -> str | None:
    container = child(node, "Colour")
    if container is None:
        container = child(node, "UpgradeColour")
    if container is None:
        return None
    channels = []
    for name in ("R", "G", "B"):
        raw = value(container, name)
        if not raw:
            return None
        channels.append(round(max(0.0, min(1.0, float(raw))) * 255))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def find_tables(root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in root.rglob("*.MXML"):
        template = ET.parse(path).getroot().attrib.get("template", "")
        key = TABLE_TEMPLATES.get(template)
        if key:
            if key in found:
                raise SystemExit(
                    f"duplicate {template} tables: {found[key]} and {path}"
                )
            found[key] = path
    missing = sorted(set(TABLE_TEMPLATES.values()) - set(found))
    if missing:
        raise SystemExit("missing tables: " + ", ".join(missing))
    return found


def load_localisation(root: Path) -> tuple[dict[str, str], int]:
    strings: dict[str, str] = {}
    files = 0
    for path in sorted(root.rglob("*.MXML")):
        document = ET.parse(path).getroot()
        if document.attrib.get("template") != "cTkLocalisationTable":
            continue
        files += 1
        table = child(document, "Table")
        if table is None:
            continue
        for entry in table:
            key = value(entry, "Id") or entry.attrib.get("_id", "")
            english = value(entry, "USEnglish") or value(entry, "English")
            if key and english:
                strings[key] = clean_text(english)
    return strings, files


def icon_fields(node: ET.Element, site_root: Path) -> tuple[str, str]:
    icon_node = child(node, "Icon")
    icon = value(icon_node, "Filename") if icon_node is not None else ""
    if not icon:
        return "", ""
    preview = "assets/" + re.sub(r"\.dds$", ".webp", icon.casefold())
    return icon, preview if (site_root / preview).is_file() else ""


def localized(strings: dict[str, str], key: str, fallback: str = "") -> str:
    return strings.get(key, fallback or key)


def common_record(
    node: ET.Element,
    *,
    strings: dict[str, str],
    site_root: Path,
    kind: str,
    category: str,
    rarity: str,
    source: str,
    fallback_name: str = "",
) -> dict:
    item_id = value(node, "ID") or node.attrib.get("_id", "")
    name_key = value(node, "Name")
    subtitle_key = value(node, "Subtitle")
    description_key = value(node, "Description")
    icon, preview = icon_fields(node, site_root)
    name = localized(strings, name_key, fallback_name or item_id)
    subtitle = localized(strings, subtitle_key, "") if subtitle_key else ""
    description = localized(strings, description_key, "") if description_key else ""
    record = {
        "id": item_id,
        "name": clean_text(name),
        "kind": kind,
        "category": humanize(category) if category else "Uncategorised",
        "categoryKey": category,
        "rarity": rarity or "Unspecified",
        "subtitle": clean_text(subtitle),
        "description": clean_text(description),
        "icon": icon,
        "preview": preview,
        "colour": colour(node),
        "source": source,
        "nameKey": name_key,
        "descriptionKey": description_key,
    }
    return record


def fixed_records(
    path: Path, strings: dict[str, str], site_root: Path, family: str
) -> list[dict]:
    document = ET.parse(path).getroot()
    table = child(document, "Table")
    if table is None:
        return []
    records = []
    for node in table:
        tags: list[str] = []
        fallback_name = ""
        if family == "products":
            kind = "Product"
            category = nested_value(node, "Type")
            rarity = nested_value(node, "Rarity")
            secondary = nested_value(node, "Category")
            for field, label in (
                ("IsCraftable", "Craftable"),
                ("Consumable", "Consumable"),
                ("CookingIngredient", "Cooking ingredient"),
                ("GoodForSelling", "Trade good"),
                ("IsTechbox", "Technology package"),
            ):
                if as_bool(node, field):
                    tags.append(label)
        elif family == "substances":
            kind = "Resource"
            category = nested_value(node, "Category")
            rarity = nested_value(node, "Rarity")
            secondary = "Substance"
            for field, label in (
                ("CookingIngredient", "Cooking ingredient"),
                ("GoodForSelling", "Trade good"),
                ("EasyToRefine", "Easy to refine"),
            ):
                if as_bool(node, field):
                    tags.append(label)
        elif family == "technologies":
            kind = "Technology"
            category = nested_value(node, "Category")
            rarity = nested_value(node, "Rarity")
            secondary = "Core" if as_bool(node, "Core") else "Installable"
            for field, label in (
                ("Core", "Core technology"),
                ("Upgrade", "Upgrade"),
                ("Chargeable", "Chargeable"),
                ("PrimaryItem", "Primary"),
                ("WikiEnabled", "Catalogue entry"),
            ):
                if as_bool(node, field):
                    tags.append(label)
        else:
            kind = "Upgrade module"
            category = nested_value(node, "Category")
            rarity = value(node, "Quality")
            secondary = value(node, "Template")
            fallback_name = localized(
                strings, value(node, "Group"), humanize(value(node, "ID"))
            )
            stat_levels = child(node, "StatLevels")
            count = len(stat_levels) if stat_levels is not None else 0
            if count:
                tags.append(f"{count} possible stats")

        record = common_record(
            node,
            strings=strings,
            site_root=site_root,
            kind=kind,
            category=category,
            rarity=rarity,
            source=path.stem.upper() + ".MBIN",
            fallback_name=fallback_name,
        )
        record.update(
            {
                "secondary": secondary,
                "tags": tags,
                "baseValue": as_number(node, "BaseValue"),
                "level": as_number(node, "Level"),
                "stackMultiplier": as_number(node, "StackMultiplier"),
            }
        )
        records.append(record)
    return records


def procedural_product_records(
    path: Path, strings: dict[str, str], site_root: Path
) -> list[dict]:
    document = ET.parse(path).getroot()
    table = child(document, "Table")
    if table is None:
        return []
    records = []
    for archetype in table:
        if archetype.attrib.get("value") != "GcProceduralProductData":
            continue
        product = child(archetype, "Product")
        if product is None:
            continue
        label = humanize(archetype.attrib.get("name", "Procedural item"))
        record = common_record(
            product,
            strings=strings,
            site_root=site_root,
            kind="Procedural item",
            category=label,
            rarity=nested_value(product, "Rarity"),
            source=path.stem.upper() + ".MBIN",
            fallback_name=f"{label} (procedural)",
        )
        if "%" in record["name"]:
            record["name"] = f"{label} (procedural)"
        record.update(
            {
                "secondary": nested_value(product, "Type"),
                "tags": ["Generated name and value"],
                "baseValue": as_number(product, "BaseValue"),
                "level": as_number(product, "Level"),
                "stackMultiplier": as_number(product, "StackMultiplier"),
            }
        )
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decompiled-root", type=Path, required=True)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "reference" / "site",
    )
    args = parser.parse_args()
    source_root = args.decompiled_root.resolve()
    site_root = args.site_root.resolve()
    tables = find_tables(source_root)
    strings, localisation_files = load_localisation(source_root)

    records: list[dict] = []
    for family in ("products", "substances", "technologies", "procedural_technologies"):
        records.extend(fixed_records(tables[family], strings, site_root, family))
    records.extend(
        procedural_product_records(tables["procedural_products"], strings, site_root)
    )
    records.sort(key=lambda item: (item["name"].casefold(), item["kind"], item["id"]))

    counts = Counter(record["kind"] for record in records)
    unresolved_names = sum(
        not record["name"] or record["name"] == record["nameKey"] for record in records
    )
    meta = {
        "count": len(records),
        "counts": dict(sorted(counts.items())),
        "localisationFiles": localisation_files,
        "unresolvedNames": unresolved_names,
        "withIconPreview": sum(bool(record["preview"]) for record in records),
        "sourceTables": [tables[key].name for key in sorted(tables)],
    }
    payload = (
        "window.NMS_GLOSSARY_META="
        + json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
        + ";window.NMS_GLOSSARY_DATA="
        + json.dumps(records, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    (site_root / "glossary-data.js").write_text(payload, encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
