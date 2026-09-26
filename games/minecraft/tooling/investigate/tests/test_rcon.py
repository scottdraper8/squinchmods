from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable

import pytest

from squinch_minecraft_investigate.rcon import RconError, execute


def _receive_exact(connection: socket.socket, length: int) -> bytes:
    value = b""
    while len(value) < length:
        value += connection.recv(length - len(value))
    return value


def _request(connection: socket.socket) -> tuple[int, int, str]:
    (length,) = struct.unpack("<i", _receive_exact(connection, 4))
    body = _receive_exact(connection, length)
    packet_id, packet_type = struct.unpack("<ii", body[:8])
    return packet_id, packet_type, body[8:-2].decode()


def _packet(packet_id: int, packet_type: int, payload: str) -> bytes:
    body = struct.pack("<ii", packet_id, packet_type) + payload.encode() + b"\x00\x00"
    return struct.pack("<i", len(body)) + body


def _run_server(handler: Callable[[socket.socket], None]) -> tuple[int, threading.Thread, list[BaseException]]:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = int(listener.getsockname()[1])
    failures: list[BaseException] = []

    def serve() -> None:
        try:
            connection, _address = listener.accept()
            with connection:
                handler(connection)
        except Exception as exc:  # noqa: BLE001 - surface handler failures to the test thread
            failures.append(exc)
        finally:
            listener.close()

    thread = threading.Thread(target=serve)
    thread.start()
    return port, thread, failures


def test_rcon_assembles_fragmented_packets_over_a_real_socket() -> None:
    """Catches recv-boundary assumptions that truncate valid authenticated command responses."""

    def handler(connection: socket.socket) -> None:
        auth_id, auth_type, password = _request(connection)
        assert (auth_type, password) == (3, "secret")
        auth = _packet(auth_id, 2, "")
        for byte in auth:
            connection.sendall(bytes([byte]))
        command_id, command_type, command = _request(connection)
        assert (command_type, command) == (2, "list")
        response = _packet(command_id, 0, "There are 0 of a max of 20 players online")
        connection.sendall(response[:3])
        connection.sendall(response[3:])

    port, thread, failures = _run_server(handler)
    assert execute("127.0.0.1", port, "secret", ["list"], timeout=2) == [
        "There are 0 of a max of 20 players online"
    ]
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert failures == []


@pytest.mark.parametrize(
    ("malformed", "message"),
    (
        (struct.pack("<i", 9), "invalid RCON packet length"),
        (struct.pack("<i", 10) + struct.pack("<ii", 1, 2) + b"xx", "invalid RCON packet terminator"),
    ),
)
def test_rcon_rejects_malformed_packets_from_a_real_socket(
    malformed: bytes, message: str
) -> None:
    """Catches corrupt framing being decoded as an authenticated server response."""

    def handler(connection: socket.socket) -> None:
        _request(connection)
        connection.sendall(malformed)

    port, thread, failures = _run_server(handler)
    with pytest.raises(RconError, match=message):
        execute("127.0.0.1", port, "secret", [], timeout=2)
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert failures == []
