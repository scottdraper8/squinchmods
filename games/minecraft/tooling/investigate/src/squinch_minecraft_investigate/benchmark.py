from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tomllib

from .catalog import CATALOG_PATH
from .errors import InvestigationError
from .output import timestamp
from .paths import LOCKS_ROOT, REPOSITORY_ROOT, RUNS_ROOT, STATE_ROOT
from .scenario import RETENTIONS, Scenario, load_scenario, run_scenario
from .state import atomic_write_json, blocking_lock, read_json

BENCHMARK_VERSION = 1
LIFECYCLE_BLOCKER_CODES = frozenset(
    {
        "cleanup_failed",
        "already_active",
        "recovery_required",
        "host_degraded",
        "host_not_quiet",
        "benchmark_inputs_changed",
    }
)
ORDERS = {"round-robin", "shuffled", "bracketed", "paired-bracketed"}
LOADERS = {"fabric", "forge", "neoforge", "quilt"}
BENCHMARK_ROOT = STATE_ROOT / "benchmarks"


@dataclass(frozen=True)
class BenchmarkVariant:
    variant_id: str
    label: str
    loader: str | None
    comparison_group: str | None
    pair_id: str | None
    companion_artifacts: tuple[str, ...]
    required_mods: tuple[str, ...]
    startup_failure: dict[str, Any] | None


@dataclass(frozen=True)
class HostPolicy:
    enabled: bool
    settle_seconds: float
    timeout: float
    max_load_per_cpu: float
    min_available_memory_mib: int
    max_swap_used_mib: int
    require_no_swap_activity: bool


@dataclass(frozen=True)
class BenchmarkMatrix:
    path: Path
    name: str
    scenario_path: Path
    repetitions: int
    order: str
    random_seed: int
    control_variant: str | None
    control_pair: str | None
    continue_on_failure: bool
    retention: str
    host: HostPolicy
    variants: tuple[BenchmarkVariant, ...]


def _error(message: str) -> InvestigationError:
    return InvestigationError("invalid_benchmark", message)


