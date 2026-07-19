from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[5] / ".github" / "workflows" / "qa-remote.yml"


class TestRemoteWorkflow:
    def _workflow(self) -> dict:
        return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    def test_dispatch_inputs_and_run_name(self):
        doc = self._workflow()

        assert doc["run-name"] == "qa-${{ inputs.run_id }}"
        inputs = doc["on"]["workflow_dispatch"]["inputs"]
        assert inputs["run_id"]["required"] == "true"
        assert inputs["mod"]["required"] == "true"
        assert set(inputs) == {"run_id", "mod", "target", "profile"}

    def test_checkout_and_toolchain_shape(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]

        checkout = next(s for s in steps if s.get("uses") == "actions/checkout@v5")
        assert checkout["with"]["submodules"] == "recursive"

        java = next(s for s in steps if s.get("uses") == "actions/setup-java@v5")
        assert java["with"]["distribution"] == "temurin"
        assert java["with"]["java-version"] == "21.0.11+10.0.LTS"

        python = next(s for s in steps if s.get("uses") == "actions/setup-python@v6")
        assert python["with"]["python-version"] == "3.11"

    def test_run_step_uses_external_run_id(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        run_step = next(s for s in steps if s.get("name") == "Run QA")
        script = run_step["run"]

        assert run_step["if"] == "env.RUN_ID_VALID == 'true'"
        assert 'python -m squinch_qa run "$MOD"' in script
        assert '--run-id "$RUN_ID"' in script
        assert '--repo-root "$GITHUB_WORKSPACE"' in script
        assert "QA_EXIT=$qa_exit" in script
        assert "exit 0" in script

    def test_run_id_validation_guards_upload_path(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        validate = next(s for s in steps if s.get("name") == "Validate run id")
        script = validate["run"]

        assert "^[0-9]+-[0-9a-f]{8}$" in script
        assert "RUN_ID_VALID=true" in script
        assert "RUN_ID_VALID=false" in script
        assert "QA_EXIT=2" in script

    def test_initializes_artifact_before_toolchain_steps(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        names = [s["name"] for s in steps if "name" in s]

        assert names.index("Initialize QA artifact") < names.index("Set up Java")
        init = next(s for s in steps if s.get("name") == "Initialize QA artifact")
        assert init["if"] == "env.RUN_ID_VALID == 'true'"
        assert "qa-manifest.json" in init["run"]
        assert "result.json" in init["run"]
        assert 'run_dir="games/minecraft/qa-state/runs/$RUN_ID"' in init["run"]
        assert "QA_EXIT=1" in init["run"]

    def test_artifact_upload_is_always_and_matches_downloader(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        upload = next(s for s in steps if s.get("name") == "Upload QA artifact")

        assert upload["if"] == "always() && env.RUN_ID_VALID == 'true'"
        assert upload["with"]["action"] == "actions/upload-artifact@v6"

        # wretry.action's `with` input is itself a nested YAML block, parsed by
        # the action at runtime rather than by the workflow schema.
        inner = yaml.safe_load(upload["with"]["with"])
        assert inner["name"] == "qa-${{ inputs.run_id }}"
        assert inner["path"] == "games/minecraft/qa-state/runs/${{ inputs.run_id }}/"
        assert inner["include-hidden-files"] is True
        assert inner["if-no-files-found"] == "error"

    def test_artifact_upload_retries_on_transient_failure(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        upload = next(s for s in steps if s.get("name") == "Upload QA artifact")

        assert upload["uses"] == "Wandalen/wretry.action@v3.8.0"
        assert int(upload["with"]["attempt_limit"]) > 1

    def test_final_step_preserves_qa_exit_code(self):
        steps = self._workflow()["jobs"]["qa"]["steps"]
        final = steps[-1]

        assert final["name"] == "Preserve QA exit code"
        assert final["if"] == "always()"
        assert final["run"] == 'exit "${QA_EXIT:-1}"'
