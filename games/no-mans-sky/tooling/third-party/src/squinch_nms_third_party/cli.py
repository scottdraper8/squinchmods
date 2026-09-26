from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .archive import inspect_archive
from .catalog import artifact_from_catalog, validate_catalog
from .errors import AcquisitionError
from .nexus import (
    acquire,
    artifact_freshness,
    artifact_metadata,
    cache_root,
    import_archive,
)

DEFAULT_CATALOG = Path(".squinch/games/no-mans-sky/third-party/artifacts.toml")
DEFAULT_REFERENCE_ROOT = Path("games/no-mans-sky/reference/sources")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="squinch third-party no-mans-sky")
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser(
        "metadata", help="Retrieve live Nexus mod and file metadata"
    )
    metadata.add_argument("--artifact-id", required=True)
    metadata.add_argument("--catalog", type=Path)

    freshness = subparsers.add_parser(
        "freshness", help="Compare a catalog pin with the newest visible MAIN file"
    )
    freshness.add_argument("--artifact-id", required=True)
    freshness.add_argument("--catalog", type=Path)

    acquire_parser = subparsers.add_parser(
        "acquire", help="Download a catalog file through Nexus"
    )
    acquire_parser.add_argument("--artifact-id", required=True)
    acquire_parser.add_argument("--catalog", type=Path)
    acquire_parser.add_argument("--cache-root", type=Path)

    import_parser = subparsers.add_parser(
        "import",
        help="Import an archive downloaded manually in an authenticated browser",
    )
    import_parser.add_argument("--artifact-id", required=True)
    import_parser.add_argument("--archive", required=True, type=Path)
    import_parser.add_argument("--catalog", type=Path)
    import_parser.add_argument("--cache-root", type=Path)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Safely unpack and inventory an acquired file"
    )
    inspect_parser.add_argument("--artifact-id", required=True)
    inspect_parser.add_argument("--catalog", type=Path)
    inspect_parser.add_argument("--cache-root", type=Path)
    inspect_parser.add_argument("--reference-root", type=Path)
    inspect_parser.add_argument(
        "--archive", type=Path, help="Explicit archive; otherwise use acquisition.json"
    )

    validate_parser = subparsers.add_parser(
        "validate", help="Validate catalog and approved cached artifacts"
    )
    validate_parser.add_argument("--catalog", type=Path)
    validate_parser.add_argument("--cache-root", type=Path)

    remove_parser = subparsers.add_parser(
        "remove", help="Dry-run or remove one exact cached/inspection artifact"
    )
    remove_parser.add_argument("--artifact-id", required=True)
    remove_parser.add_argument("--catalog", type=Path)
    remove_parser.add_argument("--cache-root", type=Path)
    remove_parser.add_argument("--reference-root", type=Path)
    remove_parser.add_argument("--apply", action="store_true")
    return parser


def _catalog(args: argparse.Namespace) -> Path:
    return (getattr(args, "catalog", None) or DEFAULT_CATALOG).expanduser().resolve()


def _cache(args: argparse.Namespace) -> Path:
    return (getattr(args, "cache_root", None) or cache_root()).expanduser().resolve()


def _reference(args: argparse.Namespace) -> Path:
    return (
        (getattr(args, "reference_root", None) or DEFAULT_REFERENCE_ROOT)
        .expanduser()
        .resolve()
    )


def _acquired_archive(artifact, root: Path) -> Path:
    directory = root / artifact.cache_relative_directory
    manifest_path = directory / "acquisition.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise AcquisitionError(f"acquisition manifest is missing: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcquisitionError(
            f"invalid acquisition manifest: {manifest_path}: {exc}"
        ) from exc
    if manifest.get("artifact_id") != artifact.id:
        raise AcquisitionError(
            f"acquisition manifest belongs to another artifact: {manifest_path}"
        )
    filename = manifest.get("file_name")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise AcquisitionError(
            f"acquisition manifest has an unsafe filename: {manifest_path}"
        )
    return directory / filename


def _remove(artifact, args: argparse.Namespace) -> dict[str, object]:
    cache_directory = _cache(args) / artifact.cache_relative_directory
    inspection_directory = _reference(args) / artifact.reference_relative_directory
    targets = [
        path for path in (cache_directory, inspection_directory) if path.exists()
    ]
    result: dict[str, object] = {
        "apply": args.apply,
        "targets": [str(path) for path in targets],
    }
    if not args.apply:
        return result
    if cache_directory.exists():
        manifest = cache_directory / "acquisition.json"
        if not manifest.is_file() or manifest.is_symlink():
            raise AcquisitionError(
                f"refusing cache removal without acquisition manifest: {cache_directory}"
            )
    if inspection_directory.exists():
        report = inspection_directory / "inspection.json"
        if not report.is_file() or report.is_symlink():
            raise AcquisitionError(
                f"refusing inspection removal without report: {inspection_directory}"
            )
    for path in targets:
        shutil.rmtree(path)
    return result


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    try:
        catalog_path = _catalog(args)
        if args.command == "validate":
            result = validate_catalog(catalog_path, cache_root=_cache(args))
        else:
            artifact = artifact_from_catalog(catalog_path, args.artifact_id)
            if args.command == "metadata":
                result = artifact_metadata(artifact)
            elif args.command == "freshness":
                result = artifact_freshness(artifact)
            elif args.command == "acquire":
                if artifact.status == "retired":
                    raise AcquisitionError(
                        f"catalog artifact is retired: {artifact.id}"
                    )
                result = acquire(artifact, destination_root=_cache(args))
            elif args.command == "import":
                result = import_archive(
                    artifact, args.archive, destination_root=_cache(args)
                )
            elif args.command == "inspect":
                archive = args.archive or _acquired_archive(artifact, _cache(args))
                result = inspect_archive(
                    artifact, archive, reference_root=_reference(args)
                )
            else:
                result = _remove(artifact, args)
        print(json.dumps(result, indent=2, sort_keys=True))
    except AcquisitionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
