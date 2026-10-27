from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import TrancheError, clean_tranche, create_tranche, resolve_tranche


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="squinch tranche")
    parser.add_argument("--repo-root", type=Path, required=True, help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "path", "resolve"):
        command = subparsers.add_parser(name)
        command.add_argument("tranche")
        if name != "resolve":
            command.add_argument("--json", action="store_true")
    clean = subparsers.add_parser("clean")
    clean.add_argument("tranche")
    clean.add_argument("--apply", action="store_true")
    clean.add_argument("--json", action="store_true")
    return parser


def _emit(value: dict, *, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(value, sort_keys=True))
        return
    if value["command"] == "create":
        print(f"created tranche {value['tranche']}: {value['workspace']}")
    elif value["command"] == "path":
        print(value["workspace"])
    elif value["action"] == "absent":
        print(f"tranche {value['tranche']} is already absent: {value['workspace']}")
    elif value["action"] == "dry-run":
        print(f"dry-run tranche {value['tranche']}: {value['workspace']}")
    else:
        print(f"cleaned tranche {value['tranche']}: {value['workspace']}")
    for record in value.get("external", []):
        for path in record["paths"]:
            print(f"external stage: {path}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            workspace = create_tranche(args.repo_root, args.tranche)
            value = {
                "command": "create",
                "tranche": args.tranche,
                "workspace": str(workspace),
            }
        elif args.command in {"path", "resolve"}:
            workspace = resolve_tranche(
                args.repo_root,
                args.tranche,
                validate_owned=args.command == "resolve",
            )
            if args.command == "resolve":
                print(workspace)
                return 0
            value = {
                "command": "path",
                "tranche": args.tranche,
                "workspace": str(workspace),
            }
        else:
            value = {
                "command": "clean",
                **clean_tranche(args.repo_root, args.tranche, apply=args.apply),
            }
        _emit(value, json_mode=args.json)
        return 0
    except TrancheError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        if exc.details:
            print(json.dumps(exc.details, sort_keys=True), file=sys.stderr)
        return 2
