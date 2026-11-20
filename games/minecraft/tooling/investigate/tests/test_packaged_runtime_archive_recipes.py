"""Actual archive/startup roles, not a sandbox or Minecraft qualification."""

from __future__ import annotations

import os
import shutil
import subprocess
import warnings
import zipfile
from pathlib import Path

import pytest
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from test_packaged_runtime import digest
from test_packaged_runtime_jvm_recipes import arguments
from test_packaged_runtime_launch_closure import file, save_template

pytest_plugins = ["test_packaged_runtime"]


def manifest(spec, location, text, *, entries=("META-INF/MANIFEST.MF",)):
    item = None
    if location in {"subject", "companion"}:
        item = spec["subject"] if location == "subject" else spec["companions"][0]
        target = Path(item["path"])
        name = "mods/" + item["name"]
    else:
        name = location
        target = file(spec, name)
    with warnings.catch_warnings(), zipfile.ZipFile(target, "w") as jar:
        warnings.simplefilter(
            "ignore", UserWarning
        )  # Deliberate duplicate ZIP entries.
        for entry in entries:
            jar.writestr(entry, text)
    if item:
        item["sha256"] = digest(target)
    return name


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "location", ["subject", "companion", "libraries/game.jar", "libraries/main.dat"]
)
@pytest.mark.parametrize(
    "entry", ["META-INF/manifest.mf", "meta-inf/manifest.mf", "Meta-Inf/MaNiFeSt.Mf"]
)
def test_cased_manifest_closes_actual_archive_edges(recipe, boundary, location, entry):
    spec, _path, save = recipe
    name = manifest(
        spec,
        location,
        "Manifest-Version: 1.0\r\ncLaSs-PaTh: missing.dat\r\n\r\n",
        entries=(entry,),
    )
    arguments(spec, ["-cp", name, "FixtureMain"], boundary)
    with pytest.raises(InvestigationError, match="missing.dat"):
        runtime.validate_spec(save_template(spec, save))
    # The same discovered manifest accepts a closed archive-relative edge.
    prefix = "../libraries/" if name.startswith("mods/") else ""
    manifest(
        spec,
        location,
        f"Manifest-Version: 1.0\nClass-Path: {prefix}dependency.dat\n\n",
        entries=(entry,),
    )
    manifest(
        spec,
        "libraries/dependency.dat",
        f"Manifest-Version: 1.0\nClass-Path: ../{name}\n\n",
    )
    runtime.validate_spec(save_template(spec, save))
    files, _directories = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert "libraries/dependency.dat" in files


