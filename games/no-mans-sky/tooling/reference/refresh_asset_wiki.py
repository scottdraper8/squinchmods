#!/usr/bin/env python3
"""Refresh canonical Asset Wiki previews and JSON-LD from an extraction run."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from build_asset_wiki import build as build_json_ld
from generate_colour_filters import generate as generate_colour_filters
from generate_glossary import generate as generate_glossary


def is_catalog_icon(path: str) -> bool:
    parts = path.casefold().split("/")
    return path.casefold().endswith(".dds") and (
        "icon" in parts
        or "icons" in parts
        or (parts[:2] == ["textures", "ui"] and "icon" in path.casefold())
    )


def convert_icon(
    record: dict, asset_store: Path, *, reuse_previews: bool
) -> dict | None:
    logical = re.sub(r"/+", "/", record["logical_path"].replace("\\", "/").casefold())
    preview = "assets/" + re.sub(r"\.dds$", ".webp", logical)
    destination = asset_store / preview
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not reuse_previews or not destination.is_file():
        result = subprocess.run(
            [
                "magick",
                record["path"],
                "-thumbnail",
                "256x256>",
                "-define",
                "webp:lossless=true",
                str(destination),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ImageMagick failed for {logical}: {result.stderr.strip()}"
            )
    if not (record.get("catalog_icon") or is_catalog_icon(logical)):
        return None
    dimensions = subprocess.run(
        ["magick", "identify", "-format", "%w %h", record["path"]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    parts = logical.split("/")
    icon_directory = next(
        (index for index, part in enumerate(parts) if part in {"icon", "icons"}), None
    )
    scope = "icons-directory" if icon_directory is not None else "icon-named-ui"
    if icon_directory is not None and icon_directory + 2 < len(parts):
        category = parts[icon_directory + 1]
    elif icon_directory is not None:
        category = parts[icon_directory]
    else:
        category = parts[2] if len(parts) > 2 else "other"
    return {
        "path": logical,
        "preview": preview,
        "width": int(dimensions[0]),
        "height": int(dimensions[1]),
        "bytes": record["bytes"],
        "scope": scope,
        "category": category,
    }


def refresh(
    source_manifest: Path,
    asset_store: Path,
    site_data: Path,
    *,
    jobs: int,
    reuse_previews: bool,
) -> dict:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    icon_sources = source["icon_sources"]
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        converted = list(
            executor.map(
                lambda record: convert_icon(
                    record, asset_store, reuse_previews=reuse_previews
                ),
                icon_sources,
            )
        )
    icons = sorted(
        (record for record in converted if record), key=lambda item: item["path"]
    )
    glossary_meta, glossary = generate_glossary(
        Path(source["decompiled_root"]), asset_store
    )
    colour_filter_meta, colour_filters = generate_colour_filters(source_manifest)

    manifest_path = asset_store / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    game = source.get("game") or {}
    identity = game.get("identity") or {}
    target = game.get("toolchain_target") or {}
    if identity.get("steam_build_id"):
        manifest["game"]["steam_build"] = identity["steam_build_id"]
    if target.get("nms_version"):
        manifest["game"]["version"] = target["nms_version"]
    manifest["generated_on"] = datetime.now(UTC).date().isoformat()
    manifest["icons"]["count"] = len(icons)
    manifest["icons"]["icons_directory_count"] = sum(
        icon["scope"] == "icons-directory" for icon in icons
    )
    manifest["icons"]["icon_named_ui_count"] = sum(
        icon["scope"] == "icon-named-ui" for icon in icons
    )
    manifest["glossary"].update(
        {
            "count": glossary_meta["count"],
            "localized_name_count": glossary_meta["count"]
            - glossary_meta["unresolvedNames"],
            "icon_preview_count": glossary_meta["withIconPreview"],
            "localisation_banks": glossary_meta["localisationFiles"],
        }
    )
    manifest["colour_filters"] = colour_filter_meta
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = build_json_ld(
        site_data, manifest, glossary_meta, glossary, icons, colour_filters
    )
    return {
        **result,
        "converted_preview_count": len(icon_sources),
        "catalog_icon_count": len(icons),
    }


def main() -> None:
    repo = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument(
        "--asset-store",
        type=Path,
        default=repo / "games/no-mans-sky/reference/asset-wiki",
    )
    parser.add_argument(
        "--site-data",
        type=Path,
        default=repo / "site/src/data/no-mans-sky/asset-wiki",
    )
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument(
        "--reuse-previews",
        action="store_true",
        help="Reuse existing WebP files instead of reconverting matching DDS paths",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    result = refresh(
        args.source_manifest.resolve(),
        args.asset_store.resolve(),
        args.site_data.resolve(),
        jobs=args.jobs,
        reuse_previews=args.reuse_previews,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
