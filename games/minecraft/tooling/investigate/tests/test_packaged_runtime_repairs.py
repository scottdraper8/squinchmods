"""Real filesystem/Git/subprocess regressions, not Minecraft qualification."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from squinch_minecraft_investigate import owned_operation
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
from squinch_minecraft_investigate.paths import active_path
from squinch_minecraft_investigate.tranche import require_tranche
from test_packaged_runtime import digest, git

pytest_plugins = ["test_packaged_runtime"]


def configuration(spec):
    template = Path(spec["template"]["path"])
    (template / "server.properties").write_text("server-port=25565\n")
    (template / "config").mkdir()
    (template / "config/example.json").write_text(
        '{"url": "https://example.invalid/initial"}'
    )
    spec["template"]["files"] = runtime._tree(template)
    spec["template"]["mutable_files"] = ["server.properties", "config/example.json"]
    return template


def manifest_for(error):
    return json.loads(
        (Path(error.details["artifact_dir"]) / "manifest.json").read_text()
    )


@pytest.mark.parametrize("late", [False, True])
def test_configuration_mutation_records_final_copy_identity_and_preserves_inputs(
    recipe, subprocess_service, monkeypatch, late
):
    spec, _path, save = recipe
    template = configuration(spec)
    original_hashes = runtime._tree(template)
    if late:
        terminate = owned_operation.terminate_owned_service

        def mutate(state, timeout, *, label):
            failures = terminate(state, timeout, label=label)
            (Path(state["run_dir"]) / "server.properties").write_text(
                "#late defaults\nserver-port=25565\n"
            )
            return failures

        monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    else:
        spec["environment"]["SQUINCH_MODE"] = "configuration"
    state = runtime.run_packaged_runtime(save())
    assert state["lifecycle"] == "succeeded"
    assert state["cleanup"]["complete"]
    assert runtime._tree(template) == original_hashes
    expected = {
        name: digest(Path(state["run_dir"]) / name)
        for name in spec["template"]["mutable_files"]
    }
    assert state["mutable_files_after"] == expected
    assert expected["server.properties"] != original_hashes["server.properties"]
    persisted = json.loads((Path(state["artifact_dir"]) / "manifest.json").read_text())
    assert persisted["mutable_files_after"] == expected


@pytest.mark.parametrize(
    "name",
    [
        "launch.args",
        "libraries/game.jar",
        "config/disguised.json",
        "missing.properties",
        "../escape",
        "config",
    ],
)
def test_invalid_mutable_declarations_fail(recipe, name):
    spec, _path, save = recipe
    template = configuration(spec)
    shutil.copyfile(template / "libraries/game.jar", template / "config/disguised.json")
    spec["template"]["files"] = runtime._tree(template)
    spec["template"]["mutable_files"] = [name]
    with pytest.raises(InvestigationError, match="mutable|unsafe relative"):
        runtime.validate_spec(save())


@pytest.mark.parametrize("boundary", ["arguments", "argfile", "manifest"])
def test_configuration_cannot_be_mutable_when_used_as_launch_code(recipe, boundary):
    spec, _path, save = recipe
    template = configuration(spec)
    if boundary == "arguments":
        spec["arguments"] = ["-cp", "config/example.json", "FixtureMain"]
    elif boundary == "argfile":
        spec["arguments"] = ["@config/example.json"]
        (template / "config/example.json").write_text("FixtureMain")
    else:
        with zipfile.ZipFile(template / "launcher.jar", "w") as jar:
            jar.writestr(
                "META-INF/MANIFEST.MF",
                "Manifest-Version: 1.0\nClass-Path: config/example.json\n",
            )
    spec["template"]["files"] = runtime._tree(template)
    with pytest.raises(InvestigationError, match="mutable"):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "name",
    [
        "launch.args",
        "libraries/game.jar",
        "mods/subject.jar",
        "mods/test.jar",
        "server.properties",
    ],
)
def test_late_immutable_changes_are_run_failures_not_cleanup_failures(
    recipe, subprocess_service, monkeypatch, name
):
    spec, _path, save = recipe
    configuration(spec)
    if name == "server.properties":
        spec["template"]["mutable_files"] = []
    terminate = owned_operation.terminate_owned_service

    def mutate(state, timeout, *, label):
        failures = terminate(state, timeout, label=label)
        (Path(state["run_dir"]) / name).write_text("changed late")
        return failures

    monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    with pytest.raises(InvestigationError) as caught:
        runtime.run_packaged_runtime(save())
    assert not isinstance(caught.value, CleanupError)
    assert caught.value.details["cleanup_complete"]
    state = manifest_for(caught.value)
    assert state["lifecycle"] == "failed"
    assert state["post_teardown_failure"]
    assert state["cleanup"] == {"complete": True, "failures": []}
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_data_urls_escaped_text_and_control_values_are_not_launch_recipes(
    recipe, subprocess_service
):
    spec, _path, save = recipe
    template = configuration(spec)
    (template / "attribution.txt").write_text(
        "https://example.invalid/license\n/ordinary/data\nC:\\escaped\\data\n"
    )
    with zipfile.ZipFile(template / "resource-data.zip", "w") as resource:
        resource.writestr(
            "META-INF/MANIFEST.MF", "Class-Path: https://example.invalid/attribution\n"
        )
    spec["template"]["files"] = runtime._tree(template)
    spec["environment"].update(
        SQUINCH_ACQUIRE_URL="https://example.invalid/resources",
        SQUINCH_DESCRIPTION="escaped\\data /not-a-classpath ../not-a-recipe",
    )
    state = runtime.run_packaged_runtime(save())
    assert state["lifecycle"] == "succeeded"
    assert (
        digest(Path(state["run_dir"]) / "attribution.txt")
        == spec["template"]["files"]["attribution.txt"]
    )


@pytest.mark.parametrize(
    "value",
    [
        "/source/build/classes",
        "../source/build/classes",
        "build/classes",
        "libraries/game.jar:/source/build/classes",
    ],
)
@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_real_classpath_boundary_rejects_external_and_development_paths(
    recipe, value, boundary
):
    spec, _path, save = recipe
    template = Path(spec["template"]["path"])
    arguments = ["-cp", value, "FixtureMain"]
    if boundary == "argv":
        spec["arguments"] = arguments
    else:
        (template / "launch.args").write_text(" ".join(arguments))
        spec["template"]["files"] = runtime._tree(template)
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save())


@pytest.mark.parametrize("late_failure", ["fatal", "source", "crash"])
def test_late_diagnostics_and_source_checks_run_after_service_cleanup(
    recipe, subprocess_service, monkeypatch, late_failure
):
    spec, _path, save = recipe
    terminate = owned_operation.terminate_owned_service

    def mutate(state, timeout, *, label):
        failures = terminate(state, timeout, label=label)
        if late_failure == "fatal":
            with Path(state["log_path"]).open("a") as log:
                log.write("[FATAL] late failure\n")
        elif late_failure == "source":
            (Path(spec["project"]) / "source.txt").write_text("late pollution")
        else:
            reports = Path(state["run_dir"]) / "crash-reports"
            reports.mkdir()
            (reports / "report.txt").write_text("late crash")
        return failures

    monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    with pytest.raises(InvestigationError) as caught:
        runtime.run_packaged_runtime(save())
    assert not isinstance(caught.value, CleanupError)
    assert caught.value.details["cleanup_complete"]
    assert manifest_for(caught.value)["post_teardown_failure"]
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_nested_target_hashes_shared_tracked_untracked_and_ignored_source(
    recipe, monkeypatch
):
    spec, _path, save = recipe
    git_root = Path(spec["project"])
    target = git_root / "targets/forge"
    target.mkdir(parents=True)
    (target / "source.txt").write_text("target")
    shared = git_root / "common"
    shared.mkdir()
    (shared / "tracked.txt").write_text("tracked")
    (git_root / ".gitignore").write_text("common/ignored.txt\n")
    git(git_root, "add", ".gitignore", "targets", "common")
    git(
        git_root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "nested source",
    )
    (shared / "untracked.txt").write_text("already untracked")
    (shared / "ignored.txt").write_text("ignored source")
    # Ordinary source directory names are not aliases of repository-specific denied state.
    for name in ("private", "tmp", "reference"):
        (shared / name).mkdir()
        (shared / name / "source.txt").write_text("production source")
    unrelated = git_root / "unrelated"
    unrelated.mkdir()
    spec["project"] = str(target)
    spec["source_roots"] = [str(git_root / "targets"), str(shared)]
    runtime.validate_spec(save())
    original_scandir = runtime.os.scandir

    def scoped_scan(path):
        assert Path(path) != git_root
        assert not Path(path).is_relative_to(unrelated)
        return original_scandir(path)

    monkeypatch.setattr(runtime.os, "scandir", scoped_scan)
    before = runtime._source_snapshot(target, spec["source_roots"])
    assert before["git_root"] == str(git_root)
    assert before["files"]["common/untracked.txt"] == digest(shared / "untracked.txt")
    assert before["files"]["common/ignored.txt"] == digest(shared / "ignored.txt")
    for name in (
        "tracked.txt",
        "untracked.txt",
        "ignored.txt",
        "private/source.txt",
        "tmp/source.txt",
        "reference/source.txt",
    ):
        original = (shared / name).read_bytes()
        (shared / name).write_text("content changed, same status flags")
        after = runtime._source_snapshot(target, spec["source_roots"])
        if name != "tracked.txt":
            assert after["status"] == before["status"]
        assert after["files"] != before["files"]
        (shared / name).write_bytes(original)


def test_shared_untracked_source_pollution_rejects_nested_run(
    recipe, subprocess_service, monkeypatch
):
    spec, _path, save = recipe
    git_root = Path(spec["project"])
    target = git_root / "target"
    target.mkdir()
    (target / "build.txt").write_text("build root")
    shared = git_root / "shared"
    shared.mkdir()
    untracked = shared / "source.txt"
    untracked.write_text("before")
    spec["project"] = str(target)
    spec["source_roots"] = [str(target), str(shared)]
    terminate = owned_operation.terminate_owned_service

    def mutate(state, timeout, *, label):
        failures = terminate(state, timeout, label=label)
        untracked.write_text("after")
        return failures

    monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    with pytest.raises(InvestigationError, match="polluted source") as caught:
        runtime.run_packaged_runtime(save())
    assert caught.value.details["cleanup_complete"]
    state = manifest_for(caught.value)
    assert state["source_before"]["status"] == state["source_after"]["status"]
    assert state["source_before"]["files"] != state["source_after"]["files"]


def test_parent_git_repository_permits_ignored_selected_tranche_inputs(
    recipe, subprocess_service
):
    spec, _path, save = recipe
    _id, workspace = require_tranche()
    parent = workspace.parents[3]
    # A real parent-repository project (not a Git submodule). No production parent scan.
    assert not (parent / ".git").exists()
    git(parent, "init")
    project = parent / "ordinary-source-project"
    project.mkdir()
    source = project / "source.txt"
    source.write_text("production")
    assert not (parent / ".gitignore").exists()
    (parent / ".gitignore").write_text(f"{workspace.relative_to(parent).parts[0]}/\n")
    git(parent, "add", ".gitignore", "ordinary-source-project")
    git(
        parent,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "parent fixture",
    )
    spec["project"] = str(project)
    spec["source_roots"] = [str(project)]
    try:
        state = runtime.run_packaged_runtime(save())
        assert state["lifecycle"] == "succeeded"
        assert state["source_before"]["git_root"] == str(parent)
        assert state["source_before"]["files"] == {
            "ordinary-source-project/source.txt": digest(source)
        }
        # Moving an input into source within this same tranche remains forbidden.
        worktree = workspace / "inputs/source-worktree"
        shutil.copytree(project, worktree)
        git(worktree, "init")
        artifact = worktree / "subject.jar"
        shutil.copyfile(spec["subject"]["path"], artifact)
        spec["subject"]["path"] = str(artifact)
        with pytest.raises(InvestigationError, match="source worktree"):
            runtime.validate_spec(save())
    finally:
        # Only this test's fake Git metadata, never another test/agent's fixtures.
        shutil.rmtree(parent / ".git")
        (parent / ".gitignore").unlink()
        shutil.rmtree(project)


def test_denied_cache_entry_is_filtered_before_stat_or_traversal(recipe, monkeypatch):
    spec, _path, _save = recipe
    project = Path(spec["project"])
    original_scandir = runtime.os.scandir

    class Entries:
        def __enter__(self):
            self.real = original_scandir(project)
            return iter(
                [
                    *self.real,
                    SimpleNamespace(
                        name="__pycache__",
                        stat=lambda **_k: pytest.fail("denied cache stat"),
                    ),
                ]
            )

        def __exit__(self, *args):
            self.real.close()

    def scan(path):
        if Path(path) == project:
            return Entries()
        pytest.fail(f"unexpected source traversal: {path}")

    # A synthetic directory entry, NOT a read/write of any existing denied cache.
    monkeypatch.setattr(runtime.os, "scandir", scan)
    snapshot = runtime._source_snapshot(project, spec["source_roots"])
    assert snapshot["files"] == {
        "source.txt": hashlib.sha256(b"original\n").hexdigest()
    }


@pytest.mark.parametrize("field", ["source_roots", "mutable_files"])
def test_explicit_boundary_arrays_are_required(recipe, field):
    spec, _path, save = recipe
    if field == "source_roots":
        del spec[field]
    else:
        del spec["template"][field]
    with pytest.raises(InvestigationError, match="required property"):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "kind", ["outside-git", "scratch", "overlap", "uncovered-project", "other-tranche"]
)
def test_invalid_source_boundaries_rejected_before_snapshot(recipe, tmp_path, kind):
    spec, path, save = recipe
    project = Path(spec["project"])
    _id, workspace = require_tranche()
    if kind == "outside-git":
        spec["source_roots"] = [str(tmp_path)]
    elif kind == "scratch":
        spec["source_roots"] = [str(path.parent)]
    elif kind == "overlap":
        child = project / "child"
        child.mkdir()
        spec["source_roots"] = [str(project), str(child)]
    elif kind == "uncovered-project":
        target = project / "target"
        target.mkdir()
        sibling = project / "sibling"
        sibling.mkdir()
        spec["project"] = str(target)
        spec["source_roots"] = [str(sibling)]
    else:
        spec["source_roots"] = [str(workspace.parent / "other-source-tranche")]
    with pytest.raises(InvestigationError, match="source root"):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "arguments",
    [
        ["-cp", "mods/*", "FixtureMain"],
        ["-Djava.class.path=mods/test.jar", "FixtureMain"],
        ["--patch-module", "fixture=mods/test.jar", "FixtureMain"],
    ],
)
def test_explicit_staged_artifacts_are_valid_launch_paths(recipe, arguments):
    spec, _path, save = recipe
    spec["arguments"] = arguments
    runtime.validate_spec(save())


@pytest.mark.parametrize(
    "arguments",
    [
        ["-Djava.class.path=config/example.json", "FixtureMain"],
        ["-Djava.library.path=config", "FixtureMain"],
        ["--patch-module", "fixture=config/example.json", "FixtureMain"],
        ["-javaagent:config/example.json", "FixtureMain"],
    ],
)
def test_typed_launch_paths_cannot_be_mutable_configuration(recipe, arguments):
    spec, _path, save = recipe
    configuration(spec)
    spec["arguments"] = arguments
    with pytest.raises(InvestigationError, match="mutable"):
        runtime.validate_spec(save())


def test_referenced_archive_manifests_checked_independent_of_template_order(recipe):
    spec, _path, save = recipe
    template = Path(spec["template"]["path"])
    with zipfile.ZipFile(template / "libraries/referenced.zip", "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Class-Path: /source/build/classes\n")
    with zipfile.ZipFile(template / "libraries/game.jar", "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Class-Path: referenced.zip\n")
    files = runtime._tree(template)
    spec["template"]["files"] = {
        "libraries/referenced.zip": files.pop("libraries/referenced.zip"),
        **files,
    }
    with pytest.raises(InvestigationError, match="references"):
        runtime.validate_spec(save())
