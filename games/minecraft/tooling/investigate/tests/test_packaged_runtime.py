from __future__ import annotations

import copy
import hashlib
import json
import os
import signal
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from squinch_minecraft_investigate import cli, owned_operation, server
from squinch_minecraft_investigate import packaged_runtime as runtime
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
from squinch_minecraft_investigate.paths import active_path
from squinch_minecraft_investigate.processes import proc_identity
from squinch_minecraft_investigate.tranche import require_tranche, validate_cli_inputs


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(project: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)


@pytest.fixture
def recipe(tmp_path):
    _id, workspace = require_tranche()
    root = workspace / "inputs" / uuid.uuid4().hex
    root.mkdir(parents=True)
    runtime.prepare_owned_directory("minecraft", "investigate", "runs")
    project = tmp_path / "project"
    project.mkdir()
    (project / "source.txt").write_text("original\n")
    git(project, "init")
    git(project, "add", "source.txt")
    git(
        project,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    template = root / "template"
    template.mkdir()
    (template / "mods").mkdir()
    (template / "launch.args").write_text("-cp libraries/game.jar FixtureMain\n")
    (template / "libraries").mkdir()
    with zipfile.ZipFile(template / "libraries/game.jar", "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
    artifacts = []
    for name in ("subject.jar", "test.jar"):
        path = root / name
        with zipfile.ZipFile(path, "w") as jar:
            jar.writestr("fixture.txt", name)
        artifacts.append({"path": str(path), "name": name, "sha256": digest(path)})
    java = root / "fixture-java"
    # This executable is deliberately NOT a JVM and proves only orchestration boundaries.
    java.write_text(f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
if sys.argv[1:] == ["-XX:-UsePerfData", "-version"]:
    print("lifecycle fixture, not a JVM")
    raise SystemExit(0)
time.sleep(0.3)
mode = os.environ.get("SQUINCH_MODE", "pass")
if mode == "timeout":
    time.sleep(30)
if mode == "source":
    Path({str(project / "source.txt")!r}).write_text("changed\\n")
if mode == "staged":
    Path("mods/subject.jar").write_text("changed")
if mode == "template":
    Path("launch.args").write_text("changed")
if mode == "configuration":
    Path("server.properties").write_text("#Generated header\\nserver-port=25565\\n")
    Path("config/example.json").write_text('{{"url": "https://example.invalid/data"}}')
if mode == "input":
    Path({str(root / "test.jar")!r}).write_text("changed")
if mode == "crash":
    Path("crash-reports").mkdir()
    Path("crash-reports/crash.txt").write_text("crash")
if mode == "fatal":
    print("[FATAL] controlled fixture failure", flush=True)
value = {{"schema_version": 1, "run_id": os.environ["SQUINCH_INVESTIGATE_RUN_ID"],
    "status": "pass", "subject_sha256": {artifacts[0]["sha256"]!r},
    "runtime": {{"loader": "forge", "minecraft": "1.16.5", "side": os.environ.get("SQUINCH_SIDE", "server")}},
    "cases": [{{"id": "behavior", "status": "pass", "observations": {{"cwd": str(Path.cwd()), "inherited": os.environ.get("SQUINCH_LEAK"), "jvm_options": os.environ.get("JAVA_TOOL_OPTIONS"), "pycache_prefix": sys.pycache_prefix, "dont_write_bytecode": sys.dont_write_bytecode}}}}]}}
if mode != "missing":
    Path(os.environ["SQUINCH_RESULT"]).write_text(json.dumps(value))
if mode == "early-fail":
    time.sleep(0.5)
    raise SystemExit(7)
""")
    java.chmod(0o700)
    spec = {
        "schema_version": 1,
        "project": str(project),
        "source_roots": [str(project)],
        "loader": "forge",
        "minecraft": "1.16.5",
        "side": "server",
        "template": {
            "path": str(template),
            "files": runtime._tree(template),
            "mutable_files": [],
        },
        "subject": artifacts[0],
        "companions": [artifacts[1]],
        "java": {
            "path": str(java),
            "sha256": digest(java),
            "version": "lifecycle fixture, not a JVM",
        },
        "arguments": ["@launch.args"],
        "environment": {},
        "results": [
            {
                "environment": "SQUINCH_RESULT",
                "name": "result.json",
                "cases": ["behavior"],
            }
        ],
        "timeout": 5,
    }
    path = root / "spec.json"

    def save():
        path.write_text(json.dumps(spec))
        return path

    save()
    return spec, path, save


@pytest.fixture
def subprocess_service(monkeypatch):
    """Real subprocess/exit-sentinel boundary, with a substitute for systemd only.

    This fixture makes NO claims about Minecraft or real cgroup/service ownership.
    Existing lifecycle tests and the optional real owned-service smoke cover that separately.
    """
    processes = []
    calls = []

    def launch(**kwargs):
        process = subprocess.Popen(
            kwargs["command"],
            cwd=kwargs["cwd"],
            stdout=kwargs["output"],
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(process)
        identity = proc_identity(process.pid)
        service = {"unit": kwargs["unit"], "cgroup": "/fixture", "wrapper": identity}
        kwargs["publish_start"](process, service, identity)
        calls.append(kwargs)
        return process, service, identity

    def terminate(state, timeout, *, label):
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=timeout)
        return []

    monkeypatch.setattr(owned_operation, "launch_service", launch)
    monkeypatch.setattr(owned_operation, "live_owned_processes", lambda *_a, **_k: [])
    monkeypatch.setattr(owned_operation, "wait_owned_exit", lambda *_a, **_k: True)
    monkeypatch.setattr(owned_operation, "terminate_owned_service", terminate)
    monkeypatch.setattr(runtime, "uninterruptible_owned_processes", lambda *_a: [])
    yield calls
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def test_strict_schema_and_explicit_cli(recipe):
    spec, path, save = recipe
    assert runtime.validate_spec(path) == spec
    args = cli.parser().parse_args(["packaged-runtime", str(path), "--json"])
    validate_cli_inputs(args)
    spec["unknown"] = True
    with pytest.raises(InvestigationError, match="Additional properties"):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "edit",
    [
        lambda s: s["subject"].update(sha256="bad"),
        lambda s: s["subject"].update(sha256="0" * 64),
        lambda s: s["subject"].update(name="../escape.jar"),
        lambda s: s["subject"].update(name="-unsafe.jar"),
        lambda s: s["companions"][0].update(name="SUBJECT.jar"),
        lambda s: s.update(loader="dummy"),
        lambda s: s.update(timeout=float("nan")),
        lambda s: s["java"].update(version="wrong"),
        lambda s: s["java"].update(sha256="0" * 64),
        lambda s: s["environment"].update(JAVA_TOOL_OPTIONS="x"),
        lambda s: s["environment"].update(SQUINCH_TRANCHE="other"),
        lambda s: s["environment"].update(SQUINCH_RESULT="elsewhere"),
        lambda s: s["results"].append(copy.deepcopy(s["results"][0])),
        lambda s: s["results"][0].update(cases=[]),
        lambda s: s["arguments"].insert(0, "-cp=/source/build/classes"),
        lambda s: s["arguments"].insert(0, "-cp=//source/build/classes"),
        lambda s: s["arguments"].insert(0, "@../source.args"),
        lambda s: s["arguments"].insert(0, "-Duser.dir=source"),
    ],
)
def test_invalid_contracts_fail_before_launch(recipe, edit):
    spec, _path, save = recipe
    edit(spec)
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save())


@pytest.mark.parametrize(
    "kind",
    [
        "outside",
        "other-tranche",
        "source",
        "symlink",
        "parent-link",
        "special",
        "hardlink",
    ],
)
def test_input_confinement(recipe, tmp_path, kind):
    spec, path, save = recipe
    original = Path(spec["subject"]["path"])
    if kind == "outside":
        target = tmp_path / "outside.jar"
        target.write_bytes(original.read_bytes())
    elif kind == "other-tranche":
        _id, workspace = require_tranche()
        target = workspace.parent / f"other-{uuid.uuid4().hex}" / "subject.jar"
        target.parent.mkdir()
        target.write_bytes(original.read_bytes())
    elif kind == "source":
        # A legitimate tranche worktree is allowed as project, not as input recipes.
        target = path.parent / "worktree" / "subject.jar"
        target.parent.mkdir()
        git(target.parent, "init")
        (target.parent / "tracked").write_text("source")
        git(target.parent, "add", "tracked")
        git(
            target.parent,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        )
        spec["project"] = str(target.parent)
        spec["source_roots"] = [str(target.parent)]
        target.write_bytes(original.read_bytes())
    elif kind == "parent-link":
        link = path.parent / "linked"
        link.symlink_to(original.parent, target_is_directory=True)
        target = link / original.name
    else:
        target = path.parent / "alias.jar"
        if kind == "symlink":
            target.symlink_to(original)
        elif kind == "hardlink":
            os.link(original, target)
        else:
            os.mkfifo(target)
    spec["subject"]["path"] = str(target)
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save())


def test_duplicate_keys_rejected(recipe):
    _spec, path, _save = recipe
    path.write_text('{"schema_version": 1, "schema_version": 1}')
    with pytest.raises(InvestigationError, match="duplicate JSON key"):
        runtime.validate_spec(path)


@pytest.mark.parametrize(
    "extra",
    [
        "mods/implicit.jar",
        "result.json",
        "results/stale.json",
        "logs/latest.log",
        "source.java",
    ],
)
def test_template_rejects_implicit_mods_and_stale_outputs(recipe, extra):
    spec, _path, save = recipe
    template = Path(spec["template"]["path"])
    target = template / extra
    target.parent.mkdir(exist_ok=True)
    target.write_text("stale")
    spec["template"]["files"] = runtime._tree(template)
    with pytest.raises(InvestigationError):
        runtime.validate_spec(save())


def test_template_manifest_and_reference_integrity(recipe):
    spec, path, save = recipe
    template = Path(spec["template"]["path"])
    launch = template / "launch.args"
    launch.write_text("-cp /source/build/classes FixtureMain")
    with pytest.raises(InvestigationError, match="manifest"):
        runtime.validate_spec(path)
    spec["template"]["files"] = runtime._tree(template)
    with pytest.raises(InvestigationError, match="references"):
        runtime.validate_spec(save())
    launch.write_text("-cp '../build/classes' FixtureMain")
    spec["template"]["files"] = runtime._tree(template)
    with pytest.raises(InvestigationError, match="references"):
        runtime.validate_spec(save())


@pytest.mark.parametrize("location", ["template", "companion"])
def test_archive_manifest_cannot_redirect_into_source(recipe, location):
    spec, _path, save = recipe
    target = (
        Path(spec["template"]["path"]) / "libraries/game.jar"
        if location == "template"
        else Path(spec["companions"][0]["path"])
    )
    with zipfile.ZipFile(target, "w") as jar:
        jar.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\nClass-Path: //source/build/game.jar\n",
        )
    if location == "template":
        spec["template"]["files"] = runtime._tree(Path(spec["template"]["path"]))
    else:
        spec["companions"][0]["sha256"] = digest(target)
    with pytest.raises(InvestigationError, match="references"):
        runtime.validate_spec(save())


def test_subject_marker_is_rejected_but_separate_test_companion_is_allowed(recipe):
    spec, _path, save = recipe
    subject = Path(spec["subject"]["path"])
    with zipfile.ZipFile(spec["companions"][0]["path"], "a") as jar:
        jar.writestr("META-INF/squinch-development-probe", "marker")
    spec["companions"][0]["sha256"] = digest(Path(spec["companions"][0]["path"]))
    runtime.validate_spec(save())
    with zipfile.ZipFile(subject, "a") as jar:
        jar.writestr("META-INF/squinch-development-probe", "marker")
    spec["subject"]["sha256"] = digest(subject)
    with pytest.raises(InvestigationError, match="probe markers"):
        runtime.validate_spec(save())


def result_state(recipe):
    spec, path, _save = recipe
    artifact = path.parent / "assertions"
    (artifact / "results").mkdir(parents=True)
    value = {
        "schema_version": 1,
        "run_id": "fixture-run",
        "status": "pass",
        "subject_sha256": spec["subject"]["sha256"],
        "runtime": {k: spec[k] for k in ("loader", "minecraft", "side")},
        "cases": [{"id": "behavior", "status": "pass"}],
    }
    output = artifact / "results" / "result.json"
    output.write_text(json.dumps(value))
    return (
        {"spec": spec, "run_id": "fixture-run", "artifact_dir": str(artifact)},
        output,
        value,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.clear(),
        lambda v: v.update(status="fail"),
        lambda v: v.pop("runtime"),
        lambda v: v.pop("subject_sha256"),
        lambda v: v.update(subject_sha256="0" * 64),
        lambda v: v.update(run_id="stale"),
        lambda v: v["runtime"].update(loader="quilt"),
        lambda v: v["runtime"].update(minecraft="1.20.1"),
        lambda v: v["runtime"].update(side="client"),
        lambda v: v.update(cases=[]),
        lambda v: v["cases"][0].update(id="wrong"),
        lambda v: v["cases"][0].update(status="fail"),
        lambda v: v["cases"].append(copy.deepcopy(v["cases"][0])),
        lambda v: v["cases"].append({"id": "unexpected", "status": "pass"}),
    ],
)
def test_result_requires_exact_passing_cases_and_identities(recipe, mutation):
    state, output, value = result_state(recipe)
    assert runtime._inspect_results(state)[0]["result"] == value
    mutation(value)
    output.write_text(json.dumps(value))
    with pytest.raises(InvestigationError):
        runtime._inspect_results(state)


def test_missing_malformed_and_linked_result(recipe):
    state, output, _value = result_state(recipe)
    output.write_text("{")
    with pytest.raises(InvestigationError):
        runtime._inspect_results(state)
    output.unlink()
    with pytest.raises(FileNotFoundError):
        runtime._inspect_results(state)
    output.symlink_to(Path(state["artifact_dir"]) / "missing")
    with pytest.raises(InvestigationError):
        runtime._inspect_results(state)


@pytest.mark.parametrize("side", ["server", "client"])
def test_real_application_boundary_command_and_clean_environment(
    recipe, subprocess_service, monkeypatch, tmp_path, side
):
    spec, path, save = recipe
    spec["side"] = side
    spec["environment"]["SQUINCH_SIDE"] = side
    monkeypatch.setenv("SQUINCH_LEAK", "must not inherit")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "must not inherit")
    if side == "client":
        display_root = tmp_path / "xdg"
        display_root.mkdir()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(display_root))
        # No compositor assertion: substitute only its wrapper, retain the real inner process.
        fake_bin = path.parent / "bin"
        fake_bin.mkdir()
        cage = fake_bin / "cage"
        cage.write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
        cage.chmod(0o700)
        original = runtime._base_environment
        monkeypatch.setattr(
            runtime,
            "_base_environment",
            lambda run: {**original(run), "PATH": f"{fake_bin}:/usr/bin:/bin"},
        )
    state = runtime.run_packaged_runtime(save())
    assert state["lifecycle"] == "succeeded"
    assert state["cleanup"]["complete"]
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()
    assert subprocess_service[0]["cwd"] == Path(spec["project"])
    command = state["command"]
    assert command[:2] == ["/usr/bin/env", "-i"]
    assert state["java_command"] == [
        spec["java"]["path"],
        "-XX:-UsePerfData",
        f"-Duser.home={Path(state['run_dir']) / 'home'}",
        f"-Djava.io.tmpdir={Path(state['run_dir']) / 'tmp'}",
        *spec["arguments"],
    ]
    assert command[-len(state["java_command"]) :] == state["java_command"]
    assert ("cage" in command) == (side == "client")
    observations = state["results"][0]["result"]["cases"][0]["observations"]
    assert observations == {
        "cwd": state["run_dir"],
        "inherited": None,
        "jvm_options": None,
        "pycache_prefix": state["environment"]["PYTHONPYCACHEPREFIX"],
        "dont_write_bytecode": True,
    }
    assert {p.name for p in (Path(state["run_dir"]) / "mods").iterdir()} == {
        "subject.jar",
        "test.jar",
    }
    assert (
        digest(Path(state["run_dir"]) / "mods/subject.jar") == spec["subject"]["sha256"]
    )
    assert state["environment"]["PYTHONDONTWRITEBYTECODE"] == "1"
    prefix = Path(state["environment"]["PYTHONPYCACHEPREFIX"])
    assert prefix.is_relative_to(Path(state["run_dir"]))
    assert not prefix.exists()
    if side == "client":
        assert not Path(state["display"]["runtime_dir"]).exists()
    args = cli.parser().parse_args(["packaged-runtime", str(path), "--json"])
    monkeypatch.setattr(cli, "run_packaged_runtime", lambda _path: state)
    value, _human = cli._packaged_runtime(args)
    assert value["data"]["authority"] == runtime.AUTHORITY


@pytest.mark.parametrize(
    "mode",
    [
        "early-fail",
        "missing",
        "timeout",
        "source",
        "staged",
        "template",
        "input",
        "fatal",
        "crash",
    ],
)
def test_execution_failures_never_succeed(recipe, subprocess_service, mode):
    spec, _path, save = recipe
    spec["environment"]["SQUINCH_MODE"] = mode
    if mode == "timeout":
        spec["timeout"] = 0.6
    with pytest.raises((InvestigationError, OSError)):
        runtime.run_packaged_runtime(save())
    active = active_path(Path(spec["project"]), spec["loader"])
    assert not active.exists(), "ordinary rejected runs must not retain recovery state"
    command = subprocess_service[0]["command"]
    artifact = Path(command[command.index("--output") + 1]).parent
    manifest = json.loads((artifact / "manifest.json").read_text())
    assert manifest["lifecycle"] == "failed"
    assert manifest["cleanup"] == {"complete": True, "failures": []}


def test_result_cannot_change_during_teardown(recipe, subprocess_service, monkeypatch):
    spec, _path, save = recipe
    original = owned_operation.terminate_owned_service

    def mutate(state, timeout, *, label):
        failures = original(state, timeout, label=label)
        output = Path(state["artifact_dir"]) / "results/result.json"
        value = json.loads(output.read_text())
        value["status"] = "fail"
        output.write_text(json.dumps(value))
        return failures

    monkeypatch.setattr(owned_operation, "terminate_owned_service", mutate)
    with pytest.raises(InvestigationError) as caught:
        runtime.run_packaged_runtime(save())
    assert not isinstance(caught.value, CleanupError)
    assert caught.value.details["cleanup_complete"]
    manifest = json.loads(
        (Path(caught.value.details["artifact_dir"]) / "manifest.json").read_text()
    )
    assert manifest["post_teardown_failure"]
    assert manifest["lifecycle"] == "failed"
    assert manifest["cleanup"]["complete"]
    project = Path(spec["project"])
    assert not active_path(project, spec["loader"]).exists()


def test_preparation_is_transactional_and_revalidated(
    recipe, subprocess_service, monkeypatch
):
    spec, _path, save = recipe
    original = runtime.validate_spec
    calls = 0

    def change_before_prepare(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            Path(spec["companions"][0]["path"]).write_text("changed")
        return original(path)

    monkeypatch.setattr(runtime, "validate_spec", change_before_prepare)
    before = set(runtime.RUNS_ROOT.iterdir())
    with pytest.raises(InvestigationError):
        runtime.run_packaged_runtime(save())
    assert not subprocess_service
    assert set(runtime.RUNS_ROOT.iterdir()) == before
    assert not active_path(Path(spec["project"]), spec["loader"]).exists()


def test_cleanup_failure_retains_status_and_doctor_recovery(
    recipe, subprocess_service, monkeypatch
):
    spec, _path, save = recipe
    monkeypatch.setattr(
        runtime, "_cleanup_display", lambda _state: ["controlled cleanup failure"]
    )
    with pytest.raises(CleanupError):
        runtime.run_packaged_runtime(save())
    project = Path(spec["project"])
    active = active_path(project, spec["loader"])
    state = server.load_owned_active(project, spec["loader"])
    assert state["operation"] == "packaged-runtime"
    assert state["lifecycle"] == "cleanup_failed"
    with pytest.raises(InvestigationError, match="already active"):
        runtime.run_packaged_runtime(save())
    monkeypatch.setattr(server, "service_members", lambda *_a: [])
    monkeypatch.setattr(server, "capture_service_threads", lambda *_a, **_k: None)
    monkeypatch.setattr(
        server,
        "uninterruptible_owned_threads",
        lambda *_a, **_k: {"threads": [], "inconclusive": []},
    )
    args = cli.parser().parse_args(
        ["status", "--project", str(project), "--loader", "forge", "--json"]
    )
    value, _human = cli._status(args)
    assert value["state"] == "degraded"
    monkeypatch.setattr(runtime, "_cleanup_display", lambda _state: [])
    args = cli.parser().parse_args(
        [
            "doctor",
            "--recover",
            "--project",
            str(project),
            "--loader",
            "forge",
            "--json",
        ]
    )
    value, _human = cli._doctor(args)
    assert value["data"]["cleanup"]["complete"]
    assert not active.exists()


def test_application_exit_preserves_default_cwd_and_records_nonzero(tmp_path):
    for explicit in (False, True):
        output = tmp_path / f"exit-{explicit}.json"
        child = tmp_path / "inner"
        child.mkdir(exist_ok=True)
        cwd_file = tmp_path / f"cwd-{explicit}.txt"
        command = [
            sys.executable,
            "-m",
            "squinch_minecraft_investigate.application_exit",
            "--output",
            str(output),
        ]
        if explicit:
            command.extend(["--cwd", str(child)])
        command.extend(
            [
                "--",
                sys.executable,
                "-c",
                f"import os, pathlib; pathlib.Path({str(cwd_file)!r}).write_text(os.getcwd()); raise SystemExit(9)",
            ]
        )
        result = subprocess.run(
            command,
            check=False,
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(runtime.PACKAGE_DIR / "src")},
        )
        assert result.returncode == 9
        assert json.loads(output.read_text())["exit_code"] == 9
        assert cwd_file.read_text() == str(child if explicit else tmp_path)
