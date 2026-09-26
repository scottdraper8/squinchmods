from __future__ import annotations

from pathlib import Path

from squinch_nms_investigate.executable import inspect_strings


def test_executable_strings_are_bounded_and_offset_backed(tmp_path: Path) -> None:
    executable = tmp_path / "NMS.exe"
    executable.write_bytes(b"MZ\x00PAGESELECTBAR\x00cGcFrontendPageDiscovery\x00")
    result = inspect_strings(executable, ["PAGESELECTBAR", "FrontendPage"], limit=1)
    assert result["match_count"] == 2
    assert result["all_patterns_matched"]
    assert result["pattern_counts"] == {"FrontendPage": 1, "PAGESELECTBAR": 1}
    assert len(result["matches"]) == 1
    assert result["matches_truncated"]
