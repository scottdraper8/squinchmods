from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from squinch_qa.remote.errors import GhError


@dataclass(frozen=True)
class GhResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_gh(
    *args: str,
    timeout: float = 30.0,
    cwd: Path | None = None,
    check: bool = True,
) -> GhResult:
    cmd = ["gh", *args]
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise GhError(f"gh {' '.join(args)} timed out after {timeout:g}s") from e
    except OSError as e:
        raise GhError(f"failed to execute gh {' '.join(args)}: {e}") from e

    result = GhResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GhError(
            f"gh {' '.join(args)} failed with exit {completed.returncode}: {detail}"
        )
    return result
