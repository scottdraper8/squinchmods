from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .errors import InvestigationError
from .fixtures import RTF_PRESET_PATH, load_fixture, materialize_ephemeral_fixture
from .paths import MINECRAFT_DIR, RUNS_ROOT, resolve_project, validate_loader
from .scenario import _java_seed
from .server import OWNERSHIP, new_run_id, sourced_environment
from .state import atomic_write_json, read_json

CELL_SCAN_ROOT = MINECRAFT_DIR / "investigations" / "reterraforged" / "cell-scan"
CELL_SCAN_OVERLAY = CELL_SCAN_ROOT / "gradle" / "cell-scan.gradle"
PREDICATE = re.compile(r"^([^:]+):(>=|<=|==|!=|>|<):(.+)$")
CELL_FIELDS = {
    "height", "height_blocks", "height_erosion", "sediment", "gradient",
    "terrain", "terrain_category", "biome_type", "continent_id", "continent_edge",
    "continent_distance", "continent_x", "continent_z", "continent_scale",
    "river_mask", "river_water_level", "river_zone", "temperature", "moisture",
    "region_temperature", "region_moisture", "erosion", "terrain_erosion",
    "weirdness", "water_table", "terrain_region_id", "terrain_region_edge",
    "terrain_region_center_x", "terrain_region_center_z", "biome_region_id",
    "biome_region_edge", "macro_biome_id", "beach_noise",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_fingerprint(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    count = 0
    size = 0
    for item in sorted(value for value in path.rglob("*") if value.is_file()):
        relative = item.relative_to(path).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with item.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        count += 1
    return digest.hexdigest(), count, size


def _git(project: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=project, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=60,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError("cell_scan_provenance_failed", f"git {' '.join(arguments)} failed: {exc}") from exc


def _tracked_status(project: Path) -> bytes:
    return _git(project, "status", "--porcelain=v2", "-z", "--untracked-files=no")


def _int_seed(value: str) -> tuple[int, int]:
    exact = _java_seed(value)
    generator = ((exact + 2**31) % 2**32) - 2**31
    return exact, generator


def _predicate(value: str) -> dict[str, Any]:
    match = PREDICATE.match(value)
    if not match:
        raise InvestigationError(
            "invalid_cell_predicate", "predicate must be FIELD:OP:VALUE"
        )
    field, operator, raw = match.groups()
    try:
        expected: Any = float(raw)
    except ValueError:
        expected = raw
    return {"field": field, "op": operator, "value": expected}


def _read_preset(path: Path) -> tuple[dict, dict]:
    resolved = path.expanduser().resolve()
    if resolved.name == "fixture.toml":
        manifest, _files = load_fixture(resolved)
        return manifest["resolved_preset"], manifest
    if resolved.is_symlink() or not resolved.is_file():
        raise InvestigationError("preset_not_found", f"preset is not a regular file: {resolved}")
    try:
        preset = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvestigationError("invalid_preset", f"preset is not valid JSON: {exc}") from exc
    if not isinstance(preset, dict):
        raise InvestigationError("invalid_preset", "preset JSON root must be an object")
    return preset, {
        "schema_version": 1,
        "id": resolved.stem,
        "classification": "resolved-source",
        "metadata_path": str(resolved),
        "resolved_preset": preset,
        "resolved_preset_sha256": _sha256(resolved),
    }


def _fields(values: list[str], predicates: list[dict], rank_field: str) -> list[str]:
    requested = []
    for value in values:
        requested.extend(item.strip() for item in value.split(",") if item.strip())
    if not requested:
        requested = [
            "height", "height_blocks", "terrain", "terrain_category", "biome_type",
            "continent_edge", "continent_distance", "river_mask", "river_zone",
            "temperature", "moisture", "erosion", "weirdness", "water_table",
            "terrain_region_id", "biome_region_id",
        ]
    for field in [rank_field, *(item["field"] for item in predicates)]:
        if field not in requested:
            requested.append(field)
    return list(dict.fromkeys(requested))


def _tiles(bounds: list[float], factor: int) -> list[dict[str, int]]:
    blocks = (1 << factor) << 4
    minimum_x = int(bounds[0] // blocks)
    minimum_z = int(bounds[1] // blocks)
    maximum_x = int(bounds[2] // blocks)
    maximum_z = int(bounds[3] // blocks)
    values = [
        {"x": x, "z": z}
        for z in range(minimum_z, maximum_z + 1)
        for x in range(minimum_x, maximum_x + 1)
    ]
    if len(values) > 64:
        raise InvestigationError(
            "cell_scan_too_large", f"tile scan selects {len(values)} tiles; maximum is 64"
        )
    return values


def _terminate_group(process: subprocess.Popen, timeout: float = 10.0) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=timeout)


def run_cell_scan(args) -> dict:
    project = resolve_project(args.project)
    validate_loader(project, "fabric")
    if not CELL_SCAN_OVERLAY.is_file():
        raise InvestigationError("cell_scan_missing", f"cell scan overlay is missing: {CELL_SCAN_OVERLAY}")
    if args.tile_size < 1 or args.tile_size > 6:
        raise InvestigationError("invalid_cell_scan", "tile-size must be between 1 and 6")
    if args.sample_step < 1:
        raise InvestigationError("invalid_cell_scan", "sample-step must be positive")
    if args.refine_step < 1 or args.refine_count < 0:
        raise InvestigationError("invalid_cell_scan", "refine-step must be positive and refine-count nonnegative")
    if args.zoom <= 0:
        raise InvestigationError("invalid_cell_scan", "zoom must be positive")

    preset, preset_manifest = _read_preset(args.preset)
    if args.preset_patch:
        if not args.base_preset_sha256 or not args.preset_id or not args.purpose:
            raise InvestigationError(
                "invalid_ephemeral_preset",
                "preset-patch requires base-preset-sha256, preset-id, and purpose",
            )

    predicates = [_predicate(value) for value in args.predicate]
    fields = _fields(args.field, predicates, args.rank_field)
    unknown_fields = sorted(set(fields) - CELL_FIELDS)
    if unknown_fields:
        raise InvestigationError(
            "invalid_cell_scan", f"unknown cell field(s): {', '.join(unknown_fields)}"
        )
    width = (1 << args.tile_size) << 4
    if args.bounds:
        bounds = [float(value) for value in args.bounds]
        if bounds[0] > bounds[2] or bounds[1] > bounds[3]:
            raise InvestigationError("invalid_cell_scan", "bounds minima must not exceed maxima")
        center_x = (bounds[0] + bounds[2]) / 2
        center_z = (bounds[1] + bounds[3]) / 2
        zoom = max((bounds[2] - bounds[0]) / width, (bounds[3] - bounds[1]) / width, 1e-6)
    else:
        center_x, center_z, zoom = float(args.center[0]), float(args.center[1]), args.zoom
        half = width * zoom / 2
        bounds = [center_x - half, center_z - half, center_x + half, center_z + half]
    tiles = _tiles(bounds, args.tile_size) if args.mode == "tile" else []
    exact_seed, generator_seed = _int_seed(args.seed)
    status_before = _tracked_status(project)
    head = _git(project, "rev-parse", "HEAD").decode().strip()
    environment = sourced_environment()

    run_id = new_run_id()
    artifact_dir = RUNS_ROOT / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    request_path = artifact_dir / "cell-scan-request.json"
    result_path = artifact_dir / "cell-scan-result.json"
    preset_path = artifact_dir / "resolved-preset.json"
    manifest_path = artifact_dir / "manifest.json"
    log_path = artifact_dir / "cell-scan.log"
    atomic_write_json(
        manifest_path,
        {
            "ownership": OWNERSHIP,
            "run_id": run_id,
            "artifact_dir": str(artifact_dir),
            "kind": "rtf-cell-scan",
            "project": str(project),
            "head": head,
            "cleanup": {"complete": False, "failures": ["scan did not reach finalization"]},
        },
    )
    if args.preset_patch:
        archive_path = artifact_dir / f"{args.preset_id}.zip"
        preset_manifest = materialize_ephemeral_fixture(
            fixture_id=args.preset_id,
            purpose=args.purpose,
            base_metadata=args.preset,
            expected_base_preset_sha256=args.base_preset_sha256,
            patch_file=args.preset_patch,
            output=archive_path,
        )
        preset = preset_manifest["resolved_preset"]
    atomic_write_json(preset_path, preset)

    request = {
        "schema_version": 1,
        "mode": args.mode,
        "seed": generator_seed,
        "requested_seed": args.seed,
        "exact_seed": exact_seed,
        "preset_path": str(preset_path),
        "tile_size": args.tile_size,
        "batch_count": args.batch_count,
        "center_x": center_x,
        "center_z": center_z,
        "zoom": zoom,
        "bounds": bounds,
        "tiles": tiles,
        "sample_step": args.sample_step,
        "fields": fields,
        "predicates": predicates,
        "rank_field": args.rank_field,
        "ascending": args.ascending,
        "top_k": args.top_k,
        "example_limit": args.example_limit,
        "refine_count": args.refine_count,
        "refine_zoom": args.refine_zoom if args.refine_zoom is not None else max(1.0, zoom / 16.0),
        "refine_step": args.refine_step,
        "exact_tile": args.exact_tile,
        "grid_json": args.grid_json,
        "grid_csv": args.grid_csv,
        "grid_json_path": str(artifact_dir / "cell-grid.json"),
        "grid_csv_path": str(artifact_dir / "cell-grid.csv"),
    }
    if args.heatmap:
        if args.heatmap not in fields:
            fields.append(args.heatmap)
        request["heatmap_field"] = args.heatmap
        request["heatmap_path"] = str(artifact_dir / f"heatmap-{args.heatmap}.png")
    atomic_write_json(request_path, request)

    command = [
        "bash", "./gradlew", ":fabric:squinchCellScan", "--console=plain", "--no-daemon",
        "--init-script", str(CELL_SCAN_OVERLAY),
        f"-PsquinchCellScanHarness={CELL_SCAN_ROOT}",
        f"-PsquinchCellScanRequest={request_path}",
        f"-PsquinchCellScanResult={result_path}",
    ]
    started = time.monotonic()
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command, cwd=project, env=environment, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_group(process)
            raise InvestigationError(
                "cell_scan_timeout", f"standalone cell scan exceeded {args.timeout} seconds",
                details={"run_id": run_id, "artifact_dir": str(artifact_dir), "log_path": str(log_path)},
            ) from exc
    wall_ms = (time.monotonic() - started) * 1000
    status_after = _tracked_status(project)
    if status_after != status_before:
        raise InvestigationError(
            "cell_scan_modified_worktree", "cell scan changed the target's tracked status",
            details={"run_id": run_id, "artifact_dir": str(artifact_dir), "log_path": str(log_path)},
        )
    if return_code != 0 or not result_path.is_file():
        raise InvestigationError(
            "cell_scan_failed", f"standalone cell scan failed with exit code {return_code}",
            details={"run_id": run_id, "artifact_dir": str(artifact_dir), "log_path": str(log_path)},
        )
    result = read_json(result_path)
    result.setdefault("timings", {})["gradle_wall_ms"] = wall_ms
    atomic_write_json(result_path, result)

    classpath = []
    for value in result.get("classpath", []):
        path = Path(value)
        directory_hash = directory_count = directory_size = None
        if path.is_dir():
            directory_hash, directory_count, directory_size = _directory_fingerprint(path)
        classpath.append({
            "path": value,
            "exists": path.exists(),
            "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
            "size": path.stat().st_size if path.is_file() else directory_size,
            "file_count": directory_count,
            "sha256": _sha256(path) if path.is_file() else directory_hash,
        })
    properties = {}
    for line in (project / "gradle.properties").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key.strip()] = value.strip()
    java_home = environment.get("JAVA_HOME")
    java_command = str(Path(java_home) / "bin" / "java") if java_home else "java"
    java_version = subprocess.run(
        [java_command, "-version"], cwd=project, env=environment, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
    ).stdout.decode(errors="replace").strip()
    manifest = {
        "ownership": OWNERSHIP,
        "run_id": run_id,
        "artifact_dir": str(artifact_dir),
        "kind": "rtf-cell-scan",
        "project": str(project),
        "head": head,
        "dirty": bool(status_before),
        "tracked_status_sha256": hashlib.sha256(status_before).hexdigest(),
        "tracked_source_unchanged": True,
        "seed": {"requested": args.seed, "exact": exact_seed, "generator_int": generator_seed},
        "preset": preset_manifest,
        "request": request,
        "command": command,
        "harness": {
            "root": str(CELL_SCAN_ROOT),
            "overlay_sha256": _sha256(CELL_SCAN_OVERLAY),
            "source_files": [
                {"path": str(path), "sha256": _sha256(path), "size": path.stat().st_size}
                for path in sorted((CELL_SCAN_ROOT / "src").rglob("*.java"))
            ],
        },
        "bootstrap": {
            "standalone_only": True,
            "minecraft": "SharedConstants.tryDetectVersion + Bootstrap.bootStrap",
            "registries": "RegistryAccess built-ins + RegistrySetBuilder",
            "rtf_noises": "PresetNoiseData.bootstrap",
            "preview_boundary": "GeneratorContext.makeUncached + generateZoomed(..., false)",
            "tile_boundary": "GeneratorContext.makeUncached + TileGenerator.generate",
        },
        "versions": {
            "minecraft": properties.get("minecraft_version"),
            "rtf": properties.get("mod_version"),
            "java_home": java_home,
            "java": java_version,
        },
        "classpath": classpath,
        "result_path": str(result_path),
        "log_path": str(log_path),
        "cleanup": {"complete": True, "failures": []},
    }
    atomic_write_json(manifest_path, manifest)
    return {
        "run_id": run_id,
        "artifact_dir": str(artifact_dir),
        "manifest_path": str(manifest_path),
        "request_path": str(request_path),
        "result_path": str(result_path),
        "log_path": str(log_path),
        "manifest": manifest,
        "result": result,
    }
