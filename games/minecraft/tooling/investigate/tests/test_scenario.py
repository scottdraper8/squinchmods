from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import squinch_minecraft_investigate.scenario as scenario_module
from squinch_minecraft_investigate import server
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
from squinch_minecraft_investigate.processes import port_is_free
from squinch_minecraft_investigate.scenario import (
    _candidate_coordinates,
    _fatal_log_pattern,
    _java_seed,
    _measurement_summary,
    load_scenario,
    parse_mod_list,
    run_scenario,
)


def test_fatal_log_policy_distinguishes_terminal_failures_from_recoverable_errors() -> None:
    assert _fatal_log_pattern(
        "[Server thread/ERROR] Too many chained neighbor updates. Skipping the rest."
    ) is None
    assert _fatal_log_pattern("Exception in server tick loop") is not None
    assert _fatal_log_pattern("---- Minecraft Crash Report ----") is not None


def test_cell_scan_candidates_become_unique_floor_correct_chunks(tmp_path: Path) -> None:
    """Catches negative-coordinate truncation and duplicate shortlist generation."""
    path = tmp_path / "cell-scan-result.json"
    path.write_text(
        json.dumps(
            {
                "scan": {
                    "top_candidates": [
                        {"x": -0.25, "z": -0.25},
                        {"x": -15.5, "z": -1.0},
                        {"x": 16.0, "z": 32.0},
                    ]
                }
            }
        )
    )

    assert _candidate_coordinates(path, 4) == [
        {"block_x": -1, "block_z": -1, "chunk_x": -1, "chunk_z": -1},
        {"block_x": 16, "block_z": 32, "chunk_x": 1, "chunk_z": 2},
    ]


def _write_scenario(path: Path, project: str = "games/minecraft/project", *, authority: str = "generation") -> None:
    path.write_text(
        f'''schema_version = 1
name = "relative-path-control"
project = "{project}"
loader = "fabric"
seed = 12345
datapacks = ["games/minecraft/investigations/fixture.zip"]
retention = "discard"

[server_properties]
view-distance = 4

[timeouts]
startup = 10
shutdown = 2
step = 3

[expectations]
required_mods = []

[[probes]]
id = "finished-chunk"
version = "1"
config_file = "games/minecraft/investigations/probe.json"

[[steps]]
id = "generate"
type = "generate"
unit = "chunk"
bounds = [0, 0, 16, 16]
authority = "{authority}"
terminal_probe = "finished-chunk"
expect = {{ region_count = 4 }}
''',
        encoding="utf-8",
    )


