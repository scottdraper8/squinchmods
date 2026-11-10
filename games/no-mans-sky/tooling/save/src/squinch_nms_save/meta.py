from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from pathlib import Path

from .codec import NMS_VERSION
from .errors import SaveToolError

META_MAGIC = 0xEEEEEEBE
META_FORMAT = 2004
SUPPORTED_META_FORMATS = {2003, 2004}
MIN_BASE_VERSION = 4135
BASE_VERSION = 4234
MAX_BASE_VERSION = BASE_VERSION
U32 = 0xFFFFFFFF


@dataclass(frozen=True)
class MetaInfo:
    format: int
    storage_slot: int
    encrypted_slot: int
    base_version: int
    decompressed_size: int
    compressed_size: int | None
    timestamp: int | None


@dataclass(frozen=True)
class MetaSummary:
    format: int
    storage_slot: int
    encrypted_slot: int
    base_version: int | None
    decompressed_size: int
    compressed_size: int | None
    timestamp: int | None
    total_play_time: int | None
    save_name: str | None


def storage_slot(path: Path) -> int:
    stem = path.stem.lower()
    if stem == "save":
        return 2
    if stem.startswith("save") and stem[4:].isdigit() and int(stem[4:]) >= 2:
        return int(stem[4:]) + 1
    raise SaveToolError(f"unsupported PC save filename: {path.name}")


def meta_path(save_path: Path) -> Path:
    return save_path.with_name(f"mf_{save_path.name}")


def _key(slot: int) -> tuple[int, int, int, int]:
    value = (slot ^ 0x1422CB8C) & U32
    rotated = ((value << 13) | (value >> 19)) & U32
    key0 = (rotated * 5 + 0xE6546B64) & U32
    return key0, 0x44415645, 0x5259414E, 0x47524E54


def _mix(next_value: int, previous: int, key_value: int, total: int) -> int:
    left = (
        ((next_value >> 3) ^ ((previous << 4) & U32))
        + (((next_value << 2) & U32) ^ (previous >> 5))
    ) & U32
    right = ((previous ^ key_value) + (next_value ^ total)) & U32
    return (left ^ right) & U32


def encrypt_words(words: list[int], slot: int, iterations: int = 6) -> list[int]:
    if len(words) < 2:
        raise SaveToolError("metadata is too short")
    result = words.copy()
    key = _key(slot)
    last = len(result) - 1
    previous = result[last]
    total = 0
    for _ in range(iterations):
        total = (total + 0x9E3779B9) & U32
        key_index = (total >> 2) & 3
        for index in range(last):
            next_value = result[index + 1]
            result[index] = (
                result[index] + _mix(next_value, previous, key[(index & 3) ^ key_index], total)
            ) & U32
            previous = result[index]
        next_value = result[0]
        result[last] = (
            result[last] + _mix(next_value, previous, key[(last & 3) ^ key_index], total)
        ) & U32
        previous = result[last]
    return result


def decrypt_words(words: list[int], slot: int, iterations: int = 6) -> list[int]:
    if len(words) < 2:
        raise SaveToolError("metadata is too short")
    result = words.copy()
    key = _key(slot)
    last = len(result) - 1
    total = (iterations * 0x9E3779B9) & U32
    for _ in range(iterations):
        key_index = (total >> 2) & 3
        next_value = result[0]
        for index in range(last, 0, -1):
            previous = result[index - 1]
            result[index] = (
                result[index] - _mix(next_value, previous, key[(index & 3) ^ key_index], total)
            ) & U32
            next_value = result[index]
        previous = result[last]
        result[0] = (result[0] - _mix(next_value, previous, key[key_index], total)) & U32
        total = (total + 0x61C88647) & U32
    return result


def _unpack(raw: bytes) -> list[int]:
    if len(raw) % 4:
        raise SaveToolError("metadata length is not divisible by four")
    return list(struct.unpack(f"<{len(raw) // 4}I", raw))


