from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .output import timestamp
from .state import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    exit_code = subprocess.run(command, check=False).returncode
    atomic_write_json(args.output, {
        "status": "exited",
        "exit_code": exit_code,
        "finished_at": timestamp(),
    })
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