def test_scenario_paths_resolve_from_toml_not_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches invocation-directory-dependent project, datapack, and probe config resolution."""
    project = tmp_path / "games/minecraft/project"
    project.mkdir(parents=True)
    assets = tmp_path / "games/minecraft/investigations"
    assets.mkdir(parents=True)
    (assets / "fixture.zip").write_bytes(b"datapack")
    (assets / "probe.json").write_text('{"radius": 4}\n')
    scenario_path = tmp_path / ".squinch/scenario.toml"
    scenario_path.parent.mkdir()
    _write_scenario(scenario_path, authority="finished-chunk")
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    scenario = load_scenario(scenario_path)

    assert scenario.project == project.resolve()
    assert scenario.datapacks == ((assets / "fixture.zip").resolve(),)
    assert scenario.probes["finished-chunk"].config == {"radius": 4}
    assert scenario.steps[0].values["bounds"] == [0, 0, 16, 16]


def test_production_launch_task_is_explicit_and_loader_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "games/minecraft/project"
    project.mkdir(parents=True)
    assets = tmp_path / "games/minecraft/investigations"
    assets.mkdir(parents=True)
    (assets / "fixture.zip").write_bytes(b"datapack")
    (assets / "probe.json").write_text("{}\n")
    scenario_path = tmp_path / ".squinch/production.toml"
    scenario_path.parent.mkdir()
    _write_scenario(scenario_path)
    scenario_path.write_text(
        scenario_path.read_text().replace(
            'loader = "fabric"', 'loader = "fabric"\nlaunch_task = "prodServer"'
        )
    )
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)

    assert load_scenario(scenario_path).launch_task == "prodServer"

    scenario_path.write_text(scenario_path.read_text().replace('loader = "fabric"', 'loader = "neoforge"'))
    assert load_scenario(scenario_path).launch_task == "prodServer"

    scenario_path.write_text(scenario_path.read_text().replace('loader = "neoforge"', 'loader = "forge"'))
    with pytest.raises(InvestigationError, match="requires Fabric or NeoForge"):
        load_scenario(scenario_path)


def test_local_subject_artifact_is_repository_scoped_and_typed_as_a_jar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "games/minecraft/project"
    project.mkdir(parents=True)
    assets = tmp_path / "games/minecraft/investigations"
    assets.mkdir(parents=True)
    (assets / "fixture.zip").write_bytes(b"datapack")
    (assets / "probe.json").write_text("{}\n")
    subject = project / "build/libs/subject.jar"
    subject.parent.mkdir(parents=True)
    subject.write_bytes(b"jar")
    subject_compile = project / "build/libs/subject-named.jar"
    subject_compile.write_bytes(b"named jar")
    scenario_path = tmp_path / ".squinch/subject.toml"
    scenario_path.parent.mkdir()
    _write_scenario(scenario_path)
    scenario_path.write_text(
        scenario_path.read_text().replace(
            'seed = 12345',
            'seed = 12345\n'
            'subject_artifact = "games/minecraft/project/build/libs/subject.jar"\n'
            'subject_compile_artifact = "games/minecraft/project/build/libs/subject-named.jar"\n'
            'probe_compile_artifacts = [{ id = "api", loader = "neoforge", mapping = "named" }]',
        )
    )
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)

    loaded = load_scenario(scenario_path)
    assert loaded.subject_artifact == subject.resolve()
    assert loaded.subject_compile_artifact == subject_compile.resolve()
    assert loaded.probe_compile_artifacts[0].artifact_id == "api"
    assert loaded.probe_compile_artifacts[0].loader == "neoforge"
    assert loaded.probe_compile_artifacts[0].mapping == "named"

    scenario_path.write_text(scenario_path.read_text().replace("subject.jar", "subject.zip"))
    with pytest.raises(InvestigationError, match="must be a repository-root-relative JAR"):
        load_scenario(scenario_path)


def test_runtime_files_are_repository_inputs_confined_to_run_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "games/minecraft/project"
    project.mkdir(parents=True)
    inputs = tmp_path / "games/minecraft/investigations"
    inputs.mkdir(parents=True)
    config = inputs / "terrablender.toml"
    config.write_text("[general]\noverworld_region_size = 2\n")
    scenario_path = tmp_path / ".squinch/runtime-file.toml"
    scenario_path.parent.mkdir()
    scenario_path.write_text(
        '''schema_version = 1
name = "runtime-file-control"
project = "games/minecraft/project"
loader = "fabric"
seed = 1
runtime_absent_files = ["config/generated-on-first-start.json"]

[[runtime_files]]
source = "games/minecraft/investigations/terrablender.toml"
target = "config/terrablender.toml"

[[steps]]
id = "list"
type = "command"
command = "list"
'''
    )
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)

    loaded = load_scenario(scenario_path)
    assert loaded.runtime_files == ((config.resolve(), "config/terrablender.toml"),)
    assert loaded.runtime_absent_files == ("config/generated-on-first-start.json",)

    scenario_path.write_text(
        scenario_path.read_text().replace(
            'target = "config/terrablender.toml"', 'target = "../terrablender.toml"'
        )
    )
    with pytest.raises(InvestigationError, match="must be a config/ path"):
        load_scenario(scenario_path)


def test_finished_chunk_authority_requires_selected_terminal_probe(tmp_path: Path) -> None:
    """Negative control: force-load acknowledgment must not be mislabeled finished-chunk proof."""
    scenario_path = tmp_path / "scenario.toml"
    scenario_path.write_text(
        '''schema_version = 1
name = "invalid-authority"
project = "games/minecraft/project"
loader = "fabric"
seed = 1

[[steps]]
id = "generate"
type = "generate"
unit = "chunk"
bounds = [0, 0, 0, 0]
authority = "finished-chunk"
'''
    )

    with pytest.raises(InvestigationError, match="requires a selected terminal_probe"):
        load_scenario(scenario_path)


def test_repeated_generation_requires_disjoint_windows_and_retains_every_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches benchmark repetitions regenerating the same chunks or hiding an outlier in a mean."""
    scenario_path = tmp_path / ".squinch/scenario.toml"
    scenario_path.parent.mkdir()
    assets = tmp_path / "games/minecraft/investigations"
    assets.mkdir(parents=True)
    (assets / "fixture.zip").write_bytes(b"fixture")
    (assets / "probe.json").write_text("{}\n")
    _write_scenario(scenario_path)
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    text = scenario_path.read_text().replace(
        "terminal_probe = \"finished-chunk\"",
        'terminal_probe = "finished-chunk"\nrepeat = 3\noffset = [17, 0]\njfr = true',
    )
    scenario_path.write_text(text)

    scenario = load_scenario(scenario_path)
    values = scenario.steps[0].values
    assert values["repeat"] == 3
    assert values["offset"] == [17, 0]
    assert values["jfr"] is True
    assert values["release_after_observation"] is False
    summary = _measurement_summary(
        [
            {"timing": {"generation_seconds": value, "probe_seconds": 0.1, "total_seconds": value + 0.1}}
            for value in (1.0, 9.0, 2.0)
        ]
    )
    assert summary["metrics"]["generation_seconds"] == {
        "observations": [1.0, 9.0, 2.0],
        "median": 2.0,
        "min": 1.0,
        "max": 9.0,
        "range": 8.0,
    }

    scenario_path.write_text(text.replace("offset = [17, 0]", "offset = [16, 0]"))
    with pytest.raises(InvestigationError, match="overlapping windows"):
        load_scenario(scenario_path)

    scenario_path.write_text(text.replace("jfr = true", 'release_after_observation = "yes"'))
    with pytest.raises(InvestigationError, match="release_after_observation must be a boolean"):
        load_scenario(scenario_path)


