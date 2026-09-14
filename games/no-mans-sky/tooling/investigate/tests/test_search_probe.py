from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from search_probes.adapter_definitions import (
    CATEGORY_ICON_OFF,
    CATEGORY_ICON_ON,
    FORM_NAVIGATION_TARGET_EVENT_ID,
    FORM_NAVIGATION_TARGET_MISSION_ID,
    LOOKUP_BOOLEAN_FIELDS,
    PRESET_NOTIFY_ICON,
    PRESET_TOPIC_ICON,
)

from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.search_probe import (
    build_native_search_probe,
)


def _property(parent: ET.Element, name: str, value: str | None = None) -> ET.Element:
    attributes = {"name": name}
    if value is not None:
        attributes["value"] = value
    return ET.SubElement(parent, "Property", attributes)


def _write(path: Path, root: ET.Element) -> Path:
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def _texture(parent: ET.Element, name: str, filename: str) -> None:
    texture = _property(parent, name, "TkTextureResource")
    _property(texture, "Filename", filename)


def _texture_filename(parent: ET.Element, name: str) -> str:
    texture = next(child for child in parent if child.attrib.get("name") == name)
    return next(
        child.attrib["value"]
        for child in texture
        if child.attrib.get("name") == "Filename"
    )


def _lookup(parent: ET.Element, name: str) -> None:
    lookup = _property(parent, name, "GcScanEventSolarSystemLookup")
    for field in LOOKUP_BOOLEAN_FIELDS:
        _property(lookup, field, "false")
    for outer, inner, value in (
        ("UseRace", "AlienRace", "Gek"),
        ("UseAnomaly", "GalaxyStarAnomaly", "Atlas"),
        ("UseConflict", "ConflictLevel", "High"),
        ("NeedsBiomeType", "Biome", "Toxic"),
        ("UseBiomeSubType", "BiomeSubType", "Standard"),
    ):
        _property(_property(lookup, outer, f"Gc{outer}"), inner, value)
    for field, value in (
        ("NeedsResourceHint", "SOURCE"),
        ("NeedsSpecificCreature", "SOURCE"),
        ("SamePlanetAsEvent", "SOURCE"),
        ("SamePlanetAsSeasonParty", "2"),
        ("SystemNeedsResourceHint", "SOURCE"),
        ("MinPlanets", "6"),
    ):
        _property(lookup, field, value)


def _mission_source(path: Path) -> Path:
    root = ET.Element("Data", {"template": "cGcMissionTable"})
    missions = _property(root, "Missions")
    mission = _property(missions, "Missions", "GcGenericMissionSequence")
    for name, value in (
        ("MissionID", "WIKI_TRADE5"),
        ("MissionClass", "Secondary"),
        ("MessageComplete", "Default"),
        ("MessageStart", "Default"),
        ("CanRenounce", "false"),
        ("AutoStart", "None"),
        ("RestartOnCompletion", "false"),
        ("MissionObjective", "WIKI_TRADE5_MISSION_OBJ"),
    ):
        _property(mission, name, value)
    events = _property(mission, "ScanEvents")
    event = _property(events, "ScanEvents", "GcScanEventData")
    _property(event, "UAsList")
    for name, value in (
        ("Name", "SE_WIKI_MISSION_TRADE5"),
        ("AlwaysShow", "false"),
        ("EventEndType", "Interact"),
        ("DisableMultiplayerSync", "false"),
        ("ReplaceEventIfAlreadyActive", "false"),
        ("BuildingLocation", "Nearest"),
        ("SearchType", "SpaceStation"),
        ("ForceWideRandom", "true"),
        ("MustFindSystem", "false"),
        ("SolarSystemLocation", "LocalOrNear"),
        ("OSDMessage", "WIKI_MISSION_TRADE5_OSD"),
        ("MarkerLabel", "WIKI_MISSION_TRADE5_MARKER"),
    ):
        _property(event, name, value)
    interaction = _property(event, "ForceInteractionType", "GcInteractionType")
    _property(interaction, "InteractionType", "MissionGiver")
    _property(
        _property(event, "SpecificBuildingClass", "GcBuildingClassification"),
        "BuildingClass",
        "None",
    )
    _lookup(event, "SolarSystemAttributes")
    _lookup(event, "SolarSystemAttributesFallback")
    stages = _property(mission, "Stages")
    for stage_type in (
        "GcMissionSequenceGroup",
        "GcMissionSequenceStartScanEvent",
        "GcMissionSequenceGetToScanEvent",
    ):
        stage = _property(stages, "Stages", "GcGenericMissionStage")
        _property(stage, "Stage", stage_type)
        _property(stage, "Event", "SE_WIKI_MISSION_TRADE5")
    return _write(path, root)


