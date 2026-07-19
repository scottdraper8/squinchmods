from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from squinch_qa.artifacts import default_qa_root, default_qa_runs_dir
from squinch_qa.config import find_repo_root, load_mod_config, load_parent_config
from squinch_qa.errors import (
    ConfigError,
    MatrixLimitExceeded,
    PlanError,
    ReplaceError,
    SummaryError,
    UnknownMod,
    UnknownProfile,
    UnknownTarget,
    ValidationError,
)
from squinch_qa.planner import build_plan, emit_plan_json
from squinch_qa.remote.errors import (
    DispatchError,
    DownloadError,
    PollError,
    PollTimeoutError,
)
from squinch_qa.resolve import resolve_profile


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="squinch_qa",
        description="squinchmods QA planner",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="<subcommand>")

    plan_p = subparsers.add_parser("plan", help="Emit an execution plan JSON")
    plan_p.add_argument("mod", metavar="<mod>", help="Mod slug or id")
    plan_p.add_argument(
        "--profile",
        metavar="<name>",
        default=None,
        help="Profile name (default: parent config default_profile)",
    )
    plan_p.add_argument(
        "--target", metavar="<id>", default=None, help="Restrict to a single target id"
    )
    plan_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )

    run_p = subparsers.add_parser("run", help="Execute a QA plan")
    run_p.add_argument("mod", metavar="<mod>", help="Mod slug or id")
    run_p.add_argument(
        "--plan",
        metavar="<path>",
        default=None,
        help="Path to pre-generated plan JSON (default: generate from mod config)",
    )
    run_p.add_argument(
        "--qa-runs-dir",
        metavar="<path>",
        default=None,
        help="Directory for run artifacts (default: <repo-root>/games/minecraft/qa-state/runs)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan JSON and exit without creating run dirs or executing",
    )
    run_p.add_argument(
        "--profile",
        metavar="<name>",
        default=None,
        help="Profile name (default: parent config default_profile)",
    )
    run_p.add_argument(
        "--target", metavar="<id>", default=None, help="Restrict to a single target id"
    )
    run_p.add_argument(
        "--run-id",
        metavar="<id>",
        default=None,
        help="External run ID to use instead of generating one",
    )
    run_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )
    run_p.add_argument(
        "--promote",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Promote passing pregen worlds to games/minecraft/qa-state/current after a passing run",
    )
    run_p.add_argument(
        "--clean",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prune old QA runs/trash after execution (default: enabled)",
    )

    promote_p = subparsers.add_parser(
        "promote",
        help="Promote a completed run's worlds into games/minecraft/qa-state/current",
    )
    promote_p.add_argument(
        "--run-id", metavar="<id>", required=True, help="Run ID to promote"
    )
    promote_p.add_argument(
        "--target", metavar="<id>", default=None, help="Restrict to a single target id"
    )
    promote_p.add_argument(
        "--test", metavar="<id>", default=None, help="Restrict to a single test id"
    )
    promote_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report what would be promoted without touching games/minecraft/qa-state/current",
    )
    promote_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )
    promote_p.add_argument(
        "--qa-runs-dir",
        metavar="<path>",
        default=None,
        help="Directory the run lives under (default: <repo-root>/games/minecraft/qa-state/runs)",
    )

    remote_p = subparsers.add_parser(
        "remote-run", help="Dispatch and collect a GitHub Actions QA run"
    )
    remote_p.add_argument("mod", metavar="<mod>", help="Mod slug or id")
    remote_p.add_argument(
        "--profile",
        metavar="<name>",
        default=None,
        help="Profile name (default: parent config default_profile)",
    )
    remote_p.add_argument(
        "--target", metavar="<id>", default=None, help="Restrict to a single target id"
    )
    remote_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )
    remote_p.add_argument(
        "--qa-runs-dir",
        metavar="<path>",
        default=None,
        help="Directory for downloaded run artifacts (default: <repo-root>/games/minecraft/qa-state/runs)",
    )
    remote_p.add_argument(
        "--promote",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Promote passing remote pregen worlds to games/minecraft/qa-state/current after download",
    )
    remote_p.add_argument(
        "--poll-interval",
        metavar="<seconds>",
        type=float,
        default=5.0,
        help="Seconds between GitHub run status checks (default: 5)",
    )
    remote_p.add_argument(
        "--timeout",
        metavar="<seconds>",
        type=float,
        default=1800.0,
        help="Seconds to wait for the GitHub Actions run (default: 1800)",
    )
    remote_p.add_argument(
        "--run-id",
        metavar="<id>",
        default=None,
        help="External run ID to use instead of generating one",
    )
    remote_p.add_argument(
        "--clean",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prune old QA runs/trash after download/promotion (default: enabled)",
    )

    clean_p = subparsers.add_parser(
        "clean",
        help="Prune generated QA runs and trash without touching current worlds",
    )
    clean_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )
    clean_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything",
    )
    clean_p.add_argument(
        "--runs",
        action="store_true",
        help="Prune games/minecraft/qa-state/runs",
    )
    clean_p.add_argument(
        "--trash",
        action="store_true",
        help="Prune games/minecraft/qa-state/trash",
    )
    clean_p.add_argument(
        "--keep-runs",
        metavar="<count>",
        type=_non_negative_int,
        default=20,
        help="Keep at least this many newest runs (default: 20)",
    )
    clean_p.add_argument(
        "--max-run-age-days",
        metavar="<days>",
        type=_non_negative_int,
        default=30,
        help="Only prune runs at least this old; set 0 for count-only pruning (default: 30)",
    )
    clean_p.add_argument(
        "--keep-trash",
        metavar="<count>",
        type=_non_negative_int,
        default=2,
        help="Keep this many trash entries per mod/target/test (default: 2)",
    )

    summary_p = subparsers.add_parser(
        "summary",
        help="Print a human-readable summary of a completed run",
    )
    summary_p.add_argument("run_id", metavar="<run-id>", help="Run id to summarize")
    summary_p.add_argument(
        "--repo-root",
        metavar="<path>",
        default=None,
        help="Path to squinchmods repo root ($SQUINCHMODS_ROOT or auto-detected)",
    )
    summary_p.add_argument(
        "--qa-runs-dir",
        metavar="<path>",
        default=None,
        help="Override the runs directory (default: games/minecraft/qa-state/runs)",
    )

    return parser


