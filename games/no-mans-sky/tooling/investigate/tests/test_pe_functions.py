from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.pe_functions import inspect_functions, parse_address


def _section(
    data: bytearray,
    offset: int,
    name: bytes,
    *,
    virtual_size: int,
    virtual_address: int,
    raw_size: int,
    raw_offset: int,
    characteristics: int,
) -> None:
    data[offset : offset + 8] = name.ljust(8, b"\0")
    struct.pack_into("<IIII", data, offset + 8, virtual_size, virtual_address, raw_size, raw_offset)
    struct.pack_into("<I", data, offset + 36, characteristics)


def _pe() -> bytes:
    base = 0x140000000
    data = bytearray(0xA00)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    struct.pack_into("<H", data, 0x86, 3)
    struct.pack_into("<H", data, 0x94, 0xF0)
    struct.pack_into("<H", data, 0x96, 0x22)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<Q", data, 0xB0, base)
    struct.pack_into("<II", data, 0xB8, 0x1000, 0x200)
    struct.pack_into("<II", data, 0xD0, 0x4000, 0x400)
    struct.pack_into("<I", data, 0x104, 16)
    _section(
        data,
        0x188,
        b".text",
        virtual_size=0x100,
        virtual_address=0x1000,
        raw_size=0x200,
        raw_offset=0x400,
        characteristics=0x60000020,
    )
    _section(
        data,
        0x1B0,
        b".pdata",
        virtual_size=0x18,
        virtual_address=0x2000,
        raw_size=0x200,
        raw_offset=0x600,
        characteristics=0x40000040,
    )
    _section(
        data,
        0x1D8,
        b".rdata",
        virtual_size=0x10,
        virtual_address=0x3000,
        raw_size=0x200,
        raw_offset=0x800,
        characteristics=0x40000040,
    )
    # call base+0x1020; mov rax,[rip-relative base+0x3000]; ret
    data[0x400:0x40D] = b"\xe8\x1b\x00\x00\x00\x48\x8b\x05\xf4\x1f\x00\x00\xc3"
    # mov rax,[rcx+0x3bf0]; ret
    data[0x420:0x428] = b"\x48\x8b\x81\xf0\x3b\x00\x00\xc3"
    struct.pack_into("<III", data, 0x600, 0x1000, 0x100D, 0)
    struct.pack_into("<III", data, 0x60C, 0x1020, 0x1028, 0)
    struct.pack_into("<QQ", data, 0x800, base + 0x1000, base + 0x1020)
    return bytes(data)


def _split_pe() -> bytes:
    data = bytearray(_pe())
    # First fragment falls through into a second unwind fragment, which then returns.
    data[0x400:0x408] = b"\x90\x90\x90\x90\x90\x90\x90\xc3"
    struct.pack_into("<III", data, 0x600, 0x1000, 0x1004, 0)
    struct.pack_into("<III", data, 0x60C, 0x1004, 0x1008, 0)
    return bytes(data)


def test_inspect_functions_retains_calls_references_callers_and_vtable(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe())
    result = inspect_functions(
        executable,
        [0x140001000, 0x140001020],
        tmp_path / "evidence",
        include_callers=True,
        vtable_address=0x140003000,
        vtable_count=2,
        memory_displacements=[0x3BF0, 0x2222],
    )

    assert result["function_count"] == 2
    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    first, second = report["functions"]
    assert first["direct_calls"] == [
        {
            "instruction": 0x140001000,
            "target": 0x140001020,
            "target_function_start": 0x140001020,
            "target_function_stop": 0x140001028,
        }
    ]
    assert first["ip_relative_memory_references"] == [
        {"instruction": 0x140001005, "target": 0x140003000}
    ]
    assert second["direct_callers"] == [
        {"instruction": 0x140001000, "target_fragment_start": 0x140001020}
    ]
    assert report["memory_displacement_references"] == {
        "0x3BF0": [
            {
                "instruction": 0x140001020,
                "function_start": 0x140001020,
                "function_stop": 0x140001028,
                "text": "mov rax,[rcx+3BF0h]",
            }
        ],
        "0x2222": [],
    }
    assert result["memory_displacement_reference_counts"] == {
        "0x3BF0": 1,
        "0x2222": 0,
    }
    assert [entry["target"] for entry in report["vtable"]["entries"]] == [
        0x140001000,
        0x140001020,
    ]
    assert "call 0000000140001020h" in Path(first["disassembly"]["path"]).read_text(
        encoding="utf-8"
    )


def test_inspect_functions_scans_preferred_address_references(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe())
    result = inspect_functions(
        executable,
        [],
        tmp_path / "evidence",
        reference_addresses=[0x140003000, 0x140001020],
    )

    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    references = report["preferred_address_references"]
    assert references["0x140003000"]["instructions"] == [
        {
            "instruction": 0x140001005,
            "function_start": 0x140001000,
            "function_stop": 0x14000100D,
            "text": "mov rax,[rel 140003000h]",
        }
    ]
    assert references["0x140003000"]["data"] == []
    assert references["0x140001020"]["instructions"] == []
    assert references["0x140001020"]["data"] == [
        {
            "section": ".rdata",
            "address": 0x140003008,
            "file_offset": 0x808,
            "target": 0x140001020,
        }
    ]
    assert result["preferred_address_reference_counts"] == {
        "0x140003000": {"instructions": 1, "data": 0},
        "0x140001020": {"instructions": 0, "data": 1},
    }


def test_inspect_functions_rejects_unbounded_address(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_pe())
    with pytest.raises(InvestigationError) as error:
        inspect_functions(executable, [0x140001100], tmp_path / "evidence")
    assert error.value.code == "function_not_found"


def test_inspect_functions_follows_fragment_fallthrough(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(_split_pe())
    result = inspect_functions(executable, [0x140001000], tmp_path / "evidence")
    assert result["functions"][0]["fragment_count"] == 2


def test_parse_address_accepts_hex_and_rejects_invalid() -> None:
    assert parse_address("0x140001000") == 0x140001000
    with pytest.raises(InvestigationError) as error:
        parse_address("planet")
    assert error.value.code == "invalid_address"
