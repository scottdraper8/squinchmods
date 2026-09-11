from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from squinch_minecraft_investigate import cli
from squinch_minecraft_investigate.output import envelope

ACTIVE_DATA = {
    "project": "/tmp/project",
    "loader": "fabric",
    "lifecycle": "ready",
    "level_name": "run-20260801-abc123",
    "ports": {"server": 25565, "rcon": 25575},
    "process": {"pid": 1234, "pgrp": 1234, "session": 1234, "start_ticks": 987654},
    "world_dir": "/tmp/project/run-20260801-abc123",
    "cleanup": {},
}


def test_start_stop_envelope_matches_active_data_shape() -> None:
    """Catches a start/stop payload that drops a field an agent's cleanup logic depends on
    (e.g. process identity or world_dir), which the schema's activeData branch requires."""
    value = envelope("start", "ready", run_id="run-1", data=dict(ACTIVE_DATA))
    assert value["data"]["process"]["pid"] == 1234
    envelope("stop", "succeeded", run_id="run-1", data=dict(ACTIVE_DATA))


def test_start_envelope_rejects_missing_process_identity() -> None:
    """Negative control: proves the schema actually enforces activeData rather than passing any
    object. A refactor that stops recording process identity on start would break this."""
    broken = {key: value for key, value in ACTIVE_DATA.items() if key != "process"}

    with pytest.raises(jsonschema.ValidationError):
        envelope("start", "ready", run_id="run-1", data=broken)


def test_run_envelope_requires_responses_alongside_active_data() -> None:
    """Catches a run-command refactor that returns process/world state but silently drops the
    per-command RCON responses agents parse to confirm what actually executed."""
    data = dict(ACTIVE_DATA)
    data["responses"] = [{"command": "seed", "response": "Seed: [123]"}]
    envelope("run", "succeeded", run_id="run-1", data=data)


def test_scenario_envelope_requires_identity_steps_and_provenance() -> None:
    """Catches a scenario response that reports success without repeatable inputs or observations."""
    data = dict(ACTIVE_DATA)
    data.update(
        {
            "scenario": {"name": "smoke", "path": "/tmp/smoke.toml", "sha256": "abc"},
            "steps": [],
            "provenance": {"code": {"head": "deadbeef"}},
            "world_identity": {"actual_seed": 123},
        }
    )
    envelope("scenario", "succeeded", run_id="run-1", data=data)

    del data["provenance"]
    with pytest.raises(jsonschema.ValidationError):
        envelope("scenario", "succeeded", run_id="run-1", data=data)


def test_scenario_envelope_cleanup_failed_preserves_step_data_with_error() -> None:
    """Steps succeeded but cleanup failed. The envelope must reject the run while retaining data."""
    data = dict(ACTIVE_DATA)
    data.update(
        {
            "scenario": {"name": "smoke", "path": "/tmp/smoke.toml", "sha256": "abc"},
            "steps": [{"id": "s1", "type": "command", "state": "succeeded"}],
            "provenance": {"code": {"head": "deadbeef"}},
            "world_identity": {"actual_seed": 123},
        }
    )
    value = envelope(
        "scenario",
        "error",
        run_id="run-1",
        data=data,
        error={"code": "cleanup_failed", "message": "save timed out", "details": {}},
    )
    assert value["state"] == "error"
    assert value["error"]["code"] == "cleanup_failed"
    assert value["data"]["steps"][0]["state"] == "succeeded"


def test_scenario_handler_rejects_cleanup_failure_and_main_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        **ACTIVE_DATA,
        "operation": "server",
        "run_id": "run-1",
        "started_at": "2026-08-01T00:00:00Z",
        "finished_at": "2026-08-01T00:01:00Z",
        "artifact_dir": "/tmp/run-1",
        "log_path": "/tmp/run-1/server.log",
    }
    result = {
        "state": state,
        "scenario": {"name": "smoke", "path": "/tmp/smoke.toml", "sha256": "abc"},
        "steps": [{"id": "s1", "type": "command", "state": "succeeded"}],
        "provenance": {"code": {"head": "deadbeef"}},
        "world_identity": {"actual_seed": 123},
        "rtf_fixture": None,
        "scenario_summary": "/tmp/run-1/scenario-summary.json",
        "scenario_progress": "/tmp/run-1/scenario-progress.jsonl",
        "cleanup_failed": {
            "code": "cleanup_failed",
            "message": "save timed out",
            "details": {},
        },
    }
    monkeypatch.setattr(cli, "load_scenario", lambda _path: SimpleNamespace(name="smoke"))
    monkeypatch.setattr(cli, "run_scenario", lambda _definition: result)

    value, _message = cli._scenario(argparse.Namespace(scenario_file=Path("smoke.toml")))

    assert value["state"] == "error"
    assert value["data"]["steps"] == result["steps"]
    monkeypatch.setitem(cli.HANDLERS, "scenario", lambda _args: (value, "rejected"))
    monkeypatch.setattr(cli, "emit", lambda *_args, **_kwargs: None)
    assert cli.main(["scenario", "smoke.toml", "--json"]) == 1


