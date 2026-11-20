from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from squinch_nms_investigate import runtime_protocol
from squinch_nms_investigate.errors import InvestigationError


def publish(directory: Path, endpoint: dict) -> None:
    directory.mkdir()
    (directory / "agent-control.json").write_text(json.dumps(endpoint), encoding="utf-8")
    (directory / "current.json").write_text(json.dumps({"generation": 1}), encoding="utf-8")
    now = time.time()
    os.utime(directory / "agent-control.json", (now, now))
    os.utime(directory / "current.json", (now, now))


def test_versioned_endpoint_advertises_explicit_capabilities(tmp_path: Path) -> None:
    directory = tmp_path / "runtime"
    publish(
        directory,
        {
            "schema": 2,
            "instance": "1234abcd-" + "b" * 32,
            "protocol": {"id": "search-probes.agent-control", "version": 1},
            "capabilities": ["search.control/v1", "nms.current-world/v1"],
        },
    )

    endpoint, _ = runtime_protocol.status(directory, required_capability="nms.current-world/v1")

    assert runtime_protocol.capabilities(endpoint) == {
        "search.control/v1",
        "nms.current-world/v1",
    }


def test_unknown_protocol_version_fails_closed(tmp_path: Path) -> None:
    directory = tmp_path / "runtime"
    publish(
        directory,
        {
            "schema": 2,
            "instance": "1234abcd-" + "c" * 32,
            "protocol": {"id": "search-probes.agent-control", "version": 2},
            "capabilities": ["search.control/v1"],
        },
    )

    with pytest.raises(InvestigationError) as caught:
        runtime_protocol.status(directory)

    assert caught.value.code == "runtime_protocol_incompatible"


def test_state_uses_its_larger_bounded_publication_contract(tmp_path: Path) -> None:
    directory = tmp_path / "runtime"
    publish(
        directory,
        {
            "schema": 2,
            "instance": "1234abcd-" + "d" * 32,
            "protocol": {"id": "search-probes.agent-control", "version": 1},
            "capabilities": ["search.control/v1"],
        },
    )
    state = {"generation": 1, "history": "x" * 1_200_000}
    (directory / "current.json").write_text(json.dumps(state), encoding="utf-8")

    _, published = runtime_protocol.status(directory)

    assert published == state
