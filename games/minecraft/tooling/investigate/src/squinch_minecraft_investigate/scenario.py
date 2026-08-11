from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import shutil
import statistics
import struct
import subprocess
import time
import tomllib
import uuid
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .catalog import resolve_artifacts
from .errors import CleanupError, InvestigationError
from .generation import generate_regions
from .fixtures import load_fixture, materialize_ephemeral_fixture, materialize_fixture
from .output import timestamp
from .paths import REPOSITORY_ROOT, STATE_ROOT
from .probe_requests import submit_probe
from .profiling import start_jfr, stop_jfr
from .processes import identity_matches
from .server import (
    persist_active,
    run_commands,
    sourced_environment,
    start_server,
    stop_server,
)
from .state import atomic_write_json, read_json

SCENARIO_VERSION = 1
STEP_TYPES = {"command", "generate", "probe"}
RETENTIONS = {"discard", "keep-on-failure", "keep"}
FATAL_LOG_PATTERNS = (
    re.compile(r"---- Minecraft Crash Report ----", re.IGNORECASE),
    re.compile(r"Exception in server tick loop", re.IGNORECASE),
    re.compile(r"Failed to start the minecraft server", re.IGNORECASE),
    re.compile(r"\[Server thread/ERROR\]"),
)


@dataclass(frozen=True)
class ProbeSelection:
    probe_id: str
    version: str
    config: dict[str, Any]


@dataclass(frozen=True)
class RTFEphemeralPreset:
    fixture_id: str
    purpose: str
    base_fixture: Path
    base_preset_sha256: str
    patch_file: Path


@dataclass(frozen=True)
class ScenarioStep:
    step_id: str
    kind: str
    timeout: float
    values: dict[str, Any]
    expect: dict[str, Any]


@dataclass(frozen=True)
class Scenario:
    path: Path
    name: str
    project: Path
    loader: str
    seed: str
    rtf_fixture: Path | None
    rtf_ephemeral: RTFEphemeralPreset | None
    datapacks: tuple[Path, ...]
    companion_artifacts: tuple[str, ...]
    probe_packs: tuple[Path, ...]
    server_properties: dict[str, str]
    retention: str
    startup_timeout: float
    shutdown_timeout: float
    step_timeout: float
    probes: dict[str, ProbeSelection]
    steps: tuple[ScenarioStep, ...]
    expectations: dict[str, Any]


def _error(message: str) -> InvestigationError:
    return InvestigationError("invalid_scenario", message)


