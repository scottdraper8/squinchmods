from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
import uuid

from .errors import CleanupError, InvestigationError
from .paths import STATE_ROOT, WORKTREES_ROOT
from .scenario import Scenario, run_scenario
from .state import atomic_write_json

COMPARISONS_ROOT = STATE_ROOT / "comparisons"
EXACT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
VOLATILE_RESULT_FIELDS = frozenset(
    {
        "elapsed_seconds",
        "feature_cpu_nanos",
        "finished_at",
        "generation_seconds",
        "poll_ticks",
        "probe_seconds",
        "profile",
        "request_id",
        "run_id",
        "started_at",
        "submitted_at",
        "timestamp",
        "timing",
        "total_seconds",
    }
)
PATH_FIELDS = frozenset(
    {
        "archive_artifact",
        "archive_path",
        "artifact_path",
        "fixture_metadata_path",
        "level_dat",
        "level_name",
        "log_path",
        "manifest",
        "materialization_path",
        "overlay_path",
        "path",
        "project",
        "root",
        "world_dir",
    }
)


def _comparison_id() -> str:
    prefix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"compare-{prefix}-{uuid.uuid4().hex[:10]}"


def _git(project: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise InvestigationError(
            "comparison_git_failed",
            f"git {' '.join(arguments)} failed for {project}: {stderr}",
        ) from exc
    return result.stdout.strip()


def resolve_exact_commit(project: Path, value: str, label: str) -> str:
    if EXACT_SHA.fullmatch(value) is None:
        raise InvestigationError(
            "comparison_commit_invalid",
            f"{label} must be a full 40-character hexadecimal commit SHA",
        )
    resolved = _git(project, "rev-parse", "--verify", f"{value}^{{commit}}").lower()
    if resolved != value.lower():
        raise InvestigationError(
            "comparison_commit_invalid", f"{label} did not resolve to the exact requested commit"
        )
    return resolved


def normalize_result(value: Any) -> Any:
    """Remove request identity and timing noise while preserving measured behavior and list order."""
    if isinstance(value, dict):
        return {
            key: normalize_result(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_RESULT_FIELDS
        }
    if isinstance(value, list):
        return [normalize_result(item) for item in value]
    return value


def normalize_scenario_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "steps": [
            normalize_result(
                {
                    "id": step.get("id"),
                    "type": step.get("type"),
                    "state": step.get("state"),
                    "result": step.get("result"),
                }
            )
            for step in steps
        ]
    }


def structured_diff(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": path, "kind": "type", "left": left, "right": right}]
    if isinstance(left, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left:
                differences.append({"path": child, "kind": "added", "right": right[key]})
            elif key not in right:
                differences.append({"path": child, "kind": "removed", "left": left[key]})
            else:
                differences.extend(structured_diff(left[key], right[key], child))
        return differences
    if isinstance(left, list):
        differences = []
        common = min(len(left), len(right))
        for index in range(common):
            differences.extend(structured_diff(left[index], right[index], f"{path}[{index}]"))
        for index in range(common, len(left)):
            differences.append(
                {"path": f"{path}[{index}]", "kind": "removed", "left": left[index]}
            )
        for index in range(common, len(right)):
            differences.append(
                {"path": f"{path}[{index}]", "kind": "added", "right": right[index]}
            )
        return differences
    if left != right:
        return [{"path": path, "kind": "changed", "left": left, "right": right}]
    return []


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fingerprint(value: Any) -> dict[str, Any]:
    return {"sha256": _sha256_json(value), "value": value}


def _without_paths(value: Any, worktree: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_paths(item, worktree)
            for key, item in sorted(value.items())
            if key not in PATH_FIELDS
        }
    if isinstance(value, list):
        return [_without_paths(item, worktree) for item in value]
    if isinstance(value, str):
        return value.replace(str(worktree), "<comparison-worktree>")
    return value


def _seconds(started: str | None, finished: str | None) -> float | None:
    if not started or not finished:
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((finish - start).total_seconds(), 6)


def _timings(result: dict[str, Any]) -> dict[str, Any]:
    state = result["state"]
    steps = []
    for step in result["steps"]:
        regions = step.get("result", {}).get("regions", [])
        steps.append(
            {
                "id": step.get("id"),
                "duration_seconds": _seconds(step.get("started_at"), step.get("finished_at")),
                "region_elapsed_seconds": [item.get("elapsed_seconds") for item in regions],
                "measurements": step.get("result", {}).get("timing"),
                "profile": step.get("result", {}).get("profile"),
            }
        )
    return {
        "server_lifetime_seconds": _seconds(
            state.get("started_at"), state.get("stopped_at") or state.get("finished_at")
        ),
        "lifecycle": state.get("timings", {}),
        "steps": steps,
    }


def _probe_fingerprint(provenance: dict[str, Any], worktree: Path) -> dict[str, Any]:
    overlay = provenance.get("probe_overlay", {})
    value = {
        "packs": [
            {
                key: pack.get(key)
                for key in (
                    "id",
                    "version",
                    "manifest_sha256",
                    "content_sha256",
                    "inputs",
                    "mixins",
                    "capabilities",
                )
            }
            for pack in overlay.get("packs", [])
        ],
        "mixins": overlay.get("mixins", []),
        "sentinel": overlay.get("sentinel"),
    }
    return _fingerprint(_without_paths(value, worktree))


def _side_record(
    label: str,
    commit: str,
    tree: str,
    worktree: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    provenance = result["provenance"]
    normalized = normalize_scenario_steps(result["steps"])
    environment = {
        key: provenance.get(key)
        for key in ("java", "gradle", "jvm_arguments", "mods", "launch_command")
    }
    inputs = {
        "scenario": provenance.get("scenario"),
        "datapacks": provenance.get("datapacks", []),
        "candidate_inputs": provenance.get("candidate_inputs", []),
        "rtf_fixture": result.get("rtf_fixture"),
        "world_identity": result.get("world_identity"),
    }
    code = {
        "commit": commit,
        "tree": tree,
        "captured": provenance.get("code"),
    }
    state = result["state"]
    return {
        "label": label,
        "commit": commit,
        "tree": tree,
        "run_id": state["run_id"],
        "artifact_dir": state["artifact_dir"],
        "scenario_summary": result["scenario_summary"],
        "cleanup": state.get("cleanup"),
        "normalized_sha256": _sha256_json(normalized),
        "normalized": normalized,
        "fingerprints": {
            "code": _fingerprint(_without_paths(code, worktree)),
            "environment": _fingerprint(_without_paths(environment, worktree)),
            "input": _fingerprint(_without_paths(inputs, worktree)),
            "probe": _probe_fingerprint(provenance, worktree),
            "timing": _fingerprint(_timings(result)),
        },
    }


def _add_worktree(project: Path, path: Path, commit: str) -> None:
    if path.exists() or path.is_symlink():
        raise InvestigationError("comparison_worktree_exists", f"worktree target exists: {path}")
    _git(project, "worktree", "add", "--detach", str(path), commit)
    if path.is_symlink() or not path.is_dir():
        raise InvestigationError("comparison_worktree_invalid", f"invalid worktree: {path}")
    actual = _git(path, "rev-parse", "HEAD")
    if actual != commit or _git(path, "status", "--porcelain=v1", "--untracked-files=all"):
        raise InvestigationError(
            "comparison_worktree_invalid", f"new worktree did not match clean commit {commit}: {path}"
        )


def _remove_clean_worktree(project: Path, root: Path, path: Path) -> None:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if (
        path.is_symlink()
        or not path.is_dir()
        or resolved.parent != resolved_root
        or path.name not in {"before", "after"}
    ):
        raise CleanupError(
            "comparison worktree ownership validation failed", details={"path": str(path)}
        )
    status = _git(path, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise CleanupError(
            "comparison worktree changed unexpectedly; preserving it",
            details={"path": str(path), "status": status.splitlines()},
        )
    _git(project, "worktree", "remove", str(path))
    if path.exists() or path.is_symlink():
        raise CleanupError(
            "git reported worktree removal but the path remains", details={"path": str(path)}
        )


def _prepare_owned_roots() -> None:
    state_root = STATE_ROOT.resolve()
    for path in (WORKTREES_ROOT, COMPARISONS_ROOT):
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.resolve().parent != state_root:
            raise InvestigationError(
                "comparison_root_invalid", f"comparison state root failed ownership validation: {path}"
            )


ScenarioRunner = Callable[[Scenario], dict[str, Any]]


def run_exact_comparison(
    project: Path,
    before: str,
    after: str,
    scenario: Scenario,
    *,
    scenario_runner: ScenarioRunner = run_scenario,
) -> dict[str, Any]:
    before = resolve_exact_commit(project, before, "before")
    after = resolve_exact_commit(project, after, "after")
    if before == after:
        raise InvestigationError("comparison_commit_invalid", "before and after commits are equal")

    _prepare_owned_roots()
    comparison_id = _comparison_id()
    worktree_root = WORKTREES_ROOT / comparison_id
    artifact_dir = COMPARISONS_ROOT / comparison_id
    summary_path = artifact_dir / "comparison-summary.json"
    worktree_root.mkdir(parents=True, exist_ok=False)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    paths = {"before": worktree_root / "before", "after": worktree_root / "after"}
    created: list[str] = []
    preserved: set[str] = set()
    sides: dict[str, dict[str, Any]] = {}
    current: str | None = None
    failure: BaseException | None = None
    cleanup_errors: list[dict[str, Any]] = []

    def write_summary(state: str, error: dict[str, Any] | None = None) -> None:
        atomic_write_json(
            summary_path,
            {
                "comparison_id": comparison_id,
                "state": state,
                "project": str(project),
                "scenario": str(scenario.path),
                "before": before,
                "after": after,
                "sides": sides,
                "preserved_worktrees": [str(paths[label]) for label in sorted(preserved)],
                "cleanup_errors": cleanup_errors,
                "error": error,
            },
        )

    try:
        for label, commit in (("before", before), ("after", after)):
            current = label
            try:
                _add_worktree(project, paths[label], commit)
            except BaseException:
                if paths[label].exists() or paths[label].is_symlink():
                    created.append(label)
                    preserved.add(label)
                raise
            created.append(label)
            current = None
        write_summary("running")
        for label, commit in (("before", before), ("after", after)):
            current = label
            selected = replace(scenario, project=paths[label], retention="keep-on-failure")
            result = scenario_runner(selected)
            tree = _git(paths[label], "rev-parse", "HEAD^{tree}")
            sides[label] = _side_record(label, commit, tree, paths[label], result)
            write_summary("running")
            current = None
        if sides["before"]["fingerprints"]["probe"]["sha256"] != sides["after"]["fingerprints"]["probe"]["sha256"]:
            raise InvestigationError(
                "comparison_probe_mismatch", "before and after did not inject the identical probe inputs"
            )
        if sides["before"]["fingerprints"]["input"]["sha256"] != sides["after"]["fingerprints"]["input"]["sha256"]:
            raise InvestigationError(
                "comparison_input_mismatch", "before and after did not use identical scenario inputs"
            )
        left = sides["before"]["normalized"]
        right = sides["after"]["normalized"]
        differences = structured_diff(left, right)
        result = {
            "comparison_id": comparison_id,
            "artifact_dir": str(artifact_dir),
            "summary_path": str(summary_path),
            "equal": not differences,
            "difference_count": len(differences),
            "differences": differences,
            "normalization": {
                "removed_fields": sorted(VOLATILE_RESULT_FIELDS),
                "list_order": "preserved",
                "numbers": "exact",
            },
            "equivalence": {
                "input_fingerprints_equal": True,
                "probe_fingerprints_equal": True,
                "behavior": "normalized structured equality",
            },
            "left": sides["before"],
            "right": sides["after"],
        }
    except BaseException as exc:
        failure = exc
        if current is not None:
            preserved.add(current)
    finally:
        for label in reversed(created):
            if label in preserved:
                continue
            try:
                _remove_clean_worktree(project, worktree_root, paths[label])
            except (CleanupError, InvestigationError) as exc:
                preserved.add(label)
                cleanup_errors.append(
                    {
                        "path": str(paths[label]),
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
        if not preserved:
            try:
                worktree_root.rmdir()
            except OSError as exc:
                cleanup_errors.append(
                    {"path": str(worktree_root), "code": "rmdir_failed", "message": str(exc)}
                )
        error_value = None
        if failure is not None:
            error_value = {
                "type": type(failure).__name__,
                "message": str(failure),
            }
        write_summary("failed" if failure or cleanup_errors else "succeeded", error_value)

    if failure is not None:
        if isinstance(failure, InvestigationError):
            failure.details.update(
                {
                    "comparison_id": comparison_id,
                    "artifact_dir": str(artifact_dir),
                    "summary_path": str(summary_path),
                    "preserved_worktrees": [str(paths[label]) for label in sorted(preserved)],
                }
            )
        raise failure
    if cleanup_errors:
        raise CleanupError(
            "comparison worktree cleanup did not complete",
            details={
                "comparison_id": comparison_id,
                "artifact_dir": str(artifact_dir),
                "summary_path": str(summary_path),
                "preserved_worktrees": [str(paths[label]) for label in sorted(preserved)],
                "cleanup_errors": cleanup_errors,
            },
        )
    result["preserved_worktrees"] = []
    write_summary("succeeded")
    # The final summary owns the complete comparison, including normalized sides and differences.
    final_summary = {
        **json.loads(summary_path.read_text(encoding="utf-8")),
        "result": result,
    }
    atomic_write_json(summary_path, final_summary)
    return result
