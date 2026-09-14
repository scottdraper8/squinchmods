#!/usr/bin/env python3
"""Send bounded pointer input only to the visible Search Probes form."""

from __future__ import annotations

import argparse
import subprocess
import time

from evdev import UInput
from evdev import ecodes as e
from nms_client.controls import ensure_uinput_access

TITLE = "NMS System Search"


def query(*arguments: str) -> str:
    return subprocess.check_output(
        ["xdotool", *arguments], text=True, timeout=5
    ).strip()


def fields(value: str) -> dict[str, int]:
    return {
        key: int(number)
        for key, number in (line.split("=") for line in value.splitlines())
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("move", "click", "scroll"))
    parser.add_argument("x", type=int, help="absolute desktop X")
    parser.add_argument("y", type=int, help="absolute desktop Y")
    parser.add_argument("--wheel", type=int, default=-3)
    args = parser.parse_args()
    windows = query("search", "--onlyvisible", "--name", f"^{TITLE}$").splitlines()
    if len(windows) != 1:
        raise RuntimeError("Expected exactly one visible Search Probes form")
    window = windows[0]
    rect = fields(query("getwindowgeometry", "--shell", window))
    if not (
        rect["X"] <= args.x < rect["X"] + rect["WIDTH"]
        and rect["Y"] <= args.y < rect["Y"] + rect["HEIGHT"]
    ):
        raise ValueError("Pointer target is outside the Search Probes form")
    ensure_uinput_access()
    query("windowactivate", "--sync", window)
    with UInput(
        {e.EV_KEY: [e.BTN_LEFT], e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL]},
        name="Squinch Form Pointer",
    ) as pointer:
        time.sleep(0.5)
        stable = 0
        for _ in range(40):
            if query("getactivewindow") != window:
                raise RuntimeError("Search Probes lost focus; no click sent")
            position = fields(query("getmouselocation", "--shell"))
            dx, dy = args.x - position["X"], args.y - position["Y"]
            if max(abs(dx), abs(dy)) <= 6:
                stable += 1
                if stable == 3:
                    break
            else:
                stable = 0
                for axis, error in ((e.REL_X, dx), (e.REL_Y, dy)):
                    step = min(100, max(1, abs(error) // 4)) if error else 0
                    pointer.write(e.EV_REL, axis, step if error >= 0 else -step)
                pointer.syn()
            time.sleep(0.3)
        else:
            raise RuntimeError("Pointer did not settle on the target; no click sent")
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
