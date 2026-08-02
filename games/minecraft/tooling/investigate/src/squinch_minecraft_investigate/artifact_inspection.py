from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from .errors import InvestigationError


_ENTRY_MARKERS = (
    ("development-probe-sentinel", "META-INF/squinch-development-probe"),
    ("probe-mixin-config", "squinch-investigate.mixins.json"),
)
_ENTRY_PREFIXES = (
    ("probe-class", "org/squinchmods/investigate/"),
)
_CONTENT_MARKERS = (
    ("development-probe-sentinel", b"SQUINCH_DEVELOPMENT_PROBE"),
    ("probe-mixin-reference", b"squinch-investigate.mixins.json"),
    ("probe-class-reference", b"org/squinchmods/investigate/"),
    ("probe-class-reference", b"org.squinchmods.investigate."),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_artifact(path: Path) -> dict:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise InvestigationError(
            "artifact_not_found", f"artifact is not a regular file: {resolved}"
        )

    findings: set[tuple[str, str, str]] = set()
    try:
        with zipfile.ZipFile(resolved) as archive:
            bad_entry = archive.testzip()
            if bad_entry is not None:
                raise InvestigationError(
                    "invalid_artifact",
                    f"artifact has a corrupt ZIP entry: {resolved}!/{bad_entry}",
                )
            entries = archive.infolist()
            for entry in entries:
                name = entry.filename
                direct_kinds: set[str] = set()
                for kind, marker in _ENTRY_MARKERS:
                    if name == marker:
                        findings.add((kind, marker, name))
                        direct_kinds.add(kind)
                for kind, prefix in _ENTRY_PREFIXES:
                    if name.startswith(prefix) and not entry.is_dir():
                        findings.add((kind, prefix, name))
                        direct_kinds.add(kind)

                if entry.is_dir():
                    continue
                with archive.open(entry) as stream:
                    overlap = b""
                    while chunk := stream.read(1024 * 1024):
                        sample = overlap + chunk
                        for kind, marker in _CONTENT_MARKERS:
                            if kind == "development-probe-sentinel" and direct_kinds:
                                continue
                            if kind == "probe-class-reference" and (
                                "probe-class" in direct_kinds
                                or "probe-mixin-config" in direct_kinds
                            ):
                                continue
                            if (
                                kind == "probe-mixin-reference"
                                and "probe-mixin-config" in direct_kinds
                            ):
                                continue
                            if marker in sample:
                                findings.add((kind, marker.decode("ascii"), name))
                        overlap = sample[-64:]
    except zipfile.BadZipFile as exc:
        raise InvestigationError(
            "invalid_artifact", f"artifact is not a readable ZIP/JAR: {resolved}"
        ) from exc

    return {
        "path": str(resolved),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
        "entry_count": len(entries),
        "clean": not findings,
        "findings": [
            {"kind": kind, "marker": marker, "entry": entry}
            for kind, marker, entry in sorted(findings)
        ],
    }