def _known_keys(value: dict, allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(f"unknown {context} key(s): {', '.join(unknown)}")


def _number(value: Any, context: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{context} must be a number")
    result = float(value)
    if positive and result <= 0:
        raise _error(f"{context} must be positive")
    return result


def _repository_path(value: Any, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise _error(f"{context} must be a nonempty repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("games",):
        raise _error(f"{context} must use a repository-root-relative path")
    resolved = (REPOSITORY_ROOT / path).resolve()
    if not resolved.is_relative_to(REPOSITORY_ROOT):
        raise _error(f"{context} escapes the repository root")
    return resolved


def _scenario_path(_scenario_file: Path, value: Any, context: str) -> Path:
    return _repository_path(value, context)


def _json_object(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _error(f"{context} must be a table")
    # TOML values are JSON-compatible for the supported scenario surface.
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise _error(f"{context} is not JSON-serializable: {exc}") from exc


def load_scenario(path: str | Path) -> Scenario:
    scenario_path = Path(path).expanduser().resolve()
    if not scenario_path.is_file():
        raise InvestigationError(
            "scenario_not_found", f"scenario file does not exist: {scenario_path}"
        )
    try:
        raw = tomllib.loads(scenario_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _error(f"invalid TOML in {scenario_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise _error("scenario root must be a table")
    _known_keys(
        raw,
        {
            "schema_version",
            "name",
            "project",
            "loader",
            "seed",
            "rtf_fixture",
            "rtf_ephemeral",
            "datapacks",
            "companion_artifacts",
            "probe_packs",
            "retention",
            "server_properties",
            "timeouts",
            "expectations",
            "probes",
            "steps",
        },
        "top-level",
    )
    if raw.get("schema_version") != SCENARIO_VERSION:
        raise _error(f"schema_version must be {SCENARIO_VERSION}")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _error("name must be a nonempty string")
    project = _scenario_path(scenario_path, raw.get("project"), "project")
    loader = raw.get("loader")
    if loader not in {"fabric", "forge", "neoforge", "quilt"}:
        raise _error(f"unsupported loader: {loader!r}")
    seed_value = raw.get("seed")
    if isinstance(seed_value, bool) or not isinstance(seed_value, (str, int)):
        raise _error("seed must be an exact string or integer")
    seed = str(seed_value)
    if not seed:
        raise _error("seed cannot be empty or random")

    rtf_fixture = None
    if "rtf_fixture" in raw:
        rtf_fixture = _scenario_path(scenario_path, raw["rtf_fixture"], "rtf_fixture")
    rtf_ephemeral = None
    if "rtf_ephemeral" in raw:
        if rtf_fixture is not None:
            raise _error("rtf_fixture and rtf_ephemeral are mutually exclusive")
        value = raw["rtf_ephemeral"]
        if not isinstance(value, dict):
            raise _error("rtf_ephemeral must be a table")
        _known_keys(
            value,
            {"id", "purpose", "base_fixture", "base_preset_sha256", "patch_file"},
            "rtf_ephemeral",
        )
        missing = sorted(
            {"id", "purpose", "base_fixture", "base_preset_sha256", "patch_file"}
            - set(value)
        )
        if missing:
            raise _error(f"rtf_ephemeral is missing: {', '.join(missing)}")
        fixture_id = value["id"]
        purpose = value["purpose"]
        base_hash = value["base_preset_sha256"]
        if (
            not isinstance(fixture_id, str)
            or not fixture_id
            or Path(fixture_id).name != fixture_id
        ):
            raise _error("rtf_ephemeral.id must be a nonempty path-safe string")
        if not isinstance(purpose, str) or not purpose:
            raise _error("rtf_ephemeral.purpose must be a nonempty string")
        if (
            not isinstance(base_hash, str)
            or len(base_hash) != 64
            or any(character not in "0123456789abcdef" for character in base_hash)
        ):
            raise _error("rtf_ephemeral.base_preset_sha256 must be a lowercase SHA-256")
        rtf_ephemeral = RTFEphemeralPreset(
            fixture_id,
            purpose,
            _scenario_path(scenario_path, value["base_fixture"], "rtf_ephemeral.base_fixture"),
            base_hash,
            _scenario_path(scenario_path, value["patch_file"], "rtf_ephemeral.patch_file"),
        )

    datapack_values = raw.get("datapacks", [])
    if not isinstance(datapack_values, list):
        raise _error("datapacks must be an array of paths")
    datapacks = tuple(
        _scenario_path(scenario_path, value, f"datapacks[{index}]")
        for index, value in enumerate(datapack_values)
    )
    companion_artifact_values = raw.get("companion_artifacts", [])
    if not isinstance(companion_artifact_values, list) or any(
        not isinstance(value, str) or not value or Path(value).name != value
        for value in companion_artifact_values
    ):
        raise _error("companion_artifacts must be an array of catalog artifact IDs")
    companion_artifacts = tuple(companion_artifact_values)
    probe_pack_values = raw.get("probe_packs", [])
    if not isinstance(probe_pack_values, list):
        raise _error("probe_packs must be an array of paths")
    probe_packs = tuple(
        _scenario_path(scenario_path, value, f"probe_packs[{index}]")
        for index, value in enumerate(probe_pack_values)
    )
    server_properties_raw = raw.get("server_properties", {})
    if not isinstance(server_properties_raw, dict):
        raise _error("server_properties must be a table")
    server_properties: dict[str, str] = {}
    for key, value in server_properties_raw.items():
        if not isinstance(key, str) or isinstance(value, (dict, list)):
            raise _error("server_properties values must be scalar")
        if isinstance(value, bool):
            server_properties[key] = str(value).lower()
        else:
            server_properties[key] = str(value)

    retention = raw.get("retention", "discard")
    if retention not in RETENTIONS:
        raise _error(f"retention must be one of {sorted(RETENTIONS)}")
    timeouts = raw.get("timeouts", {})
    if not isinstance(timeouts, dict):
        raise _error("timeouts must be a table")
    _known_keys(timeouts, {"startup", "shutdown", "step"}, "timeouts")
    startup_timeout = _number(timeouts.get("startup", 180), "timeouts.startup")
    shutdown_timeout = _number(timeouts.get("shutdown", 60), "timeouts.shutdown")
    step_timeout = _number(timeouts.get("step", 600), "timeouts.step")

    probes_raw = raw.get("probes", [])
    if not isinstance(probes_raw, list):
        raise _error("probes must be an array of tables")
    probes: dict[str, ProbeSelection] = {}
    for index, probe in enumerate(probes_raw):
        if not isinstance(probe, dict):
            raise _error(f"probes[{index}] must be a table")
        _known_keys(probe, {"id", "version", "config", "config_file"}, f"probes[{index}]")
        probe_id, version = probe.get("id"), probe.get("version")
        if not isinstance(probe_id, str) or not probe_id:
            raise _error(f"probes[{index}].id must be a nonempty string")
        if not isinstance(version, str) or not version:
            raise _error(f"probes[{index}].version must be a nonempty string")
        if probe_id in probes:
            raise _error(f"duplicate selected probe ID: {probe_id}")
        if "config" in probe and "config_file" in probe:
            raise _error(f"probes[{index}] cannot set both config and config_file")
        if "config_file" in probe:
            config_path = _scenario_path(scenario_path, probe["config_file"], "probe config_file")
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise _error(f"cannot read probe config {config_path}: {exc}") from exc
            if not isinstance(config, dict):
                raise _error(f"probe config must be a JSON object: {config_path}")
        else:
            config = _json_object(probe.get("config"), f"probes[{index}].config")
        probes[probe_id] = ProbeSelection(probe_id, version, config)

    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise _error("steps must be a nonempty array of tables")
    steps: list[ScenarioStep] = []
    seen_steps: set[str] = set()
    common = {"id", "type", "timeout", "expect", "jfr"}
    kind_keys = {
        "command": {"command", "commands"},
        "generate": {
            "unit", "bounds", "candidate_file", "candidate_limit",
            "authority", "terminal_probe", "repeat", "offset",
        },
        "probe": {"probe"},
    }
    for index, step in enumerate(steps_raw):
        if not isinstance(step, dict):
            raise _error(f"steps[{index}] must be a table")
        kind = step.get("type")
        if kind not in STEP_TYPES:
            raise _error(f"steps[{index}].type must be one of {sorted(STEP_TYPES)}")
        _known_keys(step, common | kind_keys[kind], f"steps[{index}]")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id:
            raise _error(f"steps[{index}].id must be a nonempty string")
        if step_id in seen_steps:
            raise _error(f"duplicate step ID: {step_id}")
        seen_steps.add(step_id)
        timeout = _number(step.get("timeout", step_timeout), f"steps[{index}].timeout")
        expect = _json_object(step.get("expect"), f"steps[{index}].expect")
        jfr = step.get("jfr", False)
        if not isinstance(jfr, bool):
            raise _error(f"steps[{index}].jfr must be true or false")
        values = {key: value for key, value in step.items() if key not in common}
        if kind == "command":
            if ("command" in values) == ("commands" in values):
                raise _error(f"steps[{index}] must set exactly one of command or commands")
            commands = values.get("commands", [values.get("command")])
            if not isinstance(commands, list) or not commands or any(
                not isinstance(item, str) or not item for item in commands
            ):
                raise _error(f"steps[{index}] commands must be nonempty strings")
            values = {"commands": commands}
        elif kind == "generate":
            if values.get("unit") not in {"block", "chunk"}:
                raise _error(f"steps[{index}].unit must be block or chunk")
            if ("bounds" in values) == ("candidate_file" in values):
                raise _error(
                    f"steps[{index}] must set exactly one of bounds or candidate_file"
                )
            bounds = values.get("bounds")
            candidate_file = None
            candidate_limit = None
            if bounds is not None:
                if (
                    not isinstance(bounds, list)
                    or len(bounds) != 4
                    or any(isinstance(item, bool) or not isinstance(item, int) for item in bounds)
                ):
                    raise _error(f"steps[{index}].bounds must contain four integers")
                if "candidate_limit" in values:
                    raise _error(f"steps[{index}].candidate_limit requires candidate_file")
            else:
                if values["unit"] != "block":
                    raise _error(f"steps[{index}] candidate_file generation uses block coordinates")
                candidate_file = _scenario_path(
                    scenario_path, values["candidate_file"], f"steps[{index}].candidate_file"
                )
                candidate_limit = values.get("candidate_limit", 4)
                if (
                    isinstance(candidate_limit, bool)
                    or not isinstance(candidate_limit, int)
                    or candidate_limit < 1
                    or candidate_limit > 64
                ):
                    raise _error(f"steps[{index}].candidate_limit must be 1..64")
            authority = values.get("authority", "generation")
            if authority not in {"generation", "finished-chunk"}:
                raise _error(f"steps[{index}].authority must be generation or finished-chunk")
            terminal_probe = values.get("terminal_probe")
            if authority == "finished-chunk" and terminal_probe not in probes:
                raise _error(
                    f"steps[{index}] finished-chunk authority requires a selected terminal_probe"
                )
            repeat = values.get("repeat", 1)
            if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 20:
                raise _error(f"steps[{index}].repeat must be 1..20")
            offset = values.get("offset")
            if offset is not None and (
                not isinstance(offset, list)
                or len(offset) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in offset)
            ):
                raise _error(f"steps[{index}].offset must contain two integers")
            if repeat > 1:
                if bounds is None or offset is None or offset == [0, 0]:
                    raise _error(
                        f"steps[{index}] repeated generation requires bounds and a nonzero offset"
                    )
                width = bounds[2] - bounds[0] + 1
                depth = bounds[3] - bounds[1] + 1
                if width < 1 or depth < 1:
                    raise _error(f"steps[{index}].bounds are inverted")
                if abs(offset[0]) < width and abs(offset[1]) < depth:
                    raise _error(f"steps[{index}].offset produces overlapping windows")
            values = {
                "unit": values["unit"],
                "bounds": bounds,
                "candidate_file": candidate_file,
                "candidate_limit": candidate_limit,
                "authority": authority,
                "terminal_probe": terminal_probe,
                "repeat": repeat,
                "offset": offset,
            }
        else:
            probe_id = values.get("probe")
            if probe_id not in probes:
                raise _error(f"steps[{index}] references unselected probe {probe_id!r}")
            values = {"probe": probe_id}
        values["jfr"] = jfr
        steps.append(ScenarioStep(step_id, kind, timeout, values, expect))

    expectations = _json_object(raw.get("expectations"), "expectations")
    _known_keys(expectations, {"required_mods"}, "expectations")
    required_mods = expectations.get("required_mods", [])
    if not isinstance(required_mods, list) or any(
        not isinstance(item, str) or not item for item in required_mods
    ):
        raise _error("expectations.required_mods must be an array of mod IDs")
    expectations = {"required_mods": required_mods}
    return Scenario(
        scenario_path,
        name,
        project,
        loader,
        seed,
        rtf_fixture,
        rtf_ephemeral,
        datapacks,
        companion_artifacts,
        probe_packs,
        server_properties,
        retention,
        startup_timeout,
        shutdown_timeout,
        step_timeout,
        probes,
        tuple(steps),
        expectations,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_coordinates(path: Path, limit: int) -> list[dict[str, int]]:
    try:
        value = read_json(path)
    except InvestigationError:
        raise
    scan = value.get("scan")
    if not isinstance(scan, dict):
        data = value.get("data")
        result = data.get("result") if isinstance(data, dict) else None
        scan = result.get("scan") if isinstance(result, dict) else None
    candidates = scan.get("top_candidates") if isinstance(scan, dict) else None
    if not isinstance(candidates, list):
        raise _error(f"candidate file lacks scan.top_candidates: {path}")
    selected: list[dict[str, int]] = []
    seen_chunks: set[tuple[int, int]] = set()
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise _error(f"candidate {index} is not an object: {path}")
        x, z = item.get("x"), item.get("z")
        if (
            isinstance(x, bool) or not isinstance(x, (int, float))
            or isinstance(z, bool) or not isinstance(z, (int, float))
            or not math.isfinite(float(x)) or not math.isfinite(float(z))
        ):
            raise _error(f"candidate {index} lacks finite x/z coordinates: {path}")
        block_x, block_z = math.floor(x), math.floor(z)
        chunk = (block_x // 16, block_z // 16)
        if chunk in seen_chunks:
            continue
        seen_chunks.add(chunk)
        selected.append(
            {"block_x": block_x, "block_z": block_z, "chunk_x": chunk[0], "chunk_z": chunk[1]}
        )
        if len(selected) == limit:
            break
    if not selected:
        raise _error(f"candidate file contains no usable unique chunks: {path}")
    return selected


def _run_capture(command: list[str], *, cwd: Path, environment: dict[str, str]) -> bytes:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError(
            "provenance_failed", f"failed to fingerprint {' '.join(command)}: {exc}"
        ) from exc


def capture_provenance(
    scenario: Scenario, environment: dict[str, str]
) -> tuple[dict[str, Any], bytes]:
    project = scenario.project
    head = _run_capture(["git", "rev-parse", "HEAD"], cwd=project, environment=environment).decode().strip()
    status = _run_capture(
        ["git", "status", "--porcelain=v1", "-z"], cwd=project, environment=environment
    )
    patch = _run_capture(
        ["git", "diff", "--binary", "HEAD", "--"], cwd=project, environment=environment
    )
    untracked_raw = _run_capture(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=project,
        environment=environment,
    )
    untracked = []
    for raw_path in filter(None, untracked_raw.decode(errors="surrogateescape").split("\0")):
        path = project / raw_path
        if path.is_file() and not path.is_symlink():
            untracked.append({"path": raw_path, "sha256": _sha256(path), "size": path.stat().st_size})
    java_home = environment.get("JAVA_HOME")
    java = Path(java_home) / "bin" / "java" if java_home else Path("java")
    java_version = _run_capture([str(java), "-version"], cwd=project, environment=environment).decode(
        errors="replace"
    ).strip()
    tracked_inputs = []
    gradle_jvm_arguments = None
    for relative in (
        "gradlew",
        "gradle.properties",
        "settings.gradle",
        "settings.gradle.kts",
        "build.gradle",
        "build.gradle.kts",
        "gradle/wrapper/gradle-wrapper.properties",
        "gradle/wrapper/gradle-wrapper.jar",
        f"{scenario.loader}/build.gradle",
        f"{scenario.loader}/build.gradle.kts",
    ):
        path = project / relative
        if path.is_file():
            tracked_inputs.append(
                {"path": relative, "sha256": _sha256(path), "size": path.stat().st_size}
            )
            if relative == "gradle.properties":
                match = re.search(r"^org\.gradle\.jvmargs=(.*)$", path.read_text(), re.MULTILINE)
                gradle_jvm_arguments = match.group(1).strip() if match else None
    wrapper_properties = project / "gradle/wrapper/gradle-wrapper.properties"
    distribution = None
    if wrapper_properties.is_file():
        match = re.search(r"^distributionUrl=(.+)$", wrapper_properties.read_text(), re.MULTILINE)
        distribution = match.group(1).strip() if match else None
    missing = [str(path) for path in scenario.datapacks if not path.is_file()]
    if missing:
        raise InvestigationError("datapack_not_found", f"datapack not found: {missing[0]}")
    missing_candidates = [
        str(step.values["candidate_file"])
        for step in scenario.steps
        if step.kind == "generate"
        and step.values.get("candidate_file") is not None
        and not step.values["candidate_file"].is_file()
    ]
    if missing_candidates:
        raise InvestigationError(
            "candidate_file_not_found", f"candidate file not found: {missing_candidates[0]}"
        )
    datapacks = []
    resolved_rtf_presets = 0
    rtf_preset_path = "data/reterraforged/reterraforged/worldgen/preset/preset.json"
    for path in scenario.datapacks:
        item: dict[str, Any] = {
            "path": str(path),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }
        try:
            with zipfile.ZipFile(path) as archive:
                if rtf_preset_path in archive.namelist():
                    raw_preset = archive.read(rtf_preset_path)
                    resolved = json.loads(raw_preset)
                    if not isinstance(resolved, dict):
                        raise ValueError("resolved preset is not an object")
                    item["resolved_rtf_preset"] = resolved
                    item["resolved_rtf_preset_sha256"] = hashlib.sha256(raw_preset).hexdigest()
                    resolved_rtf_presets += 1
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
            raise InvestigationError(
                "invalid_datapack", f"cannot inspect datapack {path}: {exc}"
            ) from exc
        datapacks.append(item)
    if resolved_rtf_presets > 1:
        raise InvestigationError(
            "ambiguous_rtf_preset",
            "multiple datapacks define the authoritative RTF preset registry entry",
        )
    provenance = {
        "scenario": {
            "path": str(scenario.path),
            "sha256": _sha256(scenario.path),
            "schema_version": SCENARIO_VERSION,
        },
        "code": {
            "project": str(project),
            "head": head,
            "dirty": bool(status),
            "status_sha256": hashlib.sha256(status).hexdigest(),
            "dirty_patch_sha256": hashlib.sha256(patch).hexdigest(),
            "untracked": untracked,
        },
        "datapacks": datapacks,
        "candidate_inputs": [
            {
                "step_id": step.step_id,
                "path": str(step.values["candidate_file"]),
                "sha256": _sha256(step.values["candidate_file"]),
                "size": step.values["candidate_file"].stat().st_size,
            }
            for step in scenario.steps
            if step.kind == "generate" and step.values.get("candidate_file") is not None
        ],
        "java": {"home": java_home, "version": java_version},
        "gradle": {
            "distribution": distribution,
            "jvm_arguments": gradle_jvm_arguments,
            "inputs": tracked_inputs,
        },
        "loader": scenario.loader,
        "jvm_arguments": {
            key: environment.get(key)
            for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "GRADLE_OPTS")
            if environment.get(key) is not None
        },
        "launch_command": [
            "bash",
            "./gradlew",
            f":{scenario.loader}:runServer",
            "--console=plain",
            "--no-daemon",
        ],
        "probes": [
            {
                "id": selected.probe_id,
                "version": selected.version,
                "config_sha256": hashlib.sha256(
                    json.dumps(selected.config, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            }
            for selected in scenario.probes.values()
        ],
    }
    return provenance, patch


def _java_seed(value: str) -> int:
    try:
        parsed = int(value, 10)
        if -(2**63) <= parsed < 2**63:
            return parsed
    except ValueError:
        pass
    result = 0
    for character in value:
        result = (31 * result + ord(character)) & 0xFFFFFFFF
    return result - 2**32 if result >= 2**31 else result


def _read_level_dat_seed(level_dat: Path) -> int | None:
    """Read the world seed from a Minecraft level.dat (gzipped NBT)."""
    try:
        with gzip.open(level_dat, "rb") as f:
            return _nbt_find_long(f, ("Data", "WorldGenSettings", "seed"))
    except (OSError, struct.error, UnicodeDecodeError):
        return None


def _nbt_find_long(f, path: tuple[str, ...]) -> int | None:
    """Navigate gzipped NBT compound tags to read a TAG_Long at the given path."""

    def skip(tag_id: int) -> None:
        if tag_id == 1:
            f.read(1)
        elif tag_id == 2:
            f.read(2)
        elif tag_id in (3, 5):
            f.read(4)
        elif tag_id in (4, 6):
            f.read(8)
        elif tag_id == 7:
            f.read(struct.unpack(">i", f.read(4))[0])
        elif tag_id == 8:
            f.read(struct.unpack(">H", f.read(2))[0])
        elif tag_id == 9:
            elem = struct.unpack(">b", f.read(1))[0]
            for _ in range(struct.unpack(">i", f.read(4))[0]):
                skip(elem)
        elif tag_id == 10:
            while child := struct.unpack(">b", f.read(1))[0]:
                f.read(struct.unpack(">H", f.read(2))[0])
                skip(child)
        elif tag_id == 11:
            f.read(struct.unpack(">i", f.read(4))[0] * 4)
        elif tag_id == 12:
            f.read(struct.unpack(">i", f.read(4))[0] * 8)

    def read_name() -> str:
        return f.read(struct.unpack(">H", f.read(2))[0]).decode("utf-8")

    if struct.unpack(">b", f.read(1))[0] != 10:
        return None
    read_name()
    for depth, segment in enumerate(path):
        while True:
            child_type = struct.unpack(">b", f.read(1))[0]
            if child_type == 0:
                return None
            name = read_name()
            if name == segment:
                if depth == len(path) - 1:
                    return struct.unpack(">q", f.read(8))[0] if child_type == 4 else None
                if child_type != 10:
                    return None
                break
            skip(child_type)
    return None


def parse_mod_list(log_text: str, loader: str) -> list[dict[str, str]]:
    mods: list[dict[str, str]] = []
    if loader == "fabric":
        active = False
        for line in log_text.splitlines():
            if re.search(r"FabricLoader\) Loading \d+ mods:", line):
                active = True
                continue
            if active:
                match = re.match(r"\s*-\s+([a-z0-9_.-]+)\s+(.+?)\s*$", line)
                if match:
                    mods.append({"id": match.group(1), "version": match.group(2)})
                elif mods and not re.match(r"\s*[|\\]--", line):
                    break
    elif loader in {"forge", "neoforge"}:
        active = False
        for line in log_text.splitlines():
            if "Mod List:" in line:
                active = True
                continue
            if active:
                match = re.match(r"\s*(.+?)\s+(\S+)\s+\(([a-z0-9_.-]+)\)\s*$", line)
                if match and match.group(3) != "id":
                    mods.append(
                        {"id": match.group(3), "name": match.group(1).strip(), "version": match.group(2)}
                    )
                elif mods and "Launching target" in line:
                    break
    return mods


def verify_world_identity(state: dict, requested_seed: str, timeout: float) -> dict[str, Any]:
    world = Path(state["world_dir"])
    level_dat = world / "level.dat"
    if not world.is_dir() or not level_dat.is_file():
        raise InvestigationError(
            "world_identity_failed", f"owned world level.dat is missing: {level_dat}"
        )
    expected_seed = _java_seed(requested_seed)
    response = run_commands(state, ["seed"], timeout)[0]["response"]
    match = re.search(r"Seed:\s*\[(-?\d+)\]", response)
    if match:
        actual_seed = int(match.group(1))
    else:
        actual_seed = _read_level_dat_seed(level_dat)
        if actual_seed is None:
            raise InvestigationError(
                "world_identity_failed",
                f"could not parse seed from RCON response {response!r} or level.dat",
            )
    if actual_seed != expected_seed:
        raise InvestigationError(
            "seed_mismatch",
            f"world seed is {actual_seed}, expected {expected_seed} from {requested_seed!r}",
        )
    return {
        "requested_seed": requested_seed,
        "expected_seed": expected_seed,
        "actual_seed": actual_seed,
        "level_name": state["level_name"],
        "world_dir": str(world),
        "level_dat": str(level_dat),
    }


def _check_expectations(step: ScenarioStep, result: dict[str, Any]) -> None:
    expect = step.expect
    allowed = {"response_contains", "response_regex", "region_count", "terminal_state"}
    _known_keys(expect, allowed, f"expectations for step {step.step_id}")
    responses = "\n".join(
        item.get("response", "") for item in result.get("responses", result.get("regions", []))
    )
    contains = expect.get("response_contains", [])
    if isinstance(contains, str):
        contains = [contains]
    if not isinstance(contains, list) or any(not isinstance(item, str) for item in contains):
        raise _error(f"step {step.step_id} response_contains must be a string or array")
    missing = [item for item in contains if item not in responses]
    if missing:
        raise InvestigationError(
            "assertion_failed", f"step {step.step_id} response lacks {missing!r}"
        )
    pattern = expect.get("response_regex")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise _error(f"step {step.step_id} response_regex must be a string")
        if re.search(pattern, responses) is None:
            raise InvestigationError(
                "assertion_failed", f"step {step.step_id} response did not match {pattern!r}"
            )
    if "region_count" in expect and len(result.get("regions", [])) != expect["region_count"]:
        raise InvestigationError(
            "assertion_failed",
            f"step {step.step_id} generated {len(result.get('regions', []))} regions, "
            f"expected {expect['region_count']}",
        )
    if "terminal_state" in expect and result.get("terminal_state") != expect["terminal_state"]:
        raise InvestigationError(
            "assertion_failed",
            f"step {step.step_id} terminal state is {result.get('terminal_state')!r}, "
            f"expected {expect['terminal_state']!r}",
        )


def _measurement_summary(observations: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"observation_count": len(observations), "metrics": {}}
    for key in ("generation_seconds", "probe_seconds", "total_seconds"):
        values = [float(item["timing"][key]) for item in observations]
        result["metrics"][key] = {
            "observations": values,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }
    return result


def _seconds_between(started: str | None, finished: str | None) -> float | None:
    if not started or not finished:
        return None
    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    return (finish - start).total_seconds()


def _validate_probe_terminal(step_id: str, result: dict[str, Any]) -> None:
    terminal = result.get("state")
    if terminal != "pass":
        code = "incomplete_scan" if terminal == "inconclusive" else "probe_failed"
        raise InvestigationError(code, f"step {step_id} probe terminal state is {terminal!r}")
    completeness = result.get("completeness")
    if isinstance(completeness, dict) and completeness.get("complete") is not True:
        raise InvestigationError(
            "incomplete_scan", f"step {step_id} probe reports incomplete coverage"
        )


def _scenario_summary(
    state: dict, scenario: Scenario, result_state: str, steps: list[dict], error: dict | None
) -> dict:
    return {
        "ownership": state["ownership"],
        "run_id": state["run_id"],
        "scenario": {"name": scenario.name, "path": str(scenario.path)},
        "state": result_state,
        "steps": steps,
        "error": error,
        "cleanup": state.get("cleanup"),
        "updated_at": timestamp(),
    }


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    environment = sourced_environment()
    provenance: dict[str, Any] = {}
    dirty_patch = b""
    effective_scenario = scenario
    fixture_manifest: dict[str, Any] | None = None
    ephemeral_preset = scenario.rtf_ephemeral is not None
    materialized_path: Path | None = None
    materialized_dir: Path | None = None
    state: dict | None = None
    steps: list[dict[str, Any]] = []
    world_identity: dict[str, Any] = {}
    failure: InvestigationError | None = None
    log_position = 0
    scenario_summary_path: Path | None = None
    progress_path: Path | None = None

    def cleanup_materialized() -> None:
        nonlocal materialized_path, materialized_dir
        if materialized_path is None:
            return
        try:
            expected_root = (STATE_ROOT / "materialized").resolve()
            if materialized_path.parent.resolve().parent != expected_root:
                raise ValueError("materialized fixture path failed ownership validation")
            if materialized_path.exists():
                if materialized_path.is_symlink() or not materialized_path.is_file():
                    raise ValueError("materialized fixture output is not a regular file")
                materialized_path.unlink()
            assert materialized_dir is not None
            materialized_dir.rmdir()
            materialized_path = None
            materialized_dir = None
        except (OSError, ValueError) as cleanup:
            raise CleanupError(
                "temporary fixture cleanup did not complete",
                details={"path": str(materialized_path), "error": str(cleanup)},
            ) from cleanup

    def record_event(event: str, **data: Any) -> None:
        if progress_path is None:
            return
        value = {"timestamp": timestamp(), "event": event, **data}
        with progress_path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(value, sort_keys=True) + "\n")
            output.flush()

    def health_check() -> None:
        nonlocal log_position
        assert state is not None
        if not any(identity_matches(item) for item in state.get("owned_processes", [])):
            raise InvestigationError("scenario_crash", "owned server process boundary exited")
        log_path = Path(state["log_path"])
        with log_path.open("r", encoding="utf-8", errors="replace") as source:
            source.seek(log_position)
            addition = source.read()
            log_position = source.tell()
        for pattern in FATAL_LOG_PATTERNS:
            if pattern.search(addition):
                raise InvestigationError(
                    "scenario_fatal_log", f"fatal server condition matched {pattern.pattern!r}"
                )

    def execute_probe(
        probe_id: str,
        timeout: float,
        step_id: str,
        *,
        config_override: dict[str, Any] | None = None,
    ) -> tuple[dict, dict]:
        nonlocal state
        selected = scenario.probes[probe_id]
        config = dict(selected.config)
        if config_override:
            config.update(config_override)
        request, result, state = submit_probe(
            scenario.project,
            scenario.loader,
            probe_id=selected.probe_id,
            probe_version=selected.version,
            config=config,
            timeout=timeout,
        )
        _validate_probe_terminal(step_id, result)
        return request, result

    try:
        if scenario.rtf_fixture is not None:
            fixture_manifest, _files = load_fixture(scenario.rtf_fixture)
            materialized_dir = STATE_ROOT / "materialized" / uuid.uuid4().hex
            materialized_dir.mkdir(parents=True, exist_ok=False)
            materialized_path = materialized_dir / f"{fixture_manifest['id']}.zip"
            fixture_manifest = materialize_fixture(scenario.rtf_fixture, materialized_path)
            effective_scenario = replace(
                scenario, datapacks=(materialized_path, *scenario.datapacks)
            )
        elif scenario.rtf_ephemeral is not None:
            ephemeral = scenario.rtf_ephemeral
            materialized_dir = STATE_ROOT / "materialized" / uuid.uuid4().hex
            materialized_dir.mkdir(parents=True, exist_ok=False)
            materialized_path = materialized_dir / f"{ephemeral.fixture_id}.zip"
            fixture_manifest = materialize_ephemeral_fixture(
                fixture_id=ephemeral.fixture_id,
                purpose=ephemeral.purpose,
                base_metadata=ephemeral.base_fixture,
                expected_base_preset_sha256=ephemeral.base_preset_sha256,
                patch_file=ephemeral.patch_file,
                output=materialized_path,
            )
            effective_scenario = replace(
                scenario, datapacks=(materialized_path, *scenario.datapacks)
            )
        provenance, dirty_patch = capture_provenance(effective_scenario, environment)
        if fixture_manifest is not None:
            provenance[
                "rtf_ephemeral_preset" if ephemeral_preset else "rtf_fixture"
            ] = fixture_manifest
        server_properties = dict(scenario.server_properties)
        if any(step.kind == "generate" for step in scenario.steps):
            # Deliberate bounded generation is controlled by the scenario step timeout and
            # teardown path, not Minecraft's ordinary tick-stall watchdog.
            server_properties.setdefault("max-tick-time", "-1")
        state = start_server(
            scenario.project,
            scenario.loader,
            seed=scenario.seed,
            datapacks=list(effective_scenario.datapacks),
            companion_artifacts=list(resolve_artifacts(
                scenario.companion_artifacts,
                expected_loader=scenario.loader,
            )),
            properties=server_properties,
            timeout=scenario.startup_timeout,
            retention=scenario.retention,
            probe_packs=scenario.probe_packs,
        )
        provenance["launch_command"] = state["command"]
        provenance["probe_overlay"] = state["probe_overlay"]
        provenance["companion_artifacts"] = state.get("companion_artifacts", [])
        artifact_dir = Path(state["artifact_dir"])
        scenario_summary_path = artifact_dir / "scenario-summary.json"
        progress_path = artifact_dir / "scenario-progress.jsonl"
        (artifact_dir / "scenario.toml").write_bytes(scenario.path.read_bytes())
        (artifact_dir / "dirty.patch").write_bytes(dirty_patch)
        if materialized_path is not None and fixture_manifest is not None:
            fixture_artifact_dir = artifact_dir / "datapacks"
            fixture_artifact_dir.mkdir()
            fixture_artifact = fixture_artifact_dir / materialized_path.name
            shutil.copy2(materialized_path, fixture_artifact)
            fixture_manifest["materialization_path"] = fixture_manifest["archive_path"]
            fixture_manifest["archive_path"] = str(fixture_artifact)
            fixture_manifest["archive_artifact"] = str(fixture_artifact)
            if ephemeral_preset:
                assert scenario.rtf_ephemeral is not None
                patch_artifact = artifact_dir / "rtf-preset-merge-patch.json"
                shutil.copy2(scenario.rtf_ephemeral.patch_file, patch_artifact)
                fixture_manifest["patch_input_path"] = fixture_manifest["patch_path"]
                fixture_manifest["patch_path"] = str(patch_artifact)
                fixture_manifest["patch_artifact"] = str(patch_artifact)
            for datapack in provenance["datapacks"]:
                if datapack["path"] == str(materialized_path):
                    datapack["materialization_path"] = datapack["path"]
                    datapack["path"] = str(fixture_artifact)
                    if ephemeral_preset:
                        datapack["ephemeral_patch_path"] = str(patch_artifact)
                        datapack["base_fixture_metadata_path"] = fixture_manifest[
                            "base_metadata_path"
                        ]
                    else:
                        datapack["fixture_metadata_path"] = str(scenario.rtf_fixture)
                    datapack["artifact_path"] = str(fixture_artifact)
            state["datapacks"] = [
                str(fixture_artifact) if path == str(materialized_path) else path
                for path in state["datapacks"]
            ]
            cleanup_materialized()
        log_text = Path(state["log_path"]).read_text(encoding="utf-8", errors="replace")
        mods = parse_mod_list(log_text, scenario.loader)
        provenance["mods"] = mods
        present_mods = {item["id"] for item in mods}
        missing_mods = sorted(set(scenario.expectations["required_mods"]) - present_mods)
        if missing_mods:
            raise InvestigationError(
                "required_mod_missing", f"runtime mod list lacks: {', '.join(missing_mods)}"
            )
        atomic_write_json(artifact_dir / "provenance.json", provenance)
        state["scenario"] = {
            "name": scenario.name,
            "path": str(scenario.path),
            "sha256": provenance["scenario"]["sha256"],
        }
        state["provenance"] = provenance
        state["scenario_steps"] = steps
        persist_active(state)
        record_event("ready", run_id=state["run_id"], mods=len(mods))
        log_position = Path(state["log_path"]).stat().st_size
        world_identity = verify_world_identity(state, scenario.seed, scenario.step_timeout)
        state["world_identity"] = world_identity
        state["world_verified_at"] = timestamp()
        state.setdefault("timings", {})["world_open_seconds"] = _seconds_between(
            state.get("ready_at"), state["world_verified_at"]
        )
        persist_active(state)
        record_event("world-verified", world_identity=world_identity)

        def execute_scenario_step(step: ScenarioStep) -> dict[str, Any]:
            if step.kind == "command":
                responses = run_commands(state, step.values["commands"], step.timeout)
                return {"responses": responses}
            if step.kind == "probe":
                request, probe_result = execute_probe(
                    step.values["probe"], step.timeout, step.step_id
                )
                return {
                    "request": request,
                    "result": probe_result,
                    "terminal_state": probe_result["state"],
                }

            candidate_file = step.values.get("candidate_file")
            candidates = (
                _candidate_coordinates(candidate_file, step.values["candidate_limit"])
                if candidate_file is not None
                else None
            )
            if candidates is not None:
                generation_bounds = [
                    [item["block_x"], item["block_z"], item["block_x"], item["block_z"]]
                    for item in candidates
                ]
            else:
                base_bounds = step.values["bounds"]
                offset = step.values["offset"] or [0, 0]
                generation_bounds = [
                    [
                        base_bounds[0] + offset[0] * index,
                        base_bounds[1] + offset[1] * index,
                        base_bounds[2] + offset[0] * index,
                        base_bounds[3] + offset[1] * index,
                    ]
                    for index in range(step.values["repeat"])
                ]
            regions: list[dict[str, Any]] = []
            checks: list[dict[str, Any]] = []
            observations: list[dict[str, Any]] = []
            step_started = time.monotonic()
            for index, bounds in enumerate(generation_bounds):
                remaining = step.timeout - (time.monotonic() - step_started)
                if remaining <= 0:
                    raise InvestigationError(
                        "scenario_timeout", f"step {step.step_id} exceeded its timeout"
                    )
                generation_started = time.monotonic()
                generated = generate_regions(
                    state,
                    tuple(bounds),
                    step.values["unit"],
                    remaining,
                    progress=lambda value: record_event(
                        "generation-progress",
                        step_id=step.step_id,
                        observation=index,
                        **value,
                    ),
                )
                generation_seconds = time.monotonic() - generation_started
                regions.extend(generated)
                probe_seconds = 0.0
                terminal = None
                terminal_probe = step.values["terminal_probe"]
                if terminal_probe:
                    remaining = step.timeout - (time.monotonic() - step_started)
                    if remaining <= 0:
                        raise InvestigationError(
                            "scenario_timeout", f"step {step.step_id} exceeded its timeout"
                        )
                    probe_started = time.monotonic()
                    request, probe_result = execute_probe(
                        terminal_probe,
                        remaining,
                        step.step_id,
                        config_override={"bounds": bounds, "unit": step.values["unit"]},
                    )
                    probe_seconds = time.monotonic() - probe_started
                    terminal = {"request": request, "result": probe_result}
                    checks.append(terminal)
                observations.append(
                    {
                        "index": index,
                        "bounds": bounds,
                        "regions": generated,
                        "terminal_probe": terminal,
                        "timing": {
                            "generation_seconds": generation_seconds,
                            "probe_seconds": probe_seconds,
                            "total_seconds": generation_seconds + probe_seconds,
                        },
                    }
                )
            result = {
                "authority": step.values["authority"],
                "unit": step.values["unit"],
                "input_bounds": step.values["bounds"],
                "candidate_file": str(candidate_file) if candidate_file else None,
                "candidates": candidates,
                "regions": regions,
                "observations": observations,
                "timing": _measurement_summary(observations),
            }
            if checks:
                result["terminal_probe"] = {"checks": checks}
                result["terminal_state"] = "pass"
            return result

        for step in scenario.steps:
            health_check()
            started_at = timestamp()
            record_event("step-started", step_id=step.step_id, step_type=step.kind)
            recording = (
                start_jfr(state, step.step_id, environment.get("JAVA_HOME"))
                if step.values["jfr"]
                else None
            )
            step_failure: BaseException | None = None
            profile = None
            try:
                result = execute_scenario_step(step)
            except BaseException as exc:
                step_failure = exc
                result = {}
            if recording is not None:
                try:
                    profile = stop_jfr(recording, environment.get("JAVA_HOME"))
                except BaseException as exc:
                    if step_failure is None:
                        step_failure = exc
                    elif isinstance(step_failure, InvestigationError):
                        step_failure.details["jfr_stop_error"] = str(exc)
            if step_failure is not None:
                raise step_failure
            if profile is not None:
                result["profile"] = profile
                state.setdefault("profile_artifacts", []).append(profile)
            health_check()
            _check_expectations(step, result)
            record = {
                "id": step.step_id,
                "type": step.kind,
                "state": "succeeded",
                "started_at": started_at,
                "finished_at": timestamp(),
                "result": result,
            }
            steps.append(record)
            record_event("step-finished", step_id=step.step_id, state="succeeded")
            state["scenario_steps"] = steps
            persist_active(state)
            atomic_write_json(
                scenario_summary_path,
                _scenario_summary(state, scenario, "running", steps, None),
            )
    except InvestigationError as exc:
        failure = exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = InvestigationError("scenario_error", str(exc))
    finally:
        if state is not None:
            if failure is not None:
                failure.details.update(
                    {
                        "run_id": state["run_id"],
                        "artifact_dir": state["artifact_dir"],
                        "log_path": state["log_path"],
                        "scenario": str(scenario.path),
                    }
                )
            if scenario_summary_path is not None:
                atomic_write_json(
                    scenario_summary_path,
                    _scenario_summary(
                        state,
                        scenario,
                        "failed" if failure else "succeeded",
                        steps,
                        (
                            {
                                "code": failure.code,
                                "message": failure.message,
                                "details": failure.details,
                            }
                            if failure
                            else None
                        ),
                    ),
                )
            try:
                state = stop_server(
                    scenario.project,
                    scenario.loader,
                    successful=failure is None,
                    timeout=scenario.shutdown_timeout,
                )
            except InvestigationError as cleanup:
                temporary_cleanup = None
                try:
                    cleanup_materialized()
                except CleanupError as temporary_failure:
                    temporary_cleanup = temporary_failure.details
                if scenario_summary_path is not None:
                    atomic_write_json(
                        scenario_summary_path,
                        _scenario_summary(
                            state,
                            scenario,
                            "failed",
                            steps,
                            {
                                "code": "cleanup_failed",
                                "message": cleanup.message,
                                "details": cleanup.details,
                            },
                        ),
                    )
                raise CleanupError(
                    "scenario cleanup did not complete",
                    details={
                        "run_id": state["run_id"],
                        "artifact_dir": state["artifact_dir"],
                        "log_path": state["log_path"],
                        "scenario_error": (
                            {"code": failure.code, "message": failure.message}
                            if failure
                            else None
                        ),
                        "cleanup_error": cleanup.details,
                        "temporary_fixture_cleanup_error": temporary_cleanup,
                    },
                ) from cleanup
            if scenario_summary_path is not None:
                atomic_write_json(
                    scenario_summary_path,
                    _scenario_summary(
                        state,
                        scenario,
                        "failed" if failure else "succeeded",
                        steps,
                        (
                            {
                                "code": failure.code,
                                "message": failure.message,
                                "details": failure.details,
                            }
                            if failure
                            else None
                        ),
                    ),
                )
            record_event(
                "cleanup-finished",
                state=state["lifecycle"],
                cleanup=state.get("cleanup"),
            )
        cleanup_materialized()
    if failure is not None:
        raise failure
    assert state is not None
    return {
        "state": state,
        "scenario": state["scenario"],
        "steps": steps,
        "provenance": provenance,
        "world_identity": world_identity,
        "rtf_fixture": None if ephemeral_preset else fixture_manifest,
        "rtf_ephemeral_preset": fixture_manifest if ephemeral_preset else None,
        "scenario_summary": str(scenario_summary_path),
        "scenario_progress": str(progress_path),
    }
