from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .cell_scan import (
    CELL_SCAN_OVERLAY,
    CELL_SCAN_ROOT,
    _directory_fingerprint,
    _git,
    _read_preset,
    _sha256,
    _tracked_status,
)
from .errors import InvestigationError
from .fixtures import FTF_PRESET_PATH
from .owned_operation import run_finite_service
from .paths import RUNS_ROOT, active_path, lock_path, resolve_project, validate_loader
from .server import (
    OWNERSHIP,
    load_owned_active,
    new_run_id,
    sourced_environment,
    uninterruptible_owned_processes,
)
from .state import atomic_write_json

REQUIRED_GENERATED_PATHS = (
    "pack.mcmeta",
    FTF_PRESET_PATH,
    "data/minecraft/dimension_type/overworld.json",
    "data/minecraft/worldgen/noise_settings/overworld.json",
    "data/freeterraforged/tags/worldgen/density_function/additional_noise_router_functions.json",
)

REGISTRY_ROOTS = {
    "configured_features": "data/freeterraforged/worldgen/configured_feature",
    "density_functions": "data/minecraft/worldgen/density_function",
    "noise_modules": "data/freeterraforged/freeterraforged/worldgen/noise",
    "placed_features": "data/freeterraforged/worldgen/placed_feature",
}


