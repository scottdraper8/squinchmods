from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from squinch_nms_investigate import toolchain
from squinch_nms_investigate.errors import InvestigationError
from squinch_nms_investigate.output import envelope, schema, timestamp
from squinch_nms_investigate.paths import resolve_game_root, safe_logical_path, steam_build_id
from squinch_nms_investigate.toolchain import assert_mbincompiler_supported_build


def fake_game(tmp_path: Path) -> Path:
    game = tmp_path / "steamapps/common/No Man's Sky"
    (game / "Binaries").mkdir(parents=True)
    (game / "Binaries/NMS.exe").write_bytes(b"MZfake")
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    manifest = tmp_path / "steamapps/appmanifest_275850.acf"
    manifest.write_text('"AppState" { "buildid" "12345" }', encoding="utf-8")
    return game


def test_game_resolution_and_build_identity(tmp_path: Path) -> None:
    game = fake_game(tmp_path)
    assert resolve_game_root(game) == game.resolve()
    assert steam_build_id(game) == "12345"
    with pytest.raises(InvestigationError, match="outside the pinned MBINCompiler"):
        assert_mbincompiler_supported_build(game)


def test_current_game_target_does_not_enable_new_mbincompiler_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = fake_game(tmp_path)
    manifest = tmp_path / "steamapps/appmanifest_275850.acf"
    manifest.write_text('"AppState" { "buildid" "26385139" }', encoding="utf-8")
    pins = {
        "target": {
            "nms_version": "7.13 (Forsaken)",
            "branch": "public",
            "steam_build_ids": ["26385139"],
        },
        "mbincompiler": {
            "supported_nms_version": "7.10 (Forsaken)",
            "supported_branch": "public",
            "supported_steam_build_ids": ["26271400"],
        },
        "search_probes": {
            "nms_version": "7.11 (Forsaken)",
            "branch": "public",
            "steam_build_ids": ["26295378"],
        },
    }
    monkeypatch.setattr(toolchain, "config", lambda: pins)

    assert toolchain.target_identity(game)["matches"]
    assert not toolchain.mbincompiler_target_identity(game)["matches"]
    with pytest.raises(InvestigationError, match="outside the pinned MBINCompiler"):
        assert_mbincompiler_supported_build(game)


def test_search_probes_remains_gated_to_its_exact_game_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = fake_game(tmp_path)
    manifest = tmp_path / "steamapps/appmanifest_275850.acf"
    manifest.write_text('"AppState" { "buildid" "26385139" }', encoding="utf-8")
    pins = {
        "target": {
            "nms_version": "7.13 (Forsaken)",
            "branch": "public",
            "steam_build_ids": ["26385139"],
        },
        "mbincompiler": {
            "supported_nms_version": "7.10 (Forsaken)",
            "supported_branch": "public",
            "supported_steam_build_ids": ["26271400"],
        },
        "search_probes": {
            "nms_version": "7.11 (Forsaken)",
            "branch": "public",
            "steam_build_ids": ["26295378"],
        },
    }
    monkeypatch.setattr(toolchain, "config", lambda: pins)

    with pytest.raises(InvestigationError, match="outside the Search Probes support target"):
        toolchain.assert_search_probes_supported_build(game)


def test_logical_paths_are_normalized_and_traversal_is_rejected() -> None:
    assert safe_logical_path(r"UI\COMPONENTS\PAGE.MBIN") == "ui/components/page.mbin"
    with pytest.raises(InvestigationError, match="Unsafe"):
        safe_logical_path("../NMS.exe")


def test_output_envelope_validates_and_serializes() -> None:
    now = timestamp()
    value = envelope("test", "succeeded", started_at=now, finished_at=now, data={"ok": True})
    jsonschema.validate(value, schema())
    json.dumps(value)
