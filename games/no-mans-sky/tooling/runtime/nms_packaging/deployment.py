from __future__ import annotations

import json
from pathlib import Path

from .common import PRODUCT_MARKER, BuildError

DEPLOYMENT_RECORD = "DEPLOYMENT_SOURCES.json"


def linked_source_tree(target: Path) -> Path | None:
    sources: set[Path] = set()
    for path in target.rglob("*"):
        relative = path.relative_to(target)
        if any(
            part in {".resident-search", "logs", "__pycache__"}
            for part in relative.parts
        ):
            continue
        if not path.is_symlink():
            continue
        if not path.is_file():
            raise BuildError(
                f"unsupported directory or dangling deployment link: {path}"
            )
        resolved = path.resolve(strict=True)
        source = resolved.parents[len(relative.parts) - 1]
        if source / relative != resolved or source.name != target.name:
            raise BuildError(
                f"deployment link does not mirror its product tree: {path}"
            )
        if source != target.resolve():
            sources.add(source)
    if len(sources) > 1:
        raise BuildError(f"product has multiple deployment sources: {target}")
    return next(iter(sources), None)


def deployment_targets(game_root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    runtime = game_root / "Binaries/SearchProbes"
    adapter = game_root / "GAMEDATA/MODS/SearchProbes"
    proxy = game_root / "Binaries/winmm.dll"
    runtimes, adapters, proxies = [runtime], [adapter], [proxy]
    source = linked_source_tree(runtime)
    if source is not None:
        if source.parent.name != "Binaries":
            raise BuildError(
                f"runtime deployment source is not under Binaries: {source}"
            )
        runtimes.append(source)
        proxies.append(source.parent / "winmm.dll")
    source = linked_source_tree(adapter)
    if source is not None:
        adapters.append(source)
    record = runtime / DEPLOYMENT_RECORD
    if record.is_file():
        remembered = json.loads(record.read_text())
        if remembered.get("schema") != 1:
            raise BuildError("unsupported deployment-source record")
        for key, targets in (("runtime", runtimes), ("adapter", adapters)):
            value = remembered.get(key)
            if value is None:
                continue
            previous = Path(value).resolve(strict=True)
            if previous.name != "SearchProbes" or previous == targets[0].resolve():
                raise BuildError(f"invalid remembered deployment source: {previous}")
            if len(targets) > 1 and previous != targets[1]:
                raise BuildError(
                    f"deployment source changed since installation: {previous}"
                )
            if key == "runtime" and (
                previous.parent.name != "Binaries"
                or not (previous / "SEARCH_PROBES_PRODUCT").is_file()
                or (previous / "SEARCH_PROBES_PRODUCT").read_text() != PRODUCT_MARKER
            ):
                raise BuildError(f"unowned remembered runtime source: {previous}")
            if previous not in targets:
                targets.append(previous)
            if key == "runtime" and previous.parent / "winmm.dll" not in proxies:
                proxies.append(previous.parent / "winmm.dll")
    if proxy.is_symlink():
        source_proxy = proxy.resolve(strict=True)
        if source_proxy not in proxies:
            raise BuildError(
                f"WINMM has an unrelated deployment source: {source_proxy}"
            )
    return runtimes, adapters, proxies
