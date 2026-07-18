from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_qa.errors import ValidationError
from squinch_qa.replace.validate import validate


def _world_src(tmp_path: Path) -> Path:
    src = tmp_path / "world-src"
    (src / "region").mkdir(parents=True)
    (src / "region" / "r.0.0.mca").write_bytes(b"chunk data")
    return src


class TestValidateHappyPath:
    def test_world_and_jar_promotable(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                    "jar_bytes": b"fake jar bytes",
                }
            ]
        )
        result = validate(run_dir, "neoforge-1.21.1", "pregen")
        assert result.mod_id == "fake-mod"
        assert result.target_id == "neoforge-1.21.1"
        assert result.test_id == "pregen"
        assert result.status == "pass"
        assert result.world_dir is not None and result.world_dir.is_dir()
        assert result.jar_path is not None and result.jar_path.is_file()

    def test_expected_failure_is_promotable(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "expected_failure",
                    "world_src": _world_src(tmp_path),
                }
            ]
        )
        result = validate(run_dir, "neoforge-1.21.1", "pregen")
        assert result.status == "expected_failure"

    def test_no_world_artifact_returns_none_world_dir(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "build", "status": "pass"}
            ]
        )
        result = validate(run_dir, "neoforge-1.21.1", "build")
        assert result.world_dir is None


class TestValidateRejections:
    def test_missing_run_manifest(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "no-manifest-run"
        run_dir.mkdir()
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "t", "x")
        assert exc_info.value.reason == "missing_run_manifest"

    def test_job_not_found(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "nonexistent")
        assert exc_info.value.reason == "job_not_found"

    def test_manifest_path_traversal_rejected(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        run_manifest_path = run_dir / "qa-manifest.json"
        doc = json.loads(run_manifest_path.read_text())
        doc["jobs"][0]["manifest"] = "../../../etc/passwd"
        run_manifest_path.write_text(json.dumps(doc))
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "path_traversal"

    def test_manifest_absolute_path_traversal_rejected(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        # An absolute path takes a different route through Path.__truediv__:
        # `run_dir / "/etc/passwd"` discards run_dir entirely rather than
        # walking out of it via "..", so it has to be caught by assert_within
        # rather than by rejecting "../" segments syntactically.
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        run_manifest_path = run_dir / "qa-manifest.json"
        doc = json.loads(run_manifest_path.read_text())
        doc["jobs"][0]["manifest"] = "/etc/passwd"
        run_manifest_path.write_text(json.dumps(doc))
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "path_traversal"

    def test_malformed_run_manifest_json_rejected(
        self, tmp_path: Path, qa_run_factory
    ) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        run_manifest_path = run_dir / "qa-manifest.json"
        run_manifest_path.write_text("{not valid json")
        with pytest.raises(ValidationError, match="malformed run manifest") as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "missing_run_manifest"

    def test_missing_job_manifest_file(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        (run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "manifest.json").unlink()
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "missing_job_manifest"

    def test_missing_job_result_file(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        (run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "result.json").unlink()
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "missing_job_result"

    def test_matrix_id_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "matrix_id_override": "wrong/id",
                }
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "matrix_id_mismatch"

    def test_run_id_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "run_id_override": "some-other-run",
                }
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "run_id_mismatch"

    def test_target_id_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        manifest_path = (
            run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "manifest.json"
        )
        doc = json.loads(manifest_path.read_text())
        doc["target"]["id"] = "other-target"
        manifest_path.write_text(json.dumps(doc))

        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "target_id_mismatch"

    def test_test_id_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        manifest_path = (
            run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "manifest.json"
        )
        doc = json.loads(manifest_path.read_text())
        doc["test"]["id"] = "other-test"
        manifest_path.write_text(json.dumps(doc))

        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "test_id_mismatch"

    def test_mod_id_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        manifest_path = (
            run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "manifest.json"
        )
        doc = json.loads(manifest_path.read_text())
        doc["mod"]["id"] = "other-mod"
        manifest_path.write_text(json.dumps(doc))

        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "mod_id_mismatch"

    def test_result_status_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        result_path = run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "result.json"
        doc = json.loads(result_path.read_text())
        doc["status"] = "fail"
        result_path.write_text(json.dumps(doc))

        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "status_mismatch"

    @pytest.mark.parametrize("field", ["artifacts", "logs"])
    def test_result_paths_must_not_escape_job_dir(
        self, tmp_path: Path, qa_run_factory, field: str
    ) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "pass"}
            ]
        )
        result_path = run_dir / "jobs" / "neoforge-1.21.1" / "pregen" / "result.json"
        doc = json.loads(result_path.read_text())
        doc[field] = ["../escape"]
        result_path.write_text(json.dumps(doc))

        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "path_traversal"

    def test_status_not_promotable(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {"target_id": "neoforge-1.21.1", "test_id": "pregen", "status": "fail"}
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "status_not_promotable"

    def test_jar_hash_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "jar_bytes": b"real jar",
                    "jar_sha256_override": "0" * 64,
                }
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "jar_hash_mismatch"

    def test_world_hash_mismatch(self, tmp_path: Path, qa_run_factory) -> None:
        run_dir = qa_run_factory(
            jobs=[
                {
                    "target_id": "neoforge-1.21.1",
                    "test_id": "pregen",
                    "status": "pass",
                    "world_src": _world_src(tmp_path),
                    "world_sha256_override": "0" * 64,
                }
            ]
        )
        with pytest.raises(ValidationError) as exc_info:
            validate(run_dir, "neoforge-1.21.1", "pregen")
        assert exc_info.value.reason == "world_hash_mismatch"
