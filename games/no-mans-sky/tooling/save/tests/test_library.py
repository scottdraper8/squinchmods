from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.library import publish_library, publish_systems_library


def _inventory(path: Path, suffix: str = "one") -> None:
    path.mkdir(parents=True)
    for name, field in (
        ("bases", "bases"),
        ("starships", "starships"),
        ("multitools", "multitools"),
    ):
        rows = [{"identity": f"{name}:{suffix}", "data": {"Name": suffix}}]
        (path / f"{name}.json").write_text(
            json.dumps(
                {
                    "schema_version": "2",
                    "mapping_sha256": "mapping",
                    "profile": "/profile",
                    "unique_count": len(rows),
                    field: rows,
                }
            )
        )


def test_publish_library_is_persistent_atomic_and_versioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    monkeypatch.setenv("SQUINCH_REPO_ROOT", str(repo))
    inventory = tmp_path / "inventory"
    _inventory(inventory)
    output = repo / "games/no-mans-sky/local/save-library"

    result = publish_library(inventory, output, replace=False)

    assert result["counts"] == {"bases": 1, "starships": 1, "multitools": 1}
    assert not (output / "ships.json").exists()
    assert json.loads((output / "manifest.json").read_text())["schema"] == (
        "squinch-nms-entity-library-v1"
    )
    with pytest.raises(SaveToolError, match="pass --replace"):
        publish_library(inventory, output, replace=False)

    second = tmp_path / "second"
    _inventory(second, "two")
    publish_library(second, output, replace=True)
    assert json.loads((output / "starships.json").read_text())["starships"][0]["identity"] == (
        "starships:two"
    )
    history = output.parent / "save-library.history"
    assert len(list(history.iterdir())) == 1


def test_publish_systems_adds_authority_without_replacing_existing_entities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    monkeypatch.setenv("SQUINCH_REPO_ROOT", str(repo))
    inventory = tmp_path / "inventory"
    _inventory(inventory)
    output = repo / "games/no-mans-sky/local/save-library"
    publish_library(inventory, output, replace=False)
    original_starships = (output / "starships.json").read_bytes()
    systems = tmp_path / "systems.json"
    systems.write_text(
        json.dumps(
            {
                "schema": "squinch-nms-systems-library-v1",
                "profile": "/profile",
                "mapping": {"sha256": "mapping"},
                "unique_count": 1,
                "record_counts": {"stored": 1, "available": 0, "enqueued": 0},
                "visited_system_count": 1,
                "systems": [
                    {
                        "identity": "system:0x1",
                        "system_address": "0x1",
                        "galaxy": 1,
                    }
                ],
            }
        )
    )

    result = publish_systems_library(systems, output)

    assert result["unique_systems"] == 1
    assert (output / "starships.json").read_bytes() == original_starships
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema"] == "squinch-nms-entity-library-v2"
    assert manifest["artifacts"]["systems"]["unique_count"] == 1

    replacement = tmp_path / "replacement"
    _inventory(replacement, "replacement")
    publish_library(replacement, output, replace=True)
    assert json.loads((output / "systems.json").read_text())["unique_count"] == 1
    assert json.loads((output / "manifest.json").read_text())["schema"] == (
        "squinch-nms-entity-library-v2"
    )
