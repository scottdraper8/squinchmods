from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.probe_requests import read_probe_transcript


def _request() -> dict:
    return {
        "protocol_version": "1",
        "run_id": "run-1",
        "request_id": "request-1",
        "probe_id": "squinch:test",
        "probe_version": "1",
    }


def _record(record_type: str, **values: object) -> dict:
    return {
        **_request(),
        "type": record_type,
        "timestamp": "2026-08-01T00:00:00Z",
        **values,
    }


def _write(path: Path, *records: dict) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


def test_jsonl_transcript_requires_exactly_one_final_terminal(tmp_path: Path) -> None:
    """Catches duplicate, absent, or non-final terminal publication after a runtime retry."""
    path = tmp_path / "result.jsonl"
    accepted = _record("progress", event="accepted")
    terminal = _record(
        "terminal",
        state="pass",
        phase="finished-chunk",
        completeness={"inspected": 1, "skipped": 0, "complete": True},
    )
    _write(path, accepted, terminal)

    records, parsed = read_probe_transcript(path, _request())

    assert len(records) == 2
    assert parsed == terminal

    _write(path, accepted, terminal, terminal)
    with pytest.raises(InvestigationError, match="exactly one terminal"):
        read_probe_transcript(path, _request())

    _write(path, accepted)
    with pytest.raises(InvestigationError, match="found 0"):
        read_probe_transcript(path, _request())

    _write(path, terminal, accepted)
    with pytest.raises(InvestigationError, match="must be the final"):
        read_probe_transcript(path, _request())


def test_jsonl_transcript_rejects_identity_drift(tmp_path: Path) -> None:
    """Catches one request consuming another request's otherwise valid terminal result."""
    path = tmp_path / "result.jsonl"
    terminal = _record("terminal", state="error", phase="reload")
    terminal["run_id"] = "different-run"
    _write(path, terminal)

    with pytest.raises(InvestigationError, match="identity does not match"):
        read_probe_transcript(path, _request())


def test_jsonl_transcript_rejects_unknown_terminal_state(tmp_path: Path) -> None:
    """Catches a runtime spelling or enum drift being treated as a successful terminal."""
    path = tmp_path / "result.jsonl"
    _write(path, _record("terminal", state="mostly-pass", phase="generation"))

    with pytest.raises(InvestigationError, match="invalid or missing"):
        read_probe_transcript(path, _request())


@pytest.mark.parametrize(
    ("state", "complete"),
    (("pass", False), ("fail", False), ("inconclusive", True), ("error", True)),
)
def test_jsonl_transcript_rejects_terminal_completeness_conflicts(
    tmp_path: Path, state: str, complete: bool
) -> None:
    """Catches a partial probe being published as complete or a pass hiding skipped work."""
    path = tmp_path / "result.jsonl"
    _write(
        path,
        _record(
            "terminal",
            state=state,
            phase="finished-chunk",
            completeness={
                "inspected": 1,
                "skipped": 1,
                "complete": complete,
                "reason": "controlled-partial-result",
            },
        ),
    )

    with pytest.raises(InvestigationError, match="conflicts with complete"):
        read_probe_transcript(path, _request())
