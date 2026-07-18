from __future__ import annotations

import stat as _stat
from pathlib import Path

import pytest

from squinch_qa.executors._forge_production import _find_java_bin, find_primary_mod_jar
from squinch_qa.executors._server import ServerLaunchError

# NOTE ON SCOPE: _download_forge_installer, _install_forge_server, and
# launch_forge_production_server all require a real network fetch and/or a
# real java binary running the Forge installer jar. Exercising those for real
# is out of scope for this pass (network/installer-boundary testing); they
# are left untested here as a known gap. _find_java_bin and
# find_primary_mod_jar are pure filesystem-lookup functions with no
# network/subprocess dependency, so they get direct unit tests below.


def _make_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho fake-java\n")
    mode = path.stat().st_mode
    path.chmod(mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)


# ── _find_java_bin ────────────────────────────────────────────────────────────


class TestFindJavaBin:
    def test_prefers_java_home_major_env_var(self, tmp_path: Path):
        java_home = tmp_path / "gh-actions-jdk21"
        java_bin = java_home / "bin" / "java"
        _make_executable(java_bin)
        env = {
            "JAVA_HOME_21_X64": str(java_home),
            "SDKMAN_DIR": str(tmp_path / "no-sdkman"),
            "PATH": str(tmp_path / "empty-path"),
        }
        (tmp_path / "empty-path").mkdir()

        result = _find_java_bin(env, 21)

        assert result == java_bin

    def test_falls_back_to_sdkman_candidates(self, tmp_path: Path):
        sdkman_dir = tmp_path / "sdkman"
        java_bin = sdkman_dir / "candidates" / "java" / "21.0.11-tem" / "bin" / "java"
        _make_executable(java_bin)
        env = {
            "SDKMAN_DIR": str(sdkman_dir),
            "PATH": str(tmp_path / "empty-path"),
        }
        (tmp_path / "empty-path").mkdir()

        result = _find_java_bin(env, 21)

        assert result == java_bin

    def test_falls_back_to_path_lookup(self, tmp_path: Path):
        path_dir = tmp_path / "bin"
        java_on_path = path_dir / "java"
        _make_executable(java_on_path)
        env = {
            "SDKMAN_DIR": str(tmp_path / "no-sdkman"),
            "PATH": str(path_dir),
        }

        result = _find_java_bin(env, 999)  # no real system install for major 999

        assert result == java_on_path

    def test_raises_server_launch_error_when_nothing_found(self, tmp_path: Path):
        env = {
            "SDKMAN_DIR": str(tmp_path / "no-sdkman"),
            "PATH": str(tmp_path / "empty-path"),
        }
        (tmp_path / "empty-path").mkdir()

        with pytest.raises(ServerLaunchError, match="Could not find Java"):
            _find_java_bin(env, 999)


# ── find_primary_mod_jar ──────────────────────────────────────────────────────


class TestFindPrimaryModJar:
    def test_excludes_sources_and_dev_jars(self, tmp_path: Path):
        libs = tmp_path / "build" / "libs"
        libs.mkdir(parents=True)
        (libs / "mymod-1.0.0-sources.jar").write_bytes(b"x")
        (libs / "mymod-1.0.0-dev.jar").write_bytes(b"x")
        (libs / "mymod-1.0.0.jar").write_bytes(b"x")

        result = find_primary_mod_jar(tmp_path)

        assert result == libs / "mymod-1.0.0.jar"

    def test_returns_none_when_no_jars_present(self, tmp_path: Path):
        (tmp_path / "build" / "libs").mkdir(parents=True)

        assert find_primary_mod_jar(tmp_path) is None

    def test_returns_none_when_libs_dir_missing(self, tmp_path: Path):
        assert find_primary_mod_jar(tmp_path) is None

    def test_picks_highest_sorted_name_when_multiple_candidates(self, tmp_path: Path):
        libs = tmp_path / "build" / "libs"
        libs.mkdir(parents=True)
        (libs / "mymod-1.0.0.jar").write_bytes(b"x")
        (libs / "mymod-2.0.0.jar").write_bytes(b"x")

        result = find_primary_mod_jar(tmp_path)

        assert result == libs / "mymod-2.0.0.jar"