def test_command_envelope_requires_responses() -> None:
    """Catches a command-subcommand refactor that drops the responses array agents rely on to
    tell which RCON command produced which output."""
    envelope(
        "command",
        "succeeded",
        run_id="run-1",
        data={"responses": [{"command": "list", "response": "There are 0 players"}]},
    )


def test_command_envelope_rejects_response_missing_text() -> None:
    """Negative control: a response entry without its own response text is indistinguishable
    from a command that produced no output, which is the false-success failure mode this schema
    branch exists to prevent."""
    with pytest.raises(jsonschema.ValidationError):
        envelope(
            "command",
            "succeeded",
            run_id="run-1",
            data={"responses": [{"command": "list"}]},
        )


def test_generate_envelope_requires_unit_bounds_and_regions() -> None:
    """Catches a generate refactor that reports success without the tiled region list an agent
    needs to know exactly what was force-generated."""
    envelope(
        "generate",
        "succeeded",
        run_id="run-1",
        data={
            "unit": "chunk",
            "input_bounds": [0, 0, 31, 31],
            "regions": [{"chunk_min_x": 0, "chunk_min_z": 0, "chunk_max_x": 15, "chunk_max_z": 15}],
        },
    )


def test_generate_envelope_rejects_unknown_unit() -> None:
    """Negative control: 'unit' is meant to be exactly block or chunk; silently accepting
    anything else would let ambiguous coordinate units reach an agent unflagged."""
    with pytest.raises(jsonschema.ValidationError):
        envelope(
            "generate",
            "succeeded",
            run_id="run-1",
            data={"unit": "block-ish", "input_bounds": [0, 0, 1, 1], "regions": []},
        )


def test_probe_envelope_requires_request_and_result() -> None:
    """Catches a probe refactor that reports a terminal state without the request/result pair an
    agent needs to distinguish pass/fail/inconclusive/error and its provenance."""
    request = {
        "protocol_version": "1",
        "run_id": "run-1",
        "request_id": "request-1",
        "probe_id": "cave-density",
        "probe_version": "1",
        "submitted_at": "2026-08-01T00:00:00Z",
        "config": {},
    }
    result = {
        "protocol_version": "1",
        "run_id": "run-1",
        "request_id": "request-1",
        "probe_id": "cave-density",
        "probe_version": "1",
        "type": "terminal",
        "timestamp": "2026-08-01T00:00:01Z",
        "state": "pass",
        "phase": "finished-chunk",
        "completeness": {"inspected": 1, "skipped": 0, "complete": True},
    }
    envelope(
        "probe",
        "succeeded",
        run_id="run-1",
        data={"request": request, "result": result},
    )

    del result["completeness"]["skipped"]
    with pytest.raises(jsonschema.ValidationError):
        envelope(
            "probe",
            "succeeded",
            run_id="run-1",
            data={"request": request, "result": result},
        )


def test_compare_envelope_requires_equal_left_right() -> None:
    """Catches a compare refactor that reports a result without both normalized sides, which
    would make a before/after difference unverifiable from the JSON alone."""
    envelope(
        "compare",
        "succeeded",
        run_id=None,
        data={"equal": False, "left": {"outcome": "pass"}, "right": {"outcome": "fail"}},
    )


def test_inspect_artifact_envelope_requires_inspection_identity() -> None:
    """Catches artifact output omitting the hash or entry evidence behind a clean claim."""
    envelope(
        "inspect-artifact",
        "succeeded",
        data={
            "clean": True,
            "inspections": [
                {
                    "path": "/tmp/production.jar",
                    "sha256": "a" * 64,
                    "size_bytes": 100,
                    "entry_count": 1,
                    "clean": True,
                    "findings": [],
                }
            ],
        },
    )

    with pytest.raises(jsonschema.ValidationError):
        envelope(
            "inspect-artifact",
            "succeeded",
            data={"clean": True, "inspections": [{"path": "/tmp/production.jar"}]},
        )


