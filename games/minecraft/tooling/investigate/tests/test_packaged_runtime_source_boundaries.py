"""Source provenance regressions against the real filesystem and Git, not Minecraft."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from test_packaged_runtime import git

pytest_plugins = ["test_packaged_runtime"]


@pytest.mark.parametrize(
    "name",
    [
        "tools/build/build-runtime.py",
        "tools/run/runtime-builder.py",
        "gradle/wrapper/gradle-wrapper.jar",
        "fixtures/input.class",
        "fixtures/expected.log",
    ],
)
def test_declared_tracked_build_inputs_are_not_guessed_to_be_output(recipe, name):
    spec, _path, _save = recipe
    project = Path(spec["project"])
    source = project / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"original fixture input\n")
    git(project, "add", name)
    git(
        project,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "tracked build input",
    )
    before = runtime._source_snapshot(project, spec["source_roots"])
    assert name in before["files"]
    source.write_bytes(b"changed fixture input\n")
    after = runtime._source_snapshot(project, spec["source_roots"])
    assert after["files"] != before["files"]
    assert after["status"] != before["status"]
    source.write_bytes(b"another change, still dirty\n")
    still_dirty = runtime._source_snapshot(project, spec["source_roots"])
    assert still_dirty["status"] == after["status"]
    assert still_dirty["files"] != after["files"]


def test_unexpected_binary_source_output_is_detected_without_status_flags(recipe):
    spec, _path, _save = recipe
    project = Path(spec["project"])
    before = runtime._source_snapshot(project, spec["source_roots"])
    (project / "unexpected.jar").write_bytes(b"unexpected runtime output")
    after = runtime._source_snapshot(project, spec["source_roots"])
    assert (
        after["status"] == before["status"]
    )  # Scoped porcelain excludes untracked discovery.
    assert after["files"] != before["files"]
    assert "unexpected.jar" in after["files"]


@pytest.mark.parametrize(
    "name",
    [
        "build/classes/Foo.class",
        "run/output.jar",
        "case/Foo.class",
        "case/result.jar",
        "case/latest.log",
        "case/latest.log.gz",
    ],
)
def test_former_investigation_output_exclusions_stay_scoped(name):
    # Pure lexical checks: do not create/read anything in a restricted tree.
    assert runtime._source_excluded(runtime._SOURCE_INVESTIGATIONS / name)
    assert not runtime._source_excluded(Path("/ordinary/source") / name)


@pytest.mark.parametrize(
    "name",
    [
        ".vscode",
        ".directory",
        ".DS_Store",
        "Desktop.ini",
        "ehthumbs.db",
        "Thumbs.db",
        "extension.pyd",
    ],
)
def test_runtime_denied_entries_are_rejected_before_stat(tmp_path, monkeypatch, name):
    class Entries:
        def __enter__(self):
            return iter(
                [
                    SimpleNamespace(
                        name=name,
                        path=str(tmp_path / name),
                        stat=lambda **_kwargs: pytest.fail(
                            "denied entry was inspected"
                        ),
                    )
                ]
            )

        def __exit__(self, *args):
            return None

    # Only synthetic directory entries; no denied fixture path is materialized.
    monkeypatch.setattr(runtime.os, "scandir", lambda _path: Entries())
    with pytest.raises(InvestigationError, match="source/cache state"):
        runtime._tree(tmp_path)
    assert runtime._source_excluded(tmp_path / name)
