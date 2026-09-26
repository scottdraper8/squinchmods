from __future__ import annotations

from typing import Any

from squinch_qa.errors import ConfigError, UnknownProfile
from squinch_qa.models import (
    ModConfig,
    ParentConfig,
    ProfileOverride,
    ResolvedProfile,
    TestSpec,
)


_DEFAULT_MAX_PARALLEL = 1
_DEFAULT_MAX_JOBS = 256


def _normalize_test_entry(entry: str | dict[str, Any]) -> str | dict[str, Any]:
    if not isinstance(entry, dict):
        return entry
    normalized: dict[str, Any] = {
        "id": entry["id"],
        "required": bool(entry.get("required", True)),
    }
    if "config" in entry:
        normalized["config"] = dict(entry["config"])
    return normalized


def _test_entry_id(entry: str | dict[str, Any]) -> str:
    return entry["id"] if isinstance(entry, dict) else entry


def _resolve_parent_chain(
    parent: ParentConfig,
    profile_name: str,
) -> tuple[list[str], list[str], int | None, int | None]:
    """
    Walk the parent-side extends chain for profile_name.
    Returns (chain_root_to_leaf, test_ids, max_parallel, max_jobs).
    Leaf values win for all three accumulated fields.
    """
    if profile_name not in parent.profiles:
        available = sorted(parent.profiles)
        raise UnknownProfile(
            f"profile {profile_name!r} not found in parent config; "
            f"available: {available}"
        )

    # Walk leaf → root, collecting the chain and detecting cycles
    chain_leaf_to_root: list[str] = []
    seen: set[str] = set()
    current: str | None = profile_name

    while current is not None:
        if current in seen:
            cycle_str = " -> ".join(chain_leaf_to_root + [current])
            raise ConfigError(f"cycle detected in profile extends chain: {cycle_str}")
        seen.add(current)
        chain_leaf_to_root.append(current)

        next_name = parent.profiles[current].extends
        if next_name is not None and next_name not in parent.profiles:
            chain_so_far = " -> ".join(chain_leaf_to_root)
            raise ConfigError(
                f"profile {next_name!r} referenced via extends from {current!r} "
                f"not found in parent config; chain so far: {chain_so_far}"
            )
        current = next_name

    # Reverse to root-to-leaf order
    chain = list(reversed(chain_leaf_to_root))

    # Accumulate root-to-leaf; leaf wins each field
    test_ids: list[str] | None = None
    max_parallel: int | None = None
    max_jobs: int | None = None

    for name in chain:
        prof = parent.profiles[name]
        if prof.tests:
            test_ids = list(prof.tests)
        if prof.max_parallel is not None:
            max_parallel = prof.max_parallel
        if prof.max_jobs is not None:
            max_jobs = prof.max_jobs

    return chain, test_ids or [], max_parallel, max_jobs


def _resolve_mod_chain(
    parent: ParentConfig,
    mod: ModConfig,
    profile_name: str,
) -> tuple[list[str], list[str | dict[str, Any]], int | None, int | None]:
    """
    Walk a mod-first extends chain starting from profile_name.
    Used when a mod ProfileOverride declares its own `extends` target.
    Returns (chain_root_to_leaf, test_entries, max_parallel, max_jobs).
    """
    if profile_name not in mod.profiles and profile_name not in parent.profiles:
        raise ConfigError(f"profile {profile_name!r} not found in mod or parent config")

    chain_leaf_to_root: list[str] = []
    seen: set[str] = set()
    current: str | None = profile_name

    while current is not None:
        if current in seen:
            cycle_str = " -> ".join(chain_leaf_to_root + [current])
            raise ConfigError(f"cycle detected in mod extends chain: {cycle_str}")
        seen.add(current)
        chain_leaf_to_root.append(current)

        # Mod-first lookup for extends target
        if current in mod.profiles:
            override = mod.profiles[current]
            if override.add and override.tests:
                raise ConfigError(
                    f"profile override {current!r} specifies both 'add' and 'tests'; "
                    "use one or the other"
                )
            next_name = override.extends
        elif current in parent.profiles:
            next_name = parent.profiles[current].extends
        else:
            raise ConfigError(f"profile {current!r} not found in mod or parent config")

        if next_name is not None:
            if next_name not in mod.profiles and next_name not in parent.profiles:
                raise ConfigError(
                    f"profile {next_name!r} referenced via extends from {current!r} "
                    "not found in mod or parent config"
                )
        current = next_name

    chain = list(reversed(chain_leaf_to_root))

    # Accumulate root-to-leaf (leaf wins), handling ProfileOverride and ProfileDef entries
    test_entries: list[str | dict[str, Any]] | None = None
    max_parallel: int | None = None
    max_jobs: int | None = None

    for name in chain:
        if name in mod.profiles:
            override = mod.profiles[name]
            if override.tests:
                test_entries = [_normalize_test_entry(t) for t in override.tests]
            elif override.add:
                existing_ids = {_test_entry_id(e) for e in (test_entries or [])}
                accumulated = list(test_entries or [])
                for t in override.add:
                    if t not in existing_ids:
                        accumulated.append(t)
                        existing_ids.add(t)
                test_entries = accumulated
        elif name in parent.profiles:
            prof = parent.profiles[name]
            if prof.tests:
                test_entries = list(prof.tests)
            if prof.max_parallel is not None:
                max_parallel = prof.max_parallel
            if prof.max_jobs is not None:
                max_jobs = prof.max_jobs

    return chain, test_entries or [], max_parallel, max_jobs


