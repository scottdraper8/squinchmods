from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .errors import InvestigationError
from .executable import inspect_strings
from .game import game_identity, host_capabilities, host_health
from .hgpak import extract as extract_assets
from .hgpak import inventory as archive_inventory
from .mbin import inspect_mbin, roundtrip
from .mods import (
    analysis_summary,
    analyze_mod,
    conflict_report,
    inventory_mod,
    resolve_deployment_root,
    target_mbin,
    write_analysis_report,
)
from .output import emit, envelope, timestamp
from .paths import STAGES_ROOT, resolve_game_root
from .patterns import inspect_pattern_catalog
from .pe_functions import inspect_functions, parse_address
from .runs import create_run, resolve_run, write_json
from .scenario import run_scenario
from .search_probe import (
    build_native_search_probe,
    verify_probe_patch_compile,
)
from .source import snapshot_source
from .staging import collect_evidence, stage, stage_status, unstage
from .toolchain import (
    assert_supported_build,
    hgpak_identity,
    mbin_identity,
    sync_mbincompiler,
    target_identity,
    verify_mbincompiler,
)
from .toolchain import (
    config as toolchain_config,
)
from .xmlmodel import compare_xml, verify_export

DEFAULT_STRING_PATTERNS = [
    "PAGESELECTBAR",
    "FrontendPage",
    r"UI[/\\].*(?:Inventory|Journey|Discovery|Wiki|MissionLog|Options)",
]


