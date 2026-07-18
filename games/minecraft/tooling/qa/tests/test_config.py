from __future__ import annotations

import shutil

import pytest

from squinch_qa.config import find_repo_root, load_mod_config, load_parent_config
from squinch_qa.errors import ConfigError, UnknownMod

from conftest import REAL_REPO_ROOT


class TestLoadParentConfig:
    def test_happy_path(self, fake_repo):
        parent = load_parent_config(fake_repo)
        assert parent.default_profile == "default"
        assert "default" in parent.profiles
        assert "dev" in parent.profiles
        assert "pre-pr" in parent.profiles
        assert "release" in parent.profiles

    def test_missing_file(self, tmp_path):
        (tmp_path / ".squinch" / "schema").mkdir(parents=True)
        shutil.copy(
            REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
            tmp_path / ".squinch" / "schema" / "global-config.schema.json",
        )
        with pytest.raises(
            ConfigError, match=str(tmp_path / ".squinch" / "config.yml")
        ):
            load_parent_config(tmp_path)

    def test_malformed_yaml(self, tmp_path):
        squinch = tmp_path / ".squinch"
        squinch.mkdir()
        (squinch / "config.yml").write_text("key: [unclosed\n")
        schema_dir = squinch / "schema"
        schema_dir.mkdir()
        shutil.copy(
            REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
            schema_dir / "global-config.schema.json",
        )
        with pytest.raises(ConfigError, match="YAML parse error"):
            load_parent_config(tmp_path)

    def test_schema_invalid(self, tmp_path):
        squinch = tmp_path / ".squinch"
        squinch.mkdir()
        # Missing required 'globals' key
        (squinch / "config.yml").write_text("schema: 1\n")
        schema_dir = squinch / "schema"
        schema_dir.mkdir()
        shutil.copy(
            REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
            schema_dir / "global-config.schema.json",
        )
        with pytest.raises(ConfigError, match="Schema validation failed"):
            load_parent_config(tmp_path)

    def test_profile_fields_loaded(self, fake_repo):
        parent = load_parent_config(fake_repo)
        default = parent.profiles["default"]
        assert "build" in default.tests
        assert "server-smoke" in default.tests
        assert "pregen" in default.tests
        assert default.max_parallel == 4
        assert default.max_jobs == 32

    def test_test_defaults_loaded(self, fake_repo):
        parent = load_parent_config(fake_repo)
        assert "pregen" in parent.tests
        pregen = parent.tests["pregen"]
        assert "config" in pregen
        assert pregen["config"]["preset"] == "xs"


class TestLoadModConfig:
    def test_happy_path_by_filesystem_name(self, fake_repo):
        mod, path = load_mod_config(fake_repo, "redstone-backport")
        assert mod.mod_id == "redstone-backport"
        assert mod.display_name == "Redstone Backport"
        assert len(mod.targets) == 2
        target_ids = {t.id for t in mod.targets}
        assert "forge-1.20.1" in target_ids
        assert "forge-1.21.4" in target_ids

    def test_happy_path_by_mod_id(self, fake_repo):
        # ReTerraForged dir name is "ReTerraForged", mod.id is "reterraforged"
        mod, _ = load_mod_config(fake_repo, "reterraforged")
        assert mod.mod_id == "reterraforged"
        assert mod.display_name == "ReTerraForged"

    def test_case_insensitive_filesystem_match(self, fake_repo):
        # mod.id is "reterraforged" and the fixture directory is "ReTerraForged".
        # Query with a casing that matches neither exactly ("RETERRAFORGED" !=
        # "reterraforged" and != "ReTerraForged"), so this can only succeed via
        # the directory-name case-insensitive clause, not the mod.id == mod_slug
        # clause (and not the exact-case filesystem glob in Branch 1).
        mod, _ = load_mod_config(fake_repo, "RETERRAFORGED")
        assert mod.mod_id == "reterraforged"

    def test_unknown_mod_lists_available_ids(self, fake_repo):
        with pytest.raises(UnknownMod) as exc_info:
            load_mod_config(fake_repo, "no-such-mod")
        msg = str(exc_info.value)
        assert "no-such-mod" in msg
        assert "redstone-backport" in msg or "reterraforged" in msg

    def test_missing_config_file(self, tmp_path):
        squinch = tmp_path / ".squinch"
        squinch.mkdir()
        schema_dir = squinch / "schema"
        schema_dir.mkdir()
        shutil.copy(REAL_REPO_ROOT / ".squinch" / "config.yml", squinch / "config.yml")
        shutil.copy(
            REAL_REPO_ROOT / ".squinch" / "schema" / "global-config.schema.json",
            schema_dir / "global-config.schema.json",
        )
        shutil.copy(
            REAL_REPO_ROOT / ".squinch" / "schema" / "mod-config.schema.json",
            schema_dir / "mod-config.schema.json",
        )
        with pytest.raises(UnknownMod) as exc_info:
            load_mod_config(tmp_path, "ghost-mod")
        msg = str(exc_info.value)
        assert "ghost-mod" in msg
        assert "Available mod ids: []" in msg

    def test_schema_invalid_mod(self, fake_repo):
        # Overwrite ReTerraForged config with something schema-invalid
        mod_config_dir = (
            fake_repo / ".squinch" / "games" / "minecraft" / "mods" / "ReTerraForged"
        )
        (mod_config_dir / "config.yml").write_text(
            "schema: 1\nmod:\n  id: reterraforged\n"
            # missing required 'targets' key
        )
        with pytest.raises(ConfigError, match="Schema validation failed"):
            load_mod_config(fake_repo, "reterraforged")

    def test_config_without_source_checkout_raises(self, fake_repo):
        shutil.rmtree(fake_repo / "games" / "minecraft" / "mods" / "ReTerraForged")
        with pytest.raises(ConfigError, match="no source checkout"):
            load_mod_config(fake_repo, "reterraforged")

    def test_returns_mod_source_dir_not_config_dir(self, fake_repo):
        _, mod_dir = load_mod_config(fake_repo, "reterraforged")
        assert mod_dir == fake_repo / "games" / "minecraft" / "mods" / "ReTerraForged"


class TestFindRepoRoot:
    def test_finds_root_from_root(self):
        found = find_repo_root(REAL_REPO_ROOT)
        assert found == REAL_REPO_ROOT

    def test_finds_root_walking_up(self, tmp_path):
        # Create a minimal .squinch/config.yml
        squinch = tmp_path / ".squinch"
        squinch.mkdir()
        (squinch / "config.yml").write_text("schema: 1\n")
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        found = find_repo_root(deep)
        assert found == tmp_path

    def test_raises_when_not_found(self, tmp_path):
        with pytest.raises(ConfigError, match="Could not find"):
            find_repo_root(tmp_path)
