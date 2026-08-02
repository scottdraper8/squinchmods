from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import InvestigationError

PACKAGE_DIR = Path(__file__).resolve().parents[2]
TOOLING_DIR = PACKAGE_DIR.parent
MINECRAFT_DIR = TOOLING_DIR.parent
REPOSITORY_ROOT = MINECRAFT_DIR.parents[1]
STATE_ROOT = MINECRAFT_DIR / "investigation-state"
ACTIVE_ROOT = STATE_ROOT / "active"
RUNS_ROOT = STATE_ROOT / "runs"
LOCKS_ROOT = STATE_ROOT / "locks"
WORKTREES_ROOT = STATE_ROOT / "worktrees"
ENV_SH = TOOLING_DIR / "env.sh"
PROBE_RUNTIME_ROOT = PACKAGE_DIR / "probe-runtime"
PROBE_OVERLAY = PACKAGE_DIR / "gradle" / "probe-overlay.gradle"

LOADERS = ("fabric", "forge", "neoforge", "quilt")


def resolve_project(value: str | Path) -> Path:
    project = Path(value).expanduser().resolve()
    if not project.is_dir():
        raise InvestigationError(
            "project_not_found", f"project directory does not exist: {project}"
        )
    if not (project / "gradlew").is_file():
        raise InvestigationError(
            "invalid_project", f"Gradle wrapper not found: {project / 'gradlew'}"
        )
    return project


def validate_loader(project: Path, loader: str) -> Path:
    if loader not in LOADERS:
        raise InvestigationError("invalid_loader", f"unsupported loader: {loader}")
    loader_dir = project / loader
    if not loader_dir.is_dir():
        raise InvestigationError(
            "invalid_loader", f"loader directory does not exist: {loader_dir}"
        )
    return loader_dir


def project_key(project: Path, loader: str) -> str:
    digest = hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:16]
    return f"{project.name}-{digest}-{loader}"


def active_path(project: Path, loader: str) -> Path:
    return ACTIVE_ROOT / f"{project_key(project, loader)}.json"


def lock_path(project: Path, loader: str) -> Path:
    return LOCKS_ROOT / f"{project_key(project, loader)}.lock"