def _common(parser: argparse.ArgumentParser, *, game: bool = False) -> None:
    if game:
        parser.add_argument("--game-root", type=Path, help="Exact No Man's Sky installation root")
    parser.add_argument(
        "--json", action="store_true", help="Emit the stable one-line JSON envelope"
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="squinch nms-investigate")
    sub = root.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Inspect game, host, and pinned toolchain health")
    _common(doctor, game=True)

    toolchain = sub.add_parser(
        "toolchain", help="Inspect or acquire the pinned investigation toolchain"
    )
    _common(toolchain)
    toolchain.add_argument("action", choices=("status", "sync"))

    inv = sub.add_parser("inventory", help="Retain a current HGPAK archive inventory")
    _common(inv, game=True)

    extract = sub.add_parser("extract", help="Extract exact logical paths with archive provenance")
    _common(extract, game=True)
    extract.add_argument("--path", action="append", required=True, dest="paths")

    rt = sub.add_parser(
        "roundtrip", help="Extract, decompile, compile, and semantically verify MBINs"
    )
    _common(rt, game=True)
    selection = rt.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--path", action="append", dest="paths", help="Logical path in current PAKs"
    )
    selection.add_argument(
        "--file", action="append", dest="files", type=Path, help="Local MBIN file"
    )

    analyze = sub.add_parser(
        "analyze-mod", help="Analyze a loose mod deployment tree against current assets"
    )
    _common(analyze, game=True)
    analyze.add_argument("--mod-root", required=True, type=Path)

    conflicts = sub.add_parser(
        "conflicts", help="Find full-file and property-path overlaps between mods"
    )
    _common(conflicts, game=True)
    conflicts.add_argument("--mod-root", action="append", required=True, type=Path)

    compare = sub.add_parser("compare", help="Semantically compare two MXML/EXML files")
    _common(compare)
    compare.add_argument("--left", required=True, type=Path)
    compare.add_argument("--right", required=True, type=Path)
    compare.add_argument("--expect", choices=("any", "equal", "different"), default="any")

    verify = sub.add_parser(
        "verify-export", help="Check that authored EXML leaves reached exported MXML"
    )
    _common(verify)
    verify.add_argument("--patch", required=True, type=Path)
    verify.add_argument("--exported", required=True, type=Path)
    verify.add_argument("--vanilla", type=Path)

    strings = sub.add_parser("exe-strings", help="Retain bounded NMS.exe static-string evidence")
    _common(strings, game=True)
    strings.add_argument("--pattern", action="append", default=[])
    strings.add_argument("--limit", type=int, default=500)
    strings.add_argument(
        "--allow-missing-patterns",
        action="store_true",
        help="Do not fail when one or more requested patterns have no match",
    )

    source = sub.add_parser(
        "source-snapshot",
        help="Retain selected files and symbol matches from a clean Git source tree",
    )
    _common(source)
    source.add_argument("--repository", required=True, type=Path)
    source.add_argument("--file", action="append", required=True, dest="files")
    source.add_argument("--pattern", action="append", default=[])
    source.add_argument("--limit", type=int, default=500)
    source.add_argument("--expect-revision")
    source.add_argument("--expect-origin")
    source.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Capture a dirty source tree as diagnostic evidence instead of rejecting it",
    )
    source.add_argument(
        "--allow-missing-patterns",
        action="store_true",
        help="Do not fail when one or more requested patterns have no match",
    )

    patterns = sub.add_parser(
        "exe-patterns", help="Verify named byte signatures from a JSON catalog against NMS.exe"
    )
    _common(patterns, game=True)
    patterns.add_argument("--catalog", required=True, type=Path)
    patterns.add_argument("--name", action="append", required=True, dest="names")
    patterns.add_argument("--match-limit", type=int, default=20)
    patterns.add_argument(
        "--disassemble-bytes",
        type=int,
        default=0,
        help="Retain this many bytes of bounded disassembly from every unique match",
    )
    patterns.add_argument(
        "--allow-nonunique",
        action="store_true",
        help="Require every signature to match, but do not require exactly one match each",
    )

    functions = sub.add_parser(
        "exe-functions",
        help="Retain PE function boundaries, direct calls, and optional vtable evidence",
    )
    _common(functions, game=True)
    functions.add_argument("--address", action="append", default=[], type=parse_address)
    functions.add_argument(
        "--reference-address",
        action="append",
        default=[],
        type=parse_address,
        help="Find exact RIP-relative code and aligned qword data references to this address",
    )
    functions.add_argument(
        "--include-callers",
        action="store_true",
        help="Scan .text for direct calls to the selected function starts",
    )
    functions.add_argument("--vtable", type=parse_address)
    functions.add_argument("--vtable-count", type=int, default=0)
    functions.add_argument(
        "--memory-displacement",
        action="append",
        default=[],
        type=parse_address,
        help="Scan .text for base/index memory operands using this exact structure offset",
    )

    probe = sub.add_parser(
        "native-search-probe",
        help="Build and statically verify the current-derived Guide search probe",
    )
    _common(probe, game=True)
    probe.add_argument(
        "--probe-tag",
        help="Unique 1-12 character trial tag appended to mission and scan-event IDs",
    )
    probe.add_argument(
        "--guide-preset-slots",
        type=int,
        default=0,
        help="Preload this many reachable Guide preset dispatch missions (maximum 9)",
    )

    scenario = sub.add_parser("scenario", help="Run one versioned TOML investigation scenario")
    _common(scenario, game=True)
    scenario.add_argument("scenario_file", type=Path)

    stage_parser = sub.add_parser(
        "stage", help="Dry-run or transactionally stage one mod in a unique folder"
    )
    _common(stage_parser, game=True)
    stage_parser.add_argument("--mod-root", required=True, type=Path)
    stage_parser.add_argument("--apply", action="store_true")

    status = sub.add_parser("stage-status", help="Verify one owned staged tree")
    _common(status)
    status.add_argument("--run", required=True)

    collect = sub.add_parser(
        "collect", help="Collect stopped-game logs, settings, exports, and screenshots for a stage"
    )
    _common(collect)
    collect.add_argument("--run", required=True)
    collect.add_argument("--screenshot", action="append", default=[], type=Path)

    remove = sub.add_parser(
        "unstage", help="Dry-run or remove one exact unchanged owned staged tree"
    )
    _common(remove)
    remove.add_argument("--run", required=True)
    remove.add_argument("--apply", action="store_true")

    clean = sub.add_parser("clean", help="Dry-run or remove exact owned investigation runs")
    _common(clean)
    clean.add_argument("--run", action="append", required=True, dest="runs")
    clean.add_argument("--apply", action="store_true")
    return root


