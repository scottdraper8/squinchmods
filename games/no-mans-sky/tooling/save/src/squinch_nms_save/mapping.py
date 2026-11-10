from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import SaveToolError

MAPPING_VERSION = "7.14.0.1"
MAPPING_URL = (
    "https://github.com/monkeyman192/MBINCompiler/releases/download/v7.14.0-pre1/mapping.json"
)
MAPPING_SHA256 = "8ce1d93707edd694e7430f767bf0c97cc89e0bc839e6cf2375898c19e3ba98f3"
MAX_MAPPING_SIZE = 2 * 1024 * 1024


@dataclass(frozen=True)
class SaveMapping:
    version: str
    names: dict[str, str]
    ambiguous: dict[str, tuple[str, ...]]
    raw_names: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> SaveMapping:
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SaveToolError(f"cannot read save mapping {path}: {exc}") from exc
        if not isinstance(value, dict) or value.get("libMBIN_version") != MAPPING_VERSION:
            raise SaveToolError(
                f"mapping must be MBINCompiler {MAPPING_VERSION}: "
                f"found {value.get('libMBIN_version') if isinstance(value, dict) else None!r}"
            )
        entries = value.get("Mapping")
        if not isinstance(entries, list):
            raise SaveToolError("mapping has no Mapping array")
        candidates: dict[str, set[str]] = {}
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise SaveToolError(f"mapping entry {index} is not an object")
            key = entry.get("Key")
            name = entry.get("Value")
            if not isinstance(key, str) or not isinstance(name, str):
                raise SaveToolError(f"mapping entry {index} requires string Key and Value")
            candidates.setdefault(key, set()).add(name)
        ambiguous = {
            key: tuple(sorted(names)) for key, names in candidates.items() if len(names) > 1
        }
        names = {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}
        reverse_candidates: dict[str, set[str]] = {}
        for raw_key, semantic_names in candidates.items():
            for semantic_name in semantic_names:
                reverse_candidates.setdefault(semantic_name, set()).add(raw_key)
        reverse_ambiguous = {
            name: raw_keys for name, raw_keys in reverse_candidates.items() if len(raw_keys) > 1
        }
        if reverse_ambiguous:
            names_list = ", ".join(sorted(reverse_ambiguous)[:5])
            raise SaveToolError(f"mapping has ambiguous semantic names: {names_list}")
        raw_names = {name: next(iter(raw_keys)) for name, raw_keys in reverse_candidates.items()}
        return cls(MAPPING_VERSION, names, ambiguous, raw_names)

    def deobfuscate(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self.deobfuscate(item) for item in value]
        if not isinstance(value, dict):
            return value
        result: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = self.names.get(raw_key, raw_key)
            if key in result:
                raise SaveToolError(
                    f"mapping produces duplicate key {key!r}; raw key {raw_key!r} is ambiguous"
                )
            result[key] = self.deobfuscate(child)
        return result

    def obfuscate(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self.obfuscate(item) for item in value]
        if not isinstance(value, dict):
            return value
        result: dict[str, Any] = {}
        for semantic_key, child in value.items():
            key = self.raw_names.get(semantic_key, semantic_key)
            if key in result:
                raise SaveToolError(
                    f"reverse mapping produces duplicate raw key {key!r} from {semantic_key!r}"
                )
            result[key] = self.obfuscate(child)
        return result

    def raw_key(self, semantic_name: str) -> str:
        try:
            return self.raw_names[semantic_name]
        except KeyError as exc:
            raise SaveToolError(f"mapping has no raw key for {semantic_name!r}") from exc


def verify_mapping(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    mapping = SaveMapping.load(resolved)
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise SaveToolError(f"cannot read save mapping {resolved}: {exc}") from exc
    return {
        "path": str(resolved),
        "version": mapping.version,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw_key_count": len(mapping.names) + len(mapping.ambiguous),
        "semantic_key_count": len(mapping.raw_names),
        "ambiguous_raw_keys": {
            key: list(names) for key, names in sorted(mapping.ambiguous.items())
        },
        "pinned": hashlib.sha256(raw).hexdigest() == MAPPING_SHA256,
    }


def _workspace_path(path: Path) -> Path:
    workspace_value = os.environ.get("SQUINCH_TRANCHE_WORKSPACE")
    if not workspace_value:
        raise SaveToolError("SQUINCH_TRANCHE_WORKSPACE is not set; invoke through tooling/squinch")
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(Path(workspace_value).resolve())
    except ValueError as exc:
        raise SaveToolError(
            f"mapping output must be inside the selected tranche: {resolved}"
        ) from exc
    return resolved


def acquire_mapping(output: Path, *, url: str = MAPPING_URL) -> dict[str, Any]:
    target = _workspace_path(output)
    if target.exists():
        raise SaveToolError(f"refusing to overwrite mapping: {target}")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read(MAX_MAPPING_SIZE + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise SaveToolError(f"cannot acquire pinned mapping: {exc}") from exc
    if len(raw) > MAX_MAPPING_SIZE:
        raise SaveToolError("mapping download exceeds the 2 MiB limit")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != MAPPING_SHA256:
        raise SaveToolError(
            f"mapping download hash mismatch: expected {MAPPING_SHA256}, found {digest}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SaveToolError(f"cannot write mapping {target}: {exc}") from exc
    return verify_mapping(target)
