from __future__ import annotations

import shutil
from pathlib import Path

from .mbin import convert, inspect_mbin
from .paths import sha256_file
from .xmlmodel import compare_xml, verify_export


def verify_asset_compile(patch: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    source = destination / f"{patch.stem}.MXML"
    shutil.copy2(patch, source)
    compiled, compile_result = convert(source, work_dir=destination)
    if not compiled:
        return {"passed": False, "compile": compile_result}
    inspection = inspect_mbin(compiled, destination / "verify")
    decompiled = inspection.get("decompiled")
    if not decompiled:
        return {"passed": False, "compile": compile_result, "inspection": inspection}
    comparison = compare_xml(source, Path(decompiled))
    leaf_verification = verify_export(source, Path(decompiled))
    compiler_default_expansion_only = comparison["equal"] or all(
        difference["kind"] == "added" for difference in comparison["differences"]
    )
    return {
        "passed": leaf_verification["passed"],
        "exact_roundtrip": comparison["equal"],
        "compiler_default_expansion_only": (
            compiler_default_expansion_only and not comparison["equal"]
        ),
        "authored_leaf_verification": leaf_verification,
        "compile": compile_result,
        "compiled": {"path": str(compiled), "sha256": sha256_file(compiled)},
        "inspection": inspection,
        "semantic_comparison": comparison,
    }
