from __future__ import annotations

import re
import shutil
from pathlib import Path

from .errors import InvestigationError
from .paths import sha256_file
from .toolchain import run_mbincompiler
from .xmlmodel import compare_xml, xml_summary

VERSION = re.compile(r"\b\d+\.\d+\.\d+\.\d+\b")


def compiler_version(path: Path, *, work_dir: Path) -> dict:
    result = run_mbincompiler(["version", str(path)], work_dir=work_dir)
    output = (result.stdout + result.stderr).strip()
    match = VERSION.search(output)
    return {
        "returncode": result.returncode,
        "version": match.group(0) if match else None,
        "output": output[-2000:],
    }


def convert(path: Path, *, work_dir: Path) -> tuple[Path | None, dict]:
    result = run_mbincompiler([str(path)], work_dir=work_dir)
    output = (result.stdout + result.stderr).strip()
    if path.suffix.casefold() == ".mbin":
        generated = path.with_suffix(".MXML")
    elif path.suffix.casefold() == ".mxml":
        generated = path.with_suffix(".MBIN")
    else:
        generated = path.with_suffix(path.suffix + ".out")
    return (generated if generated.is_file() else None), {
        "returncode": result.returncode,
        "output": output[-10000:],
    }


def inspect_mbin(source: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    local = destination / source.name
    shutil.copy2(source, local)
    version = compiler_version(local, work_dir=destination)
    generated, conversion = convert(local, work_dir=destination)
    result = {
        "source": str(source),
        "sha256": sha256_file(source),
        "version": version,
        "decompile": conversion,
        "decompiled": str(generated) if generated else None,
    }
    if generated:
        result["xml"] = xml_summary(generated)
    return result


def roundtrip(source: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    original_dir = destination / "original"
    original_dir.mkdir()
    local = original_dir / source.name
    shutil.copy2(source, local)
    original_version = compiler_version(local, work_dir=destination)
    original_xml, decompile = convert(local, work_dir=destination)
    if not original_xml:
        return {
            "passed": False,
            "source": str(source),
            "source_sha256": sha256_file(source),
            "version": original_version,
            "decompile": decompile,
            "failure": "decompile-failed",
        }
    rebuilt_dir = destination / "rebuilt"
    rebuilt_dir.mkdir()
    rebuilt_xml_input = rebuilt_dir / original_xml.name
    shutil.copy2(original_xml, rebuilt_xml_input)
    rebuilt_mbin, compile_result = convert(rebuilt_xml_input, work_dir=destination)
    if not rebuilt_mbin:
        return {
            "passed": False,
            "source": str(source),
            "source_sha256": sha256_file(source),
            "version": original_version,
            "decompile": decompile,
            "compile": compile_result,
            "failure": "recompile-failed",
        }
    verify_dir = destination / "verify"
    verify_dir.mkdir()
    verify_mbin = verify_dir / rebuilt_mbin.name
    shutil.copy2(rebuilt_mbin, verify_mbin)
    verify_xml, verify_result = convert(verify_mbin, work_dir=destination)
    if not verify_xml:
        raise InvestigationError(
            "roundtrip_verify_failed", f"Rebuilt MBIN could not be decompiled: {source}"
        )
    semantic = compare_xml(original_xml, verify_xml)
    return {
        "passed": semantic["equal"],
        "source": str(source),
        "source_sha256": sha256_file(source),
        "version": original_version,
        "decompile": decompile,
        "compile": compile_result,
        "verify_decompile": verify_result,
        "original_xml": xml_summary(original_xml),
        "rebuilt_mbin": {"path": str(rebuilt_mbin), "sha256": sha256_file(rebuilt_mbin)},
        "semantic_comparison": semantic,
    }
