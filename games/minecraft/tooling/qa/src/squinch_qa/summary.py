from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from squinch_qa.errors import SummaryError


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as e:
        raise SummaryError(f"missing {path}") from e
    except json.JSONDecodeError as e:
        raise SummaryError(f"malformed JSON in {path}: {e}") from e


def _job_line(run_dir: Path, job_ref: dict[str, Any]) -> str:
    matrix_id = job_ref["matrix_id"]
    status = job_ref["status"]

    job_result = _read_json(run_dir / job_ref["result"])
    duration_s = job_result.get("duration_s", 0.0)

    detail = ""
    failure = job_result.get("failure")
    if status in ("fail", "error") and failure:
        detail = f"  {failure['reason']}"
        if failure.get("detail"):
            detail += f": {failure['detail']}"
    elif status == "expected_failure":
        job_manifest = _read_json(run_dir / job_ref["manifest"])
        ef = job_manifest.get("test", {}).get("expected_failure")
        if ef:
            expires = f" (expires {ef['expires']})" if ef.get("expires") else ""
            detail = f"  {ef['reason']}{expires}"

    return f"  {matrix_id:<40} {status:<18} {duration_s:>7.1f}s{detail}"


def render_summary(run_dir: Path) -> str:
    """Render a human-readable summary of a completed run from its already-written
    manifest/result JSON files. Read-only; does not execute or re-check anything."""
    result = _read_json(run_dir / "result.json")
    qa_manifest = _read_json(run_dir / "qa-manifest.json")

    lines = [
        f"Run {qa_manifest['run_id']} — {qa_manifest['mod_id']} ({qa_manifest['profile']})",
        f"Status: {result['status'].upper()} (exit {result['exit_code']})"
        f"   Duration: {result['duration_s']:.1f}s",
        "  ".join(f"{status}: {count}" for status, count in result["counts"].items()),
        "",
    ]
    lines.extend(_job_line(run_dir, job_ref) for job_ref in qa_manifest["jobs"])

    return "\n".join(lines) + "\n"
