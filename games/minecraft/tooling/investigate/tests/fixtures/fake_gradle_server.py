from __future__ import annotations

import os
import signal
import socket
import struct
import time
from pathlib import Path


def receive_exact(connection: socket.socket, length: int) -> bytes:
    value = b""
    while len(value) < length:
        chunk = connection.recv(length - len(value))
        if not chunk:
            raise EOFError
        value += chunk
    return value


def packet(connection: socket.socket) -> tuple[int, int, str]:
    (length,) = struct.unpack("<i", receive_exact(connection, 4))
    body = receive_exact(connection, length)
    packet_id, packet_type = struct.unpack("<ii", body[:8])
    return packet_id, packet_type, body[8:-2].decode()


def reply(connection: socket.socket, packet_id: int, packet_type: int, payload: str) -> None:
    body = struct.pack("<ii", packet_id, packet_type) + payload.encode() + b"\x00\x00"
    connection.sendall(struct.pack("<i", len(body)) + body)


def properties() -> dict[str, str]:
    values = {}
    for line in Path("fabric/run/server.properties").read_text().splitlines():
        key, value = line.split("=", 1)
        values[key] = value
    return values


def main() -> None:
    values = properties()
    server_port = int(values["server-port"])
    rcon_port = int(values["rcon.port"])
    password = values["rcon.password"]
    child_ignores_term = values.get("fake-child-ignore-term", "true") == "true"
    linger_after_stop = float(values.get("fake-linger-after-stop", "0"))
    delayed_command_prefix = values.get("fake-delay-command-prefix", "")
    command_delay = float(values.get("fake-command-delay", "0"))
    delayed_command = False
    world = Path("fabric/run") / values["level-name"]
    world.mkdir(parents=True, exist_ok=True)
    (world / "level.dat").write_bytes(b"fake-level-identity")

    child = os.fork()
    if child == 0:
        if child_ignores_term:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        with socket.socket() as game:
            game.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            game.bind(("127.0.0.1", server_port))
            game.listen()
            while True:
                time.sleep(1)

    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", rcon_port))
        listener.listen()
        stopping = False
        while not stopping:
            connection, _address = listener.accept()
            with connection:
                auth_id, _kind, supplied = packet(connection)
                reply(connection, auth_id if supplied == password else -1, 2, "")
                while supplied == password:
                    try:
                        command_id, _kind, command = packet(connection)
                    except (EOFError, OSError):
                        break
                    if (
                        not delayed_command
                        and delayed_command_prefix
                        and command.startswith(delayed_command_prefix)
                    ):
                        delayed_command = True
                        time.sleep(command_delay)
                    response = (
                        f"Seed: [{values['level-seed']}]" if command == "seed" else "ok"
                    )
                    try:
                        reply(connection, command_id, 0, response)
                    except OSError:
                        break
                    if command == "stop":
                        stopping = True
                        break
    if not child_ignores_term:
        os.kill(child, signal.SIGTERM)
        os.waitpid(child, 0)
    if linger_after_stop:
        time.sleep(linger_after_stop)


if __name__ == "__main__":
    main()
