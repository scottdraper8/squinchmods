#!/usr/bin/env python3
"""Attach one temporary virtual controller to an already-running NMS window."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach a temporary virtual controller to a running NMS window"
    )
    parser.parse_args()
    sys.path.insert(0, str(Path(__file__).parent))
    from nms_client import controls as launch

    launch.ensure_uinput_access()
    window = launch.find_window(10.0)
    with launch.UInput(
        launch.CAPABILITIES,
        name=launch.CONTROLLER_NAME,
        bustype=launch.e.BUS_USB,
        vendor=0x045E,
        product=0x028E,
        version=0x0114,
    ) as controller:
        launch.event(
            "controller_ready", controller=launch.CONTROLLER_NAME, window=window
        )
        time.sleep(2.0)
        launch.interactive(controller, window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
