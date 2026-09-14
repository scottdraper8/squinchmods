from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _matrix_module(monkeypatch):
    runtime = Path(__file__).parents[2] / "runtime"
    monkeypatch.syspath_prepend(str(runtime))
    monkeypatch.syspath_prepend(
        str(Path(__file__).parents[3] / "mods/search-probes/src")
    )
    path = runtime / "resident_search_matrix.py"
    spec = importlib.util.spec_from_file_location("resident_search_matrix_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_require_search_matches_accepts_only_nonempty_positive_results(monkeypatch) -> None:
    matrix = _matrix_module(monkeypatch)
    searches = {
        "paradise": {"matched": True, "matches": [{"address": "1"}]},
        "waterworld": {
            "matched": True,
            "matches": [{"address": "2"}, {"address": "3"}],
        },
    }
    assert matrix._require_search_matches(searches, ("paradise", "waterworld")) == {
        "paradise": 1,
        "waterworld": 2,
    }


def test_first_object_source_control_uses_exact_planet_sample(monkeypatch) -> None:
    matrix = _matrix_module(monkeypatch)
    assert matrix._first_object_source_control(
        {
            "samples": {
                "object_list_source_option": {
                    "METADATA/OBJECTS.MBIN": {
                        "address": "0xABCD",
                        "planet": 4,
                    }
                }
            }
        },
        "0x1234",
    ) == ("0xABCD", 4)
    assert matrix._first_object_source_control({}, "0x1234") == ("0x1234", 0)


def test_first_remote_enumerated_address_skips_current_system(monkeypatch) -> None:
    matrix = _matrix_module(monkeypatch)
    enumeration = {
        "candidates": [
            {"address": "0xCURRENT"},
            {"address": "0xREMOTE"},
        ]
    }
    assert matrix._first_remote_enumerated_address(enumeration) == "0xREMOTE"

    with pytest.raises(RuntimeError, match="remote candidate"):
        matrix._first_remote_enumerated_address({"candidates": []})


def test_resolved_asset_summary_counts_exact_object_flags(monkeypatch) -> None:
    matrix = _matrix_module(monkeypatch)
    assert matrix._resolved_asset_summary(
        {
            "collections": {
                "objects": {
                    "records": [
                        {
                            "source_object": {
                                "debug_name": "ISLAND_A",
                                "is_floating_island": True,
                            },
                            "selected_resource": {"filename": "SCENES/ISLAND_A.SCENE.MBIN"},
                        },
                        {
                            "source_object": {
                                "debug_name": "TREE_A",
                                "is_floating_island": False,
                            },
                            "selected_resource": {"filename": "SCENES/TREE_A.SCENE.MBIN"},
                        },
                    ]
                },
                "landmarks": {"records": []},
            }
        }
    ) == {
        "record_count": 2,
        "floating_island_count": 1,
        "selected_filenames": [
            "SCENES/ISLAND_A.SCENE.MBIN",
            "SCENES/TREE_A.SCENE.MBIN",
        ],
        "source_debug_names": ["ISLAND_A", "TREE_A"],
    }
@pytest.mark.parametrize(
    "searches,label,error",
    (
        ({}, "missing", TypeError),
        ({"negative": {"matched": False, "matches": []}}, "negative", RuntimeError),
        ({"empty": {"matched": True, "matches": []}}, "empty", RuntimeError),
    ),
)
def test_require_search_matches_fails_closed(monkeypatch, searches, label, error) -> None:
    matrix = _matrix_module(monkeypatch)
    with pytest.raises(error):
        matrix._require_search_matches(searches, (label,))
