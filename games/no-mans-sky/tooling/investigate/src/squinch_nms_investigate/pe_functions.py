from __future__ import annotations

import bisect
import struct
from pathlib import Path

import pefile
from iced_x86 import Decoder, DecoderOptions, FlowControl, Formatter, FormatterSyntax, Register

from .errors import InvestigationError
from .paths import sha256_file
from .runs import write_json


def parse_address(value: str) -> int:
    try:
        result = int(value, 0)
    except ValueError as exc:
        raise InvestigationError("invalid_address", f"Invalid address: {value}") from exc
    if result < 0:
        raise InvestigationError("invalid_address", f"Address cannot be negative: {value}")
    return result


class _Image:
    def __init__(self, executable: Path):
        self.executable = executable.expanduser().resolve()
        if not self.executable.is_file() or self.executable.is_symlink():
            raise InvestigationError(
                "executable_not_found", f"Not a regular file: {self.executable}"
            )
        self.data = self.executable.read_bytes()
        try:
            self.pe = pefile.PE(data=self.data, fast_load=True)
        except pefile.PEFormatError as exc:
            raise InvestigationError("invalid_pe", f"Could not parse PE executable: {exc}") from exc
        self.image_base = int(self.pe.OPTIONAL_HEADER.ImageBase)
        self.sections = {
            section.Name.rstrip(b"\0").decode("ascii", errors="replace"): section
            for section in self.pe.sections
        }
        text = self.sections.get(".text")
        pdata = self.sections.get(".pdata")
        if text is None or pdata is None:
            raise InvestigationError(
                "invalid_pe", "PE executable requires .text and .pdata sections"
            )
        self.text = text
        self.function_ranges = self._function_ranges(pdata)
        self.function_starts = [start for start, _ in self.function_ranges]

    def _function_ranges(self, section) -> list[tuple[int, int]]:
        start = int(section.PointerToRawData)
        stop = start + int(section.SizeOfRawData)
        ranges = []
        for offset in range(start, stop - 11, 12):
            begin_rva, end_rva, _ = struct.unpack_from("<III", self.data, offset)
            if begin_rva and begin_rva < end_rva:
                ranges.append((self.image_base + begin_rva, self.image_base + end_rva))
        return sorted(set(ranges))

    def function_range(self, address: int) -> tuple[int, int] | None:
        index = bisect.bisect_right(self.function_starts, address) - 1
        if index >= 0:
            start, stop = self.function_ranges[index]
            if start <= address < stop:
                return start, stop
        return None

    def offset(self, address: int) -> int:
        rva = address - self.image_base
        try:
            return int(self.pe.get_offset_from_rva(rva))
        except pefile.PEFormatError as exc:
            raise InvestigationError(
                "unmapped_address", f"Address is not backed by PE file data: 0x{address:X}"
            ) from exc

    def decode(self, start: int, stop: int):
        offset = self.offset(start)
        return list(
            Decoder(
                64,
                self.data[offset : offset + stop - start],
                ip=start,
                options=DecoderOptions.NONE,
            )
        )

    def text_function_instructions(self):
        """Decode each unwind-bounded text fragment from its own instruction boundary."""

        text_start = self.image_base + int(self.text.VirtualAddress)
        text_stop = text_start + min(
            int(self.text.Misc_VirtualSize), int(self.text.SizeOfRawData)
        )
        for start, stop in self.function_ranges:
            if start < text_start or stop > text_stop:
                continue
            yield from self.decode(start, stop)

    def direct_callers(self, targets: set[int]) -> dict[int, list[int]]:
        result = {target: [] for target in targets}
        for instruction in self.text_function_instructions():
            if instruction.flow_control == FlowControl.CALL:
                target = instruction.near_branch_target
                if target in result:
                    result[target].append(instruction.ip)
        return result

    def memory_displacement_references(self, targets: set[int]) -> dict[int, list[dict]]:
        """Find base/index memory operands with an exact structure displacement.

        This intentionally excludes RIP-relative operands: iced-x86 exposes those as resolved
        virtual addresses, while this query is for offsets such as ``object + 0x3BF0``.
        Results are candidate structure-field xrefs, not proof that every base register has the
        same concrete type.
        """

        result = {target: [] for target in targets}
        formatter = Formatter(FormatterSyntax.NASM)
        for instruction in self.text_function_instructions():
            if instruction.is_ip_rel_memory_operand:
                continue
            if (
                instruction.memory_base == Register.NONE
                and instruction.memory_index == Register.NONE
            ):
                continue
            displacement = int(instruction.memory_displacement)
            if displacement not in result:
                continue
            bounds = self.function_range(instruction.ip)
            result[displacement].append(
                {
                    "instruction": instruction.ip,
                    "function_start": bounds[0] if bounds else None,
                    "function_stop": bounds[1] if bounds else None,
                    "text": formatter.format(instruction),
                }
            )
        return result

    def preferred_address_references(self, targets: set[int]) -> dict[int, dict[str, list[dict]]]:
        """Find exact references to preferred virtual addresses in code and PE data."""

        result = {target: {"instructions": [], "data": []} for target in targets}
        formatter = Formatter(FormatterSyntax.NASM)
        for instruction in self.text_function_instructions():
            if not instruction.is_ip_rel_memory_operand:
                continue
            target = instruction.ip_rel_memory_address
            if target not in result:
                continue
            bounds = self.function_range(instruction.ip)
            result[target]["instructions"].append(
                {
                    "instruction": instruction.ip,
                    "function_start": bounds[0] if bounds else None,
                    "function_stop": bounds[1] if bounds else None,
                    "text": formatter.format(instruction),
                }
            )

        for section_name, section in self.sections.items():
            if int(section.Characteristics) & 0x20000000:
                continue
            start = int(section.PointerToRawData)
            stop = min(start + int(section.SizeOfRawData), len(self.data))
            section_address = self.image_base + int(section.VirtualAddress)
            aligned_start = (start + 7) & ~7
            for offset in range(aligned_start, stop - 7, 8):
                target = struct.unpack_from("<Q", self.data, offset)[0]
                if target not in result:
                    continue
                result[target]["data"].append(
                    {
                        "section": section_name,
                        "address": section_address + (offset - start),
                        "file_offset": offset,
                        "target": target,
                    }
                )
        return result