def test_seed_derivation_matches_minecraft_numeric_and_java_string_rules() -> None:
    """Catches comparing Minecraft's numeric seed response directly with a textual seed input."""
    assert _java_seed("-9223372036854775808") == -(2**63)
    assert _java_seed("9223372036854775807") == 2**63 - 1
    assert _java_seed("hello") == 99162322
    assert _java_seed("9223372036854775808") == -1773151197


def test_real_loader_log_shapes_produce_exact_runtime_mod_identities() -> None:
    """Catches provenance that records build declarations instead of the loader's actual mod list."""
    fabric = """[main/INFO] (FabricLoader) Loading 2 mods:
\t- minecraft 1.21.1
\t- reterraforged 0.0.6005
[main/INFO] (Minecraft) Starting server
"""
    fabric_production = """[02:03:32] [main/INFO]: Loading 2 mods:
\t- minecraft 1.21.1
\t- reterraforged 0.0.6005
[02:03:33] [main/INFO]: Starting minecraft server version 1.21.1
"""
    neoforge = """[main/INFO] (ModDiscoverer)
     Mod List:
        Name Version (Mod Id)
        Minecraft 1.21.1 (minecraft)
        ReTerraForged 0.0.6005 (reterraforged)
[main/INFO] (LaunchServiceHandler) Launching target 'forgeserverdev'
"""

    assert parse_mod_list(fabric, "fabric") == [
        {"id": "minecraft", "version": "1.21.1"},
        {"id": "reterraforged", "version": "0.0.6005"},
    ]
    assert parse_mod_list(fabric_production, "fabric") == [
        {"id": "minecraft", "version": "1.21.1"},
        {"id": "reterraforged", "version": "0.0.6005"},
    ]
    assert [item["id"] for item in parse_mod_list(neoforge, "neoforge")] == [
        "minecraft",
        "reterraforged",
    ]


