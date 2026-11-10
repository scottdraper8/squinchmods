from __future__ import annotations

import struct
from pathlib import Path

import pytest

from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.meta import (
    BASE_VERSION,
    META_FORMAT,
    decrypt_meta,
    inspect_meta_bytes,
    rename_meta,
    storage_slot,
    update_meta,
)


def test_current_meta_round_trip_and_preservation(save_pair: tuple[Path, Path]) -> None:
    save, meta = save_pair
    original = meta.read_bytes()
    original_plain, slot = decrypt_meta(original, storage_slot(save))
    updated, info = update_meta(
        original,
        save,
        decompressed_size=123456,
        compressed_size=65432,
        timestamp=1_800_000_000,
    )
    updated_plain, updated_slot = decrypt_meta(updated, storage_slot(save))

    assert slot == updated_slot == 2
    assert info.format == META_FORMAT
    assert info.base_version == BASE_VERSION
    assert info.decompressed_size == 123456
    assert info.compressed_size == 65432
    assert info.timestamp == 1_800_000_000
    for start, end in ((56, 64), (84, 88), (356, 360)):
        original_plain[start:end] = updated_plain[start:end]
    assert original_plain == updated_plain


def test_meta_accepts_current_profile_base_version(save_pair: tuple[Path, Path]) -> None:
    save, meta = save_pair
    raw = meta.read_bytes()
    plain, _ = decrypt_meta(raw, storage_slot(save))
    struct.pack_into("<I", plain, 68, BASE_VERSION - 1)
    words = list(struct.unpack(f"<{len(plain) // 4}I", plain))
    from squinch_nms_save.meta import encrypt_words

    invalid = struct.pack(f"<{len(words)}I", *encrypt_words(words, storage_slot(save)))
    assert inspect_meta_bytes(invalid, save).base_version == BASE_VERSION - 1


def test_meta_rejects_unsupported_base_version(save_pair: tuple[Path, Path]) -> None:
    save, meta = save_pair
    raw = meta.read_bytes()
    plain, _ = decrypt_meta(raw, storage_slot(save))
    struct.pack_into("<I", plain, 68, 4000)
    words = list(struct.unpack(f"<{len(plain) // 4}I", plain))
    from squinch_nms_save.meta import encrypt_words

    invalid = struct.pack(f"<{len(words)}I", *encrypt_words(words, storage_slot(save)))
    with pytest.raises(SaveToolError, match="outside the validated range"):
        inspect_meta_bytes(invalid, save)


def test_meta_fails_closed_above_714_ceiling(save_pair: tuple[Path, Path]) -> None:
    save, meta = save_pair
    plain, _ = decrypt_meta(meta.read_bytes(), storage_slot(save))
    struct.pack_into("<I", plain, 68, BASE_VERSION + 1)
    words = list(struct.unpack(f"<{len(plain) // 4}I", plain))
    from squinch_nms_save.meta import encrypt_words

    future = struct.pack(f"<{len(words)}I", *encrypt_words(words, storage_slot(save)))
    with pytest.raises(SaveToolError, match="up to NMS 7.14"):
        inspect_meta_bytes(future, save)


def test_storage_slot_mapping() -> None:
    assert storage_slot(Path("save.hg")) == 2
    assert storage_slot(Path("save2.hg")) == 3
    assert storage_slot(Path("save20.hg")) == 21


def test_rename_meta_preserves_other_plaintext(save_pair: tuple[Path, Path]) -> None:
    save, meta = save_pair
    original_plain, _slot = decrypt_meta(meta.read_bytes(), storage_slot(save))
    renamed = rename_meta(meta.read_bytes(), save, "Galaxies 51-100")
    renamed_plain, renamed_slot = decrypt_meta(renamed, storage_slot(save))

    assert renamed_slot == storage_slot(save)
    assert bytes(renamed_plain[88:216]).split(b"\0", 1)[0] == b"Galaxies 51-100"
    original_plain[88:216] = renamed_plain[88:216]
    assert original_plain == renamed_plain


def test_compressed_size_mode_preserves_historical_wrapper(
    save_pair: tuple[Path, Path],
) -> None:
    save, meta = save_pair
    updated, info = update_meta(
        meta.read_bytes(),
        save,
        decompressed_size=123456,
        compressed_size=65432,
        timestamp=1_800_000_000,
        size_mode="compressed",
    )
    plain, _slot = decrypt_meta(updated, storage_slot(save))

    assert info.decompressed_size == 65432
    assert info.compressed_size == 65432
    assert struct.unpack_from("<I", plain, 84)[0] == 65432
