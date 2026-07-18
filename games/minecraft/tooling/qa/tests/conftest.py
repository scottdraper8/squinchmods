from __future__ import annotations

import json
import stat as _stat
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
# Real squinchmods repo root (parent config + schemas live here)
REAL_REPO_ROOT = Path(__file__).parents[5]

FAKE_SERVER_SCRIPT = Path(__file__).parent / "fixtures" / "fake_server.py"


def _build_fake_repo(
    tmp_path: Path,
    *,
    mod_configs: dict[str, Path],
    parent_config: Path | None = None,
) -> Path:
    """
    Construct a temporary repo tree with the real parent config/schemas plus
    the given mod configs placed at
    .squinch/games/minecraft/mods/<name>/config.yml. A bare
    games/minecraft/mods/<name>/ directory is also created for each mod,
    since load_mod_config requires the mod's source checkout to exist
    alongside its config; tests needing real source-tree content (e.g. a
    stub gradlew) build further on top via the runner_repo fixture below.
    Returns the fake repo root.

    Pass parent_config to use a fixture parent .squinch/config.yml instead of
    the real repo's (e.g. to exercise a profile/limits combination the real
    parent config doesn't have); schemas are always copied from the real repo.
    """
    squinch_dir = tmp_path / ".squinch"
    squinch_dir.mkdir()
    schema_dir = squinch_dir / "schema"
    schema_dir.mkdir()

    shutil.copy(
        parent_config or (REAL_REPO_ROOT / ".squinch" / "config.yml"),
        squinch_dir / "config.yml",
    )
    shutil.copy(
        REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
        schema_dir / "global-config.schema.json",
    )
    shutil.copy(
        REAL_REPO_ROOT / ".squinch" / "schema" / "mod-config.schema.json",
        schema_dir / "mod-config.schema.json",
    )

    mod_config_root = squinch_dir / "games" / "minecraft" / "mods"
    for name, src in mod_configs.items():
        mod_config_dir = mod_config_root / name
        mod_config_dir.mkdir(parents=True)
        shutil.copy(src, mod_config_dir / "config.yml")

        mod_source_dir = tmp_path / "games" / "minecraft" / "mods" / name
        mod_source_dir.mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Fake repo with redstone-backport and ReTerraForged fixture configs."""
    return _build_fake_repo(
        tmp_path,
        mod_configs={
            "redstone-backport": FIXTURES / "redstone-backport-mod.yml",
            "ReTerraForged": FIXTURES / "reterraforged-mod.yml",
        },
    )


@pytest.fixture
def qa_run_factory(tmp_path: Path):
    """
    Factory fixture: build a fake completed run dir (qa-manifest.json plus
    per-job manifest.json/result.json) for replace-pipeline tests. Hashes are
    computed correctly from the actual on-disk bytes by default; pass
    jar_sha256_override / world_sha256_override to simulate a mismatch.
    """
    from squinch_qa.artifacts import sha256_file
    from squinch_qa.replace.world_hash import world_hash

    def _make(
        *,
        jobs: list[dict],
        run_id: str = "run-1",
        runs_root: Path | None = None,
        mod_id: str = "fake-mod",
    ) -> Path:
        rdir = (runs_root or tmp_path / "qa-runs") / run_id
        rdir.mkdir(parents=True, exist_ok=True)

        job_refs = []
        for j in jobs:
            target_id = j["target_id"]
            test_id = j["test_id"]
            status = j.get("status", "pass")
            jdir = rdir / "jobs" / target_id / test_id
            jdir.mkdir(parents=True, exist_ok=True)
            matrix_id = f"{target_id}/{test_id}"

            artifacts = []
            jar_sha256 = None
            if j.get("jar_bytes") is not None:
                jar_path = jdir / "mod.jar"
                jar_path.write_bytes(j["jar_bytes"])
                artifacts.append("mod.jar")
                jar_sha256 = j.get("jar_sha256_override", sha256_file(jar_path))

            world_sha256 = None
            if j.get("world_src") is not None:
                world_dst = jdir / "world"
                shutil.copytree(j["world_src"], world_dst)
                artifacts.append("world")
                world_sha256 = j.get("world_sha256_override", world_hash(world_dst))

            (jdir / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "run_id": j.get("run_id_override", run_id),
                        "profile": "default",
                        "matrix_id": j.get("matrix_id_override", matrix_id),
                        "target": {
                            "id": target_id,
                            "java": 17,
                            "loader": "neoforge",
                            "loader_version": None,
                            "minecraft": "1.21.1",
                        },
                        "mod": {"id": mod_id, "jar_sha256": jar_sha256},
                        "test": {"id": test_id, "required": True, "status": status},
                        "world_sha256": world_sha256,
                    }
                )
            )
            (jdir / "result.json").write_text(
                json.dumps(
                    {
                        "status": status,
                        "started_at": "2026-01-01T00:00:00+00:00",
                        "finished_at": "2026-01-01T00:01:00+00:00",
                        "duration_s": 60.0,
                        "logs": [],
                        "artifacts": artifacts,
                        "failure": None,
                    }
                )
            )

            job_refs.append(
                {
                    "manifest": f"jobs/{target_id}/{test_id}/manifest.json",
                    "matrix_id": matrix_id,
                    "result": f"jobs/{target_id}/{test_id}/result.json",
                    "status": status,
                    "target": target_id,
                    "test": test_id,
                }
            )

        (rdir / "qa-manifest.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "run_id": run_id,
                    "profile": "default",
                    "mod_id": mod_id,
                    "plan_sha256": "deadbeef",
                    "repo_commit": None,
                    "mod_commit": None,
                    "jobs": job_refs,
                }
            )
        )
        return rdir

    return _make


def _make_stub_gradlew(mod_dir: Path) -> None:
    """Write an executable stub gradlew that routes *:runServer to fake_server.py."""
    gradlew = mod_dir / "gradlew"
    gradlew.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        f'    *:runServer) exec python3 "{FAKE_SERVER_SCRIPT}" "$@" ;;\n'
        "  esac\n"
        "done\n"
        "exit 0\n"
    )
    mode = gradlew.stat().st_mode
    gradlew.chmod(mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)


@pytest.fixture
def runner_repo(tmp_path: Path) -> Path:
    """
    Fake repo extended with dummy subproject trees and a stub gradlew.
    redstone-backport uses loader 'forge'; ReTerraForged uses 'neoforge' and 'fabric'.
    """
    repo = _build_fake_repo(
        tmp_path,
        mod_configs={
            "redstone-backport": FIXTURES / "redstone-backport-mod.yml",
            "ReTerraForged": FIXTURES / "reterraforged-mod.yml",
        },
    )
    for mod_name, loaders in [
        ("redstone-backport", ["forge"]),
        ("ReTerraForged", ["neoforge", "fabric"]),
    ]:
        mod_dir = repo / "games" / "minecraft" / "mods" / mod_name
        for loader in loaders:
            (mod_dir / loader / "build" / "libs").mkdir(parents=True)
            (mod_dir / loader / "run" / "mods").mkdir(parents=True)
        _make_stub_gradlew(mod_dir)
    return repo


@pytest.fixture
def make_job_context(runner_repo: Path, tmp_path: Path):
    """
    Factory fixture: call it to get a JobContext for executor tests.
    Defaults to forge-1.20.1 / build on redstone-backport.
    """
    from squinch_qa.artifacts import job_dir as _art_job_dir
    from squinch_qa.executors.base import JobContext
    from squinch_qa.models import Target

    def _make(
        test_id: str = "build",
        target_id: str = "forge-1.20.1",
        mod_name: str = "redstone-backport",
        config: dict | None = None,
        *,
        repo: Path | None = None,
        target: Target | None = None,
    ) -> JobContext:
        repo = repo or runner_repo
        qa_runs_dir = tmp_path / "qa-runs"
        run_id = "test-run"
        jdir = _art_job_dir(qa_runs_dir, run_id, target_id, test_id)
        jdir.mkdir(parents=True, exist_ok=True)
        return JobContext(
            run_id=run_id,
            target_id=target_id,
            test_id=test_id,
            job_dir=jdir,
            adapter=None,
            test_config=config or {},
            repo_root=repo,
            mod_dir=repo / "games" / "minecraft" / "mods" / mod_name,
            target=target,
        )

    return _make
