from __future__ import annotations

import json
from pathlib import Path

from squinch_nms_save.cli import main
from squinch_nms_save.output import envelope


def test_inspect_emits_conventional_envelope(save_pair: tuple[Path, Path], capsys) -> None:
    save, _ = save_pair
    assert main(["inspect", str(save)]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["schema_version"] == "1"
    assert output["command"] == "inspect"
    assert output["state"] == "succeeded"
    assert output["data"]["nms_version"] == "7.14"
    assert output["data"]["slot"] == 1


def test_get_and_list(save_pair: tuple[Path, Path], capsys) -> None:
    save, _ = save_pair
    assert main(["get", str(save), "/nested/count"]) == 0
    get_output = json.loads(capsys.readouterr().out)
    assert get_output["data"]["value"] == 7

    assert main(["list", "--directory", str(save.parent)]) == 0
    list_output = json.loads(capsys.readouterr().out)
    assert list_output["data"]["saves"][0]["state"] == "supported"


def test_error_is_structured(save_pair: tuple[Path, Path], capsys) -> None:
    save, _ = save_pair
    assert main(["get", str(save), "/missing"]) == 1
    captured = capsys.readouterr()
    output = json.loads(captured.err)
    assert output["state"] == "error"
    assert output["error"]["code"] == "save_tool_error"


def test_planned_state_is_part_of_cli_contract() -> None:
    assert envelope("projection-plan", "planned")["state"] == "planned"
