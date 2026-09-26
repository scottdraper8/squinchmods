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
    modules = ("nms_client.launch", "nms_client.controls", "nms_client.saves", "nms_client.errors", "nms_client")
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
        ("save5.hg", 2),
        ("save10.hg", 4),
    ),
)
def test_save_pair_index(
    filename: str, pair: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    _client_module(monkeypatch)
    from nms_client.saves import save_pair_index

    assert save_pair_index(Path(filename)) == pair


def test_latest_visible_save_maps_to_controller_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client_module(monkeypatch)
    (tmp_path / "save.hg").write_bytes(b"old")
    latest = tmp_path / "save5.hg"
    latest.write_bytes(b"latest")
    latest.touch()

    from nms_client.saves import verify_latest_save

    result = verify_latest_save(tmp_path)

    assert result["save_pair"] == 3


def test_latest_offscreen_save_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client_module(monkeypatch)
    latest = tmp_path / "save11.hg"
    latest.write_bytes(b"latest")

    from nms_client.saves import verify_latest_save

    with pytest.raises(client.LaunchError, match="unproved scrolling"):
        verify_latest_save(tmp_path)


@pytest.mark.parametrize("filename", ["save.hg", "save2.hg", "save17.hg"])
def test_automatic_save_loading_is_blocked_before_input(monkeypatch, filename):
    launch = _client_module(monkeypatch)
    monkeypatch.setattr(launch, "require_command", lambda _: None)
    monkeypatch.setattr(launch, "nms_processes", lambda: [])
    monkeypatch.setattr(launch, "save_profile", lambda: Path("profile"))
    args = launch.parser().parse_args(["--load-save", filename])
    with pytest.raises(launch.LaunchError, match="disabled|restricted"):
        launch.run(args)


def test_launch_stops_before_menu_input(monkeypatch):
    launch = _client_module(monkeypatch)
    events = []
    class Controller:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    monkeypatch.setattr(launch, "require_command", lambda _: None)
    monkeypatch.setattr(launch, "nms_processes", lambda: [])
    monkeypatch.setattr(launch, "save_profile", lambda: Path("profile"))
    monkeypatch.setattr(launch, "ensure_uinput_access", lambda: None)
    monkeypatch.setattr(launch, "event", lambda name, **kw: events.append((name, kw)))
    monkeypatch.setattr(launch, "UInput", lambda *a, **kw: Controller())
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(launch, "find_window", lambda _: "window")
    monkeypatch.setattr(launch, "wait_for_geometry", lambda _: (3840, 2160))
    monkeypatch.setattr(launch, "wait", lambda *a: None)
    from nms_client import controls
    monkeypatch.setattr(controls, "tap_button", lambda *a, **kw: pytest.fail("unexpected menu input"))
    launch.run(launch.parser().parse_args([]))
    assert ("complete", {"result": "startup_checkpoint", "window": "window"}) in events


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
