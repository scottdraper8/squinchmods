from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from squinch_qa.artifacts import sha256_file
from squinch_qa.errors import ReplaceError, ValidationError
from squinch_qa.replace._pathsafe import assert_within
from squinch_qa.replace.world_hash import world_hash

PROMOTABLE_STATUSES = ("pass", "expected_failure")


@dataclass
class ValidatedJob:
    mod_id: str
    target_id: str
    test_id: str
    job_dir: Path
    status: str
    world_dir: Path | None
    jar_path: Path | None


def _load_json(path: Path, *, reason: str, what: str) -> dict:
    if not path.is_file():
        raise ValidationError(reason=reason, message=f"missing {what}: {path}")
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValidationError(
            reason=reason, message=f"malformed {what}: {path} ({e})"
        ) from e


def _safe_relpath(run_dir: Path, relpath: str, *, what: str) -> Path:
    try:
        return assert_within(run_dir, run_dir / relpath)
    except ReplaceError as e:
        raise ValidationError(
            reason="path_traversal", message=f"{what} escapes run dir: {relpath} ({e})"
        ) from e


def validate(run_dir: Path, target_id: str, test_id: str) -> ValidatedJob:
    """Validate a single completed job before it's eligible for promotion.

    Checks, in order: the run-level manifest exists and lists this job; its
    manifest/result paths don't escape run_dir; the per-job manifest and
    result agree with each other and with the run manifest on identity; the
    job's status is promotable; and, if present, the jar and world hashes
    recorded in the manifest match what's actually on disk. Raises
    ValidationError(reason=...) on the first failure.
    """
    run_manifest = _load_json(
        run_dir / "qa-manifest.json", reason="missing_run_manifest", what="run manifest"
    )

    matrix_id = f"{target_id}/{test_id}"
    job_ref = next(
        (j for j in run_manifest.get("jobs", []) if j.get("matrix_id") == matrix_id),
        None,
    )
    if job_ref is None:
        raise ValidationError(
            reason="job_not_found",
            message=f"{matrix_id} not listed in {run_dir}/qa-manifest.json",
        )

    manifest_path = _safe_relpath(
        run_dir, job_ref["manifest"], what="job manifest path"
    )
    result_path = _safe_relpath(run_dir, job_ref["result"], what="job result path")

    job_manifest = _load_json(
        manifest_path, reason="missing_job_manifest", what="job manifest"
    )
    job_result = _load_json(result_path, reason="missing_job_result", what="job result")

    if job_manifest.get("matrix_id") != matrix_id:
        raise ValidationError(
            reason="matrix_id_mismatch",
            message=f"job manifest matrix_id {job_manifest.get('matrix_id')!r} != {matrix_id!r}",
        )
    manifest_target_id = job_manifest.get("target", {}).get("id")
    if manifest_target_id != target_id:
        raise ValidationError(
            reason="target_id_mismatch",
            message=f"job manifest target id {manifest_target_id!r} != {target_id!r}",
        )
    manifest_test_id = job_manifest.get("test", {}).get("id")
    if manifest_test_id != test_id:
        raise ValidationError(
            reason="test_id_mismatch",
            message=f"job manifest test id {manifest_test_id!r} != {test_id!r}",
        )
    if job_manifest.get("run_id") != run_manifest.get("run_id"):
        raise ValidationError(
            reason="run_id_mismatch",
            message=(
                f"job manifest run_id {job_manifest.get('run_id')!r} != "
                f"run manifest run_id {run_manifest.get('run_id')!r}"
            ),
        )

    mod_id = run_manifest.get("mod_id")
    if not isinstance(mod_id, str) or not mod_id:
        raise ValidationError(
            reason="missing_mod_id",
            message=f"run manifest has invalid mod_id {mod_id!r}",
        )
    job_mod_id = job_manifest.get("mod", {}).get("id")
    if job_mod_id != mod_id:
        raise ValidationError(
            reason="mod_id_mismatch",
            message=f"job manifest mod id {job_mod_id!r} != run manifest {mod_id!r}",
        )

    status = job_manifest.get("test", {}).get("status")
    result_status = job_result.get("status")
    if result_status != status:
        raise ValidationError(
            reason="status_mismatch",
            message=f"job result status {result_status!r} != job manifest {status!r}",
        )
    if status not in PROMOTABLE_STATUSES:
        raise ValidationError(
            reason="status_not_promotable",
            message=f"status {status!r} is not one of {PROMOTABLE_STATUSES}",
        )

    job_dir = manifest_path.parent
    artifacts = job_result.get("artifacts", [])
    for rel in artifacts:
        _safe_relpath(job_dir, rel, what="artifact path")
    for rel in job_result.get("logs", []):
        _safe_relpath(job_dir, rel, what="log path")

    jar_path: Path | None = None
    jar_rel = next((a for a in artifacts if a.endswith(".jar")), None)
    if jar_rel is not None:
        jar_path = job_dir / jar_rel
        expected_jar_sha256 = job_manifest.get("mod", {}).get("jar_sha256")
        actual_jar_sha256 = sha256_file(jar_path)
        if expected_jar_sha256 != actual_jar_sha256:
            raise ValidationError(
                reason="jar_hash_mismatch",
                message=f"jar_sha256 {actual_jar_sha256} != manifest {expected_jar_sha256}",
            )

    world_dir: Path | None = None
    if "world" in artifacts:
        world_dir = job_dir / "world"
        expected_world_sha256 = job_manifest.get("world_sha256")
        actual_world_sha256 = world_hash(world_dir)
        if expected_world_sha256 != actual_world_sha256:
            raise ValidationError(
                reason="world_hash_mismatch",
                message=f"world_sha256 {actual_world_sha256} != manifest {expected_world_sha256}",
            )

    return ValidatedJob(
        mod_id=mod_id,
        target_id=target_id,
        test_id=test_id,
        job_dir=job_dir,
        status=status,
        world_dir=world_dir,
        jar_path=jar_path,
    )
