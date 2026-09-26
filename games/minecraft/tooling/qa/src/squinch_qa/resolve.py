from __future__ import annotations

from typing import Any

from squinch_qa.errors import ConfigError, UnknownProfile
from squinch_qa.models import (
    ModConfig,
    ParentConfig,
    ResolvedProfile,
    TestDef,
    TestSpec,
)

_DEFAULT_MAX_JOBS = 256


def _test_entry_id(entry: str | dict[str, Any]) -> str:
    return entry["id"] if isinstance(entry, dict) else entry


def _resolve_parent_chain(
    parent: ParentConfig, profile_name: str
) -> tuple[list[str], list[str], int]:
    if profile_name not in parent.profiles:
        available = sorted(parent.profiles)
        raise UnknownProfile(
            f"profile {profile_name!r} not found in parent config; available: {available}"
        )

    chain_leaf_to_root: list[str] = []
    seen: set[str] = set()
    current: str | None = profile_name

    while current is not None:
        if current in seen:
            cycle = " -> ".join(chain_leaf_to_root + [current])
            raise ConfigError(f"cycle detected in profile extends chain: {cycle}")
        seen.add(current)
        chain_leaf_to_root.append(current)

        next_name = parent.profiles[current].extends
        if next_name is not None and next_name not in parent.profiles:
            raise ConfigError(
                f"profile {next_name!r} referenced via extends from {current!r} "
                f"not found in parent config"
            )
        current = next_name

    chain = list(reversed(chain_leaf_to_root))
    test_ids: list[str] = []
    max_jobs: int | None = None
    for name in chain:
        profile = parent.profiles[name]
        tests = profile.tests
        if tests:
            test_ids = list(tests)
        if profile.max_jobs is not None:
            max_jobs = profile.max_jobs
    return chain, test_ids, max_jobs or _DEFAULT_MAX_JOBS


def _build_test_specs(
    entries: list[str | dict[str, Any]], parent: ParentConfig, mod: ModConfig
) -> list[TestSpec]:
    specs: list[TestSpec] = []
    for index, entry in enumerate(entries):
        test_id = _test_entry_id(entry)
        profile_config = (
            dict(entry.get("config", {})) if isinstance(entry, dict) else {}
        )
        parent_config = parent.tests.get(test_id, {}).get("config", {})
        mod_config = mod.tests.get(test_id, TestDef()).config
        specs.append(
            TestSpec(
                id=test_id,
                config={**parent_config, **mod_config, **profile_config},
                origin_index=index,
            )
        )
    return specs


def resolve_profile(
    parent: ParentConfig, mod: ModConfig, profile_name: str | None
) -> ResolvedProfile:
    if profile_name is None:
        profile_name = parent.default_profile

    chain, test_ids, max_jobs = _resolve_parent_chain(parent, profile_name)
    entries: list[str | dict[str, Any]] = list(test_ids)

    for name in chain:
        override = mod.profiles.get(name)
        if override is None:
            continue
        if override.add and override.tests:
            raise ConfigError(
                f"profile override {name!r} specifies both 'add' and 'tests'; use one"
            )
        if override.tests:
            entries = list(override.tests)
        elif override.add:
            existing = {_test_entry_id(entry) for entry in entries}
            for test in override.add:
                if test not in existing:
                    entries.append(test)
                    existing.add(test)

    return ResolvedProfile(
        name=profile_name,
        resolved_from=chain,
        tests=_build_test_specs(entries, parent, mod),
        max_jobs=max_jobs,
    )
