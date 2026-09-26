#!/usr/bin/env python3
"""Summarize retained worldgen-normalization census results without probe internals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROBE_ID = "squinch:ftf-worldgen-normalization-census"


def summary_path(value: str) -> Path:
    path = Path(value).resolve()
    return path / "scenario-summary.json" if path.is_dir() else path


def probe_result(document: dict[str, Any]) -> dict[str, Any]:
    for step in document.get("steps", []):
        outer = step.get("result", {})
        if outer.get("request", {}).get("probe_id") == PROBE_ID:
            return outer["result"]
    raise ValueError(f"retained summary has no {PROBE_ID} result")


def third_party_types(data: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for domain, values in data.get("registered_worldgen_types", {}).items():
        result[domain] = sorted(value for value in values if not value.startswith("minecraft:"))
    return result


def summarize(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    data = probe_result(document)
    codecs: dict[str, Any] = {}
    for domain, value in sorted(data.get("codec_round_trip", {}).items()):
        codecs[domain] = {
            "objects": value["objects"],
            "exact_json": value["exact_json_round_trips"],
            "canonical_fixed_point": value.get(
                "canonical_fixed_point_round_trips", value["exact_json_round_trips"]
            ),
            "operation_failures": value["encode_failures"]
            + value["decode_failures"]
            + value["reencode_failures"],
            "non_exact": value.get("non_exact_round_trips", 0),
            "examples": value.get("failure_examples", []),
        }
    clone = data.get("generator_clone_parity", {})
    layers = data.get("worldgen_resource_layers", {})
    return {
        "run_id": document["run_id"],
        "scenario": document["scenario"]["name"],
        "state": document["state"],
        "authority": data["authority"],
        "generator_class": data["generator_class"],
        "biome_source_class": data["biome_source_class"],
        "counts": {
            key: data[key]
            for key in (
                "possible_biomes",
                "active_placed_features",
                "active_configured_features",
                "active_configured_carvers",
                "possible_structure_sets",
                "possible_structures",
                "registered_density_functions",
                "codec_objects_tested",
                "codec_operation_failures",
                "codec_json_mismatches",
            )
            if key in data
        },
        "third_party_registered_types": third_party_types(data),
        "codec_domains": codecs,
        "generator_clone_parity": {
            key: clone[key]
            for key in (
                "clone_available",
                "generator_class_equal",
                "biome_source_class_equal",
                "possible_biomes_equal",
                "biome_samples",
                "biome_mismatches",
                "biome_query_error",
                "isolated_random_state_clone_available",
                "density_samples",
                "density_mismatches",
            )
            if key in clone
        },
        "worldgen_resource_layers": {
            "keys": layers.get("keys", 0),
            "layers": layers.get("layers", 0),
            "overridden_keys": layers.get("overridden_keys", 0),
            "keys_by_category": layers.get("keys_by_category", {}),
            "keys_by_pack": layers.get("keys_by_pack", {}),
            "errors": layers.get("errors", []),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summaries", nargs="+", help="run directories or scenario-summary.json files")
    args = parser.parse_args()
    results = [summarize(summary_path(value)) for value in args.summaries]
    print(json.dumps({"schema_version": 1, "runs": results}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
