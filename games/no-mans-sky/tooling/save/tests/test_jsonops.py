from __future__ import annotations

import pytest

from squinch_nms_save.codec import RawNumber
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.jsonops import apply_patch, diff_values, find_matches, resolve


def test_json_patch_operations_and_pointer_escapes() -> None:
    source = {"a/b": {"~key": [1, 2]}, "copy": None}
    result = apply_patch(
        source,
        [
            {"op": "test", "path": "/a~1b/~0key/0", "value": 1},
            {"op": "replace", "path": "/a~1b/~0key/1", "value": 3},
            {"op": "copy", "from": "/a~1b/~0key", "path": "/copy"},
            {"op": "add", "path": "/a~1b/~0key/-", "value": 4},
        ],
    )

    assert resolve(result, "/a~1b/~0key") == [1, 3, 4]
    assert result["copy"] == [1, 3]
    assert source["copy"] is None


def test_json_patch_test_compares_numeric_values() -> None:
    result = apply_patch(
        {"value": RawNumber("1.00")},
        [{"op": "test", "path": "/value", "value": 1}],
    )
    assert result["value"] == RawNumber("1.00")


def test_json_patch_is_atomic_on_failure() -> None:
    source = {"value": 1}
    with pytest.raises(SaveToolError, match="operation 1"):
        apply_patch(
            source,
            [
                {"op": "replace", "path": "/value", "value": 2},
                {"op": "remove", "path": "/missing"},
            ],
        )
    assert source == {"value": 1}


def test_find_and_diff_are_bounded() -> None:
    document = {"alpha": "needle", "nested": {"alphabet": "needle two"}}
    matches, truncated = find_matches(
        document, key_pattern="alpha", value_pattern="needle", limit=1
    )
    assert len(matches) == 1
    assert truncated

    difference = diff_values({"a": 1, "b": 2}, {"a": 3, "c": 4}, limit=2)
    assert len(difference.changes) == 2
    assert difference.truncated
