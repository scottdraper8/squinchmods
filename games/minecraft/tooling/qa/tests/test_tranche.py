from __future__ import annotations

from pathlib import Path

import pytest
from squinch_qa.errors import ConfigError
from squinch_qa.tranche import prepare_owned_directory


def test_owned_output_rejects_symlink_escape(
    selected_tranche: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (selected_tranche / "minecraft").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ConfigError, match="output directory is unsafe"):
        prepare_owned_directory("minecraft", "qa")
    assert not (outside / "qa").exists()
