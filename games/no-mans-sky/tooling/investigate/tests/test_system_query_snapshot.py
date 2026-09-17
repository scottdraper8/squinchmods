import importlib.util
import struct
import sys
from pathlib import Path

import pytest


def _load_module():
    source = Path(__file__).parents[3] / "mods/search-probes/src"
    package = source / "search_probes/system_query_snapshot.py"
    spec = importlib.util.spec_from_file_location(
        "search_probes.system_query_snapshot",
        package,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snapshot = _load_module()


def test_water_colour_requires_actual_water_on_the_target():
    decoded = snapshot.decode_query(_sample())
    for planet in decoded["planets"]:
        planet["primary_hues"] = {"Water": "Blue"}
        planet["has_water"] = False
    assert not snapshot.matches({"water_primary_hue": "Blue"}, decoded)[0]
    decoded["planets"][0]["has_water"] = True
    assert snapshot.matches({"water_primary_hue": "Blue"}, decoded)[0]


@pytest.mark.parametrize("frequency", [0, 1, 2, 3, None, 99])
@pytest.mark.parametrize("extreme", [False, True])
def test_storm_conditions_distinguish_frequency_from_climate(frequency, extreme):
    decoded = snapshot.decode_query(_sample())
    for planet in decoded["planets"]:
        planet["weather"] = {"storm_frequency": frequency, "weather_type": 2}
        planet["has_extreme_weather"] = extreme
    expected = (
        None
        if frequency not in range(4)
        else ("None" if frequency == 0 else "Extreme" if extreme else "Non-extreme")
    )
    for condition in ("None", "Non-extreme", "Extreme"):
        assert snapshot.matches({"weather_conditions": condition}, decoded)[0] == (
            condition == expected
        )


def _put_id(raw: bytearray, offset: int, value: str) -> None:
    encoded = value.encode("ascii")
    raw[offset : offset + 0x10] = encoded.ljust(0x10, b"\0")


def _put_fixed_string(raw: bytearray, offset: int, size: int, value: str) -> None:
    encoded = value.encode("utf-8")
    raw[offset : offset + size] = encoded.ljust(size, b"\0")


def _sample() -> bytes:
    raw = bytearray(snapshot.QUERY_SIZE)
    metadata = snapshot.METADATA_OFFSET
    struct.pack_into("<i", raw, metadata + 0x2544, 2)
    struct.pack_into("<i", raw, metadata + 0x2548, 1)
    struct.pack_into("<I", raw, metadata + 0x2520, 1)
    struct.pack_into("<I", raw, metadata + 0x2524, 2)
    struct.pack_into("<I", raw, metadata + 0x2530, 0)
    struct.pack_into("<I", raw, metadata + 0x2534, 0)
    struct.pack_into("<I", raw, metadata + 0x2550, 2)
    _put_fixed_string(raw, metadata + 0x2554, 0x80, "Generated System")
    for index in range(snapshot.MAX_PLANETS):
        struct.pack_into("<i", raw, metadata + 0x24B0 + index * 4, -1)

    planet = snapshot.PLANET_INPUT_OFFSET
    struct.pack_into("<I", raw, planet + 0x30, 0)
    struct.pack_into("<I", raw, planet + 0x34, 2)
    struct.pack_into("<i", raw, planet + 0x3C, 0)
    struct.pack_into("<I", raw, planet + 0x40, 0)
    raw[planet + 0x4D] = 1

    query = snapshot.PLANET_QUERY_OFFSET
    struct.pack_into("<I", raw, query + 0x80, 0)
    struct.pack_into("<I", raw, query + 0x84, 2)
    _put_id(raw, query + 0x88, "BLUE2")
    _put_id(raw, query + 0x98, "LUSH1")
    _put_id(raw, query + 0xA8, "CAVE1")
    raw[query + 0x120] = 1
    raw[query + 0x124] = 1
    raw[query + 0x132] = 1
    struct.pack_into("<i", raw, query + 0x134, 11)
    raw[query + 0x138] = 1
    raw[query + 0x13A] = 1

    moon = snapshot.PLANET_INPUT_OFFSET + snapshot.PLANET_INPUT_SIZE
    struct.pack_into("<i", raw, moon + 0x3C, 1)
    struct.pack_into("<I", raw, moon + 0x40, 3)
    struct.pack_into("<i", raw, metadata + 0x24B0 + 1 * 4, 0)
    moon_query = snapshot.PLANET_QUERY_OFFSET + snapshot.PLANET_QUERY_SIZE
    struct.pack_into("<I", raw, moon_query + 0x80, 4)
    struct.pack_into("<I", raw, moon_query + 0x84, 1)
    struct.pack_into("<i", raw, moon_query + 0x134, 1)
    return bytes(raw)


def test_decode_query_preserves_target_relationships_and_resources():
    result = snapshot.decode_query(_sample())
    assert result["planet_count"] == 2
    assert result["star_type"] == 2
    assert result["wealth_class"] == 2
    assert result["population_state"] == "Inhabited"
    assert result["system_name"] == "Generated System"
    assert result["planets"][0]["has_rings"] is True
    assert result["planets"][0]["moon_indices"] == (1,)
    assert result["planets"][0]["resources"] == ("BLUE2", "LUSH1", "CAVE1")
    assert result["planets"][0]["terrain_setting"] == "FloatingIslandsPrime"
    assert result["planets"][0]["has_floating_island_terrain"] is True
    assert "has_floating_islands" not in result["planets"][0]


def test_matches_requires_all_target_predicates_on_one_planet():
    decoded = snapshot.decode_query(_sample())
    decoded["planets"][0]["has_floating_islands"] = True
    decoded["planets"][1]["has_floating_islands"] = False
    decoded["planets"][0]["weather"] = {
        "storm_frequency": snapshot.STORM_FREQUENCIES.index("None"),
        "weather_intensity": snapshot.WEATHER_INTENSITIES.index("Default"),
        "weather_type": snapshot.WEATHER_TYPES.index("Humid"),
    }
    decoded["planets"][0]["primary_hues"] = {
        "Sky": "Blue",
        "Grass": "Green",
        "Water": "Cyan",
    }
    assert snapshot.matches(
        {
            "target_biome": "Lush",
            "star_type": "Blue",
            "wealth_class": "Wealthy",
            "conflict_level": "Low",
            "planet_size": "Large",
            "planet_rings": "Require",
            "planet_has_moons": "Require",
            "pirate_system": "Exclude",
            "water_planet": "Require",
            "floating_islands": "Require",
            "prime_planet": "Require",
            "sentinels": "Require",
            "suitable_creature_discovery": "Require",
            "suitable_creature_taming": "Require",
            "required_resources": ["LUSH1", "CAVE1"],
            "sky_primary_hue": "Blue",
            "grass_primary_hue": "Green",
            "storm_frequency": "None",
            "weather_intensity": "Default",
            "weather_type": "Humid",
        },
        decoded,
    ) == (True, 0)
    assert snapshot.matches({"target_biome": "Frozen", "planet_rings": "Require"}, decoded) == (
        False,
        None,
    )
    assert snapshot.matches({"pirate_system": "Require"}, decoded) == (False, None)
    assert snapshot.matches({"terrain_setting": "FloatingIslandsPrime"}, decoded) == (True, 0)
    assert snapshot.matches({"floating_islands": "Exclude"}, decoded) == (True, 1)
    assert snapshot.matches({"required_resources": ["LUSH1", "HOT1"]}, decoded) == (
        False,
        None,
    )
    assert snapshot.matches({"sky_primary_hue": "Green"}, decoded) == (False, None)
    assert snapshot.matches({"storm_frequency": "High"}, decoded) == (False, None)


def test_matches_fixed_planet_metadata_and_exact_paradise_predicate() -> None:
    decoded = snapshot.decode_query(_sample())
    decoded["planets"][0].update(
        {
            "life_level": snapshot.PLANET_LIFE_LEVELS.index("Full"),
            "creature_life_level": snapshot.PLANET_LIFE_LEVELS.index("Mid"),
            "building_density": snapshot.BUILDING_DENSITY_LEVELS.index("Full"),
            "resource_level": snapshot.RESOURCE_LEVELS.index("High"),
            "is_paradise": True,
        }
    )
    assert snapshot.matches(
        {
            "life_level": "Full",
            "creature_life_level": "Mid",
            "building_density": "Full",
            "resource_level": "High",
            "paradise_planet": "Require",
        },
        decoded,
    ) == (True, 0)
    assert snapshot.matches({"life_level": "Low"}, decoded) == (False, None)
    assert snapshot.matches({"paradise_planet": "Exclude"}, decoded) == (True, 1)


def test_exact_player_facing_paradise_predicate() -> None:
    baseline = {
        "biome": snapshot.BIOMES.index("Lush"),
        "biome_subtype": snapshot.BIOME_SUBTYPES.index("Standard") + 1,
        "weather_intensity": snapshot.WEATHER_INTENSITIES.index("Default"),
        "storm_frequency": snapshot.STORM_FREQUENCIES.index("None"),
        "sentinel_level": 0,
    }
    assert snapshot.is_paradise_planet(**baseline) is True
    assert (
        snapshot.is_paradise_planet(
            **{**baseline, "biome_subtype": snapshot.BIOME_SUBTYPES.index("HighQuality") + 1}
        )
        is True
    )
    for excluded in ("Structure", "Infested", "Swamp"):
        assert (
            snapshot.is_paradise_planet(
                **{
                    **baseline,
                    "biome_subtype": snapshot.BIOME_SUBTYPES.index(excluded) + 1,
                }
            )
            is False
        )
    for changed in (
        {"biome": snapshot.BIOMES.index("Frozen")},
        {"weather_intensity": snapshot.WEATHER_INTENSITIES.index("Extreme")},
        {"storm_frequency": snapshot.STORM_FREQUENCIES.index("Low")},
        {"sentinel_level": 1},
    ):
        assert snapshot.is_paradise_planet(**{**baseline, **changed}) is False


def test_matches_resolved_floating_island_objects_only_when_captured() -> None:
    decoded = snapshot.decode_query(_sample())
    assert snapshot.matches({"floating_islands": "Require"}, decoded) == (False, None)
    assert snapshot.matches({"floating_islands": "Exclude"}, decoded) == (False, None)
    decoded["planets"][0]["has_floating_islands"] = False
    decoded["planets"][1]["has_floating_islands"] = True
    assert snapshot.matches({"floating_islands": "Require"}, decoded) == (True, 1)
    assert snapshot.matches({"floating_islands": "Exclude"}, decoded) == (True, 0)


def test_unknown_snapshot_filter_is_not_silently_ignored():
    with pytest.raises(ValueError, match="unsupported snapshot criteria"):
        snapshot.matches({"misspelled_filter": "Require"}, snapshot.decode_query(_sample()))


def test_matching_planet_indices_retains_every_same_planet_candidate() -> None:
    decoded = snapshot.decode_query(_sample())
    assert snapshot.matching_planet_indices({}, decoded) == (0, 1)
    assert snapshot.matching_planet_indices({"target_biome": "Lush"}, decoded) == (0,)
    assert snapshot.matching_planet_indices({"target_biome": "Toxic"}, decoded) == ()


def test_primary_colour_hue_classification_is_deterministic() -> None:
    assert snapshot.classify_hue([1.0, 0.1, 0.1, 1.0]) == "Red"
    assert snapshot.classify_hue([0.8, 0.45, 0.1, 1.0]) == "Orange"
    assert snapshot.classify_hue([0.8, 0.8, 0.1, 1.0]) == "Yellow"
    assert snapshot.classify_hue([0.1, 0.8, 0.2, 1.0]) == "Green"
    assert snapshot.classify_hue([0.1, 0.8, 0.8, 1.0]) == "Cyan"
    assert snapshot.classify_hue([0.1, 0.2, 0.8, 1.0]) == "Blue"
    assert snapshot.classify_hue([0.5, 0.1, 0.8, 1.0]) == "Purple"
    assert snapshot.classify_hue([0.8, 0.1, 0.5, 1.0]) == "Magenta"
    assert snapshot.classify_hue([0.5, 0.52, 0.5, 1.0]) == "Neutral"


def test_decode_colour_palette_preserves_five_rgba_slots_and_indices() -> None:
    raw = bytearray(snapshot.COLOUR_PALETTE_SIZE)
    for slot in range(5):
        struct.pack_into(
            "<4f",
            raw,
            slot * 0x10,
            slot + 0.1,
            slot + 0.2,
            slot + 0.3,
            slot + 0.4,
        )
    struct.pack_into("<5i", raw, 0x50, 9, 8, 7, 6, 5)

    decoded = snapshot.decode_colour_palette(bytes(raw))
    assert decoded["indices"] == [9, 8, 7, 6, 5]
    assert len(decoded["colours"]) == 5
    assert decoded["colours"][0] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert decoded["colours"][4] == pytest.approx([4.1, 4.2, 4.3, 4.4])

    with pytest.raises(ValueError, match="exactly 0x70"):
        snapshot.decode_colour_palette(b"")


def test_giant_size_and_gas_giant_biome_are_distinct() -> None:
    raw = bytearray(_sample())
    first_input = snapshot.PLANET_INPUT_OFFSET
    first_query = snapshot.PLANET_QUERY_OFFSET
    struct.pack_into("<I", raw, first_input + 0x40, snapshot.PLANET_SIZES.index("Giant"))
    decoded = snapshot.decode_query(bytes(raw))
    assert decoded["has_giant_planet"] is True
    assert decoded["has_gas_giant"] is False
    assert decoded["has_non_gas_giant"] is True
    assert snapshot.matches({"non_gas_giant_planet": "Require"}, decoded) == (True, 0)

    struct.pack_into("<I", raw, first_query + 0x80, snapshot.BIOMES.index("GasGiant"))
    decoded = snapshot.decode_query(bytes(raw))
    assert decoded["has_giant_planet"] is True
    assert decoded["has_gas_giant"] is True
    assert decoded["has_non_gas_giant"] is False
    assert snapshot.matches({"gas_giant_system": "Require"}, decoded) == (True, 0)
    assert snapshot.matches({"non_gas_giant_system": "Require"}, decoded) == (False, None)


def test_native_biome_group_predicates_have_exact_snapshot_equivalents() -> None:
    raw = bytearray(_sample())
    first_query = snapshot.PLANET_QUERY_OFFSET
    struct.pack_into("<I", raw, first_query + 0x80, snapshot.BIOMES.index("Weird"))
    struct.pack_into(
        "<I",
        raw,
        first_query + 0x84,
        snapshot.BIOME_SUBTYPES.index("Structure") + 1,
    )
    decoded = snapshot.decode_query(bytes(raw))
    assert decoded["has_relic_planet"] is True
    assert decoded["has_normal_planet"] is True  # the second body is ordinary
    assert snapshot.matches({"system_relic_planet": "Require"}, decoded) == (True, 0)
    assert snapshot.matches({"relic_planet": "Require"}, decoded) == (True, 0)
    assert snapshot.matches({"normal_planet": "Require"}, decoded) == (True, 1)

    struct.pack_into("<I", raw, first_query + 0x80, snapshot.BIOMES.index("Blue"))
    decoded = snapshot.decode_query(bytes(raw))
    assert decoded["has_rgb_planet"] is True
    assert snapshot.matches({"rgb_planet": "Require"}, decoded) == (True, 0)


def test_scrap_filter_requires_captured_planet_metadata() -> None:
    decoded = snapshot.decode_query(_sample())
    assert snapshot.matches({"has_scrap": "Require"}, decoded) == (False, None)
    decoded["planets"][0]["has_scrap"] = True
    decoded["planets"][1]["has_scrap"] = False
    assert snapshot.matches({"has_scrap": "Require"}, decoded) == (True, 0)
    assert snapshot.matches({"has_scrap": "Exclude"}, decoded) == (True, 1)


def test_summarize_match_labels_only_decoded_fields():
    decoded = snapshot.decode_query(_sample())
    decoded["planets"][0]["weather"] = {
        "storm_frequency": 0,
        "weather_intensity": 0,
        "weather_type": 2,
    }
    summary = snapshot.summarize_match(decoded, 0)
    assert summary["system"] == {
        "name": "Generated System",
        "star_type": "Blue",
        "planet_count": 2,
        "wealth_class": "Wealthy",
        "trading_class": "HighTech",
        "conflict_level": "Low",
        "population_state": "Inhabited",
        "race": "Traders",
        "system_class": "Default",
        "is_pirate": False,
        "has_giant_planet": False,
        "has_gas_giant": False,
        "has_non_gas_giant": False,
        "has_waterworld": False,
        "has_water_planet": True,
        "has_deep_water_planet": False,
        "has_weird_planet": False,
        "has_infested_planet": False,
        "has_normal_planet": True,
        "has_relic_planet": False,
        "has_rgb_planet": False,
        "has_corrupt_sentinel_planet": False,
        "has_extreme_storm_planet": False,
    }
    assert summary["planet"] == {
        "name": "",
        "index": 0,
        "planet_index": 0,
        "biome": "Lush",
        "biome_subtype": "HighQuality",
        "size": "Large",
        "terrain_setting": "FloatingIslandsPrime",
        "has_floating_island_terrain": True,
        "has_rings": True,
        "moon_count": 1,
        "resources": ["BLUE2", "LUSH1", "CAVE1"],
        "has_water": True,
        "has_deep_water": False,
        "has_extreme_weather": False,
        "has_extreme_hazard": False,
        "has_extreme_sentinels": False,
        "has_corrupt_sentinels": False,
        "has_sentinels": True,
        "is_prime": True,
        "is_infested": False,
        "is_normal": True,
        "is_relic": False,
        "is_rgb": False,
        "suitable_creature_discovery": True,
        "suitable_weird_creature_discovery": False,
        "suitable_creature_taming": True,
        "suitable_robot_creature_discovery": False,
        "storm_frequency": "None",
        "weather_intensity": "Default",
        "weather_type": "Humid",
    }


def test_summary_uses_the_complete_current_alien_race_enum() -> None:
    raw = bytearray(_sample())
    struct.pack_into("<I", raw, snapshot.METADATA_OFFSET + 0x2534, 7)
    assert (
        snapshot.summarize_match(snapshot.decode_query(bytes(raw)), 0)["system"]["race"] == "None"
    )
    struct.pack_into("<I", raw, snapshot.METADATA_OFFSET + 0x2534, 8)
    assert (
        snapshot.summarize_match(snapshot.decode_query(bytes(raw)), 0)["system"]["race"]
        == "Builders"
    )


def test_decode_rejects_invalid_size_or_count():
    try:
        snapshot.decode_query(b"")
    except ValueError as exc:
        assert "exactly" in str(exc)
    else:
        raise AssertionError("short query snapshot was accepted")

    raw = bytearray(snapshot.QUERY_SIZE)
    struct.pack_into("<i", raw, snapshot.METADATA_OFFSET + 0x2544, 9)
    try:
        snapshot.decode_query(bytes(raw))
    except ValueError as exc:
        assert "planet count" in str(exc)
    else:
        raise AssertionError("invalid planet count was accepted")


@pytest.mark.parametrize(
    ("difficulty_offset", "expected"),
    (
        (0, (False, False, False)),
        (1, (True, False, False)),
        (2, (True, True, True)),
        (3, (True, True, False)),
    ),
)
def test_difficulty_selected_sentinel_flags_use_the_runtime_offset(
    difficulty_offset, expected
):
    raw = bytearray(_sample())
    query = snapshot.PLANET_QUERY_OFFSET
    raw[query + 0x124 : query + 0x128] = bytes((0, 1, 1, 1))
    raw[query + 0x128 : query + 0x12C] = bytes((0, 0, 1, 1))
    raw[query + 0x12C : query + 0x130] = bytes((0, 0, 1, 0))
    decoded = snapshot.decode_query(bytes(raw), difficulty_offset=difficulty_offset)
    planet = decoded["planets"][0]
    assert (
        planet["has_sentinels"],
        planet["has_extreme_sentinels"],
        planet["has_corrupt_sentinels"],
    ) == expected


def test_system_extreme_storm_requires_extreme_flag_and_nonzero_frequency() -> None:
    raw = bytearray(_sample())
    query = snapshot.PLANET_QUERY_OFFSET
    raw[query + 0x130] = 1
    assert snapshot.decode_query(bytes(raw))["has_extreme_storm_planet"] is False
    struct.pack_into("<I", raw, query + 0x168, 2)
    assert snapshot.decode_query(bytes(raw))["has_extreme_storm_planet"] is True


def test_protocol_and_snapshot_enum_contracts_stay_identical():
    from search_probes import resident_search_protocol as protocol

    for name in (
        "BIOMES",
        "STAR_TYPES",
        "WEALTH_CLASSES",
        "TRADING_CLASSES",
        "CONFLICT_LEVELS",
        "PLANET_SIZES",
        "BIOME_SUBTYPES",
        "TERRAIN_SETTINGS",
        "HUE_FAMILIES",
        "STORM_FREQUENCIES",
        "WEATHER_INTENSITIES",
        "WEATHER_TYPES",
        "PLANET_LIFE_LEVELS",
        "BUILDING_DENSITY_LEVELS",
        "RESOURCE_LEVELS",
        "SYSTEM_CLASSES",
        "RACE_ENUM",
    ):
        assert getattr(snapshot, name) == getattr(protocol, name)
