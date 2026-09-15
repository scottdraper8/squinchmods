from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from search_probes import overlay_form as form
from search_probes import overlay_platform as platform
from search_probes import overlay_results as results


def _overlay_module():
    path = (
        Path(__file__).parents[3]
        / "mods/search-probes/src/search_probes/resident_search_overlay.py"
    )
    spec = importlib.util.spec_from_file_location("resident_search_overlay_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_criteria_omits_any_and_converts_minimum_planets() -> None:
    _overlay_module()
    assert form.build_criteria(
        {
            "target_biome": "Lush",
            "planet_size": "Large",
            "terrain_setting": "FloatingIslandsPrime",
            "floating_islands": "Require",
            "paradise_planet": "Require",
            "life_level": "Full",
            "creature_life_level": "Mid",
            "building_density": "Full",
            "resource_level": "High",
            "planet_rings": "Exclude",
            "grass_primary_hue": "Green",
            "sky_primary_hue": "Blue",
            "resource": "LUSH1",
            "weather_conditions": "None",
            "weather_type": "Humid",
            "required_resources": ["LUSH1", "CAVE1", "Any"],
            "star_type": "Blue",
            "minimum_planets": "6",
            "wealth_class": "Wealthy",
            "trading_class": "Any",
            "conflict_level": "Low",
            "population_state": "Inhabited",
            "anomaly": "BlackHole",
            "pirate_system": "Exclude",
        }
    ) == {
        "target_biome": "Lush",
        "planet_size": "Large",
        "terrain_setting": "FloatingIslandsPrime",
        "floating_islands": "Require",
        "paradise_planet": "Require",
        "life_level": "Full",
        "creature_life_level": "Mid",
        "building_density": "Full",
        "resource_level": "High",
        "planet_rings": "Exclude",
        "grass_primary_hue": "Green",
        "sky_primary_hue": "Blue",
        "resource": "LUSH1",
        "weather_conditions": "None",
        "weather_type": "Humid",
        "required_resources": ["LUSH1", "CAVE1"],
        "star_type": "Blue",
        "minimum_planets": 6,
        "wealth_class": "Wealthy",
        "conflict_level": "Low",
        "population_state": "Inhabited",
        "anomaly": "BlackHole",
        "pirate_system": "Exclude",
    }


def test_build_criteria_all_any_is_empty() -> None:
    _overlay_module()
    assert form.build_criteria({}) == {}


def test_form_exposes_all_proven_generated_planet_groups() -> None:
    _overlay_module()
    assert {
        "floating_islands",
        "normal_planet",
        "relic_planet",
        "rgb_planet",
        "has_scrap",
        "system_normal_planet",
        "system_relic_planet",
        "system_rgb_planet",
    } <= set(form.FORM_CRITERIA_FIELDS)
    assert sum(field == "floating_islands" for field in form.FORM_CRITERIA_FIELDS) == 1
    assert "cloud_primary_hue" not in form.FORM_CRITERIA_FIELDS
    assert "weather_intensity" not in form.FORM_CRITERIA_FIELDS

    overlay_source = Path(
        Path(__file__).parents[3]
        / "mods/search-probes/src/search_probes/resident_search_overlay.py"
    ).read_text(encoding="utf-8")
    terrain_section = overlay_source.split('"Terrain family (exact)"', 1)[1].split(
        '"Floating islands"', 1
    )[0]
    exclusion = terrain_section.split("not in {", 1)[1].split("}", 1)[0]
    excluded_values = {
        "FloatingIslands",
        "FloatingIslandsPrime",
        "FloatingIslandsPurple",
    }
    assert all(f'"{value}"' in exclusion for value in excluded_values)
    assert not any(
        f'"{value}"' in terrain_section.split("not in {", 1)[0] for value in excluded_values
    )


def test_earthlike_preset_resets_every_filter_and_remains_editable() -> None:
    _overlay_module()
    assert form.BUILTIN_PRESETS is form._PRESETS.DEFAULT_PRESETS
    assert form.PROVEN_PRESETS == {
        "Earthlike": {
            "target_biome": "Lush",
            "paradise_planet": "Require",
            "grass_primary_hue": "Green",
            "sky_primary_hue": "Blue",
            "planet_has_moons": "Require",
        }
    }
    earthlike = form.preset_form_values("Earthlike")
    assert set(earthlike) == set(form.FORM_WIDGET_FIELDS)
    assert earthlike["target_biome"] == "Lush"
    assert earthlike["paradise_planet"] == "Require"
    assert earthlike["grass_primary_hue"] == "Green"
    assert earthlike["sky_primary_hue"] == "Blue"
    assert earthlike["planet_has_moons"] == "Require"
    assert earthlike["weather_conditions"] == "Any"
    assert earthlike["resource_label_1"] == "Any"

    try:
        form.preset_form_values("Unproved preset")
    except ValueError as exc:
        assert "unknown preset" in str(exc)
    else:
        raise AssertionError("an unknown preset was accepted")


def test_stored_criteria_expand_to_resource_and_population_widgets() -> None:
    _overlay_module()
    values = form.criteria_form_values(
        {
            "population_state": "Empty",
            "required_resources": ["LUSH1", "WATER1"],
            "planet_rings": "Require",
        },
        {"LUSH1": "Star Bulb", "WATER1": "Salt"},
    )
    assert set(values) == set(form.FORM_WIDGET_FIELDS)
    assert values["population_label"] == "Uncharted / empty"
    assert values["resource_label_1"] == "Star Bulb"
    assert values["resource_label_2"] == "Salt"
    assert values["resource_label_3"] == "Any"
    assert values["planet_rings"] == "Require"


def test_saved_criteria_split_and_merge_preserves_hidden_filters() -> None:
    _overlay_module()
    criteria = {
        "target_biome": "Lush",
        "required_resources": ["LUSH1"],
        "cloud_primary_hue": "Neutral",
        "storm_frequency": "None",
        "weather_intensity": "Default",
    }
    values, extras = form.split_criteria(criteria, {"LUSH1": "Star Bulb"})
    assert values["target_biome"] == "Lush"
    assert values["resource_label_1"] == "Star Bulb"
    assert extras == {
        "cloud_primary_hue": "Neutral",
        "storm_frequency": "None",
        "weather_intensity": "Default",
    }
    values["required_resources"] = ["LUSH1"]
    assert form.merge_criteria(values, extras) == criteria
    values["minimum_planets"] = "Any"
    assert "minimum_planets" not in form.merge_criteria(values, {"minimum_planets": 7})


def test_ui_layout_scales_with_the_nms_window_and_stays_bounded() -> None:
    _overlay_module()
    standard = platform.compute_ui_layout((0, 0, 1920, 1080))
    assert standard["font_scale"] == 1.0
    assert standard["viewport_width"] == 760
    assert standard["viewport_height"] == 850
    assert standard["viewport_x"] == 1136

    four_k = platform.compute_ui_layout((0, 0, 3840, 2160))
    assert four_k["font_scale"] == 2.0
    assert four_k["viewport_width"] == 1520
    assert four_k["viewport_height"] == 1700
    assert four_k["viewport_x"] == 2296

    small = platform.compute_ui_layout((20, 30, 1300, 750))
    assert small["font_scale"] == 1.0
    assert small["viewport_width"] <= 1280 - 48
    assert small["viewport_height"] <= 720 - 96

    try:
        platform.compute_ui_layout((0, 0, 320, 240))
    except ValueError as exc:
        assert "too small" in str(exc)
    else:
        raise AssertionError("an unusably small NMS window was accepted")


def test_native_bootstrap_overlay_starts_hidden() -> None:
    overlay = _overlay_module()
    from search_probes.overlay_client import OverlayClient

    instance = overlay.ResidentSearchOverlay(
        OverlayClient(
            Path("commands"),
            Path("results"),
            threading.Lock(),
            lambda: 0,
            lambda: {"revision": 0, "state": "idle"},
            SimpleNamespace(names=lambda: [], get=lambda _name: None),
            lambda *_args, **_kwargs: None,
        )
    )
    assert instance._visible is False
    assert instance._passive is False


def test_active_progress_requires_a_nonactivating_window() -> None:
    _overlay_module()
    assert platform.progress_requires_passive_window("overlay-1", {"state": "idle"})
    assert platform.progress_requires_passive_window(None, {"state": "searching"})
    assert not platform.progress_requires_passive_window(None, {"state": "completed"})


def test_win32_hotkey_polling_emits_only_a_rising_edge() -> None:
    _overlay_module()
    assert platform.key_press_transition(0x0000, False) == (False, False)
    assert platform.key_press_transition(0x8000, False) == (True, True)
    assert platform.key_press_transition(-0x8000, True) == (False, True)
    assert platform.key_press_transition(0x0001, True) == (False, False)


def test_wait_for_open_exits_without_toggle_when_stopped() -> None:
    overlay = _overlay_module()
    instance = overlay.ResidentSearchOverlay.__new__(overlay.ResidentSearchOverlay)
    instance._stop = threading.Event()
    instance._toggle = threading.Event()
    instance._ready = threading.Event()
    instance._stop.set()
    assert (
        instance._wait_for_open(lambda _key: pytest.fail("stopped poll must not read F7")) is False
    )


def test_wait_for_open_sets_toggle_on_f7_rising_edge_and_returns_key_state() -> None:
    overlay = _overlay_module()
    instance = overlay.ResidentSearchOverlay.__new__(overlay.ResidentSearchOverlay)
    instance._stop = threading.Event()
    instance._toggle = threading.Event()
    instance._ready = threading.Event()
    assert instance._wait_for_open(lambda _key: 0x8000) is True
    assert instance._toggle.is_set()


def test_wait_for_open_honors_programmatic_toggle_without_f7() -> None:
    overlay = _overlay_module()
    instance = overlay.ResidentSearchOverlay.__new__(overlay.ResidentSearchOverlay)
    instance._stop = threading.Event()
    instance._toggle = threading.Event()
    instance._ready = threading.Event()
    instance._toggle.set()
    assert instance._wait_for_open(lambda _key: 0) is False


def test_overlay_thread_reaches_ready_without_importing_dearpygui(monkeypatch) -> None:
    overlay = _overlay_module()
    import ctypes

    class User32:
        @staticmethod
        def GetAsyncKeyState(_key):
            return 0

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=User32()), raising=False)
    imported: list[str] = []
    original_import = __import__

    def track_import(name, *args, **kwargs):
        if name.startswith(("dearpygui", "win32")):
            imported.append(name)
            raise AssertionError(f"cold overlay imported UI dependency: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", track_import)
    client = SimpleNamespace(_generation_getter=lambda: 0, emit=lambda *_args, **_kwargs: None)
    instance = overlay.ResidentSearchOverlay(client)
    instance.start(timeout=1)
    assert instance._ready.is_set()
    instance.close()
    assert imported == []
    assert "dearpygui.dearpygui" not in sys.modules