def _pack(words: list[int]) -> bytes:
    return struct.pack(f"<{len(words)}I", *words)


def decrypt_meta(raw: bytes, expected_slot: int) -> tuple[bytearray, int]:
    iterations = 8 if len(raw) == 104 else 6
    words = _unpack(raw)
    candidates = [expected_slot, *(slot for slot in range(32) if slot != expected_slot)]
    for slot in candidates:
        plain_words = decrypt_words(words, slot, iterations)
        if plain_words[0] == META_MAGIC:
            return bytearray(_pack(plain_words)), slot
    raise SaveToolError("metadata could not be decrypted with any NMS storage-slot key")


def summarize_meta_bytes(raw: bytes, save_path: Path) -> MetaSummary:
    expected = storage_slot(save_path)
    plain, encrypted_slot = decrypt_meta(raw, expected)
    if len(plain) < 60:
        raise SaveToolError("metadata is too short for a PC save")
    meta_format = struct.unpack_from("<I", plain, 4)[0]
    base_version = struct.unpack_from("<I", plain, 68)[0] if len(plain) >= 72 else None
    stored_compressed_size = struct.unpack_from("<I", plain, 60)[0] if len(plain) >= 64 else 0
    compressed_size = stored_compressed_size or None
    timestamp = (
        struct.unpack_from("<I", plain, 356)[0]
        if meta_format >= 2003 and len(plain) >= 360
        else None
    )
    total_play_time = struct.unpack_from("<Q", plain, 76)[0] if len(plain) >= 84 else None
    save_name = None
    if len(plain) >= 216:
        raw_name = bytes(plain[88:216]).split(b"\0", 1)[0]
        save_name = raw_name.decode("utf-8", errors="replace")
    return MetaSummary(
        format=meta_format,
        storage_slot=expected,
        encrypted_slot=encrypted_slot,
        base_version=base_version,
        decompressed_size=struct.unpack_from("<I", plain, 56)[0],
        compressed_size=compressed_size,
        timestamp=timestamp,
        total_play_time=total_play_time,
        save_name=save_name,
    )


def summarize_meta_file(path: Path, save_path: Path) -> MetaSummary:
    try:
        return summarize_meta_bytes(path.read_bytes(), save_path)
    except OSError as exc:
        raise SaveToolError(f"cannot read metadata {path}: {exc}") from exc


def inspect_meta_bytes(raw: bytes, save_path: Path) -> MetaInfo:
    summary = summarize_meta_bytes(raw, save_path)
    expected = summary.storage_slot
    plain, encrypted_slot = decrypt_meta(raw, expected)
    if len(plain) < 360:
        raise SaveToolError("metadata is too short for a current-profile PC save")
    meta_format = summary.format
    if meta_format not in SUPPORTED_META_FORMATS:
        raise SaveToolError(
            f"metadata format {meta_format} is not supported in the NMS {NMS_VERSION} profile"
        )
    base_version = summary.base_version
    if base_version is None:
        raise SaveToolError("metadata has no NMS 7.14 base version field")
    if not MIN_BASE_VERSION <= base_version <= MAX_BASE_VERSION:
        raise SaveToolError(
            f"metadata base version {base_version} is outside the validated range "
            f"{MIN_BASE_VERSION}-{MAX_BASE_VERSION} for saves up to NMS {NMS_VERSION}"
        )
    stored_compressed_size = struct.unpack_from("<I", plain, 60)[0]
    compressed_size = stored_compressed_size or None
    timestamp = struct.unpack_from("<I", plain, 356)[0]
    return MetaInfo(
        format=meta_format,
        storage_slot=expected,
        encrypted_slot=encrypted_slot,
        base_version=base_version,
        decompressed_size=struct.unpack_from("<I", plain, 56)[0],
        compressed_size=compressed_size,
        timestamp=timestamp,
    )


def inspect_meta_file(path: Path, save_path: Path) -> MetaInfo:
    try:
        return inspect_meta_bytes(path.read_bytes(), save_path)
    except OSError as exc:
        raise SaveToolError(f"cannot read metadata {path}: {exc}") from exc


