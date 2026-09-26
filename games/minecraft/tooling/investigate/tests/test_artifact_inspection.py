from __future__ import annotations

import zipfile

from squinch_minecraft_investigate.artifact_inspection import inspect_artifact
from squinch_minecraft_investigate.cli import main


def _jar(path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_clean_production_jar_passes(tmp_path) -> None:
    """Catches an overbroad contamination rule that rejects unrelated production bytecode."""
    artifact = tmp_path / "production.jar"
    _jar(artifact, {"example/Production.class": b"production bytecode"})

    result = inspect_artifact(artifact)

    assert result["clean"] is True
    assert result["findings"] == []
    assert len(result["sha256"]) == 64


def test_injected_probe_jar_is_rejected_by_public_command(tmp_path, capsys) -> None:
    """Catches packaged development classes, sentinel, or Mixin metadata escaping inspection."""
    artifact = tmp_path / "contaminated.jar"
    _jar(
        artifact,
        {
            "META-INF/squinch-development-probe": b"SQUINCH_DEVELOPMENT_PROBE\n",
            "org/squinchmods/investigate/RuntimeDispatcher.class": b"probe bytecode",
            "fabric.mod.json": b'{"mixins":["squinch-investigate.mixins.json"]}',
            "squinch-investigate.mixins.json": b"{}",
        },
    )

    exit_code = main(["inspect-artifact", str(artifact), "--json"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert '"state": "failed"' in output
    assert '"clean": false' in output
    assert "development-probe-sentinel" in output
    assert "probe-class" in output
    assert "probe-mixin" in output
