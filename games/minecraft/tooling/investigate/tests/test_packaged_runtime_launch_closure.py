"""Original synthetic launch recipes; no Minecraft or loader qualification."""

from __future__ import annotations

import json
import shlex
import zipfile
from pathlib import Path

import pytest
from squinch_minecraft_investigate import owned_operation
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.paths import active_path
from test_packaged_runtime import digest

pytest_plugins = ["test_packaged_runtime"]


def file(spec, name, text="fixture"):
    target = Path(spec["template"]["path"]) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def archive(spec, location, references):
    if location == "subject":
        item = spec["subject"]
        target = Path(item["path"])
    elif location == "companion":
        item = spec["companions"][0]
        target = Path(item["path"])
    else:
        item = None
        target = file(spec, location)
    with zipfile.ZipFile(target, "w") as jar:
        jar.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\r\nClass-Path: " + references + "\r\n\r\n",
        )
    if item:
        item["sha256"] = digest(target)
    return target


def save_template(spec, save):
    spec["template"]["files"] = runtime._tree(Path(spec["template"]["path"]))
    return save()


def arguments(spec, text, boundary):
    if boundary == "argv":
        spec["arguments"] = [text, "-cp", "libraries/game.jar", "FixtureMain"]
    else:
        file(spec, "launch.args", f"{text}\n-cp libraries/game.jar FixtureMain\n")


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize("input", ["missing", "present", "mutable", "premain-home"])
def test_vm_options_file_is_rejected_before_launch(
    recipe, subprocess_service, boundary, input
):
    spec, _path, save = recipe
    if input != "missing":
        text = "-Xmx64m\n"
        if input == "premain-home":
            # Same real JVM boundary as the observed premain/owned-home bypass.
            text = f"-javaagent:{spec['project']}/external-agent.jar\n-Duser.home=/external\n"
        file(spec, "config/jvm.cfg", text)
    if input == "mutable":
        spec["template"]["mutable_files"] = ["config/jvm.cfg"]
    arguments(spec, "-XX:VMOptionsFile=config/jvm.cfg", boundary)
    source_before = runtime._source_snapshot(
        Path(spec["project"]), spec["source_roots"]
    )
    with pytest.raises(
        InvestigationError, match=r"VMOptionsFile is unsupported.*@argument-file"
    ):
        runtime.run_packaged_runtime(save_template(spec, save))
    assert (
        not subprocess_service
    )  # No invented exit/cleanup record for a rejected spec.
    assert (
        runtime._source_snapshot(Path(spec["project"]), spec["source_roots"])
        == source_before
    )
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


@pytest.mark.parametrize("property", ["legacyClassPath", "libraryDirectory"])
@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_known_loader_paths_require_packaged_existence(recipe, property, boundary):
    spec, _path, save = recipe
    arguments(spec, f"-D{property}=not-in-the-template", boundary)
    with pytest.raises(InvestigationError, match="not a packaged input"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("property", ["legacyClassPath", "libraryDirectory"])
@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_loader_paths_are_immutable_even_when_named_config(recipe, property, boundary):
    spec, _path, save = recipe
    file(spec, "config/boot.cfg", "-Xmx64m\n")
    spec["template"]["mutable_files"] = ["config/boot.cfg"]
    value = "config" if property == "libraryDirectory" else "config/boot.cfg"
    arguments(spec, f"-D{property}={value}", boundary)
    with pytest.raises(InvestigationError, match="mutable"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "argument",
    [
        "-DlegacyClassPath=mods/subject.jar:mods/test.jar:libraries/game.jar",
        "-DlegacyClassPath=libraries",
        "-DlibraryDirectory=libraries",
    ],
)
@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_packaged_loader_path_forms_are_supported(recipe, argument, boundary):
    spec, _path, save = recipe
    arguments(spec, argument, boundary)
    runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "argument",
    [
        "-DlegacyClassPath=mods/test.jar:",
        "-DlegacyClassPath=:mods/test.jar",
        "-DlegacyClassPath=mods/*",
        "-DlegacyClassPath",
        "-DlibraryDirectory=mods/test.jar",
        "-DlibraryDirectory=libraries:config",
        "-DlibraryDirectory=libraries/*",
        "-DlibraryDirectory",
        "-DlibraryDirectory=",
    ],
)
def test_unsupported_loader_path_forms_fail_closed(recipe, argument):
    spec, _path, save = recipe
    arguments(spec, argument, "argv")
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("location", ["libraries/game.jar", "subject", "companion"])
def test_every_archive_root_rejects_missing_manifest_edges(recipe, location):
    spec, _path, save = recipe
    archive(spec, location, "generated-at-runtime.jar")
    with pytest.raises(
        InvestigationError, match="manifest launch dependency is not a packaged input"
    ):
        runtime.validate_spec(save_template(spec, save))


