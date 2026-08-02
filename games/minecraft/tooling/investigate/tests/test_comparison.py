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
    (repo / "behavior.txt").write_text("before\n")
    _git(repo, "add", "gradlew", "behavior.txt")
    _git(repo, "commit", "-qm", "before")
    before = _git(repo, "rev-parse", "HEAD")
    (repo / "behavior.txt").write_text("after\n")
    _git(repo, "commit", "-qam", "after")
    return repo, before, _git(repo, "rev-parse", "HEAD")


def _scenario(path: Path, repo: Path) -> Scenario:
    path.write_text('schema_version = 1\nname = "comparison test"\n')
    return Scenario(
        path=path,
        name="comparison test",
        project=repo,
        loader="fabric",
        seed="123",
        rtf_fixture=None,
        rtf_ephemeral=None,
        datapacks=(),
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
        "world_identity": {"actual_seed": 123, "world_dir": str(selected.project / "world")},
        "rtf_fixture": None,
        "rtf_ephemeral_preset": None,
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
        repo, before, after, _scenario(tmp_path / "scenario.toml", repo), scenario_runner=_runner
    )

    assert result["equal"] is False
    assert result["left"]["commit"] == before
    assert result["right"]["commit"] == after
    assert result["left"]["fingerprints"]["probe"]["sha256"] == result["right"]["fingerprints"]["probe"]["sha256"]
    assert result["left"]["fingerprints"]["input"]["sha256"] == result["right"]["fingerprints"]["input"]["sha256"]
    assert result["equivalence"]["input_fingerprints_equal"] is True
    assert result["preserved_worktrees"] == []
    assert list((tmp_path / "state" / "worktrees").glob("compare-*")) == []
    listed = _git(repo, "worktree", "list", "--porcelain")
    assert listed.count("worktree ") == 1


def test_failed_side_is_preserved_while_unused_clean_side_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a finally block that destroys the exact checkout needed to diagnose a failed run."""
    repo, before, after = _repository(tmp_path)
    _roots(tmp_path, monkeypatch)

    def fail_before(selected: Scenario) -> dict:
        if selected.project.name == "before":
            raise InvestigationError("deliberate_failure", "controlled scenario failure")
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
            if line.startswith("worktree ") and line.removeprefix("worktree ") != str(repo):
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
            if line.startswith("worktree ") and line.removeprefix("worktree ") != str(repo):
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
                result["provenance"]["probe_overlay"]["packs"][0]["content_sha256"] = "c" * 64
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
