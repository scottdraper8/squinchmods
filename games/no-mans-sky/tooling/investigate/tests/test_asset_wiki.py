from pathlib import Path

import pytest

from squinch_nms_investigate.asset_wiki import (
    BIOME_FILE_LIST_PATH,
    SCREEN_FILTER_PATH,
    TABLE_PATHS,
    is_catalog_icon,
    positive_biome_sources,
    referenced_dds_paths,
    select_mbin_sources,
)
from squinch_nms_investigate.errors import InvestigationError


def test_selects_tables_and_all_english_localisation_banks() -> None:
    members = {
        *TABLE_PATHS,
        SCREEN_FILTER_PATH,
        BIOME_FILE_LIST_PATH,
        "language/nms_loc1_english.mbin",
        "language/nms_update8_english.mbin",
        "language/nms_loc1_french.mbin",
    }
    selected = select_mbin_sources(members)
    assert selected[:7] == [*TABLE_PATHS, SCREEN_FILTER_PATH, BIOME_FILE_LIST_PATH]
    assert selected[7:] == [
        "language/nms_loc1_english.mbin",
        "language/nms_update8_english.mbin",
    ]


def test_missing_table_fails_closed() -> None:
    with pytest.raises(InvestigationError) as error:
        select_mbin_sources({"language/nms_loc1_english.mbin"})
    assert error.value.code == "asset_wiki_sources_missing"


def test_missing_screen_filter_table_fails_closed() -> None:
    with pytest.raises(InvestigationError) as error:
        select_mbin_sources({*TABLE_PATHS, BIOME_FILE_LIST_PATH, "language/nms_loc1_english.mbin"})
    assert error.value.code == "asset_wiki_sources_missing"
    assert error.value.details["paths"] == [SCREEN_FILTER_PATH]


def test_selects_only_positive_weight_biome_definitions(tmp_path: Path) -> None:
    document = tmp_path / "biomefilenames.MXML"
    document.write_text(
        '<Data template="cGcBiomeFileList"><Property name="BiomeFiles">'
        '<Property name="FileOptions" value="GcBiomeFileListOption">'
        '<Property name="Filename" value="BIOMES\\NORMAL.MXML" />'
        '<Property name="Weight" value="1.000000" />'
        '<Property name="PurpleSystemWeight" value="0.000000" /></Property>'
        '<Property name="FileOptions" value="GcBiomeFileListOption">'
        '<Property name="Filename" value="BIOMES/PURPLE.MXML" />'
        '<Property name="Weight" value="0.000000" />'
        '<Property name="PurpleSystemWeight" value="0.500000" /></Property>'
        '<Property name="FileOptions" value="GcBiomeFileListOption">'
        '<Property name="Filename" value="BIOMES/UNUSED.MXML" />'
        '<Property name="Weight" value="0.000000" />'
        '<Property name="PurpleSystemWeight" value="0.000000" /></Property>'
        "</Property></Data>",
        encoding="utf-8",
    )

    assert positive_biome_sources(document) == [
        "biomes/normal.mbin",
        "biomes/purple.mbin",
    ]


def test_icon_scope_and_table_references(tmp_path: Path) -> None:
    document = tmp_path / "table.MXML"
    document.write_text(
        '<Data><Property name="Filename" value="TEXTURES\\UI//OTHER.DDS" />'
        '<Property name="Ignored" value="TEXTURES/UI/OTHER.PNG" /></Data>',
        encoding="utf-8",
    )
    assert referenced_dds_paths([document]) == {"textures/ui/other.dds"}
    assert is_catalog_icon("textures/ui/frontend/icons/test.dds")
    assert is_catalog_icon("textures/ui/frontend/test_icon.dds")
    assert not is_catalog_icon("textures/planets/test.dds")
