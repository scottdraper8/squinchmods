from __future__ import annotations

from pathlib import Path

import pytest

from squinch_qa.errors import ReplaceError
from squinch_qa.replace._pathsafe import assert_within
from squinch_qa.replace.layout import (
    assert_same_device,
    current_job_dir,
    incoming_job_dir,
    matrix_id_safe,
    path_id_safe,
    staging_job_dir,
    trash_job_dir,
)


class TestPathSafe:
    def test_direct_child_is_within(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        child = root / "a" / "b"
        child.mkdir(parents=True)
        assert assert_within(root, child) == child.resolve()

    def test_root_itself_is_within(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        assert assert_within(root, root) == root.resolve()

    def test_dotdot_escape_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(ReplaceError) as exc_info:
            assert_within(root, root / ".." / "outside")
        assert exc_info.value.reason == "path_escape"

    def test_absolute_escape_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(ReplaceError) as exc_info:
            assert_within(root, outside)
        assert exc_info.value.reason == "path_escape"

    def test_symlink_escape_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = root / "link"
        link.symlink_to(outside)
        with pytest.raises(ReplaceError) as exc_info:
            assert_within(root, link)
        assert exc_info.value.reason == "path_escape"


class TestMatrixIdSafe:
    def test_encoding(self) -> None:
        assert matrix_id_safe("neoforge-1.21.1", "pregen") == "neoforge-1.21.1__pregen"

    def test_layout_helpers_use_state_first_identity_path(self, tmp_path: Path) -> None:
        assert (
            incoming_job_dir(tmp_path, "m", "t", "x")
            == tmp_path / "incoming" / "m" / "t" / "x"
        )
        assert (
            staging_job_dir(tmp_path, "m", "t", "x")
            == tmp_path / "staging" / "m" / "t" / "x"
        )
        assert (
            current_job_dir(tmp_path, "m", "t", "x")
            == tmp_path / "current" / "m" / "t" / "x"
        )

    def test_trash_job_dir_is_nested_by_identity(self, tmp_path: Path) -> None:
        dest = trash_job_dir(tmp_path, "m", "t", "x", "run-1")
        assert dest.parent == tmp_path / "trash" / "m" / "t" / "x"
        assert dest.name.endswith("-run-1")

    def test_trash_job_dir_distinct_run_ids_differ(self, tmp_path: Path) -> None:
        a = trash_job_dir(tmp_path, "m", "t", "x", "run-1")
        b = trash_job_dir(tmp_path, "m", "t", "x", "run-2")
        assert a != b

    @pytest.mark.parametrize(
        "field,bad_id",
        [
            (field, bad_id)
            for field in ("target_id", "test_id")
            for bad_id in ["../evil", "a/b", "a\\b", "..", "."]
        ],
    )
    def test_rejects_unsafe_id(self, field: str, bad_id: str) -> None:
        args = {"target_id": "neoforge-1.21.1", "test_id": "pregen"}
        args[field] = bad_id
        with pytest.raises(ReplaceError) as exc_info:
            matrix_id_safe(args["target_id"], args["test_id"])
        assert exc_info.value.reason == "unsafe_matrix_id"

    def test_job_dir_helpers_reject_unsafe_ids(self, tmp_path: Path) -> None:
        with pytest.raises(ReplaceError):
            incoming_job_dir(tmp_path, "../escape", "target", "pregen")

    @pytest.mark.parametrize("bad_id", ["../evil", "a/b", "a\\b", "..", "."])
    def test_path_id_safe_rejects_unsafe_mod_id(self, bad_id: str) -> None:
        with pytest.raises(ReplaceError) as exc_info:
            path_id_safe(bad_id, "mod_id")
        assert exc_info.value.reason == "unsafe_storage_id"


class TestAssertSameDevice:
    def test_same_device_passes(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        assert_same_device(a, b)  # no raise

    def test_nonexistent_path_walks_to_ancestor(self, tmp_path: Path) -> None:
        a = tmp_path / "a" / "b" / "c"  # doesn't exist yet
        assert_same_device(tmp_path, a)  # no raise; walks up to tmp_path

    def test_cross_device_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from squinch_qa.replace import layout as layout_mod

        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()

        real_stat_dev = layout_mod._stat_dev

        def fake_stat_dev(path: Path) -> int:
            return 1 if path == a else 2 if path == b else real_stat_dev(path)

        monkeypatch.setattr(layout_mod, "_stat_dev", fake_stat_dev)
        with pytest.raises(ReplaceError) as exc_info:
            assert_same_device(a, b)
        assert exc_info.value.reason == "cross_device"