def _reachable_fragments(image: _Image, address: int) -> list[tuple[tuple[int, int], list]]:
    entry = image.function_range(address)
    if entry is None:
        raise InvestigationError(
            "function_not_found",
            f"No x64 exception-table function contains address 0x{address:X}",
        )
    queued = [entry]
    seen: set[tuple[int, int]] = set()
    result = []
    while queued:
        bounds = queued.pop(0)
        if bounds in seen:
            continue
        seen.add(bounds)
        start, stop = bounds
        instructions = image.decode(start, stop)
        result.append((bounds, instructions))
        for instruction in instructions:
            if instruction.flow_control not in {
                FlowControl.CONDITIONAL_BRANCH,
                FlowControl.UNCONDITIONAL_BRANCH,
            }:
                continue
            target_bounds = image.function_range(instruction.near_branch_target)
            if target_bounds is not None and target_bounds not in seen:
                queued.append(target_bounds)
        if instructions and instructions[-1].flow_control in {
            FlowControl.NEXT,
            FlowControl.CONDITIONAL_BRANCH,
        }:
            fallthrough = image.function_range(stop)
            if fallthrough is not None and fallthrough[0] == stop and fallthrough not in seen:
                queued.append(fallthrough)
        if len(queued) + len(seen) > 256:
            raise InvestigationError(
                "function_graph_too_large",
                f"Direct-branch graph from 0x{address:X} exceeds 256 PE fragments",
            )
    return sorted(result, key=lambda item: item[0])


def _function_record(image: _Image, address: int, destination: Path) -> dict:
    fragments = _reachable_fragments(image, address)
    entry_bounds = image.function_range(address)
    assert entry_bounds is not None
    entry_start, entry_stop = entry_bounds
    formatter = Formatter(FormatterSyntax.NASM)
    lines = []
    for (start, stop), instructions in fragments:
        lines.append(f"; PE fragment {start:016X}-{stop:016X}")
        lines.extend(
            f"{instruction.ip:016X}  {formatter.format(instruction)}"
            for instruction in instructions
        )
    artifact = destination / f"function-{entry_start:016x}.asm"
    artifact.write_text("\n".join(lines) + "\n", encoding="utf-8")

    calls = []
    memory_references = []
    fragment_records = []
    for (start, stop), instructions in fragments:
        fragment_records.append(
            {
                "start": start,
                "stop": stop,
                "size": stop - start,
                "instructions": len(instructions),
            }
        )
        for instruction in instructions:
            if instruction.flow_control == FlowControl.CALL:
                target = instruction.near_branch_target
                if target:
                    target_bounds = image.function_range(target)
                    calls.append(
                        {
                            "instruction": instruction.ip,
                            "target": target,
                            "target_function_start": target_bounds[0] if target_bounds else None,
                            "target_function_stop": target_bounds[1] if target_bounds else None,
                        }
                    )
            if instruction.is_ip_rel_memory_operand:
                memory_references.append(
                    {
                        "instruction": instruction.ip,
                        "target": instruction.ip_rel_memory_address,
                    }
                )
    return {
        "requested_address": address,
        "function_start": entry_start,
        "function_stop": entry_stop,
        "size": sum(record["size"] for record in fragment_records),
        "instruction_count": sum(record["instructions"] for record in fragment_records),
        "fragments": fragment_records,
        "direct_calls": calls,
        "ip_relative_memory_references": memory_references,
        "disassembly": {"path": str(artifact), "sha256": sha256_file(artifact)},
    }


