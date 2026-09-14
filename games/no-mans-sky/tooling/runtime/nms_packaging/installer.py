from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .adapter import is_owned_installed_adapter, retire_superseded_adapters
from .common import (
    APP_ID,
    OWNED_PROXY_HASH,
    PRODUCT_MARKER,
    BuildError,
    file_hash,
    nms_running,
    run,
)


def install_tree(package: Path, game_root: Path) -> None:
    if nms_running():
        raise BuildError("NMS must be stopped before installing Search Probes")
    source_runtime = package / "Binaries/SearchProbes"
    source_proxy = package / "Binaries/winmm.dll"
    source_mod = package / "GAMEDATA/MODS/SearchProbes"
    target_runtime = game_root / "Binaries/SearchProbes"
    target_proxy = game_root / "Binaries/winmm.dll"
    target_mod = game_root / "GAMEDATA/MODS/SearchProbes"
    if target_proxy.exists():
        target_proxy_hash = file_hash(target_proxy)
        source_proxy_hash = file_hash(source_proxy)
        owned_hash_path = target_runtime / OWNED_PROXY_HASH
        recorded_hash = (
            owned_hash_path.read_text(encoding="ascii").strip()
            if owned_hash_path.is_file()
            else ""
        )
        if (
            target_proxy_hash != source_proxy_hash
            and target_proxy_hash != recorded_hash
        ):
            raise BuildError(
                f"refusing to overwrite a foreign WINMM proxy: {target_proxy}; "
                "chain-loader compatibility is not established"
            )
    preserve: dict[str, bytes] = {}
    old_state = target_runtime / "app/.resident-search"
    for name in (
        "presets.json",
        "presets.backup.json",
    ):
        path = old_state / name
        if path.is_file():
            preserve[name] = path.read_bytes()
    with tempfile.TemporaryDirectory(
        prefix=".search-probes-install-", dir=game_root
    ) as temp_text:
        staging = Path(temp_text)
        shutil.copytree(source_runtime, staging / "runtime")
        shutil.copytree(source_mod, staging / "mod")
        shutil.copy2(source_proxy, staging / "winmm.dll")
        state = staging / "runtime/app/.resident-search"
        for name, content in preserve.items():
            (state / name).write_bytes(content)
        backups: list[tuple[Path, Path]] = []
        installed_targets: list[Path] = []
        try:
            for role, target in (("runtime", target_runtime), ("mod", target_mod)):
                if target.exists():
                    owned = (
                        (target / "SEARCH_PROBES_PRODUCT").is_file()
                        and (target / "SEARCH_PROBES_PRODUCT").read_text(
                            encoding="utf-8"
                        )
                        == PRODUCT_MARKER
                        if target == target_runtime
                        else is_owned_installed_adapter(target)
                    )
                    if not owned:
                        raise BuildError(
                            f"refusing to replace an unowned product path: {target}"
                        )
                    backup = staging / f"backup-{role}"
                    target.replace(backup)
                    backups.append((target, backup))
            if target_proxy.exists():
                backup = staging / "backup-winmm.dll"
                target_proxy.replace(backup)
                backups.append((target_proxy, backup))
            target_runtime.parent.mkdir(parents=True, exist_ok=True)
            target_mod.parent.mkdir(parents=True, exist_ok=True)
            (staging / "runtime").replace(target_runtime)
            installed_targets.append(target_runtime)
            (staging / "mod").replace(target_mod)
            installed_targets.append(target_mod)
            os.replace(staging / "winmm.dll", target_proxy)
            installed_targets.append(target_proxy)
        except BaseException:
            for target in reversed(installed_targets):
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
            for target, backup in reversed(backups):
                if backup.exists():
                    backup.replace(target)
            raise
    retire_superseded_adapters(game_root)


def configure_proton_override(steam_root: Path) -> None:
    proton = Path(
        os.environ.get(
            "SQN_NMS_PROTON_ROOT", steam_root / "steamapps/common/Proton - Experimental"
        )
    )
    prefix = Path(
        os.environ.get(
            "SQN_NMS_PREFIX",
            steam_root / f"steamapps/compatdata/{APP_ID}/pfx",
        )
    )
    wine = proton / "files/bin/wine"
    if not wine.is_file() or not prefix.is_dir():
        return
    env = dict(os.environ)
    env.update(
        {
            "WINEPREFIX": str(prefix),
            "WINEDEBUG": "-all",
            "WINEFSYNC": "1",
            "WINEDLLPATH": f"{proton}/files/lib/vkd3d:{proton}/files/lib/wine",
            "LD_LIBRARY_PATH": (
                f"{proton}/files/lib/x86_64-linux-gnu:"
                f"{proton}/files/lib/i386-linux-gnu:"
                "/usr/lib/pressure-vessel/overrides/lib/x86_64-linux-gnu/aliases:"
                "/usr/lib/pressure-vessel/overrides/lib/i386-linux-gnu/aliases"
            ),
        }
    )
    run(
        [
            str(wine),
            "reg",
            "add",
            r"HKCU\Software\Wine\AppDefaults\NMS.exe\DllOverrides",
            "/v",
            "winmm",
            "/d",
            "native,builtin",
            "/f",
        ],
        env=env,
        capture=True,
    )