def _resolve_repo_root(args: argparse.Namespace) -> Path:
    if args.repo_root is not None:
        return Path(args.repo_root)
    if "SQUINCHMODS_ROOT" in os.environ:
        return Path(os.environ["SQUINCHMODS_ROOT"])
    return find_repo_root(Path.cwd())


def _cmd_plan(args: argparse.Namespace) -> int:
    repo_root = _resolve_repo_root(args)
    parent = load_parent_config(repo_root)
    mod, _ = load_mod_config(repo_root, args.mod)
    resolved = resolve_profile(parent, mod, args.profile)
    plan = build_plan(mod, resolved, args.target)
    sys.stdout.write(emit_plan_json(plan))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from squinch_qa.runner import create_run_state, parse_plan_json, run_plan

    repo_root = _resolve_repo_root(args)
    mod, mod_dir = load_mod_config(repo_root, args.mod)

    if args.plan is not None:
        plan_bytes = Path(args.plan).read_bytes()
        plan = parse_plan_json(plan_bytes)
        if plan.mod_id != mod.mod_id:
            raise PlanError(
                f"plan mod id {plan.mod_id!r} does not match selected mod "
                f"{mod.mod_id!r}"
            )
    else:
        parent = load_parent_config(repo_root)
        resolved = resolve_profile(parent, mod, args.profile)
        plan = build_plan(mod, resolved, args.target)
        plan_bytes = emit_plan_json(plan).encode()

    if args.qa_runs_dir is not None:
        qa_runs_dir = Path(args.qa_runs_dir)
    else:
        qa_runs_dir = default_qa_runs_dir(repo_root)

    state = create_run_state(plan_bytes, qa_runs_dir, run_id=args.run_id)

    return run_plan(
        state,
        repo_root=repo_root,
        mod_dir=mod_dir,
        dry_run=args.dry_run,
        promote=args.promote,
        clean=args.clean,
    )


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _cmd_promote(args: argparse.Namespace) -> int:
    from squinch_qa.replace import promote_run, recover_pending
    from squinch_qa.replace._pathsafe import assert_within

    repo_root = _resolve_repo_root(args)
    qa_runs_dir = (
        Path(args.qa_runs_dir)
        if args.qa_runs_dir is not None
        else default_qa_runs_dir(repo_root)
    )
    run_dir = assert_within(qa_runs_dir, qa_runs_dir / args.run_id)

    if not args.dry_run:
        recover_pending(default_qa_root(repo_root))

    _emit({"type": "promote_start", "run_id": args.run_id})
    results = promote_run(
        default_qa_root(repo_root),
        run_dir,
        target_filter=args.target,
        test_filter=args.test,
        dry_run=args.dry_run,
    )
    for r in results:
        _emit(
            {
                "type": "promote_job",
                "mod_id": r.mod_id,
                "target": r.target_id,
                "test": r.test_id,
                "promoted": r.promoted,
                "reason": r.reason,
            }
        )
    _emit({"type": "promote_done", "run_id": args.run_id})
    return 6 if any(r.is_failure for r in results) else 0


