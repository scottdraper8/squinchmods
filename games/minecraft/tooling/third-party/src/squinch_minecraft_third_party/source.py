from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .errors import AcquisitionError


def _run(command: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "")
        raise AcquisitionError(f"command failed: {' '.join(command)}\n{detail}") from exc
    return result.stdout.strip()


def checkout_source(
    repository: str,
    destination: Path,
    ref: str,
    *,
    minecraft_version: str,
    sparse_paths: tuple[str, ...],
    replace: bool = False,
) -> dict[str, object]:
    if destination.exists():
        if not replace:
            raise AcquisitionError(f"source destination already exists: {destination} (use --replace explicitly)")
        if destination.is_symlink() or destination.resolve() in {Path("/"), Path.home().resolve()}:
            raise AcquisitionError(f"refusing unsafe source replacement: {destination}")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", "--branch", ref, repository, str(destination)])
    _run(["git", "sparse-checkout", "init", "--cone"], cwd=destination)
    _run(["git", "sparse-checkout", "set", *sparse_paths], cwd=destination)
    _run(["git", "checkout", ref], cwd=destination)
    commit = _run(["git", "rev-parse", "HEAD"], cwd=destination)
    manifest = {
        "schema_version": 1,
        "acquired_at": datetime.now(UTC).isoformat(),
        "minecraft_version": minecraft_version,
        "repository": repository,
        "requested_ref": ref,
        "resolved_commit": commit,
        "shallow": True,
        "blob_filter": True,
        "sparse_paths": list(sparse_paths),
    }
    (destination / "source-acquisition.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
