from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "build_asset_wiki.py"
SPEC = importlib.util.spec_from_file_location("build_asset_wiki", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_builds_json_ld_with_public_previews(tmp_path: Path) -> None:
    output = tmp_path / "output"
    result = MODULE.build(
        output,
        {"game": {"version": "7.14", "steam_build": "1"}},
        {"count": 1},
        [
            {
                "id": "TEST",
                "name": "Test",
                "kind": "Product",
                "preview": "assets/test.webp",
            }
        ],
        [{"path": "test.dds", "preview": "assets/test.webp"}],
        [
            {
                "native_value": 12,
                "name": "Weird1",
                "samples": [],
                "grey_ramp": [],
            }
        ],
    )
    items = json.loads((output / "items.jsonld").read_text(encoding="utf-8"))
    assert result["datasets"] == {
        "items": 1,
        "icons": 1,
        "colour-filters": 1,
    }
    assert items["@graph"][0]["preview"] == "/asset-wiki/assets/test.webp"
    assert items["@graph"][0]["@id"].endswith("/item/product/TEST")
    colour_filters = json.loads(
        (output / "colour-filters.jsonld").read_text(encoding="utf-8")
    )
    assert colour_filters["@graph"][0]["@id"].endswith("/world-colour-filter/12")
