from __future__ import annotations

from pathlib import Path

from squinch_nms_investigate.xmlmodel import compare_xml, validate_patch, verify_export, xml_summary


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_amumss_annotations_and_current_schema_validation(tmp_path: Path) -> None:
    vanilla = write(
        tmp_path / "TABLE.MXML",
        '<Data template="cTable"><Property name="Items">'
        '<Property name="Items" value="cItem"><Property name="Id" value="OLD" />'
        "</Property></Property></Data>",
    )
    patch = write(
        tmp_path / "TABLE.EXML",
        '<Data template="cTable"><Property name="Items">'
        '<Property name="Items" value="cItem" _id="NEW">'
        '<Property name="Id" value="NEW" /> !# CHANGED\n'
        "</Property></Property></Data>",
    )
    result = validate_patch(patch, vanilla)
    assert result["structurally_compatible"]
    assert result["amumss_annotation_count"] == 1


def test_unknown_property_is_rejected(tmp_path: Path) -> None:
    vanilla = write(
        tmp_path / "v.MXML", '<Data template="cTable"><Property name="Known" value="1" /></Data>'
    )
    patch = write(
        tmp_path / "p.EXML",
        '<Data template="cTable"><Property name="RemovedField" value="1" /></Data>',
    )
    result = validate_patch(patch, vanilla)
    assert result["structurally_compatible"]
    assert not result["all_paths_present_in_vanilla_instance"]
    assert result["paths_absent_from_vanilla_instance"][0]["path"] == "RemovedField"


def test_semantic_compare_ignores_formatting_but_detects_values(tmp_path: Path) -> None:
    left = write(
        tmp_path / "left.MXML", '<Data template="c"><Property name="A" value="1" /></Data>'
    )
    same = write(
        tmp_path / "same.MXML", '<Data template="c">\n  <Property value="1" name="A"/>\n</Data>'
    )
    changed = write(
        tmp_path / "changed.MXML", '<Data template="c"><Property name="A" value="2" /></Data>'
    )
    assert compare_xml(left, same)["equal"]
    assert not compare_xml(left, changed)["equal"]


def test_export_verification_has_positive_and_negative_controls(tmp_path: Path) -> None:
    patch = write(
        tmp_path / "p.EXML", '<Data template="c"><Property name="A" value="wanted" /></Data>'
    )
    good = write(
        tmp_path / "good.MXML", '<Data template="c"><Property name="A" value="wanted" /></Data>'
    )
    bad = write(
        tmp_path / "bad.MXML", '<Data template="c"><Property name="A" value="wrong" /></Data>'
    )
    assert verify_export(patch, good)["passed"]
    assert not verify_export(patch, bad)["passed"]


def test_export_verification_checks_the_full_property_path(tmp_path: Path) -> None:
    patch = write(
        tmp_path / "path.EXML",
        '<Data template="c"><Property name="First"><Property name="Value" value="wanted" />'
        "</Property></Data>",
    )
    wrong_branch = write(
        tmp_path / "wrong.MXML",
        '<Data template="c"><Property name="Second"><Property name="Value" value="wanted" />'
        "</Property></Data>",
    )
    assert not verify_export(patch, wrong_branch)["passed"]


def test_nonfinite_values_are_reported(tmp_path: Path) -> None:
    value = write(
        tmp_path / "value.MXML", '<Data template="c"><Property name="Scale" value="NaN" /></Data>'
    )
    assert xml_summary(value)["nonfinite_values"][0]["value"] == "NaN"


def test_repeated_typed_siblings_are_distinct_and_ordered(tmp_path: Path) -> None:
    left = write(
        tmp_path / "left-list.MXML",
        '<Data template="c"><Property name="Items">'
        '<Property name="Items" value="cItem"><Property name="Scale" value="NaN" /></Property>'
        '<Property name="Items" value="cItem"><Property name="Scale" value="2" /></Property>'
        "</Property></Data>",
    )
    reordered = write(
        tmp_path / "reordered-list.MXML",
        '<Data template="c"><Property name="Items">'
        '<Property name="Items" value="cItem"><Property name="Scale" value="2" /></Property>'
        '<Property name="Items" value="cItem"><Property name="Scale" value="NaN" /></Property>'
        "</Property></Data>",
    )
    summary = xml_summary(left)
    assert summary["node_count"] == 6
    assert len(summary["nonfinite_values"]) == 1
    assert not compare_xml(left, reordered)["equal"]
