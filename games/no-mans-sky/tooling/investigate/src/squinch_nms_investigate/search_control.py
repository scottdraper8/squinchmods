"""Session-bound local control of the installed Search Probes Rust backend."""

from __future__ import annotations

import copy
from pathlib import Path

from .errors import InvestigationError
from .runtime_protocol import read_json


def settings_directory(game_root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve(strict=True)
    users = game_root.parents[1] / "compatdata/275850/pfx/drive_c/users"
    matches = sorted(p for p in users.glob("*/AppData/Local/SearchProbes") if p.is_dir())
    if len(matches) != 1:
        raise InvestigationError(
            "search_settings_ambiguous",
            "Specify --settings-dir for the running Search Probes installation",
            candidates=[str(p) for p in matches],
        )
    return matches[0].resolve()


def action_from_options(args, state: dict) -> dict:
    if args.action == "cancel":
        return {"type": "cancel"}
    settings = read_json(args.settings) if args.settings else copy.deepcopy(state["settings"])
    if args.criteria:
        settings["search"]["criteria"] = read_json(args.criteria)
    if args.systems is not None:
        settings["search"]["systems"] = args.systems
    if args.results is not None:
        settings["search"]["results"] = args.results
    if args.action == "configure":
        return {"type": "configure", "settings": settings}
    return {"type": "start", "settings": settings}
