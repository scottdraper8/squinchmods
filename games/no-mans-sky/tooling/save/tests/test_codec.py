from __future__ import annotations

import struct

import pytest

from squinch_nms_save.codec import (
    HEADER,
    RawNumber,
    decode_bytes,
    encode_document,
    serialize_document,
)
from squinch_nms_save.errors import SaveToolError


def test_round_trip_preserves_raw_float_text() -> None:
    document = {
        "F2P": 4746,
        "value": RawNumber("1.2300000000000001"),
        "control": "before\x1cafter",
    }
    encoded, decompressed_size = encode_document(document)
    decoded = decode_bytes(encoded)

    assert decoded.document == document
    assert decoded.decompressed_size == decompressed_size
    assert serialize_document(decoded.document) == (
        b'{"F2P":4746,"value":1.2300000000000001,"control":"before\\u001Cafter"}'
    )


def test_decode_accepts_current_profile_snapshot_revision() -> None:
    encoded, _ = encode_document({"F2P": 4745})

    assert decode_bytes(encoded).document["F2P"] == 4745


def test_decode_rejects_missing_save_version() -> None:
    encoded, _ = encode_document({"not-version": 4746})

    with pytest.raises(SaveToolError, match="no valid NMS save-format version"):
        decode_bytes(encoded)


def test_decode_rejects_nonzero_reserved_header() -> None:
    encoded, _ = encode_document({"F2P": 4746})
    damaged = bytearray(encoded)
    magic, compressed, uncompressed, _ = HEADER.unpack_from(damaged)
    HEADER.pack_into(damaged, 0, magic, compressed, uncompressed, 1)

    with pytest.raises(SaveToolError, match="nonzero reserved"):
        decode_bytes(bytes(damaged))


def test_encode_rejects_non_latin1() -> None:
    with pytest.raises(SaveToolError, match="outside Latin-1"):
        encode_document({"F2P": 4746, "value": "launch 🚀"})


def test_decode_rejects_truncated_block() -> None:
    encoded, _ = encode_document({"F2P": 4746})
    compressed = struct.unpack_from("<I", encoded, 4)[0]
    assert compressed > 1

    with pytest.raises(SaveToolError, match="truncated LZ4 block"):
        decode_bytes(encoded[:-1])


def test_decode_rejects_duplicate_keys() -> None:
    import lz4.block

    payload = b'{"F2P":4746,"F2P":4746}\0'
    compressed = lz4.block.compress(payload, store_size=False)
    encoded = HEADER.pack(bytes.fromhex("e5a1edfe"), len(compressed), len(payload), 0) + compressed

    with pytest.raises(SaveToolError, match="duplicate object key"):
        decode_bytes(encoded)