def update_meta(
    raw: bytes,
    save_path: Path,
    *,
    decompressed_size: int,
    compressed_size: int,
    timestamp: int | None = None,
    size_mode: str = "decoded",
) -> tuple[bytes, MetaInfo]:
    expected = storage_slot(save_path)
    plain, _encrypted_slot = decrypt_meta(raw, expected)
    if len(plain) < 360:
        raise SaveToolError("metadata is too short for a current-profile PC save")
    meta_format = struct.unpack_from("<I", plain, 4)[0]
    if meta_format not in SUPPORTED_META_FORMATS:
        raise SaveToolError(
            f"metadata format {meta_format} is not supported in the NMS 7.14 profile"
        )
    base_version = struct.unpack_from("<I", plain, 68)[0]
    if not MIN_BASE_VERSION <= base_version <= MAX_BASE_VERSION:
        raise SaveToolError(
            f"metadata base version {base_version} is outside the validated range "
            f"{MIN_BASE_VERSION}-{MAX_BASE_VERSION} for saves up to NMS {NMS_VERSION}"
        )
    if size_mode not in {"decoded", "compressed"}:
        raise SaveToolError(f"unsupported metadata size mode: {size_mode}")
    primary_size = decompressed_size if size_mode == "decoded" else compressed_size
    struct.pack_into("<I", plain, 56, primary_size)
    struct.pack_into("<I", plain, 84, primary_size)
    if size_mode == "compressed" or struct.unpack_from("<I", plain, 60)[0] != 0:
        struct.pack_into("<I", plain, 60, compressed_size)
    struct.pack_into("<I", plain, 356, int(time.time()) if timestamp is None else timestamp)
    words = _unpack(bytes(plain))
    encrypted = _pack(encrypt_words(words, expected, 6))
    return encrypted, inspect_meta_bytes(encrypted, save_path)


def rekey_meta(raw: bytes, source_save_path: Path, destination_save_path: Path) -> bytes:
    source_slot = storage_slot(source_save_path)
    destination_slot = storage_slot(destination_save_path)
    plain, encrypted_slot = decrypt_meta(raw, source_slot)
    if encrypted_slot != source_slot:
        raise SaveToolError(
            f"metadata for {source_save_path.name} is encrypted for storage slot "
            f"{encrypted_slot}, not {source_slot}"
        )
    iterations = 8 if len(raw) == 104 else 6
    encrypted = _pack(encrypt_words(_unpack(bytes(plain)), destination_slot, iterations))
    info = inspect_meta_bytes(encrypted, destination_save_path)
    if info.encrypted_slot != destination_slot:
        raise SaveToolError(
            f"rekeyed metadata did not use destination storage slot {destination_slot}"
        )
    return encrypted


def rename_meta(raw: bytes, save_path: Path, save_name: str) -> bytes:
    encoded_name = save_name.encode("utf-8")
    if not encoded_name or len(encoded_name) > 127 or b"\0" in encoded_name:
        raise SaveToolError("metadata save name must be 1-127 UTF-8 bytes without NUL")
    expected_slot = storage_slot(save_path)
    plain, encrypted_slot = decrypt_meta(raw, expected_slot)
    if encrypted_slot != expected_slot:
        raise SaveToolError(
            f"metadata for {save_path.name} is encrypted for storage slot "
            f"{encrypted_slot}, not {expected_slot}"
        )
    if len(plain) < 216:
        raise SaveToolError("metadata is too short for a save name")
    plain[88:216] = encoded_name + bytes(128 - len(encoded_name))
    iterations = 8 if len(raw) == 104 else 6
    encrypted = _pack(encrypt_words(_unpack(bytes(plain)), expected_slot, iterations))
    summary = summarize_meta_bytes(encrypted, save_path)
    if summary.save_name != save_name:
        raise SaveToolError("re-encoded metadata save name failed verification")
    return encrypted
