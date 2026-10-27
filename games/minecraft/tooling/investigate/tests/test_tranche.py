from __future__ import annotations

import json
from pathlib import Path

import pytest
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.tranche import prepare_owned_directory


def test_owned_output_rejects_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "tranche"
    workspace.mkdir()
    (workspace / ".tranche.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tranche": "output-test",
                "workspace": str(workspace),
            }
        ),
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "minecraft").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("SQUINCH_TRANCHE", "output-test")
    monkeypatch.setenv("SQUINCH_TRANCHE_WORKSPACE", str(workspace))

    with pytest.raises(InvestigationError, match="output directory is unsafe"):
        prepare_owned_directory("minecraft", "investigate")
    assert not (outside / "investigate").exists()