def _wiki_source(path: Path) -> Path:
    root = ET.Element("Data", {"template": "cGcWiki"})
    categories = _property(root, "Categories")
    category = _property(categories, "Categories", "GcWikiCategory")
    _property(category, "CategoryID", "SOURCE_CATEGORY")
    _property(category, "CategoryIDUpper", "SOURCE_CATEGORY_U")
    _texture(category, "IconOn", "TEXTURES/SOURCE/CATEGORY.ON.DDS")
    _texture(category, "IconOff", "TEXTURES/SOURCE/CATEGORY.OFF.DDS")
    topics = _property(category, "Topics")
    topic = _property(topics, "Topics", "GcWikiTopic")
    for name, value in (
        ("TopicID", "SOURCE_TOPIC"),
        ("ShortDescriptionID", "SOURCE_SHORT"),
        ("Mission", ""),
        ("MissionButtonText", "SOURCE_BUTTON"),
        ("Seen", "false"),
        ("Unlocked", "false"),
    ):
        _property(topic, name, value)
    _texture(topic, "Icon", "TEXTURES/SOURCE/TOPIC.DDS")
    _texture(topic, "NotifyIcon", "TEXTURES/SOURCE/NOTIFY.DDS")
    pages = _property(topic, "Pages")
    page = _property(pages, "Pages", "GcWikiPage")
    _property(page, "PageID", "SOURCE_TOPIC")
    _texture(page, "Icon", "TEXTURES/SOURCE/PAGE.DDS")
    _property(page, "Content", "SOURCE_BODY")
    _property(_property(topic, "ActionSet", "GcActionSetType"), "ActionSetType", "VehicleMode")
    _property(_property(category, "Type", "GcWikiTopicType"), "WikiTopicType", "Guide")
    _property(category, "Items")
    _property(category, "UnseenCount", "1")
    _property(category, "UnlockedCount", "1")
    return _write(path, root)


def _reference_source(path: Path) -> Path:
    root = ET.Element("Data", {"template": "cGcMissionTable"})
    event = _property(root, "ScanEvents", "GcScanEventData")
    _property(event, "Name", "SE_PHOTO_BIOME_LUSH")
    _property(event, "BuildingLocation", "PlanetSearch")
    _property(event, "SearchType", "Any")
    _property(event, "ForceWideRandom", "true")
    _property(event, "MustFindSystem", "false")
    _property(event, "SolarSystemLocation", "LocalOrNear")
    building = _property(event, "SpecificBuildingClass", "GcBuildingClassification")
    _property(building, "BuildingClass", "None")
    lookup = _property(event, "SolarSystemAttributes", "GcScanEventSolarSystemLookup")
    _property(lookup, "NeedsBiome", "true")
    biome = _property(lookup, "NeedsBiomeType", "GcBiomeType")
    _property(biome, "Biome", "Lush")
    near_event = _property(root, "ScanEvents", "GcScanEventData")
    _property(near_event, "Name", "SE_CURRENT_NEAR")
    _property(near_event, "ForceWideRandom", "false")
    _property(near_event, "MustFindSystem", "false")
    _property(near_event, "SolarSystemLocation", "Near")
    return _write(path, root)