@pytest.mark.parametrize("location", ["subject", "companion", "libraries/main.dat"])
@pytest.mark.parametrize(
    "entries",
    [
        ("META-INF/MANIFEST.MF", "META-INF/MANIFEST.MF"),
        ("META-INF/MANIFEST.MF", "meta-inf/manifest.mf"),
        ("META-INF/manifest.mf", "meta-inf/manifest.mf"),
    ],
)
def test_ambiguous_manifests_fail_closed_even_with_identical_content(
    recipe, location, entries
):
    spec, _path, save = recipe
    name = manifest(spec, location, "Manifest-Version: 1.0\n\n", entries=entries)
    spec["arguments"] = ["-cp", name, "FixtureMain"]
    with pytest.raises(InvestigationError, match="ambiguous runtime manifests"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "option",
    [
        "-XX:SharedArchiveFile",
        "-XX:SharedClassListFile",
        "-XX:ExtraSharedClassListFile",
        "-XX:SharedArchiveConfigFile",
        "-XX:CompileCommandFile",
        "-XX:CompilerDirectivesFile",
        "-XXaltjvm",
        "-J-XXaltjvm",
    ],
)
@pytest.mark.parametrize("form", ["missing", "source", "mutable", "empty", "bare"])
def test_optional_startup_file_selectors_reject_before_allocation(
    recipe, subprocess_service, boundary, option, form
):
    spec, _path, save = recipe
    value = "missing.input"
    if form == "mutable":
        file(
            spec,
            "config/input.cfg",
            "original validation-shape fixture, not a CDS archive",
        )
        spec["template"]["mutable_files"] = ["config/input.cfg"]
        value = "config/input.cfg"
    elif form == "source":
        source = Path(spec["project"]) / "external.input"
        source.write_text("original validation-shape fixture")
        value = str(source)
    token = (
        option if form == "bare" else option + "=" + ("" if form == "empty" else value)
    )
    arguments(spec, [token, "-cp", "mods/test.jar", "FixtureMain"], boundary)
    before = runtime._source_snapshot(Path(spec["project"]), spec["source_roots"])
    runs = set(runtime.RUNS_ROOT.iterdir())
    with pytest.raises(InvestigationError, match="is unsupported"):
        runtime.run_packaged_runtime(save_template(spec, save))
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == runs
    assert (
        runtime._source_snapshot(Path(spec["project"]), spec["source_roots"]) == before
    )


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "token",
    [
        "-agentlib:instrument=missing.jar",
        "-Xruninstrument:missing.jar",
        "-agentlib:jdwp=opaque",
        "-Xrunhprof:opaque",
    ],
)
def test_named_native_agent_aliases_cannot_hide_a_second_java_agent(
    recipe, boundary, token
):
    spec, _path, save = recipe
    arguments(spec, [token, "FixtureMain"], boundary)
    with pytest.raises(InvestigationError, match="named native agents.*unsupported"):
        runtime.validate_spec(save_template(spec, save))


@pytest.mark.parametrize("boundary", ["argv", "argfile"])
@pytest.mark.parametrize(
    "location", ["subject", "companion", "libraries/game.jar", "libraries/main.dat"]
)
@pytest.mark.parametrize(
    "value", ["ArchiveFixture$Agent", "ArchiveFixture$Ag\r\n ent", ""]
)
def test_only_actual_main_jar_role_rejects_launcher_agent(
    recipe, boundary, location, value
):
    spec, _path, save = recipe
    name = manifest(
        spec,
        location,
        "Manifest-Version: 1.0\r\nMain-Class: FixtureMain\r\n"
        f"lAuNcHeR-aGeNt-ClAsS: {value}\r\nBoot-Class-Path: /source/outside.jar\r\n\r\n",
    )
    arguments(spec, ["-jar", name], boundary)
    with pytest.raises(InvestigationError, match="Launcher-Agent-Class is unsupported"):
        runtime.validate_spec(save_template(spec, save))
    # The very same attributes do not invoke an agent through -cp.
    arguments(spec, ["-cp", name, "FixtureMain"], boundary)
    runtime.validate_spec(save_template(spec, save))


def test_earlier_cyclic_visit_cannot_hide_actual_executable_role(recipe):
    spec, _path, save = recipe
    name = manifest(
        spec,
        "companion",
        "Manifest-Version: 1.0\nClass-Path: ../libraries/game.jar\nLauncher-Agent-Class: Agent\n\n",
    )
    manifest(
        spec, "libraries/game.jar", f"Manifest-Version: 1.0\nClass-Path: ../{name}\n\n"
    )
    spec["arguments"] = ["-cp", "libraries/game.jar", "-jar", name]
    with pytest.raises(InvestigationError, match="Launcher-Agent-Class is unsupported"):
        runtime.validate_spec(save_template(spec, save))


