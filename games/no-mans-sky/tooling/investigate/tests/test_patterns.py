from __future__ import annotations

import json
import struct
import subprocess
from pathlib import Path

import pytest

from squinch_nms_investigate import patterns
from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.patterns import inspect_pattern_catalog


def _catalog(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _pe(payload: bytes, *, image_base: int = 0x140000000) -> bytes:
    data = bytearray(0x400 + len(payload))
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    struct.pack_into("<H", data, 0x86, 1)
    struct.pack_into("<H", data, 0x94, 0xF0)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<Q", data, 0xB0, image_base)
    section = 0x188
    data[section : section + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section + 8, len(payload), 0x1000, len(payload), 0x400)
    struct.pack_into("<I", data, section + 36, 0x60000020)
    data[0x400:] = payload
    return bytes(data)


def test_pattern_catalog_records_unique_wildcard_match(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe(b"\x00\x48\x89\xaa\x24\x10\xcc"))
    catalog = _catalog(
        tmp_path / "data.json",
        [{"name": "Query::Run", "signature": "48 89 ? 24 ??", "mangled_name": "?Run"}],
    )
    result = inspect_pattern_catalog(executable, catalog, ["Query::Run"], tmp_path / "evidence")
    assert result["all_matched"]
    assert result["all_unique"]
    assert result["results"][0]["matches"] == [
        {
            "file_offset": 0x401,
            "bytes": "48 89 AA 24 10",
            "pe_location": {
                "section": ".text",
                "relative_virtual_address": 0x1001,
                "virtual_address": 0x140001001,
            },
        }
    ]
    assert result["pe"]["format"] == "PE32+"
    assert Path(result["catalog_snapshot"]).read_bytes() == catalog.read_bytes()


def test_pattern_catalog_reports_nonunique_and_unmatched_signatures(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe(b"\x48\x89\x48\x89"))
    catalog = _catalog(
        tmp_path / "data.json",
        [
            {"name": "Duplicate", "signature": "48 89"},
            {"name": "Missing", "signature": "CC DD"},
        ],
    )
    result = inspect_pattern_catalog(
        executable, catalog, ["Duplicate", "Missing"], tmp_path / "evidence"
    )
    assert not result["all_matched"]
    assert not result["all_unique"]
    assert [item["match_count"] for item in result["results"]] == [2, 0]


def test_pattern_catalog_rejects_missing_name_and_invalid_token(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe(b"MZ"))
    catalog = _catalog(tmp_path / "data.json", [{"name": "Known", "signature": "GG"}])
    with pytest.raises(InvestigationError) as missing:
        inspect_pattern_catalog(executable, catalog, ["Unknown"], tmp_path / "missing")
    assert missing.value.code == "pattern_name_not_found"

    with pytest.raises(InvestigationError) as invalid:
        inspect_pattern_catalog(executable, catalog, ["Known"], tmp_path / "invalid")
    assert invalid.value.code == "invalid_signature"


def test_pattern_catalog_retains_bounded_disassembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe(b"\x48\x89\xcc"))
    catalog = _catalog(tmp_path / "data.json", [{"name": "Query::Run", "signature": "48 89"}])

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        output = "GNU objdump test\n" if command[1] == "--version" else "bounded disassembly\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(patterns.shutil, "which", lambda _: "/usr/bin/objdump")
    monkeypatch.setattr(patterns.subprocess, "run", fake_run)
    result = inspect_pattern_catalog(
        executable,
        catalog,
        ["Query::Run"],
        tmp_path / "evidence",
        disassemble_bytes=32,
    )
    disassembly = result["results"][0]["disassembly"]
    assert result["disassembler"]["version"] == "GNU objdump test"
    assert disassembly["preferred_virtual_address_start"] == 0x140001000
    assert disassembly["preferred_virtual_address_stop"] == 0x140001020
    assert Path(disassembly["path"]).read_text(encoding="utf-8") == "bounded disassembly\n"
