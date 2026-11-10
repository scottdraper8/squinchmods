"""Write the canonical Asset Wiki records as compact Worker-searchable JSON-LD."""

from __future__ import annotations

import json
from pathlib import Path

GAME_NAMESPACE = "https://no-mans-sky.squinchmods.com/asset-wiki/id/"
CONTEXT = {
    "@vocab": "https://squinchmods.com/ns/no-mans-sky#",
    "schema": "https://schema.org/",
    "name": "schema:name",
    "description": "schema:description",
}


def public_preview(value: str) -> str:
    if not value:
        return ""
    return "/asset-wiki/assets/" + value.removeprefix("assets/")


def dataset(
    identifier: str, name: str, version: str, build_id: str, records: list[dict]
) -> dict:
    return {
        "@context": CONTEXT,
        "@id": f"https://no-mans-sky.squinchmods.com/asset-wiki/data/{identifier}",
        "@type": "schema:Dataset",
        "name": name,
        "gameVersion": version,
        "steamBuild": build_id,
        "recordCount": len(records),
        "@graph": records,
    }


def build(
    output: Path,
    manifest: dict,
    glossary_meta: dict,
    glossary: list[dict],
    icons: list[dict],
    colour_filters: list[dict],
) -> dict:
    version = manifest["game"]["version"]
    build_id = manifest["game"]["steam_build"]

    item_records = []
    for record in glossary:
        item = dict(record)
        kind = record["kind"].casefold().replace(" ", "-")
        item["@id"] = f"{GAME_NAMESPACE}item/{kind}/{record['id']}"
        item["@type"] = "GameAsset"
        item["preview"] = public_preview(record.get("preview", ""))
        item_records.append(item)

    icon_records = []
    for record in icons:
        icon = dict(record)
        icon["@id"] = GAME_NAMESPACE + "icon/" + record["path"]
        icon["@type"] = "GameIcon"
        icon["name"] = Path(record["path"]).stem
        icon["preview"] = public_preview(record["preview"])
        icon_records.append(icon)

    colour_filter_records = []
    for record in colour_filters:
        colour_filter = dict(record)
        colour_filter["@id"] = (
            f"{GAME_NAMESPACE}world-colour-filter/{record['native_value']}"
        )
        colour_filter["@type"] = "WorldColourFilter"
        colour_filter_records.append(colour_filter)

    output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "items": dataset(
            "items",
            "No Man's Sky items and technology",
            version,
            build_id,
            item_records,
        ),
        "icons": dataset(
            "icons", "No Man's Sky icon assets", version, build_id, icon_records
        ),
        "colour-filters": dataset(
            "colour-filters",
            "No Man's Sky world colour filters",
            version,
            build_id,
            colour_filter_records,
        ),
    }
    for name, value in outputs.items():
        (output / f"{name}.jsonld").write_text(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    result = {
        "schema_version": 1,
        "game_version": version,
        "steam_build": build_id,
        "datasets": {name: value["recordCount"] for name, value in outputs.items()},
        "glossary": glossary_meta,
    }
    (output / "manifest.jsonld").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result
