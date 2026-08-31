#!/usr/bin/env python3
"""Independently recalculate retained spatial-compatibility raw grids."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import statistics
import struct
from collections import Counter, deque
from pathlib import Path


MAGIC = 0x52544653
HEADER = struct.Struct(">7i")
RECORD_V1 = struct.Struct(">6i")
RECORD_V2 = struct.Struct(">3iq2i")


def transition_category(version: int, left: tuple[int, ...], right: tuple[int, ...]) -> str:
    provider_only = "terrablender_only" if version == 1 else "provider_only"
    region_change = left[2] != right[2]
    cell_change = left[3] != right[3]
    return (
        "both" if region_change and cell_change else
        provider_only if region_change else
        "ftf_cell_only" if cell_change else
        "interior"
    )


def terminal_record(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    terminal = [record for record in records if record.get("type") == "terminal"]
    if len(terminal) != 1 or terminal[0].get("state") != "pass":
        raise ValueError(f"expected one passing terminal record in {path}")
    return terminal[0]


def decode(record: dict) -> tuple[tuple[int, ...], list[tuple[int, ...]]]:
    raw = record["raw_grid"]
    compressed = base64.b64decode(raw["data"], validate=True)
    digest = hashlib.sha256(compressed).hexdigest()
    if digest != raw["sha256"]:
        raise ValueError(f"raw-grid SHA-256 mismatch: {digest} != {raw['sha256']}")
    payload = gzip.decompress(compressed)
    header = HEADER.unpack_from(payload)
    magic, version, width, height, origin_x, origin_z, step = header
    if magic != MAGIC or version not in (1, 2):
        raise ValueError(f"unsupported grid header: {header}")
    record_struct = RECORD_V1 if version == 1 else RECORD_V2
    expected = HEADER.size + width * height * record_struct.size
    if len(payload) != expected:
        raise ValueError(f"raw-grid size mismatch: {len(payload)} != {expected}")
    records = [
        record_struct.unpack_from(payload, HEADER.size + index * record_struct.size)
        for index in range(width * height)
    ]
    return (version, width, height, origin_x, origin_z, step), records


def transitions(version: int, width: int, height: int, records: list[tuple[int, ...]]) -> dict:
    provider_only = "terrablender_only" if version == 1 else "provider_only"
    counts = {
        name: {"edges": 0, "biome_changes": 0, "edge_sum": 0.0}
        for name in ("interior", provider_only, "ftf_cell_only", "both")
    }

    def signed_float(bits: int) -> float:
        return struct.unpack(">f", struct.pack(">i", bits))[0]

    def add(left: int, right: int) -> None:
        biome_change = records[left][0] != records[right][0]
        category = transition_category(version, records[left], records[right])
        target = counts[category]
        target["edges"] += 1
        target["biome_changes"] += int(biome_change)
        target["edge_sum"] += (
            signed_float(records[left][4]) + signed_float(records[right][4])
        ) * 0.5

    for z in range(height):
        for x in range(width):
            index = z * width + x
            if x + 1 < width:
                add(index, index + 1)
            if z + 1 < height:
                add(index, index + width)
    for target in counts.values():
        edges = target["edges"]
        target["biome_change_fraction"] = target["biome_changes"] / edges if edges else 0.0
        target["mean_ftf_biome_region_edge"] = target.pop("edge_sum") / edges if edges else 0.0
    return counts


def adjacency_pairs(
    version: int,
    width: int,
    height: int,
    records: list[tuple[int, ...]],
    biome_dictionary: list[str],
) -> dict[str, list[dict]]:
    provider_only = "terrablender_only" if version == 1 else "provider_only"
    counts = {
        name: Counter()
        for name in ("interior", provider_only, "ftf_cell_only", "both")
    }

    def add(left_index: int, right_index: int) -> None:
        left = records[left_index]
        right = records[right_index]
        if left[0] == right[0]:
            return
        pair = tuple(sorted((biome_dictionary[left[0]], biome_dictionary[right[0]])))
        counts[transition_category(version, left, right)][pair] += 1

    for z in range(height):
        for x in range(width):
            index = z * width + x
            if x + 1 < width:
                add(index, index + 1)
            if z + 1 < height:
                add(index, index + width)

    return {
        category: [
            {"biomes": list(pair), "edges": edges}
            for pair, edges in sorted(
                category_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        for category, category_counts in counts.items()
    }


def components(
    width: int,
    height: int,
    records: list[tuple[int, ...]],
    biome_dictionary: list[str],
) -> tuple[int, dict[str, dict], dict[str, dict]]:
    visited = bytearray(width * height)
    by_biome: dict[str, list[dict]] = {}
    total = 0
    for start in range(width * height):
        if visited[start]:
            continue
        total += 1
        biome_index = records[start][0]
        queue = deque([start])
        visited[start] = 1
        area = 0
        regions: set[int] = set()
        cells: set[int] = set()
        while queue:
            index = queue.popleft()
            area += 1
            regions.add(records[index][2])
            cells.add(records[index][3])
            x = index % width
            z = index // width
            neighbors = []
            if x:
                neighbors.append(index - 1)
            if x + 1 < width:
                neighbors.append(index + 1)
            if z:
                neighbors.append(index - width)
            if z + 1 < height:
                neighbors.append(index + width)
            for neighbor in neighbors:
                if not visited[neighbor] and records[neighbor][0] == biome_index:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        biome = biome_dictionary[biome_index]
        by_biome.setdefault(biome, []).append({
            "samples": area,
            "provider_domains": len(regions),
            "ftf_cells": len(cells),
        })
    summaries = {}
    for biome, values in by_biome.items():
        largest = max(values, key=lambda value: value["samples"])
        summaries[biome] = {
            "component_count": len(values),
            "sample_count": sum(value["samples"] for value in values),
            "largest": largest,
            "spanning_provider_domains": sum(
                value["provider_domains"] > 1 for value in values
            ),
            "spanning_ftf_cells": sum(value["ftf_cells"] > 1 for value in values),
        }
    namespace_samples: dict[str, list[int]] = {}
    for biome, values in by_biome.items():
        namespace = biome.partition(":")[0]
        namespace_samples.setdefault(namespace, []).extend(
            value["samples"] for value in values
        )
    namespace_summaries = {
        namespace: {
            "component_count": len(samples),
            "sample_count": sum(samples),
            "mean_component_samples": sum(samples) / len(samples),
            "median_component_samples": statistics.median(samples),
            "largest_component_samples": max(samples),
        }
        for namespace, samples in sorted(namespace_samples.items())
    }
    return total, summaries, namespace_summaries


def analyze(path: Path) -> dict:
    terminal = terminal_record(path)
    header, records = decode(terminal)
    version, width, height, origin_x, origin_z, step = header
    transition_summary = transitions(version, width, height, records)
    component_count, biome_components, namespace_components = components(
        width, height, records, terminal["biome_dictionary"]
    )
    pair_summary = adjacency_pairs(
        version, width, height, records, terminal["biome_dictionary"]
    )
    region_counts = Counter(record[2] for record in records)
    probe_transitions = terminal["transition_ownership"]
    transition_matches = all(
        transition_summary[name]["edges"] == probe_transitions[name]["adjacent_edges"]
        and transition_summary[name]["biome_changes"] == probe_transitions[name]["biome_changes"]
        for name in transition_summary
    )
    return {
        "probe": str(path.resolve()),
        "raw_grid_sha256": terminal["raw_grid"]["sha256"],
        "grid": {
            "schema_version": version,
            "width": width,
            "height": height,
            "origin_block_x": origin_x,
            "origin_block_z": origin_z,
            "step_blocks": step,
            "samples": len(records),
        },
        "independent_checks": {
            "component_count_matches": (
                component_count == terminal["component_topology"]["component_count"]
            ),
            "transitions_match": transition_matches,
        },
        "component_count": component_count,
        "ice_spikes": biome_components.get("minecraft:ice_spikes"),
        "namespace_components": namespace_components,
        "biome_adjacency_pairs": pair_summary,
        "provider_domain_samples": dict(sorted(region_counts.items())),
        "transitions": transition_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe_jsonl", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.probe_jsonl), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
