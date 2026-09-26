from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Raw config representations ────────────────────────────────────────────────


@dataclass
class Target:
    id: str
    minecraft: str
    loader: str  # "forge" | "neoforge" | "fabric" | "quilt"
    loader_version: str | None
    java: int
    supported: bool
    capabilities: list[str]


@dataclass
class TestDef:
    """Per-test definition from mod config (tests.<name>)."""

    requires: list[str] = field(default_factory=list)
    adapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    expectations: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileDef:
    """A profile entry as read from parent config (globals.profiles.<name>)."""

    tests: list[str] = field(default_factory=list)
    extends: str | None = None
    max_parallel: int | None = None
    max_jobs: int | None = None


@dataclass
class ParentConfig:
    default_profile: str
    profiles: dict[str, ProfileDef]  # required; always present (schema enforces)
    tests: dict[str, dict[str, Any]] = field(default_factory=dict)  # optional in schema


@dataclass
class ProfileOverride:
    """Mod-level profileOverride as read from mod config (profiles.<name>)."""

    extends: str | None = None
    add: list[str] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)  # [{id, required}]


@dataclass
class ExpectedFailure:
    target: str
    test: str
    reason: str
    expires: str | None  # ISO date string "YYYY-MM-DD" or None


@dataclass
class ModConfig:
    mod_id: str
    targets: list[Target]
    display_name: str | None = None  # optional in schema
    profiles: dict[str, ProfileOverride] = field(
        default_factory=dict
    )  # optional in schema
    tests: dict[str, TestDef] = field(default_factory=dict)  # optional in schema
    expected_failures: list[ExpectedFailure] = field(
        default_factory=list
    )  # optional in schema


# ── Resolved/planned representations ─────────────────────────────────────────


@dataclass
class TestSpec:
    """A single test entry in the resolved profile, ready for matrix expansion."""

    id: str
    required: bool
    requires: list[str]  # capability names
    adapters: dict[str, dict[str, Any]]  # loader → adapter dict
    expectations: dict[str, Any]
    config: dict[str, Any]  # merged parent+mod config
    origin_index: int  # position in the resolved test list for stable ordering


@dataclass
class ResolvedProfile:
    name: str
    resolved_from: list[str]  # profile names walked, root-first
    tests: list[TestSpec]
    max_parallel: int  # always set; default 1
    max_jobs: int  # always set; default 256


@dataclass
class PlannedJob:
    target: Target
    test_spec: TestSpec
    adapter: dict[str, Any] | None  # resolved adapter dict, or None
    expected_failure: dict[str, Any] | None  # {reason, expires, expired} or None
    expectations: dict[str, Any]  # test_spec.expectations["default"] merged with
    # ["by_target"][target.id]; {} if none declared


@dataclass
class SkippedEntry:
    target_id: str
    test_id: str
    reason: str


@dataclass
class SkippedTarget:
    target_id: str
    reason: str


@dataclass
class ExecutionPlan:
    mod_id: str
    display_name: str | None
    profile: ResolvedProfile
    jobs: list[PlannedJob]
    skipped: list[SkippedEntry]
    skipped_targets: list[SkippedTarget]
