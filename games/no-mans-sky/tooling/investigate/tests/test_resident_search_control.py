from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _control_module(monkeypatch):
    runtime = Path(__file__).parents[2] / "runtime"
    monkeypatch.syspath_prepend(str(runtime))
    monkeypatch.syspath_prepend(
        str(Path(__file__).parents[3] / "mods/search-probes/src")
    )
    path = runtime / "resident_search_control.py"
    spec = importlib.util.spec_from_file_location("resident_search_control_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_next_generation_uses_resident_state(tmp_path: Path, monkeypatch) -> None:
    control = _control_module(monkeypatch)
    (tmp_path / "state.json").write_text('{"generation":17}\n', encoding="utf-8")
    assert control._next_generation(tmp_path) == 18


def test_stop_restores_hook_before_sending_executor_escape(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    control = _control_module(monkeypatch)
    events: list[object] = []

    monkeypatch.setattr(control, "_session", lambda: tmp_path)
    monkeypatch.setattr(control, "_nms_pids", lambda: {42})
    monkeypatch.setattr(
        control,
        "_read_json",
        lambda _path: {"generation": 8, "state": "closed"},
    )

    def write_command(path: Path, payload: object) -> None:
        events.append(("command", path.name, payload))

    monkeypatch.setattr(control, "_atomic_json", write_command)
    monkeypatch.setattr(control, "_focus_nms_window", lambda: events.append("focus") or True)

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def sendall(self, payload: bytes) -> None:
            events.append(("executor", payload))

    connections = 0

    def connect(_address, timeout: float):
        nonlocal connections
        assert timeout > 0
        connections += 1
        if connections == 1:
            return Client()
        raise ConnectionRefusedError

    monkeypatch.setattr(control.socket, "create_connection", connect)
    assert control._stop(argparse.Namespace(wait=1.0)) == 0
    command = events[0][2]
    assert command["action"] == "shutdown"
    assert command["generation"] == 9
    assert events[1] == "focus"
    assert events[2] == ("executor", control.EXECUTOR_ESCAPE)
    result = json.loads(capsys.readouterr().out)
    assert result["hook_restored"] is True
    assert result["executor_closed"] is True
    assert result["nms_pid"] == 42
