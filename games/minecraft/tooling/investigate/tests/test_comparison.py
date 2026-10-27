from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from squinch_minecraft_investigate import comparison
from squinch_minecraft_investigate.errors import CleanupError, InvestigationError
from squinch_minecraft_investigate.scenario import Scenario


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Comparison Test")
    _git(repo, "config", "user.email", "comparison@example.invalid")
    (repo / "gradlew").write_text("#!/bin/sh\n")
    (repo / "gradle" / "wrapper").mkdir(parents=True)
    (repo / "gradle" / "wrapper" / "gradle-wrapper.properties").write_text(
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-test-bin.zip\n"
    )
    (repo / ".gitignore").write_text("gradle/wrapper/gradle-wrapper.jar\n")
    (repo / "behavior.txt").write_text("before\n")
    _git(
        repo,
        "add",
        "gradlew",
        "behavior.txt",
        ".gitignore",
        "gradle/wrapper/gradle-wrapper.properties",
    )
    _git(repo, "commit", "-qm", "before")
    before = _git(repo, "rev-parse", "HEAD")
    (repo / "behavior.txt").write_text("after\n")
    _git(repo, "commit", "-qam", "after")
    after = _git(repo, "rev-parse", "HEAD")
    (repo / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(
        b"local ignored wrapper bootstrap"
    )
    return repo, before, after


def _scenario(path: Path, repo: Path) -> Scenario:
    path.write_text('schema_version = 1\nname = "comparison test"\n')
    return Scenario(
        path=path,
        name="comparison test",
        project=repo,
        loader="fabric",
        launch_task="runServer",
        seed="123",
        ftf_preset=None,
        subject_source_project=None,
        datapacks=(),
        runtime_files=(),
        runtime_absent_files=(),
        subject_artifact=None,
        subject_compile_artifact=None,
        companion_artifacts=(),
        probe_compile_artifacts=(),
        probe_packs=(),
        server_properties={},
        retention="discard",
        startup_timeout=1,
        shutdown_timeout=1,
        step_timeout=1,
        probes={},
        steps=(),
        expectations={"required_mods": []},
    )


def _runner(selected: Scenario) -> dict:
    value = (selected.project / "behavior.txt").read_text().strip()
    label = selected.project.name
    return {
        "state": {
            "run_id": f"run-{label}",
            "artifact_dir": f"/artifacts/{label}",
            "started_at": "2026-08-01T00:00:00Z",
            "stopped_at": "2026-08-01T00:00:02Z",
            "finished_at": "2026-08-01T00:00:02Z",
            "cleanup": {"complete": True, "failures": []},
        },
        "steps": [
            {
                "id": "measure",
                "type": "probe",
                "state": "succeeded",
                "started_at": "2026-08-01T00:00:00Z",
                "finished_at": "2026-08-01T00:00:01Z",
                "result": {
                    "request": {
                        "run_id": f"run-{label}",
                        "request_id": f"request-{label}",
                        "timestamp": f"timestamp-{label}",
                    },
                    "result": {"state": "pass", "behavior": value, "poll_ticks": 3},
                    "terminal_state": "pass",
                },
            }
        ],
        "provenance": {
            "code": {"head": _git(selected.project, "rev-parse", "HEAD")},
            "scenario": {"sha256": "scenario-hash"},
            "datapacks": [],
            "candidate_inputs": [],
            "java": {"version": "test-java"},
            "gradle": {"distribution": "test-gradle"},
            "jvm_arguments": {},
            "mods": [],
            "launch_command": [str(selected.project / "gradlew")],
            "probe_overlay": {
                "packs": [
                    {
                        "id": "test-pack",
                        "version": "1",
                        "manifest_sha256": "a" * 64,
                        "content_sha256": "b" * 64,
                        "inputs": [],
                        "mixins": [],
                        "capabilities": [],
                    }
                ],
                "mixins": [],
                "sentinel": "TEST",
            },
        },
        "world_identity": {
            "actual_seed": 123,
            "world_dir": str(selected.project / "world"),
        },
        "ftf_preset": None,
        "scenario_summary": f"/artifacts/{label}/scenario-summary.json",
        "scenario_progress": f"/artifacts/{label}/scenario-progress.jsonl",
    }


def _roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(comparison, "STATE_ROOT", state)
    monkeypatch.setattr(comparison, "WORKTREES_ROOT", state / "worktrees")
    monkeypatch.setattr(comparison, "COMPARISONS_ROOT", state / "comparisons")


def test_normalization_ignores_transport_identity_but_diff_keeps_behavior() -> None:
    """Catches comparison noise from request identity without hiding a real measured change."""
    left = {"run_id": "one", "request_id": "a", "poll_ticks": 1, "value": 10}
    same = {"run_id": "two", "request_id": "b", "poll_ticks": 8, "value": 10}
    changed = {**same, "value": 11}

    assert comparison.normalize_result(left) == comparison.normalize_result(same)
    assert comparison.structured_diff(
        comparison.normalize_result(left), comparison.normalize_result(changed)
    ) == [{"path": "$.value", "kind": "changed", "left": 10, "right": 11}]


def test_exact_comparison_uses_detached_commits_and_removes_clean_worktrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a comparison that runs the caller's checkout or leaves baseline worktrees behind."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)

    result = comparison.run_exact_comparison(
        repo,
        before,
        after,
        _scenario(tmp_path / "scenario.toml", repo),
        scenario_runner=_runner,
    )

    assert result["equal"] is False
    assert result["left"]["commit"] == before
    assert result["right"]["commit"] == after
    assert (
        result["left"]["fingerprints"]["probe"]["sha256"]
        == result["right"]["fingerprints"]["probe"]["sha256"]
    )
    assert (
        result["left"]["fingerprints"]["input"]["sha256"]
        == result["right"]["fingerprints"]["input"]["sha256"]
    )
    assert result["equivalence"]["input_fingerprints_equal"] is True
    assert result["preserved_worktrees"] == []
    assert list((tmp_path / "state" / "worktrees").glob("compare-*")) == []
    listed = _git(repo, "worktree", "list", "--porcelain")
    assert listed.count("worktree ") == 1


def test_sparse_worktree_missing_wrapper_properties_fails_preflight(
    tmp_path: Path,
) -> None:
    repo, _, _ = _repository(tmp_path)
    worktree = tmp_path / "sparse-worktree"
    worktree.mkdir()
    (worktree / "gradlew").write_text(
        "#!/bin/sh\nexec java -classpath gradle/wrapper/gradle-wrapper.jar "
        "org.gradle.wrapper.GradleWrapperMain\n"
    )

    with pytest.raises(InvestigationError) as failure:
        comparison._prepare_gradle_wrapper_bootstrap(repo, worktree)

    assert failure.value.code == "comparison_bootstrap_missing"
    assert (
        failure.value.details["missing_path"]
        == "gradle/wrapper/gradle-wrapper.properties"
    )


def test_sparse_worktree_missing_wrapper_script_fails_preflight(
    tmp_path: Path,
) -> None:
    repo, _, _ = _repository(tmp_path)
    worktree = tmp_path / "sparse-worktree"
    worktree.mkdir()

    with pytest.raises(InvestigationError) as failure:
        comparison._prepare_gradle_wrapper_bootstrap(repo, worktree)

    assert failure.value.code == "comparison_bootstrap_missing"
    assert failure.value.details["missing_path"] == "gradlew"


def test_missing_worktree_wrapper_jar_is_staged_and_fingerprinted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches sparse comparison worktrees failing before Minecraft because an ignored wrapper JAR is absent."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)
    observed: list[bytes] = []

    def runner(selected: Scenario) -> dict:
        jar = selected.project / comparison.GRADLE_WRAPPER_JAR
        assert jar.is_file()
        observed.append(jar.read_bytes())
        return _runner(selected)

    result = comparison.run_exact_comparison(
        repo,
        before,
        after,
        _scenario(tmp_path / "scenario.toml", repo),
        scenario_runner=runner,
    )

    assert observed == [b"local ignored wrapper bootstrap"] * 2
    assert result["bootstrap_inputs"]["before"]["staged"] is True
    assert result["bootstrap_inputs"]["after"]["staged"] is True
    assert (
        result["bootstrap_inputs"]["before"]["sha256"]
        == result["bootstrap_inputs"]["after"]["sha256"]
    )
    assert result["preserved_worktrees"] == []
    assert list((tmp_path / "state" / "worktrees").glob("compare-*")) == []


def test_missing_wrapper_source_fails_before_scenario_and_cleans_worktrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches an opaque Gradle class-loading failure when no wrapper bootstrap can be staged."""
    repo, before, after = _repository(tmp_path)
    (repo / comparison.GRADLE_WRAPPER_JAR).unlink()
    _roots(tmp_path, monkeypatch)
    invoked = False

    def runner(_selected: Scenario) -> dict:
        nonlocal invoked
        invoked = True
        return {}

    with pytest.raises(InvestigationError) as failure:
        comparison.run_exact_comparison(
            repo,
            before,
            after,
            _scenario(tmp_path / "scenario.toml", repo),
            scenario_runner=runner,
        )

    assert failure.value.code == "comparison_bootstrap_missing"
    assert not invoked
    assert failure.value.details["missing_path"] == "gradle/wrapper/gradle-wrapper.jar"
    assert _git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert list((tmp_path / "state" / "worktrees").glob("compare-*")) == []


def test_failed_side_is_preserved_while_unused_clean_side_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a finally block that destroys the exact checkout needed to diagnose a failed run."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)

    def fail_before(selected: Scenario) -> dict:
        if selected.project.name == "before":
            raise InvestigationError(
                "deliberate_failure", "controlled scenario failure"
            )
        return _runner(selected)

    try:
        with pytest.raises(InvestigationError) as caught:
            comparison.run_exact_comparison(
                repo,
                before,
                after,
                _scenario(tmp_path / "scenario.toml", repo),
                scenario_runner=fail_before,
            )
        preserved = [Path(path) for path in caught.value.details["preserved_worktrees"]]
        assert len(preserved) == 1
        assert preserved[0].name == "before"
        assert preserved[0].is_dir()
        assert not preserved[0].with_name("after").exists()
    finally:
        listed = _git(repo, "worktree", "list", "--porcelain")
        for line in listed.splitlines():
            if line.startswith("worktree ") and line.removeprefix("worktree ") != str(
                repo
            ):
                _git(repo, "worktree", "remove", line.removeprefix("worktree "))


def test_unexpected_worktree_change_is_preserved_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches cleanup that force-removes diagnostic or user changes made during a comparison."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)

    def dirty_before(selected: Scenario) -> dict:
        result = _runner(selected)
        if selected.project.name == "before":
            (selected.project / "behavior.txt").write_text("unexpected change\n")
        return result

    try:
        with pytest.raises(CleanupError) as caught:
            comparison.run_exact_comparison(
                repo,
                before,
                after,
                _scenario(tmp_path / "scenario.toml", repo),
                scenario_runner=dirty_before,
            )
        preserved = [Path(path) for path in caught.value.details["preserved_worktrees"]]
        assert [path.name for path in preserved] == ["before"]
        assert (preserved[0] / "behavior.txt").read_text() == "unexpected change\n"
    finally:
        listed = _git(repo, "worktree", "list", "--porcelain")
        for line in listed.splitlines():
            if line.startswith("worktree ") and line.removeprefix("worktree ") != str(
                repo
            ):
                path = Path(line.removeprefix("worktree "))
                (path / "behavior.txt").write_text("before\n")
                _git(repo, "worktree", "remove", str(path))


@pytest.mark.parametrize(
    ("drift", "error_code"),
    (("probe", "comparison_probe_mismatch"), ("input", "comparison_input_mismatch")),
)
def test_comparison_rejects_nonidentical_probe_or_scenario_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
    error_code: str,
) -> None:
    """Catches an apparent code comparison that silently changes its probe or scenario input."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)

    def drifting_runner(selected: Scenario) -> dict:
        result = _runner(selected)
        if selected.project.name == "after":
            if drift == "probe":
                result["provenance"]["probe_overlay"]["packs"][0]["content_sha256"] = (
                    "c" * 64
                )
            else:
                result["world_identity"]["actual_seed"] = 456
        return result

    with pytest.raises(InvestigationError) as caught:
        comparison.run_exact_comparison(
            repo,
            before,
            after,
            _scenario(tmp_path / "scenario.toml", repo),
            scenario_runner=drifting_runner,
        )

    assert caught.value.code == error_code
    assert caught.value.details["preserved_worktrees"] == []
    assert _git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