def test_named_sections_uninvoked_archives_and_prose_remain_data(recipe):
    spec, _path, save = recipe
    name = manifest(
        spec,
        "companion",
        "Manifest-Version: 1.0\nMain-Class: FixtureMain\n\nName: data.txt\nLauncher-Agent-Class: Agent\nBoot-Class-Path: /source/data.jar\nClass-Path: missing.jar\n\n",
    )
    manifest(
        spec,
        "data/opaque.zip",
        "Manifest-Version: 1.0\nLauncher-Agent-Class: Agent\nClass-Path: /source/data.jar\n\n",
        entries=("META-INF/MANIFEST.MF", "meta-inf/manifest.mf"),
    )
    manifest(
        spec,
        "libraries/uninvoked.jar",
        "Manifest-Version: 1.0\nLauncher-Agent-Class: Agent\nBoot-Class-Path: /source/data.jar\n\n",
    )
    prose = "-XX:SharedArchiveFile=/data.jsa -agentlib:instrument=/data -XXaltjvm=/data -XX:CompilerDirectivesFile=/data"
    arguments(
        spec, ["-Ddescription=" + prose, "-jar", name, "@missing", prose], "argfile"
    )
    spec["environment"]["SQUINCH_DESCRIPTION"] = prose
    file(spec, "config/data.cfg", prose)
    spec["template"]["mutable_files"] = ["config/data.cfg"]
    runtime.validate_spec(save_template(spec, save))
    files, _directories = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert "data/opaque.zip" not in files and "config/data.cfg" not in files


