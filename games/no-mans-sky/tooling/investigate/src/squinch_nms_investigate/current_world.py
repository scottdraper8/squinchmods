"""Read and validate the live current-world snapshot published by the NMS runtime."""

from __future__ import annotations

import math
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


def _rgb(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(channel, int | float) and math.isfinite(channel) for channel in value)
    )


def _appearance(value: object) -> bool:
    return (
        isinstance(value, dict)
        and _rgb(value.get("source_linear_rgb"))
        and _rgb(value.get("tone_mapped_srgb"))
        and set(value) == {"source_linear_rgb", "tone_mapped_srgb"}
    )


def _colour_observations(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    provenances = {
        "generated_reference_appearance",
        "grass_material_appearance",
        "flora_model_appearance",
    }
    for field, observation in value.items():
        if not isinstance(observation, dict):
            return False
        labels = observation.get("labels")
        evaluated = observation.get("evaluated_labels")
        if (
            not isinstance(observation.get("classification"), int)
            or not isinstance(labels, list)
            or any(not isinstance(label, str) for label in labels)
            or not isinstance(evaluated, list)
            or any(not isinstance(label, str) for label in evaluated)
            or not isinstance(observation.get("complete"), bool)
            or observation.get("provenance") not in provenances
        ):
            return False
        appearance = observation.get("appearance")
        if appearance is not None and not _appearance(appearance):
            return False
        components = observation.get("components", {})
        if not isinstance(components, dict) or any(
            component not in {"sky_colour", "sky_solar_colour", "sky_upper_colour", "sun_colour"}
            or not isinstance(component_observation, dict)
            or not isinstance(component_observation.get("classification"), int)
            or not _appearance(component_observation.get("appearance"))
            for component, component_observation in components.items()
        ):
            return False
        sky_reference = observation.get("sky_reference")
        if sky_reference is not None and (
            field != "sky"
            or not isinstance(sky_reference, dict)
            or set(sky_reference) != {"gradient_progress", "gradient_speed"}
            or not isinstance(sky_reference.get("gradient_progress"), int | float)
            or not math.isfinite(sky_reference["gradient_progress"])
            or not 0 <= sky_reference["gradient_progress"] <= 1
            or not _rgb(sky_reference.get("gradient_speed"))
            or any(channel < 0 for channel in sky_reference["gradient_speed"])
        ):
            return False
    return True


def _facts(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    fields = value.get("fields")
    colour_observations = value.get("colour_observations", {})
    flags = [value.get("planet_flags"), value.get("system_flags")]
    resources = value.get("resources")
    if (
        not isinstance(fields, dict)
        or not _colour_observations(colour_observations)
        or any(not isinstance(item, dict) for item in flags)
    ):
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


def _non_grass_surface_models(value: object) -> bool:
    if value is None:
        return True
    if (
        not isinstance(value, dict)
        or set(value) != {"classification", "labels", "complete", "models"}
        or not isinstance(value.get("classification"), int)
        or not isinstance(value.get("labels"), list)
        or any(not isinstance(label, str) for label in value["labels"])
        or not isinstance(value.get("complete"), bool)
        or not isinstance(value.get("models"), list)
    ):
        return False
    fields = {
        "model",
        "source_ground_index",
        "match_ground_colour",
        "ground_colour_index",
        "swap_primary_for_random",
        "swap_primary_for_secondary",
        "labels",
    }
    for model in value["models"]:
        if (
            not isinstance(model, dict)
            or not fields.issubset(model)
            or set(model) - fields - {"classification", "error"}
            or not isinstance(model.get("model"), str)
            or not model["model"]
            or not isinstance(model.get("source_ground_index"), int)
            or not isinstance(model.get("match_ground_colour"), bool)
            or not isinstance(model.get("ground_colour_index"), int)
            or not isinstance(model.get("swap_primary_for_random"), bool)
            or not isinstance(model.get("swap_primary_for_secondary"), bool)
            or not isinstance(model.get("labels"), list)
            or any(not isinstance(label, str) for label in model["labels"])
            or ("classification" in model) == ("error" in model)
            or ("classification" in model and not isinstance(model["classification"], int))
            or ("error" in model and not isinstance(model["error"], str))
            or ("error" in model and model["labels"])
        ):
            return False
    return True


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
        or not _non_grass_surface_models(world.get("non_grass_surface_models"))
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
