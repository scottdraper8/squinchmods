from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import write_save_pair

from squinch_nms_save.codec import decode_file
from squinch_nms_save.errors import SaveToolError
from squinch_nms_save.jsonops import resolve
from squinch_nms_save.meta import summarize_meta_file
from squinch_nms_save.stage import (
    apply_stage,
    apply_stage_batch,
    create_stage,
    sha256_file,
    verify_stage,
)


def test_stage_is_verified_and_does_not_touch_source(
    save_pair: tuple[Path, Path], patch_file: Path, tranche: Path
) -> None:
    save, meta = save_pair
    before = (sha256_file(save), sha256_file(meta))

    result = create_stage(save, patch_file, timestamp=1_800_000_000)
    verification = verify_stage(Path(result["stage"]))

    assert verification["valid"]
    assert verification["source_current"]
    assert (sha256_file(save), sha256_file(meta)) == before
    staged = decode_file(Path(result["stage"]) / save.name)
    assert resolve(staged.document, "/nested/count") == 8
    assert resolve(staged.document, "/items/2") == "gamma"


def test_stage_can_update_metadata_save_name(
    save_pair: tuple[Path, Path], patch_file: Path, tranche: Path
) -> None:
    save, _meta = save_pair
    result = create_stage(
        save,
        patch_file,
        timestamp=1_800_000_000,
        metadata_save_name="Galaxies 51-100",
    )
    stage = Path(result["stage"])

    assert summarize_meta_file(stage / f"mf_{save.name}", save).save_name == ("Galaxies 51-100")
    assert json.loads((stage / "manifest.json").read_text())["metadata_save_name"] == (
        "Galaxies 51-100"
    )


def test_stage_rejects_stale_source(
    save_pair: tuple[Path, Path], patch_file: Path, tranche: Path
) -> None:
    save, _ = save_pair
    result = create_stage(save, patch_file)
    save.write_bytes(save.read_bytes() + b"changed")

    with pytest.raises(SaveToolError, match="source pair changed"):
        verify_stage(Path(result["stage"]))


def test_stage_requires_patch_inside_tranche(
    save_pair: tuple[Path, Path], tmp_path: Path, tranche: Path
) -> None:
    save, _ = save_pair
    patch = tmp_path / "outside.json"
    patch.write_text("[]")

    with pytest.raises(SaveToolError, match="patch must be inside the selected tranche"):
        create_stage(save, patch)


def test_apply_requires_flag_and_creates_verified_backup(
    save_pair: tuple[Path, Path], patch_file: Path, tranche: Path
) -> None:
    save, meta = save_pair
    original = (sha256_file(save), sha256_file(meta))
    result = create_stage(save, patch_file, timestamp=1_800_000_000)
    stage = Path(result["stage"])

    with pytest.raises(SaveToolError, match="explicit --apply"):
        apply_stage(stage, apply=False)

    applied = apply_stage(stage, apply=True)
    backup = Path(applied["backup"])
    assert applied["applied"]
    assert (sha256_file(backup / save.name), sha256_file(backup / meta.name)) == original
    assert resolve(decode_file(save).document, "/nested/count") == 8
    assert json.loads((backup / "manifest.json").read_text())["schema"] == (
        "squinch-nms-save-backup-v1"
    )


def test_stage_supports_older_wrapper_inside_714_ceiling(
    tmp_path: Path, patch_file: Path, tranche: Path
) -> None:
    save, _meta = write_save_pair(
        tmp_path / "profile",
        meta_format=2003,
        base_version=4148,
        meta_size=384,
        store_compressed_size=False,
    )

    result = create_stage(save, patch_file, timestamp=1_800_000_000)
    verification = verify_stage(Path(result["stage"]))

    assert verification["valid"] is True
    assert verification["meta_format"] == 2003
    assert verification["base_version"] == 4148
    assert verification["size_mode"] == "decoded"


def test_stage_preserves_compressed_metadata_size_mode(
    tmp_path: Path, patch_file: Path, tranche: Path
) -> None:
    save, _meta = write_save_pair(
        tmp_path / "profile",
        meta_format=2004,
        base_version=4148,
        meta_size=384,
        size_mode="compressed",
    )

    result = create_stage(save, patch_file, timestamp=1_800_000_000)
    verification = verify_stage(Path(result["stage"]))

    assert verification["valid"] is True
    assert verification["size_mode"] == "compressed"


def test_batch_apply_backs_up_all_pairs_before_replacement(
    tmp_path: Path, patch_file: Path, tranche: Path
) -> None:
    profile = tmp_path / "profile"
    save1, _meta1 = write_save_pair(profile, name="save.hg")
    save2, _meta2 = write_save_pair(profile, name="save2.hg")
    stage1 = Path(create_stage(save1, patch_file)["stage"])
    stage2 = Path(create_stage(save2, patch_file)["stage"])

    with pytest.raises(SaveToolError, match="explicit --apply"):
        apply_stage_batch([stage1, stage2], apply=False)
    result = apply_stage_batch([stage1, stage2], apply=True)

    assert result["count"] == 2
    assert resolve(decode_file(save1).document, "/nested/count") == 8
    assert resolve(decode_file(save2).document, "/nested/count") == 8
    manifest = json.loads((Path(result["backup"]) / "manifest.json").read_text())
    assert manifest["schema"] == "squinch-nms-save-batch-backup-v1"
    assert len(manifest["entries"]) == 2