def _read_json_object(path: Path, label: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise InvestigationError("preset_fixture_incomplete", f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvestigationError(
            "preset_fixture_incomplete", f"{label} is invalid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise InvestigationError("preset_fixture_incomplete", f"{label} is not a JSON object")
    return value


def _validate_derived_registries(output: Path, preset: dict) -> dict:
    properties = preset["world"]["properties"]
    world_height = int(properties["worldHeight"])
    world_depth = int(properties.get("worldDepth", 64))
    sea_level = int(properties["seaLevel"])
    total_height = world_height + world_depth
    dimension = _read_json_object(
        output / "data/minecraft/dimension_type/overworld.json", "dimension type"
    )
    noise_settings = _read_json_object(
        output / "data/minecraft/worldgen/noise_settings/overworld.json", "noise settings"
    )
    noise_shape = noise_settings.get("noise")
    expected_dimension = {
        "min_y": -world_depth,
        "height": total_height,
        "logical_height": total_height,
    }
    expected_noise = {
        "min_y": -world_depth,
        "height": total_height,
        "size_horizontal": 1,
        "size_vertical": 2,
    }
    actual_dimension = {key: dimension.get(key) for key in expected_dimension}
    if actual_dimension != expected_dimension:
        raise InvestigationError(
            "preset_fixture_mismatch",
            f"dimension type disagrees with preset: {actual_dimension} != {expected_dimension}",
        )
    if noise_shape != expected_noise or noise_settings.get("sea_level") != sea_level:
        raise InvestigationError(
            "preset_fixture_mismatch", "noise settings disagree with preset dimensions or sea level"
        )
    expected_ore_veins = bool(preset["caves"]["largeOreVeins"])
    if noise_settings.get("ore_veins_enabled") is not expected_ore_veins:
        raise InvestigationError(
            "preset_fixture_mismatch", "noise settings disagree with preset ore-vein policy"
        )
    depth = _read_json_object(
        output / "data/minecraft/worldgen/density_function/overworld/depth.json",
        "depth density function",
    )
    gradient = depth.get("argument1", {})
    expected_gradient = {
        "from_y": -world_depth,
        "to_y": world_height,
        "from_value": 1.0 + world_depth / 128.0,
        "to_value": 1.0 - world_height / 128.0,
    }
    actual_gradient = {key: gradient.get(key) for key in expected_gradient}
    if actual_gradient != expected_gradient:
        raise InvestigationError(
            "preset_fixture_mismatch",
            f"depth density function disagrees with preset: {actual_gradient} != {expected_gradient}",
        )
    counts = {
        name: sum(1 for path in (output / relative).rglob("*.json") if path.is_file())
        for name, relative in REGISTRY_ROOTS.items()
    }
    if any(count == 0 for count in counts.values()):
        raise InvestigationError(
            "preset_fixture_incomplete", f"generated fixture has empty required registries: {counts}"
        )
    return {
        "dimension": expected_dimension,
        "noise": expected_noise,
        "sea_level": sea_level,
        "ore_veins_enabled": expected_ore_veins,
        "depth_gradient": expected_gradient,
        "registry_counts": counts,
    }


def _inspect_generated_fixture(output: Path, canonical_preset_path: Path) -> dict:
    if output.is_symlink() or not output.is_dir():
        raise InvestigationError(
            "preset_fixture_failed", f"generator did not create a source directory: {output}"
        )
    files = sorted(path for path in output.rglob("*") if path.is_file())
    symlinks = sorted(path for path in output.rglob("*") if path.is_symlink())
    if symlinks:
        raise InvestigationError(
            "preset_fixture_failed",
            f"generated fixture contains symlinks: {[str(path) for path in symlinks]}",
        )
    missing = [relative for relative in REQUIRED_GENERATED_PATHS if not (output / relative).is_file()]
    if missing:
        raise InvestigationError(
            "preset_fixture_incomplete", f"generated fixture is missing: {missing}"
        )
    preset_path = output / FTF_PRESET_PATH
    generated_preset = _read_json_object(preset_path, "generated preset")
    canonical_preset = _read_json_object(canonical_preset_path, "canonical preset")
    if generated_preset != canonical_preset:
        raise InvestigationError(
            "preset_fixture_mismatch", "generated preset does not equal the requested preset"
        )
    derived = _validate_derived_registries(output, generated_preset)
    content_sha256, file_count, size = _directory_fingerprint(output)
    return {
        "path": str(output),
        "content_sha256": content_sha256,
        "file_count": file_count,
        "size": size,
        "derived": derived,
        "density_function_count": derived["registry_counts"]["density_functions"],
        "canonical_preset_sha256": _sha256(canonical_preset_path),
        "resolved_preset_sha256": _sha256(preset_path),
        "required_paths": list(REQUIRED_GENERATED_PATHS),
        "files": [path.relative_to(output).as_posix() for path in files],
    }


def generate_preset_fixture(
    *, project_value: str | Path, preset: Path, timeout: float
) -> dict:
    project = resolve_project(project_value)
    validate_loader(project, "fabric")
    if timeout <= 0:
        raise InvestigationError("invalid_preset_fixture", "timeout must be positive")
    if not CELL_SCAN_OVERLAY.is_file():
        raise InvestigationError(
            "preset_fixture_missing", f"standalone overlay is missing: {CELL_SCAN_OVERLAY}"
        )

    preset, preset_manifest = _read_preset(preset)

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
    preset_path = artifact_dir / "resolved-preset.json"
    canonical_preset_path = artifact_dir / "canonical-preset.json"
    output_path = artifact_dir / "generated-fixture"
    log_path = artifact_dir / "preset-fixture.log"
    manifest_path = artifact_dir / "manifest.json"
    command = [
        "bash", "./gradlew", ":fabric:squinchPresetFixture", "--console=plain", "--no-daemon",
        "--init-script", str(CELL_SCAN_OVERLAY),
        f"-PsquinchCellScanHarness={CELL_SCAN_ROOT}",
        f"-PsquinchFixturePreset={preset_path}",
        f"-PsquinchFixtureCanonicalPreset={canonical_preset_path}",
        f"-PsquinchFixtureOutput={output_path}",
    ]
    started = time.monotonic()

    def prepare() -> None:
        atomic_write_json(preset_path, preset)

    def validate(_state: dict) -> dict:
        if _tracked_status(project) != status_before:
            raise InvestigationError(
                "preset_fixture_modified_worktree",
                "preset fixture generation changed the target's tracked status",
            )
        return _inspect_generated_fixture(output_path, canonical_preset_path)

    state, generated = run_finite_service(
        project=project,
        loader="fabric",
        operation="preset-fixture",
        ownership=OWNERSHIP,
        run_id=run_id,
        artifact_dir=artifact_dir,
        run_dir=artifact_dir,
        log_path=log_path,
        active_path=active,
        lock_path=lock_path(project, "fabric"),
        command=command,
        environment=environment,
        timeout=timeout,
        load_active=load_owned_active,
        prepare=prepare,
        validate=validate,
        state_fields={
            "preset_path": str(preset_path),
            "canonical_preset_path": str(canonical_preset_path),
            "output_path": str(output_path),
        },
    )
    generated["gradle_wall_ms"] = (time.monotonic() - started) * 1000
    manifest = {
        "ownership": OWNERSHIP,
        "schema_version": 1,
        "run_id": run_id,
        "kind": "ftf-preset-fixture",
        "artifact_dir": str(artifact_dir),
        "project": str(project),
        "head": head,
        "dirty": bool(status_before),
        "tracked_status_sha256": hashlib.sha256(status_before).hexdigest(),
        "tracked_source_unchanged": True,
        "preset": preset_manifest,
        "generated": generated,
        "command": command,
        "harness": {
            "root": str(CELL_SCAN_ROOT),
            "overlay_sha256": _sha256(CELL_SCAN_OVERLAY),
            "source_files": [
                {"path": str(path), "sha256": _sha256(path), "size": path.stat().st_size}
                for path in sorted((CELL_SCAN_ROOT / "src").rglob("*.java"))
            ],
        },
        "process_service": state["service"],
        "owned_processes": state["owned_processes"],
        "started_at": state["started_at"],
        "finished_at": state["finished_at"],
        "log_path": str(log_path),
        "cleanup": state["cleanup"],
    }
    atomic_write_json(manifest_path, manifest)
    return {
        "run_id": run_id,
        "artifact_dir": str(artifact_dir),
        "manifest_path": str(manifest_path),
        "preset_path": str(preset_path),
        "canonical_preset_path": str(canonical_preset_path),
        "output_path": str(output_path),
        "log_path": str(log_path),
        "manifest": manifest,
    }


def run_preset_fixture(args) -> dict:
    return generate_preset_fixture(
        project_value=args.project,
        preset=args.preset,
        timeout=args.timeout,
    )
