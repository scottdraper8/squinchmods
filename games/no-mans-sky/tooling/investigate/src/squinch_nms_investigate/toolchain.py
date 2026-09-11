from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from .errors import InvestigationError
from .paths import TOOLCHAIN_CONFIG, cache_root, sha256_file, steam_build_id


@lru_cache(maxsize=1)
def config() -> dict:
    value = tomllib.loads(TOOLCHAIN_CONFIG.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        raise InvestigationError(
            "invalid_toolchain_config", "toolchain.toml schema_version must be 1"
        )
    target = value.get("target")
    hgpak = value.get("hgpaktool")
    mbin = value.get("mbincompiler")
    if (
        not isinstance(target, dict)
        or not isinstance(target.get("nms_version"), str)
        or target.get("branch") not in {"public", "experimental"}
        or not isinstance(target.get("steam_build_ids"), list)
        or not target["steam_build_ids"]
        or not all(isinstance(item, str) and item.isdigit() for item in target["steam_build_ids"])
    ):
        raise InvestigationError("invalid_toolchain_config", "Invalid target toolchain pin")
    if (
        not isinstance(hgpak, dict)
        or hgpak.get("package") != "hgpaktool"
        or not isinstance(hgpak.get("version"), str)
        or hgpak.get("platform") != "windows"
    ):
        raise InvestigationError("invalid_toolchain_config", "Invalid HGPAKtool pin")
    if (
        not isinstance(mbin, dict)
        or not isinstance(mbin.get("url"), str)
        or not mbin["url"].startswith("https://")
        or not re.fullmatch(r"[0-9a-f]{64}", str(mbin.get("sha256", "")))
        or not re.search(r"@sha256:[0-9a-f]{64}$", str(mbin.get("container_image", "")))
        or not isinstance(mbin.get("dotnet_major"), int)
    ):
        raise InvestigationError("invalid_toolchain_config", "Invalid MBINCompiler pin")
    return value


def target_identity(game_root: Path) -> dict:
    target = config()["target"]
    actual = steam_build_id(game_root)
    allowed = target["steam_build_ids"]
    return {
        "nms_version": target["nms_version"],
        "branch": target["branch"],
        "allowed_steam_build_ids": allowed,
        "actual_steam_build_id": actual,
        "matches": actual in allowed,
    }


def assert_supported_build(game_root: Path) -> dict:
    identity = target_identity(game_root)
    if not identity["matches"]:
        raise InvestigationError(
            "unsupported_game_build",
            "The installed Steam build is not approved for the pinned NMS toolchain",
            **identity,
        )
    return identity


def mbin_path() -> Path:
    value = config()["mbincompiler"]
    return cache_root() / "mbincompiler" / value["release"] / value["filename"]


def sync_mbincompiler() -> dict:
    value = config()["mbincompiler"]
    destination = mbin_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (destination.is_symlink() or not destination.is_file()):
        raise InvestigationError(
            "unsafe_tool_path", f"Tool destination is not a regular file: {destination}"
        )
    if destination.is_file() and sha256_file(destination) == value["sha256"]:
        downloaded = False
    else:
        try:
            request = urllib.request.Request(
                value["url"], headers={"User-Agent": "squinchmods-nms-investigate/0.1"}
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise InvestigationError(
                "tool_download_failed", f"Could not download MBINCompiler: {exc}"
            ) from exc
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        actual = sha256_file(temporary)
        if actual != value["sha256"]:
            temporary.unlink(missing_ok=True)
            raise InvestigationError(
                "tool_hash_mismatch",
                "Downloaded MBINCompiler hash does not match the pin",
                expected=value["sha256"],
                actual=actual,
            )
        temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR)
        temporary.replace(destination)
        downloaded = True
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR)
    return {
        "path": str(destination),
        "release": value["release"],
        "reported_version": value["reported_version"],
        "sha256": sha256_file(destination),
        "downloaded": downloaded,
    }


