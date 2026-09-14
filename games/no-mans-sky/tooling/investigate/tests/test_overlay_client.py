from __future__ import annotations

import json
import threading
from pathlib import Path

from search_probes.overlay_client import OverlayClient


def _client(tmp_path: Path) -> OverlayClient:
    commands = tmp_path / "commands"
    results = tmp_path / "results"
    commands.mkdir()
    results.mkdir()
    return OverlayClient(
        commands,
        results,
        threading.Lock(),
        lambda: 4,
        lambda: {"revision": 2, "state": "idle"},
        object(),
        lambda *_args, **_kwargs: None,
    )


def test_write_command_normalizes_and_publishes_atomically(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.write_command(
        {"protocol": 1, "id": "cmd-1", "generation": 4, "action": "cancel", "target_id": "target"}
    )

    payload = json.loads((tmp_path / "commands/cmd-1.json").read_text())
    assert payload["protocol"] == 1
    assert payload["id"] == "cmd-1"
    assert not list((tmp_path / "commands").glob("*.tmp"))


def test_result_reads_are_locked_and_paths_are_explicit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    result_path = client.result_path("cmd-2")
    result_path.write_text('{"status":"completed"}\n')

    assert client.read_result(result_path) == {"status": "completed"}
    assert client.progress_path("cmd-2").name == "cmd-2.progress.json"
    assert client.next_generation() == 5
