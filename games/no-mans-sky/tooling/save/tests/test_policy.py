from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.policy import SavePolicy


def test_default_policy_resolves_dynamic_ranges() -> None:
    policy = SavePolicy.default()

    assert policy.classify("Galaxies 51-60").galaxies == (51, 60)
    assert policy.classify("Galaxy 256 Super Build").galaxies == (256, 256)
    assert policy.classify("Survival").category == "non-galaxy-centric"


def test_custom_policy_rejects_overlapping_rules(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema": "squinch-nms-save-policy-v1",
                "owned_base_types": ["HomePlanetBase", "FreighterBase"],
                "portable_base_types": ["FreighterBase"],
                "rules": [
                    {
                        "id": "first",
                        "save_name_regex": "Save",
                        "category": "range",
                        "galaxies": [1, 1],
                    },
                    {
                        "id": "second",
                        "save_name_regex": "Save",
                        "category": "range",
                        "galaxies": [2, 2],
                    },
                ],
            }
        )
    )

    with pytest.raises(SaveToolError, match="matches multiple policy rules"):
        SavePolicy.load(path).classify("Save")