def test_combined_namespace_closure_is_archive_relative_transitive_and_cycle_safe(
    recipe,
):
    spec, _path, save = recipe
    # Template -> staged subject -> staged companion -> non-JAR archive -> template.
    archive(spec, "libraries/game.jar", "../mods/subject.jar")
    archive(spec, "subject", "./test.jar")
    archive(spec, "companion", "../libraries/dependency.dat")
    archive(spec, "libraries/dependency.dat", "./game.jar ../classes/")
    file(spec, "classes/pinned.txt")
    runtime.validate_spec(save_template(spec, save))
    files, directories = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert {
        "libraries/game.jar",
        "mods/subject.jar",
        "mods/test.jar",
        "libraries/dependency.dat",
        "classes/pinned.txt",
    } <= files
    assert "classes" in directories
    # Missing transitive edge may not be silently ignored, including cycles.
    archive(spec, "libraries/dependency.dat", "game.jar absent.jar")
    with pytest.raises(InvestigationError, match="absent.jar"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("entry", ["subject", "companion", "libraries/game.jar"])
def test_missing_transitive_edge_through_non_jar_archive_rejected(recipe, entry):
    spec, _path, save = recipe
    prefix = "../libraries/" if entry in {"subject", "companion"} else ""
    archive(spec, entry, prefix + "not-a-jar.dat")
    archive(spec, "libraries/not-a-jar.dat", "missing.dat")
    with pytest.raises(InvestigationError, match="missing.dat"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "reference",
    [
        "../../escape.jar",
        "/source/escape.jar",
        "file:external.jar",
        "https://example.invalid/x",
        "../libraries/missing/",
        "../classes",
        "../libraries/%67ame.jar",
        "../libraries/game.jar?query",
    ],
)
def test_manifest_missing_unsafe_or_unsupported_paths_rejected(recipe, reference):
    spec, _path, save = recipe
    archive(spec, "subject", reference)
    file(spec, "classes/pinned.txt")
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save_template(spec, save))


def test_manifest_folded_main_attributes_not_named_entry_prose(recipe):
    spec, _path, save = recipe
    target = Path(spec["subject"]["path"])
    with zipfile.ZipFile(target, "w") as jar:
        jar.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\r\ncLaSs-PaTh: ../libraries/ga\r\n me.jar\r\n\r\n"
            "Name: resource.txt\r\nClass-Path: https://example.invalid/data\r\n\r\n",
        )
    spec["subject"]["sha256"] = digest(target)
    runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "edge", ["manifest", "classpath", "legacyClassPath", "libraryDirectory"]
)
def test_referenced_non_jar_config_archives_are_immutable(recipe, edge):
    spec, _path, save = recipe
    archive(spec, "config/dependency.cfg", "../libraries/game.jar")
    spec["template"]["mutable_files"] = ["config/dependency.cfg"]
    if edge == "manifest":
        archive(spec, "subject", "../config/dependency.cfg")
    else:
        flag = {
            "classpath": "--class-path=config/dependency.cfg",
            "legacyClassPath": "-DlegacyClassPath=config/dependency.cfg",
            "libraryDirectory": "-DlibraryDirectory=config",
        }[edge]
        arguments(spec, flag, "argv")
    with pytest.raises(InvestigationError, match="mutable"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "edge", ["manifest", "classpath", "legacyClassPath", "libraryDirectory"]
)
def test_directories_do_not_promote_unreferenced_data_zips_to_recipes(recipe, edge):
    spec, _path, save = recipe
    archive(spec, "data/resource.zip", "https://example.invalid/attribution")
    if edge == "manifest":
        archive(spec, "subject", "../data/")
    else:
        flag = {
            "classpath": "--class-path=data",
            "legacyClassPath": "-DlegacyClassPath=data",
            "libraryDirectory": "-DlibraryDirectory=data",
        }[edge]
        arguments(spec, flag, "argv")
    runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "edge", ["manifest", "classpath", "legacyClassPath", "libraryDirectory"]
)
def test_launch_directories_cannot_acquire_unmanifested_files_after_launch(
    recipe, subprocess_service, monkeypatch, edge
):
    spec, _path, save = recipe
    file(spec, "config/pinned.cfg")
    if edge == "manifest":
        archive(spec, "companion", "../config/")
    else:
        flag = {
            "classpath": "--class-path=config",
            "legacyClassPath": "-DlegacyClassPath=config",
            "libraryDirectory": "-DlibraryDirectory=config",
        }[edge]
        arguments(spec, flag, "argv")
    terminate = owned_operation.terminate_owned_service

    def mutate(state, timeout, *, label):
        failures = terminate(state, timeout, label=label)
        (Path(state["run_dir"]) / "config/generated.dat").write_text("late code input")
        return failures

    monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    with pytest.raises(
        InvestigationError, match="unmanifested file in a launch directory"
    ) as caught:
        runtime.run_packaged_runtime(save_template(spec, save))
    assert caught.value.details["cleanup_complete"]
    state = json.loads(
        (Path(caught.value.details["artifact_dir"]) / "manifest.json").read_text()
    )
    assert state["post_teardown_failure"]
    assert state["cleanup"] == {"complete": True, "failures": []}
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_application_and_unrelated_property_data_are_not_recipes(recipe, boundary):
    spec, _path, save = recipe
    prose = "https://example.invalid/data /ordinary/path ../data -XX:VMOptionsFile=not-a-recipe"
    tokens = [
        "-Ddescription=" + prose,
        "-cp",
        "mods/test.jar",
        "FixtureMain",
        "-XX:VMOptionsFile=not-a-recipe",
        "-DlibraryDirectory=not-a-path",
        prose,
    ]
    if boundary == "argv":
        spec["arguments"] = tokens
    else:
        file(spec, "launch.args", shlex.join(tokens))
    spec["environment"]["SQUINCH_DESCRIPTION"] = prose
    file(spec, "config/data.cfg", "-XX:VMOptionsFile=/not-a-recipe\n" + prose)
    spec["template"]["mutable_files"] = ["config/data.cfg"]
    runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "entrypoint",
    [
        ["-jar", "libraries/game.jar"],
        ["--module", "fixture/main"],
        ["--module=fixture/main"],
    ],
)
def test_application_option_looking_data_after_jar_or_module_is_opaque(
    recipe, entrypoint
):
    spec, _path, save = recipe
    spec["arguments"] = [
        *entrypoint,
        "-XX:VMOptionsFile=application-data",
        "-Duser.home=application-data",
    ]
    runtime.validate_spec(save())


