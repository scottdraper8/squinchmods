from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .errors import InvestigationError
from .executable import inspect_strings
from .hgpak import extract as extract_assets
from .hgpak import inventory as archive_inventory
from .mbin import inspect_mbin, roundtrip
from .mods import (
    analysis_summary,
    analyze_mod,
    conflict_report,
    inventory_mod,
    resolve_deployment_root,
    target_mbin,
    write_analysis_report,
)
from .paths import resolve_game_root
from .runs import write_json
from .toolchain import assert_supported_build
from .xmlmodel import compare_xml, verify_export

STEP_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OPERATIONS = {
    "extract",
    "roundtrip",
    "analyze-mod",
    "conflicts",
    "compare",
    "verify-export",
    "exe-strings",
}
STATES = {"succeeded", "failed", "inconclusive", "error"}


def _strings(value: object, field: str, *, minimum: int = 1) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise InvestigationError(
            "invalid_scenario", f"Scenario {field} must be an array of nonempty strings"
        )
    return value


def load_scenario(path: Path) -> dict:
    source = path.expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise InvestigationError("scenario_not_found", f"Scenario is not a regular file: {source}")
    try:
        value = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InvestigationError(
            "invalid_scenario", f"Could not parse scenario {source}: {exc}"
        ) from exc
    if value.get("schema_version") != 1:
        raise InvestigationError("invalid_scenario", "Scenario schema_version must be 1")
    if not isinstance(value.get("id"), str) or not STEP_ID.fullmatch(value["id"]):
        raise InvestigationError(
            "invalid_scenario", "Scenario id must be a lowercase kebab-case slug"
        )
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        raise InvestigationError(
            "invalid_scenario", "Scenario must contain at least one [[steps]] table"
        )
    seen: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise InvestigationError("invalid_scenario", f"steps[{index}] must be a table")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not STEP_ID.fullmatch(step_id) or step_id in seen:
            raise InvestigationError(
                "invalid_scenario", f"steps[{index}].id must be unique kebab-case"
            )
        seen.add(step_id)
        if step.get("operation") not in OPERATIONS:
            raise InvestigationError("invalid_scenario", f"steps[{index}].operation is unsupported")
        if step.get("expect", "succeeded") not in STATES:
            raise InvestigationError("invalid_scenario", f"steps[{index}].expect is invalid")
    value["source"] = str(source)
    return value


