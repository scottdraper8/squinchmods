from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cleanup import remove_acquired
from .errors import AcquisitionError
from .modrinth import acquire_catalog_artifact, audit_latest_catalog, cache_root
from .catalog import load_catalog, validate_catalog
from .source import checkout_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="squinch third-party minecraft")
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire = subparsers.add_parser("acquire", help="Acquire a Modrinth release JAR")
    acquire.add_argument("--artifact-id", required=True)
    acquire.add_argument("--catalog", type=Path)
    acquire.add_argument("--cache-root", type=Path)
    acquire.add_argument("--include-beta", action="store_true", help="Allow an explicitly pinned beta-channel release")

    validate = subparsers.add_parser("validate", help="Validate the committed artifact catalog")
    validate.add_argument("--catalog", type=Path)
    validate.add_argument("--cache-root", type=Path)

    latest = subparsers.add_parser(
        "audit-latest", help="Compare catalog pins with live compatible Modrinth releases"
    )
    latest.add_argument("--artifact-id", action="append", dest="artifact_ids")
    latest.add_argument("--catalog", type=Path)
    latest.add_argument(
        "--include-beta", action="store_true", help="Include beta and alpha channels"
    )

    remove = subparsers.add_parser("remove", help="Remove acquired release and optional source artifacts")
    remove.add_argument("--artifact-id", required=True, help="Catalog artifact ID to remove")
    remove.add_argument("--catalog", type=Path)
    remove.add_argument("--source", type=Path, help="Explicit source checkout to remove, if present")
    remove.add_argument("--cache-root", type=Path)
    remove.add_argument("--apply", action="store_true", help="Perform the removal; otherwise print a dry-run plan")

    source = subparsers.add_parser("source", help="Create a shallow sparse source checkout")
    source.add_argument("--repository", required=True)
    source.add_argument("--destination", required=True, type=Path)
    source.add_argument("--ref", required=True, help="Branch or tag targeting the requested Minecraft version")
    source.add_argument("--minecraft-version", required=True, dest="minecraft_version")
    source.add_argument("--sparse", action="append", required=True, dest="sparse_paths")
    source.add_argument("--replace", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    try:
        catalog = (getattr(args, "catalog", None) or Path(".squinch/games/minecraft/third-party/artifacts.toml")).expanduser().resolve()
        if args.command == "acquire":
            release = acquire_catalog_artifact(
                args.artifact_id,
                catalog,
                destination_root=args.cache_root,
                include_beta=args.include_beta,
            )
            print(json.dumps({
                "project": release.project,
                "project_id": release.project_id,
                "version_id": release.version_id,
                "version_number": release.version_number,
                "minecraft_version": release.minecraft_version,
                "loader": release.requested_loader,
                "path": str(release.path),
                "sha256": release.sha256,
                "required_dependencies": list(release.dependencies),
            }, indent=2, sort_keys=True))
        elif args.command == "validate":
            print(json.dumps(validate_catalog(
                catalog,
                cache_root=args.cache_root or cache_root(),
            ), indent=2, sort_keys=True))
        elif args.command == "audit-latest":
            artifacts, _sources = load_catalog(catalog)
            selected_ids = args.artifact_ids or [
                artifact.id
                for artifact in artifacts.values()
                if artifact.status in {"approved", "diagnostic-only"}
            ]
            missing = sorted(set(selected_ids) - artifacts.keys())
            if missing:
                raise AcquisitionError(f"catalog artifact does not exist: {missing[0]}")
            print(json.dumps(audit_latest_catalog(
                [artifacts[artifact_id] for artifact_id in selected_ids],
                include_beta=args.include_beta,
            ), indent=2, sort_keys=True))
        elif args.command == "source":
            print(json.dumps(checkout_source(
                args.repository,
                args.destination.expanduser().resolve(),
                args.ref,
                minecraft_version=args.minecraft_version,
                sparse_paths=tuple(args.sparse_paths),
                replace=args.replace,
            ), indent=2, sort_keys=True))
        else:
            artifacts, _sources = load_catalog(catalog)
            try:
                artifact = artifacts[args.artifact_id]
            except KeyError as exc:
                raise AcquisitionError(f"catalog artifact does not exist: {args.artifact_id}") from exc
            print(json.dumps(remove_acquired(
                artifact.project_slug,
                artifact.minecraft_version,
                artifact.loader,
                version_number=artifact.version_number,
                source=args.source,
                destination_root=args.cache_root,
                apply=args.apply,
            ), indent=2, sort_keys=True))
    except AcquisitionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
