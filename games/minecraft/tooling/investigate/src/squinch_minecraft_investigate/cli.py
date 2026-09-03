from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .artifact_inspection import inspect_artifact
from .catalog import resolve_artifacts
from .cell_scan import run_cell_scan
from .client import run_client
from .preset_fixture import run_preset_fixture
from .comparison import run_exact_comparison, structured_diff
from .errors import InvestigationError
from .generation import generate_regions, tile_chunks
from .output import emit, envelope, timestamp
from .paths import ACTIVE_ROOT, LOCKS_ROOT, RUNS_ROOT, lock_path, resolve_project, validate_loader
from .probe_requests import submit_probe
from .scenario import load_scenario, run_scenario
from .server import (
    OWNERSHIP,
    load_active,
    recover,
    run_commands,
    start_server,
    status,
    stop_server,
)
from .state import project_lock, read_json

RETENTIONS = ("discard", "keep-on-failure", "keep")


def _common(
    parser: argparse.ArgumentParser,
    *,
    project: bool = True,
    loaders: tuple[str, ...] = ("fabric", "forge", "neoforge", "quilt"),
) -> None:
    if project:
        parser.add_argument("--project", required=True, help="Exact mod project/worktree path")
        parser.add_argument("--loader", required=True, choices=loaders)
    parser.add_argument("--json", action="store_true", help="Emit the versioned JSON envelope")


