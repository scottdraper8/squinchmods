"""Regression proposal: alias spelling must not erase actual archive roles."""

from pathlib import Path

import pytest
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from test_packaged_runtime_archive_recipes import manifest
from test_packaged_runtime_jvm_recipes import arguments
from test_packaged_runtime_launch_closure import file, save_template

pytest_plugins = ["test_packaged_runtime"]


def alias(name, spelling):
    if spelling == "leading":
        return "./" + name
    if spelling == "repeated":
        return "././" + name
    return name.replace("/", "/./", 1) if "/" in name else "./" + name


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize("role", ["executable", "javaagent"])
@pytest.mark.parametrize(
    "location",
    ["subject", "companion", "libraries/game.jar", "libraries/main.dat", "root.jar"],
)
@pytest.mark.parametrize("spelling", ["leading", "repeated", "interior"])
def test_alias_cannot_hide_an_actually_invoked_archive_role(
    recipe, boundary, role, location, spelling
):
    spec, _path, save = recipe
    name = manifest(
        spec,
        location,
        "Manifest-Version: 1.0\nMain-Class: FixtureMain\n"
        "Launcher-Agent-Class: Agent\nPremain-Class: Agent\n"
        "Boot-Class-Path: /source/external.jar\n\n",
    )
    operand = alias(name, spelling)
    argv = (
        ["-jar", operand]
        if role == "executable"
        else ["-javaagent:" + operand, "FixtureMain"]
    )
    arguments(spec, argv, boundary)
    # Either an actionable lexical rejection or correct canonical role binding is safe.
    with pytest.raises(
        InvestigationError,
        match="unsafe relative filename|Launcher-Agent-Class.*unsupported|agent Boot-Class-Path.*unsupported",
    ):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "value", ["./data", "dir/./data", "././data", "../external-data"]
)
def test_application_and_uninvoked_manifest_alias_prose_remains_data(
    recipe, boundary, value
):
    spec, _path, save = recipe
    name = manifest(
        spec,
        "libraries/uninvoked.jar",
        "Manifest-Version: 1.0\nLauncher-Agent-Class: Agent\n"
        f"Boot-Class-Path: {value}\n\n",
    )
    file(spec, "config/prose.txt", value)
    arguments(spec, ["-cp", name, "FixtureMain", value], boundary)
    runtime.validate_spec(save_template(spec, save))
    launch_files, _dirs = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert name in launch_files
    assert "config/prose.txt" not in launch_files