@pytest.mark.slow
def test_failed_scenario_assertion_runs_finally_cleanup_and_preserves_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a failed step returning early and stranding its process, listener, or world."""
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    profile = {"path": "/retained/profile.jfr", "size": 42, "sha256": "a" * 64}
    monkeypatch.setattr(scenario_module, "start_jfr", lambda *_args: object())
    monkeypatch.setattr(scenario_module, "stop_jfr", lambda *_args: profile)
    project = tmp_path / "games/minecraft/project"
    run_dir = project / "fabric" / "run"
    run_dir.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew = project / "gradlew"
    gradlew.write_text(f"#!/usr/bin/env bash\nexec python3 {fixture!s}\n")
    gradlew.chmod(0o644)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Scenario Test"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.email", "scenario@example.invalid"], cwd=project, check=True
    )
    subprocess.run(["git", "add", "gradlew"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)
    (project / "untracked-input.txt").write_text("must affect provenance\n")

    scenario_path = tmp_path / ".squinch/failure.toml"
    scenario_path.parent.mkdir()
    scenario_path.write_text(
        f'''schema_version = 1
name = "assertion-cleanup-control"
project = "games/minecraft/project"
loader = "fabric"
seed = 12345
retention = "discard"

[timeouts]
startup = 10
shutdown = 2
step = 2

[[steps]]
id = "failing-expectation"
type = "command"
command = "list"
jfr = true
expect = {{ response_contains = "deliberately absent" }}
'''
    )
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")
    with pytest.raises(InvestigationError) as caught:
        run_scenario(load_scenario(scenario_path))

    assert caught.value.code == "assertion_failed"
    assert not (state_root / "active.json").exists()
    artifact_dir = Path(caught.value.details["artifact_dir"])
    manifest = json.loads((artifact_dir / "manifest.json").read_text())
    assert manifest["cleanup"]["complete"] is True
    assert manifest["profile_artifacts"] == [profile]
    assert manifest["retained_world"] is None
    assert not Path(manifest["world_dir"]).exists()
    assert port_is_free(manifest["ports"]["server"])
    assert port_is_free(manifest["ports"]["rcon"])
    provenance = json.loads((artifact_dir / "provenance.json").read_text())
    assert provenance["code"]["dirty"] is True
    assert provenance["code"]["untracked"][0]["path"] == "untracked-input.txt"
    summary = json.loads((artifact_dir / "scenario-summary.json").read_text())
    assert summary["state"] == "failed"
    assert summary["error"]["code"] == "assertion_failed"
    assert summary["cleanup"]["complete"] is True
    progress = [
        json.loads(line)
        for line in (artifact_dir / "scenario-progress.jsonl").read_text().splitlines()
    ]
    assert progress[-1]["event"] == "cleanup-finished"
    assert progress[-1]["cleanup"]["complete"] is True


@pytest.mark.slow
def test_generation_timeout_runs_finally_without_leaking_world_or_listener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a timed-out force-load command bypassing scenario cleanup or claiming generation."""
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    profile = {"path": "/retained/timeout.jfr", "size": 42, "sha256": "b" * 64}
    monkeypatch.setattr(scenario_module, "start_jfr", lambda *_args: object())
    monkeypatch.setattr(scenario_module, "stop_jfr", lambda *_args: profile)
    project = tmp_path / "games/minecraft/project"
    (project / "fabric" / "run").mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew = project / "gradlew"
    gradlew.write_text(f"#!/usr/bin/env bash\nexec python3 {fixture!s}\n")
    gradlew.chmod(0o644)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Timeout Test"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.email", "timeout@example.invalid"], cwd=project, check=True
    )
    subprocess.run(["git", "add", "gradlew"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)

    scenario_path = tmp_path / ".squinch/generation-timeout.toml"
    scenario_path.parent.mkdir()
    scenario_path.write_text(
        f'''schema_version = 1
name = "generation-timeout-control"
project = "games/minecraft/project"
loader = "fabric"
seed = 12345
retention = "discard"

[server_properties]
fake-child-ignore-term = false
fake-delay-command-prefix = "forceload add"
fake-command-delay = 0.3

[timeouts]
startup = 10
shutdown = 2
step = 0.05

[[steps]]
id = "timed-out-generation"
type = "generate"
unit = "chunk"
bounds = [0, 0, 0, 0]
jfr = true
'''
    )
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    with pytest.raises(InvestigationError) as caught:
        run_scenario(load_scenario(scenario_path))

    assert caught.value.code == "rcon_failed"
    assert not (state_root / "active.json").exists()
    artifact_dir = Path(caught.value.details["artifact_dir"])
    manifest = json.loads((artifact_dir / "manifest.json").read_text())
    assert manifest["cleanup"]["complete"] is True
    assert manifest["profile_artifacts"] == [profile]
    assert manifest["forceload_regions"] == []
    assert manifest["retained_world"] is None
    assert not Path(manifest["world_dir"]).exists()
    assert port_is_free(manifest["ports"]["server"])
    assert port_is_free(manifest["ports"]["rcon"])
    summary = json.loads((artifact_dir / "scenario-summary.json").read_text())
    assert summary["state"] == "failed"
    assert summary["error"]["code"] == "rcon_failed"
    assert summary["steps"] == []


@pytest.mark.slow
def test_cleanup_failure_with_succeeded_steps_returns_data_not_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Steps succeeded but shutdown cleanup failed. The run must return normally
    with all step data intact and a cleanup_failed key, not raise CleanupError."""
    monkeypatch.setattr(scenario_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(scenario_module, "start_jfr", lambda *_args: None)
    monkeypatch.setattr(scenario_module, "stop_jfr", lambda *_args: None)
    project = tmp_path / "games/minecraft/project"
    (project / "fabric" / "run").mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "fake_gradle_server.py"
    gradlew = project / "gradlew"
    gradlew.write_text(f"#!/usr/bin/env bash\nexec python3 {fixture!s}\n")
    gradlew.chmod(0o644)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Cleanup Test"], cwd=project, check=True)
    subprocess.run(
        ["git", "config", "user.email", "cleanup@example.invalid"], cwd=project, check=True
    )
    subprocess.run(["git", "add", "gradlew"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=project, check=True)

    scenario_path = tmp_path / ".squinch/cleanup-failure.toml"
    scenario_path.parent.mkdir()
    scenario_path.write_text(
        '''schema_version = 1
name = "cleanup-failure-control"
project = "games/minecraft/project"
loader = "fabric"
seed = 12345
retention = "discard"

[server_properties]
fake-child-ignore-term = false
fake-delay-command-prefix = "save-all"
fake-command-delay = 2.0

[timeouts]
startup = 10
shutdown = 0.5
step = 2

[[steps]]
id = "passing-list"
type = "command"
command = "list"
'''
    )
    state_root = tmp_path / "state"
    monkeypatch.setattr(server, "RUNS_ROOT", state_root / "runs")
    monkeypatch.setattr(server, "active_path", lambda _project, _loader: state_root / "active.json")
    monkeypatch.setattr(server, "lock_path", lambda _project, _loader: state_root / "lock")

    result = run_scenario(load_scenario(scenario_path))

    assert result["cleanup_failed"] is not None
    assert result["cleanup_failed"]["code"] == "cleanup_failed"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["state"] == "succeeded"
    assert result["world_identity"]["actual_seed"] == result["world_identity"]["expected_seed"]
    artifact_dir = Path(result["state"]["artifact_dir"])
    summary = json.loads((artifact_dir / "scenario-summary.json").read_text())
    assert summary["state"] == "failed"
    assert summary["error"]["code"] == "cleanup_failed"
