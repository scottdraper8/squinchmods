from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
from pathlib import Path

from .errors import InvestigationError
from .paths import sha256_file


def _pe_layout(data: bytes) -> dict:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise InvestigationError("invalid_pe", "Executable does not have a valid DOS header")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise InvestigationError("invalid_pe", "Executable does not have a valid PE header")
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    optional_offset = pe_offset + 24
    if optional_offset + optional_size > len(data) or optional_size < 32:
        raise InvestigationError("invalid_pe", "Executable has a truncated optional header")
    magic = struct.unpack_from("<H", data, optional_offset)[0]
    if magic == 0x20B:
        image_base = struct.unpack_from("<Q", data, optional_offset + 24)[0]
        format_name = "PE32+"
    elif magic == 0x10B:
        image_base = struct.unpack_from("<I", data, optional_offset + 28)[0]
        format_name = "PE32"
    else:
        raise InvestigationError("invalid_pe", f"Unsupported PE optional-header magic: 0x{magic:X}")
    section_offset = optional_offset + optional_size
    if section_offset + section_count * 40 > len(data):
        raise InvestigationError("invalid_pe", "Executable has truncated section headers")
    sections: list[dict] = []
    for index in range(section_count):
        offset = section_offset + index * 40
        raw_name = data[offset : offset + 8].split(b"\0", 1)[0]
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise InvestigationError("invalid_pe", "PE section name is not ASCII") from exc
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        characteristics = struct.unpack_from("<I", data, offset + 36)[0]
        sections.append(
            {
                "index": index,
                "name": name,
                "virtual_size": virtual_size,
                "relative_virtual_address": virtual_address,
                "raw_size": raw_size,
                "raw_offset": raw_offset,
                "characteristics": characteristics,
            }
        )
    return {
        "format": format_name,
        "image_base": image_base,
        "pe_header_offset": pe_offset,
        "section_count": section_count,
        "sections": sections,
    }


def _map_file_offset(layout: dict, file_offset: int) -> dict | None:
    for section in layout["sections"]:
        start = section["raw_offset"]
        end = start + section["raw_size"]
        if start <= file_offset < end:
            rva = section["relative_virtual_address"] + file_offset - start
            return {
                "section": section["name"],
                "relative_virtual_address": rva,
                "virtual_address": layout["image_base"] + rva,
            }
    return None


def _compile_signature(value: object, name: str) -> tuple[re.Pattern[bytes], int]:
    if not isinstance(value, str) or not value.strip():
        raise InvestigationError("invalid_signature", f"Missing signature for {name}")
    parts: list[bytes] = []
    tokens = value.split()
    for token in tokens:
        if token in {"?", "??"}:
            parts.append(b".")
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{2}", token):
            raise InvestigationError(
                "invalid_signature", f"Invalid signature token {token!r} for {name}"
            )
        parts.append(re.escape(bytes([int(token, 16)])))
    return re.compile(b"".join(parts), re.DOTALL), len(tokens)


def _objdump_identity() -> tuple[Path, str]:
    executable = shutil.which("objdump")
    if not executable:
        raise InvestigationError("objdump_not_found", "objdump is required for disassembly")
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise InvestigationError(
            "objdump_failed", "Could not identify objdump", output=completed.stderr.strip()
        )
    return Path(executable).resolve(), completed.stdout.splitlines()[0].strip()


