#!/usr/bin/env python3
"""Run the current capability-proof matrix against one resident NMS session."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

from search_probes import resident_search_protocol as protocol

ROOT = Path(
    os.environ.get(
        "SQN_RESIDENT_SEARCH_ROOT",
        str(Path(__file__).with_name(".resident-search")),
    )
)
LUSH_ASSET_SUBTYPES = (
    "Standard",
    "HighQuality",
    "Variant_A",
    "Variant_B",
    "Variant_C",
    "Variant_D",
    "HugeToxic",
    "Bubble",
    "Infested",
    "HugeLush",
    "Swamp",
    "Worlds",
    "HugePlant",
    "HydroGarden",
    "Structure",
)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object in {path}")
    return value


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class ResidentClient:
    def __init__(self, run_id: str, *, default_timeout: float) -> None:
        current = _read_json(ROOT / "current.json")
        session_id = current.get("session_id")
        if not isinstance(session_id, str):
            raise TypeError("resident current.json has no session_id")
        self.session = ROOT / "sessions" / session_id
        state = _read_json(self.session / "state.json")
        if state.get("state") != "ready":
            raise RuntimeError(f"resident session is not ready: {state!r}")
        self.generation = int(state.get("generation", 0))
        self.run_id = run_id
        self.default_timeout = default_timeout
        self.result_paths: list[str] = []

    def submit(
        self,
        label: str,
        action: str,
        *,
        timeout: float | None = None,
        **payload: object,
    ) -> dict[str, object]:
        self.generation += 1
        command_id = f"matrix-{self.run_id}-{label}"
        command = protocol.normalize_command(
            {
                "protocol": protocol.PROTOCOL_VERSION,
                "id": command_id,
                "generation": self.generation,
                "action": action,
                **payload,
            }
        )
        command_path = self.session / "commands" / f"{command_id}.json"
        _atomic_json(command_path, command)
        result_path = self.session / "results" / f"{command_id}.json"
        deadline = time.monotonic() + (
            self.default_timeout if timeout is None else timeout
        )
        while time.monotonic() < deadline:
            if result_path.exists():
                result = _read_json(result_path)
                if result.get("status") not in {"completed", "accepted"}:
                    raise RuntimeError(f"{label} returned {result!r}")
                self.result_paths.append(str(result_path))
                return result
            state = _read_json(self.session / "state.json")
            if state.get("state") in {"closed", "failed"}:
                raise RuntimeError(
                    f"resident session stopped during {label}: {state!r}"
                )
            time.sleep(0.05)
        raise TimeoutError(f"no result for {label} within the timeout")


def _first_address(survey: Mapping[str, object]) -> str:
    name_samples = survey.get("name_samples", [])
    if isinstance(name_samples, list):
        for sample in name_samples:
            if isinstance(sample, Mapping) and isinstance(sample.get("address"), str):
                return str(sample["address"])
    samples = survey.get("samples", {})
    if isinstance(samples, Mapping):
        for category in samples.values():
            if not isinstance(category, Mapping):
                continue
            for sample in category.values():
                if isinstance(sample, Mapping) and isinstance(
                    sample.get("address"), str
                ):
                    return str(sample["address"])
    raise RuntimeError("survey did not retain a candidate address")


def _first_remote_enumerated_address(enumeration: Mapping[str, object]) -> str:
    candidates = enumeration.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) < 2:
        raise RuntimeError("enumeration did not retain a remote candidate address")
    candidate = candidates[1]
    if not isinstance(candidate, Mapping) or not isinstance(
        candidate.get("address"), str
    ):
        raise TypeError("first remote enumeration candidate has no address")
    return str(candidate["address"])


def _first_object_source_control(
    spawn_survey: Mapping[str, object], fallback_address: str
) -> tuple[str, int]:
    samples = spawn_survey.get("samples", {})
    if isinstance(samples, Mapping):
        option_samples = samples.get("object_list_source_option", {})
        if isinstance(option_samples, Mapping):
            for option, sample in option_samples.items():
                if (
                    option
                    and isinstance(sample, Mapping)
                    and isinstance(sample.get("address"), str)
                    and isinstance(sample.get("planet"), int)
                ):
                    return str(sample["address"]), int(sample["planet"])
    return fallback_address, 0


def _without_runtime_resource_handles(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_runtime_resource_handles(child)
            for key, child in value.items()
            if key != "resource_id"
        }
    if isinstance(value, list):
        return [_without_runtime_resource_handles(child) for child in value]
    return value


def _resolved_asset_summary(resolved: Mapping[str, object]) -> dict[str, object]:
    collections = resolved.get("collections", {})
    if not isinstance(collections, Mapping):
        raise TypeError("resolved object-list collections must be a mapping")
    record_count = 0
    floating_island_count = 0
    selected_filenames: set[str] = set()
    source_debug_names: set[str] = set()
    for collection in collections.values():
        if not isinstance(collection, Mapping):
            raise TypeError("resolved object-list collection must be a mapping")
        records = collection.get("records", [])
        if not isinstance(records, list):
            raise TypeError("resolved object-list records must be a list")
        record_count += len(records)
        for record in records:
            if not isinstance(record, Mapping):
                raise TypeError("resolved object-list record must be a mapping")
            source = record.get("source_object", {})
            selected = record.get("selected_resource", {})
            if isinstance(source, Mapping):
                floating_island_count += bool(source.get("is_floating_island"))
                if source.get("debug_name"):
                    source_debug_names.add(str(source["debug_name"]))
            if isinstance(selected, Mapping) and selected.get("filename"):
                selected_filenames.add(str(selected["filename"]))
    return {
        "record_count": record_count,
        "floating_island_count": floating_island_count,
        "selected_filenames": sorted(selected_filenames),
        "source_debug_names": sorted(source_debug_names),
    }


def _parity_summary(survey: Mapping[str, object]) -> dict[str, object]:
    counts = survey.get("counts", {})
    if not isinstance(counts, Mapping):
        raise TypeError("survey counts must be a mapping")
    return {
        str(name): dict(values)
        for name, values in counts.items()
        if str(name).startswith("native_generated_parity_")
        and isinstance(values, Mapping)
    }


def _require_observed(
    counts: Mapping[str, object], category: str, values: object
) -> dict[str, int]:
    """Require every advertised value to have a positive full-survey control."""

    observed = counts.get(category, {})
    if not isinstance(observed, Mapping):
        raise TypeError(f"full survey did not record {category}")
    required = tuple(str(value) for value in values)
    missing = [value for value in required if int(observed.get(value, 0)) <= 0]
    if missing:
        raise RuntimeError(
            f"advertised {category} values have no positive control: {', '.join(missing)}"
        )
    return {value: int(observed[value]) for value in required}


def _ui_positive_controls(counts: Mapping[str, object]) -> dict[str, object]:
    """Validate all non-palette form choices against one complete generated survey."""

    controls: dict[str, object] = {}
    for category, names, offset in (
        ("biome", protocol.PROVEN_BIOMES, 0),
        ("biome_subtype", protocol.PROVEN_BIOME_SUBTYPES, 1),
        ("size", protocol.PLANET_SIZES, 0),
        ("life_level", protocol.PROVEN_PLANET_LIFE_LEVELS, 0),
        ("creature_life_level", protocol.PROVEN_CREATURE_LIFE_LEVELS, 0),
        ("building_density", protocol.PROVEN_BUILDING_DENSITY_LEVELS, 0),
        ("resource_level", protocol.PROVEN_RESOURCE_LEVELS, 0),
        ("storm_frequency", protocol.PROVEN_STORM_FREQUENCIES, 0),
        ("weather_intensity", protocol.WEATHER_INTENSITIES, 0),
        ("weather_type", protocol.PROVEN_WEATHER_TYPES, 0),
        ("star_type", protocol.STAR_TYPES, 0),
        ("wealth_class", protocol.WEALTH_CLASSES, 0),
        ("trading_class", protocol.TRADING_CLASSES, 0),
        ("race", protocol.PROVEN_RACES, 0),
    ):
        domain = protocol.__dict__.get(
            {
                "biome": "BIOMES",
                "biome_subtype": "BIOME_SUBTYPES",
                "size": "PLANET_SIZES",
                "life_level": "PLANET_LIFE_LEVELS",
                "creature_life_level": "PLANET_LIFE_LEVELS",
                "building_density": "BUILDING_DENSITY_LEVELS",
                "resource_level": "RESOURCE_LEVELS",
                "storm_frequency": "STORM_FREQUENCIES",
                "weather_intensity": "WEATHER_INTENSITIES",
                "weather_type": "WEATHER_TYPES",
                "star_type": "STAR_TYPES",
                "wealth_class": "WEALTH_CLASSES",
                "trading_class": "TRADING_CLASSES",
                "race": "RACE_ENUM",
            }[category]
        )
        controls[category] = _require_observed(
            counts,
            category,
            (domain.index(name) + offset for name in names),
        )
    controls["terrain_setting"] = _require_observed(
        counts, "terrain_setting", protocol.PROVEN_TERRAIN_SETTINGS
    )
    controls["resource"] = _require_observed(counts, "resource", protocol.RESOURCE_IDS)
    controls["population_state"] = _require_observed(
        counts, "population_state", protocol.POPULATION_STATES
    )
    controls["conflict_level"] = _require_observed(
        counts,
        "conflict_level",
        (protocol.CONFLICT_LEVELS[name] for name in protocol.CONFLICT_LEVELS),
    )
    controls["generated_planet_name"] = _require_observed(
        counts, "planet_name_empty", (False,)
    )

    planet_counts = counts.get("planet_count", {})
    if not isinstance(planet_counts, Mapping):
        raise TypeError("full survey did not record planet_count")
    observed_planet_counts = {
        int(value): int(count)
        for value, count in planet_counts.items()
        if int(count) > 0
    }
    missing_minima = [
        minimum
        for minimum in protocol.PROVEN_MINIMUM_PLANETS
        if not any(actual >= minimum for actual in observed_planet_counts)
    ]
    if missing_minima:
        raise RuntimeError(
            "advertised minimum-planet values have no positive control: "
            + ", ".join(str(value) for value in missing_minima)
        )
    controls["minimum_planets"] = {
        str(minimum): sum(
            count
            for actual, count in observed_planet_counts.items()
            if actual >= minimum
        )
        for minimum in protocol.PROVEN_MINIMUM_PLANETS
    }

    for category in (
        "has_floating_islands",
        "is_non_gas_giant",
        "has_rings",
        "has_moons",
        "has_water",
        "has_deep_water",
        "is_paradise",
        "has_extreme_weather",
        "has_extreme_hazard",
        "has_sentinels",
        "has_extreme_sentinels",
        "has_corrupt_sentinels",
        "is_prime",
        "is_infested",
        "is_normal",
        "is_relic",
        "is_rgb",
        "has_scrap",
        "suitable_creature_discovery",
        "suitable_weird_creature_discovery",
        "suitable_creature_taming",
        "suitable_robot_creature_discovery",
        "is_pirate",
        "has_giant_planet",
        "has_gas_giant",
        "has_non_gas_giant",
        "has_waterworld",
        "has_water_planet",
        "has_deep_water_planet",
        "has_weird_planet",
        "has_infested_planet",
        "has_normal_planet",
        "has_relic_planet",
        "has_rgb_planet",
        "has_corrupt_sentinel_planet",
        "has_extreme_storm_planet",
    ):
        controls[category] = _require_observed(counts, category, (False, True))
    return controls


def _search(
    client: ResidentClient,
    label: str,
    criteria: Mapping[str, object],
    *,
    candidate_limit: int,
    result_limit: int = 1,
) -> dict[str, object]:
    return client.submit(
        label,
        "search",
        timeout=900.0,
        criteria=dict(criteria),
        name=label.replace("-", " ").title(),
        candidate_limit=candidate_limit,
        result_limit=result_limit,
    )


def _require_search_matches(
    searches: Mapping[str, object], labels: tuple[str, ...]
) -> dict[str, int]:
    """Require an end-to-end positive result for every advertised composition."""

    controls: dict[str, int] = {}
    for label in labels:
        result = searches.get(label)
        if not isinstance(result, Mapping):
            raise TypeError(f"search matrix did not record {label}")
        matches = result.get("matches", [])
        if not result.get("matched") or not isinstance(matches, list) or not matches:
            raise RuntimeError(
                f"advertised search composition has no positive result: {label}"
            )
        controls[label] = len(matches)
    return controls


def _run_smoke(client: ResidentClient, summary: dict[str, object]) -> dict[str, object]:
    summary["ping_before"] = client.submit("ping-before", "ping")
    enumeration = client.submit(
        "enumerate-for-name-control", "enumerate", candidate_limit=64
    )
    address = _first_remote_enumerated_address(enumeration)
    name_first = client.submit(
        "system-name-a", "system_name_probe", timeout=180.0, address=address
    )
    name_second = client.submit(
        "system-name-b", "system_name_probe", timeout=180.0, address=address
    )
    first_name = name_first.get("generated_system_name")
    second_name = name_second.get("generated_system_name")
    if not isinstance(first_name, str) or not first_name or first_name != second_name:
        raise RuntimeError("base procedural system name was empty or non-repeatable")
    summary["generated_system_name_repeatability"] = {
        "address": address,
        "name": first_name,
        "exact": True,
    }
    survey = client.submit(
        "survey-64",
        "survey",
        timeout=180.0,
        candidate_limit=64,
    )
    summary["survey_64"] = {
        "systems_checked": survey.get("systems_checked"),
        "planets_checked": survey.get("planets_checked"),
        "evaluation_ns": survey.get("evaluation_ns"),
        "max_evaluation_ns": survey.get("max_evaluation_ns"),
        "max_slice_ns": survey.get("max_slice_ns"),
        "parity": _parity_summary(survey),
    }
    spawn = client.submit(
        "spawn-survey-8",
        "spawn_survey",
        timeout=180.0,
        candidate_limit=8,
    )
    summary["spawn_survey_8"] = {
        "systems_checked": spawn.get("systems_checked"),
        "planets_checked": spawn.get("planets_checked"),
        "evaluation_ns": spawn.get("evaluation_ns"),
        "max_evaluation_ns": spawn.get("max_evaluation_ns"),
        "max_slice_ns": spawn.get("max_slice_ns"),
        "floating_island_resources": (
            spawn.get("counts", {}).get("floating_island_spawn_resource", {})
            if isinstance(spawn.get("counts"), Mapping)
            else {}
        ),
        "object_list_source_names": (
            spawn.get("counts", {}).get("object_list_source_name", {})
            if isinstance(spawn.get("counts"), Mapping)
            else {}
        ),
        "object_list_source_options": (
            spawn.get("counts", {}).get("object_list_source_option", {})
            if isinstance(spawn.get("counts"), Mapping)
            else {}
        ),
    }
    address = _first_address(survey)
    first = client.submit("snapshot-a", "snapshot", timeout=180.0, address=address)
    second = client.submit("snapshot-b", "snapshot", timeout=180.0, address=address)
    first_snapshot = first.get("snapshot")
    second_snapshot = second.get("snapshot")
    summary["snapshot_repeatability"] = {
        "address": address,
        "exact": first_snapshot == second_snapshot,
        "without_runtime_resource_handles": (
            _without_runtime_resource_handles(first_snapshot)
            == _without_runtime_resource_handles(second_snapshot)
        ),
    }
    if not summary["snapshot_repeatability"]["without_runtime_resource_handles"]:
        raise RuntimeError(
            "repeated generated snapshot changed at the stable semantic boundary"
        )
    resolver_address, resolver_planet = _first_object_source_control(spawn, address)
    resolver_first = client.submit(
        "object-resolver-a",
        "object_resolver_probe",
        timeout=180.0,
        address=resolver_address,
        planet_index=resolver_planet,
    )
    resolver_second = client.submit(
        "object-resolver-b",
        "object_resolver_probe",
        timeout=180.0,
        address=resolver_address,
        planet_index=resolver_planet,
    )
    first_resolved = resolver_first.get("resolved_object_lists", {})
    second_resolved = resolver_second.get("resolved_object_lists", {})
    if not isinstance(first_resolved, Mapping) or not isinstance(
        second_resolved, Mapping
    ):
        raise TypeError("object resolver did not return result mappings")
    if not bool(first_resolved.get("rng_restored")) or not bool(
        second_resolved.get("rng_restored")
    ):
        raise RuntimeError("object resolver did not restore the procedural RNG")
    if not bool(first_resolved.get("outputs_released")) or not bool(
        second_resolved.get("outputs_released")
    ):
        raise RuntimeError("object resolver did not release every caller-owned output")
    first_collections = _without_runtime_resource_handles(
        first_resolved.get("collections", {})
    )
    second_collections = _without_runtime_resource_handles(
        second_resolved.get("collections", {})
    )
    if first_collections != second_collections:
        raise RuntimeError(
            "object resolver output changed for an identical planet control"
        )
    second_cache_before = second_resolved.get("cache_before", {})
    second_cache_after = second_resolved.get("cache_after", {})
    if second_cache_before != second_cache_after:
        raise RuntimeError(
            "object resolver cache continued growing for an identical control"
        )
    collection_sizes = {
        name: (
            value.get("header", {}).get("size") if isinstance(value, Mapping) else None
        )
        for name, value in (
            first_resolved.get("collections", {}).items()
            if isinstance(first_resolved.get("collections"), Mapping)
            else ()
        )
    }
    if int(resolver_first.get("source_headers", {}).get("size", 0)) > 0 and not any(
        int(value or 0) > 0 for value in collection_sizes.values()
    ):
        raise RuntimeError(
            "object resolver produced no records for a non-empty source control"
        )
    summary["object_resolver_repeatability"] = {
        "address": resolver_address,
        "planet_index": resolver_planet,
        "source_count": len(resolver_first.get("object_list_sources", [])),
        "semantic_output_equal": True,
        "first_rng_advanced": first_resolved.get("rng_advanced"),
        "first_rng_restored": first_resolved.get("rng_restored"),
        "first_outputs_released": first_resolved.get("outputs_released"),
        "second_rng_advanced": second_resolved.get("rng_advanced"),
        "second_rng_restored": second_resolved.get("rng_restored"),
        "second_outputs_released": second_resolved.get("outputs_released"),
        "first_cache_before": first_resolved.get("cache_before"),
        "first_cache_after": first_resolved.get("cache_after"),
        "second_cache_stable": second_cache_before == second_cache_after,
        "collection_sizes": collection_sizes,
        "assets": _resolved_asset_summary(first_resolved),
    }
    object_island_searches = {
        "require": _search(
            client,
            "smoke-object-islands-require",
            {
                "target_biome": "Lush",
                "biome_subtype": "HydroGarden",
                "floating_island_objects": "Require",
            },
            candidate_limit=64,
        ),
        "exclude": _search(
            client,
            "smoke-object-islands-exclude",
            {
                "target_biome": "Lush",
                "biome_subtype": "Standard",
                "floating_island_objects": "Exclude",
            },
            candidate_limit=64,
        ),
    }
    for label, result in object_island_searches.items():
        matches = result.get("matches", [])
        if not result.get("matched") or not isinstance(matches, list) or not matches:
            raise RuntimeError(
                f"resolver-backed object-island {label} search did not match"
            )
        first_match = matches[0]
        summary_value = (
            first_match.get("summary", {}) if isinstance(first_match, Mapping) else {}
        )
        planet = (
            summary_value.get("planet", {})
            if isinstance(summary_value, Mapping)
            else {}
        )
        expected = label == "require"
        if (
            not isinstance(planet, Mapping)
            or planet.get("has_floating_island_objects") is not expected
        ):
            raise RuntimeError(
                f"resolver-backed object-island {label} result lost its exact flag"
            )
        system = (
            summary_value.get("system", {})
            if isinstance(summary_value, Mapping)
            else {}
        )
        if not isinstance(system, Mapping) or not str(system.get("name", "")):
            raise RuntimeError(
                "retained resolver-backed search result lost its generated name"
            )
        if int(result.get("max_candidates_per_slice", 0)) > 1:
            raise RuntimeError(
                "resolver-backed search evaluated more than one system per update"
            )
    summary["resolver_backed_object_island_searches"] = object_island_searches
    enumeration_metadata = survey.get("enumeration_metadata", {})
    if isinstance(enumeration_metadata, Mapping) and isinstance(
        enumeration_metadata.get("resolved_address"), str
    ):
        current_address = str(enumeration_metadata["resolved_address"])
        current = client.submit(
            "snapshot-current",
            "snapshot",
            timeout=180.0,
            address=current_address,
        )
        current_snapshot = current.get("snapshot", {})
        if not isinstance(current_snapshot, Mapping):
            raise TypeError("current-system snapshot must be a mapping")
        current_planets = current_snapshot.get("planets", [])
        if not isinstance(current_planets, list):
            raise TypeError("current-system planets must be a list")
        current_system_name = client.submit(
            "system-name-current",
            "system_name_probe",
            timeout=180.0,
            address=current_address,
        )
        summary["current_generated_names"] = {
            "address": current_address,
            "system": current_system_name.get("generated_system_name", ""),
            "planets": [
                planet.get("name", "")
                for planet in current_planets
                if isinstance(planet, Mapping)
            ],
        }
        current_undiscovered = client.submit(
            "undiscovered-current",
            "candidate",
            timeout=180.0,
            address=current_address,
            criteria={"undiscovered": "Require"},
        )
        remote_undiscovered = client.submit(
            "undiscovered-remote",
            "candidate",
            timeout=180.0,
            address=address,
            criteria={"undiscovered": "Require"},
        )
        summary["undiscovered_controls"] = {
            "current": {
                "address": current_address,
                "accepted": current_undiscovered.get("accepted"),
                "evaluation_pass": current_undiscovered.get("evaluation_pass"),
            },
            "remote": {
                "address": address,
                "accepted": remote_undiscovered.get("accepted"),
                "evaluation_pass": remote_undiscovered.get("evaluation_pass"),
            },
        }
    summary["ping_after_smoke"] = client.submit("ping-after-smoke", "ping")
    return survey


def _run_full(
    client: ResidentClient,
    summary: dict[str, object],
    *,
    candidate_limit: int,
) -> None:
    survey = client.submit(
        "survey-full",
        "survey",
        timeout=1800.0,
        candidate_limit=candidate_limit,
    )
    counts = survey.get("counts", {})
    if not isinstance(counts, Mapping):
        raise TypeError("full survey counts must be a mapping")
    summary["survey_full"] = {
        "candidate_limit": candidate_limit,
        "candidate_count": survey.get("candidate_count"),
        "systems_checked": survey.get("systems_checked"),
        "planets_checked": survey.get("planets_checked"),
        "evaluation_ns": survey.get("evaluation_ns"),
        "max_evaluation_ns": survey.get("max_evaluation_ns"),
        "max_slice_ns": survey.get("max_slice_ns"),
        "max_candidates_per_slice": survey.get("max_candidates_per_slice"),
        "parity": _parity_summary(survey),
        "system_names_empty": counts.get("system_name_empty", {}),
        "planet_names_empty": counts.get("planet_name_empty", {}),
        "paradise_and_description": counts.get("paradise_and_description", {}),
        "life_and_flora_description": counts.get("life_and_flora_description", {}),
        "creature_life_and_fauna_description": counts.get(
            "creature_life_and_fauna_description", {}
        ),
        "resource_level_and_description": counts.get(
            "resource_level_and_description", {}
        ),
        "sentinel_level_and_description": counts.get(
            "sentinel_level_and_description", {}
        ),
        "floating_island_signals": counts.get(
            "terrain_and_object_floating_islands", {}
        ),
        "object_list_source_counts": counts.get(
            "spawn_header_object_list_sources_count", {}
        ),
        "object_list_source_names": counts.get("object_list_source_name", {}),
        "object_list_source_options": counts.get("object_list_source_option", {}),
        "race": counts.get("race", {}),
        "system_class": counts.get("system_class", {}),
        "native_undiscovered": counts.get("native_undiscovered", {}),
        "ui_positive_controls": _ui_positive_controls(counts),
        "generated_name_controls": {
            "system": _require_observed(counts, "system_name_empty", (False,)),
            "planet": _require_observed(counts, "planet_name_empty", (False,)),
        },
    }

    colour_survey = client.submit(
        "colour-survey-full",
        "colour_survey",
        timeout=1800.0,
        candidate_limit=candidate_limit,
    )
    colour_counts = colour_survey.get("counts", {})
    if not isinstance(colour_counts, Mapping):
        raise TypeError("full colour survey counts must be a mapping")
    palette_hues = {
        palette: colour_counts.get(f"primary_hue_{palette}", {})
        for palette in protocol.PRIMARY_COLOUR_PALETTE_KEYS.values()
    }
    for criterion, proven_hues in protocol.PROVEN_PRIMARY_HUES.items():
        palette = protocol.PRIMARY_COLOUR_PALETTE_KEYS[criterion]
        observed = palette_hues[palette]
        if not isinstance(observed, Mapping) or not set(proven_hues) <= set(observed):
            raise RuntimeError(
                f"full colour survey lost a proven {palette} hue: "
                f"expected={proven_hues!r}, observed={observed!r}"
            )
    summary["colour_survey_full"] = {
        "candidate_limit": candidate_limit,
        "candidate_count": colour_survey.get("candidate_count"),
        "systems_checked": colour_survey.get("systems_checked"),
        "planets_checked": colour_survey.get("planets_checked"),
        "evaluation_ns": colour_survey.get("evaluation_ns"),
        "max_evaluation_ns": colour_survey.get("max_evaluation_ns"),
        "max_slice_ns": colour_survey.get("max_slice_ns"),
        "max_candidates_per_slice": colour_survey.get("max_candidates_per_slice"),
        "palette_hues": palette_hues,
    }

    searches: dict[str, object] = {}
    fixed_searches = {
        "paradise": {"paradise_planet": "Require"},
        "calm-lush": {"target_biome": "Lush", "storm_frequency": "None"},
        "waterworld": {"target_biome": "Waterworld"},
        "floating-object": {"floating_island_objects": "Require"},
        "floating-terrain": {"floating_islands": "Require"},
        "lush-hydrogarden-floating-object": {
            "target_biome": "Lush",
            "biome_subtype": "HydroGarden",
            "floating_island_objects": "Require",
        },
        "floating-both": {
            "floating_islands": "Require",
            "floating_island_objects": "Require",
        },
        "normal-planet": {"normal_planet": "Require"},
        "relic-target-planet": {"relic_planet": "Require"},
        "rgb-planet": {"rgb_planet": "Require"},
        "scrap-planet": {"has_scrap": "Require"},
        "relic-planet": {"system_relic_planet": "Require"},
        "native-normal": {"any_biome_not_weird_or_dead": "Require"},
        "native-infested": {"any_infested_biome": "Require"},
        "native-rgb": {"any_rgb_biome": "Require"},
        "undiscovered": {"undiscovered": "Require"},
        "waterworld-giant": {
            "target_biome": "Waterworld",
            "planet_size": "Giant",
        },
        "storm-frequency-always": {"storm_frequency": "Always"},
        "candidate-preset-lush-terrain-islands": {
            "target_biome": "Lush",
            "floating_islands": "Require",
        },
        "candidate-preset-wet-non-gas-giant": {
            "planet_size": "Giant",
            "non_gas_giant_planet": "Require",
            "water_planet": "Require",
        },
        "candidate-preset-wealthy-low-conflict-settled": {
            "wealth_class": "Wealthy",
            "conflict_level": "Low",
            "population_state": "Inhabited",
        },
    }
    for label, criteria in fixed_searches.items():
        searches[label] = _search(
            client,
            f"search-{label}",
            criteria,
            candidate_limit=candidate_limit,
            result_limit=3 if label in {"paradise", "floating-object"} else 1,
        )

    for anomaly in protocol.ANOMALIES:
        label = f"anomaly-{anomaly}"
        searches[label] = _search(
            client,
            f"search-{label}",
            {"anomaly": anomaly},
            candidate_limit=candidate_limit,
        )

    summary["advertised_search_positive_controls"] = _require_search_matches(
        searches,
        (
            "paradise",
            "calm-lush",
            "waterworld",
            "floating-terrain",
            "floating-object",
            "lush-hydrogarden-floating-object",
            "normal-planet",
            "relic-target-planet",
            "rgb-planet",
            "scrap-planet",
            "relic-planet",
            *(f"anomaly-{anomaly}" for anomaly in protocol.PROVEN_ANOMALIES),
        ),
    )

    for criterion in protocol.PRIMARY_COLOUR_FIELDS:
        palette = protocol.PRIMARY_COLOUR_PALETTE_KEYS[criterion]
        observed = palette_hues[palette]
        if not isinstance(observed, Mapping) or not observed:
            raise RuntimeError(f"full colour survey did not record {palette}")
        most_common = max(observed, key=lambda value: int(observed[value]))
        label = f"colour-{criterion.replace('_primary_hue', '').replace('_', '-')}"
        result = _search(
            client,
            f"search-{label}",
            {criterion: most_common},
            candidate_limit=candidate_limit,
        )
        if not result.get("matched"):
            raise RuntimeError(
                f"runtime colour criterion {criterion} did not match observed hue {most_common}"
            )
        searches[label] = result

    asset_families: dict[str, object] = {}
    for subtype in LUSH_ASSET_SUBTYPES:
        label = f"lush-assets-{subtype.casefold().replace('_', '-')}"
        result = _search(
            client,
            f"search-{label}",
            {"target_biome": "Lush", "biome_subtype": subtype},
            candidate_limit=candidate_limit,
        )
        searches[label] = result
        matches = result.get("matches", [])
        if not isinstance(matches, list) or not matches:
            asset_families[subtype] = {"matched": False}
            continue
        match = matches[0]
        if not isinstance(match, Mapping):
            raise TypeError("Lush asset search match must be a mapping")
        match_summary = match.get("summary", {})
        planet_summary = (
            match_summary.get("planet", {})
            if isinstance(match_summary, Mapping)
            else {}
        )
        if not isinstance(planet_summary, Mapping):
            raise TypeError("Lush asset result planet summary must be a mapping")
        address = str(match["address"])
        planet_index = int(planet_summary["index"])
        captured = client.submit(
            f"resolve-{label}",
            "object_resolver_probe",
            timeout=180.0,
            address=address,
            planet_index=planet_index,
        )
        resolved = captured.get("resolved_object_lists", {})
        if not isinstance(resolved, Mapping):
            raise TypeError("Lush asset resolver result must be a mapping")
        if not bool(resolved.get("rng_restored")) or not bool(
            resolved.get("outputs_released")
        ):
            raise RuntimeError("Lush asset resolver did not restore owned native state")
        sources = captured.get("object_list_sources", [])
        if not isinstance(sources, list):
            raise TypeError("Lush asset resolver sources must be a list")
        asset_families[subtype] = {
            "matched": True,
            "address": address,
            "planet_index": planet_index,
            "source_names": sorted(
                {
                    str(source.get("name", ""))
                    for source in sources
                    if isinstance(source, Mapping) and source.get("name")
                }
            ),
            "source_options": sorted(
                {
                    str(option)
                    for source in sources
                    if isinstance(source, Mapping)
                    and isinstance(source.get("options"), list)
                    for option in source["options"]
                    if option
                }
            ),
            "resolved": _resolved_asset_summary(resolved),
            "elapsed_ns": resolved.get("elapsed_ns"),
            "rng_advanced": resolved.get("rng_advanced"),
            "rng_restored": resolved.get("rng_restored"),
            "outputs_released": resolved.get("outputs_released"),
            "cache_before": resolved.get("cache_before"),
            "cache_after": resolved.get("cache_after"),
        }
    summary["lush_asset_families"] = asset_families
    summary["lush_resolved_floating_island_controls"] = {
        subtype: family["resolved"]["floating_island_count"]
        for subtype, family in asset_families.items()
        if isinstance(family, Mapping)
        and isinstance(family.get("resolved"), Mapping)
        and int(family["resolved"].get("floating_island_count", 0)) > 0
    }

    for field, values in (
        ("life_level", protocol.PLANET_LIFE_LEVELS),
        ("creature_life_level", protocol.PLANET_LIFE_LEVELS),
        ("building_density", protocol.BUILDING_DENSITY_LEVELS),
        ("resource_level", protocol.RESOURCE_LEVELS),
    ):
        observed = counts.get(field, {})
        if not isinstance(observed, Mapping):
            continue
        for raw_value in observed:
            value_index = int(raw_value)
            if not 0 <= value_index < len(values):
                raise RuntimeError(f"survey returned invalid {field} value {raw_value}")
            value = values[value_index]
            label = f"abundance-{field}-{value}"
            searches[label] = _search(
                client,
                f"search-{label}",
                {field: value},
                candidate_limit=candidate_limit,
            )
            if not searches[label].get("matched"):
                raise RuntimeError(
                    f"runtime abundance criterion {field} did not match observed value {value}"
                )

    summary["searches"] = {
        label: {
            "matched": result.get("matched"),
            "candidates_checked": result.get("candidates_checked"),
            "candidate_count": result.get("candidate_count"),
            "evaluation_ns": result.get("evaluation_ns"),
            "max_evaluation_ns": result.get("max_evaluation_ns"),
            "max_slice_ns": result.get("max_slice_ns"),
            "matches": result.get("matches", []),
        }
        for label, result in searches.items()
    }
    summary["ping_after_full"] = client.submit("ping-after-full", "ping")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("smoke", "full"))
    parser.add_argument("--candidate-limit", type=int, default=protocol.MAX_CANDIDATES)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    run_id = f"{args.phase}-{time.time_ns()}"
    client = ResidentClient(run_id, default_timeout=args.timeout)
    summary_path = client.session / "results" / f"matrix-{run_id}-summary.json"
    summary: dict[str, object] = {
        "run_id": run_id,
        "phase": args.phase,
        "session": client.session.name,
        "started_at_ns": time.time_ns(),
        "status": "running",
    }
    _atomic_json(summary_path, summary)
    try:
        _run_smoke(client, summary)
        _atomic_json(summary_path, summary)
        if args.phase == "full":
            _run_full(client, summary, candidate_limit=args.candidate_limit)
        summary["status"] = "completed"
        summary["finished_at_ns"] = time.time_ns()
        summary["result_paths"] = client.result_paths
        _atomic_json(summary_path, summary)
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        summary["finished_at_ns"] = time.time_ns()
        summary["result_paths"] = client.result_paths
        _atomic_json(summary_path, summary)
        raise
    print(
        json.dumps(
            {"status": "completed", "summary": str(summary_path)}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
