from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def _rules_allow(rules: list[dict] | None, features: dict[str, bool] | None = None) -> bool:
    if not rules:
        return True
    allowed = False
    current_os = {"Linux": "linux", "Windows": "windows", "Darwin": "osx"}.get(
        platform.system(), platform.system().lower()
    )
    current_arch = platform.machine().lower()
    features = features or {}
    for rule in rules:
        os_rule = rule.get("os", {})
        if os_rule.get("name") not in (None, current_os):
            continue
        if os_rule.get("arch") not in (None, current_arch):
            continue
        version = os_rule.get("version")
        if version is not None and re.search(version, platform.release()) is None:
            continue
        if any(features.get(name, False) != value for name, value in rule.get("features", {}).items()):
            continue
        allowed = rule.get("action") == "allow"
    return allowed


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_download(root: Path, download: dict) -> Path:
    path = root / "libraries" / download["path"]
    if not path.exists():
        url = download.get("url")
        if not url:
            raise RuntimeError(f"installed NeoForge library is missing and has no URL: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".squinch-part")
        try:
            with urllib.request.urlopen(url, timeout=60) as source, temporary.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"installed NeoForge library is not a regular file: {path}")
    expected = download.get("sha1")
    if expected and _sha1(path) != expected:
        raise RuntimeError(f"installed NeoForge library checksum differs: {path}")
    return path


def _expand_arguments(values: list, variables: dict[str, str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, dict):
            if not _rules_allow(value.get("rules")):
                continue
            value = value.get("value", [])
        items = value if isinstance(value, list) else [value]
        for item in items:
            expanded = str(item)
            for name, replacement in variables.items():
                expanded = expanded.replace("${" + name + "}", replacement)
            if "${" in expanded:
                raise RuntimeError(f"unresolved launcher argument variable: {expanded}")
            result.append(expanded)
    return result


def _extract_natives(archives: list[tuple[Path, tuple[str, ...]]], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    for archive, excludes in archives:
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                name = member.filename
                if member.is_dir() or any(name.startswith(prefix) for prefix in excludes):
                    continue
                output = (root / name).resolve()
                if not output.is_relative_to(root):
                    raise RuntimeError(f"native archive path escapes destination: {name}")
                output.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as input_file, output.open("wb") as output_file:
                    output_file.write(input_file.read())


def build_launch_command(
    client_home: Path,
    run_dir: Path,
    assets_dir: Path,
    version: str,
    java: Path,
) -> list[str]:
    child_path = client_home / "versions" / f"neoforge-{version}" / f"neoforge-{version}.json"
    child = json.loads(child_path.read_text(encoding="utf-8"))
    parent_id = child["inheritsFrom"]
    parent_path = client_home / "versions" / parent_id / f"{parent_id}.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))

    classpath: list[Path] = []
    natives: list[tuple[Path, tuple[str, ...]]] = []
    for library in [*parent.get("libraries", []), *child.get("libraries", [])]:
        if not _rules_allow(library.get("rules")):
            continue
        downloads = library.get("downloads", {})
        artifact = downloads.get("artifact")
        if artifact is not None:
            path = _verified_download(client_home, artifact)
            if path not in classpath:
                classpath.append(path)
        native_key = library.get("natives", {}).get("linux")
        if native_key:
            native_key = native_key.replace("${arch}", "64")
            classifier = downloads.get("classifiers", {}).get(native_key)
            if classifier is None:
                raise RuntimeError(f"native classifier {native_key!r} is missing for {library['name']}")
            natives.append((
                _verified_download(client_home, classifier),
                tuple(library.get("extract", {}).get("exclude", [])),
            ))
    client_jar = client_home / "versions" / parent_id / f"{parent_id}.jar"
    client_download = parent.get("downloads", {}).get("client", {})
    if not client_jar.is_file() or client_jar.is_symlink():
        raise RuntimeError(f"installed Minecraft client is missing: {client_jar}")
    if client_download.get("sha1") and _sha1(client_jar) != client_download["sha1"]:
        raise RuntimeError(f"installed Minecraft client checksum differs: {client_jar}")
    # NeoForge's production client provider supplies the patched SRG client. Adding the
    # inherited vanilla version JAR here creates a second named Minecraft module.

    asset_id = f"{parent_id}-{parent['assetIndex']['id']}"
    asset_index = assets_dir / "indexes" / f"{asset_id}.json"
    if not asset_index.is_file() or asset_index.is_symlink():
        raise RuntimeError(f"Loom asset index is missing: {asset_index}")
    natives_dir = run_dir / "natives"
    _extract_natives(natives, natives_dir)
    variables = {
        "auth_player_name": "SquinchProbe",
        "version_name": f"neoforge-{version}",
        "game_directory": str(run_dir),
        "assets_root": str(assets_dir),
        "assets_index_name": asset_id,
        "auth_uuid": "00000000000000000000000000000000",
        "auth_access_token": "0",
        "clientid": "0",
        "auth_xuid": "0",
        "user_type": "legacy",
        "version_type": "release",
        "natives_directory": str(natives_dir),
        "launcher_name": "squinch-mc-investigate",
        "launcher_version": "1",
        "classpath": os.pathsep.join(str(path) for path in classpath),
        "library_directory": str(client_home / "libraries"),
        "classpath_separator": os.pathsep,
    }
    jvm = _expand_arguments(parent["arguments"]["jvm"], variables)
    jvm.extend(_expand_arguments(child["arguments"]["jvm"], variables))
    game = _expand_arguments(parent["arguments"]["game"], variables)
    game.extend(_expand_arguments(child["arguments"]["game"], variables))
    return [
        str(java),
        "-Xmx24G",
        "-XX:ActiveProcessorCount=8",
        *jvm,
        child["mainClass"],
        *game,
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--client-home", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("gradle_command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    gradle_command = args.gradle_command
    if gradle_command[:1] == ["--"]:
        gradle_command = gradle_command[1:]
    if not gradle_command:
        parser.error("a Gradle preparation command is required after --")
    completed = subprocess.run(gradle_command, cwd=args.project, check=False)
    if completed.returncode != 0:
        return completed.returncode
    command = build_launch_command(
        args.client_home.resolve(), args.run_dir.resolve(), args.assets_dir.resolve(),
        args.version, args.java.resolve(),
    )
    os.chdir(args.run_dir)
    os.execvpe(command[0], command, os.environ)
    return 127


if __name__ == "__main__":
    sys.exit(main())
