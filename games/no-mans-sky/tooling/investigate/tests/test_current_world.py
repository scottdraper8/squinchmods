from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from squinch_nms_investigate import current_world
from squinch_nms_investigate.errors import InvestigationError


def publish(directory: Path, *, player: int | None, world: dict | None) -> None:
    directory.mkdir()
    instance = "1234abcd-" + "a" * 32
    (directory / "agent-control.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "instance": instance,
                "protocol": {"id": "search-probes.agent-control", "version": 1},
                "capabilities": ["search.control/v1", "nms.current-world/v1"],
            }
        ),
        encoding="utf-8",
    )
    (directory / "current.json").write_text(
        json.dumps({"generation": 7, "player": player, "current_world": world}),
        encoding="utf-8",
    )
    now = time.time()
    os.utime(directory / "agent-control.json", (now, now))
    os.utime(directory / "current.json", (now, now))


def test_current_world_returns_matching_live_snapshot(tmp_path: Path) -> None:
    world = {
        "schema": 1,
        "command_id": 9,
        "address": 42,
        "acquisition": "criteria_and_core",
        "criteria": {},
        "system": {
            "fields": {},
            "planet_flags": {},
            "system_flags": {},
            "resources": None,
        },
        "planet": None,
        "system_verdict": "match",
        "planet_verdict": None,
        "target_verdict": "match",
        "criteria_evaluations": [],
        "section_evaluations": [],
    }
    publish(tmp_path / "runtime", player=42, world=world)

    _, state, result = current_world.snapshot(tmp_path / "runtime")

    assert state["generation"] == 7
    assert result == world


def test_current_world_rejects_uncaptured_system(tmp_path: Path) -> None:
    publish(tmp_path / "runtime", player=42, world=None)

    with pytest.raises(InvestigationError) as caught:
        current_world.snapshot(tmp_path / "runtime")

    assert caught.value.code == "current_world_uncaptured"
    assert caught.value.details == {"player": 42}


def test_current_world_rejects_stale_location(tmp_path: Path) -> None:
    publish(
        tmp_path / "runtime",
        player=42,
        world={"schema": 1, "command_id": 9, "address": 41},
    )

    with pytest.raises(InvestigationError) as caught:
        current_world.snapshot(tmp_path / "runtime")

    assert caught.value.code == "current_world_changed"


def test_current_world_requests_fresh_native_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = {
        "schema": 1,
        "command_id": 17,
        "address": 42,
        "acquisition": "criteria_and_core",
        "criteria": {},
        "system": {
            "fields": {},
            "planet_flags": {},
            "system_flags": {},
            "resources": None,
        },
        "planet": None,
        "system_verdict": "match",
        "planet_verdict": None,
        "target_verdict": "match",
        "criteria_evaluations": [],
        "section_evaluations": [],
    }
    directory = tmp_path / "runtime"
    publish(directory, player=42, world=world)
    requested: list[tuple[Path, dict, float]] = []

    def command(path: Path, action: dict, *, timeout: float) -> dict:
        requested.append((path, action, timeout))
        return {"phase": "applied", "acknowledgement": {"command_id": 17}}

    monkeypatch.setattr(current_world.runtime_protocol, "command", command)

    _, _, result = current_world.inspect(directory, timeout=45)

    assert result == world
    assert requested == [(directory, {"type": "inspect_current"}, 45)]