def test_cell_scan_envelope_requires_authority_manifest_and_result() -> None:
    """Catches a cell scan claiming success without its authority or inspected result evidence."""
    data = {
        "authority": "prediction",
        "mode": "preview",
        "manifest": {"head": "deadbeef"},
        "result": {
            "authority": "prediction",
            "mode": "preview",
            "timings": {"cold_scan_ms": 10, "warm_scan_ms": 5},
            "scan": {"inspected": 16},
            "deterministic_sha256": "a" * 64,
            "cold_warm_equal": True,
        },
    }
    envelope("cell-scan", "succeeded", run_id="run-1", data=data)

    del data["result"]["scan"]
    with pytest.raises(jsonschema.ValidationError):
        envelope("cell-scan", "succeeded", run_id="run-1", data=data)


def test_client_envelope_requires_verified_results_and_cleanup() -> None:
    data = {
        "operation": "client",
        "project": "/tmp/project",
        "loader": "fabric",
        "lifecycle": "succeeded",
        "process": ACTIVE_DATA["process"],
        "cleanup": {"complete": True, "failures": []},
        "run_dir": "/tmp/run/client-run",
        "display": {
            "backend": "headless",
            "runtime_dir": "/tmp/run/display-runtime",
            "wayland_display": "squinch-test",
        },
        "results": [{
            "environment": "SQUINCH_RESULT",
            "path": "/tmp/run/result.json",
            "sha256": "a" * 64,
            "result": {"status": "pass"},
        }],
    }
    envelope("client", "succeeded", run_id="run-1", data=data)

    data["cleanup"] = {"complete": False, "failures": ["leaked"]}
    with pytest.raises(jsonschema.ValidationError):
        envelope("client", "succeeded", run_id="run-1", data=data)


def test_preset_fixture_envelope_requires_complete_generated_evidence() -> None:
    manifest = {
        "kind": "rtf-preset-fixture",
        "run_id": "run-1",
        "project": "/tmp/project",
        "head": "deadbeef",
        "preset": {"resolved_preset_sha256": "b" * 64},
        "tracked_source_unchanged": True,
        "cleanup": {"complete": True, "failures": []},
        "generated": {
            "path": "/tmp/run/generated-fixture",
            "content_sha256": "a" * 64,
            "file_count": 5,
            "size": 100,
            "density_function_count": 1,
            "resolved_preset_sha256": "b" * 64,
            "required_paths": ["a", "b", "c", "d"],
            "files": ["pack.mcmeta"],
        },
    }
    envelope("preset-fixture", "succeeded", run_id="run-1", data={"manifest": manifest})

    del manifest["generated"]["density_function_count"]
    with pytest.raises(jsonschema.ValidationError):
        envelope("preset-fixture", "succeeded", run_id="run-1", data={"manifest": manifest})


def test_clean_envelope_requires_action_and_targets() -> None:
    """Catches a clean refactor that stops reporting whether it was a dry run, which is the one
    field that tells an agent whether anything was actually deleted."""
    envelope("clean", "succeeded", run_id=None, data={"action": "dry-run", "targets": []})


def test_clean_envelope_rejects_unknown_action() -> None:
    """Negative control: 'action' must be exactly dry-run or deleted; anything else defeats the
    whole point of distinguishing a dry run from a real deletion."""
    with pytest.raises(jsonschema.ValidationError):
        envelope("clean", "succeeded", run_id=None, data={"action": "removed", "targets": []})


def test_status_active_envelope_requires_identity_and_binding_fields() -> None:
    """Catches a status refactor that drops the leader-identity/bound-ports fields doctor and an
    agent's own safety checks depend on to avoid signaling a reused PID."""
    data = dict(ACTIVE_DATA)
    data.update({
        "operation": "server",
        "leader_identity_valid": True,
        "owned_pids": [1234],
        "bound_ports": [25565, 25575],
    })
    envelope("status", "ready", run_id="run-1", data=data)


def test_status_accepts_finite_operation_without_server_fields() -> None:
    data = {
        "operation": "preset-fixture",
        "project": "/tmp/project",
        "loader": "fabric",
        "lifecycle": "running",
        "process": ACTIVE_DATA["process"],
        "cleanup": {"complete": False, "failures": []},
        "run_dir": "/tmp/run",
        "leader_identity_valid": True,
        "owned_pids": [1234],
        "bound_ports": [],
    }
    envelope("status", "ready", run_id="run-1", data=data)

    del data["run_dir"]
    with pytest.raises(jsonschema.ValidationError):
        envelope("status", "ready", run_id="run-1", data=data)


def test_doctor_envelope_accepts_action_or_issues() -> None:
    """Catches a doctor refactor that reports neither a recovery action nor an issue list, which
    would make its output indistinguishable from 'nothing to check'."""
    envelope("doctor", "succeeded", run_id="run-1", data={"action": "finalized-failed-run"})
    envelope("doctor", "degraded", run_id="run-1", data={"issues": ["orphaned world directory"]})
