from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .catalog import CatalogArtifact, sha256_file
from .errors import AcquisitionError

RUNTIME_SUFFIXES = {
    ".EXML",
    ".MBIN",
    ".MXML",
    ".DDS",
    ".WEM",
    ".BNK",
    ".TTF",
    ".OTF",
    ".PNG",
}
SOURCE_SUFFIXES = {".LUA", ".TXT", ".MD", ".PDF"}
NMS_CONTENT_ROOTS = {
    "AUDIO",
    "FONTS",
    "GLOBALS",
    "LANGUAGE",
    "MATERIALS",
    "METADATA",
    "MODELS",
    "MUSIC",
    "SCENES",
    "SHADERS",
    "TEXTURES",
    "UI",
}


def _safe_member(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise AcquisitionError(f"archive contains an unsafe path: {name!r}")
    return path


def _zip_members(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            values: list[str] = []
            for info in archive.infolist():
                _safe_member(info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise AcquisitionError(
                        f"archive contains a symbolic link: {info.filename}"
                    )
                values.append(info.filename)
            return values
    except zipfile.BadZipFile as exc:
        raise AcquisitionError(f"invalid ZIP archive: {path}") from exc


def _seven_zip_members(path: Path) -> list[str]:
    executable = shutil.which("7z")
    if not executable:
        raise AcquisitionError("7z is required to inspect non-ZIP Nexus archives")
    result = subprocess.run(
        [executable, "l", "-slt", "--", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AcquisitionError(f"7z could not list {path}: {result.stderr.strip()}")
    members: list[str] = []
    in_entries = False
    entry: dict[str, str] = {}
    for line in result.stdout.splitlines() + [""]:
        if line.startswith("----------"):
            in_entries = True
            entry = {}
            continue
        if not in_entries:
            continue
        if not line:
            if entry.get("Path"):
                name = entry["Path"]
                _safe_member(name)
                attributes = entry.get("Attributes", "")
                if "L" in attributes or entry.get("Symbolic Link"):
                    raise AcquisitionError(f"archive contains a symbolic link: {name}")
                members.append(name)
            entry = {}
            continue
        if " = " in line:
            key, value = line.split(" = ", 1)
            entry[key] = value
    if not members:
        raise AcquisitionError(f"archive contains no entries: {path}")
    return members


def list_members(path: Path) -> list[str]:
    if zipfile.is_zipfile(path):
        return _zip_members(path)
    return _seven_zip_members(path)


def _extract(path: Path, destination: Path) -> None:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            archive.extractall(destination)
        return
    executable = shutil.which("7z")
    if not executable:
        raise AcquisitionError("7z is required to extract this Nexus archive")
    result = subprocess.run(
        [executable, "x", "-y", f"-o{destination}", "--", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AcquisitionError(f"7z could not extract {path}: {result.stderr.strip()}")


def _validate_tree(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise AcquisitionError(
                f"extracted tree contains a symbolic link: {path.relative_to(root)}"
            )
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise AcquisitionError(
                f"extracted tree contains a special file: {path.relative_to(root)}"
            )
    return files


def _runtime_roots(files: list[Path], root: Path) -> list[str]:
    candidates: set[str] = set()
    for file in files:
        relative = file.relative_to(root)
        suffix = file.suffix.upper()
        if suffix not in RUNTIME_SUFFIXES:
            continue
        parts = relative.parts
        content_index = next(
            (
                index
                for index, part in enumerate(parts[:-1])
                if part.upper() in NMS_CONTENT_ROOTS
            ),
            None,
        )
        if content_index is not None:
            prefix = parts[:content_index]
            candidates.add(PurePosixPath(*prefix).as_posix() if prefix else ".")
        elif file.name.casefold() == "loctable.mxml":
            parent = relative.parent.as_posix()
            candidates.add(parent)
    return sorted(candidates)


def inspect_archive(
    artifact: CatalogArtifact,
    archive: Path,
    *,
    reference_root: Path,
) -> dict[str, Any]:
    resolved_archive = archive.expanduser().resolve()
    if not resolved_archive.is_file() or resolved_archive.is_symlink():
        raise AcquisitionError(f"archive is not a regular file: {resolved_archive}")
    members = list_members(resolved_archive)
    destination = reference_root / artifact.reference_relative_directory
    if destination.exists():
        report_path = destination / "inspection.json"
        if destination.is_symlink() or not destination.is_dir():
            raise AcquisitionError(
                f"inspection destination is not a regular directory: {destination}"
            )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AcquisitionError(
                f"existing inspection has no valid report: {report_path}"
            ) from exc
        archive_sha256 = sha256_file(resolved_archive)
        expected = {
            "artifact_id": artifact.id,
            "mod_id": artifact.mod_id,
            "file_id": artifact.file_id,
            "nms_version": artifact.nms_version,
            "archive_sha256": archive_sha256,
        }
        mismatches = [
            key for key, value in expected.items() if report.get(key) != value
        ]
        if mismatches:
            raise AcquisitionError(
                "existing inspection does not match this artifact/archive "
                f"({', '.join(mismatches)}): {destination}"
            )
        report["inspection_root"] = str(destination)
        report["report"] = str(report_path)
        return report
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = destination.parent
    with tempfile.TemporaryDirectory(
        prefix=f".{artifact.file_id}-", dir=temporary_parent
    ) as temporary:
        temporary_path = Path(temporary)
        _extract(resolved_archive, temporary_path)
        files = _validate_tree(temporary_path)
        suffix_counts = Counter((path.suffix.upper() or "<NONE>") for path in files)
        runtime_files = [
            path for path in files if path.suffix.upper() in RUNTIME_SUFFIXES
        ]
        source_files = [
            path for path in files if path.suffix.upper() in SOURCE_SUFFIXES
        ]
        inventory = [
            {
                "path": path.relative_to(temporary_path).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "classification": (
                    "runtime"
                    if path in runtime_files
                    else "authoring-or-documentation"
                    if path in source_files
                    else "unknown"
                ),
            }
            for path in sorted(files)
        ]
        report = {
            "schema_version": 1,
            "inspected_at": datetime.now(UTC).isoformat(),
            "artifact_id": artifact.id,
            "mod_id": artifact.mod_id,
            "file_id": artifact.file_id,
            "nms_version": artifact.nms_version,
            "archive": str(resolved_archive),
            "archive_sha256": sha256_file(resolved_archive),
            "archive_member_count": len(members),
            "file_count": len(files),
            "runtime_file_count": len(runtime_files),
            "authoring_or_documentation_file_count": len(source_files),
            "suffix_counts": dict(sorted(suffix_counts.items())),
            "candidate_deployment_roots": _runtime_roots(files, temporary_path),
            "files": inventory,
        }
        (temporary_path / "inspection.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary_path, destination)
    report["inspection_root"] = str(destination)
    report["report"] = str(destination / "inspection.json")
    return report
