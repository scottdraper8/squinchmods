from __future__ import annotations

import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import IO, Iterable

RUN_ID_RE = re.compile(r"^\d+-[0-9a-f]{8}$")


def default_qa_root(repo_root: Path) -> Path:
    return repo_root / "games" / "minecraft" / "qa-state"


def default_qa_runs_dir(repo_root: Path) -> Path:
    return default_qa_root(repo_root) / "runs"


def make_run_id() -> str:
    """Return a time-ordered run ID: <unix_ms>-<uuid4_hex8>."""
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    return f"{ts}-{uid}"


def is_valid_run_id(run_id: str) -> bool:
    return RUN_ID_RE.fullmatch(run_id) is not None


def run_dir(qa_runs_dir: Path, run_id: str) -> Path:
    return qa_runs_dir / run_id


def job_dir(qa_runs_dir: Path, run_id: str, target_id: str, test_id: str) -> Path:
    return run_dir(qa_runs_dir, run_id) / "jobs" / target_id / test_id


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tee_stream(source: Iterable[bytes], *sinks: IO[bytes]) -> None:
    """Read lines from source, writing each to all sinks (line-buffered)."""
    for line in source:
        for sink in sinks:
            sink.write(line)
            sink.flush()
