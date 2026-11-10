from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))
MODULE = importlib.import_module("refresh_asset_wiki")


def test_convert_icon_reuses_preview_and_preserves_catalog_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preview = tmp_path / "assets/textures/ui/icons/test.webp"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"preview")

    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "64 32", ""),
    )
    record = MODULE.convert_icon(
        {
            "logical_path": "TEXTURES\\UI//ICONS/TEST.DDS",
            "path": "/source/test.dds",
            "bytes": 123,
            "catalog_icon": True,
        },
        tmp_path,
        reuse_previews=True,
    )

    assert record == {
        "path": "textures/ui/icons/test.dds",
        "preview": "assets/textures/ui/icons/test.webp",
        "width": 64,
        "height": 32,
        "bytes": 123,
        "scope": "icons-directory",
        "category": "icons",
    }
