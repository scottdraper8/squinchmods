from __future__ import annotations

import pytest

from squinch_minecraft_investigate.cell_scan import (
    CELL_FIELDS,
    _fields,
    _predicate,
    _tiles,
    _validate_result,
)


def test_default_fields_are_supported_by_the_current_cell_model() -> None:
    assert set(_fields([], [], "height")) <= CELL_FIELDS
    assert "biome_type" not in CELL_FIELDS
from squinch_minecraft_investigate.errors import InvestigationError


def test_tile_selection_uses_floor_coordinates_across_negative_origin() -> None:
    """Catches truncation toward zero, which would silently omit negative RTF tiles."""
    assert _tiles([-129, -129, 0, 0], 3) == [
        {"x": x, "z": z} for z in (-2, -1, 0) for x in (-2, -1, 0)
    ]


def test_predicate_parser_preserves_numeric_and_categorical_expectations() -> None:
    """Catches predicate parsing that coerces terrain IDs to numbers or accepts ambiguous syntax."""
    assert _predicate("height:>=:0.5") == {"field": "height", "op": ">=", "value": 0.5}
    assert _predicate("terrain:==:mountains_3") == {
        "field": "terrain", "op": "==", "value": "mountains_3",
    }
    with pytest.raises(InvestigationError):
        _predicate("height >= 0.5")


def test_cell_result_rejects_malformed_output() -> None:
    with pytest.raises(InvestigationError) as caught:
        _validate_result({"mode": "preview", "cold_warm_equal": True}, {"mode": "preview"})

    assert caught.value.code == "cell_scan_result_invalid"
