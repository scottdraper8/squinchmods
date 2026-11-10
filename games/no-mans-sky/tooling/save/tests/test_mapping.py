from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import squinch_nms_save.mapping as mapping_module
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.mapping import SaveMapping, acquire_mapping, verify_mapping


def write_mapping(path: Path, version: str = "7.14.0.1") -> Path:
    path.write_text(
        json.dumps(
            {
                "libMBIN_version": version,
                "Mapping": [
                    {"Key": "abc", "Value": "PlayerStateData"},
                    {"Key": "def", "Value": "Name"},
                    {"Key": "dup", "Value": "First"},
                    {"Key": "dup", "Value": "Second"},
                ],
            }
        )
    )
    return path


def test_load_and_deobfuscate_mapping(tmp_path: Path) -> None:
    mapping = SaveMapping.load(write_mapping(tmp_path / "mapping.json"))

    assert mapping.ambiguous == {"dup": ("First", "Second")}
    assert mapping.deobfuscate({"abc": {"def": "value"}, "dup": 1}) == {
        "PlayerStateData": {"Name": "value"},
        "dup": 1,
    }
    assert mapping.obfuscate({"PlayerStateData": {"Name": "value"}}) == {"abc": {"def": "value"}}
    assert mapping.raw_key("Name") == "def"


def test_mapping_requires_714(tmp_path: Path) -> None:
    with pytest.raises(SaveToolError, match="must be MBINCompiler 7.14.0.1"):
        SaveMapping.load(write_mapping(tmp_path / "mapping.json", "7.13.0.1"))


def test_acquire_mapping_is_hash_pinned(
    tmp_path: Path, tranche: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_mapping(tmp_path / "source.json")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(mapping_module, "MAPPING_SHA256", digest)
    output = tranche / "inputs/mapping.json"

    result = acquire_mapping(output, url=source.as_uri())

    assert result["pinned"] is True
    assert verify_mapping(output)["version"] == "7.14.0.1"