def _known_keys(value: dict, allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(f"unknown {context} key(s): {', '.join(unknown)}")


def _number(value: Any, context: str, *, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{context} must be a number")
    result = float(value)
    if result < minimum:
        raise _error(f"{context} must be at least {minimum}")
    return result


def _repository_file(value: Any, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise _error(f"{context} must be a nonempty repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise _error(f"{context} must be a repository-relative path")
    resolved = (REPOSITORY_ROOT / path).resolve()
    if not resolved.is_relative_to(REPOSITORY_ROOT):
        raise _error(f"{context} escapes the repository root")
    if not resolved.is_file():
        raise _error(f"{context} does not exist: {value}")
    return resolved


def load_benchmark(path: str | Path) -> BenchmarkMatrix:
    benchmark_path = Path(path).expanduser().resolve()
    if not benchmark_path.is_file():
        raise InvestigationError(
            "benchmark_not_found", f"benchmark file does not exist: {benchmark_path}"
        )
    try:
        raw = tomllib.loads(benchmark_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _error(f"invalid TOML in {benchmark_path}: {exc}") from exc
    _known_keys(
        raw,
        {
            "schema_version",
            "name",
            "scenario",
            "repetitions",
            "order",
            "random_seed",
            "control_variant",
            "control_pair",
            "continue_on_failure",
            "retention",
            "host",
            "variants",
        },
        "top-level",
    )
    if raw.get("schema_version") != BENCHMARK_VERSION:
        raise _error(f"schema_version must be {BENCHMARK_VERSION}")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _error("name must be a nonempty string")
    scenario_path = _repository_file(raw.get("scenario"), "scenario")
    repetitions = raw.get("repetitions", 1)
    if (
        isinstance(repetitions, bool)
        or not isinstance(repetitions, int)
        or not 1 <= repetitions <= 100
    ):
        raise _error("repetitions must be 1..100")
    order = raw.get("order", "round-robin")
    if order not in ORDERS:
        raise _error(f"order must be one of {sorted(ORDERS)}")
    random_seed = raw.get("random_seed", 0)
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise _error("random_seed must be an integer")
    continue_on_failure = raw.get("continue_on_failure", False)
    if not isinstance(continue_on_failure, bool):
        raise _error("continue_on_failure must be true or false")
    retention = raw.get("retention", "keep")
    if retention not in RETENTIONS:
        raise _error(f"retention must be one of {sorted(RETENTIONS)}")

    host_raw = raw.get("host", {})
    if not isinstance(host_raw, dict):
        raise _error("host must be a table")
    _known_keys(
        host_raw,
        {
            "enabled",
            "settle_seconds",
            "timeout",
            "max_load_per_cpu",
            "min_available_memory_mib",
            "max_swap_used_mib",
            "require_no_swap_activity",
        },
        "host",
    )
    host_enabled = host_raw.get("enabled", True)
    no_swap_activity = host_raw.get("require_no_swap_activity", True)
    if not isinstance(host_enabled, bool) or not isinstance(no_swap_activity, bool):
        raise _error("host enabled and require_no_swap_activity must be booleans")
    memory = host_raw.get("min_available_memory_mib", 4096)
    swap = host_raw.get("max_swap_used_mib", 256)
    if (
        isinstance(memory, bool)
        or not isinstance(memory, int)
        or memory < 0
        or isinstance(swap, bool)
        or not isinstance(swap, int)
        or swap < 0
    ):
        raise _error("host memory and swap thresholds must be nonnegative integers")
    host = HostPolicy(
        enabled=host_enabled,
        settle_seconds=_number(
            host_raw.get("settle_seconds", 5), "host.settle_seconds"
        ),
        timeout=_number(host_raw.get("timeout", 300), "host.timeout", minimum=0.1),
        max_load_per_cpu=_number(
            host_raw.get("max_load_per_cpu", 0.5), "host.max_load_per_cpu"
        ),
        min_available_memory_mib=memory,
        max_swap_used_mib=swap,
        require_no_swap_activity=no_swap_activity,
    )

    variants_raw = raw.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        raise _error("variants must be a nonempty array of tables")
    variants: list[BenchmarkVariant] = []
    variant_ids: set[str] = set()
    for index, value in enumerate(variants_raw):
        context = f"variants[{index}]"
        if not isinstance(value, dict):
            raise _error(f"{context} must be a table")
        _known_keys(
            value,
            {
                "id",
                "label",
                "loader",
                "comparison_group",
                "pair_id",
                "companion_artifacts",
                "required_mods",
                "startup_failure",
            },
            context,
        )
        variant_id = value.get("id")
        if (
            not isinstance(variant_id, str)
            or not variant_id
            or Path(variant_id).name != variant_id
        ):
            raise _error(f"{context}.id must be a filename-safe nonempty string")
        if variant_id in variant_ids:
            raise _error(f"duplicate variant ID: {variant_id}")
        variant_ids.add(variant_id)
        label = value.get("label", variant_id)
        if not isinstance(label, str) or not label:
            raise _error(f"{context}.label must be a nonempty string")
        loader = value.get("loader")
        if loader is not None and loader not in LOADERS:
            raise _error(f"{context}.loader must be one of {sorted(LOADERS)}")
        comparison_group = value.get("comparison_group")
        pair_id = value.get("pair_id")
        for field, item in (
            ("comparison_group", comparison_group),
            ("pair_id", pair_id),
        ):
            if item is not None and (
                not isinstance(item, str) or not item or Path(item).name != item
            ):
                raise _error(
                    f"{context}.{field} must be a filename-safe nonempty string"
                )
        if (comparison_group is None) != (pair_id is None):
            raise _error(f"{context} must set comparison_group and pair_id together")
        artifacts = value.get("companion_artifacts", [])
        required_mods = value.get("required_mods", [])
        for field, items in (
            ("companion_artifacts", artifacts),
            ("required_mods", required_mods),
        ):
            if not isinstance(items, list) or any(
                not isinstance(item, str) or not item or Path(item).name != item
                for item in items
            ):
                raise _error(f"{context}.{field} must be an array of IDs")
            if len(set(items)) != len(items):
                raise _error(f"{context}.{field} contains duplicates")
        startup_failure = value.get("startup_failure")
        if startup_failure is not None:
            if not isinstance(startup_failure, dict):
                raise _error(f"{context}.startup_failure must be an inline table")
            _known_keys(
                startup_failure, {"code", "log_contains"}, f"{context}.startup_failure"
            )
            code = startup_failure.get("code")
            log_contains = startup_failure.get("log_contains", [])
            if not isinstance(code, str) or not code:
                raise _error(
                    f"{context}.startup_failure.code must be a nonempty string"
                )
            if not isinstance(log_contains, list) or any(
                not isinstance(item, str) or not item for item in log_contains
            ):
                raise _error(
                    f"{context}.startup_failure.log_contains must be an array of nonempty strings"
                )
            startup_failure = {"code": code, "log_contains": list(log_contains)}
        variants.append(
            BenchmarkVariant(
                variant_id,
                label,
                loader,
                comparison_group,
                pair_id,
                tuple(artifacts),
                tuple(required_mods),
                startup_failure,
            )
        )

    control_variant = raw.get("control_variant")
    if control_variant is not None and control_variant not in variant_ids:
        raise _error("control_variant must reference a declared variant")
    if order == "bracketed" and control_variant is None:
        raise _error("bracketed order requires control_variant")

    control_pair = raw.get("control_pair")
    if control_pair is not None and (
        not isinstance(control_pair, str)
        or not control_pair
        or Path(control_pair).name != control_pair
    ):
        raise _error("control_pair must be a filename-safe nonempty string")
    if order == "paired-bracketed":
        if control_pair is None:
            raise _error("paired-bracketed order requires control_pair")
        if control_variant is not None:
            raise _error(
                "paired-bracketed order uses control_pair, not control_variant"
            )
        members: dict[str, dict[str, BenchmarkVariant]] = {}
        for variant in variants:
            if variant.comparison_group is None or variant.pair_id is None:
                raise _error(
                    "paired-bracketed variants require comparison_group and pair_id"
                )
            group_members = members.setdefault(variant.pair_id, {})
            if variant.comparison_group in group_members:
                raise _error(
                    f"duplicate paired member for {variant.pair_id}/"
                    f"{variant.comparison_group}"
                )
            group_members[variant.comparison_group] = variant
        if control_pair not in members:
            raise _error("control_pair must reference a declared pair_id")
        groups = set(members[control_pair])
        if len(groups) < 2:
            raise _error(
                "paired-bracketed order requires at least two comparison groups"
            )
        for pair_id, group_members in members.items():
            if set(group_members) != groups:
                raise _error(
                    f"pair {pair_id} must contain exactly the comparison groups "
                    f"{sorted(groups)}"
                )
    elif control_pair is not None:
        raise _error("control_pair is only valid with paired-bracketed order")

    return BenchmarkMatrix(
        benchmark_path,
        name,
        scenario_path,
        repetitions,
        order,
        random_seed,
        control_variant,
        control_pair,
        continue_on_failure,
        retention,
        host,
        tuple(variants),
    )


def build_plan(matrix: BenchmarkMatrix) -> list[dict[str, Any]]:
    rng = random.Random(matrix.random_seed)
    plan: list[dict[str, Any]] = []
    sequence = 0
    for repetition in range(1, matrix.repetitions + 1):
        variants = list(matrix.variants)
        if matrix.order == "shuffled":
            rng.shuffle(variants)
            entries = [(variant, None) for variant in variants]
        elif matrix.order == "bracketed":
            control = next(
                variant
                for variant in variants
                if variant.variant_id == matrix.control_variant
            )
            treatment = [variant for variant in variants if variant != control]
            rng.shuffle(treatment)
            entries = [
                (control, "start"),
                *((variant, None) for variant in treatment),
                (control, "end"),
            ]
        elif matrix.order == "paired-bracketed":
            paired: dict[str, dict[str, BenchmarkVariant]] = {}
            for variant in variants:
                paired.setdefault(variant.pair_id or "", {})[
                    variant.comparison_group or ""
                ] = variant
            pair_ids = sorted(
                pair_id for pair_id in paired if pair_id != matrix.control_pair
            )
            rng.shuffle(pair_ids)
            start_controls = list(paired[matrix.control_pair or ""].values())
            end_controls = list(start_controls)
            rng.shuffle(start_controls)
            rng.shuffle(end_controls)
            entries = [(variant, "start") for variant in start_controls]
            for pair_id in pair_ids:
                members = list(paired[pair_id].values())
                rng.shuffle(members)
                entries.extend((variant, None) for variant in members)
            entries.extend((variant, "end") for variant in end_controls)
        else:
            entries = [(variant, None) for variant in variants]
        for variant, bracket in entries:
            sequence += 1
            plan.append(
                {
                    "sequence": sequence,
                    "repetition": repetition,
                    "variant_id": variant.variant_id,
                    "label": variant.label,
                    "loader": variant.loader,
                    "comparison_group": variant.comparison_group,
                    "pair_id": variant.pair_id,
                    "bracket": bracket,
                    "companion_artifacts": list(variant.companion_artifacts),
                    "required_mods": list(variant.required_mods),
                    "startup_failure": variant.startup_failure,
                }
            )
    return plan


def _read_key_values(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1].isdigit():
            values[fields[0].rstrip(":")] = int(fields[1])
    return values


def host_snapshot() -> dict[str, Any]:
    cpus = os.cpu_count() or 1
    load1, load5, load15 = os.getloadavg()
    memory = _read_key_values(Path("/proc/meminfo"))
    vmstat = _read_key_values(Path("/proc/vmstat"))
    swap_total = memory.get("SwapTotal", 0)
    swap_free = memory.get("SwapFree", 0)
    return {
        "timestamp": timestamp(),
        "kernel": platform.release(),
        "logical_cpus": cpus,
        "load": {"one": load1, "five": load5, "fifteen": load15},
        "load_per_cpu": load1 / cpus,
        "memory_available_mib": memory.get("MemAvailable", 0) / 1024,
        "swap_used_mib": max(0, swap_total - swap_free) / 1024,
        "swap_io": {
            "pages_in": vmstat.get("pswpin", 0),
            "pages_out": vmstat.get("pswpout", 0),
        },
    }


def _host_reasons(
    policy: HostPolicy, current: dict, previous: dict | None
) -> list[str]:
    reasons: list[str] = []
    if current["load_per_cpu"] > policy.max_load_per_cpu:
        reasons.append("load")
    if current["memory_available_mib"] < policy.min_available_memory_mib:
        reasons.append("memory")
    if current["swap_used_mib"] > policy.max_swap_used_mib:
        reasons.append("swap-used")
    if (
        policy.require_no_swap_activity
        and previous is not None
        and current["swap_io"] != previous["swap_io"]
    ):
        reasons.append("swap-activity")
    return reasons


def wait_for_quiet_host(policy: HostPolicy) -> dict[str, Any]:
    if not policy.enabled:
        return {"enabled": False, "snapshot": host_snapshot(), "wait_seconds": 0.0}
    started = time.monotonic()
    stable_since: float | None = None
    previous: dict | None = None
    last_reasons: list[str] = []
    while True:
        current = host_snapshot()
        last_reasons = _host_reasons(policy, current, previous)
        now = time.monotonic()
        if not last_reasons:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= policy.settle_seconds:
                return {
                    "enabled": True,
                    "snapshot": current,
                    "wait_seconds": now - started,
                    "stable_seconds": now - stable_since,
                }
        else:
            stable_since = None
        if now - started >= policy.timeout:
            raise InvestigationError(
                "host_not_quiet",
                "host did not satisfy benchmark health policy",
                details={
                    "wait_seconds": now - started,
                    "reasons": last_reasons,
                    "snapshot": current,
                },
            )
        previous = current
        time.sleep(min(1.0, max(0.1, policy.settle_seconds / 2 or 0.1)))


def _effective_scenario(
    base: Scenario, matrix: BenchmarkMatrix, entry: dict[str, Any]
) -> Scenario:
    artifacts = tuple(
        dict.fromkeys((*base.companion_artifacts, *entry["companion_artifacts"]))
    )
    expectations = dict(base.expectations)
    expectations["required_mods"] = list(
        dict.fromkeys((*base.expectations["required_mods"], *entry["required_mods"]))
    )
    startup_failure = entry.get("startup_failure")
    expectations["startup_failure"] = startup_failure
    return replace(
        base,
        name=f"{base.name} [{entry['variant_id']}]",
        loader=entry.get("loader") or base.loader,
        companion_artifacts=artifacts,
        retention=matrix.retention,
        probes={} if startup_failure is not None else base.probes,
        steps=() if startup_failure is not None else base.steps,
        expectations=expectations,
    )


def _metrics(result: dict[str, Any]) -> dict[str, dict]:
    values: dict[str, dict] = {}
    for step in result.get("steps", []):
        for metric_id, metric in step.get("result", {}).get("metrics", {}).items():
            values[f"{step['id']}.{metric_id}"] = metric
    return values


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for record in records:
        if record.get("state") != "succeeded":
            continue
        variant = record["plan"]["variant_id"]
        for metric_id, metric in record.get("metrics", {}).items():
            value = metric.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            grouped.setdefault(variant, {}).setdefault(metric_id, []).append(
                float(value)
            )
    aggregate: dict[str, Any] = {}
    for variant, metrics in grouped.items():
        aggregate[variant] = {}
        for metric_id, values in metrics.items():
            aggregate[variant][metric_id] = {
                "count": len(values),
                "minimum": min(values),
                "maximum": max(values),
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
                "sample_standard_deviation": (
                    statistics.stdev(values) if len(values) > 1 else None
                ),
                "values": values,
            }
    return aggregate


def _paired_comparison(
    records: list[dict[str, Any]], control_pair: str | None
) -> dict[str, Any] | None:
    if control_pair is None:
        return None
    values: dict[str, dict[str, dict[str, list[float]]]] = {}
    repeated_values: dict[str, dict[str, dict[str, list[tuple[int, float]]]]] = {}
    for record in records:
        plan = record.get("plan", {})
        group = plan.get("comparison_group")
        pair_id = plan.get("pair_id")
        repetition = plan.get("repetition")
        if (
            record.get("state") != "succeeded"
            or not group
            or not pair_id
            or not isinstance(repetition, int)
        ):
            continue
        for metric_id, metric in record.get("metrics", {}).items():
            value = metric.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            numeric = float(value)
            values.setdefault(group, {}).setdefault(pair_id, {}).setdefault(
                metric_id, []
            ).append(numeric)
            repeated_values.setdefault(group, {}).setdefault(pair_id, {}).setdefault(
                metric_id, []
            ).append((repetition, numeric))

    groups: dict[str, Any] = {}
    normalized: dict[str, dict[str, dict[str, float]]] = {}
    for group, pairs in values.items():
        groups[group] = {}
        normalized[group] = {}
        controls = repeated_values.get(group, {}).get(control_pair, {})
        for pair_id, metrics in pairs.items():
            groups[group][pair_id] = {}
            normalized[group][pair_id] = {}
            for metric_id, samples in metrics.items():
                mean = statistics.fmean(samples)
                median = statistics.median(samples)
                result = {
                    "count": len(samples),
                    "minimum": min(samples),
                    "maximum": max(samples),
                    "mean": mean,
                    "median": median,
                    "sample_standard_deviation": (
                        statistics.stdev(samples) if len(samples) > 1 else None
                    ),
                    "values": samples,
                }
                control_by_repetition: dict[int, list[float]] = {}
                for repetition, value in controls.get(metric_id, []):
                    control_by_repetition.setdefault(repetition, []).append(value)
                relative_samples = []
                for repetition, value in repeated_values[group][pair_id][metric_id]:
                    repetition_controls = control_by_repetition.get(repetition, [])
                    if repetition_controls:
                        control = statistics.fmean(repetition_controls)
                        if control:
                            relative_samples.append(value / control)
                if relative_samples:
                    result["mean_relative_to_control"] = statistics.fmean(
                        relative_samples
                    )
                    result["median_relative_to_control"] = statistics.median(
                        relative_samples
                    )
                    result["relative_to_control_values"] = relative_samples
                groups[group][pair_id][metric_id] = result
                relative = result.get("median_relative_to_control")
                if relative is not None:
                    normalized[group][pair_id][metric_id] = relative

    pair_comparisons: dict[str, Any] = {}
    group_names = sorted(normalized)
    pair_ids = sorted({pair_id for group in normalized.values() for pair_id in group})
    for pair_id in pair_ids:
        metric_ids = sorted(
            {
                metric_id
                for group in normalized.values()
                for metric_id in group.get(pair_id, {})
            }
        )
        pair_comparisons[pair_id] = {}
        for metric_id in metric_ids:
            relative_by_group = {
                group: normalized[group][pair_id][metric_id]
                for group in group_names
                if metric_id in normalized[group].get(pair_id, {})
            }
            ratios: dict[str, float] = {}
            for left_index, left in enumerate(group_names):
                for right in group_names[left_index + 1 :]:
                    left_value = relative_by_group.get(left)
                    right_value = relative_by_group.get(right)
                    if left_value and right_value is not None:
                        ratios[f"{right}/{left}"] = right_value / left_value
            pair_comparisons[pair_id][metric_id] = {
                "median_relative_to_control": relative_by_group,
                "group_ratios": ratios,
            }

    return {
        "control_pair": control_pair,
        "groups": groups,
        "pairs": pair_comparisons,
    }


def _result_path(run_dir: Path, entry: dict[str, Any]) -> Path:
    return run_dir / "runs" / f"{entry['sequence']:04d}-{entry['variant_id']}.json"


def _new_run_id() -> str:
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{now}-{uuid.uuid4().hex[:10]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_bytes(project: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError(
            "benchmark_input_failed",
            f"failed to fingerprint benchmark project {project}: {exc}",
        ) from exc


def _git_identity(project: Path) -> dict[str, Any]:
    status = _git_bytes(project, "status", "--porcelain=v1", "-z")
    patch = _git_bytes(project, "diff", "--binary", "HEAD", "--")
    untracked_raw = _git_bytes(
        project, "ls-files", "--others", "--exclude-standard", "-z"
    )
    untracked = []
    for raw_path in filter(
        None, untracked_raw.decode(errors="surrogateescape").split("\0")
    ):
        path = project / raw_path
        if path.is_file() and not path.is_symlink():
            untracked.append(
                {
                    "path": raw_path,
                    "sha256": _sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    return {
        "project": str(project),
        "head": _git_bytes(project, "rev-parse", "HEAD").decode().strip(),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "dirty_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "untracked": untracked,
    }


def _path_identity(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.exists():
        raise InvestigationError(
            "benchmark_input_failed", f"benchmark input does not exist: {path}"
        )
    if path.is_file():
        return {
            "path": str(path),
            "kind": "file",
            "sha256": _sha256_file(path),
            "size": path.stat().st_size,
        }
    if not path.is_dir():
        raise InvestigationError(
            "benchmark_input_failed",
            f"benchmark input is not a file or directory: {path}",
        )
    files = []
    for child in sorted(path.rglob("*")):
        if child.is_file() and not child.is_symlink():
            files.append(
                {
                    "path": child.relative_to(path).as_posix(),
                    "sha256": _sha256_file(child),
                    "size": child.stat().st_size,
                }
            )
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "path": str(path),
        "kind": "directory",
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "files": files,
    }


def _campaign_input_identity(base: Scenario) -> dict[str, Any]:
    paths: list[Path] = []
    optional_paths = (
        base.ftf_preset,
        base.subject_artifact,
        base.subject_compile_artifact,
    )
    paths.extend(path for path in optional_paths if path is not None)
    paths.extend(base.datapacks)
    paths.extend(source for source, _target in base.runtime_files)
    paths.extend(base.probe_packs)
    for step in base.steps:
        candidate = step.values.get("candidate_file")
        if isinstance(candidate, Path):
            paths.append(candidate)
    unique_paths = sorted({path.resolve() for path in paths}, key=str)
    projects = [base.project]
    if base.subject_source_project is not None:
        projects.append(base.subject_source_project)
    identity = {
        "projects": [
            _git_identity(project)
            for project in dict.fromkeys(project.resolve() for project in projects)
        ],
        "files": [_path_identity(path) for path in unique_paths],
        "catalog": _path_identity(CATALOG_PATH.resolve()),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "inputs": identity}


def _attempt_path(run_dir: Path, entry: dict[str, Any], attempt: int) -> Path:
    return (
        run_dir
        / "attempts"
        / f"{entry['sequence']:04d}-{entry['variant_id']}"
        / f"{attempt:04d}.json"
    )


def _checkpoint_path(result_path: Path) -> Path:
    return result_path.with_suffix(result_path.suffix + ".sha256")


def _write_checkpoint(path: Path, record: dict[str, Any]) -> None:
    atomic_write_json(path, record)
    checkpoint = _checkpoint_path(path)
    temporary = checkpoint.with_name(f".{checkpoint.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(f"{_sha256_file(path)}\n", encoding="ascii")
    os.replace(temporary, checkpoint)


def _verify_checkpoint(path: Path, record: dict[str, Any], *, artifacts: bool) -> None:
    checkpoint = _checkpoint_path(path)
    if not checkpoint.is_file():
        raise InvestigationError(
            "benchmark_checkpoint_corrupt",
            f"accepted benchmark checkpoint is missing its digest: {path}",
        )
    expected = checkpoint.read_text(encoding="ascii").strip()
    actual = _sha256_file(path)
    if expected != actual:
        raise InvestigationError(
            "benchmark_checkpoint_corrupt",
            f"accepted benchmark checkpoint digest changed: {path}",
        )
    if not artifacts:
        return
    scenario_run_id = record.get("scenario_run_id")
    if not isinstance(scenario_run_id, str) or not scenario_run_id:
        raise InvestigationError(
            "benchmark_checkpoint_incomplete",
            f"accepted benchmark checkpoint has no scenario run ID: {path}",
        )
    artifact_dir = RUNS_ROOT / scenario_run_id
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise InvestigationError(
            "benchmark_checkpoint_incomplete",
            f"accepted scenario evidence is missing for {scenario_run_id}",
        )
    manifest = read_json(manifest_path)
    if manifest.get("run_id") != scenario_run_id:
        raise InvestigationError(
            "benchmark_checkpoint_corrupt",
            f"accepted scenario evidence identity changed for {scenario_run_id}",
        )
    for key in ("scenario_summary", "scenario_progress"):
        value = record.get(key)
        if not isinstance(value, str) or not Path(value).is_file():
            raise InvestigationError(
                "benchmark_checkpoint_incomplete",
                f"accepted scenario evidence is missing {key} for {scenario_run_id}",
            )


def _archive_legacy_attempt(
    run_dir: Path, entry: dict[str, Any], record: dict[str, Any]
) -> int:
    attempt = record.get("attempt")
    if not isinstance(attempt, int) or attempt < 1:
        attempt = 1
        record = {**record, "attempt": attempt}
    path = _attempt_path(run_dir, entry, attempt)
    if not path.is_file():
        atomic_write_json(path, record)
    return attempt


def _next_attempt_number(
    run_dir: Path,
    entry: dict[str, Any],
    existing: dict[str, Any] | None,
) -> int:
    if existing is not None:
        _archive_legacy_attempt(run_dir, entry, existing)
    directory = _attempt_path(run_dir, entry, 1).parent
    attempts = (
        [int(path.stem) for path in directory.glob("*.json") if path.stem.isdigit()]
        if directory.is_dir()
        else []
    )
    return max(attempts, default=0) + 1


def _matching_campaigns(
    benchmark_root: Path,
    *,
    benchmark_sha256: str,
    scenario_sha256: str,
    plan: list[dict[str, Any]],
    input_identity: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    resumable: list[str] = []
    completed: list[str] = []
    changed_inputs: list[str] = []
    if not benchmark_root.exists():
        return resumable, completed, changed_inputs
    for path in sorted(benchmark_root.iterdir()):
        if not path.is_dir() or path.is_symlink():
            continue
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = read_json(manifest_path)
        except InvestigationError:
            continue
        if (
            manifest.get("benchmark_sha256") != benchmark_sha256
            or manifest.get("scenario_sha256") != scenario_sha256
            or manifest.get("plan") != plan
        ):
            continue
        if manifest.get("input_identity") != input_identity:
            changed_inputs.append(path.name)
            continue
        summary_path = path / "summary.json"
        state = (
            read_json(summary_path).get("state")
            if summary_path.is_file()
            else "running"
        )
        if state == "succeeded":
            completed.append(path.name)
        else:
            resumable.append(path.name)
    return resumable, completed, changed_inputs


def accepted_checkpoint_references(
    benchmark_root: Path = BENCHMARK_ROOT,
) -> dict[str, list[dict[str, Any]]]:
    references: dict[str, list[dict[str, Any]]] = {}
    if not benchmark_root.exists():
        return references
    for benchmark_dir in sorted(benchmark_root.iterdir()):
        if not benchmark_dir.is_dir() or benchmark_dir.is_symlink():
            continue
        manifest_path = benchmark_dir / "manifest.json"
        runs_dir = benchmark_dir / "runs"
        if not manifest_path.is_file() or not runs_dir.is_dir():
            continue
        try:
            manifest = read_json(manifest_path)
        except InvestigationError:
            continue
        benchmark_id = manifest.get("run_id")
        if benchmark_id != benchmark_dir.name:
            continue
        for path in sorted(runs_dir.glob("*.json")):
            try:
                record = read_json(path)
            except InvestigationError:
                continue
            scenario_run_id = record.get("scenario_run_id")
            if record.get("state") != "succeeded" or not isinstance(
                scenario_run_id, str
            ):
                continue
            plan = record.get("plan", {})
            references.setdefault(scenario_run_id, []).append(
                {
                    "benchmark_id": benchmark_id,
                    "sequence": plan.get("sequence"),
                    "variant_id": plan.get("variant_id"),
                    "record": str(path),
                }
            )
    return references


def run_benchmark(
    matrix: BenchmarkMatrix,
    *,
    resume_run_id: str | None = None,
    max_new_runs: int | None = None,
    retry_failed: bool = False,
    new_campaign: bool = False,
    scenario_runner: Callable[[Scenario], dict[str, Any]] = run_scenario,
    benchmark_root: Path = BENCHMARK_ROOT,
) -> dict[str, Any]:
    if max_new_runs is not None and max_new_runs < 1:
        raise InvestigationError("invalid_benchmark", "max_new_runs must be at least 1")
    if resume_run_id is not None and new_campaign:
        raise InvestigationError(
            "invalid_benchmark", "resume_run_id and new_campaign are mutually exclusive"
        )

    config_bytes = matrix.path.read_bytes()
    config_sha256 = hashlib.sha256(config_bytes).hexdigest()
    scenario_sha256 = hashlib.sha256(matrix.scenario_path.read_bytes()).hexdigest()
    plan = build_plan(matrix)
    base = load_scenario(matrix.scenario_path)
    validate_artifacts = scenario_runner is run_scenario
    input_identity = _campaign_input_identity(base) if validate_artifacts else None
    auto_resumed = False

    with blocking_lock(LOCKS_ROOT / "benchmark-matrix.lock"):
        if resume_run_id is None and not new_campaign:
            resumable, completed, changed_inputs = _matching_campaigns(
                benchmark_root,
                benchmark_sha256=config_sha256,
                scenario_sha256=scenario_sha256,
                plan=plan,
                input_identity=input_identity,
            )
            if len(resumable) > 1:
                raise InvestigationError(
                    "benchmark_resume_ambiguous",
                    "multiple matching incomplete benchmark campaigns exist",
                    details={"run_ids": resumable},
                )
            if resumable:
                resume_run_id = resumable[0]
                auto_resumed = True
            elif completed:
                raise InvestigationError(
                    "benchmark_already_completed",
                    "an identical benchmark campaign already completed; use --new-campaign "
                    "to deliberately repeat it",
                    details={"run_ids": completed},
                )
            elif changed_inputs:
                raise InvestigationError(
                    "benchmark_resume_mismatch",
                    "matching benchmark campaigns use different source or input fingerprints; "
                    "use --resume with restored inputs or --new-campaign",
                    details={"run_ids": changed_inputs},
                )

        run_id = resume_run_id or _new_run_id()
        run_dir = benchmark_root / run_id
        manifest_path = run_dir / "manifest.json"
        summary_path = run_dir / "summary.json"
        progress_path = run_dir / "progress.jsonl"

        if resume_run_id is None:
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "runs").mkdir()
            (run_dir / "attempts").mkdir()
            (run_dir / "benchmark.toml").write_bytes(config_bytes)
            progress_path.touch()
            manifest = {
                "schema_version": BENCHMARK_VERSION,
                "run_id": run_id,
                "name": matrix.name,
                "benchmark_path": str(matrix.path),
                "benchmark_sha256": config_sha256,
                "scenario_path": str(matrix.scenario_path),
                "scenario_sha256": scenario_sha256,
                "input_identity": input_identity,
                "created_at": timestamp(),
                "plan": plan,
            }
            atomic_write_json(manifest_path, manifest)
        else:
            if not manifest_path.is_file():
                raise InvestigationError(
                    "benchmark_resume_missing",
                    f"benchmark run does not exist: {run_id}",
                )
            manifest = read_json(manifest_path)
            if manifest.get("benchmark_sha256") != config_sha256:
                raise InvestigationError(
                    "benchmark_resume_mismatch",
                    "benchmark config changed since the requested run was created",
                )
            if manifest.get("plan") != plan:
                raise InvestigationError(
                    "benchmark_resume_mismatch", "benchmark execution plan changed"
                )
            if manifest.get("scenario_sha256") != scenario_sha256:
                raise InvestigationError(
                    "benchmark_resume_mismatch",
                    "base scenario changed since the requested run was created",
                )
            if manifest.get("input_identity") != input_identity:
                raise InvestigationError(
                    "benchmark_resume_mismatch",
                    "benchmark source or external inputs changed since the campaign started",
                )
            (run_dir / "runs").mkdir(exist_ok=True)
            (run_dir / "attempts").mkdir(exist_ok=True)
            progress_path.touch(exist_ok=True)

        new_runs = 0
        for entry in plan:
            path = _result_path(run_dir, entry)
            existing = read_json(path) if path.is_file() else None
            if existing is not None and existing.get("state") == "succeeded":
                _verify_checkpoint(path, existing, artifacts=validate_artifacts)
                continue
            if existing is not None:
                existing_code = (existing.get("error") or {}).get("code")
                retryable = existing_code in LIFECYCLE_BLOCKER_CODES or retry_failed
                if not retryable:
                    continue
            if max_new_runs is not None and new_runs >= max_new_runs:
                break

            attempt = _next_attempt_number(run_dir, entry, existing)
            effective = _effective_scenario(base, matrix, entry)
            started_at = timestamp()
            host_before: dict[str, Any] | None = None
            try:
                if (
                    validate_artifacts
                    and _campaign_input_identity(base) != input_identity
                ):
                    raise InvestigationError(
                        "benchmark_inputs_changed",
                        "benchmark source or external inputs changed during the campaign",
                    )
                host_before = wait_for_quiet_host(matrix.host)
                result = scenario_runner(effective)
                if result.get("cleanup_failed"):
                    details = dict(result["cleanup_failed"])
                    details.setdefault("run_id", result.get("state", {}).get("run_id"))
                    details.setdefault(
                        "scenario_summary", result.get("scenario_summary")
                    )
                    details.setdefault(
                        "scenario_progress", result.get("scenario_progress")
                    )
                    details.setdefault("log_diagnostics", result.get("log_diagnostics"))
                    details.setdefault("provenance", result.get("provenance"))
                    raise InvestigationError(
                        "cleanup_failed",
                        "scenario cleanup failed during benchmark",
                        details=details,
                    )
                if (
                    validate_artifacts
                    and _campaign_input_identity(base) != input_identity
                ):
                    raise InvestigationError(
                        "benchmark_inputs_changed",
                        "benchmark source or external inputs changed during a scenario",
                        details={
                            "run_id": result.get("state", {}).get("run_id"),
                            "scenario_summary": result.get("scenario_summary"),
                            "scenario_progress": result.get("scenario_progress"),
                            "log_diagnostics": result.get("log_diagnostics"),
                            "provenance": result.get("provenance"),
                        },
                    )
                record = {
                    "plan": entry,
                    "attempt": attempt,
                    "disposition": "accepted",
                    "state": "succeeded",
                    "started_at": started_at,
                    "finished_at": timestamp(),
                    "host_before": host_before,
                    "host_after": host_snapshot(),
                    "scenario_run_id": result.get("state", {}).get("run_id"),
                    "scenario_summary": result.get("scenario_summary"),
                    "scenario_progress": result.get("scenario_progress"),
                    "log_diagnostics": result.get("log_diagnostics"),
                    "provenance": result.get("provenance"),
                    "metrics": _metrics(result),
                    "error": None,
                }
            except InvestigationError as exc:
                disposition = (
                    "retryable" if exc.code in LIFECYCLE_BLOCKER_CODES else "rejected"
                )
                record = {
                    "plan": entry,
                    "attempt": attempt,
                    "disposition": disposition,
                    "state": "failed",
                    "started_at": started_at,
                    "finished_at": timestamp(),
                    "host_before": host_before,
                    "host_after": host_snapshot(),
                    "scenario_run_id": exc.details.get("run_id"),
                    "scenario_summary": exc.details.get("scenario_summary"),
                    "scenario_progress": exc.details.get("scenario_progress"),
                    "log_diagnostics": exc.details.get("log_diagnostics"),
                    "provenance": exc.details.get("provenance"),
                    "metrics": {},
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                }

            atomic_write_json(_attempt_path(run_dir, entry, attempt), record)
            if record["state"] == "succeeded":
                _write_checkpoint(path, record)
            else:
                atomic_write_json(path, record)
                _checkpoint_path(path).unlink(missing_ok=True)
            new_runs += 1
            with progress_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                os.fsync(output.fileno())

            lifecycle_blocked = record.get("disposition") == "retryable"
            if lifecycle_blocked or (
                record["state"] == "failed" and not matrix.continue_on_failure
            ):
                break

        records: list[dict[str, Any]] = []
        for entry in plan:
            path = _result_path(run_dir, entry)
            if not path.is_file():
                continue
            record = read_json(path)
            if record.get("state") == "succeeded":
                _verify_checkpoint(path, record, artifacts=validate_artifacts)
            records.append(record)

        completed = len(records)
        accepted = sum(record["state"] == "succeeded" for record in records)
        retryable = sum(record.get("disposition") == "retryable" for record in records)
        rejected = sum(
            record["state"] == "failed" and record.get("disposition") != "retryable"
            for record in records
        )
        failed = retryable + rejected
        attempted = sum(1 for _path in (run_dir / "attempts").glob("*/*.json"))
        if accepted == len(plan):
            result_state = "succeeded"
        elif failed:
            result_state = "failed"
        else:
            result_state = "running"
        summary = {
            "schema_version": BENCHMARK_VERSION,
            "run_id": run_id,
            "name": matrix.name,
            "state": result_state,
            "benchmark_path": str(matrix.path),
            "benchmark_sha256": config_sha256,
            "scenario_path": str(matrix.scenario_path),
            "scenario_sha256": scenario_sha256,
            "input_identity_sha256": (
                input_identity.get("sha256") if input_identity is not None else None
            ),
            "run_dir": str(run_dir),
            "manifest": str(manifest_path),
            "progress": str(progress_path),
            "planned_runs": len(plan),
            "completed_runs": completed,
            "accepted_runs": accepted,
            "failed_runs": failed,
            "retryable_runs": retryable,
            "rejected_runs": rejected,
            "attempted_runs": attempted,
            "new_runs": new_runs,
            "auto_resumed": auto_resumed,
            "records": records,
            "aggregate_metrics": _aggregate(records),
            "paired_comparison": _paired_comparison(records, matrix.control_pair),
            "updated_at": timestamp(),
        }
        atomic_write_json(summary_path, summary)
        return summary