def test_build_native_search_probe_derives_bounded_lush_profile(tmp_path: Path) -> None:
    result = build_native_search_probe(
        _wiki_source(tmp_path / "wiki.MXML"),
        _mission_source(tmp_path / "missions.MXML"),
        _reference_source(tmp_path / "reference.MXML"),
        tmp_path / "probe",
    )

    mission_root = ET.parse(result["files"][1]["path"]).getroot()
    values = {
        node.attrib.get("name"): node.attrib.get("value") for node in mission_root.iter("Property")
    }
    assert values["MissionID"] == "SQN_SS_LUSH"
    assert values["MissionClass"] == "Secondary"
    assert values["Name"] == "SE_SQN_SS_LUSH"
    assert values["NeedsBiome"] == "true"
    assert values["Biome"] == "Lush"
    assert values["RequireUndiscovered"] == "false"
    assert values["NeedsWaterPlanet"] == "false"
    assert values["BuildingLocation"] == "PlanetSearch"
    assert values["SearchType"] == "Any"
    assert values["BuildingClass"] == "None"
    assert values["ForceWideRandom"] == "false"
    assert values["MustFindSystem"] == "false"
    assert values["SolarSystemLocation"] == "Near"
    assert values["ReplaceEventIfAlreadyActive"] == "true"
    assert values["EventEndType"] == "None"
    assert "GcMissionSequenceQuickWarp" not in values.values()
    stage_types = [
        node.attrib.get("value")
        for node in mission_root.iter("Property")
        if node.attrib.get("name") == "Stage"
    ]
    assert stage_types == [
        "GcMissionSequenceGroup",
        "GcMissionSequenceEndScanEvent",
        "GcMissionSequenceStartScanEvent",
        "GcMissionSequenceWaitForConditions",
        "GcMissionSequenceWaitForConditions",
        "GcMissionSequenceEndScanEvent",
        "GcMissionSequenceShowMissionUpdateMessage",
    ]
    assert "GcMissionSequenceGetToScanEvent" not in stage_types
    local_conditions = [
        node
        for node in mission_root.iter("Property")
        if node.attrib.get("name") == "GcMissionConditionIsScanEventLocal"
    ]
    assert len(local_conditions) == 1
    assert {
        node.attrib.get("name"): node.attrib.get("value") for node in local_conditions[0]
    } == {
        "Event": "SE_SQN_SS_LUSH",
        "BlockMissionRestart": "false",
        "RequiresFullFireteam": "false",
    }
    planet_conditions = [
        node
        for node in mission_root.iter("Property")
        if node.attrib.get("name") == "GcMissionConditionIsScanEventOnCurrentPlanet"
    ]
    assert len(planet_conditions) == 1
    assert {
        node.attrib.get("name"): node.attrib.get("value") for node in planet_conditions[0]
    } == {"Event": "SE_SQN_SS_LUSH", "AllowInShip": "true"}

    wiki_root = ET.parse(result["files"][0]["path"]).getroot()
    wiki_values = {
        node.attrib.get("name"): node.attrib.get("value") for node in wiki_root.iter("Property")
    }
    assert wiki_values["CategoryID"] == "SQN_SS_CATEGORY"
    assert wiki_values["Mission"] == "SQN_SS_LUSH"
    assert wiki_values["Unlocked"] == "true"
    category = next(
        node
        for node in wiki_root.iter("Property")
        if node.attrib.get("value") == "GcWikiCategory"
    )
    assert _texture_filename(category, "IconOn") == CATEGORY_ICON_ON
    assert _texture_filename(category, "IconOff") == CATEGORY_ICON_OFF
    topic = next(
        node
        for node in wiki_root.iter("Property")
        if node.attrib.get("value") == "GcWikiTopic"
    )
    page = next(
        node
        for node in wiki_root.iter("Property")
        if node.attrib.get("value") == "GcWikiPage"
    )
    assert _texture_filename(topic, "Icon") == PRESET_TOPIC_ICON
    assert _texture_filename(topic, "NotifyIcon") == PRESET_NOTIFY_ICON
    assert _texture_filename(page, "Icon") == PRESET_TOPIC_ICON
    assert result["targeting_reference"] == "SE_PHOTO_BIOME_LUSH"
    assert result["location_references"] == ["SE_CURRENT_NEAR"]


def test_build_native_search_probe_can_use_fresh_trial_identity(tmp_path: Path) -> None:
    result = build_native_search_probe(
        _wiki_source(tmp_path / "wiki.MXML"),
        _mission_source(tmp_path / "missions.MXML"),
        _reference_source(tmp_path / "reference.MXML"),
        tmp_path / "probe",
        probe_tag="run_02",
    )

    mission_root = ET.parse(result["files"][1]["path"]).getroot()
    values = {
        node.attrib.get("name"): node.attrib.get("value") for node in mission_root.iter("Property")
    }
    wiki_root = ET.parse(result["files"][0]["path"]).getroot()
    wiki_values = {
        node.attrib.get("name"): node.attrib.get("value") for node in wiki_root.iter("Property")
    }
    assert result["mission_id"] == "SQN_SS_LUSH_RUN_02"
    assert result["scan_event_id"] == "SE_SQN_SS_LUSH_RUN_02"
    assert values["MissionID"] == result["mission_id"]
    assert values["Name"] == result["scan_event_id"]
    assert values["MissionObjective"] == "SQN_SS_LUSH_MISSION_OBJ"
    assert result["scan_event_id"] in {value for name, value in values.items() if name == "Event"}
    assert wiki_values["Mission"] == result["mission_id"]


