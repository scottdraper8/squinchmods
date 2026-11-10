from pathlib import Path

import pytest

from squinch_nms_investigate.asset_wiki import (
    TABLE_PATHS,
    is_catalog_icon,
    referenced_dds_paths,
    select_mbin_sources,
)
from squinch_nms_investigate.errors import InvestigationError


def test_selects_tables_and_all_english_localisation_banks() -> None:
    members = {
        *TABLE_PATHS,
        "language/nms_loc1_english.mbin",
        "language/nms_update8_english.mbin",
        "language/nms_loc1_french.mbin",
    }
    selected = select_mbin_sources(members)
    assert selected[:5] == list(TABLE_PATHS)
    assert selected[5:] == [
        "language/nms_loc1_english.mbin",
        "language/nms_update8_english.mbin",
    ]


def test_missing_table_fails_closed() -> None:
    with pytest.raises(InvestigationError) as error:
        select_mbin_sources({"language/nms_loc1_english.mbin"})
    assert error.value.code == "asset_wiki_sources_missing"


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
