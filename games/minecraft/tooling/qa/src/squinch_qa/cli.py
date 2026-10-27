from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from squinch_qa.artifacts import default_qa_runs_dir
from squinch_qa.config import find_repo_root, load_mod_config, load_parent_config
from squinch_qa.errors import (
    ConfigError,
    PlanError,
    PlanLimitExceeded,
    SummaryError,
    UnknownMod,
    UnknownProfile,
    UnknownTarget,
    ValidationError,
)
from squinch_qa.planner import build_plan, emit_plan_json
from squinch_qa.resolve import resolve_profile
from squinch_qa.tranche import prepare_owned_directory, require_scratch_input


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="squinch_qa",
        description="Plan and run local Minecraft checks for squinchmods",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="<subcommand>")

    plan = subparsers.add_parser("plan", help="Emit an execution plan JSON")
    plan.add_argument("mod", metavar="<mod>", help="Mod slug or id")
    plan.add_argument("--profile", metavar="<name>")
    plan.add_argument("--target", metavar="<id>")
    plan.add_argument("--repo-root", metavar="<path>")

    run = subparsers.add_parser("run", help="Execute a QA plan")
    run.add_argument("mod", metavar="<mod>", help="Mod slug or id")
    run.add_argument(
        "--plan",
        metavar="<path>",
        help="Task-local plan inside the selected tranche (default: generate from config)",
    )
    run.add_argument("--profile", metavar="<name>")
    run.add_argument("--target", metavar="<id>")
    run.add_argument("--run-id", metavar="<id>")
    run.add_argument("--repo-root", metavar="<path>")

    summary = subparsers.add_parser("summary", help="Print a completed run summary")
    summary.add_argument("run_id", metavar="<run-id>")
    summary.add_argument("--repo-root", metavar="<path>")
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
        plan_bytes = require_scratch_input(Path(args.plan)).read_bytes()
        plan = parse_plan_json(plan_bytes)
        if plan.mod_id != mod.mod_id:
            raise PlanError(
                f"plan mod id {plan.mod_id!r} does not match selected mod {mod.mod_id!r}"
            )
    else:
        parent = load_parent_config(repo_root)
        resolved = resolve_profile(parent, mod, args.profile)
        plan = build_plan(mod, resolved, args.target)
        plan_bytes = emit_plan_json(plan).encode()
    state = create_run_state(
        plan_bytes,
        default_qa_runs_dir(repo_root),
        run_id=args.run_id,
    )
    return run_plan(state, repo_root=repo_root, mod_dir=mod_dir)


def _cmd_summary(args: argparse.Namespace) -> int:
    from squinch_qa.summary import render_summary

    runs = default_qa_runs_dir(_resolve_repo_root(args)).resolve()
    selected = (runs / args.run_id).resolve()
    if selected.parent != runs:
        raise SummaryError(f"run ID escapes the selected tranche: {args.run_id}")
    sys.stdout.write(render_summary(selected))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.print_help(sys.stderr)
        return 1
    try:
        prepare_owned_directory("minecraft", "qa")
        if args.subcommand == "plan":
            return _cmd_plan(args)
        if args.subcommand == "run":
            return _cmd_run(args)
        if args.subcommand == "summary":
            return _cmd_summary(args)
    except (UnknownMod, UnknownProfile, UnknownTarget) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (ConfigError, PlanError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    except PlanLimitExceeded as exc:
        print(f"plan limit: {exc}", file=sys.stderr)
        return 3
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 5
    except SummaryError as exc:
        print(f"summary error: {exc}", file=sys.stderr)
        return 10
    return 0
