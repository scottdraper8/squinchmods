#!/usr/bin/env python3
"""Launch NMS, optionally loading the verified latest save for gameplay checks."""

from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from evdev import UInput
from evdev import ecodes as e

from .controls import (
    CAPABILITIES,
    CONTROLLER_NAME,
    capture,
    ensure_uinput_access,
    event,
    find_window,
    interactive,
    require_command,
    tap_button,
    wait_for_geometry,
)
from .errors import LaunchError
from .saves import APP_ID, save_profile, verify_latest_save, verify_save


@dataclass(frozen=True)
class Timings:
    controller_settle: float = 2.0
    warning: float = 50.0
    main_menu: float = 12.0
    save_menu: float = 7.0


def nms_processes() -> list[str]:
    processes: list[str] = []
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() != "NMS.exe":
                continue
            command = (comm.parent / "cmdline").read_bytes().replace(b"\0", b" ")
            processes.append(
                f"{comm.parent.name} {command.decode('utf-8', 'backslashreplace').strip()}"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return processes


def wait(label: str, seconds: float) -> None:
    event("wait", state=label, seconds=seconds)
    time.sleep(seconds)


def run(args: argparse.Namespace) -> None:
    for command in ("steam", "xdotool"):
        require_command(command)
    running = nms_processes()
    if running:
        raise LaunchError("NMS is already running:\n" + "\n".join(running))
    profile = save_profile()
    load_save = getattr(args, "load_save", None)
    if load_save and args.load_latest_save:
        raise LaunchError("choose either --load-latest-save or --load-save")
    if load_save:
        save = verify_save(profile, load_save)
    else:
        save = verify_latest_save(profile)
    event("preflight", **save)
    ensure_uinput_access()
    timings = Timings(
        args.controller_settle,
        args.warning_wait,
        args.main_menu_wait,
        args.save_menu_wait,
    )
    window: str | None = None
    try:
        with UInput(
            CAPABILITIES,
            name=CONTROLLER_NAME,
            bustype=e.BUS_USB,
            vendor=0x045E,
            product=0x028E,
            version=0x0114,
        ) as controller:
            event("controller_ready", controller=CONTROLLER_NAME)
            wait("controller_settle", timings.controller_settle)
            subprocess.Popen(
                ["steam", "-applaunch", APP_ID],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            event("steam_launch", app_id=APP_ID)
            window = find_window(args.window_timeout)
            event("window_found", window=window)
            width, height = wait_for_geometry(window)
            event("window_geometry", width=width, height=height)
            if (width, height) != (3840, 2160):
                raise LaunchError(
                    f"Expected 3840x2160, got {width}x{height}; the cursor route is not proven for this layout"
                )
            wait("mod_warning", timings.warning)
            tap_button(controller, window, e.BTN_SOUTH)
            event("input", action="dismiss_mod_warning", button="A")
            wait("main_menu", timings.main_menu)
            tap_button(controller, window, e.BTN_SOUTH, duration=2.5)
            event("input", action="select_play", button="A", hold_seconds=2.5)
            wait("save_menu", timings.save_menu)
            if args.load_latest_save or load_save:
                save_pair = int(save["save_pair"])
                for _row in range(save_pair - 1):
                    tap_button(controller, window, e.BTN_DPAD_DOWN)
                    event("input", action="select_next_save_row", button="down")
                event(
                    "input",
                    action="load_verified_save",
                    save_pair=save_pair,
                    save=Path(str(save["save"])).name,
                    button="A",
                    hold_seconds=2.5,
                )
                tap_button(controller, window, e.BTN_SOUTH, duration=2.5)
                wait("gameplay_load", args.gameplay_wait)
            if args.screenshot is not None:
                capture(window, args.screenshot.resolve())
            event(
                "complete",
                result=(
                    "gameplay_ready"
                    if args.load_latest_save or load_save
                    else "save_menu_ready"
                ),
                window=window,
            )
            if args.interactive:
                interactive(controller, window)
    except Exception:
        if window is not None and args.failure_screenshot is not None:
            try:
                capture(window, args.failure_screenshot.resolve())
            except (
                LaunchError,
                OSError,
                subprocess.SubprocessError,
            ) as screenshot_error:
                event("failure_screenshot_error", error=str(screenshot_error))
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Launch NMS and optionally load the verified latest save"
    )
    value.add_argument("--window-timeout", type=float, default=120.0)
    value.add_argument("--controller-settle", type=float, default=2.0)
    value.add_argument("--warning-wait", type=float, default=50.0)
    value.add_argument("--main-menu-wait", type=float, default=12.0)
    value.add_argument("--save-menu-wait", type=float, default=7.0)
    value.add_argument(
        "--save-menu-only",
        action="store_true",
        help="Stop at the save menu (the default safe behavior)",
    )
    value.add_argument(
        "--load-latest-save",
        action="store_true",
        help="Select and load the already-verified latest save, without moving the player",
    )
    value.add_argument(
        "--load-save",
        metavar="FILENAME",
        help="Select and load this verified visible save file, such as save2.hg",
    )
    value.add_argument(
        "--gameplay-wait",
        type=float,
        default=75.0,
        help="Seconds to allow the selected save to load before continuing",
    )
    value.add_argument(
        "--interactive", action="store_true", help="Accept controller commands on stdin"
    )
    value.add_argument(
        "--screenshot", type=Path, help="Optional save-menu checkpoint screenshot"
    )
    value.add_argument(
        "--failure-screenshot",
        type=Path,
        default=Path("/tmp/squinch-nms-launch-failure.png"),
        help="Screenshot written only if automation fails after the NMS window appears",
    )
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        run(args)
    except (LaunchError, OSError, subprocess.SubprocessError) as error:
        event("error", error=str(error), error_type=type(error).__name__)
        return 1
    return 0
