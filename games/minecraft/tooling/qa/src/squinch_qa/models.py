from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Target:
    id: str
    minecraft: str
    loader: str
    loader_version: str | None
    java: int


@dataclass
class TestDef:
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileDef:
    tests: list[str] = field(default_factory=list)
    extends: str | None = None
    max_jobs: int | None = None


@dataclass
class ParentConfig:
    default_profile: str
    profiles: dict[str, ProfileDef]
    tests: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class ProfileOverride:
    add: list[str] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ModConfig:
    mod_id: str
    targets: list[Target]
    display_name: str | None = None
    profiles: dict[str, ProfileOverride] = field(default_factory=dict)
    tests: dict[str, TestDef] = field(default_factory=dict)


@dataclass
class TestSpec:
    id: str
    config: dict[str, Any]
    origin_index: int


@dataclass
class ResolvedProfile:
    name: str
    resolved_from: list[str]
    tests: list[TestSpec]
    max_jobs: int


@dataclass
class PlannedJob:
    target: Target
    test_spec: TestSpec


@dataclass
class ExecutionPlan:
    mod_id: str
    display_name: str | None
    profile: ResolvedProfile
    jobs: list[PlannedJob]
