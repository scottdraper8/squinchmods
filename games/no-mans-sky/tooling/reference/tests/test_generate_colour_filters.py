from __future__ import annotations

import importlib.util
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "generate_colour_filters.py"
SPEC = importlib.util.spec_from_file_location("generate_colour_filters", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def property_node(name: str, value: str = "") -> ET.Element:
    attributes = {"name": name}
    if value:
        attributes["value"] = value
    return ET.Element("Property", attributes)


def test_reads_supported_world_filter_metadata(tmp_path: Path) -> None:
    root = ET.Element("Data", {"template": "cGcScreenFilterTable"})
    filters = property_node("Filters")
    root.append(filters)
    for index in range(83):
        record = property_node(f"Filter{index}", "GcScreenFilterData")
        record.extend(
            [
                property_node("FilenameSdr", f"TEXTURES/LUT/FILTERS/{index}.DDS"),
                property_node("FilenameHdr", f"TEXTURES/LUT/FILTERSHDR/{index}.DDS"),
                property_node(
                    "FadeDistance", "100.000000" if index == 15 else "0.000000"
                ),
            ]
        )
        filters.append(record)
    path = tmp_path / "screenfilters.MXML"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    records = MODULE.filter_metadata(path)
    assert len(records) == 41
    assert [record["native_value"] for record in records] == list(
        MODULE.WORLD_FILTER_VALUES
    )
    weird4 = next(record for record in records if record["native_value"] == 15)
    assert weird4["name"] == "Filter15"
    assert weird4["fade_distance"] == 100
    assert weird4["description"] == "Hue shift with violet shadows"


def test_decodes_and_samples_supported_sdr_lut(tmp_path: Path) -> None:
    size = 16
    header = bytearray(128)
    header[:4] = b"DDS "
    for offset, value in {
        4: 124,
        12: size,
        16: size,
        24: size,
        80: 0x40,
        84: 0,
        88: 32,
        92: 0xFF0000,
        96: 0xFF00,
        100: 0xFF,
        104: 0xFF000000,
    }.items():
        struct.pack_into("<I", header, offset, value)
    pixels = bytearray()
    for blue in range(size):
        for green in range(size):
            for red in range(size):
                pixels.extend((blue * 17, green * 17, red * 17, 255))
    path = tmp_path / "identity.dds"
    path.write_bytes(header + pixels)

    lut = MODULE.SdrLut(path)
    assert lut.size == size
    assert lut.sample((0, 0, 0)) == [0, 0, 0]
    assert lut.sample((1, 1, 1)) == [1, 1, 1]
    assert all(abs(value - 0.5) < 0.001 for value in lut.sample((0.5, 0.5, 0.5)))
