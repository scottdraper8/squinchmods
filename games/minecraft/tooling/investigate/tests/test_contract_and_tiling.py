from __future__ import annotations

import argparse
from pathlib import Path

import jsonschema
import pytest

from squinch_minecraft_investigate import cli, generation
from squinch_minecraft_investigate.output import _schema, envelope


def test_json_contract_rejects_missing_error_field() -> None:
    """Catches a CLI refactor that silently drops a required agent-facing key."""
    value = envelope("status", "inactive", data={"project": "/tmp/project", "loader": "fabric"})
    del value["error"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, _schema())


def test_chunk_tiling_has_independent_inclusive_boundaries() -> None:
    """Catches inclusive/exclusive mistakes and illegal tiles larger than 16x16 chunks."""
    regions = generation.tile_chunks((-17, -1, 16, 16), "block")

    assert regions == [
        {
            "chunk_min_x": -2,
            "chunk_min_z": -1,
            "chunk_max_x": 1,
            "chunk_max_z": 1,
            "block_min_x": -32,
            "block_min_z": -16,
            "block_max_x": 31,
            "block_max_z": 31,
        }
    ]

    large = generation.tile_chunks((0, 0, 32, 17), "chunk")
    assert [(item["chunk_max_x"] - item["chunk_min_x"] + 1, item["chunk_max_z"] - item["chunk_min_z"] + 1) for item in large] == [
        (16, 16),
        (16, 2),
        (16, 16),
        (16, 2),
        (1, 16),
        (1, 2),
    ]
    assert large[-1]["block_max_x"] == 527
    assert large[-1]["block_max_z"] == 287


def test_generate_command_reports_the_real_region_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Catches a stale variable reference in the generate command's success message. The CLI
    crashed with NameError on its first real invocation because the human-readable summary
    referenced a variable name ('regions') that had been renamed to 'results'; this exercises
    that exact line without needing a live server."""
    project = tmp_path / "fake-project"
    (project / "fabric").mkdir(parents=True)
    (project / "gradlew").write_text("#!/bin/sh\n")

    fake_state = {
        "run_id": "run-1",
        "started_at": "2026-08-01T00:00:00Z",
        "artifact_dir": str(tmp_path / "artifacts"),
        "log_path": str(tmp_path / "server.log"),
        "lifecycle": "ready",
    }
    fake_regions = [{"chunk_min_x": 0, "chunk_min_z": 0, "chunk_max_x": 15, "chunk_max_z": 15}]

    monkeypatch.setattr(cli, "load_active", lambda *_args, **_kwargs: fake_state)
    monkeypatch.setattr(cli, "generate_regions", lambda *_args, **_kwargs: fake_regions)

    args = argparse.Namespace(
        project=str(project), loader="fabric", bounds=[0, 0, 15, 15], unit="chunk", timeout=1.0
    )
    value, message = cli._generate(args)

    assert message == "generated 1 region tile(s)"
    assert value["data"]["regions"] == fake_regions


def test_release_regions_forgets_only_each_acknowledged_owned_tile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = {"block_min_x": 1, "block_min_z": 2, "block_max_x": 3, "block_max_z": 4}
    second = {"block_min_x": 5, "block_min_z": 6, "block_max_x": 7, "block_max_z": 8}
    state = {"forceload_regions": [first, second]}
    commands: list[str] = []
    snapshots: list[list[dict[str, int]]] = []

    def run(_state: dict, values: list[str], _timeout: float) -> list[dict]:
        commands.extend(values)
        return [{"command": values[0], "response": "Unmarked"}]

    monkeypatch.setattr(generation, "run_commands", run)
    monkeypatch.setattr(
        generation,
        "persist_active",
        lambda current: snapshots.append(list(current["forceload_regions"])),
    )

    released = generation.release_regions(state, [first, second], 10)

    assert commands == ["forceload remove 5 6 7 8", "forceload remove 1 2 3 4"]
    assert [item["region"] for item in released] == [second, first]
    assert snapshots == [[first], []]
    assert state["forceload_regions"] == []