def _disassemble(
    objdump: Path,
    executable: Path,
    destination: Path,
    start: int,
    byte_count: int,
) -> dict:
    stop = start + byte_count
    completed = subprocess.run(
        [
            str(objdump),
            "-d",
            "-M",
            "intel",
            f"--start-address=0x{start:x}",
            f"--stop-address=0x{stop:x}",
            str(executable),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise InvestigationError(
            "objdump_failed",
            "Could not disassemble the selected executable range",
            start=start,
            stop=stop,
            output=completed.stderr.strip(),
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(completed.stdout, encoding="utf-8")
    return {
        "path": str(destination),
        "sha256": sha256_file(destination),
        "preferred_virtual_address_start": start,
        "preferred_virtual_address_stop": stop,
        "requested_bytes": byte_count,
    }


def inspect_pattern_catalog(
    executable: Path,
    catalog: Path,
    names: list[str],
    destination: Path,
    *,
    match_limit: int = 20,
    disassemble_bytes: int = 0,
) -> dict:
    executable = executable.expanduser().resolve()
    catalog = catalog.expanduser().resolve()
    if not executable.is_file() or executable.is_symlink():
        raise InvestigationError("executable_not_found", f"Not a regular file: {executable}")
    if not catalog.is_file() or catalog.is_symlink():
        raise InvestigationError("pattern_catalog_not_found", f"Not a regular file: {catalog}")
    if not names or len(set(names)) != len(names) or not all(names):
        raise InvestigationError(
            "invalid_pattern_names", "Pattern names must be a nonempty unique list"
        )
    if match_limit < 1:
        raise InvestigationError("invalid_limit", "Pattern match limit must be positive")
    if disassemble_bytes < 0:
        raise InvestigationError("invalid_limit", "Disassembly byte count cannot be negative")
    try:
        entries = json.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvestigationError(
            "invalid_pattern_catalog", f"Could not read pattern catalog {catalog}: {exc}"
        ) from exc
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise InvestigationError(
            "invalid_pattern_catalog", "Pattern catalog must be an object array"
        )

    selected = [(index, entry) for index, entry in enumerate(entries) if entry.get("name") in names]
    missing = sorted(set(names) - {entry.get("name") for _, entry in selected})
    if missing:
        raise InvestigationError(
            "pattern_name_not_found", "Requested names are absent from the catalog", names=missing
        )

    destination.mkdir(parents=True, exist_ok=False)
    catalog_snapshot = destination / catalog.name
    shutil.copy2(catalog, catalog_snapshot)
    data = executable.read_bytes()
    pe = _pe_layout(data)
    results: list[dict] = []
    for selected_index, (catalog_index, entry) in enumerate(selected):
        name = entry["name"]
        signature = entry.get("signature")
        regex, signature_bytes = _compile_signature(signature, name)
        found = list(regex.finditer(data))
        results.append(
            {
                "catalog_index": catalog_index,
                "selected_index": selected_index,
                "name": name,
                "mangled_name": entry.get("mangled_name"),
                "signature": signature,
                "signature_bytes": signature_bytes,
                "match_count": len(found),
                "unique": len(found) == 1,
                "matches": [
                    {
                        "file_offset": match.start(),
                        "bytes": match.group().hex(" ").upper(),
                        "pe_location": _map_file_offset(pe, match.start()),
                    }
                    for match in found[:match_limit]
                ],
                "matches_truncated": len(found) > match_limit,
            }
        )
    objdump_data = None
    if disassemble_bytes:
        if not all(result["unique"] for result in results):
            raise InvestigationError(
                "nonunique_disassembly_target",
                "Disassembly requires exactly one match for every selected signature",
            )
        objdump, objdump_version = _objdump_identity()
        objdump_data = {"path": str(objdump), "version": objdump_version}
        for result in results:
            location = result["matches"][0]["pe_location"]
            if location is None:
                raise InvestigationError(
                    "unmapped_disassembly_target",
                    "Pattern match does not map to a PE section",
                    name=result["name"],
                )
            result["disassembly"] = _disassemble(
                objdump,
                executable,
                destination / "disassembly" / f"{result['selected_index']:04d}.txt",
                location["virtual_address"],
                disassemble_bytes,
            )
    return {
        "executable": str(executable),
        "executable_bytes": len(data),
        "executable_sha256": sha256_file(executable),
        "catalog": str(catalog),
        "catalog_snapshot": str(catalog_snapshot),
        "catalog_sha256": sha256_file(catalog),
        "pe": pe,
        "requested_names": names,
        "selected_signature_count": len(results),
        "all_matched": all(result["match_count"] > 0 for result in results),
        "all_unique": all(result["unique"] for result in results),
        "results": results,
        "disassembler": objdump_data,
        "disassemble_bytes": disassemble_bytes,
        "authority": "exact-byte-pattern-cardinality",
    }
