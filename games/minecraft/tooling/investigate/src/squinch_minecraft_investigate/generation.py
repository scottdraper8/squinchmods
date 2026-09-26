from __future__ import annotations

import time
from collections.abc import Callable

from .errors import InvestigationError
from .server import persist_active, run_commands


def tile_chunks(bounds: tuple[int, int, int, int], unit: str) -> list[dict]:
    """Convert inclusive block/chunk bounds into legal 16x16-chunk force-load tiles."""
    if unit not in {"block", "chunk"}:
        raise InvestigationError("invalid_unit", f"unsupported coordinate unit: {unit}")
    min_x, min_z, max_x, max_z = bounds
    if min_x > max_x or min_z > max_z:
        raise InvestigationError(
            "invalid_bounds", "bounds must be inclusive MIN_X MIN_Z MAX_X MAX_Z"
        )
    if unit == "block":
        min_x, max_x = min_x // 16, max_x // 16
        min_z, max_z = min_z // 16, max_z // 16
    regions: list[dict] = []
    for chunk_x in range(min_x, max_x + 1, 16):
        end_x = min(chunk_x + 15, max_x)
        for chunk_z in range(min_z, max_z + 1, 16):
            end_z = min(chunk_z + 15, max_z)
            regions.append(
                {
                    "chunk_min_x": chunk_x,
                    "chunk_min_z": chunk_z,
                    "chunk_max_x": end_x,
                    "chunk_max_z": end_z,
                    "block_min_x": chunk_x * 16,
                    "block_min_z": chunk_z * 16,
                    "block_max_x": (end_x + 1) * 16 - 1,
                    "block_max_z": (end_z + 1) * 16 - 1,
                }
            )
    return regions


def generate_regions(
    state: dict,
    bounds: tuple[int, int, int, int],
    unit: str,
    timeout: float,
    progress: Callable[[dict], None] | None = None,
) -> list[dict]:
    """Force-load tiles serially and persist exact ownership after each successful command."""
    regions = tile_chunks(bounds, unit)
    results: list[dict] = []
    started = time.monotonic()
    for index, region in enumerate(regions, 1):
        command = (
            f"forceload add {region['block_min_x']} {region['block_min_z']} "
            f"{region['block_max_x']} {region['block_max_z']}"
        )
        response = run_commands(state, [command], timeout)[0]
        state["forceload_regions"].append(region)
        persist_active(state)
        result = {
            "index": index,
            "region": region,
            "elapsed_seconds": time.monotonic() - started,
            **response,
        }
        results.append(result)
        if progress is not None:
            progress({"completed": index, "total": len(regions), **result})
    return results


def release_regions(
    state: dict,
    regions: list[dict],
    timeout: float,
) -> list[dict]:
    """Release exact owned force-load tiles and forget each only after acknowledgement."""
    results: list[dict] = []
    started = time.monotonic()
    for index, region in enumerate(reversed(regions), 1):
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise InvestigationError(
                "generation_release_timeout",
                "timed out while releasing generated force-load regions",
            )
        if region not in state["forceload_regions"]:
            raise InvestigationError(
                "generation_release_ownership",
                "generated force-load region is no longer owned by this run",
            )
        command = (
            f"forceload remove {region['block_min_x']} {region['block_min_z']} "
            f"{region['block_max_x']} {region['block_max_z']}"
        )
        response = run_commands(state, [command], remaining)[0]
        state["forceload_regions"].remove(region)
        persist_active(state)
        results.append(
            {
                "index": index,
                "region": region,
                "elapsed_seconds": time.monotonic() - started,
                **response,
            }
        )
    return results