def _build_test_specs(
    test_entries: list[str | dict[str, Any]],
    parent: ParentConfig,
    mod: ModConfig,
) -> list[TestSpec]:
    """
    Build TestSpec list from the resolved test entry list.
    Each entry is either a bare string (id) or a {id, required} dict.
    Shallow-merges parent test config with mod test config (mod wins).
    """
    specs: list[TestSpec] = []
    for i, entry in enumerate(test_entries):
        if isinstance(entry, dict):
            test_id: str = entry["id"]
            required = bool(entry.get("required", True))
            profile_config = dict(entry.get("config", {}))
        else:
            test_id = entry
            required = True
            profile_config = {}

        parent_raw = parent.tests.get(test_id, {})
        parent_config = (
            parent_raw.get("config", {}) if isinstance(parent_raw, dict) else {}
        )

        mod_test = mod.tests.get(test_id)
        if mod_test is not None:
            merged_config = {**parent_config, **mod_test.config, **profile_config}
            requires = list(mod_test.requires)
            adapters = dict(mod_test.adapters)
            expectations = dict(mod_test.expectations)
        else:
            merged_config = {**parent_config, **profile_config}
            requires = []
            adapters = {}
            expectations = {}

        specs.append(
            TestSpec(
                id=test_id,
                required=required,
                requires=requires,
                adapters=adapters,
                expectations=expectations,
                config=merged_config,
                origin_index=i,
            )
        )

    return specs


def resolve_profile(
    parent: ParentConfig,
    mod: ModConfig,
    profile_name: str | None,
) -> ResolvedProfile:
    """Resolve profile extends chain and mod overrides; return final ResolvedProfile."""
    if profile_name is None:
        profile_name = parent.default_profile

    # Step 1: Resolve parent-side extends chain and limits. The root-to-leaf
    # chain also tells us which same-named mod overrides must apply; a mod
    # override on "pre-pr" should naturally flow into "release" because parent
    # release extends pre-pr.
    resolved_from, test_ids, max_parallel, max_jobs = _resolve_parent_chain(
        parent, profile_name
    )

    # Step 2: Apply mod-side overrides for every profile in the inherited
    # chain, root-to-leaf. A mod override can append tests, replace the list, or
    # explicitly derive from another mod/parent profile with `extends`.
    final_entries: list[str | dict[str, Any]] = list(test_ids)
    for chain_name in resolved_from:
        mod_override: ProfileOverride | None = mod.profiles.get(chain_name)
        if mod_override is None:
            continue
        if mod_override.add and mod_override.tests:
            raise ConfigError(
                f"profile override {chain_name!r} specifies both 'add' and 'tests'; "
                "use one or the other"
            )

        if mod_override.extends:
            _, final_entries, mp, mj = _resolve_mod_chain(
                parent, mod, mod_override.extends
            )
            if mp is not None:
                max_parallel = mp
            if mj is not None:
                max_jobs = mj

        if mod_override.tests:
            final_entries = [_normalize_test_entry(t) for t in mod_override.tests]
        elif mod_override.add:
            existing_ids = {_test_entry_id(e) for e in final_entries}
            for t in mod_override.add:
                if t not in existing_ids:
                    final_entries.append(t)
                    existing_ids.add(t)

    # Step 3: Apply defaults for limits not set anywhere in the chain
    if max_parallel is None:
        max_parallel = _DEFAULT_MAX_PARALLEL
    if max_jobs is None:
        max_jobs = _DEFAULT_MAX_JOBS

    # Step 4: Build TestSpec list with origin_index for stable ordering
    test_specs = _build_test_specs(final_entries, parent, mod)

    return ResolvedProfile(
        name=profile_name,
        resolved_from=resolved_from,
        tests=test_specs,
        max_parallel=max_parallel,
        max_jobs=max_jobs,
    )
