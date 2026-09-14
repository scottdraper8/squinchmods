"""Build and optionally install a self-starting Search Probes Nexus layout."""

import hashlib
import subprocess
from pathlib import Path

APP_ID = "275850"
NMS_VERSION = "7.01"
PRODUCT_MARKER = "SearchProbes product=1\n"
OWNED_PROXY_HASH = "OWNED_WINMM_SHA256"
FEDORA_MINGW_IMAGE = (
    "docker.io/library/fedora:44@"
    "sha256:be9d65e2344d805cc11114319c685ecaa96b6d9b4350a0a6460cdb931babbd19"
)
MOD_SOURCE = Path("games/no-mans-sky/mods/search-probes/src/search_probes")
MOD_NATIVE_BOOTSTRAP = Path("games/no-mans-sky/mods/search-probes/native-bootstrap")


class BuildError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    timeout: float = 900.0,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=capture,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BuildError(
            f"command timed out after {timeout:g}s: {' '.join(command)}"
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() if capture else ""
        raise BuildError(
            f"command failed ({result.returncode}): {' '.join(command)} {detail}"
        )
    return result


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nms_running() -> bool:
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text(encoding="utf-8").strip() == "NMS.exe":
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return False


def validate_game_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    if not (root / "Binaries/NMS.exe").is_file() or not (root / "GAMEDATA").is_dir():
        raise BuildError(f"not a No Man's Sky installation: {root}")
    return root