def _relative(base: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InvestigationError("invalid_scenario", f"Scenario {field} must be a path string")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


class Context:
    def __init__(self, game_root: Path | None, run_path: Path) -> None:
        self.game_root = game_root
        self.run_path = run_path
        self._catalog: dict[str, list[str]] | None = None
        self._members: set[str] | None = None

    def game(self) -> Path:
        if self.game_root is None:
            self.game_root = resolve_game_root(None)
        return self.game_root

    def inventory(self) -> tuple[dict[str, list[str]], set[str]]:
        if self._catalog is None:
            self._catalog = archive_inventory(self.game(), self.run_path / "archive-inventory")
            self._members = {member for values in self._catalog.values() for member in values}
        return self._catalog, self._members or set()

    def vanilla_xml(self, targets: list[str], destination: Path) -> dict[str, Path]:
        if not targets:
            return {}
        catalog, _ = self.inventory()
        extracted = extract_assets(targets, catalog, destination / "vanilla-mbin")
        result: dict[str, Path] = {}
        for index, record in enumerate(extracted):
            inspection = inspect_mbin(
                Path(record["path"]), destination / "vanilla-decompiled" / f"{index:04d}"
            )
            if inspection["decompiled"]:
                result[record["logical_path"]] = Path(inspection["decompiled"])
        return result


def _analyze(context: Context, root: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    _, members = context.inventory()
    records = inventory_mod(resolve_deployment_root(root))
    targets = sorted(
        {
            target_mbin(item["logical_path"]) if item["suffix"] == ".exml" else item["logical_path"]
            for item in records
            if (item["suffix"] == ".exml" and target_mbin(item["logical_path"]) in members)
            or (item["suffix"] == ".mbin" and item["logical_path"] in members)
        }
    )
    vanilla = context.vanilla_xml(targets, destination)
    return analyze_mod(
        root, destination / "analysis", current_inventory=members, vanilla_xml=vanilla
    )


def _run_step(context: Context, base: Path, step: dict, destination: Path) -> tuple[str, dict]:
    operation = step["operation"]
    if operation == "extract":
        paths = _strings(step.get("paths"), f"step {step['id']} paths")
        catalog, _ = context.inventory()
        data = {"files": extract_assets(paths, catalog, destination / "extracted")}
        return "succeeded", data
    if operation == "roundtrip":
        assert_supported_build(context.game())
        paths = _strings(step.get("paths"), f"step {step['id']} paths")
        catalog, _ = context.inventory()
        extracted = extract_assets(paths, catalog, destination / "extracted")
        results = [
            roundtrip(Path(item["path"]), destination / "roundtrip" / f"{index:04d}")
            for index, item in enumerate(extracted)
        ]
        passed = all(item["passed"] for item in results)
        return ("succeeded" if passed else "failed"), {"passed": passed, "results": results}
    if operation == "analyze-mod":
        assert_supported_build(context.game())
        analysis = _analyze(
            context,
            _relative(base, step.get("mod_root"), f"step {step['id']} mod_root"),
            destination,
        )
        report = destination / "analysis-report.json"
        write_analysis_report(analysis, report)
        data = analysis_summary(analysis) | {"analysis_report": str(report)}
        return analysis["static_outcome"], data
    if operation == "conflicts":
        assert_supported_build(context.game())
        roots = [
            _relative(base, value, f"step {step['id']} mod_roots")
            for value in _strings(step.get("mod_roots"), f"step {step['id']} mod_roots", minimum=2)
        ]
        analyses = [
            _analyze(context, root, destination / f"mod-{index:04d}")
            for index, root in enumerate(roots)
        ]
        summaries = []
        for index, analysis in enumerate(analyses):
            report = destination / f"mod-{index:04d}" / "analysis-report.json"
            write_analysis_report(analysis, report)
            summaries.append(analysis_summary(analysis) | {"report": str(report)})
        data = {"mods": summaries, **conflict_report(analyses)}
        state = (
            "failed"
            if data["confirmed_conflict_count"]
            else ("inconclusive" if data["potential_conflict_count"] else "succeeded")
        )
        return state, data
    if operation == "compare":
        data = compare_xml(
            _relative(base, step.get("left"), f"step {step['id']} left"),
            _relative(base, step.get("right"), f"step {step['id']} right"),
        )
        expected = step.get("comparison", "any")
        if expected not in {"any", "equal", "different"}:
            raise InvestigationError("invalid_scenario", f"step {step['id']} comparison is invalid")
        met = expected == "any" or data["equal"] == (expected == "equal")
        data.update({"comparison": expected, "comparison_met": met})
        return ("succeeded" if met else "failed"), data
    if operation == "verify-export":
        data = verify_export(
            _relative(base, step.get("patch"), f"step {step['id']} patch"),
            _relative(base, step.get("exported"), f"step {step['id']} exported"),
            _relative(base, step["vanilla"], f"step {step['id']} vanilla")
            if "vanilla" in step
            else None,
        )
        return ("succeeded" if data["passed"] else "failed"), data
    patterns = _strings(step.get("patterns"), f"step {step['id']} patterns")
    data = inspect_strings(
        context.game() / "Binaries/NMS.exe", patterns, limit=step.get("limit", 500)
    )
    require_each = step.get("require_each_pattern", True)
    if not isinstance(require_each, bool):
        raise InvestigationError(
            "invalid_scenario", f"step {step['id']} require_each_pattern must be boolean"
        )
    passed = data["all_patterns_matched"] or not require_each
    data.update({"require_each_pattern": require_each, "expectation_met": passed})
    return ("succeeded" if passed else "failed"), data


def _step_summary(operation: str, data: dict) -> dict:
    if operation == "conflicts":
        return {
            "mods": data["mods"],
            "conflict_free": data["conflict_free"],
            "conflict_count": data["conflict_count"],
            "confirmed_conflict_count": data["confirmed_conflict_count"],
            "potential_conflict_count": data["potential_conflict_count"],
        }
    if operation == "compare":
        return {key: value for key, value in data.items() if key != "differences"}
    if operation == "verify-export":
        summary = {key: value for key, value in data.items() if key != "checks"}
        if "export_vs_vanilla" in summary:
            summary["export_vs_vanilla"] = {
                key: value
                for key, value in summary["export_vs_vanilla"].items()
                if key != "differences"
            }
        return summary
    if operation == "exe-strings":
        return {key: value for key, value in data.items() if key != "matches"}
    return data


def run_scenario(path: Path, game_override: Path | None, run_path: Path) -> dict:
    scenario = load_scenario(path)
    source = Path(scenario["source"])
    configured_game = scenario.get("game_root")
    game_value = game_override or (
        _relative(source.parent, configured_game, "game_root") if configured_game else None
    )
    context = Context(resolve_game_root(game_value) if game_value else None, run_path)
    results: list[dict] = []
    fail_fast = scenario.get("fail_fast", True)
    for step in scenario["steps"]:
        destination = run_path / "steps" / step["id"]
        destination.mkdir(parents=True, exist_ok=False)
        try:
            state, data = _run_step(context, source.parent, step, destination)
            error = None
        except InvestigationError as exc:
            state = "error"
            data = {}
            error = {"code": exc.code, "message": exc.message, "details": exc.details}
        expected = step.get("expect", "succeeded")
        met = state == expected
        full_result = {
            "schema_version": 1,
            "id": step["id"],
            "operation": step["operation"],
            "state": state,
            "expected_state": expected,
            "expectation_met": met,
            "error": error,
            "data": data,
        }
        result_path = destination / "result.json"
        write_json(result_path, full_result)
        results.append(
            {
                "id": step["id"],
                "operation": step["operation"],
                "state": state,
                "expected_state": expected,
                "expectation_met": met,
                "artifact_path": str(destination),
                "result_path": str(result_path),
                "error": error,
                "data": _step_summary(step["operation"], data),
            }
        )
        if fail_fast and not met:
            break
    complete = len(results) == len(scenario["steps"])
    passed = complete and all(result["expectation_met"] for result in results)
    return {
        "scenario_id": scenario["id"],
        "scenario_source": scenario["source"],
        "game_root": str(context.game_root) if context.game_root else None,
        "fail_fast": fail_fast,
        "step_count": len(scenario["steps"]),
        "executed_step_count": len(results),
        "complete": complete,
        "passed": passed,
        "steps": results,
    }
