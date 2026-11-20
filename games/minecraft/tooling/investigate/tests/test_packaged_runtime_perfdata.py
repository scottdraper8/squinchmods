"""HotSpot optional perfdata suppression, not universal transient-state confinement."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.paths import active_path
from test_packaged_runtime_launch_closure import file, save_template

pytest_plugins = ["test_packaged_runtime"]
FLAG = "-XX:-UsePerfData"


def test_every_actual_identity_probe_disables_perfdata(recipe, monkeypatch):
    spec, path, _save = recipe
    original = runtime.subprocess.run
    commands = []

    def observe(command, **kwargs):
        if command[0] == spec["java"]["path"]:
            commands.append(command)
            assert command == [spec["java"]["path"], FLAG, "-version"]
            assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        return original(command, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "run", observe)
    assert runtime.validate_spec(path) == spec
    assert runtime._java_identity(spec)["observed_version"] == spec["java"]["version"]
    assert len(commands) == 2


def test_unsupported_vm_reports_required_perfdata_option(recipe, monkeypatch):
    spec, _path, _save = recipe

    def unsupported(command, **kwargs):
        assert command == [spec["java"]["path"], FLAG, "-version"]
        return subprocess.CompletedProcess(
            command, 1, b"Unrecognized VM option: UsePerfData"
        )

    monkeypatch.setattr(runtime.subprocess, "run", unsupported)
    with pytest.raises(
        InvestigationError,
        match="HotSpot-compatible JVM supporting -XX:-UsePerfData.*Unrecognized",
    ):
        runtime._java_identity(spec)


@pytest.mark.parametrize("boundary", ["argv", "argfile", "split", "operand"])
@pytest.mark.parametrize(
    "token",
    [
        "-XX:+UsePerfData",
        "-XX:+UsePerfData=true",
        "-XX:UsePerfData=true",
        "-XX:UsePerfData=1",
        "-XX:UsePerfData",
        "-XX:-UsePerfData=true",
    ],
)
def test_reenable_attempts_reject_before_probe_allocation_or_launch(
    recipe, subprocess_service, monkeypatch, boundary, token
):
    spec, _path, save = recipe
    tokens = [FLAG, token, FLAG, "-cp", "libraries/game.jar", "FixtureMain"]
    if boundary == "argv":
        spec["arguments"] = tokens
    elif boundary == "argfile":
        file(spec, "launch.args", shlex.join(tokens) + "\n")
    elif boundary == "split":
        file(spec, "launch.args", FLAG + "\n")
        spec["arguments"] += tokens[1:]
    else:
        file(spec, "operand.args", "libraries/game.jar\n")
        spec["arguments"] = ["-cp", "@operand.args", token, "FixtureMain"]
    source = runtime._source_snapshot(Path(spec["project"]), spec["source_roots"])
    runs = set(runtime.RUNS_ROOT.iterdir())
    monkeypatch.setattr(
        runtime, "_java_identity", lambda _: pytest.fail("identity probe reached")
    )
    with pytest.raises(
        InvestigationError, match="performance data must remain disabled.*UsePerfData"
    ):
        runtime.run_packaged_runtime(save_template(spec, save))
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == runs
    assert (
        runtime._source_snapshot(Path(spec["project"]), spec["source_roots"]) == source
    )
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


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
def test_reenable_looking_data_after_every_main_boundary_remains_literal(
    recipe, boundary, entry
):
    spec, _path, save = recipe
    prose = "-XX:+UsePerfData -XX:UsePerfData=true"
    tokens = [FLAG, "-Ddescription=" + prose, "-cp", "libraries/game.jar", *entry]
    data = ["-XX:+UsePerfData", "-XX:UsePerfData=true", "@missing", prose]
    if boundary == "argv":
        spec["arguments"] = tokens + data
    else:
        file(
            spec,
            "launch.args",
            shlex.join(tokens + (data if boundary == "argfile" else [])) + "\n",
        )
        if boundary == "split":
            spec["arguments"] += data
    file(spec, "config/data.cfg", prose)
    spec["template"]["mutable_files"] = ["config/data.cfg"]
    spec["environment"]["SQUINCH_DESCRIPTION"] = prose
    assert runtime.validate_spec(save_template(spec, save)) == spec
    files, _dirs = runtime._launch_inputs(spec, Path(spec["template"]["path"]))
    assert "config/data.cfg" not in files


@pytest.mark.parametrize("version", ["8", "17"])
def test_selected_hotspot_effective_flag_and_owned_sentinel(tmp_path, version):
    home = os.environ.get("JDK" + version + "_HOME")
    if not home:
        pytest.skip(
            "set JDK" + version + "_HOME for selected HotSpot perfdata controls"
        )
    java = Path(home) / "bin/java"
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TMPDIR": str(tmp_path)}
    flags = subprocess.run(
        [str(java), FLAG, "-XX:+PrintFlagsFinal", "-version"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert any(
        line.split()[:4] == ["bool", "UsePerfData", "=", "false"]
        or line.split()[:4] == ["bool", "UsePerfData", ":=", "false"]
        for line in flags.stdout.splitlines()
    ), flags.stdout
    source = Path(__file__).parent / "fixtures/PerfDataFixture.java"
    subprocess.run(
        [
            str(java.parent / "javac"),
            "-J" + FLAG,
            "-proc:none",
            "-d",
            str(tmp_path),
            str(source),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=True,
        timeout=30,
    )
    # Tools accept JVM options through -J, not raw launcher options.
    tool = subprocess.run(
        [
            str(java.parent / "javap"),
            "-J" + FLAG,
            "-J-XX:+PrintFlagsFinal",
            "-classpath",
            str(tmp_path),
            "PerfDataFixture",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert any(
        "UsePerfData" in line and "false" in line for line in tool.stdout.splitlines()
    )
    result = subprocess.run(
        [
            str(java),
            FLAG,
            "-Djava.io.tmpdir=" + str(tmp_path),
            "-cp",
            str(tmp_path),
            "PerfDataFixture",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert "UsePerfData=false\n" in result.stdout
    assert "vmArguments=[" + FLAG in result.stdout
    assert (
        "sentinel=" + str(tmp_path / "perfdata-disabled-sentinel.txt") in result.stdout
    )
    assert (
        tmp_path / "perfdata-disabled-sentinel.txt"
    ).read_text() == "owned scratch only\n"
