from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from .errors import ConfigError, UnknownMod
from .models import (
    ExpectedFailure,
    ModConfig,
    ParentConfig,
    ProfileDef,
    ProfileOverride,
    Target,
    TestDef,
)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Config file is empty or not a mapping: {path}")
    return data


def _validate_schema(data: dict, schema_path: Path, source_path: Path) -> None:
    if not schema_path.exists():
        raise ConfigError(f"Schema file not found: {schema_path}")
    schema = json.loads(schema_path.read_text())
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        path_str = " -> ".join(str(p) for p in e.absolute_path) or "(root)"
        raise ConfigError(
            f"Schema validation failed in {source_path} at {path_str}: {e.message}"
        ) from e
    except jsonschema.SchemaError as e:
        raise ConfigError(f"Internal schema error in {schema_path}: {e.message}") from e


def _build_parent_config(data: dict) -> ParentConfig:
    globals_block = data["globals"]
    profiles_raw = globals_block["profiles"]
    tests_raw = globals_block.get("tests", {})

    profiles = {
        name: ProfileDef(
            tests=pdef.get("tests", []),
            extends=pdef.get("extends"),
            max_parallel=pdef.get("max_parallel"),
            max_jobs=pdef.get("max_jobs"),
        )
        for name, pdef in profiles_raw.items()
    }

    tests: dict[str, dict] = {
        name: {"config": tdef.get("config", {})} for name, tdef in tests_raw.items()
    }

    return ParentConfig(
        default_profile=globals_block["default_profile"],
        profiles=profiles,
        tests=tests,
    )


def _build_mod_config(data: dict) -> ModConfig:
    mod_block = data["mod"]
    targets_raw = data["targets"]
    profiles_raw = data.get("profiles", {})
    tests_raw = data.get("tests", {})
    expected_failures_raw = data.get("expected_failures", [])

    targets = [
        Target(
            id=t["id"],
            minecraft=t["minecraft"],
            loader=t["loader"],
            loader_version=t.get("loader_version"),
            java=t["java"],
            supported=t.get("supported", True),
            capabilities=t.get("capabilities", []),
        )
        for t in targets_raw
    ]

    profiles = {
        name: ProfileOverride(
            extends=pov.get("extends"),
            add=pov.get("add", []),
            tests=pov.get("tests", []),
        )
        for name, pov in profiles_raw.items()
    }

    tests = {
        name: TestDef(
            requires=tdef.get("requires", []),
            adapters=tdef.get("adapters", {}),
            config=tdef.get("config", {}),
            expectations=tdef.get("expectations", {}),
        )
        for name, tdef in tests_raw.items()
    }

    expected_failures = [
        ExpectedFailure(
            target=ef["target"],
            test=ef["test"],
            reason=ef["reason"],
            expires=ef.get("expires"),
        )
        for ef in expected_failures_raw
    ]

    return ModConfig(
        mod_id=mod_block["id"],
        display_name=mod_block.get("display_name"),
        targets=targets,
        profiles=profiles,
        tests=tests,
        expected_failures=expected_failures,
    )


def find_repo_root(start: Path) -> Path:
    """Walk up from start looking for .squinch/config.yml; return its directory."""
    current = start.resolve()
    while True:
        if (current / ".squinch" / "config.yml").exists():
            return current
        parent = current.parent
        if parent == current:
            raise ConfigError(
                f"Could not find .squinch/config.yml searching up from {start}"
            )
        current = parent


def load_parent_config(repo_root: Path) -> ParentConfig:
    """Read and validate <repo_root>/.squinch/config.yml; return ParentConfig."""
    config_path = repo_root / ".squinch" / "config.yml"
    schema_path = repo_root / ".squinch" / "schema" / "global-config.schema.json"
    data = _load_yaml(config_path)
    _validate_schema(data, schema_path, config_path)
    return _build_parent_config(data)


# This package only drives Minecraft mods, so mod discovery is scoped to
# games/minecraft/mods rather than a games/*/mods wildcard.
_MOD_SOURCE_ROOT = ("games", "minecraft", "mods")


def _mod_config_root(repo_root: Path) -> Path:
    return repo_root / ".squinch" / "games" / "minecraft" / "mods"


def _mod_source_dir(repo_root: Path, mod_dir_name: str) -> Path:
    return repo_root.joinpath(*_MOD_SOURCE_ROOT, mod_dir_name)


def load_mod_config(repo_root: Path, mod_slug: str) -> tuple[ModConfig, Path]:
    """
    Resolve mod config under .squinch/games/minecraft/mods/, read and
    validate it; return (ModConfig, mod_source_dir), the mod's checkout
    under games/minecraft/mods/ used for builds and git commit lookups.
    """
    schema_path = repo_root / ".squinch" / "schema" / "mod-config.schema.json"
    config_root = _mod_config_root(repo_root)

    def _resolved(
        mod_dir_name: str, config_path: Path, data: dict
    ) -> tuple[ModConfig, Path]:
        _validate_schema(data, schema_path, config_path)
        mod_source_dir = _mod_source_dir(repo_root, mod_dir_name)
        if not mod_source_dir.is_dir():
            raise ConfigError(
                f"mod '{mod_dir_name}' has config at {config_path} but no source "
                f"checkout at {mod_source_dir} (submodule not initialized?)"
            )
        return _build_mod_config(data), mod_source_dir

    # Branch 1: direct filesystem path (exact case)
    candidates = list(config_root.glob(f"{mod_slug}/config.yml"))
    if len(candidates) == 1:
        config_path = candidates[0]
        data = _load_yaml(config_path)
        return _resolved(mod_slug, config_path, data)
    elif len(candidates) > 1:
        raise ConfigError(
            f"Ambiguous mod slug '{mod_slug}': found in multiple locations: "
            + ", ".join(str(c) for c in candidates)
        )

    # Branch 2: scan and match on mod.id or case-insensitive basename
    all_mod_configs = list(config_root.glob("*/config.yml"))
    available_ids: list[str] = []

    for candidate_path in all_mod_configs:
        mod_dir_name = candidate_path.parts[-2]  # dir before config.yml

        try:
            raw = _load_yaml(candidate_path)
        except ConfigError:
            continue

        mod_id = raw.get("mod", {}).get("id", "")
        if mod_id:
            available_ids.append(mod_id)

        if mod_id == mod_slug or mod_dir_name.lower() == mod_slug.lower():
            return _resolved(mod_dir_name, candidate_path, raw)

    raise UnknownMod(
        f"Unknown mod '{mod_slug}'. Available mod ids: {sorted(set(available_ids))}"
    )
