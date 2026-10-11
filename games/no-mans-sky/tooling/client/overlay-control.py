#!/usr/bin/env python3
"""Send bounded pointer input to a focused NMS Search Probes overlay."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from evdev import UInput
from evdev import ecodes as e
from nms_client.controls import ensure_uinput_access

TITLE = "No Man's Sky"
DIAGNOSTICS = (
    Path.home()
    / ".local/share/Steam/steamapps/compatdata/275850/pfx/drive_c/users/steamuser/AppData/Local/SearchProbes/overlay.json"
)


def query(*arguments: str) -> str:
    return subprocess.check_output(
        ["xdotool", *arguments], text=True, timeout=5
    ).strip()


def fields(value: str) -> dict[str, int]:
    return {
        key: int(number)
        for key, number in (line.split("=") for line in value.splitlines())
    }


def require_overlay(window: str, diagnostics: Path) -> None:
    if query("getactivewindow") != window:
        raise RuntimeError("NMS must already have focus; no input sent")
    if time.time() - diagnostics.stat().st_mtime > 2:
        raise RuntimeError("Overlay diagnostics are stale; no input sent")
    state = json.loads(diagnostics.read_text())
    if not state["input"]["active"] or not state["input"]["visible"]:
        raise RuntimeError(
            "Search Probes must be open and capturing input; no input sent"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("move", "click", "scroll"))
    parser.add_argument("x", type=int, help="absolute desktop X")
    parser.add_argument("y", type=int, help="absolute desktop Y")
    parser.add_argument("--wheel", type=int, default=-3)
    parser.add_argument("--diagnostics", type=Path, default=DIAGNOSTICS)
    args = parser.parse_args()
    windows = query("search", "--onlyvisible", "--name", f"^{TITLE}$").splitlines()
    if len(windows) != 1:
        raise RuntimeError("Expected exactly one visible NMS window")
    window = windows[0]
    rect = fields(query("getwindowgeometry", "--shell", window))
    if not (
        rect["X"] <= args.x < rect["X"] + rect["WIDTH"]
        and rect["Y"] <= args.y < rect["Y"] + rect["HEIGHT"]
    ):
        raise ValueError("Pointer target is outside the NMS window")
    ensure_uinput_access()
    require_overlay(window, args.diagnostics)
    with UInput(
        {e.EV_KEY: [e.BTN_LEFT], e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]},
        name="Squinch Overlay Pointer",
    ) as pointer:
        time.sleep(0.5)
        stable = 0
        for _ in range(40):
            require_overlay(window, args.diagnostics)
            position = fields(query("getmouselocation", "--shell"))
            dx, dy = args.x - position["X"], args.y - position["Y"]
            if max(abs(dx), abs(dy)) <= 6:
                stable += 1
                if stable == 3:
                    break
            else:
                stable = 0
                for axis, error in ((e.REL_X, dx), (e.REL_Y, dy)):
                    step = min(100, max(2, abs(error) // 4)) if error else 0
                    pointer.write(e.EV_REL, axis, step if error >= 0 else -step)
                pointer.syn()
            time.sleep(0.3)
        else:
            raise RuntimeError("Pointer did not settle on the target; no click sent")
        require_overlay(window, args.diagnostics)
        if args.action == "click":
            pointer.write(e.EV_KEY, e.BTN_LEFT, 1)
            pointer.syn()
            try:
                time.sleep(0.2)
            finally:
                pointer.write(e.EV_KEY, e.BTN_LEFT, 0)
                pointer.syn()
        elif args.action == "scroll":
            pointer.write(e.EV_REL, e.REL_WHEEL, max(-10, min(10, args.wheel)))
            pointer.syn()
        time.sleep(0.3)


if __name__ == "__main__":
    main()
