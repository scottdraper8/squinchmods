from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .common import BuildError, run


def native_adapter(repo_root: Path, game_root: Path) -> Path:
    result = run(
        [
            str(repo_root / "tooling/squinch"),
            "nms-investigate",
            "native-search-probe",
            "--game-root",
            str(game_root),
            "--probe-tag",
            "R08",
            "--guide-preset-slots",
            "9",
            "--json",
        ],
        cwd=repo_root,
        capture=True,
    )
    payload = json.loads(result.stdout)
    source = Path(payload["data"]["probe"]["deployment_root"])
    validate_adapter(source)
    return source


def validate_adapter(source: Path) -> Path:
    source = source.expanduser().resolve()
    expected = {
        "LocTable.MXML",
        "METADATA/REALITY/WIKI.EXML",
        "METADATA/SIMULATION/MISSIONS/TABLES/NPCMISSIONTABLE.EXML",
        "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML",
    }
    actual = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise BuildError(f"unexpected navigation-adapter contents: {sorted(actual)}")
    wiki = (source / "METADATA/REALITY/WIKI.EXML").read_text(encoding="utf-8")
    missions = (
        source / "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML"
    ).read_text(encoding="utf-8")
    navigation_missions = (
        source / "METADATA/SIMULATION/MISSIONS/TABLES/NPCMISSIONTABLE.EXML"
    ).read_text(encoding="utf-8")
    required_wiki = (
        "MISSION.BLACKHOLE.ON.DDS",
        "MISSION.BLACKHOLE.OFF.DDS",
        "HUD/ICONS/WIKI/EXPLORATION4.DDS",
        "HUD/ICONS/WIKI/EXPLORATION2.DDS",
    )
    if any(value not in wiki for value in required_wiki):
        raise BuildError(
            "navigation adapter does not contain the selected production icons"
        )
    if (
        any(
            event not in missions
            for event in (
                "SE_SQN_SS_LUSH_R08",
                "SE_SQN_SS9_P08",
                "SE_SQN_SS9_R08",
                "SE_SQN_SS9_T08",
            )
        )
        or "SE_SQN_SS11_TGT" not in navigation_missions
    ):
        raise BuildError("navigation adapter does not contain the R08 dispatch range")
    combined_missions = missions + navigation_missions
    if (
        combined_missions.count('value="GcMissionConditionIsScanEventLocal"') != 11
        or combined_missions.count('name="BlockMissionRestart" value="false"') != 11
        or combined_missions.count('name="RequiresFullFireteam" value="false"') != 11
        or missions.count('value="GcMissionConditionIsScanEventActive"') != 9
        or missions.count('name="MustMatchThisMissionIDSeed" value="true"') != 9
        or combined_missions.count(
            'value="GcMissionConditionIsScanEventOnCurrentPlanet"'
        )
        != 11
        or combined_missions.count('name="AllowInShip" value="true"') != 11
        or combined_missions.count('value="GcMissionSequenceEndScanEvent"') != 40
        or combined_missions.count('value="GcMissionSequenceStartScanEvent"') != 20
        or combined_missions.count('value="GcMissionSequenceStartMission"') != 0
        or combined_missions.count('value="GcMissionSequenceShowMissionUpdateMessage"')
        != 11
        or 'value="GcMissionSequenceGetToScanEvent"' in combined_missions
        or combined_missions.count('name="EventEndType" value="None"') != 29
        or combined_missions.count('name="SolarSystemLocation" value="FromList"') != 10
        or combined_missions.count('name="UAsList" value="0000000000000000"') != 10
    ):
        raise BuildError(
            "navigation adapter does not contain the native FromList completion lifecycle"
        )
    return source


def is_owned_installed_adapter(source: Path) -> bool:
    """Recognize only this product's exact loose-file adapter footprint."""

    legacy_expected = {
        "LocTable.MXML",
        "METADATA/REALITY/WIKI.EXML",
        "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML",
    }
    expected = legacy_expected | {
        "METADATA/SIMULATION/MISSIONS/TABLES/NPCMISSIONTABLE.EXML"
    }
    if not source.is_dir():
        return False
    actual = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
    }
    if actual not in (legacy_expected, expected):
        return False
    try:
        wiki = (source / "METADATA/REALITY/WIKI.EXML").read_text(encoding="utf-8")
        missions = (
            source / "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML"
        ).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return "SQN_SS_CATEGORY" in wiki and "SE_SQN_SS_LUSH_R08" in missions


def superseded_adapter_roots(game_root: Path) -> list[Path]:
    """Find exact old investigation adapters, including Amethyst's redeploy source.

    Amethyst imports loose files into its ``overwrite`` tree and recreates the game-side symlinks
    on launch.  Removing only the deployed ``GAMEDATA/MODS`` directory therefore allows a retired
    probe to return on the next launch. Recognize only our exact legacy three-file adapter
    footprint and never select the production ``SearchProbes`` directory.
    """

    candidates: set[Path] = set()
    mods = game_root / "GAMEDATA/MODS"
    candidates.update(mods.glob("SQUINCH_INVESTIGATION_*"))

    manager_root = Path(
        os.environ.get(
            "SQN_NMS_AMETHYST_OVERWRITE",
            str(Path.home() / "Games/Amethyst/No Man's Sky/overwrite"),
        )
    ).expanduser()
    if manager_root.is_dir():
        candidates.update(manager_root.glob("SQUINCH_INVESTIGATION_*"))

    # A deployed adapter may consist of per-file symlinks into a manager store at a non-default
    # location. Recover that adapter root from the resolved mission-table path before retiring the
    # deployment directory.
    for candidate in tuple(candidates):
        event = candidate / "METADATA/SIMULATION/MISSIONS/TABLES/WIKIMISSIONTABLE.EXML"
        if event.is_symlink():
            resolved = event.resolve(strict=False)
            if len(resolved.parents) >= 5:
                candidates.add(resolved.parents[4])

    return sorted(
        candidate.resolve(strict=False)
        for candidate in candidates
        if candidate.name != "SearchProbes" and is_owned_installed_adapter(candidate)
    )


def retire_superseded_adapters(game_root: Path) -> list[Path]:
    """Move every recognized pre-production adapter source to the desktop trash."""

    candidates = superseded_adapter_roots(game_root)
    if not candidates:
        return []
    gio = shutil.which("gio")
    if not gio:
        raise BuildError(
            "cannot retire superseded adapters without the recoverable gio trash: "
            + ", ".join(str(path) for path in candidates)
        )
    retired: list[Path] = []
    for candidate in candidates:
        if candidate.exists():
            run([gio, "trash", str(candidate)])
            retired.append(candidate)
    return retired
