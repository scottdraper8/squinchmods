from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .errors import InvestigationError
from .fixtures import load_fixture
from .owned_operation import (
    recover_finite_service,
    run_finite_service,
)
from .paths import (
    MINECRAFT_DIR,
    RUNS_ROOT,
    active_path,
    lock_path,
    resolve_project,
    validate_loader,
)
from .scenario import _java_seed
from .server import (
    OWNERSHIP,
    load_owned_active,
    new_run_id,
    sourced_environment,
    uninterruptible_owned_processes,
)
from .state import atomic_write_json, read_json

CELL_SCAN_ROOT = MINECRAFT_DIR / "investigations" / "freeterraforged" / "cell-scan"
CELL_SCAN_OVERLAY = CELL_SCAN_ROOT / "gradle" / "cell-scan.gradle"
PREDICATE = re.compile(r"^([^:]+):(>=|<=|==|!=|>|<):(.+)$")
CELL_FIELDS = {
    "height", "height_blocks", "height_erosion", "sediment", "gradient",
    "terrain", "terrain_category", "continent_id", "continent_edge",
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
            ["git", *arguments], cwd=project, check=True, capture_output=True, timeout=60,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError("cell_scan_provenance_failed", f"git {' '.join(arguments)} failed: {exc}") from exc


def _tracked_status(project: Path) -> bytes:
    return _git(project, "status", "--porcelain=v2", "-z", "--untracked-files=no")


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
        manifest = load_fixture(resolved)
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
            "height", "height_blocks", "terrain", "terrain_category",
            "continent_edge", "continent_distance", "river_mask", "river_zone",
            "temperature", "moisture", "erosion", "weirdness", "water_table",
            "terrain_region_id", "biome_region_id",
        ]
    for field in [rank_field, *(item["field"] for item in predicates)]:
        if field not in requested:
            requested.append(field)
    return list(dict.fromkeys(requested))


def _validate_result(result: dict, request: dict) -> None:
    scan = result.get("scan")
    timings = result.get("timings")
    artifacts = result.get("artifacts")
    classpath = result.get("classpath")
    digest = result.get("deterministic_sha256")
    if (
        result.get("mode") != request["mode"]
        or result.get("authority") not in {"prediction", "ftf-horizontal-cell-model"}
        or result.get("cold_warm_equal") is not True
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or not isinstance(scan, dict)
        or not isinstance(scan.get("inspected"), int)
        or scan["inspected"] <= 0
        or not isinstance(timings, dict)
        or not isinstance(artifacts, list)
        or not all(isinstance(path, str) for path in artifacts)
        or not isinstance(classpath, list)
        or not all(isinstance(path, str) for path in classpath)
    ):
        raise InvestigationError(
            "cell_scan_result_invalid", "standalone cell scan wrote an invalid result"
        )


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
    exact_seed = _java_seed(args.seed)
    active = active_path(project, "fabric")
    blocked = uninterruptible_owned_processes(active.parent)
    if blocked:
        raise InvestigationError(
            "host_degraded",
            "refusing to launch while an investigation-owned process is in uninterruptible sleep",
            details={"processes": blocked},
        )
    status_before = _tracked_status(project)
    head = _git(project, "rev-parse", "HEAD").decode().strip()
    environment = sourced_environment()

    run_id = new_run_id()
    artifact_dir = RUNS_ROOT / run_id
    request_path = artifact_dir / "cell-scan-request.json"
    result_path = artifact_dir / "cell-scan-result.json"
    preset_path = artifact_dir / "resolved-preset.json"
    manifest_path = artifact_dir / "manifest.json"
    log_path = artifact_dir / "cell-scan.log"
    request = {
        "schema_version": 1,
        "mode": args.mode,
        "seed": exact_seed,
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

    def prepare() -> None:
        atomic_write_json(preset_path, preset)
        atomic_write_json(request_path, request)

    command = [
        "bash", "./gradlew", ":fabric:squinchCellScan", "--console=plain", "--no-daemon",
        "--init-script", str(CELL_SCAN_OVERLAY),
        f"-PsquinchCellScanHarness={CELL_SCAN_ROOT}",
        f"-PsquinchCellScanRequest={request_path}",
        f"-PsquinchCellScanResult={result_path}",
    ]
    started = time.monotonic()
    def validate(_state: dict) -> dict:
        wall_ms = (time.monotonic() - started) * 1000
        status_after = _tracked_status(project)
        if status_after != status_before:
            raise InvestigationError(
                "cell_scan_modified_worktree",
                "cell scan changed the target's tracked status",
            )
        if not result_path.is_file():
            raise InvestigationError(
                "cell_scan_failed", "standalone cell scan did not write its result"
            )
        result = read_json(result_path)
        _validate_result(result, request)
        result.setdefault("timings", {})["gradle_wall_ms"] = wall_ms
        atomic_write_json(result_path, result)
        return {"result": result, "status_after": status_after, "wall_ms": wall_ms}

    state, validated = run_finite_service(
        project=project,
        loader="fabric",
        operation="cell-scan",
        ownership=OWNERSHIP,
        run_id=run_id,
        artifact_dir=artifact_dir,
        run_dir=artifact_dir,
        log_path=log_path,
        active_path=active,
        lock_path=lock_path(project, "fabric"),
        command=command,
        environment=environment,
        timeout=args.timeout,
        load_active=load_owned_active,
        prepare=prepare,
        validate=validate,
    )
    result = validated["result"]

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
    manifest = {
        "ownership": OWNERSHIP,
        "run_id": run_id,
        "artifact_dir": str(artifact_dir),
        "kind": "ftf-cell-scan",
        "project": str(project),
        "head": head,
        "dirty": bool(status_before),
        "tracked_status_sha256": hashlib.sha256(status_before).hexdigest(),
        "tracked_source_unchanged": True,
        "seed": {"requested": args.seed, "exact": exact_seed},
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
            "ftf_noises": "PresetNoiseData.bootstrap",
            "preview_boundary": "GeneratorContext.makeUncached + generateZoomed(..., false)",
            "tile_boundary": "GeneratorContext.makeUncached + TileGenerator.generate",
        },
        "versions": {
            "minecraft": properties.get("minecraft_version"),
            "ftf": properties.get("mod_version"),
            "java_home": java_home,
            "java": result.get("java_version"),
            "java_vendor": result.get("java_vendor"),
        },
        "classpath": classpath,
        "result_path": str(result_path),
        "log_path": str(log_path),
        "process_service": state["service"],
        "owned_processes": state["owned_processes"],
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


def recover_standalone(project: Path, loader: str, timeout: float) -> dict:
    return recover_finite_service(
        project=project,
        loader=loader,
        timeout=timeout,
        lock_path=lock_path(project, loader),
        load_active=load_owned_active,
        operations={"cell-scan", "preset-fixture"},
    )
