from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_TEMPORARY = tempfile.TemporaryDirectory(prefix="squinch-minecraft-investigate-tests-")
_WORKSPACE = Path(_TEMPORARY.name) / "test-tranche"
_WORKSPACE.mkdir()
(_WORKSPACE / ".tranche.json").write_text(
    json.dumps(
        {
            "schema_version": 1,
            "tranche": "test-tranche",
            "workspace": str(_WORKSPACE),
        }
    )
    + "\n",
    encoding="utf-8",
)
os.environ["SQUINCH_TRANCHE"] = "test-tranche"
os.environ["SQUINCH_TRANCHE_WORKSPACE"] = str(_WORKSPACE)
