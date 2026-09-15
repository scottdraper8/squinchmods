from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest


def _protocol():
    path = (
        Path(__file__).parents[3]
        / "mods/search-probes/src/search_probes/resident_search_protocol.py"
    )
    spec = importlib.util.spec_from_file_location("resident_search_protocol_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_graph_boundary_is_proven_for_diagnostics_and_the_form() -> None:
    protocol = _protocol()
    assert protocol.MAX_CANDIDATES == protocol.MAX_SURVEY_CANDIDATES == 20_000
    assert protocol.MAX_PROVEN_UI_CANDIDATES == 20_000


@pytest.mark.parametrize("conditions", ["Any", "None", "Non-extreme", "Extreme"])
def test_storm_conditions_are_validated_and_request_weather_capture(conditions):
    protocol = _protocol()
    criteria = protocol.normalize_criteria({"weather_conditions": conditions})
    assert criteria == {"weather_conditions": conditions}
    assert protocol.uses_planet_weather(criteria) == (conditions != "Any")
    with pytest.raises(ValueError, match="weather_conditions"):
        protocol.normalize_criteria({"weather_conditions": "Calmish"})


def test_navigation_address_targets_one_planet_without_changing_its_system() -> None:
    protocol = _protocol()
    system = 0x00009AFF278028A5
    assert protocol.universe_address_with_planet_index(system, 0) == 0x00109AFF278028A5
    target = protocol.universe_address_with_planet_index(system, 5)
    assert target == 0x00609AFF278028A5
    assert protocol.universe_address_reality_index(target) == 0xFF
    assert protocol.universe_address_with_planet_index(target, 2) == 0x00309AFF278028A5
    assert protocol.universe_address_planet_index(system) == 0
    assert protocol.universe_address_planet_index(target) == 6
    assert protocol.universe_address_system(target) == system
    for invalid in (-1, 0xFFF, True):
        with pytest.raises(ValueError, match="planet index"):
            protocol.universe_address_with_planet_index(system, invalid)


def test_live_universe_address_components_round_trip_the_observed_destination() -> None:
    protocol = _protocol()
    current_system = protocol.universe_address_from_components(
        planet_index=0,
        solar_system_index=160,
        voxel_x=-1883,
        voxel_y=39,
        voxel_z=-2046,
        reality_index=255,
    )
    assert current_system == 0x0000A0FF278028A5
    target = protocol.universe_address_from_components(
        planet_index=1,
        solar_system_index=160,
        voxel_x=-1883,
        voxel_y=39,
        voxel_z=-2046,
        reality_index=255,
    )
    assert target == 0x0010A0FF278028A5
    assert protocol.universe_address_system(current_system) == protocol.universe_address_system(
        target
    )

    with pytest.raises(ValueError, match="voxel_x"):
        protocol.universe_address_from_components(
            planet_index=0,
            solar_system_index=160,
            voxel_x=-2049,
            voxel_y=39,
            voxel_z=-2046,
            reality_index=255,
        )


def test_object_resolver_probe_requires_a_bounded_address_and_planet_index() -> None:
    protocol = _protocol()
    normalized = protocol.normalize_command(
        {
            "protocol": protocol.PROTOCOL_VERSION,
            "id": "resolver-control",
            "action": "object_resolver_probe",
            "address": "0x1234",
            "planet_index": 3,
        }
    )
    assert normalized["address"] == 0x1234
    assert normalized["planet_index"] == 3

    for planet_index in (-1, 16, True):
        with pytest.raises(ValueError, match="planet_index"):
            protocol.normalize_command(
                {
                    "protocol": protocol.PROTOCOL_VERSION,
                    "id": "resolver-invalid",
                    "action": "object_resolver_probe",
                    "address": 0x1234,
                    "planet_index": planet_index,
                }
            )


def test_system_name_probe_requires_a_bounded_address() -> None:
    protocol = _protocol()
    normalized = protocol.normalize_command(
        {
            "protocol": protocol.PROTOCOL_VERSION,
            "id": "name-control",
            "action": "system_name_probe",
            "address": "0x1234",
        }
    )
    assert normalized["address"] == 0x1234

    with pytest.raises(ValueError, match="address"):
        protocol.normalize_command(
            {
                "protocol": protocol.PROTOCOL_VERSION,
                "id": "name-invalid",
                "action": "system_name_probe",
            }
        )


def test_wiki_snapshot_is_a_parameterless_diagnostic_action() -> None:
    protocol = _protocol()
    assert protocol.normalize_command(
        {
            "protocol": protocol.PROTOCOL_VERSION,
            "id": "wiki-shape",
            "action": "wiki_snapshot",
        }
    ) == {
        "protocol": protocol.PROTOCOL_VERSION,
        "id": "wiki-shape",
        "generation": 0,
        "action": "wiki_snapshot",
    }


def test_wiki_mirror_probe_requires_a_bounded_nonempty_topic_array() -> None:
    protocol = _protocol()
    command = protocol.normalize_command(
        {
            "protocol": protocol.PROTOCOL_VERSION,
            "id": "wiki-mirror",
            "action": "wiki_mirror_probe",
            "topic_count": 64,
            "label_prefix": "Saved preset",
        }
    )
    assert command["topic_count"] == 64
    assert command["label_prefix"] == "Saved preset"

    for topic_count in (0, 129, True, None):
        with pytest.raises(ValueError, match="topic_count"):
            protocol.normalize_command(
                {
                    "protocol": protocol.PROTOCOL_VERSION,
                    "id": "wiki-mirror-invalid",
                    "action": "wiki_mirror_probe",
                    "topic_count": topic_count,
                }
            )


def test_launch_mode_defaults_to_overlay_and_accepts_explicit_headless(tmp_path: Path) -> None:
    protocol = _protocol()
    assert protocol.read_launch_overlay_enabled(tmp_path) is True
    (tmp_path / protocol.LAUNCH_MODE_FILE).write_text(
        '{"overlay_enabled":false,"protocol":1}\n', encoding="utf-8"
    )
    assert protocol.read_launch_overlay_enabled(tmp_path) is False


@pytest.mark.parametrize(
    "payload",
    (
        "{}\n",
        '{"overlay_enabled":0,"protocol":1}\n',
        '{"overlay_enabled":false,"protocol":2}\n',
    ),
)
def test_launch_mode_rejects_malformed_configuration(
    tmp_path: Path, payload: str
) -> None:
    protocol = _protocol()
    (tmp_path / protocol.LAUNCH_MODE_FILE).write_text(payload, encoding="utf-8")
    with pytest.raises((TypeError, ValueError), match="launch-mode"):
        protocol.read_launch_overlay_enabled(tmp_path)


def test_apply_criteria_changes_only_proven_primitive_fields() -> None:
    protocol = _protocol()
    original = bytes(protocol.EVENT_SIZE)
    result = protocol.apply_criteria(
        original,
        {
            "target_biome": "Frozen",
            "star_type": "Blue",
            "minimum_planets": 7,
            "wealth_class": "Wealthy",
            "trading_class": "Scientific",
            "conflict_level": "Low",
            "population_state": "Inhabited",
        },
    )

    assert len(result) == protocol.EVENT_SIZE
    assert struct.unpack_from("<I", result, 0x78)[0] == 7
    assert struct.unpack_from("<I", result, 0x7C)[0] == 4
    assert struct.unpack_from("<I", result, 0x84)[0] == 2
    assert struct.unpack_from("<I", result, 0x74)[0] == 2
    assert struct.unpack_from("<I", result, 0x70)[0] == 5
    assert struct.unpack_from("<I", result, 0x90)[0] == 0
    assert result[0x9F] == 1
    assert result[0xBB] == 1
    assert result[0xBC] == 1
    assert result[0xBD] == 1
    assert result[0xA9] == 1
    assert result[0xAA] == 1
    changed = (
        set(range(0x70, 0x80))
        | set(range(0x84, 0x88))
        | set(range(0x90, 0x94))
        | set(range(0x94, 0x98))
        | {0x9E, 0x9F, 0xA2, 0xA9, 0xAA, 0xBB, 0xBC, 0xBD}
    )
    assert all(
        result[index] == original[index] for index in range(len(result)) if index not in changed
    )


@pytest.mark.parametrize(
    "criteria",
    (
        {"sky_colour": "Blue"},
        {"target_biome": "Paradise"},
        {"star_type": "Orange"},
        {"minimum_planets": 0},
        {"minimum_planets": 9},
        {"minimum_planets": True},
        {"wealth_class": "ThreeStar"},
        {"trading_class": "Agriculture"},
        {"conflict_level": "Default"},
        {"population_state": "Uncharted"},
        {"race": "Builders"},
        {"biome_subtype": "Remix_D"},
        {"terrain_setting": "Continents"},
        {"sky_primary_hue": "Azure"},
        {"required_resources": []},
        {"required_resources": ["LUSH1", "LUSH1"]},
        {"required_resources": ["LUSH1", "NOT_A_RESOURCE"]},
    ),
)
def test_unproven_or_invalid_criteria_fail_closed(criteria: dict[str, object]) -> None:
    protocol = _protocol()
    with pytest.raises(ValueError):
        protocol.normalize_criteria(criteria)


def test_omitted_and_any_fields_are_neutralized_from_lush_template() -> None:
    protocol = _protocol()
    original = bytearray([0]) * protocol.EVENT_SIZE
    original[0x9F] = 1
    original[0xBB] = 1
    original[0xBC] = 1
    original[0xBD] = 1
    original[0x9E] = 1
    original[0xA2] = 1
    original[0xA9] = 1
    original[0xAA] = 1
    struct.pack_into("<I", original, 0x90, 3)

    for criteria in ({}, {"target_biome": "Any", "star_type": "Any"}):
        result = protocol.apply_criteria(bytes(original), criteria)
        assert result[0x9F] == 0
        assert result[0xBB] == 0
        assert result[0xBC] == 0
        assert result[0xBD] == 0
        assert result[0x9E] == 0
        assert result[0xA2] == 0
        assert result[0xA9] == 0
        assert result[0xAA] == 0
        assert struct.unpack_from("<I", result, 0x90)[0] == 1


def test_extended_fixed_fields_map_to_current_schema_offsets() -> None:
    protocol = _protocol()
    result = protocol.apply_criteria(
        bytes(protocol.EVENT_SIZE),
        {
            "biome_subtype": "HighQuality",
            "anomaly": "BlackHole",
            "race": "Explorers",
            "water_planet": "Require",
            "system_water": "Require",
            "extreme_weather_planet": "Exclude",
            "gas_giant_system": "Require",
        },
    )

    assert struct.unpack_from("<I", result, 0x8C)[0] == 2
    assert struct.unpack_from("<I", result, 0x88)[0] == 3
    assert struct.unpack_from("<I", result, 0x94)[0] == 2
    assert result[0xA8] == 1
    assert result[0xB9] == 1
    assert result[0xA5] == 0
    assert result[0xAC] == 1
    assert result[0xB5] == 1
    assert result[0xAD] == 0


@pytest.mark.parametrize(
    "criteria",
    (
        {"biome_subtype": "None"},
        {"anomaly": "None"},
        {"race": "None"},
        {"extreme_weather_planet": "Never"},
    ),
)
def test_extended_fixed_fields_reject_nonsemantic_values(
    criteria: dict[str, object],
) -> None:
    protocol = _protocol()
    with pytest.raises(ValueError):
        protocol.normalize_criteria(criteria)


def test_generated_snapshot_fields_accept_explicit_exclusion() -> None:
    protocol = _protocol()
    criteria = {
        field: "Exclude"
        for field in (
            "water_planet",
            "deep_water_planet",
            "extreme_hazard_planet",
            "corrupt_sentinel_planet",
            "planet_rings",
            "planet_has_moons",
            "floating_islands",
            "non_gas_giant_planet",
            "prime_planet",
            "sentinels",
            "infested_planet",
            "normal_planet",
            "relic_planet",
            "rgb_planet",
            "has_scrap",
            "pirate_system",
            "giant_planet_system",
            "gas_giant_system",
            "non_gas_giant_system",
            "waterworld_system",
            "system_water",
            "deep_water_system",
            "system_normal_planet",
            "system_relic_planet",
            "system_rgb_planet",
        )
    }
    assert protocol.normalize_criteria(criteria) == criteria


def test_resource_catalog_is_complete_for_the_current_runtime_survey() -> None:
    protocol = _protocol()
    assert len(protocol.RESOURCE_IDS) == 28
    assert set(protocol.RESOURCE_LABELS) == set(protocol.RESOURCE_IDS)
    assert len(set(protocol.RESOURCE_LABELS.values())) == len(protocol.RESOURCE_IDS)
    for resource in protocol.RESOURCE_IDS:
        assert protocol.normalize_criteria({"resource": resource}) == {"resource": resource}
    assert protocol.normalize_criteria({"required_resources": ["LUSH1", "CAVE1", "WATER1"]}) == {
        "required_resources": ["LUSH1", "CAVE1", "WATER1"]
    }


def test_only_positive_control_anomaly_values_are_marked_for_the_form() -> None:
    protocol = _protocol()
    assert protocol.PROVEN_ANOMALIES == ("AtlasStation", "BlackHole")
    assert set(protocol.PROVEN_ANOMALIES) < set(protocol.ANOMALIES)


def test_terrain_catalog_matches_current_generated_enum() -> None:
    protocol = _protocol()
    assert protocol.PROVEN_MINIMUM_PLANETS == (1, 2, 3, 4, 5)
    assert len(protocol.TERRAIN_SETTINGS) == 31
    assert protocol.TERRAIN_SETTINGS[0] == "FloatingIslands"
    assert protocol.TERRAIN_SETTINGS[11] == "FloatingIslandsPrime"
    assert protocol.TERRAIN_SETTINGS[21] == "FloatingIslandsPurple"
    for terrain in protocol.TERRAIN_SETTINGS:
        assert protocol.normalize_criteria({"terrain_setting": terrain}) == {
            "terrain_setting": terrain
        }


def test_primary_palette_hue_catalog_has_field_specific_positive_controls() -> None:
    protocol = _protocol()
    assert protocol.HUE_FAMILIES == (
        "Red",
        "Orange",
        "Yellow",
        "Green",
        "Cyan",
        "Blue",
        "Purple",
        "Magenta",
        "Neutral",
    )
    for field in protocol.PRIMARY_COLOUR_FIELDS:
        assert protocol.PROVEN_PRIMARY_HUES[field]
        assert set(protocol.PROVEN_PRIMARY_HUES[field]) <= set(protocol.HUE_FAMILIES)
        for hue in protocol.HUE_FAMILIES:
            assert protocol.normalize_criteria({field: hue}) == {field: hue}
        assert protocol.normalize_criteria({field: "Any"}) == {field: "Any"}
    assert protocol.uses_primary_colour({}) is False
    assert protocol.uses_primary_colour({"sky_primary_hue": "Any"}) is False
    assert protocol.uses_primary_colour({"sky_primary_hue": "Blue"}) is True


def test_planet_weather_catalog_is_bounded_and_capture_is_sparse() -> None:
    protocol = _protocol()
    assert protocol.STORM_FREQUENCIES == ("None", "Low", "High", "Always")
    assert protocol.PROVEN_STORM_FREQUENCIES == ("None", "Low", "High")
    assert protocol.WEATHER_INTENSITIES == ("Default", "Extreme")
    assert len(protocol.WEATHER_TYPES) == 17
    assert protocol.WEATHER_TYPES[:7] + protocol.WEATHER_TYPES[10:] == protocol.PROVEN_WEATHER_TYPES
    for field, values in (
        ("storm_frequency", protocol.STORM_FREQUENCIES),
        ("weather_intensity", protocol.WEATHER_INTENSITIES),
        ("weather_type", protocol.WEATHER_TYPES),
    ):
        for value in values:
            assert protocol.normalize_criteria({field: value}) == {field: value}
        assert protocol.normalize_criteria({field: "Any"}) == {field: "Any"}
    assert protocol.uses_planet_weather({}) is False
    assert protocol.uses_planet_weather({"storm_frequency": "Any"}) is False
    assert protocol.uses_planet_weather({"storm_frequency": "None"}) is True


def test_fixed_planet_metadata_catalog_is_bounded_and_capture_is_sparse() -> None:
    protocol = _protocol()
    for field, values in (
        ("life_level", protocol.PLANET_LIFE_LEVELS),
        ("creature_life_level", protocol.PLANET_LIFE_LEVELS),
        ("building_density", protocol.BUILDING_DENSITY_LEVELS),
        ("resource_level", protocol.RESOURCE_LEVELS),
    ):
        for value in values:
            assert protocol.normalize_criteria({field: value}) == {field: value}
    assert protocol.normalize_criteria({"paradise_planet": "Require"}) == {
        "paradise_planet": "Require"
    }
    assert protocol.uses_planet_metadata({}) is False
    assert protocol.uses_planet_metadata({"life_level": "Any"}) is False
    assert protocol.uses_planet_metadata({"life_level": "Full"}) is True
    assert protocol.uses_planet_spawn_flags({}) is False
    assert protocol.uses_planet_spawn_flags({"floating_islands": "Any"}) is False
    assert protocol.uses_planet_spawn_flags({"floating_islands": "Require"}) is True


def test_legacy_island_and_water_colour_aliases_normalize_to_current_fields() -> None:
    protocol = _protocol()
    assert protocol.normalize_criteria({"floating_island_objects": "Require"}) == {
        "floating_islands": "Require"
    }
    assert protocol.normalize_criteria({"near_water_primary_hue": "Cyan"}) == {
        "water_primary_hue": "Cyan"
    }
    with pytest.raises(ValueError, match="conflicting floating_island_objects"):
        protocol.normalize_criteria(
            {"floating_island_objects": "Require", "floating_islands": "Exclude"}
        )
    with pytest.raises(ValueError, match="conflicting near_water_primary_hue"):
        protocol.normalize_criteria(
            {"near_water_primary_hue": "Cyan", "water_primary_hue": "Blue"}
        )


@pytest.mark.parametrize(
    ("criteria", "expected"),
    (
        ({}, ("Pirate", "Empty", "Abandoned")),
        (
            {"wealth_class": "Any", "conflict_level": "Any"},
            ("Pirate", "Empty", "Abandoned"),
        ),
        ({"trading_class": "Mining"}, ()),
        ({"wealth_class": "Poor"}, ()),
        ({"wealth_class": "Pirate"}, ()),
        ({"conflict_level": "Low"}, ()),
        ({"conflict_level": "Pirate"}, ()),
        ({"race": "Traders"}, ()),
        ({"anomaly": "BlackHole"}, ()),
        ({"population_state": "Inhabited"}, ("Pirate",)),
        ({"population_state": "Empty"}, ()),
        ({"population_state": "Abandoned"}, ()),
    ),
)
def test_supplemental_passes_cover_only_unconstrained_native_categories(
    criteria: dict[str, object], expected: tuple[str, ...]
) -> None:
    protocol = _protocol()
    assert protocol.supplemental_system_passes(criteria) == expected


def test_candidate_command_normalizes_hex_address() -> None:
    protocol = _protocol()
    result = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "query-1",
            "generation": 3,
            "action": "candidate",
            "criteria": {"target_biome": "Lush"},
            "address": "0x00010E0477777777",
        }
    )
    assert result["address"] == 0x00010E0477777777
    assert result["generation"] == 3


