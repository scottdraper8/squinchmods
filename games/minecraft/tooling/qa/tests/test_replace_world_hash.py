from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from squinch_qa.errors import ValidationError
from squinch_qa.replace.world_hash import world_hash


def _make_world(root: Path) -> Path:
    world = root / "world"
    (world / "region").mkdir(parents=True)
    (world / "region" / "r.0.0.mca").write_bytes(b"chunk data")
    (world / "level.dat").write_bytes(b"level data")
    return world


class TestWorldHash:
    def test_deterministic_across_calls(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        assert world_hash(world) == world_hash(world)

    def test_deterministic_across_identical_copies(self, tmp_path: Path) -> None:
        import shutil

        w1 = _make_world(tmp_path / "a")
        w2 = tmp_path / "b" / "world"
        shutil.copytree(w1, w2)
        assert world_hash(w1) == world_hash(w2)

    def test_content_change_changes_hash(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        before = world_hash(world)
        (world / "level.dat").write_bytes(b"different data")
        assert world_hash(world) != before

    def test_rename_changes_hash(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        before = world_hash(world)
        (world / "level.dat").rename(world / "level2.dat")
        assert world_hash(world) != before

    def test_executable_bit_changes_hash(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        before = world_hash(world)
        target = world / "level.dat"
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        assert world_hash(world) != before

    def test_empty_directory_hashes_consistently(self, tmp_path: Path) -> None:
        world = tmp_path / "world"
        world.mkdir()
        assert world_hash(world) == world_hash(world)

    def test_symlink_file_rejected(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        (world / "evil").symlink_to(world / "level.dat")
        with pytest.raises(ValidationError) as exc_info:
            world_hash(world)
        assert exc_info.value.reason == "world_unsupported_entry"

    def test_symlinked_subdirectory_rejected(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.dat").write_bytes(b"secret")
        (world / "evil_dir").symlink_to(outside)
        with pytest.raises(ValidationError) as exc_info:
            world_hash(world)
        assert exc_info.value.reason == "world_unsupported_entry"

    def test_fifo_rejected(self, tmp_path: Path) -> None:
        world = _make_world(tmp_path)
        fifo_path = world / "a_fifo"
        os.mkfifo(fifo_path)
        with pytest.raises(ValidationError) as exc_info:
            world_hash(world)
        assert exc_info.value.reason == "world_unsupported_entry"
