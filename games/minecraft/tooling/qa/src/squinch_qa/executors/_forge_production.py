from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from squinch_qa.executors._server import ServerLaunchError


def _cache_root() -> Path:
    cache_home = os.environ.get("SQINCHMODS_CACHE_HOME")
    if cache_home:
        base = Path(cache_home)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
        base = base / "squinchmods"
    return base / "qa" / "forge-installers"


def _find_java_bin(env: dict[str, str], major: int) -> Path:
    env_home = env.get(f"JAVA_HOME_{major}_X64")
    if env_home and (Path(env_home) / "bin" / "java").is_file():
        return Path(env_home) / "bin" / "java"

    sdkman_dir = Path(env.get("SDKMAN_DIR", Path.home() / ".sdkman"))
    candidates_dir = sdkman_dir / "candidates" / "java"
    if candidates_dir.is_dir():
        candidates = sorted(candidates_dir.glob(f"{major}.*"))
        for candidate in candidates:
            java = candidate / "bin" / "java"
            if java.is_file():
                return java

    for candidate in (
        Path(f"/usr/lib/jvm/temurin-{major}-jdk-amd64"),
        Path(f"/usr/lib/jvm/java-{major}-openjdk-amd64"),
    ):
        java = candidate / "bin" / "java"
        if java.is_file():
            return java

    java_on_path = shutil.which("java", path=env.get("PATH"))
    if java_on_path:
        return Path(java_on_path)
    raise ServerLaunchError(f"Could not find Java {major} runtime")


def _download_forge_installer(
    minecraft_version: str,
    forge_version: str,
    log_path: Path,
) -> Path:
    forge_coord = f"{minecraft_version}-{forge_version}"
    cache_dir = _cache_root() / forge_coord
    installer = cache_dir / f"forge-{forge_coord}-installer.jar"
    if installer.is_file():
        return installer

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = installer.with_suffix(".tmp")
    url = (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        f"{forge_coord}/forge-{forge_coord}-installer.jar"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "squinchmods-qa/0.1"})
        with (
            urllib.request.urlopen(req, timeout=120) as resp,
            tmp.open("wb") as out,
        ):
            shutil.copyfileobj(resp, out)
        tmp.rename(installer)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        tmp.unlink(missing_ok=True)
        with log_path.open("ab") as log:
            log.write(f"Failed to download Forge installer {url}: {e}\n".encode())
        raise ServerLaunchError(f"Failed to download Forge installer: {e}") from e
    return installer


def _install_forge_server(
    *,
    server_dir: Path,
    installer: Path,
    java_bin: Path,
    log_path: Path,
    env: dict[str, str],
) -> None:
    server_dir.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = subprocess.run(
            [str(java_bin), "-jar", str(installer), "--installServer", str(server_dir)],
            cwd=server_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if proc.returncode != 0:
        raise ServerLaunchError(f"Forge installer exited with code {proc.returncode}")


def find_primary_mod_jar(loader_dir: Path) -> Path | None:
    libs_dir = loader_dir / "build" / "libs"
    candidates = [
        p
        for p in libs_dir.glob("*.jar")
        if not (p.stem.endswith("-sources") or p.stem.endswith("-dev"))
    ]
    return sorted(candidates)[-1] if candidates else None


def launch_forge_production_server(
    *,
    server_dir: Path,
    mod_dir: Path,
    tool_jar: Path | None,
    minecraft_version: str,
    forge_version: str,
    java_major: int,
    env: dict[str, str],
    logs_dir: Path,
) -> tuple[subprocess.Popen, Path, Path]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "server.stdout.log"

    java_bin = _find_java_bin(env, java_major)
    installer = _download_forge_installer(minecraft_version, forge_version, log_path)
    _install_forge_server(
        server_dir=server_dir,
        installer=installer,
        java_bin=java_bin,
        log_path=log_path,
        env=env,
    )

    mod_jar = find_primary_mod_jar(mod_dir / "forge")
    if mod_jar is None:
        raise ServerLaunchError(f"No Forge mod jar found under {mod_dir / 'forge'}")

    mods_dir = server_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mod_jar, mods_dir / mod_jar.name)
    if tool_jar is not None:
        shutil.copy2(tool_jar, mods_dir / tool_jar.name)

    (server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (server_dir / "server.properties").write_text(
        "\n".join(
            [
                "online-mode=false",
                "server-port=0",
                "enable-rcon=false",
                "level-name=world",
                "",
            ]
        ),
        encoding="utf-8",
    )

    forge_coord = f"{minecraft_version}-{forge_version}"
    unix_args = (
        server_dir
        / "libraries"
        / "net"
        / "minecraftforge"
        / "forge"
        / forge_coord
        / "unix_args.txt"
    )
    if not unix_args.is_file():
        raise ServerLaunchError(f"Forge server args file not found: {unix_args}")

    try:
        proc = subprocess.Popen(
            [
                str(java_bin),
                "@user_jvm_args.txt",
                f"@{unix_args}",
                "nogui",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=server_dir,
            env=env,
        )
    except OSError as e:
        raise ServerLaunchError(f"Failed to launch Forge production server: {e}") from e

    return proc, log_path, server_dir