def test_build_native_search_probe_preloads_bounded_guide_dispatch_slots(
    tmp_path: Path,
) -> None:
    result = build_native_search_probe(
        _wiki_source(tmp_path / "wiki.MXML"),
        _mission_source(tmp_path / "missions.MXML"),
        _reference_source(tmp_path / "reference.MXML"),
        tmp_path / "probe",
        probe_tag="R08",
        guide_preset_slots=2,
    )

    mission_root = ET.parse(result["files"][1]["path"]).getroot()
    mission_ids = [
        next(
            child.attrib["value"]
            for child in mission
            if child.attrib.get("name") == "MissionID"
        )
        for mission in mission_root.iter("Property")
        if mission.attrib.get("value") == "GcGenericMissionSequence"
    ]
    event_names = [
        node.attrib["value"]
        for node in mission_root.iter("Property")
        if node.attrib.get("name") == "Name"
    ]
    assert mission_ids == [
        "SQN_SS_LUSH_R08",
        "SQN_SS9_P00",
        "SQN_SS9_P01",
    ]
    assert event_names == [
        "SE_SQN_SS_LUSH_R08",
        "SE_SQN_SS9_P00",
        "SE_SQN_SS9_R00",
        "SE_SQN_SS9_T00",
        "SE_SQN_SS9_P01",
        "SE_SQN_SS9_R01",
        "SE_SQN_SS9_T01",
    ]
    assert result["guide_preset_slots"] == 2
    assert result["form_navigation_target_event_id"] == FORM_NAVIGATION_TARGET_EVENT_ID

    npc_path = next(
        Path(record["path"])
        for record in result["files"]
        if str(record["path"]).endswith("NPCMISSIONTABLE.EXML")
    )
    npc_root = ET.parse(npc_path).getroot()
    missions = [
        node
        for node in npc_root.iter("Property")
        if node.attrib.get("value") == "GcGenericMissionSequence"
    ]
    target_host = next(
        mission
        for mission in missions
        if next(
            node.attrib.get("value")
            for node in mission
            if node.attrib.get("name") == "MissionID"
        )
        == FORM_NAVIGATION_TARGET_MISSION_ID
    )
    target_events = [
        node
        for node in target_host.iter("Property")
        if node.attrib.get("name") == "ScanEvents"
        and node.attrib.get("value") == "GcScanEventData"
    ]
    assert len(target_events) == 1
    target_values = {
        node.attrib.get("name"): node.attrib.get("value") for node in target_events[0]
    }
    assert target_values["Name"] == FORM_NAVIGATION_TARGET_EVENT_ID
    assert target_values["SolarSystemLocation"] == "FromList"
    assert target_values["MustFindSystem"] == "true"
    assert [
        node.attrib.get("value")
        for node in next(
            child for child in target_events[0] if child.attrib.get("name") == "UAsList"
        )
    ] == ["0000000000000000"]
    target_values = {
        node.attrib.get("name"): node.attrib.get("value") for node in target_host
    }
    assert target_values["MissionClass"] == "Secondary"
    assert target_values["AutoStart"] == "None"
    assert target_values["RestartOnCompletion"] == "false"
    assert target_values["CanRenounce"] == "true"
    target_stage_types = [
        node.attrib.get("value")
        for node in target_host.iter("Property")
        if node.attrib.get("name") == "Stage"
    ]
    assert target_stage_types == [
        "GcMissionSequenceGroup",
        "GcMissionSequenceEndScanEvent",
        "GcMissionSequenceStartScanEvent",
        "GcMissionSequenceWaitForConditions",
        "GcMissionSequenceWaitForConditions",
        "GcMissionSequenceEndScanEvent",
        "GcMissionSequenceShowMissionUpdateMessage",
    ]
    assert not any(
        node.attrib.get("value") == "GcMissionSequenceStartMission"
        for root in (mission_root, npc_root)
        for node in root.iter("Property")
    )


def test_build_native_search_probe_rejects_excess_guide_dispatch_slots(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="guide_preset_slots"):
        build_native_search_probe(
            _wiki_source(tmp_path / "wiki.MXML"),
            _mission_source(tmp_path / "missions.MXML"),
            _reference_source(tmp_path / "reference.MXML"),
            tmp_path / "probe",
            guide_preset_slots=10,
        )


@pytest.mark.parametrize("probe_tag", ("", "HAS-DASH", "TOO_LONG_FOR_TAG"))
def test_build_native_search_probe_rejects_invalid_trial_identity(
    tmp_path: Path, probe_tag: str
) -> None:
    with pytest.raises(InvestigationError, match="Probe tag"):
        build_native_search_probe(
            _wiki_source(tmp_path / f"wiki-{probe_tag}.MXML"),
            _mission_source(tmp_path / f"missions-{probe_tag}.MXML"),
            _reference_source(tmp_path / f"reference-{probe_tag}.MXML"),
            tmp_path / f"probe-{probe_tag}",
            probe_tag=probe_tag,
        )