def test_search_command_has_bounded_result_limit() -> None:
    protocol = _protocol()
    result = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "search-1",
            "generation": 4,
            "action": "search",
            "criteria": {"target_biome": "Frozen"},
            "result_limit": 3,
            "candidate_limit": 128,
        }
    )
    assert result["result_limit"] == 3
    assert result["candidate_limit"] == 128
    assert result["name"] == "System search"

    named = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "search-named",
            "generation": 5,
            "action": "search",
            "name": "  Blue paradise candidate  ",
            "criteria": {},
            "result_limit": 1,
            "candidate_limit": 64,
        }
    )
    assert named["name"] == "Blue paradise candidate"

    with pytest.raises(ValueError):
        protocol.normalize_command(
            {
                "protocol": 1,
                "id": "search-unbounded",
                "action": "search",
                "criteria": {},
                "result_limit": protocol.MAX_RESULTS + 1,
            }
        )


def test_snapshot_and_survey_commands_are_bounded_diagnostics() -> None:
    protocol = _protocol()
    snapshot = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "snapshot-1",
            "action": "snapshot",
            "address": "0x1234",
        }
    )
    assert snapshot["address"] == 0x1234

    survey = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "survey-1",
            "action": "survey",
            "candidate_limit": 5000,
        }
    )
    assert survey["candidate_limit"] == 5000

    colour_survey = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "colour-survey-1",
            "action": "colour_survey",
            "candidate_limit": protocol.MAX_SURVEY_CANDIDATES,
        }
    )
    assert colour_survey["candidate_limit"] == protocol.MAX_SURVEY_CANDIDATES

    spawn_survey = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "spawn-survey-1",
            "action": "spawn_survey",
            "candidate_limit": protocol.MAX_SURVEY_CANDIDATES,
        }
    )
    assert spawn_survey["candidate_limit"] == protocol.MAX_SURVEY_CANDIDATES

    navigate = protocol.normalize_command(
        {
            "protocol": 1,
            "id": "navigate-1",
            "action": "navigate",
            "address": "0x0000C30477777777",
        }
    )
    assert navigate["address"] == 0x0000C30477777777


def test_universe_address_reality_index_decodes_the_galaxy_byte() -> None:
    protocol = _protocol()
    assert protocol.universe_address_reality_index(0x0000000000000000) == 0
    assert protocol.universe_address_reality_index(0xABCDEF0901234567) == 9
    assert protocol.universe_address_reality_index(0xFFFFFFFFFFFFFFFF) == 255
    for invalid in (-1, 0x1_0000_0000_0000_0000, True, "0x1"):
        with pytest.raises(ValueError):
            protocol.universe_address_reality_index(invalid)