def test_candidate_limit_text_is_strictly_bounded() -> None:
    _overlay_module()
    assert platform.parse_candidate_limit(" 5000 ", 20_000) == 5000
    assert platform.parse_candidate_limit(1, 20_000) == 1
    for invalid in ("", "0", "20001", "1.5", "-2", "five"):
        with pytest.raises(ValueError, match="Maximum systems"):
            platform.parse_candidate_limit(invalid, 20_000)


def test_result_reads_hold_the_probe_io_lock(tmp_path: Path) -> None:
    overlay = _overlay_module()
    from search_probes.overlay_client import OverlayClient

    path = tmp_path / "result.json"
    path.write_text('{"status":"completed"}\n', encoding="utf-8")
    events: list[str] = []

    class Lock:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, *_args):
            events.append("exit")

    instance = overlay.ResidentSearchOverlay.__new__(overlay.ResidentSearchOverlay)
    instance._client = OverlayClient(
        tmp_path / "commands",
        tmp_path / "results",
        Lock(),
        lambda: 0,
        lambda: {},
        SimpleNamespace(),
        lambda *_args, **_kwargs: None,
    )
    assert instance._read_result(path) == {"status": "completed"}
    assert events == ["enter", "exit"]


def test_result_formatting_uses_proven_summary_fields() -> None:
    _overlay_module()
    match = {
        "address": "0x0003E90477777777",
        "galaxy_number": 5,
        "rank": 70,
        "evaluation_pass": "generated_snapshot:planet=0",
        "summary": {
            "system": {
                "name": "Oteginu",
                "star_type": "Blue",
                "wealth_class": "Wealthy",
                "trading_class": "Scientific",
                "conflict_level": "Low",
                "population_state": "Inhabited",
                "race": "Explorers",
                "is_pirate": False,
                "has_giant_planet": True,
                "has_gas_giant": False,
                "has_non_gas_giant": True,
                "has_waterworld": False,
                "has_water_planet": True,
                "has_deep_water_planet": False,
                "has_weird_planet": False,
                "has_infested_planet": False,
                "has_corrupt_sentinel_planet": False,
                "has_extreme_storm_planet": False,
            },
            "planet": {
                "name": "Luyon",
                "index": 0,
                "biome": "Lush",
                "biome_subtype": "HighQuality",
                "size": "Giant",
                "terrain_setting": "FloatingIslandsPrime",
                "has_floating_islands": True,
                "has_floating_island_objects": True,
                "has_rings": True,
                "moon_count": 2,
                "resources": ["LUSH1", "CAVE1"],
                "has_water": True,
                "has_deep_water": False,
                "storm_frequency": "None",
                "weather_intensity": "Default",
                "weather_type": "Humid",
                "is_paradise": True,
                "life_level": "Full",
                "creature_life_level": "Full",
                "building_density": "Mid",
                "resource_level": "High",
                "has_extreme_weather": False,
                "has_extreme_hazard": False,
                "has_extreme_sentinels": False,
                "has_corrupt_sentinels": False,
                "has_sentinels": True,
                "is_prime": True,
                "is_infested": False,
                "suitable_creature_discovery": True,
                "suitable_weird_creature_discovery": False,
                "suitable_creature_taming": True,
                "suitable_robot_creature_discovery": False,
                "primary_hues": {
                    "Grass": "Green",
                    "Water": "Cyan",
                    "Sky": "Blue",
                    "Clouds": "Neutral",
                    "Sunset": "Orange",
                    "Night": "Blue",
                },
            },
        },
    }
    assert results.format_result_label(match, 0) == (
        "1. Luyon · Lush / Giant · Blue · Wealthy · Low · rank 70 · planet 1"
    )
    details = results.format_result_details(match, {"LUSH1": "Paraffinium", "CAVE1": "Cobalt"})
    assert "0x0003E90477777777" in details
    assert "Galaxy: #5" in details
    assert "Paraffinium, Cobalt" in details
    assert "Survey resources: Paraffinium, Cobalt" in details
    assert "HighQuality" in details
    assert "FloatingIslandsPrime" in details
    assert "floating islands yes" in details
    assert "floating-island terrain" not in details
    assert "floating-island objects" not in details
    assert "System contains: giant yes, gas giant no" in details
    assert "Creature suitability: discovery yes" in details
    assert "Grass: Green" in details
    assert "Sky: Blue" in details
    assert "Clouds: Neutral" not in details
    assert "Sunset: Orange" not in details
    assert "Night: Blue" not in details
    assert "Weather: Humid · storm frequency None · intensity Default" in details
    assert "generated name: Luyon" in details
    assert "Generated system name: Oteginu" in details
    assert "paradise yes" in details
    assert "generated life Full" in details
    assert "generated buildings Mid" in details


def test_system_only_result_formatting_does_not_invent_a_target_planet() -> None:
    _overlay_module()
    match = {
        "address": "0x000079FF278028A5",
        "rank": 42,
        "evaluation_pass": "primary",
        "summary": {
            "system": {
                "name": "Noyama",
                "star_type": "Yellow",
                "wealth_class": "Average",
                "conflict_level": "Low",
            },
            "planet": {},
        },
    }
    assert results.format_result_label(match, 0) == ("1. Noyama · Yellow · Average · Low · rank 42")
    details = results.format_result_details(match, {})
    assert "Generated system name: Noyama" in details
    assert "Planet type" not in details
