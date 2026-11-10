"""Generate isolated SDR world-colour-filter samples from current game LUTs."""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

WORLD_FILTER_VALUES = (
    0,
    2,
    4,
    6,
    8,
    9,
    10,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    27,
    42,
    43,
    44,
    45,
    51,
    57,
    58,
    60,
    61,
    63,
    69,
    70,
    71,
    72,
    73,
    74,
    75,
    76,
    77,
    78,
    79,
    80,
    81,
    82,
)

DESCRIPTIONS = {
    0: "Default grading",
    12: "Selective grey with red/orange accents",
    13: "Cool shadows, warm highlights",
    14: "Red/orange colour remapping",
    15: "Hue shift with violet shadows",
    16: "Red-biased colour remapping",
    17: "Dark grey/red",
    18: "Amber/sepia",
    19: "Muted colours, warm highlights",
}

TEST_COLOURS = (
    (0.8, 0.1, 0.1),
    (0.9, 0.5, 0.1),
    (0.8, 0.8, 0.1),
    (0.1, 0.8, 0.1),
    (0.1, 0.8, 0.8),
    (0.1, 0.1, 0.8),
    (0.8, 0.1, 0.8),
    (0.1, 0.1, 0.1),
    (0.5, 0.5, 0.5),
    (0.9, 0.9, 0.9),
)


def child(node: ET.Element, name: str) -> ET.Element | None:
    return node.find(f"./Property[@name='{name}']")


def value(node: ET.Element, name: str) -> str:
    result = child(node, name)
    return result.attrib.get("value", "") if result is not None else ""


def filter_metadata(path: Path) -> list[dict]:
    document = ET.parse(path).getroot()
    if document.attrib.get("template") != "cGcScreenFilterTable":
        raise ValueError(f"not a cGcScreenFilterTable: {path}")
    filters = child(document, "Filters")
    if filters is None:
        raise ValueError(f"screen-filter table has no Filters: {path}")
    entries = list(filters)
    if max(WORLD_FILTER_VALUES) >= len(entries):
        raise ValueError(
            "screen-filter table is shorter than the supported world-filter set"
        )

    records = []
    for native_value in WORLD_FILTER_VALUES:
        entry = entries[native_value]
        sdr = value(entry, "FilenameSdr").replace("\\", "/").casefold()
        hdr = value(entry, "FilenameHdr").replace("\\", "/").casefold()
        if not sdr.endswith(".dds") or not hdr.endswith(".dds"):
            raise ValueError(f"world filter {native_value} has incomplete LUT paths")
        records.append(
            {
                "native_value": native_value,
                "name": entry.attrib.get("name", f"Filter {native_value}"),
                "sdr": sdr,
                "hdr": hdr,
                "fade_distance": float(value(entry, "FadeDistance") or 0),
                "description": DESCRIPTIONS.get(native_value, ""),
            }
        )
    return records


class SdrLut:
    def __init__(self, path: Path) -> None:
        data = path.read_bytes()

        def u32(offset: int) -> int:
            return struct.unpack_from("<I", data, offset)[0]

        if len(data) < 128 or data[:4] != b"DDS " or u32(4) != 124:
            raise ValueError(f"invalid world-colour LUT header: {path}")
        self.size = u32(16)
        if (
            self.size not in {16, 32}
            or u32(12) != self.size
            or u32(24) != self.size
            or u32(80) & 0x40 == 0
            or u32(84) != 0
            or u32(88) != 32
            or [u32(offset) for offset in (92, 96, 100, 104)]
            != [0xFF0000, 0xFF00, 0xFF, 0xFF000000]
            or len(data) != 128 + self.size**3 * 4
        ):
            raise ValueError(f"unsupported world-colour LUT format: {path}")
        self.rgb = [
            (pixel[2] / 255, pixel[1] / 255, pixel[0] / 255)
            for pixel in (
                data[offset : offset + 4] for offset in range(128, len(data), 4)
            )
        ]

    def sample(self, rgb: tuple[float, float, float]) -> list[float]:
        position = [
            min(self.size - 1, max(0.0, value * self.size - 0.5)) for value in rgb
        ]
        low = [int(value) for value in position]
        fraction = [position[index] - low[index] for index in range(3)]
        result = [0.0, 0.0, 0.0]
        for corner in range(8):
            high = [corner & 1 != 0, corner & 2 != 0, corner & 4 != 0]
            index = [
                min(low[axis] + int(high[axis]), self.size - 1) for axis in range(3)
            ]
            weight = 1.0
            for axis in range(3):
                weight *= fraction[axis] if high[axis] else 1 - fraction[axis]
            sample = self.rgb[(index[2] * self.size + index[1]) * self.size + index[0]]
            for axis in range(3):
                result[axis] += sample[axis] * weight
        return [min(1.0, max(0.0, value)) for value in result]


def generate(source_manifest: Path) -> tuple[dict, list[dict]]:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    metadata = filter_metadata(Path(source["screen_filter_document"]))
    lut_sources = {
        record["logical_path"].casefold(): Path(record["path"])
        for record in source["colour_filter_lut_sources"]
    }
    required = {record[field] for record in metadata for field in ("sdr", "hdr")}
    missing = sorted(required - set(lut_sources))
    if missing:
        raise ValueError("missing world-colour LUT sources: " + ", ".join(missing))

    records = []
    for record in metadata:
        lut = SdrLut(lut_sources[record["sdr"]])
        records.append(
            {
                **record,
                "samples": [lut.sample(colour) for colour in TEST_COLOURS],
                "grey_ramp": [
                    lut.sample((step / 63, step / 63, step / 63)) for step in range(64)
                ],
            }
        )
    return (
        {
            "count": len(records),
            "nativeValues": [record["native_value"] for record in records],
            "mode": "isolated SDR LUT trilinear samples",
        },
        records,
    )