@pytest.mark.parametrize(
    "option",
    [
        "--add-opens",
        "--add-exports",
        "--add-reads",
        "--add-modules",
        "--limit-modules",
        "--enable-native-access",
    ],
)
def test_non_path_option_operand_does_not_hide_following_jvm_recipe(recipe, option):
    spec, _path, save = recipe
    spec["arguments"] = [
        option,
        "fixture",
        "-XX:VMOptionsFile=config/jvm.cfg",
        "FixtureMain",
    ]
    with pytest.raises(InvestigationError, match="VMOptionsFile is unsupported"):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "option",
    [
        "--class-path=libraries/recipe.dat",
        "--module-path=libraries/recipe.dat",
        "--upgrade-module-path=libraries/recipe.dat",
        "--patch-module=fixture=libraries/recipe.dat",
        "-jar=libraries/recipe.dat",
        "-javaagent:libraries/recipe.dat=opaque-options",
        "-agentpath:libraries/recipe.dat=opaque-options",
        "-Xbootclasspath/a:libraries/recipe.dat",
        "-DlegacyClassPath=libraries/recipe.dat",
    ],
)
def test_already_supported_file_references_close_non_jar_manifest_edges(recipe, option):
    spec, _path, save = recipe
    archive(spec, "libraries/recipe.dat", "missing.jar")
    arguments(spec, option, "argv")
    with pytest.raises(InvestigationError, match="missing.jar"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "text",
    [
        "'unterminated",
        "'multi\nline'",
        "FixtureMain\f-XX:VMOptionsFile=x",
        r"-XX:VMOptionsFile=config\jvm.cfg",
    ],
)
def test_unsupported_argument_file_grammar_is_actionably_rejected(recipe, text):
    spec, _path, save = recipe
    file(spec, "launch.args", text)
    with pytest.raises(InvestigationError, match="unsupported argument file"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "prefix", ["# full-line comment\n", "  # comment\n", "-Ddescription=x# inline "]
)
def test_argument_file_comments_cannot_hide_jvm_recipes(recipe, prefix):
    spec, _path, save = recipe
    file(
        spec,
        "launch.args",
        prefix
        + "-XX:VMOptionsFile=config/jvm.cfg\n-cp libraries/game.jar FixtureMain\n",
    )
    with pytest.raises(
        InvestigationError, match="VMOptionsFile is unsupported|whole-line # comments"
    ):
        runtime.validate_spec(save_template(spec, save))


def test_whole_line_argument_comments_and_quoted_data_are_supported(recipe):
    spec, _path, save = recipe
    file(
        spec,
        "launch.args",
        "# -XX:VMOptionsFile=only-a-comment\n-Ddescription='data with spaces'\n-cp libraries/game.jar FixtureMain\n",
    )
    runtime.validate_spec(save_template(spec, save))


def test_transitive_plain_config_launch_input_cannot_be_mutable(recipe):
    spec, _path, save = recipe
    archive(spec, "companion", "../libraries/recipe.dat")
    archive(spec, "libraries/recipe.dat", "../config/dependency.cfg")
    file(spec, "config/dependency.cfg")
    spec["template"]["mutable_files"] = ["config/dependency.cfg"]
    with pytest.raises(InvestigationError, match="mutable"):
        runtime.validate_spec(save_template(spec, save))
