from __future__ import annotations

import json
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lz4.block

from .errors import SaveToolError

MAGIC = bytes.fromhex("e5a1edfe")
BLOCK_SIZE = 512 * 1024
MAX_DECOMPRESSED_SIZE = 256 * 1024 * 1024
MAX_COMPRESSED_BLOCK = BLOCK_SIZE + BLOCK_SIZE // 255 + 16
MAX_COMPRESSED_SIZE = 300 * 1024 * 1024
HEADER = struct.Struct("<4sIII")
NMS_VERSION = "7.14"
CONTROL_ESCAPE = re.compile(r"\\u00[0-9a-f]{2}")


@dataclass(frozen=True)
class RawNumber:
    """A JSON floating-point token retained exactly across an edit."""

    text: str


@dataclass(frozen=True)
class DecodedSave:
    document: dict[str, Any]
    json_bytes: bytes
    block_count: int
    compressed_size: int
    decompressed_size: int


def _decode_float(text: str) -> RawNumber:
    return RawNumber(text)


def _dump_string(value: str) -> str:
    encoded = json.dumps(value, ensure_ascii=False)
    return CONTROL_ESCAPE.sub(lambda match: match.group()[:4] + match.group()[4:].upper(), encoded)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite number {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def parse_json(data: bytes, *, source: str = "JSON", require_714: bool = True) -> dict[str, Any]:
    try:
        text = data.decode("latin-1")
        value = json.loads(
            text,
            parse_float=_decode_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeError, ValueError) as exc:
        raise SaveToolError(f"{source} is not valid Latin-1 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SaveToolError(f"{source} root must be a JSON object")
    version = value.get("F2P")
    if require_714 and (isinstance(version, bool) or not isinstance(version, int) or version <= 0):
        raise SaveToolError(f"{source} has no valid NMS save-format version in F2P")
    return value


def decode_bytes(raw: bytes, *, source: str = "save", require_714: bool = True) -> DecodedSave:
    if len(raw) > MAX_COMPRESSED_SIZE:
        raise SaveToolError(f"{source} exceeds the 300 MiB compressed-size limit")
    if len(raw) < HEADER.size:
        raise SaveToolError(f"{source} is too small to be an NMS LZ4 save")

    output = bytearray()
    position = 0
    blocks = 0
    while position < len(raw):
        if len(raw) - position < HEADER.size:
            raise SaveToolError(f"{source} has a truncated LZ4 header at offset {position}")
        magic, compressed_len, uncompressed_len, padding = HEADER.unpack_from(raw, position)
        if magic != MAGIC:
            raise SaveToolError(f"{source} has invalid LZ4 magic at offset {position}")
        if padding != 0:
            raise SaveToolError(f"{source} has nonzero reserved header bytes at offset {position}")
        if compressed_len <= 0 or uncompressed_len <= 0:
            raise SaveToolError(f"{source} has an empty LZ4 block at offset {position}")
        if compressed_len > MAX_COMPRESSED_BLOCK:
            raise SaveToolError(f"{source} has an oversized LZ4 block at offset {position}")
        if uncompressed_len > BLOCK_SIZE:
            raise SaveToolError(
                f"{source} block at offset {position} exceeds the 512 KiB PC block size"
            )
        position += HEADER.size
        end = position + compressed_len
        if end > len(raw):
            raise SaveToolError(f"{source} has a truncated LZ4 block at offset {position}")
        try:
            block = lz4.block.decompress(raw[position:end], uncompressed_size=uncompressed_len)
        except lz4.block.LZ4BlockError as exc:
            raise SaveToolError(f"{source} has an invalid LZ4 block at offset {position}") from exc
        if len(block) != uncompressed_len:
            raise SaveToolError(
                f"{source} block at offset {position} decoded to {len(block)} bytes; "
                f"expected {uncompressed_len}"
            )
        output.extend(block)
        if len(output) > MAX_DECOMPRESSED_SIZE:
            raise SaveToolError(f"{source} exceeds the 256 MiB decoded-size limit")
        position = end
        blocks += 1

    if not output or output[-1] != 0:
        raise SaveToolError(f"{source} JSON is missing its required NUL terminator")
    if b"\0" in output[:-1]:
        raise SaveToolError(f"{source} contains an unexpected NUL before the terminator")
    json_bytes = bytes(output[:-1])
    document = parse_json(json_bytes, source=source, require_714=require_714)
    return DecodedSave(document, json_bytes, blocks, len(raw), len(output))


def decode_file(path: Path, *, require_714: bool = True) -> DecodedSave:
    try:
        if path.stat().st_size > MAX_COMPRESSED_SIZE:
            raise SaveToolError(f"{path} exceeds the 300 MiB compressed-size limit")
        raw = path.read_bytes()
    except OSError as exc:
        raise SaveToolError(f"cannot read save {path}: {exc}") from exc
    return decode_bytes(raw, source=str(path), require_714=require_714)


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, RawNumber):
        return value.text
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SaveToolError("JSON cannot contain NaN or infinity")
        return repr(value)
    if isinstance(value, str):
        return _dump_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                f"{_dump_string(str(key))}:{_serialize(item)}" for key, item in value.items()
            )
            + "}"
        )
    raise SaveToolError(f"unsupported JSON value type: {type(value).__name__}")


def serialize_json(value: Any) -> str:
    return _serialize(value)


def serialize_document(document: dict[str, Any]) -> bytes:
    try:
        return serialize_json(document).encode("latin-1")
    except UnicodeEncodeError as exc:
        raise SaveToolError(
            "edited JSON contains characters outside Latin-1; PC NMS saves cannot encode them"
        ) from exc


def encode_document(document: dict[str, Any]) -> tuple[bytes, int]:
    payload = serialize_document(document) + b"\0"
    if len(payload) > MAX_DECOMPRESSED_SIZE:
        raise SaveToolError("edited save exceeds the 256 MiB decoded-size limit")
    output = bytearray()
    for offset in range(0, len(payload), BLOCK_SIZE):
        block = payload[offset : offset + BLOCK_SIZE]
        compressed = lz4.block.compress(block, store_size=False)
        output.extend(HEADER.pack(MAGIC, len(compressed), len(block), 0))
        output.extend(compressed)
    return bytes(output), len(payload)
