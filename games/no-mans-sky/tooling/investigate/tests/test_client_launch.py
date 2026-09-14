from __future__ import annotations

import io
import sys
import types
from pathlib import Path

import pytest


def _client_module(monkeypatch: pytest.MonkeyPatch):
    class Codes:
        def __getattr__(self, name: str) -> int:
            return sum(name.encode("ascii"))

    evdev = types.ModuleType("evdev")
    evdev.AbsInfo = lambda *values: values
    evdev.UInput = object
    evdev.ecodes = Codes()
    monkeypatch.setitem(sys.modules, "evdev", evdev)
    client_path = Path(__file__).parents[2] / "client"
    sys.path.insert(0, str(client_path))
    modules = ("nms_client.launch", "nms_client.controls", "nms_client.saves", "nms_client.errors")
    for name in modules:
        sys.modules.pop(name, None)
    from nms_client import launch

    return launch


@pytest.mark.parametrize(
    ("filename", "pair"),
    (
        ("save.hg", 0),
        ("save2.hg", 0),
        ("save3.hg", 1),
        ("save7.hg", 3),
        ("save10.hg", 4),
    ),
)
def test_save_pair_index(
    filename: str, pair: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client_module(monkeypatch)
    from nms_client.saves import save_pair_index

    assert save_pair_index(Path(filename)) == pair


def test_latest_visible_save_maps_to_proven_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client_module(monkeypatch)
    (tmp_path / "save.hg").write_bytes(b"old")
    latest = tmp_path / "save7.hg"
    latest.write_bytes(b"latest")
    latest.touch()

    result = client.verify_latest_save(tmp_path)

    assert result["save_pair"] == 4
    from nms_client.saves import SAVE_ROW_SPACING, TOP_SAVE_X, TOP_SAVE_Y

    assert result["selection_x"] == TOP_SAVE_X
    assert result["selection_y"] == TOP_SAVE_Y + 3 * SAVE_ROW_SPACING


def test_latest_offscreen_save_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client_module(monkeypatch)
    latest = tmp_path / "save11.hg"
    latest.write_bytes(b"latest")

    with pytest.raises(client.LaunchError, match="unproved scrolling"):
        client.verify_latest_save(tmp_path)


def test_keyboard_key_uses_separate_device_and_releases_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client_module(monkeypatch)
    from nms_client import controls

    assert controls.e.KEY_F7 not in controls.CAPABILITIES[controls.e.EV_KEY]
    writes: list[tuple[int, int, int]] = []

    class Keyboard:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def write(self, event_type: int, code: int, value: int) -> None:
            writes.append((event_type, code, value))

        def syn(self) -> None:
            return None

    monkeypatch.setattr(controls, "UInput", lambda capabilities, name: Keyboard())
    monkeypatch.setattr(controls, "focus", lambda _window: None)
    monkeypatch.setattr(controls.time, "sleep", lambda _seconds: None)
    controls.keyboard_key("f7", "form")

    assert writes == [
        (controls.e.EV_KEY, controls.e.KEY_F7, 1),
        (controls.e.EV_KEY, controls.e.KEY_F7, 0),
    ]
    with pytest.raises(ValueError, match="unsupported"):
        controls.keyboard_key("ctrl", "form")


def test_focus_skips_redundant_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    _client_module(monkeypatch)
    from nms_client import controls

    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object):
        calls.append(command)
        return type("Result", (), {"stdout": "window-1\n"})()

    monkeypatch.setattr(controls.subprocess, "run", run)
    controls.focus("window-1")

    assert calls == [["xdotool", "getactivewindow"]]


def test_interactive_axis_accepts_bounded_magnitude(monkeypatch: pytest.MonkeyPatch) -> None:
    _client_module(monkeypatch)
    from nms_client import controls

    writes: list[tuple[int, int, int]] = []

    class Controller:
        def write(self, event_type: int, code: int, value: int) -> None:
            writes.append((event_type, code, value))

        def syn(self) -> None:
            return None

    monkeypatch.setattr(controls, "focus", lambda _window: None)
    monkeypatch.setattr(controls.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO("move_back 0.2 0.5\nquit\n"))
    controls.interactive(Controller(), "window")

    assert writes == [
        (controls.e.EV_ABS, controls.e.ABS_Y, round(32767 * 0.5)),
        (controls.e.EV_ABS, controls.e.ABS_Y, 0),
    ]


def test_capture_uses_spectacle_for_wayland_vulkan_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client_module(monkeypatch)
    from nms_client import controls

    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object):
        calls.append(command)
        return type("Result", (), {"stdout": "window-1\n"})()

    monkeypatch.setattr(controls, "focus", lambda _window: None)
    monkeypatch.setattr(
        controls.shutil,
        "which",
        lambda name: "/usr/bin/spectacle" if name == "spectacle" else None,
    )
    monkeypatch.setattr(controls.subprocess, "run", run)
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    controls.capture("window-1", tmp_path / "capture.png")

    assert calls == [
        ["/usr/bin/spectacle", "-a", "-b", "-n", "-o", str(tmp_path / "capture.png")],
        ["xdotool", "getactivewindow"],
    ]