def _vtable_record(image: _Image, address: int, count: int) -> dict:
    if count < 1 or count > 1024:
        raise InvestigationError("invalid_vtable_count", "Vtable count must be from 1 to 1024")
    offset = image.offset(address)
    size = count * 8
    if offset + size > len(image.data):
        raise InvestigationError("truncated_vtable", "Vtable extends beyond the executable")
    entries = []
    for index in range(count):
        target = struct.unpack_from("<Q", image.data, offset + index * 8)[0]
        bounds = image.function_range(target)
        entries.append(
            {
                "index": index,
                "target": target,
                "target_function_start": bounds[0] if bounds else None,
                "target_function_stop": bounds[1] if bounds else None,
            }
        )
    return {"address": address, "count": count, "entries": entries}


def inspect_functions(
    executable: Path,
    addresses: list[int],
    destination: Path,
    *,
    include_callers: bool = False,
    vtable_address: int | None = None,
    vtable_count: int = 0,
    memory_displacements: list[int] | None = None,
    reference_addresses: list[int] | None = None,
) -> dict:
    memory_displacements = memory_displacements or []
    reference_addresses = reference_addresses or []
    if (
        not addresses
        and vtable_address is None
        and not memory_displacements
        and not reference_addresses
    ):
        raise InvestigationError(
            "missing_address",
            "At least one function, vtable, or memory displacement is required",
        )
    if len(set(addresses)) != len(addresses):
        raise InvestigationError("duplicate_address", "Function addresses must be unique")
    if len(set(memory_displacements)) != len(memory_displacements):
        raise InvestigationError(
            "duplicate_displacement", "Memory displacements must be unique"
        )
    if len(set(reference_addresses)) != len(reference_addresses):
        raise InvestigationError(
            "duplicate_reference_address", "Reference addresses must be unique"
        )
    destination.mkdir(parents=True, exist_ok=False)
    image = _Image(executable)
    functions = [_function_record(image, address, destination) for address in addresses]
    displacement_references = (
        image.memory_displacement_references(set(memory_displacements))
        if memory_displacements
        else {}
    )
    address_references = (
        image.preferred_address_references(set(reference_addresses))
        if reference_addresses
        else {}
    )
    if include_callers:
        targets = {
            fragment["start"] for record in functions for fragment in record["fragments"]
        }
        callers = image.direct_callers(targets)
        for record in functions:
            record["direct_callers"] = [
                {"instruction": instruction, "target_fragment_start": fragment["start"]}
                for fragment in record["fragments"]
                for instruction in callers[fragment["start"]]
            ]
    result = {
        "executable": str(image.executable),
        "executable_sha256": sha256_file(image.executable),
        "image_base": image.image_base,
        "functions": functions,
        "direct_callers_included": include_callers,
        "memory_displacement_references": {
            f"0x{displacement:X}": displacement_references[displacement]
            for displacement in memory_displacements
        },
        "preferred_address_references": {
            f"0x{address:X}": address_references[address]
            for address in reference_addresses
        },
        "vtable": (
            _vtable_record(image, vtable_address, vtable_count)
            if vtable_address is not None
            else None
        ),
    }
    report = destination / "report.json"
    write_json(report, result)
    return {
        "report": str(report),
        "report_sha256": sha256_file(report),
        "executable": result["executable"],
        "executable_sha256": result["executable_sha256"],
        "function_count": len(functions),
        "functions": [
            {
                "requested_address": record["requested_address"],
                "function_start": record["function_start"],
                "function_stop": record["function_stop"],
                "size": record["size"],
                "fragment_count": len(record["fragments"]),
                "instruction_count": record["instruction_count"],
                "direct_call_count": len(record["direct_calls"]),
                "direct_caller_count": len(record.get("direct_callers", [])),
                "disassembly": record["disassembly"],
            }
            for record in functions
        ],
        "direct_callers_included": include_callers,
        "memory_displacement_reference_counts": {
            f"0x{displacement:X}": len(displacement_references[displacement])
            for displacement in memory_displacements
        },
        "preferred_address_reference_counts": {
            f"0x{address:X}": {
                "instructions": len(address_references[address]["instructions"]),
                "data": len(address_references[address]["data"]),
            }
            for address in reference_addresses
        },
        "vtable_entry_count": vtable_count if vtable_address is not None else 0,
    }