@pytest.fixture(params=["8", "17"])
def archive_jvm(request, tmp_path):
    version = request.param
    home = os.environ.get("JDK" + version + "_HOME")
    if not home:
        pytest.skip("set JDK" + version + "_HOME for real archive controls")
    java = Path(home) / "bin/java"
    fixtures = Path(__file__).parent / "fixtures"
    subprocess.run(
        [
            str(java.parent / "javac"),
            "-J-XX:-UsePerfData",
            "-d",
            str(tmp_path),
            str(fixtures / "ArchiveFixture.java"),
            str(fixtures / "ArchivePayload.java"),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return java, tmp_path, version


def jvm(java, root, *arguments):
    return subprocess.run(
        [str(java), "-XX:-UsePerfData", *arguments],
        cwd=root,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def real_archive(root, name, text, classes, entry="META-INF/MANIFEST.MF"):
    with zipfile.ZipFile(root / name, "w") as jar:
        jar.writestr(entry, text)
        for cls in classes:
            jar.write(root / (cls + ".class"), cls + ".class")


@pytest.mark.parametrize(
    "entry",
    [
        "META-INF/MANIFEST.MF",
        "META-INF/manifest.mf",
        "meta-inf/manifest.mf",
        "Meta-Inf/MaNiFeSt.Mf",
    ],
)
def test_real_jarfile_cased_manifest_classpath(archive_jvm, entry):
    java, root, _version = archive_jvm
    real_archive(root, "payload.dat", "Manifest-Version: 1.0\n\n", ["ArchivePayload"])
    real_archive(
        root,
        "main.jar",
        "Manifest-Version: 1.0\nClass-Path: payload.dat\n\n",
        ["ArchiveFixture"],
        entry,
    )
    p = jvm(java, root, "-cp", "main.jar", "ArchiveFixture")
    assert p.returncode == 0, p.stderr
    assert "payload=original-archive-payload" in p.stdout


def test_real_main_jar_agent_role_and_native_instrument_aliases(archive_jvm):
    java, root, version = archive_jvm
    real_archive(root, "payload.jar", "Manifest-Version: 1.0\n\n", ["ArchivePayload"])
    attributes = (
        "Manifest-Version: 1.0\nMain-Class: ArchiveFixture\nPremain-Class: ArchiveFixture$Agent\nAgent-Class: ArchiveFixture$Agent\nBoot-Class-Path: "
        + str(root / "payload.jar")
        + "\n"
    )
    classes = ["ArchiveFixture", "ArchiveFixture$Agent"]
    real_archive(root, "ordinary.jar", attributes + "\n", classes)
    p = jvm(java, root, "-jar", "ordinary.jar")
    assert p.returncode == 0, p.stderr
    assert "payload=absent" in p.stdout and "agent=absent" in p.stdout
    real_archive(
        root,
        "invoked.dat",
        attributes + "Launcher-Agent-Class: ArchiveFixture$Agent\n\n",
        classes,
    )
    p = jvm(java, root, "-jar", "invoked.dat")
    assert p.returncode == 0, p.stderr
    if version == "17":
        assert (
            "bootstrap=true" in p.stdout
            and "agent=original-archive-payload" in p.stdout
        )
    else:
        assert "payload=absent" in p.stdout and "agent=absent" in p.stdout
    for selector in [
        "-agentlib:instrument=ordinary.jar",
        "-Xruninstrument:ordinary.jar",
    ]:
        p = jvm(java, root, selector, "-cp", "ordinary.jar", "ArchiveFixture")
        assert p.returncode == 0, p.stderr
        assert (
            "agent=original-archive-payload" in p.stdout
            and "bootstrap=true" in p.stdout
        )


def test_real_alternate_vm_selector_loads_external_vm_library(archive_jvm):
    java, root, version = archive_jvm
    home = java.parent.parent
    library = home / ("jre/lib/amd64" if version == "8" else "lib")
    alternate = root / "external-vm/lib/server"
    alternate.mkdir(parents=True)
    shutil.copyfile(library / "server/libjvm.so", alternate / "libjvm.so")
    for source in library.glob("*.so"):
        shutil.copyfile(source, alternate.parent / source.name)
    boot = ["-Xbootclasspath:" + str(home / "jre/lib/rt.jar")] if version == "8" else []
    if version == "17":
        shutil.copyfile(home / "lib/modules", alternate.parent / "modules")
    for selector in ["-XXaltjvm=", "-J-XXaltjvm="]:
        p = jvm(
            java,
            root,
            selector + str(alternate),
            *boot,
            "-cp",
            str(root),
            "ArchiveFixture",
            "vm-maps",
        )
        assert p.returncode == 0, p.stderr
        assert str(alternate / "libjvm.so") in p.stdout
    missing = jvm(java, root, "-XXaltjvm=" + str(root / "missing"), "-version")
    assert missing.returncode != 0


def test_real_explicit_compiler_file_selectors_are_vm_inputs(archive_jvm):
    java, root, version = archive_jvm
    commands = root / "commands.txt"
    commands.write_text("exclude ArchiveFixture.main\n")
    p = jvm(
        java,
        root,
        "-XX:CompileCommandFile=" + str(commands),
        "-cp",
        str(root),
        "ArchiveFixture",
    )
    assert p.returncode == 0, p.stderr
    assert "exclude ArchiveFixture.main" in p.stdout
    if version == "17":
        directives = root / "directives.json"
        directives.write_text(
            '[ { match: "ArchiveFixture::main", c2: { Exclude: true } } ]\n'
        )
        p = jvm(
            java,
            root,
            "-XX:+UnlockDiagnosticVMOptions",
            "-XX:CompilerDirectivesFile=" + str(directives),
            "-XX:+CompilerDirectivesPrint",
            "-cp",
            str(root),
            "ArchiveFixture",
        )
        assert p.returncode == 0, p.stderr
        assert "ArchiveFixture.main" in p.stdout


def test_real_explicit_app_cds_archive_loads_original_application_classes(archive_jvm):
    java, root, version = archive_jvm
    if version == "8":
        pytest.skip("dynamic AppCDS control is specific to JDK17, not a JDK8 claim")
    real_archive(
        root,
        "application.jar",
        "Manifest-Version: 1.0\n\n",
        ["ArchiveFixture", "ArchivePayload"],
    )
    p = jvm(
        java,
        root,
        "-XX:ArchiveClassesAtExit=app.jsa",
        "-cp",
        "application.jar",
        "ArchiveFixture",
    )
    assert p.returncode == 0, p.stderr
    p = jvm(
        java,
        root,
        "-Xshare:on",
        "-XX:SharedArchiveFile=app.jsa",
        "-Xlog:class+load=info",
        "-cp",
        "application.jar",
        "ArchiveFixture",
    )
    assert p.returncode == 0, p.stderr
    assert "ArchiveFixture source: shared objects file (top)" in p.stdout
    assert "ArchivePayload source: shared objects file (top)" in p.stdout
    missing = jvm(
        java, root, "-Xshare:on", "-XX:SharedArchiveFile=missing.jsa", "-version"
    )
    assert missing.returncode != 0
