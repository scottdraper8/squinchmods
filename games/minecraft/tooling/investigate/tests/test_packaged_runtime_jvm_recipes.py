"""Known JVM recipe boundaries; fixture labels never establish game qualification."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import zipfile
from pathlib import Path

import pytest
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.paths import active_path
from test_packaged_runtime import digest
from test_packaged_runtime_launch_closure import file, save_template

pytest_plugins = ["test_packaged_runtime"]


def arguments(spec, tokens, boundary):
    if boundary == "argv":
        spec["arguments"] = tokens
    else:
        file(spec, "launch.args", shlex.join(tokens) + "\n")


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "facility", ["-XX:Flags", "-Djava.ext.dirs", "-Djava.endorsed.dirs"]
)
@pytest.mark.parametrize("form", ["missing", "mutable", "source", "bare", "empty"])
def test_optional_legacy_and_flags_recipes_reject_before_allocation(
    recipe, subprocess_service, facility, boundary, form
):
    spec, _path, save = recipe
    value = "not-packaged"
    if form == "mutable":
        file(spec, "config/flags.cfg", "MaxHeapSize=100663296\n")
        spec["template"]["mutable_files"] = ["config/flags.cfg"]
        value = "config/flags.cfg" if facility == "-XX:Flags" else "config"
    elif form == "source":
        value = str(Path(spec["project"]) / "external")
        Path(value).write_text("MaxHeapSize=100663296\n")
    token = (
        facility
        if form == "bare"
        else facility + "=" + ("" if form == "empty" else value)
    )
    arguments(spec, [token, "-cp", "mods/test.jar", "FixtureMain"], boundary)
    before = runtime._source_snapshot(Path(spec["project"]), spec["source_roots"])
    runs = set(runtime.RUNS_ROOT.iterdir())
    with pytest.raises(
        InvestigationError, match="is unsupported.*(?:explicit|packaged)"
    ):
        runtime.run_packaged_runtime(save_template(spec, save))
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == runs
    assert (
        runtime._source_snapshot(Path(spec["project"]), spec["source_roots"]) == before
    )
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "property",
    ["java.home", "sun.boot.class.path", "sun.boot.library.path"],
)
def test_selected_installation_paths_cannot_be_overridden(recipe, boundary, property):
    spec, _path, save = recipe
    arguments(spec, [f"-D{property}=/external", "FixtureMain"], boundary)
    with pytest.raises(InvestigationError, match="unsupported|owned Java directories"):
        runtime.validate_spec(save_template(spec, save))


def agent_manifest(spec, location, boot, *, classpath="", named=False):
    if location == "subject":
        item = spec["subject"]
        target = Path(item["path"])
        name = "mods/subject.jar"
    elif location == "companion":
        item = spec["companions"][0]
        target = Path(item["path"])
        name = "mods/test.jar"
    else:
        item = None
        name = location
        target = file(spec, name)
    main = "Manifest-Version: 1.0\r\nPremain-Class: FixtureAgent\r\n"
    if classpath:
        main += "Class-Path: " + classpath + "\r\n"
    if named:
        main += "\r\nName: data.txt\r\n"
    main += "bOoT-cLaSs-PaTh: " + boot + "\r\n\r\n"
    with zipfile.ZipFile(target, "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", main)
    if item:
        item["sha256"] = digest(target)
    return name


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize("location", ["subject", "companion", "libraries/agent.bin"])
@pytest.mark.parametrize(
    "reference",
    ["/source/payload.jar", "missing.jar", "../config/", "pay\r\n load.jar"],
)
def test_invoked_agent_boot_classpath_rejects_in_every_runtime_role(
    recipe, boundary, location, reference
):
    spec, _path, save = recipe
    name = agent_manifest(spec, location, reference)
    file(spec, "config/boot.cfg")
    spec["template"]["mutable_files"] = ["config/boot.cfg"]
    arguments(
        spec,
        [f"-javaagent:{name}=opaque-options", "-cp", name, "FixtureMain"],
        boundary,
    )
    with pytest.raises(
        InvestigationError, match="agent Boot-Class-Path is unsupported"
    ):
        runtime.validate_spec(save_template(spec, save))


def test_agent_role_cannot_be_hidden_by_prior_ordinary_or_cyclic_edges(recipe):
    spec, _path, save = recipe
    name = agent_manifest(
        spec, "companion", "missing.jar", classpath="../libraries/game.jar"
    )
    agent_manifest(spec, "libraries/game.jar", "data-only", classpath="../" + name)
    spec["arguments"] = [
        "-cp",
        name,
        f"-javaagent:{name}",
        f"-javaagent:{name}",
        "FixtureMain",
    ]
    with pytest.raises(
        InvestigationError, match="agent Boot-Class-Path is unsupported"
    ):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize(
    "context",
    ["ordinary", "named-attribute", "empty-agent", "whitespace-agent", "native-agent"],
)
def test_only_nonempty_main_attributes_of_invoked_java_agents_have_authority(
    recipe, context
):
    spec, _path, save = recipe
    boot = "https://example.invalid/ordinary-data"
    if context == "empty-agent":
        boot = ""
    elif context == "whitespace-agent":
        boot = "  \r\n  "
    name = agent_manifest(spec, "companion", boot, named=context == "named-attribute")
    spec["arguments"] = ["-cp", name, "FixtureMain"]
    if context != "ordinary":
        flag = "-agentpath:" if context == "native-agent" else "-javaagent:"
        spec["arguments"].insert(0, flag + name)
    runtime.validate_spec(save_template(spec, save))
    # Ordinary Class-Path is still authoritative in all these roles.
    agent_manifest(
        spec,
        "companion",
        boot,
        named=context == "named-attribute",
        classpath="missing.bin",
    )
    with pytest.raises(InvestigationError, match="missing.bin"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("boundary", ["argv", "argfile", "split"])
@pytest.mark.parametrize(
    "entry",
    [
        ["FixtureMain"],
        ["-jar", "libraries/game.jar"],
        ["-m", "fixture/main"],
        ["--module=fixture/main"],
    ],
)
@pytest.mark.parametrize("data", ["@not-present", "@config/application.txt"])
def test_application_at_values_are_literal_and_configuration_remains_mutable(
    recipe, boundary, entry, data
):
    spec, _path, save = recipe
    file(
        spec,
        "config/application.txt",
        "-XX:Flags=/ordinary-data\n-Djava.ext.dirs=/data\n",
    )
    spec["template"]["mutable_files"] = ["config/application.txt"]
    tokens = ["-cp", "libraries/game.jar", *entry, data, "-XX:Flags=app-data"]
    arguments(spec, tokens, "argfile" if boundary in {"argfile", "split"} else "argv")
    if boundary == "split":
        spec["arguments"].append("@another-missing-file")
    runtime.validate_spec(save_template(spec, save))
    files, _dirs = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert "config/application.txt" not in files
    assert ("launch.args" in files) == (boundary != "argv")


@pytest.mark.parametrize("prefix", [[], ["@prefix.args"]])
def test_actual_argument_file_operands_and_cross_file_option_state(recipe, prefix):
    spec, _path, save = recipe
    file(spec, "prefix.args", "-cp\n")
    file(spec, "operand.args", "libraries/game.jar\n")
    file(spec, "main.args", "FixtureMain @missing\n")
    spec["arguments"] = [
        *(prefix or ["-cp"]),
        "@operand.args",
        "@main.args",
        "@missing-too",
    ]
    runtime.validate_spec(save_template(spec, save))
    files, _dirs = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert {"operand.args", "main.args", "libraries/game.jar"} <= files


@pytest.mark.parametrize("option", ["--add-opens", "--add-modules", "--module-path"])
def test_consuming_an_option_operand_does_not_start_application_data(recipe, option):
    spec, _path, save = recipe
    file(
        spec,
        "operand.args",
        "libraries/game.jar\n" if option == "--module-path" else "fixture\n",
    )
    spec["arguments"] = [
        option,
        "@operand.args",
        "-XX:Flags=missing.cfg",
        "FixtureMain",
    ]
    with pytest.raises(InvestigationError, match="Flags is unsupported"):
        runtime.validate_spec(save_template(spec, save))


def test_nested_launcher_at_tokens_are_explicitly_unsupported_not_silently_expanded(
    recipe,
):
    spec, _path, save = recipe
    file(spec, "launch.args", "-cp @nested.args FixtureMain\n")
    with pytest.raises(InvestigationError, match="nested argument files"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
def test_optional_recipe_looking_property_application_and_control_data_stays_opaque(
    recipe, boundary
):
    spec, _path, save = recipe
    prose = "-XX:Flags=/data -Djava.ext.dirs=/data -Djava.endorsed.dirs=/data -Dsun.boot.class.path=/data -Dsun.boot.library.path=/data -Djava.home=/data"
    arguments(
        spec,
        ["-Ddescription=" + prose, "FixtureMain", prose, "-XX:Flags=application"],
        boundary,
    )
    spec["environment"]["SQUINCH_DESCRIPTION"] = prose
    file(spec, "config/data.cfg", prose)
    spec["template"]["mutable_files"] = ["config/data.cfg"]
    runtime.validate_spec(save_template(spec, save))


@pytest.fixture
def real_jdk17(tmp_path):
    """Explicit opt-in real launcher control, not a substituted Java executable."""
    home = os.environ.get("JDK17_HOME")
    if not home:
        pytest.skip("set JDK17_HOME for actual launcher grammar controls")
    jdk = Path(home)
    source = Path(__file__).parent / "fixtures/BoundaryFixture.java"
    subprocess.run(
        [
            str(jdk / "bin/javac"),
            "-J-XX:-UsePerfData",
            "-d",
            str(tmp_path),
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return jdk / "bin/java", tmp_path


@pytest.mark.parametrize("form", ["main", "jar", "module", "argfile", "operand"])
def test_real_java_application_boundary_and_mutable_at_data(real_jdk17, form):
    java, root = real_jdk17
    data = root / "app.data"
    data.write_text("-XX:Flags=not-a-recipe\n")
    args = ["-cp", str(root), "BoundaryFixture"]
    if form == "jar":
        with zipfile.ZipFile(root / "main.jar", "w") as jar:
            jar.write(root / "BoundaryFixture.class", "BoundaryFixture.class")
            jar.writestr(
                "META-INF/MANIFEST.MF",
                "Manifest-Version: 1.0\nMain-Class: BoundaryFixture\n\n",
            )
        args = ["-jar", "main.jar"]
    elif form == "module":
        # Automatic modules require a named package; compile a namespaced copy.
        source = root / "BoundaryFixture.java"
        original = Path(__file__).parent / "fixtures/BoundaryFixture.java"
        source.write_text("package fixture;\n" + original.read_text())
        subprocess.run(
            [
                str(java.parent / "javac"),
                "-J-XX:-UsePerfData",
                "-d",
                str(root),
                str(source),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        with zipfile.ZipFile(root / "fixture.jar", "w") as jar:
            jar.write(
                root / "fixture/BoundaryFixture.class", "fixture/BoundaryFixture.class"
            )
        args = [
            "--module-path",
            "fixture.jar",
            "--module",
            "fixture/fixture.BoundaryFixture",
        ]
    elif form == "argfile":
        (root / "launch.args").write_text("-cp . BoundaryFixture @missing @app.data\n")
        args = ["@launch.args"]
    elif form == "operand":
        (root / "prefix.args").write_text("-cp\n")
        (root / "operand.args").write_text(".\n")
        args = ["@prefix.args", "@operand.args", "BoundaryFixture"]
    if form != "argfile":
        args += ["@missing", "@app.data"]
    result = subprocess.run(
        [str(java), "-XX:-UsePerfData", *args],
        check=False,
        cwd=root,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["@missing", "@app.data"]
    assert data.read_text() == "application-mutated\n"
