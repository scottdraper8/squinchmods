from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.scenario import load_scenario, run_scenario


def test_scenario_executes_expected_positive_and_negative_controls(tmp_path: Path) -> None:
    (tmp_path / "a.MXML").write_text(
        '<Data template="c"><Property name="A" value="1" /></Data>', encoding="utf-8"
    )
    (tmp_path / "b.MXML").write_text(
        '<Data template="c"><Property name="A" value="2" /></Data>', encoding="utf-8"
    )
    scenario = tmp_path / "scenario.toml"
    scenario.write_text(
        """schema_version = 1
id = "comparison-controls"
fail_fast = true

[[steps]]
id = "equal-control"
operation = "compare"
left = "a.MXML"
right = "a.MXML"
comparison = "equal"

[[steps]]
id = "different-control"
operation = "compare"
left = "a.MXML"
right = "b.MXML"
comparison = "different"
""",
        encoding="utf-8",
    )
    result = run_scenario(scenario, None, tmp_path / "run")
    assert result["passed"]
    assert result["complete"]
    assert [step["state"] for step in result["steps"]] == ["succeeded", "succeeded"]
    assert "differences" not in result["steps"][1]["data"]
    detailed = json.loads(Path(result["steps"][1]["result_path"]).read_text(encoding="utf-8"))
    assert detailed["data"]["difference_count"] == 1
    assert detailed["data"]["differences"]


def test_scenario_rejects_duplicate_step_ids(tmp_path: Path) -> None:
    scenario = tmp_path / "bad.toml"
    scenario.write_text(
        """schema_version = 1
id = "bad"
[[steps]]
id = "same"
operation = "compare"
[[steps]]
id = "same"
operation = "compare"
""",
        encoding="utf-8",
    )
    with pytest.raises(InvestigationError, match="unique"):
        load_scenario(scenario)
