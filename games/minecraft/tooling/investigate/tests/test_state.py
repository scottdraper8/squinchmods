from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_minecraft_investigate.state import atomic_write_json
from squinch_minecraft_investigate.server import _remove_protocol_files


def test_failed_atomic_replace_preserves_previous_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Catches interrupted writes replacing valid process ownership state with partial data."""
    path = tmp_path / "active.json"
    atomic_write_json(path, {"generation": 1})

    def fail_replace(source: str, destination: Path) -> None:
        raise OSError("controlled replace failure")

    monkeypatch.setattr("squinch_minecraft_investigate.state.os.replace", fail_replace)
    with pytest.raises(OSError, match="controlled"):
        atomic_write_json(path, {"generation": 2})

    assert json.loads(path.read_text()) == {"generation": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_protocol_cleanup_removes_only_identity_validated_run_files(tmp_path: Path) -> None:
    """Catches probe requests being stranded in a target loader's shared run directory."""
    run_dir = tmp_path / "loader-run"
    request = run_dir / ".squinch-investigate" / "requests" / "request.json"
    result = run_dir / ".squinch-investigate" / "results" / "request.json"
    atomic_write_json(request, {"run_id": "run-1"})
    atomic_write_json(result, {"run_id": "run-1", "state": "pass"})

    failures = _remove_protocol_files(
        {
            "run_id": "run-1",
            "run_dir": str(run_dir),
            "protocol_files": [str(request), str(result)],
        }
    )

    assert failures == []
    assert not (run_dir / ".squinch-investigate").exists()