def _run(
    command: list[str], *, cwd: Path | None = None, timeout: float = 300
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, cwd=cwd, text=True, capture_output=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InvestigationError(
            "tool_execution_failed", f"Could not execute {command[0]}: {exc}"
        ) from exc


def hgpak_command() -> list[str]:
    executable = shutil.which("hgpaktool")
    if not executable:
        raise InvestigationError(
            "missing_tool", "The uv-locked HGPAKtool console script is unavailable"
        )
    return [executable]


def hgpak_identity() -> dict:
    value = config()["hgpaktool"]
    installed = importlib.metadata.version(value["package"])
    if installed != value["version"]:
        raise InvestigationError(
            "hgpaktool_version_mismatch",
            f"Installed HGPAKtool is {installed}, expected {value['version']}",
        )
    result = _run([*hgpak_command(), "--help"], timeout=60)
    combined = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or value["version"] not in combined:
        raise InvestigationError(
            "hgpaktool_unhealthy",
            f"Pinned HGPAKtool did not report version {value['version']}: {combined}",
        )
    return {
        "package": value["package"],
        "version": value["version"],
        "executable": hgpak_command()[0],
        "reported": combined.splitlines()[0],
    }


def _dotnet_has_major(major: int) -> bool:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return False
    result = _run([dotnet, "--list-runtimes"], timeout=30)
    return result.returncode == 0 and any(
        line.split()[1].startswith(f"{major}.")
        for line in result.stdout.splitlines()
        if len(line.split()) > 1
    )


def mbin_backend(*, acquire: bool = False) -> dict:
    value = config()["mbincompiler"]
    if _dotnet_has_major(value["dotnet_major"]):
        return {"kind": "host-dotnet", "dotnet_major": value["dotnet_major"]}
    podman = shutil.which("podman")
    if not podman:
        raise InvestigationError(
            "missing_runtime", f"MBINCompiler needs .NET {value['dotnet_major']} or Podman"
        )
    inspect = _run(
        [podman, "image", "inspect", value["container_image"], "--format", "json"], timeout=30
    )
    if inspect.returncode != 0:
        if not acquire:
            raise InvestigationError(
                "missing_container_image",
                f"Pinned container image is absent; run toolchain sync: {value['container_image']}",
            )
        pull = _run([podman, "pull", value["container_image"]], timeout=600)
        if pull.returncode != 0:
            raise InvestigationError(
                "container_pull_failed",
                f"Could not acquire {value['container_image']}: {pull.stderr.strip()}",
            )
        inspect = _run(
            [podman, "image", "inspect", value["container_image"], "--format", "json"], timeout=30
        )
    try:
        details = json.loads(inspect.stdout)[0]
    except (json.JSONDecodeError, IndexError, TypeError) as exc:
        raise InvestigationError(
            "container_identity_failed", "Could not establish MBINCompiler container identity"
        ) from exc
    return {
        "kind": "podman",
        "image": value["container_image"],
        "image_id": details.get("Id"),
        "repo_digests": details.get("RepoDigests", []),
    }


def mbin_identity(*, acquire_backend: bool = False) -> dict:
    path = mbin_path()
    value = config()["mbincompiler"]
    if not path.is_file() or path.is_symlink():
        raise InvestigationError(
            "missing_tool", "Pinned MBINCompiler is not installed; run toolchain sync"
        )
    actual = sha256_file(path)
    if actual != value["sha256"]:
        raise InvestigationError(
            "tool_hash_mismatch",
            "Cached MBINCompiler does not match its pin",
            expected=value["sha256"],
            actual=actual,
        )
    identity = {
        "path": str(path),
        "release": value["release"],
        "reported_version": value["reported_version"],
        "sha256": actual,
    }
    identity["backend"] = mbin_backend(acquire=acquire_backend)
    return identity


def run_mbincompiler(
    arguments: list[str],
    *,
    work_dir: Path,
    timeout: float = 300,
    acquire_backend: bool = False,
) -> subprocess.CompletedProcess[str]:
    identity = mbin_identity(acquire_backend=acquire_backend)
    binary = Path(identity["path"])
    backend = identity["backend"]
    local_tool_dir = work_dir / ".mbincompiler"
    local_tool_dir.mkdir(exist_ok=True)
    local_binary = local_tool_dir / binary.name
    if not local_binary.exists():
        shutil.copy2(binary, local_binary)
        local_binary.chmod(local_binary.stat().st_mode | stat.S_IXUSR)
    if backend["kind"] == "host-dotnet":
        command = [str(local_binary), *arguments]
    else:
        relative_arguments: list[str] = []
        for argument in arguments:
            path = Path(argument)
            try:
                relative_arguments.append(
                    f"/work/{path.resolve().relative_to(work_dir.resolve()).as_posix()}"
                )
            except (ValueError, OSError):
                relative_arguments.append(argument)
        command = [
            shutil.which("podman") or "podman",
            "run",
            "--rm",
            "--network=none",
            "--userns=keep-id",
            "-v",
            f"{work_dir}:/work:Z",
            "-w",
            "/work",
            backend["image"],
            f"/work/.mbincompiler/{binary.name}",
            *relative_arguments,
        ]
    result = _run(command, cwd=work_dir, timeout=timeout)
    return result


def verify_mbincompiler(*, acquire_backend: bool = False) -> dict:
    identity = mbin_identity(acquire_backend=acquire_backend)
    with tempfile.TemporaryDirectory(prefix="squinch-mbin-verify-") as temporary:
        result = run_mbincompiler(
            ["version"],
            work_dir=Path(temporary),
            timeout=60,
            acquire_backend=acquire_backend,
        )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or identity["release"] not in output:
        raise InvestigationError(
            "mbincompiler_unhealthy",
            f"Pinned MBINCompiler did not report {identity['release']}: {output}",
        )
    identity["verified_output"] = output
    return identity
