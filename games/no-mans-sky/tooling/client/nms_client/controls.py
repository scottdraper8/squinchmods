from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from evdev import AbsInfo, UInput
from evdev import ecodes as e

from .errors import LaunchError

WINDOW_NAME = "^No Man's Sky$"
EXPECTED_WIDTH = 3840
EXPECTED_HEIGHT = 2160
CONTROLLER_NAME = "Squinch NMS Menu Driver"

CAPABILITIES = {
    e.EV_KEY: [
        e.BTN_SOUTH,
        e.BTN_EAST,
        e.BTN_NORTH,
        e.BTN_WEST,
        e.BTN_TL,
        e.BTN_TR,
        e.BTN_SELECT,
        e.BTN_START,
        e.BTN_THUMBL,
        e.BTN_THUMBR,
        e.BTN_DPAD_UP,
        e.BTN_DPAD_DOWN,
        e.BTN_DPAD_LEFT,
        e.BTN_DPAD_RIGHT,
    ],
    e.EV_ABS: [
        (e.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)),
        (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),
        (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
        (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),
        (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
    ],
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def event(name: str, **values: object) -> None:
    print(
        json.dumps({"time": now(), "event": name, **values}, sort_keys=True), flush=True
    )


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise LaunchError(f"Required command is unavailable: {name}")


def ensure_uinput_access() -> None:
    device = Path("/dev/uinput")
    if os.access(device, os.W_OK):
        return
    require_command("loginctl")
    sessions = subprocess.run(
        ["loginctl", "list-sessions", "--no-legend"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    candidates = [
        fields[0]
        for line in sessions.stdout.splitlines()
        if len(fields := line.split()) >= 4
        and fields[1] == str(os.getuid())
        and fields[3] != "-"
    ]
    for session in candidates:
        subprocess.run(
            ["loginctl", "activate", session],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if os.access(device, os.W_OK):
                event("uinput_access_restored", session=session)
                return
            time.sleep(0.1)
    raise LaunchError(
        f"{device} is not writable and no local graphical login session restored its uaccess ACL"
    )


def find_window(timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", WINDOW_NAME],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            windows = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]
            if windows:
                return windows[-1]
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    raise LaunchError(f"NMS window did not appear within {timeout:g} seconds")


def focus(window: str) -> None:
    active = subprocess.run(
        ["xdotool", "getactivewindow"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5.0,
    ).stdout.strip()
    if active == window:
        return
    subprocess.run(
        ["xdotool", "windowactivate", "--sync", window], check=True, timeout=5.0
    )


def geometry(window: str) -> tuple[int, int]:
    result = subprocess.run(
        ["xdotool", "getwindowgeometry", "--shell", window],
        check=True,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    fields = dict(
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
    )
    return int(fields["WIDTH"]), int(fields["HEIGHT"])


def wait_for_geometry(window: str, timeout: float = 15.0) -> tuple[int, int]:
    deadline = time.monotonic() + timeout
    current: tuple[int, int] | None = None
    while time.monotonic() < deadline:
        try:
            current = geometry(window)
        except (KeyError, ValueError, OSError, subprocess.SubprocessError):
            current = None
        if current == (EXPECTED_WIDTH, EXPECTED_HEIGHT):
            return current
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    if current is None:
        raise LaunchError(
            f"NMS window geometry was unavailable within {timeout:g} seconds"
        )
    return current


def tap_button(
    controller: UInput, window: str, code: int, duration: float = 0.15
) -> None:
    focus(window)
    controller.write(e.EV_KEY, code, 1)
    controller.syn()
    time.sleep(duration)
    controller.write(e.EV_KEY, code, 0)
    controller.syn()


def pulse_axis(
    controller: UInput, window: str, code: int, value: int, duration: float
) -> None:
    focus(window)
    controller.write(e.EV_ABS, code, value)
    controller.syn()
    time.sleep(duration)
    controller.write(e.EV_ABS, code, 0)
    controller.syn()


KEYBOARD_KEYS = {"f7": e.KEY_F7, "esc": e.KEY_ESC, "enter": e.KEY_ENTER}


def keyboard_key(name: str, window: str, duration: float = 0.2) -> None:
    if name not in KEYBOARD_KEYS:
        raise ValueError(f"unsupported keyboard key: {name}")
    code = KEYBOARD_KEYS[name]
    focus(window)
    with UInput(
        {e.EV_KEY: list(KEYBOARD_KEYS.values())}, name="Squinch NMS Keyboard"
    ) as keyboard:
        time.sleep(0.5)
        keyboard.write(e.EV_KEY, code, 1)
        keyboard.syn()
        try:
            time.sleep(duration)
        finally:
            keyboard.write(e.EV_KEY, code, 0)
            keyboard.syn()


def capture(window: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    focus(window)
    spectacle = shutil.which("spectacle")
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" and spectacle:
        subprocess.run(
            [spectacle, "-a", "-b", "-n", "-o", str(path)],
            check=True,
            timeout=20.0,
        )
        active = subprocess.run(
            ["xdotool", "getactivewindow"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        ).stdout.strip()
        if active != window:
            raise LaunchError("NMS lost focus while capturing the screenshot")
    else:
        require_command("import")
        subprocess.run(["import", "-window", window, str(path)], check=True, timeout=20.0)
    event("screenshot", path=str(path))


def interactive(controller: UInput, window: str) -> None:
    buttons = {
        "a": e.BTN_SOUTH,
        "b": e.BTN_EAST,
        "x": e.BTN_WEST,
        "y": e.BTN_NORTH,
        "lb": e.BTN_TL,
        "rb": e.BTN_TR,
        "back": e.BTN_SELECT,
        "start": e.BTN_START,
        "lstick": e.BTN_THUMBL,
        "rstick": e.BTN_THUMBR,
        "up": e.BTN_DPAD_UP,
        "down": e.BTN_DPAD_DOWN,
        "left": e.BTN_DPAD_LEFT,
        "right": e.BTN_DPAD_RIGHT,
    }
    axes = {
        "move_forward": (e.ABS_Y, -32768),
        "move_back": (e.ABS_Y, 32767),
        "move_left": (e.ABS_X, -32768),
        "move_right": (e.ABS_X, 32767),
        "look_up": (e.ABS_RY, -32768),
        "look_down": (e.ABS_RY, 32767),
        "look_left": (e.ABS_RX, -32768),
        "look_right": (e.ABS_RX, 32767),
    }
    event(
        "interactive_ready", commands=sorted([*buttons, *axes, *KEYBOARD_KEYS, "quit"])
    )
    for line in sys.stdin:
        fields = line.strip().lower().split()
        if not fields:
            continue
        command = fields[0]
        if command == "quit":
            event("interactive_complete")
            return
        try:
            duration = float(fields[1]) if len(fields) > 1 else 0.15
        except ValueError:
            event("interactive_error", command=line.strip(), error="invalid duration")
            continue
        duration = min(max(duration, 0.05), 5.0)
        if len(fields) > 2 and command not in axes:
            event("interactive_error", command=line.strip(), error="magnitude is only valid for axes")
            continue
        if command in buttons:
            tap_button(controller, window, buttons[command], duration)
        elif command in axes:
            code, axis_value = axes[command]
            try:
                magnitude = float(fields[2]) if len(fields) > 2 else 1.0
            except ValueError:
                event("interactive_error", command=line.strip(), error="invalid magnitude")
                continue
            if not math.isfinite(magnitude) or not 0 < magnitude <= 1:
                event("interactive_error", command=line.strip(), error="magnitude must be between 0 and 1")
                continue
            pulse_axis(controller, window, code, round(axis_value * magnitude), duration)
        elif command in KEYBOARD_KEYS:
            keyboard_key(command, window, duration)
        else:
            event("interactive_error", command=command, error="unknown command")
            continue
        event("interactive_input", command=command, duration=duration)