def _cmd_remote_run(args: argparse.Namespace) -> int:
    from squinch_qa.remote import remote_run

    repo_root = _resolve_repo_root(args)
    parent = load_parent_config(repo_root)
    mod_config, _ = load_mod_config(repo_root, args.mod)
    resolved = resolve_profile(parent, mod_config, args.profile)
    build_plan(mod_config, resolved, args.target)

    qa_runs_dir = (
        Path(args.qa_runs_dir)
        if args.qa_runs_dir is not None
        else default_qa_runs_dir(repo_root)
    )
    return remote_run(
        mod=args.mod,
        repo_root=repo_root,
        qa_runs_dir=qa_runs_dir,
        target=args.target,
        profile=args.profile,
        promote=args.promote,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        run_id=args.run_id,
        clean=args.clean,
        emit=_emit,
    )


def _cmd_clean(args: argparse.Namespace) -> int:
    from squinch_qa.cleanup import CleanPolicy, clean_qa

    repo_root = _resolve_repo_root(args)
    states = []
    if args.runs:
        states.append("runs")
    if args.trash:
        states.append("trash")
    if not states:
        states = ["runs", "trash"]

    policy = CleanPolicy(
        keep_runs=args.keep_runs,
        max_run_age_days=args.max_run_age_days,
        keep_trash=args.keep_trash,
    )

    _emit({"type": "clean_start", "states": states, "dry_run": args.dry_run})
    actions = clean_qa(
        default_qa_root(repo_root),
        policy=policy,
        states=tuple(states),
        dry_run=args.dry_run,
    )
    for action in actions:
        _emit(
            {
                "type": "clean_item",
                "state": action.state,
                "path": str(action.path),
                "reason": action.reason,
                "removed": action.removed,
            }
        )
    _emit({"type": "clean_done", "count": len(actions), "dry_run": args.dry_run})
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    from squinch_qa.replace._pathsafe import assert_within
    from squinch_qa.summary import render_summary

    repo_root = _resolve_repo_root(args)
    qa_runs_dir = (
        Path(args.qa_runs_dir)
        if args.qa_runs_dir is not None
        else default_qa_runs_dir(repo_root)
    )
    run_dir = assert_within(qa_runs_dir, qa_runs_dir / args.run_id)
    sys.stdout.write(render_summary(run_dir))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help(sys.stderr)
        return 1

    try:
        if args.subcommand == "plan":
            return _cmd_plan(args)
        if args.subcommand == "run":
            return _cmd_run(args)
        if args.subcommand == "promote":
            return _cmd_promote(args)
        if args.subcommand == "remote-run":
            return _cmd_remote_run(args)
        if args.subcommand == "clean":
            return _cmd_clean(args)
        if args.subcommand == "summary":
            return _cmd_summary(args)
    except (UnknownMod, UnknownProfile, UnknownTarget) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    except MatrixLimitExceeded as e:
        print(f"matrix limit: {e}", file=sys.stderr)
        return 3
    except PlanError as e:
        print(f"plan error: {e}", file=sys.stderr)
        return 2
    except ValidationError as e:
        print(f"validation error: {e}", file=sys.stderr)
        return 5
    except ReplaceError as e:
        print(f"replace error: {e}", file=sys.stderr)
        return 6
    except DispatchError as e:
        print(f"dispatch error: {e}", file=sys.stderr)
        return 7
    except PollTimeoutError as e:
        print(f"poll timeout: {e}", file=sys.stderr)
        return 8
    except PollError as e:
        print(f"poll error: {e}", file=sys.stderr)
        return 8
    except DownloadError as e:
        print(f"download error: {e}", file=sys.stderr)
        return 9
    except SummaryError as e:
        print(f"summary error: {e}", file=sys.stderr)
        return 10

    return 0
