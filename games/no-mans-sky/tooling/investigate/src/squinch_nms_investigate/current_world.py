"""Read and validate the live current-world snapshot published by the NMS runtime."""

from __future__ import annotations

from pathlib import Path

from . import runtime_protocol
from .errors import InvestigationError


def inspect(directory: Path, *, timeout: float = 120) -> tuple[dict, dict, dict]:
    """Ask the live runtime for fresh native facts, then validate its published snapshot."""
    result = runtime_protocol.command(
        directory,
        {"type": "inspect_current"},
        timeout=timeout,
    )
    command_id = result["acknowledgement"]["command_id"]
    return snapshot(directory, command_id=command_id)


def _facts(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    fields = value.get("fields")
    flags = [value.get("planet_flags"), value.get("system_flags")]
    resources = value.get("resources")
    if not isinstance(fields, dict) or any(not isinstance(item, dict) for item in flags):
        return False
    if resources is not None and (
        not isinstance(resources, list) or any(not isinstance(item, str) for item in resources)
    ):
        return False
    return all(
        isinstance(observation, dict)
        and isinstance(observation.get("native"), int)
        and isinstance(observation.get("labels"), list)
        and all(isinstance(label, str) for label in observation["labels"])
        for observation in fields.values()
    ) and all(
        isinstance(flag, str) and isinstance(state, bool)
        for item in flags
        for flag, state in item.items()
    )


def snapshot(directory: Path, *, command_id: int | None = None) -> tuple[dict, dict, dict]:
    endpoint, state = runtime_protocol.status(directory, required_capability="nms.current-world/v1")
    player = state.get("player")
    world = state.get("current_world")
    if not isinstance(player, int):
        raise InvestigationError(
            "current_world_unavailable", "NMS does not currently have a loaded system"
        )
    if world is None:
        raise InvestigationError(
            "current_world_uncaptured",
            "The current system has not been captured by the installed NMS runtime",
            player=player,
        )
    if not isinstance(world, dict) or world.get("schema") != 1:
        raise InvestigationError("current_world_incompatible", "Unsupported current-world snapshot")
    if (
        not isinstance(world.get("command_id"), int)
        or world["command_id"] < 1
        or (command_id is not None and world["command_id"] != command_id)
    ):
        raise InvestigationError(
            "current_world_changed", "Current-world snapshot does not belong to this request"
        )
    if world.get("address") != player:
        raise InvestigationError(
            "current_world_changed", "The player location changed while facts were published"
        )
    system = world.get("system")
    planet = world.get("planet")
    evaluations = world.get("criteria_evaluations")
    sections = world.get("section_evaluations")
    verdicts = {"match", "no_match", "unknown"}
    if (
        world.get("acquisition") != "criteria_and_core"
        or not isinstance(world.get("criteria"), dict)
        or world.get("system_verdict") not in verdicts
        or world.get("target_verdict") not in verdicts
        or (world.get("planet_verdict") is not None and world["planet_verdict"] not in verdicts)
        or not _facts(system)
        or (planet is not None and not _facts(planet))
        or not isinstance(evaluations, list)
        or not isinstance(sections, list)
        or any(
            not isinstance(item, dict)
            or item.get("scope") not in {"system", "planet"}
            or not isinstance(item.get("description"), str)
            or not isinstance(item.get("predicate"), dict)
            or item.get("verdict") not in verdicts
            for item in evaluations
        )
        or any(
            not isinstance(item, dict)
            or item.get("scope") not in {"system", "planet"}
            or item.get("mode") not in {"all", "any"}
            or item.get("verdict") not in verdicts
            for item in sections
        )
    ):
        raise InvestigationError("current_world_incompatible", "Malformed current-world facts")
    return endpoint, state, world
