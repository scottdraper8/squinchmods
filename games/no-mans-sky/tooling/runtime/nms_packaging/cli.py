from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .common import APP_ID, BuildError, validate_game_root
from .distribution import build_package, verify_manifest
from .installer import configure_proton_override, install_tree


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parents[4]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Build and install the self-starting Search Probes Nexus package"
    )
    value.add_argument("output", type=Path, help="expanded package output directory")
    value.add_argument("--no-install", action="store_true", help="build only")
    value.add_argument(
        "--install-only",
        action="store_true",
        help="verify and install an existing expanded package without rebuilding it",
    )
    value.add_argument("--rebuild-runtime", action="store_true")
    value.add_argument("--game-root", type=Path)
    value.add_argument(
        "--adapter-root",
        type=Path,
        help="use a previously generated adapter after validating its exact production contract",
    )
    return value


def main() -> int:
    args = parser().parse_args()
    if args.no_install and args.install_only:
        raise BuildError("--no-install and --install-only are mutually exclusive")
    repo_root = repository_root()
    steam_root = Path(
        os.environ.get("SQN_STEAM_ROOT", Path.home() / ".local/share/Steam")
    )
    game_root = validate_game_root(
        args.game_root
        or Path(
            os.environ.get(
                "SQN_NMS_GAME_ROOT", steam_root / "steamapps/common/No Man's Sky"
            )
        )
    )
    runtime_root = (
        Path(
            os.environ.get(
                "SQN_NMS_RUNTIME_ROOT",
                steam_root / f"steamapps/compatdata/{APP_ID}/nmspy-runtime",
            )
        )
        .expanduser()
        .resolve()
    )
    if args.install_only:
        package = args.output.expanduser().resolve()
        archive = package.parent / f"{package.name}.zip"
    else:
        package, archive = build_package(
            args.output,
            repo_root=repo_root,
            game_root=game_root,
            runtime_root=runtime_root,
            rebuild_runtime=args.rebuild_runtime,
            adapter_root=args.adapter_root,
        )
    verify_manifest(package)
    if not args.no_install:
        install_tree(package, game_root)
        configure_proton_override(steam_root)
    print(
        json.dumps(
            {
                "archive": str(archive),
                "installed": not args.no_install,
                "nms_root": str(game_root),
                "package": str(package),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0