def _inventory_context(game_root: Path, run_path: Path) -> tuple[dict[str, list[str]], set[str]]:
    catalog = archive_inventory(game_root, run_path / "archive-inventory")
    members = {member for values in catalog.values() for member in values}
    return catalog, members


def _game_evidence(game_root: Path) -> dict:
    health = host_health()
    return {
        "identity": game_identity(
            game_root,
            include_archives=False,
            include_executable_hash=health["healthy"],
        ),
        "host_health": health,
        "performance_evidence_valid": health["healthy"],
        "toolchain_target": target_identity(game_root),
    }


def _toolchain_evidence(*, mbin: bool) -> dict:
    result = {"target": toolchain_config()["target"], "hgpaktool": hgpak_identity()}
    if mbin:
        result["mbincompiler"] = mbin_identity()
    return result


def _vanilla_xml(
    targets: list[str], catalog: dict[str, list[str]], run_path: Path
) -> tuple[dict[str, Path], list[dict]]:
    if not targets:
        return {}, []
    extracted = extract_assets(targets, catalog, run_path / "vanilla-mbin")
    values: dict[str, Path] = {}
    inspections: list[dict] = []
    for index, record in enumerate(extracted):
        inspection = inspect_mbin(
            Path(record["path"]), run_path / "vanilla-decompiled" / f"{index:04d}"
        )
        inspection["logical_path"] = record["logical_path"]
        inspection["archive"] = record["archive"]
        inspection["archive_sha256"] = record["archive_sha256"]
        inspections.append(inspection)
        if inspection["decompiled"]:
            values[record["logical_path"]] = Path(inspection["decompiled"])
    return values, inspections


def _finish(run, command: str, state: str, data: dict, *, json_mode: bool) -> None:
    finished = timestamp()
    value = envelope(
        command,
        state,
        run_id=run.id if run else None,
        started_at=run.started_at if run else None,
        finished_at=finished,
        artifact_paths=[str(run.path)] if run else [],
        data=data,
    )
    if run:
        run.write("result.json", value)
    emit(value, json_mode=json_mode)
    if state in {"failed", "inconclusive"}:
        raise SystemExit(1)


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _require_file(path: Path) -> Path:
    value = path.expanduser().resolve()
    if not value.is_file() or value.is_symlink():
        raise InvestigationError("file_not_found", f"Not a regular file: {value}")
    return value


def _analyze_with_current(mod_root: Path, game_root: Path, run_path: Path) -> dict:
    catalog, members = _inventory_context(game_root, run_path)
    deployment = resolve_deployment_root(mod_root)
    candidate_records = inventory_mod(deployment)
    targets = sorted(
        {
            (
                target_mbin(item["logical_path"])
                if item["suffix"] == ".exml"
                else item["logical_path"]
            )
            for item in candidate_records
            if (item["suffix"] == ".exml" and target_mbin(item["logical_path"]) in members)
            or (item["suffix"] == ".mbin" and item["logical_path"] in members)
        }
    )
    vanilla, vanilla_inspections = _vanilla_xml(targets, catalog, run_path)
    result = analyze_mod(
        mod_root, run_path / "mod-analysis", current_inventory=members, vanilla_xml=vanilla
    )
    result["vanilla_target_inspections"] = vanilla_inspections
    return result


