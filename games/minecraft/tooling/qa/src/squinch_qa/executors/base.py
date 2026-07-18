from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from squinch_qa.models import Target


@dataclass
class FailureDetail:
    reason: str
    detail: str = ""


@dataclass
class JobResult:
    status: str  # "pass" | "fail" | "error" | "expected_failure"
    started_at: str  # ISO-8601
    finished_at: str  # ISO-8601
    duration_s: float
    logs: list[str] = field(default_factory=list)  # relative paths under job_dir
    artifacts: list[str] = field(default_factory=list)  # relative paths under job_dir
    failure: FailureDetail | None = None
    tool_used: str | None = None  # pregen only: "chunksmith" | "chunky" | …
    jar_sha256: str | None = None  # sha256 of the built/used jar


@dataclass
class JobContext:
    run_id: str
    target_id: str
    test_id: str
    job_dir: Path
    adapter: dict[str, Any] | None
    test_config: dict[str, Any]
    repo_root: Path
    mod_dir: Path
    target: Target | None = None


@runtime_checkable
class Executor(Protocol):
    def run(self, ctx: JobContext) -> JobResult: ...
