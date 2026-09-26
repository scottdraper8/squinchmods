from __future__ import annotations

import socket
import struct

from .errors import InvestigationError


class RconError(InvestigationError):
    def __init__(self, message: str):
        super().__init__("rcon_failed", message)


def _receive_exact(connection: socket.socket, length: int) -> bytes:
    value = bytearray()
    while len(value) < length:
        chunk = connection.recv(length - len(value))
        if not chunk:
            raise RconError("RCON socket closed before a complete packet arrived")
        value.extend(chunk)
    return bytes(value)


def _receive_packet(connection: socket.socket) -> tuple[int, int, str]:
    (length,) = struct.unpack("<i", _receive_exact(connection, 4))
    if length < 10 or length > 4 * 1024 * 1024:
        raise RconError(f"invalid RCON packet length: {length}")
    body = _receive_exact(connection, length)
    if body[-2:] != b"\x00\x00":
        raise RconError("invalid RCON packet terminator")
    packet_id, packet_type = struct.unpack("<ii", body[:8])
    return packet_id, packet_type, body[8:-2].decode("utf-8", errors="replace")


def execute(
    host: str,
    port: int,
    password: str,
    commands: list[str],
    *,
    timeout: float = 15.0,
) -> list[str]:
    next_id = 0

    def send(connection: socket.socket, packet_type: int, payload: str) -> int:
        nonlocal next_id
        next_id += 1
        body = struct.pack("<ii", next_id, packet_type) + payload.encode() + b"\x00\x00"
        connection.sendall(struct.pack("<i", len(body)) + body)
        return next_id

    try:
        connection = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        raise RconError(f"cannot connect to RCON at {host}:{port}: {exc}") from exc

    responses: list[str] = []
    try:
        with connection:
            connection.settimeout(timeout)
            auth_id = send(connection, 3, password)
            reply_id, _reply_type, _reply = _receive_packet(connection)
            if reply_id == -1:
                raise RconError("RCON authentication failed")
            if reply_id != auth_id:
                raise RconError(
                    f"RCON authentication returned packet {reply_id}, expected {auth_id}"
                )
            for command in commands:
                command_id = send(connection, 2, command)
                reply_id, _reply_type, payload = _receive_packet(connection)
                if reply_id != command_id:
                    raise RconError(
                        f"RCON command returned packet {reply_id}, expected {command_id}"
                    )
                responses.append(payload)
    except RconError:
        raise
    except OSError as exc:
        raise RconError(f"RCON I/O failed: {exc}") from exc
    return responses
