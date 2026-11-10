from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from squinch_nms_save.codec import RawNumber, encode_document
from squinch_nms_save.meta import BASE_VERSION, META_FORMAT, META_MAGIC, encrypt_words, storage_slot


def write_save_pair(
    directory: Path,
    *,
    name: str = "save.hg",
    document: dict | None = None,
    meta_format: int = META_FORMAT,
    base_version: int = BASE_VERSION,
    meta_size: int = 432,
    size_mode: str = "decoded",
    store_compressed_size: bool = True,
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    save_path = directory / name
    value = document or {
        "F2P": 4746,
        "8>q": "Win|Final",
        "XTp": "Main",
        "nested": {"count": 7, "precise": RawNumber("1.2300000000000001")},
        "items": ["alpha", "beta"],
    }
    data, decompressed_size = encode_document(value)
    save_path.write_bytes(data)

    plain = bytearray(meta_size)
    struct.pack_into("<I", plain, 0, META_MAGIC)
    struct.pack_into("<I", plain, 4, meta_format)
    primary_size = decompressed_size if size_mode == "decoded" else len(data)
    struct.pack_into("<I", plain, 56, primary_size)
    if store_compressed_size:
        struct.pack_into("<I", plain, 60, len(data))
    struct.pack_into("<I", plain, 68, base_version)
    struct.pack_into("<I", plain, 84, primary_size)
    plain[88:98] = b"Test Save\0"
    struct.pack_into("<I", plain, 356, 1_700_000_000)
    struct.pack_into("<I", plain, 360, meta_format)
    words = list(struct.unpack(f"<{len(plain) // 4}I", plain))
    encrypted = struct.pack(f"<{len(words)}I", *encrypt_words(words, storage_slot(save_path), 6))
    meta_path = directory / f"mf_{name}"
    meta_path.write_bytes(encrypted)
    return save_path, meta_path


@pytest.fixture
def save_pair(tmp_path: Path) -> tuple[Path, Path]:
    return write_save_pair(tmp_path / "profile")


@pytest.fixture
def tranche(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "tranche"
    path.mkdir()
    monkeypatch.setenv("SQUINCH_TRANCHE_WORKSPACE", str(path))
    return path


@pytest.fixture
def patch_file(tranche: Path) -> Path:
    path = tranche / "inputs/patch.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            [
                {"op": "test", "path": "/nested/count", "value": 7},
                {"op": "replace", "path": "/nested/count", "value": 8},
                {"op": "add", "path": "/items/-", "value": "gamma"},
            ]
        )
    )
    return path
