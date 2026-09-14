#!/usr/bin/env python3
"""Build and optionally install the Search Probes package."""

from __future__ import annotations

import json
import sys

from nms_packaging.cli import main
from nms_packaging.common import BuildError

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, json.JSONDecodeError, OSError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