def _clean(runs: list[str], *, apply: bool) -> dict:
    if len(set(runs)) != len(runs):
        raise InvestigationError("duplicate_run", "Each clean --run value must be unique")
    targets = [resolve_run(run_id) for run_id in runs]
    active = [run_id for run_id in runs if (STAGES_ROOT / f"{run_id}.json").exists()]
    if active:
        raise InvestigationError(
            "run_has_active_stage", "Unstage these runs before cleaning them", runs=active
        )
    result = {"apply": apply, "targets": [str(path) for path in targets]}
    if apply:
        for target in targets:
            shutil.rmtree(target)
        result["removed"] = [path.name for path in targets]
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    run = None
    json_mode = args.json
    try:
        if args.command == "doctor":
            started = timestamp()
            game_root = resolve_game_root(args.game_root)
            health = host_health()
            checks: dict[str, object] = {
                "game": game_identity(
                    game_root,
                    include_executable_hash=health["healthy"],
                ),
                "host": host_capabilities(),
                "host_health": health,
                "toolchain_target": target_identity(game_root),
            }
            problems: list[dict] = []
            if not health["healthy"]:
                problems.append(
                    {
                        "component": "host-health",
                        "code": "uninterruptible_processes",
                        "message": (
                            "The host has processes in uninterruptible sleep; performance and "
                            "large-file evidence are invalid until the host recovers"
                        ),
                    }
                )
            if checks["game"]["running_processes"]:
                problems.append(
                    {
                        "component": "game",
                        "code": "game_running",
                        "message": "NMS.exe is running; staging and complete collection are unsafe",
                    }
                )
            if not checks["toolchain_target"]["matches"]:
                problems.append(
                    {
                        "component": "toolchain-target",
                        "code": "unsupported_game_build",
                        "message": "Installed Steam build is outside the pinned toolchain target",
                    }
                )
            for name, function in (
                ("hgpaktool", hgpak_identity),
                ("mbincompiler", verify_mbincompiler),
            ):
                try:
                    checks[name] = function()
                except InvestigationError as exc:
                    checks[name] = None
                    problems.append({"component": name, "code": exc.code, "message": exc.message})
            state = (
                "succeeded"
                if not problems and health["healthy"] and not checks["game"]["running_processes"]
                else "degraded"
            )
            value = envelope(
                "doctor",
                state,
                started_at=started,
                finished_at=timestamp(),
                data={"checks": checks, "problems": problems},
            )
            emit(value, json_mode=json_mode)
            if state == "degraded":
                raise SystemExit(1)
            return

        if args.command == "toolchain":
            started = timestamp()
            if args.action == "sync":
                sync_mbincompiler()
            mbin = verify_mbincompiler(acquire_backend=args.action == "sync")
            data = {
                "target": toolchain_config()["target"],
                "hgpaktool": hgpak_identity(),
                "mbincompiler": mbin,
            }
            value = envelope(
                f"toolchain {args.action}",
                "succeeded",
                started_at=started,
                finished_at=timestamp(),
                data=data,
            )
            emit(value, json_mode=json_mode)
            return

        if args.command == "stage-status":
            started = timestamp()
            data = stage_status(args.run)
            state = (
                "staged"
                if data["staged"] and data.get("content_matches")
                else ("degraded" if data["staged"] else "inactive")
            )
            emit(
                envelope(
                    "stage-status",
                    state,
                    run_id=args.run,
                    started_at=started,
                    finished_at=timestamp(),
                    data=data,
                ),
                json_mode=json_mode,
            )
            if state == "degraded":
                raise SystemExit(1)
            return

        if args.command == "unstage":
            started = timestamp()
            data = unstage(args.run, apply=args.apply)
            state = (
                "inactive"
                if data.get("removed") or not data["staged"]
                else ("staged" if data.get("content_matches") else "degraded")
            )
            emit(
                envelope(
                    "unstage",
                    state,
                    run_id=args.run,
                    started_at=started,
                    finished_at=timestamp(),
                    data=data,
                ),
                json_mode=json_mode,
            )
            return

        if args.command == "collect":
            started = timestamp()
            data = collect_evidence(args.run, args.screenshot)
            emit(
                envelope(
                    "collect",
                    "succeeded",
                    run_id=args.run,
                    started_at=started,
                    finished_at=timestamp(),
                    artifact_paths=[data["artifact_path"]],
                    data=data,
                ),
                json_mode=json_mode,
            )
            return

        if args.command == "clean":
            started = timestamp()
            data = _clean(args.runs, apply=args.apply)
            emit(
                envelope(
                    "clean", "succeeded", started_at=started, finished_at=timestamp(), data=data
                ),
                json_mode=json_mode,
            )
            return

        inputs = _jsonable(
            {key: value for key, value in vars(args).items() if key not in {"json", "command"}}
        )
        run = create_run(args.command, inputs)

        if args.command == "inventory":
            game_root = resolve_game_root(args.game_root)
            catalog, members = _inventory_context(game_root, run.path)
            data = {
                "game": _game_evidence(game_root),
                "toolchain": _toolchain_evidence(mbin=False),
                "archive_count": len(catalog),
                "member_count": sum(map(len, catalog.values())),
                "unique_member_count": len(members),
            }
            _finish(run, "inventory", "succeeded", data, json_mode=json_mode)
        elif args.command == "extract":
            game_root = resolve_game_root(args.game_root)
            catalog, _ = _inventory_context(game_root, run.path)
            records = extract_assets(args.paths, catalog, run.path / "extracted")
            _finish(
                run,
                "extract",
                "succeeded",
                {
                    "game": _game_evidence(game_root),
                    "toolchain": _toolchain_evidence(mbin=False),
                    "files": records,
                },
                json_mode=json_mode,
            )
        elif args.command == "roundtrip":
            sources: list[tuple[str, Path]] = []
            game_data = None
            if args.paths:
                game_root = resolve_game_root(args.game_root)
                assert_supported_build(game_root)
                catalog, _ = _inventory_context(game_root, run.path)
                extracted = extract_assets(args.paths, catalog, run.path / "extracted")
                sources = [(item["logical_path"], Path(item["path"])) for item in extracted]
                game_data = _game_evidence(game_root)
            else:
                sources = [
                    (str(path.expanduser().resolve()), _require_file(path)) for path in args.files
                ]
            results = [
                roundtrip(path, run.path / "roundtrip" / f"{index:04d}") | {"logical_path": logical}
                for index, (logical, path) in enumerate(sources)
            ]
            passed = all(result["passed"] for result in results)
            _finish(
                run,
                "roundtrip",
                "succeeded" if passed else "failed",
                {
                    "game": game_data,
                    "toolchain": _toolchain_evidence(mbin=True),
                    "results": results,
                    "passed": passed,
                },
                json_mode=json_mode,
            )
        elif args.command == "analyze-mod":
            game_root = resolve_game_root(args.game_root)
            assert_supported_build(game_root)
            analysis = _analyze_with_current(args.mod_root, game_root, run.path)
            report = run.path / "mod-analysis/report.json"
            write_analysis_report(analysis, report)
            data = analysis_summary(analysis)
            data["analysis_report"] = str(report)
            data["game"] = _game_evidence(game_root)
            data["toolchain"] = _toolchain_evidence(mbin=True)
            _finish(run, "analyze-mod", data["static_outcome"], data, json_mode=json_mode)
        elif args.command == "conflicts":
            game_root = resolve_game_root(args.game_root)
            assert_supported_build(game_root)
            catalog, members = _inventory_context(game_root, run.path)
            all_targets: set[str] = set()
            for root in args.mod_root:
                for item in inventory_mod(resolve_deployment_root(root)):
                    if item["suffix"] == ".exml" and target_mbin(item["logical_path"]) in members:
                        all_targets.add(target_mbin(item["logical_path"]))
                    elif item["suffix"] == ".mbin" and item["logical_path"] in members:
                        all_targets.add(item["logical_path"])
            vanilla, vanilla_inspections = _vanilla_xml(sorted(all_targets), catalog, run.path)
            analyses = [
                analyze_mod(
                    root,
                    run.path / "mods" / f"{index:04d}",
                    current_inventory=members,
                    vanilla_xml=vanilla,
                )
                for index, root in enumerate(args.mod_root)
            ]
            analysis_reports = []
            for index, analysis in enumerate(analyses):
                report = run.path / "mods" / f"{index:04d}" / "analysis-report.json"
                write_analysis_report(analysis, report)
                analysis_reports.append(analysis_summary(analysis) | {"report": str(report)})
            inspection_report = run.path / "vanilla-target-inspections.json"
            write_json(inspection_report, vanilla_inspections)
            data = {
                "mods": analysis_reports,
                "vanilla_target_inspection_count": len(vanilla_inspections),
                "vanilla_target_inspections_report": str(inspection_report),
                "game": _game_evidence(game_root),
                "toolchain": _toolchain_evidence(mbin=True),
                **conflict_report(analyses),
            }
            _finish(
                run,
                "conflicts",
                (
                    "failed"
                    if data["confirmed_conflict_count"]
                    else ("inconclusive" if data["potential_conflict_count"] else "succeeded")
                ),
                data,
                json_mode=json_mode,
            )
        elif args.command == "compare":
            data = compare_xml(_require_file(args.left), _require_file(args.right))
            passed = (
                args.expect == "any"
                or (args.expect == "equal" and data["equal"])
                or (args.expect == "different" and not data["equal"])
            )
            data["expectation"] = args.expect
            data["expectation_met"] = passed
            _finish(run, "compare", "succeeded" if passed else "failed", data, json_mode=json_mode)
        elif args.command == "verify-export":
            data = verify_export(
                _require_file(args.patch),
                _require_file(args.exported),
                _require_file(args.vanilla) if args.vanilla else None,
            )
            _finish(
                run,
                "verify-export",
                "succeeded" if data["passed"] else "failed",
                data,
                json_mode=json_mode,
            )
        elif args.command == "exe-strings":
            game_root = resolve_game_root(args.game_root)
            data = inspect_strings(
                game_root / "Binaries/NMS.exe",
                args.pattern or DEFAULT_STRING_PATTERNS,
                limit=args.limit,
            )
            data["game"] = _game_evidence(game_root)
            passed = data["all_patterns_matched"] or args.allow_missing_patterns
            data["require_each_pattern"] = not args.allow_missing_patterns
            data["expectation_met"] = passed
            _finish(
                run,
                "exe-strings",
                "succeeded" if passed else "failed",
                data,
                json_mode=json_mode,
            )
        elif args.command == "source-snapshot":
            data = snapshot_source(
                args.repository,
                args.files,
                run.path / "source-snapshot",
                patterns=args.pattern,
                limit=args.limit,
                allow_dirty=args.allow_dirty,
            )
            revision_matches = (
                args.expect_revision is None or data["revision"] == args.expect_revision
            )
            origin_matches = args.expect_origin is None or data["origin"] == args.expect_origin
            patterns_match = data["all_patterns_matched"] or args.allow_missing_patterns
            data["expectations"] = {
                "revision": args.expect_revision,
                "revision_matches": revision_matches,
                "origin": args.expect_origin,
                "origin_matches": origin_matches,
                "require_each_pattern": not args.allow_missing_patterns,
                "patterns_match": patterns_match,
            }
            passed = revision_matches and origin_matches and patterns_match
            _finish(
                run,
                "source-snapshot",
                "succeeded" if passed else "failed",
                data,
                json_mode=json_mode,
            )
        elif args.command == "exe-patterns":
            game_root = resolve_game_root(args.game_root)
            data = inspect_pattern_catalog(
                game_root / "Binaries/NMS.exe",
                args.catalog,
                args.names,
                run.path / "pattern-catalog",
                match_limit=args.match_limit,
                disassemble_bytes=args.disassemble_bytes,
            )
            data["game"] = _game_evidence(game_root)
            data["require_unique"] = not args.allow_nonunique
            passed = data["all_matched"] and (data["all_unique"] or args.allow_nonunique)
            data["expectation_met"] = passed
            _finish(
                run,
                "exe-patterns",
                "succeeded" if passed else "failed",
                data,
                json_mode=json_mode,
            )
        elif args.command == "exe-functions":
            game_root = resolve_game_root(args.game_root)
            if (args.vtable is None) != (args.vtable_count == 0):
                raise InvestigationError(
                    "invalid_vtable",
                    "--vtable and a positive --vtable-count must be supplied together",
                )
            data = inspect_functions(
                game_root / "Binaries/NMS.exe",
                args.address,
                run.path / "pe-functions",
                include_callers=args.include_callers,
                vtable_address=args.vtable,
                vtable_count=args.vtable_count,
                memory_displacements=args.memory_displacement,
                reference_addresses=args.reference_address,
            )
            data["game"] = _game_evidence(game_root)
            _finish(run, "exe-functions", "succeeded", data, json_mode=json_mode)
        elif args.command == "native-search-probe":
            game_root = resolve_game_root(args.game_root)
            assert_supported_build(game_root)
            catalog, members = _inventory_context(game_root, run.path)
            targets = [
                "metadata/reality/wiki.mbin",
                "metadata/simulation/missions/tables/wikimissiontable.mbin",
                "metadata/simulation/missions/tables/npcmissiontable.mbin",
            ]
            vanilla, vanilla_inspections = _vanilla_xml(targets, catalog, run.path)
            probe = build_native_search_probe(
                vanilla[targets[0]],
                vanilla[targets[1]],
                vanilla[targets[2]],
                run.path / "native-search-probe",
                probe_tag=args.probe_tag,
                guide_preset_slots=args.guide_preset_slots,
            )
            analysis = analyze_mod(
                Path(probe["deployment_root"]),
                run.path / "mod-analysis",
                current_inventory=members,
                vanilla_xml=vanilla,
            )
            report = run.path / "mod-analysis/report.json"
            write_analysis_report(analysis, report)
            deployment = Path(probe["deployment_root"])
            patch_compile_checks = [
                verify_probe_patch_compile(
                    patch,
                    run.path / "patch-compile-checks" / f"{index:02d}-{patch.stem.casefold()}",
                )
                for index, patch in enumerate(sorted(deployment.rglob("*.EXML")))
            ]
            analysis_data = analysis_summary(analysis)
            passed = analysis_data["static_outcome"] == "succeeded" and all(
                check["passed"] for check in patch_compile_checks
            )
            _finish(
                run,
                "native-search-probe",
                "succeeded" if passed else "failed",
                {
                    "probe": probe,
                    "analysis": analysis_data,
                    "analysis_report": str(report),
                    "patch_compile_checks": patch_compile_checks,
                    "vanilla_target_inspections": vanilla_inspections,
                    "game": _game_evidence(game_root),
                    "toolchain": _toolchain_evidence(mbin=True),
                    "runtime_compatibility_proven": False,
                },
                json_mode=json_mode,
            )
        elif args.command == "scenario":
            data = run_scenario(args.scenario_file, args.game_root, run.path)
            data["toolchain"] = _toolchain_evidence(mbin=True)
            if data["game_root"]:
                data["game"] = _game_evidence(Path(data["game_root"]))
            _finish(
                run,
                "scenario",
                "succeeded" if data["passed"] else "failed",
                data,
                json_mode=json_mode,
            )
        elif args.command == "stage":
            game_root = resolve_game_root(args.game_root)
            data = stage(args.mod_root, game_root, run.id, apply=args.apply)
            _finish(
                run, "stage", "staged" if args.apply else "succeeded", data, json_mode=json_mode
            )
        else:
            raise InvestigationError("unknown_command", f"Unhandled command: {args.command}")
    except InvestigationError as exc:
        value = envelope(
            args.command,
            "error",
            run_id=run.id if run else None,
            started_at=run.started_at if run else None,
            finished_at=timestamp(),
            artifact_paths=[str(run.path)] if run else [],
            error={"code": exc.code, "message": exc.message, "details": exc.details},
        )
        if run:
            run.write("result.json", value)
        emit(value, json_mode=json_mode)
        raise SystemExit(2) from exc
    except Exception as exc:
        value = envelope(
            args.command,
            "error",
            run_id=run.id if run else None,
            started_at=run.started_at if run else None,
            finished_at=timestamp(),
            artifact_paths=[str(run.path)] if run else [],
            error={
                "code": "internal_error",
                "message": str(exc),
                "details": {"type": type(exc).__name__},
            },
        )
        if run:
            run.write("result.json", value)
        emit(value, json_mode=json_mode)
        raise SystemExit(3) from exc


if __name__ == "__main__":
    main()