def _server_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed")
    parser.add_argument("--datapack", action="append", default=[], type=Path)
    parser.add_argument("--probe-pack", action="append", default=[], type=Path)
    parser.add_argument("--server-property", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--server-port", type=int)
    parser.add_argument("--rcon-port", type=int)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retention", choices=RETENTIONS, default="discard")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="squinch mc-investigate")
    subparsers = root.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start and authenticate a development server")
    _common(start)
    _server_inputs(start)

    stop = subparsers.add_parser("stop", help="Stop a tracked server and verify cleanup")
    _common(stop)
    stop.add_argument("--timeout", type=float, default=60.0)
    stop.add_argument(
        "--failed", action="store_true", help="Record the stopped investigation as failed"
    )

    stat = subparsers.add_parser("status", help="Inspect tracked process and socket state")
    _common(stat)

    doctor = subparsers.add_parser("doctor", help="Diagnose or recover active state")
    _common(doctor)
    doctor.add_argument("--recover", action="store_true")
    doctor.add_argument("--timeout", type=float, default=30.0)

    command = subparsers.add_parser("command", help="Run RCON commands on the active server")
    _common(command)
    command.add_argument("--timeout", type=float, default=60.0)
    command.add_argument("rcon_command", nargs="+")

    run = subparsers.add_parser("run", help="Start, execute commands, and always stop")
    _common(run)
    _server_inputs(run)
    run.add_argument("--command", action="append", default=[], dest="commands", required=True)

    client = subparsers.add_parser(
        "client", help="Run an isolated, instrumented world-creation client lifecycle"
    )
    _common(client, loaders=("fabric", "neoforge"))
    client.add_argument(
        "--probe-pack", action="append", required=True, type=Path,
        help="Probe-pack root to compile as a standalone development mod",
    )
    client.add_argument(
        "--artifact", action="append", default=[], dest="artifacts",
        help="Exact catalog artifact ID to remap and load at runtime",
    )
    client.add_argument(
        "--compile-artifact",
        action="append",
        default=[],
        metavar="ID:LOADER:MAPPING",
        help="Exact catalog artifact imported by probe source; MAPPING is named or loader",
    )
    client.add_argument(
        "--probe-env", action="append", default=[], metavar="NAME=VALUE",
        help="SQUINCH_* probe control environment value",
    )
    client.add_argument(
        "--result-env", action="append", required=True, metavar="NAME=FILENAME",
        help="SQUINCH_* result path environment and retained JSON basename",
    )
    client.add_argument("--timeout", type=float, default=300.0)

    scenario = subparsers.add_parser(
        "scenario", help="Run one versioned TOML investigation scenario"
    )
    _common(scenario, project=False)
    scenario.add_argument("scenario_file", type=Path, help="Canonical or one-off TOML file")

    generate = subparsers.add_parser("generate", help="Tile and force-generate a bounded region")
    _common(generate)
    generate.add_argument("--unit", choices=("block", "chunk"), required=True)
    generate.add_argument("--bounds", nargs=4, type=int, required=True, metavar=("MIN_X", "MIN_Z", "MAX_X", "MAX_Z"))
    generate.add_argument("--timeout", type=float, default=600.0)

    probe = subparsers.add_parser("probe", help="Submit one atomic probe request")
    _common(probe)
    probe.add_argument("--probe-id", required=True)
    probe.add_argument("--probe-version", required=True)
    probe.add_argument("--config", type=Path)
    probe.add_argument("--timeout", type=float, default=300.0)

    compare = subparsers.add_parser(
        "compare", help="Compare result files or run one scenario at two exact commits"
    )
    _common(compare, project=False)
    compare.add_argument("--left", type=Path, help="Existing structured result file")
    compare.add_argument("--right", type=Path, help="Existing structured result file")
    compare.add_argument("--project", help="Source Git worktree for exact-commit comparison")
    compare.add_argument("--before", help="Full 40-character before commit SHA")
    compare.add_argument("--after", help="Full 40-character after commit SHA")
    compare.add_argument("--scenario", type=Path, help="Scenario to run against both commits")
    compare.add_argument(
        "--expect", choices=("any", "equal", "different"), default="any"
    )

    inspect = subparsers.add_parser(
        "inspect-artifact", help="Reject development-probe contamination in production JARs"
    )
    _common(inspect, project=False)
    inspect.add_argument("artifact", nargs="+", type=Path, help="Exact production JAR path")

    cell_scan = subparsers.add_parser(
        "cell-scan", help="Run the standalone RTF preview/tile model without a game process"
    )
    cell_scan.add_argument("--project", required=True, help="Exact RTF project/worktree path")
    cell_scan.add_argument("--preset", required=True, type=Path, help="fixture.toml or resolved preset JSON")
    cell_scan.add_argument("--seed", required=True)
    cell_scan.add_argument("--mode", choices=("preview", "tile", "adaptive"), default="preview")
    cell_scan.add_argument("--bounds", nargs=4, type=float, metavar=("MIN_X", "MIN_Z", "MAX_X", "MAX_Z"))
    cell_scan.add_argument("--center", nargs=2, type=float, default=(0.0, 0.0), metavar=("X", "Z"))
    cell_scan.add_argument("--zoom", type=float, default=4.0)
    cell_scan.add_argument("--tile-size", type=int, default=4, help="RTF tile factor; preview parity is 4, runtime parity is 3")
    cell_scan.add_argument("--batch-count", type=int, default=6)
    cell_scan.add_argument("--sample-step", type=int, default=1)
    cell_scan.add_argument("--field", action="append", default=[])
    cell_scan.add_argument("--predicate", action="append", default=[], metavar="FIELD:OP:VALUE")
    cell_scan.add_argument("--rank-field", default="height")
    cell_scan.add_argument("--ascending", action="store_true")
    cell_scan.add_argument("--top-k", type=int, default=20)
    cell_scan.add_argument("--example-limit", type=int, default=20)
    cell_scan.add_argument("--refine-count", type=int, default=4)
    cell_scan.add_argument("--refine-zoom", type=float)
    cell_scan.add_argument("--refine-step", type=int, default=2)
    cell_scan.add_argument("--exact-tile", action="store_true")
    cell_scan.add_argument("--grid-json", action="store_true")
    cell_scan.add_argument("--grid-csv", action="store_true")
    cell_scan.add_argument("--heatmap", metavar="NUMERIC_FIELD")
    cell_scan.add_argument("--timeout", type=float, default=300.0)
    cell_scan.add_argument("--json", action="store_true", help="Emit the versioned JSON envelope")

    preset_fixture = subparsers.add_parser(
        "preset-fixture", help="Generate a complete RTF datapack from one resolved preset"
    )
    preset_fixture.add_argument("--project", required=True, help="Exact FTF project/worktree path")
    preset_fixture.add_argument(
        "--preset", required=True, type=Path, help="Base fixture.toml or resolved preset JSON"
    )
    preset_fixture.add_argument("--timeout", type=float, default=300.0)
    preset_fixture.add_argument(
        "--json", action="store_true", help="Emit the versioned JSON envelope"
    )

    clean = subparsers.add_parser("clean", help="Enumerate and remove exact owned run artifacts")
    _common(clean, project=False)
    selection = clean.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run", action="append", dest="runs")
    selection.add_argument("--older-than-days", type=float)
    clean.add_argument("--apply", action="store_true", help="Delete; without this flag, dry-run")

    return root


def _properties(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise InvestigationError(
                "invalid_property", f"server property must be KEY=VALUE: {value}"
            )
        result[key] = item
    return result


def _resolve(args: argparse.Namespace) -> tuple[Path, str]:
    project = resolve_project(args.project)
    validate_loader(project, args.loader)
    return project, args.loader


def _artifacts(state: dict) -> list[str]:
    return [state["artifact_dir"], state["log_path"]]


def _public_state(state: dict) -> dict:
    value = {
        "operation": state["operation"],
        "project": state["project"],
        "loader": state["loader"],
        "lifecycle": state["lifecycle"],
        "process": state["process"],
        "cleanup": state.get("cleanup"),
    }
    if state["operation"] == "server":
        value.update({
            "level_name": state["level_name"],
            "ports": state["ports"],
            "world_dir": state["world_dir"],
        })
    elif state["operation"] == "client":
        value.update({
            "run_dir": state["run_dir"],
            "display": state["display"],
            "results": state.get("results", []),
        })
    else:
        value["run_dir"] = state["run_dir"]
    return value


def _start(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    state = start_server(
        project,
        loader,
        seed=args.seed,
        datapacks=args.datapack,
        properties=_properties(args.server_property),
        timeout=args.timeout,
        retention=args.retention,
        probe_packs=tuple(args.probe_pack),
        server_port=args.server_port,
        rcon_port=args.rcon_port,
    )
    value = envelope(
        "start",
        "ready",
        run_id=state["run_id"],
        started_at=state["started_at"],
        artifact_paths=_artifacts(state),
        data=_public_state(state),
    )
    return value, f"ready {project}/{loader} (run {state['run_id']}, pid {state['process']['pid']})"


def _stop(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    state = stop_server(project, loader, successful=not args.failed, timeout=args.timeout)
    result_state = "failed" if args.failed else "succeeded"
    value = envelope(
        "stop",
        result_state,
        run_id=state["run_id"],
        started_at=state["started_at"],
        finished_at=state["finished_at"],
        artifact_paths=_artifacts(state),
        data=_public_state(state),
    )
    return value, f"stopped {project}/{loader}; cleanup verified"


def _status(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    state = status(project, loader)
    if state is None:
        return envelope("status", "inactive", data={"project": str(project), "loader": loader}), f"inactive {project}/{loader}"
    healthy = (
        state["lifecycle"] == "ready" and bool(state["bound_ports"])
        if state["operation"] == "server"
        else state["lifecycle"] == "running" and bool(state["owned_pids"])
    )
    machine_state = "ready" if healthy else "degraded"
    value = envelope(
        "status",
        machine_state,
        run_id=state["run_id"],
        started_at=state["started_at"],
        artifact_paths=_artifacts(state),
        data={**_public_state(state), "leader_identity_valid": state["leader_identity_valid"], "owned_pids": state["owned_pids"], "bound_ports": state["bound_ports"]},
    )
    return value, f"{machine_state} {project}/{loader} (run {state['run_id']})"


def _doctor(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    current = status(project, loader)
    if current is None:
        return envelope("doctor", "inactive", data={"project": str(project), "loader": loader, "action": "none"}), "no active investigation state"
    if not args.recover:
        issues = []
        if not current["leader_identity_valid"] and not current["owned_pids"]:
            issues.append("tracked process boundary is no longer alive")
        expected_lifecycle = "ready" if current["operation"] == "server" else "running"
        if current["lifecycle"] != expected_lifecycle:
            issues.append(f"lifecycle is {current['lifecycle']}")
        state_name = "degraded" if issues else "ready"
        return envelope("doctor", state_name, run_id=current["run_id"], started_at=current["started_at"], artifact_paths=_artifacts(current), data={"issues": issues, **_public_state(current)}), ("; ".join(issues) if issues else "active state is healthy")
    recovered = recover(project, loader, args.timeout)
    return envelope("doctor", "failed", run_id=recovered["run_id"], started_at=recovered["started_at"], finished_at=recovered["finished_at"], artifact_paths=_artifacts(recovered), data={"action": "recovered", **_public_state(recovered)}), f"recovered and finalized failed run {recovered['run_id']}"


def _command(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    with project_lock(lock_path(project, loader)):
        state = load_active(project, loader)
        if state["lifecycle"] != "ready":
            raise InvestigationError("server_not_ready", f"active lifecycle is {state['lifecycle']}")
        values = run_commands(state, args.rcon_command, args.timeout)
    return envelope("command", "succeeded", run_id=state["run_id"], started_at=state["started_at"], finished_at=timestamp(), artifact_paths=_artifacts(state), data={"responses": values}), "\n".join(f"> {item['command']}\n{item['response']}" for item in values)


def _run(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    state: dict | None = None
    responses: list[dict] = []
    succeeded = False
    interrupted = False
    try:
        state = start_server(project, loader, seed=args.seed, datapacks=args.datapack, properties=_properties(args.server_property), timeout=args.timeout, retention=args.retention, probe_packs=tuple(args.probe_pack), server_port=args.server_port, rcon_port=args.rcon_port)
        responses = run_commands(state, args.commands, args.timeout)
        succeeded = True
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if state is not None:
            state = stop_server(project, loader, successful=succeeded, timeout=min(args.timeout, 60.0))
    assert state is not None
    if interrupted:
        raise InvestigationError(
            "interrupted",
            "server run interrupted by signal",
            details={
                "run_id": state["run_id"],
                "artifact_dir": state["artifact_dir"],
                "log_path": state["log_path"],
                "cleanup_complete": True,
            },
        )
    return envelope("run", "succeeded", run_id=state["run_id"], started_at=state["started_at"], finished_at=state["finished_at"], artifact_paths=_artifacts(state), data={"responses": responses, **_public_state(state)}), f"run {state['run_id']} succeeded; cleanup verified"


def _named_values(values: list[str], *, kind: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, item = value.partition("=")
        if (
            not separator
            or re.fullmatch(r"SQUINCH_[A-Z0-9_]+", name) is None
            or name in result
            or any(character in item for character in "\0\r\n")
        ):
            raise InvestigationError(
                "client_arguments_invalid", f"{kind} must be a unique SQUINCH_NAME=VALUE: {value}"
            )
        result[name] = item
    return result


def _client(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    runtime_artifacts = resolve_artifacts(tuple(args.artifacts), expected_loader=loader)
    compile_artifacts = []
    for value in args.compile_artifact:
        parts = value.split(":")
        if len(parts) != 3 or parts[1] not in {"fabric", "neoforge"} or parts[2] not in {"named", "loader"}:
            raise InvestigationError(
                "client_arguments_invalid",
                f"compile artifact must be ID:LOADER:named|loader: {value}",
            )
        artifact = resolve_artifacts((parts[0],), expected_loader=parts[1])[0]
        compile_artifacts.append((artifact, parts[2]))
    probe_environment = _named_values(args.probe_env, kind="probe environment")
    result_files = _named_values(args.result_env, kind="result environment")
    overlap = set(probe_environment) & set(result_files)
    if overlap:
        raise InvestigationError(
            "client_arguments_invalid",
            f"result environments cannot also be probe environments: {sorted(overlap)}",
        )
    for variable, filename in result_files.items():
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise InvestigationError(
                "client_arguments_invalid",
                f"result filename must be a basename ending in .json: {variable}={filename}",
            )
    state = run_client(
        project,
        loader,
        probe_packs=tuple(args.probe_pack),
        runtime_artifacts=runtime_artifacts,
        compile_artifacts=tuple(compile_artifacts),
        probe_environment=probe_environment,
        result_files=result_files,
        timeout=args.timeout,
    )
    artifact_paths = [
        state["artifact_dir"],
        state["log_path"],
        str(Path(state["artifact_dir"]) / "manifest.json"),
        str(Path(state["artifact_dir"]) / "summary.json"),
        *(item["path"] for item in state["results"]),
    ]
    return (
        envelope(
            "client",
            "succeeded",
            run_id=state["run_id"],
            started_at=state["started_at"],
            finished_at=state["finished_at"],
            artifact_paths=artifact_paths,
            data=_public_state(state),
        ),
        f"client lifecycle {state['run_id']} succeeded; cleanup verified",
    )


def _scenario(args: argparse.Namespace) -> tuple[dict, str]:
    definition = load_scenario(args.scenario_file)
    result = run_scenario(definition)
    state = result["state"]
    artifact_paths = [
        *_artifacts(state),
        result["scenario_summary"],
        result["scenario_progress"],
        str(Path(state["artifact_dir"]) / "provenance.json"),
        str(Path(state["artifact_dir"]) / "scenario.toml"),
    ]
    materialized = result["rtf_fixture"]
    if materialized is not None:
        artifact_paths.append(materialized["archive_artifact"])
    value = envelope(
        "scenario",
        "succeeded",
        run_id=state["run_id"],
        started_at=state["started_at"],
        finished_at=state["finished_at"],
        artifact_paths=artifact_paths,
        data={
            **_public_state(state),
            "scenario": result["scenario"],
            "steps": result["steps"],
            "provenance": result["provenance"],
            "world_identity": result["world_identity"],
            "rtf_fixture": result["rtf_fixture"],
        },
    )
    return (
        value,
        f"scenario {definition.name!r} succeeded (run {state['run_id']}); cleanup verified",
    )


def _generate(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    with project_lock(lock_path(project, loader)):
        state = load_active(project, loader)
        if state["lifecycle"] != "ready":
            raise InvestigationError("server_not_ready", f"active lifecycle is {state['lifecycle']}")
        results = generate_regions(state, tuple(args.bounds), args.unit, args.timeout)
    return envelope("generate", "succeeded", run_id=state["run_id"], started_at=state["started_at"], finished_at=timestamp(), artifact_paths=_artifacts(state), data={"unit": args.unit, "input_bounds": args.bounds, "regions": results}), f"generated {len(results)} region tile(s)"


def _probe(args: argparse.Namespace) -> tuple[dict, str]:
    project, loader = _resolve(args)
    config = {}
    if args.config:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise InvestigationError("invalid_probe_config", "probe config must be a JSON object")
    request, result, state = submit_probe(
        project,
        loader,
        probe_id=args.probe_id,
        probe_version=args.probe_version,
        config=config,
        timeout=args.timeout,
    )
    request_path = Path(state["run_dir"]) / ".squinch-investigate" / "requests" / f"{request['request_id']}.json"
    result_path = Path(state["run_dir"]) / ".squinch-investigate" / "results" / f"{request['request_id']}.jsonl"
    terminal = result["state"]
    envelope_state = {"pass": "succeeded", "fail": "failed", "inconclusive": "inconclusive", "error": "error"}[terminal]
    return envelope("probe", envelope_state, run_id=state["run_id"], started_at=request["submitted_at"], finished_at=timestamp(), artifact_paths=[*_artifacts(state), str(request_path), str(result_path)], data={"request": request, "result": result}), f"probe {args.probe_id} terminal state: {terminal}"


def _compare(args: argparse.Namespace) -> tuple[dict, str]:
    file_mode = args.left is not None or args.right is not None
    exact_mode = any(
        value is not None for value in (args.project, args.before, args.after, args.scenario)
    )
    if file_mode and exact_mode:
        raise InvestigationError(
            "comparison_arguments_invalid",
            "use either --left/--right or --project/--before/--after/--scenario",
        )
    if file_mode:
        if args.left is None or args.right is None:
            raise InvestigationError(
                "comparison_arguments_invalid", "file comparison requires --left and --right"
            )
        left_path, right_path = args.left.resolve(), args.right.resolve()
        left, right = read_json(left_path), read_json(right_path)
        differences = structured_diff(left, right)
        data = {
            "equal": not differences,
            "difference_count": len(differences),
            "differences": differences,
            "left": left,
            "right": right,
        }
        artifact_paths = [str(left_path), str(right_path)]
        run_id = None
    else:
        if any(value is None for value in (args.project, args.before, args.after, args.scenario)):
            raise InvestigationError(
                "comparison_arguments_invalid",
                "exact comparison requires --project, --before, --after, and --scenario",
            )
        project = resolve_project(args.project)
        scenario = load_scenario(args.scenario)
        with project_lock(LOCKS_ROOT / "exact-comparison.lock"):
            result = run_exact_comparison(project, args.before, args.after, scenario)
        data = {
            key: result[key]
            for key in (
                "comparison_id",
                "equal",
                "difference_count",
                "differences",
                "normalization",
                "equivalence",
                "preserved_worktrees",
                "left",
                "right",
            )
        }
        artifact_paths = [
            result["artifact_dir"],
            result["summary_path"],
            result["left"]["artifact_dir"],
            result["right"]["artifact_dir"],
        ]
        run_id = result["comparison_id"]
    equal = data["equal"]
    expectation_met = (
        args.expect == "any"
        or (args.expect == "equal" and equal)
        or (args.expect == "different" and not equal)
    )
    state = "succeeded" if expectation_met else "failed"
    human = "results are identical" if equal else f"results differ ({data['difference_count']} fields)"
    if not expectation_met:
        human = f"comparison expectation {args.expect!r} was not met: {human}"
    return (
        envelope(
            "compare",
            state,
            run_id=run_id,
            finished_at=timestamp(),
            artifact_paths=artifact_paths,
            data=data,
        ),
        human,
    )


def _inspect_artifact(args: argparse.Namespace) -> tuple[dict, str]:
    inspections_by_path = {
        item["path"]: item for item in (inspect_artifact(path) for path in args.artifact)
    }
    inspections = list(inspections_by_path.values())
    clean = all(item["clean"] for item in inspections)
    paths = [item["path"] for item in inspections]
    value = envelope(
        "inspect-artifact",
        "succeeded" if clean else "failed",
        finished_at=timestamp(),
        artifact_paths=paths,
        data={"clean": clean, "inspections": inspections},
    )
    if clean:
        human = f"clean: {len(inspections)} production artifact(s)"
    else:
        finding_count = sum(len(item["findings"]) for item in inspections)
        human = f"rejected: {finding_count} development-probe finding(s)"
    return value, human


def _cell_scan(args: argparse.Namespace) -> tuple[dict, str]:
    scan = run_cell_scan(args)
    result = scan["result"]
    artifact_paths = [
        scan["artifact_dir"], scan["manifest_path"], scan["request_path"],
        scan["result_path"], scan["log_path"], *result.get("artifacts", []),
    ]
    value = envelope(
        "cell-scan", "succeeded", run_id=scan["run_id"], finished_at=timestamp(),
        artifact_paths=list(dict.fromkeys(artifact_paths)),
        data={
            "authority": result["authority"],
            "mode": result["mode"],
            "manifest": scan["manifest"],
            "result": result,
        },
    )
    return value, (
        f"{result['mode']} cell scan {scan['run_id']} inspected "
        f"{result['scan']['inspected']} RTF cells ({result['authority']})"
    )


def _preset_fixture(args: argparse.Namespace) -> tuple[dict, str]:
    generated = run_preset_fixture(args)
    value = envelope(
        "preset-fixture",
        "succeeded",
        run_id=generated["run_id"],
        finished_at=timestamp(),
        artifact_paths=[
            generated["artifact_dir"],
            generated["manifest_path"],
            generated["preset_path"],
            generated["canonical_preset_path"],
            generated["output_path"],
            generated["log_path"],
        ],
        data={"manifest": generated["manifest"]},
    )
    return value, (
        f"preset fixture {generated['run_id']} generated "
        f"{generated['manifest']['generated']['file_count']} files"
    )


def _active_run_ids() -> set[str]:
    values: set[str] = set()
    if not ACTIVE_ROOT.exists():
        return values
    for path in ACTIVE_ROOT.glob("*.json"):
        with contextlib.suppress(InvestigationError):
            values.add(str(read_json(path).get("run_id")))
    return values


def _clean(args: argparse.Namespace) -> tuple[dict, str]:
    candidates: list[Path] = []
    if args.runs:
        for run_id in args.runs:
            if not run_id or Path(run_id).name != run_id:
                raise InvestigationError("invalid_run_id", f"invalid exact run ID: {run_id!r}")
            candidates.append(RUNS_ROOT / run_id)
    else:
        if args.older_than_days < 0:
            raise InvestigationError("invalid_age", "age must be nonnegative")
        cutoff = datetime.now(UTC) - timedelta(days=args.older_than_days)
        for path in RUNS_ROOT.iterdir() if RUNS_ROOT.exists() else []:
            if path.is_dir() and datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
                candidates.append(path)
    active = _active_run_ids()
    inspected = []
    for path in sorted(set(candidates)):
        resolved = path.resolve()
        if resolved.parent != RUNS_ROOT.resolve() or path.is_symlink():
            raise InvestigationError("unsafe_clean_target", f"run target escaped ownership root: {path}")
        manifest_path = path / "manifest.json"
        manifest = read_json(manifest_path)
        run_id = manifest.get("run_id")
        if manifest.get("ownership") != OWNERSHIP or run_id != path.name:
            raise InvestigationError("unsafe_clean_target", f"run ownership validation failed: {path}")
        if run_id in active:
            raise InvestigationError("run_active", f"refusing to clean active run: {run_id}")
        retained_world = manifest.get("retained_world")
        if retained_world:
            expected_world = Path(manifest.get("run_dir", "")) / str(
                manifest.get("level_name", "")
            )
            if (
                Path(retained_world) != expected_world
                or expected_world.name != f"squinch-{run_id.lower()}"
            ):
                raise InvestigationError(
                    "unsafe_clean_target", f"retained world ownership failed: {retained_world}"
                )
        inspected.append({"run_id": run_id, "artifact_dir": str(path), "retained_world": retained_world})
    if args.apply:
        for item in inspected:
            world_value = item["retained_world"]
            if world_value:
                world = Path(world_value)
                if world.exists():
                    if world.is_symlink() or not world.is_dir() or world.name != f"squinch-{item['run_id'].lower()}":
                        raise InvestigationError("unsafe_clean_target", f"retained world validation failed: {world}")
                    shutil.rmtree(world)
            shutil.rmtree(Path(item["artifact_dir"]))
    action = "deleted" if args.apply else "dry-run"
    return envelope("clean", "succeeded", finished_at=timestamp(), artifact_paths=[item["artifact_dir"] for item in inspected], data={"action": action, "targets": inspected}), f"{action}: {len(inspected)} owned run(s)"


HANDLERS = {
    "start": _start,
    "stop": _stop,
    "status": _status,
    "doctor": _doctor,
    "command": _command,
    "run": _run,
    "client": _client,
    "scenario": _scenario,
    "generate": _generate,
    "probe": _probe,
    "compare": _compare,
    "inspect-artifact": _inspect_artifact,
    "cell-scan": _cell_scan,
    "preset-fixture": _preset_fixture,
    "clean": _clean,
}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    def interrupted(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous_handlers = {
        signum: signal.signal(signum, interrupted)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    try:
        value, human = HANDLERS[args.command](args)
        emit(value, json_mode=args.json, human=human)
        return 0 if value["state"] not in {"failed", "inconclusive", "error", "degraded", "unknown"} else 1
    except KeyboardInterrupt:
        error = InvestigationError("interrupted", "command interrupted by signal")
    except InvestigationError as caught:
        error = caught
    except (OSError, ValueError, json.JSONDecodeError) as caught:
        error = InvestigationError("unexpected_error", str(caught))
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    artifact_paths = [
        path
        for path in (
            error.details.get("artifact_dir"),
            error.details.get("log_path"),
        )
        if isinstance(path, str)
    ]
    artifact_dir = error.details.get("artifact_dir")
    if isinstance(artifact_dir, str):
        for name in ("manifest.json", "summary.json"):
            path = Path(artifact_dir) / name
            if path.is_file():
                artifact_paths.append(str(path))
    value = envelope(
        args.command,
        "error",
        run_id=error.details.get("run_id"),
        finished_at=timestamp(),
        artifact_paths=list(dict.fromkeys(artifact_paths)),
        error={"code": error.code, "message": error.message, "details": error.details},
    )
    emit(value, json_mode=args.json, human=f"error [{error.code}]: {error.message}")
    return 1
