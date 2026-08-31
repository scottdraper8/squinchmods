from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "investigations/reterraforged/analysis/spatial_grid_analysis.py"
SPEC = importlib.util.spec_from_file_location("spatial_grid_analysis", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_adjacency_pairs_are_unordered_and_separated_by_ownership_boundary() -> None:
    # biome, provider domain, FTF cell, cell id, edge bits, unused
    records = [
        (0, 0, 10, 100, 0, 0),
        (1, 0, 10, 100, 0, 0),
        (0, 0, 20, 200, 0, 0),
        (1, 0, 20, 200, 0, 0),
    ]

    result = MODULE.adjacency_pairs(2, 2, 2, records, ["test:a", "test:b"])

    assert result["interior"] == [
        {"biomes": ["test:a", "test:b"], "edges": 2}
    ]
    assert result["both"] == []
    assert result["provider_only"] == []
    assert result["ftf_cell_only"] == []


def test_adjacency_pairs_count_a_cell_boundary_once_per_grid_edge() -> None:
    records = [
        (0, 0, 10, 100, 0, 0),
        (1, 0, 20, 200, 0, 0),
    ]

    result = MODULE.adjacency_pairs(2, 2, 1, records, ["test:a", "test:b"])

    assert result["both"] == [
        {"biomes": ["test:a", "test:b"], "edges": 1}
    ]


def test_component_summary_groups_namespaces_without_a_named_mod_allowlist() -> None:
    records = [
        (0, 0, 10, 100, 0, 0),
        (0, 0, 10, 100, 0, 0),
        (1, 0, 20, 200, 0, 0),
        (2, 0, 20, 200, 0, 0),
    ]

    _, _, namespaces = MODULE.components(
        2, 2, records, ["first:a", "first:b", "second:c"]
    )

    assert namespaces["first"] == {
        "component_count": 2,
        "sample_count": 3,
        "mean_component_samples": 1.5,
        "median_component_samples": 1.5,
        "largest_component_samples": 2,
    }
    assert namespaces["second"]["component_count"] == 1
