import json
import struct
from pathlib import Path

import pytest
from search_probes.planet_colours import capture_selected_colours, water_reflectance
from search_probes.system_query_snapshot import classify_hue

WATER_FIXTURE = json.loads(
    Path(__file__).with_name("fixtures").joinpath("water_reflectance.json").read_text()
)["records"]


@pytest.mark.parametrize("record", WATER_FIXTURE)
def test_water_reflectance_matches_native_calculation(record):
    assert water_reflectance(bytes.fromhex(record["raw"])) == pytest.approx(
        record["native"], abs=3e-7
    )


def test_reference_vegetation_base_colours():
    assert classify_hue((0.261, 0.283, 0.163)) == "Green"
    assert classify_hue((0.359, 0.400, 0.144)) == "Green"
    assert classify_hue((0.239, 0.188, 0.322)) == "Purple"
    assert classify_hue((1, 1, 0)) == "Yellow"
    assert classify_hue((0.8, 1, 0)) == "Green"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_hue_rejects_invalid_components(value):
    with pytest.raises(ValueError, match="finite and non-negative"):
        classify_hue((value, 0.2, 0.3))


def _memory(biome=0, subtype=13, fallback=True):
    planet, generator = 0x10000, 0x20000
    regions = {}
    regions[planet + 0x32B8] = struct.pack("<2i", biome, subtype)
    regions[planet + 0x1E34] = struct.pack("<3i", 0, 0, 0)
    regions[planet + 0x3518] = struct.pack("<i", 0)
    regions[planet + 0x1E44] = struct.pack("<i", 42)
    actual_biome = {25: 12, 26: 13}.get(subtype, biome)
    for ordinal, offset in enumerate((0x518, 0x520, 0x528)):
        table = 0x30000 + ordinal * 0x10000
        pointer = table + 0x1000
        regions[generator + offset] = struct.pack("<Q", table)
        header = struct.pack("<Qi4x", pointer, 1)
        regions[table + actual_biome * 16] = bytes(16) if fallback else header
        regions[table + 0x120] = header
        raw = bytearray(0xE0)
        struct.pack_into("<4f", raw, 0x70, 0.576, 0.812, 0.996, 1)
        regions[pointer] = bytes(raw)
    regions[generator + 0x530] = struct.pack("<Q", 0x60000)
    regions[0x60000] = struct.pack("<Qi4x", 0x61000, 1)
    regions[0x61000] = bytes.fromhex(WATER_FIXTURE[5]["raw"])

    def read(address, size):
        result = regions[address]
        assert len(result) == size
        return result

    return planet, generator, regions, read


@pytest.mark.parametrize("subtype", [13, 25, 26])
@pytest.mark.parametrize("fallback", [False, True])
def test_selected_colours_follow_biome_overrides_and_generic_fallback(subtype, fallback):
    planet, generator, _, read = _memory(subtype=subtype, fallback=fallback)
    captured = capture_selected_colours(planet, generator, read)
    assert classify_hue(captured["colours"]["Sky"]) == "Blue"
    assert captured["colours"]["Water"] == pytest.approx(WATER_FIXTURE[5]["native"], abs=3e-7)
    assert captured["sky_indices"] == {"day": 0, "dusk": 0, "night": 0}
    assert captured["screen_filter"] == 42
    assert "WaterNear" not in captured["colours"]


@pytest.mark.parametrize("index", [-1, 1, 100000])
def test_selected_colours_fail_closed_on_invalid_index(index):
    planet, generator, regions, read = _memory()
    regions[planet + 0x1E34] = struct.pack("<3i", index, 0, 0)
    with pytest.raises(ValueError, match="outside table"):
        capture_selected_colours(planet, generator, read)


@pytest.mark.parametrize("offset,value", [(0x40, float("nan")), (0x50, 2), (0x68, 0)])
def test_invalid_optical_coefficients_fail_closed(offset, value):
    raw = bytearray.fromhex(WATER_FIXTURE[0]["raw"])
    struct.pack_into("<f", raw, offset, value)
    with pytest.raises(ValueError):
        water_reflectance(raw)
