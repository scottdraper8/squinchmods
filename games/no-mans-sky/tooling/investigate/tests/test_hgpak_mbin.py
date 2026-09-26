from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from squinch_nms_investigate import hgpak, mbin
from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.mbin import VERSION


def test_archive_inventory_extract_and_missing_negative_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "game"
    banks = game / "GAMEDATA/PCBANKS"
    banks.mkdir(parents=True)
    archive = banks / "NMSARC.Test.pak"
    archive.write_bytes(b"pak")
    helper = tmp_path / "fake_hgpak.py"
    helper.write_text(
        """import json, pathlib, sys
args=sys.argv[1:]
if '-L' in args:
    pak=next(value for value in args if value.endswith('.pak'))
    pathlib.Path('filenames.json').write_text(json.dumps({pak:['UI/TEST.MBIN']}))
elif '-U' in args:
    output=pathlib.Path(args[args.index('-O')+1]); output.joinpath('ui').mkdir(parents=True)
    output.joinpath('ui/test.mbin').write_bytes(b'MBIN')
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(hgpak, "hgpak_command", lambda: ["python", str(helper)])
    catalog = hgpak.inventory(game, tmp_path / "inventory")
    records = hgpak.extract(["UI/TEST.MBIN"], catalog, tmp_path / "output")
    assert records[0]["logical_path"] == "ui/test.mbin"
    with pytest.raises(InvestigationError, match="not in the current game"):
        hgpak.locate(["UI/MISSING.MBIN"], catalog)
    with pytest.raises(InvestigationError, match="multiple game archives"):
        hgpak.locate(
            ["UI/TEST.MBIN"],
            {"first.pak": ["ui/test.mbin"], "second.pak": ["ui/test.mbin"]},
        )


def test_mbin_roundtrip_semantic_positive_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "TEST.MBIN"
    source.write_bytes(b"original")

    def fake(arguments: list[str], *, work_dir: Path, timeout: float = 300):
        if arguments[0] == "version":
            return subprocess.CompletedProcess(arguments, 0, "7.01.0.1", "")
        path = Path(arguments[0])
        if path.suffix.casefold() == ".mbin":
            path.with_suffix(".MXML").write_text(
                '<Data template="cTest"><Property name="Value" value="1" /></Data>',
                encoding="utf-8",
            )
        else:
            path.with_suffix(".MBIN").write_bytes(b"rebuilt")
        return subprocess.CompletedProcess(arguments, 0, "converted", "")

    monkeypatch.setattr(mbin, "run_mbincompiler", fake)
    result = mbin.roundtrip(source, tmp_path / "roundtrip")
    assert result["passed"]
    assert result["semantic_comparison"]["equal"]


def test_mbin_roundtrip_reports_decompile_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "STALE.MBIN"
    source.write_bytes(b"stale")

    def fake(arguments: list[str], *, work_dir: Path, timeout: float = 300):
        output = "Unknown MBIN version" if arguments[0] == "version" else "schema error"
        return subprocess.CompletedProcess(arguments, 1, output, "")

    monkeypatch.setattr(mbin, "run_mbincompiler", fake)
    result = mbin.roundtrip(source, tmp_path / "roundtrip-failed")
    assert not result["passed"]
    assert result["failure"] == "decompile-failed"


def test_compiler_version_pattern_accepts_v_prefix() -> None:
    assert VERSION.search("Compiled with MBINCompiler v7.1.0.1").group() == "7.1.0.1"
