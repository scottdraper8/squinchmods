from __future__ import annotations

import json
from pathlib import Path

import pytest

from squinch_nms_investigate import cli, runs
from squinch_nms_investigate.cli import main


def fake_game(tmp_path: Path) -> Path:
    game = tmp_path / "steamapps/common/No Man's Sky"
    (game / "Binaries").mkdir(parents=True)
    (game / "Binaries/NMS.exe").write_bytes(b"MZ\0PAGESELECTBAR\0")
    (game / "GAMEDATA/PCBANKS").mkdir(parents=True)
    (tmp_path / "steamapps/appmanifest_275850.acf").write_text(
        '"AppState" { "buildid" "12345" }', encoding="utf-8"
    )
    return game


def test_executable_cli_positive_and_negative_assertions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    game = fake_game(tmp_path)
    monkeypatch.setattr(runs, "RUNS_ROOT", tmp_path / "runs")
    main(
        [
            "exe-strings",
            "--game-root",
            str(game),
            "--pattern",
            "PAGESELECTBAR",
            "--json",
        ]
    )
    positive = json.loads(capsys.readouterr().out)
    assert positive["state"] == "succeeded"
    assert positive["data"]["all_patterns_matched"]

    with pytest.raises(SystemExit) as stopped:
        main(
            [
                "exe-strings",
                "--game-root",
                str(game),
                "--pattern",
                "DOES_NOT_EXIST",
                "--json",
            ]
        )
    assert stopped.value.code == 1
    negative = json.loads(capsys.readouterr().out)
    assert negative["state"] == "failed"
    assert not negative["data"]["all_patterns_matched"]


def test_doctor_explains_degraded_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    game = fake_game(tmp_path)
    monkeypatch.setattr(cli, "resolve_game_root", lambda _: game)
    monkeypatch.setattr(
        cli,
        "host_health",
        lambda: {
            "healthy": False,
            "load_average": ["9.0", "8.0", "7.0"],
            "uninterruptible_processes": [{"pid": 42, "name": "java"}],
        },
    )
    monkeypatch.setattr(
        cli,
        "game_identity",
        lambda *_args, **_kwargs: {"running_processes": []},
    )
    monkeypatch.setattr(cli, "host_capabilities", lambda: {})
    monkeypatch.setattr(cli, "target_identity", lambda _: {"matches": True})
    monkeypatch.setattr(cli, "hgpak_identity", lambda: {})
    monkeypatch.setattr(cli, "verify_mbincompiler", lambda: {})
    with pytest.raises(SystemExit) as stopped:
        main(["doctor", "--game-root", str(game), "--json"])
    assert stopped.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "degraded"
    assert result["data"]["problems"] == [
        {
            "code": "uninterruptible_processes",
            "component": "host-health",
            "message": (
                "The host has processes in uninterruptible sleep; performance and large-file "
                "evidence are invalid until the host recovers"
            ),
        }
    ]
