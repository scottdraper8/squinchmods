from __future__ import annotations

import signal
import subprocess

import pytest
from squinch_minecraft_investigate import processes
from squinch_minecraft_investigate.errors import InvestigationError


def _stat_record(
    pid: int, state: str, *, ppid: int, pgrp: int, session: int, start_ticks: int
) -> str:
    fields = [state, str(ppid), str(pgrp), str(session), *(["0"] * 16)]
    fields[19] = str(start_ticks)
    return f"{pid} (test-thread) " + " ".join(fields)


def _thread_identity(
    proc_root, tid: int, state: str, *, start_ticks: int = 101
) -> dict:
    task_dir = proc_root / str(tid)
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "stat").write_text(
        _stat_record(tid, state, ppid=1, pgrp=100, session=100, start_ticks=start_ticks)
    )
    return {
        "pid": tid,
        "ppid": 1,
        "pgrp": 100,
        "session": 100,
        "start_ticks": start_ticks,
        "state": "S",
    }


def test_owned_thread_inspection_detects_captured_d_state_thread(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _thread_identity(tmp_path, 102, "D")
    monkeypatch.setattr(processes, "PROC_ROOT", tmp_path)

    result = processes.uninterruptible_owned_threads(
        [expected], timeout=1.0, confirmation_seconds=0.0
    )

    assert result == {
        "threads": [
            {
                "pid": 102,
                "tid": 102,
                "ppid": 1,
                "pgrp": 100,
                "session": 100,
                "start_ticks": 101,
                "state": "D",
            }
        ],
        "inconclusive": [],
    }


def test_owned_thread_inspection_rejects_reused_tid(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _thread_identity(tmp_path, 102, "D", start_ticks=101)
    _thread_identity(tmp_path, 102, "D", start_ticks=202)
    monkeypatch.setattr(processes, "PROC_ROOT", tmp_path)

    result = processes.uninterruptible_owned_threads(
        [expected], timeout=1.0, confirmation_seconds=0.0
    )

    assert result == {"threads": [], "inconclusive": []}


def test_owned_thread_inspection_does_not_report_a_transient_d_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _thread_identity(tmp_path, 102, "D")
    monkeypatch.setattr(processes, "PROC_ROOT", tmp_path)

    def resolve_transient_state(_seconds: float) -> None:
        (tmp_path / "102" / "stat").write_text(
            _stat_record(102, "S", ppid=1, pgrp=100, session=100, start_ticks=101)
        )

    monkeypatch.setattr(processes.time, "sleep", resolve_transient_state)
    result = processes.uninterruptible_owned_threads(
        [expected], timeout=1.0, confirmation_seconds=0.01
    )

    assert result == {"threads": [], "inconclusive": []}


def test_cgroup_thread_capture_is_scoped_and_skips_known_ids(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cgroup_root = tmp_path / "cgroups"
    cgroup = cgroup_root / "service"
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.threads").write_text("101\n102\n103\n")
    _thread_identity(tmp_path / "proc", 102, "S")
    _thread_identity(tmp_path / "proc", 103, "S")
    monkeypatch.setattr(processes, "CGROUP_ROOT", cgroup_root)
    monkeypatch.setattr(processes, "PROC_ROOT", tmp_path / "proc")

    result = processes.service_thread_members(
        {"cgroup": "/service"},
        known_threads={103: _thread_identity(tmp_path / "proc", 103, "S")},
        process_ids={101},
        timeout=1.0,
    )

    assert [item["pid"] for item in result["threads"]] == [102]
    assert result["inconclusive"] == []


def test_owned_thread_inspection_reports_unreadable_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "pid": 102,
        "ppid": 1,
        "pgrp": 100,
        "session": 100,
        "start_ticks": 101,
        "state": "S",
    }
    calls = 0

    def read_identity(_tid: int) -> tuple[dict | None, str | None]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {**expected, "state": "D"}, None
        return None, "TimeoutError: blocked procfs read"

    monkeypatch.setattr(processes, "proc_identity_result", read_identity)
    monkeypatch.setattr(processes.time, "sleep", lambda _seconds: None)

    result = processes.uninterruptible_owned_threads(
        [expected], timeout=1.0, confirmation_seconds=0.0
    )

    assert result["threads"] == [{**expected, "state": "D", "tid": 102}]
    assert result["inconclusive"] == [
        "could not confirm owned thread 102: TimeoutError: blocked procfs read"
    ]


def test_cgroup_thread_capture_reports_unreadable_thread_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cgroup_root = tmp_path / "cgroups"
    cgroup = cgroup_root / "service"
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.threads").write_text("102\n")
    monkeypatch.setattr(processes, "CGROUP_ROOT", cgroup_root)
    monkeypatch.setattr(
        processes,
        "proc_identity_result",
        lambda _tid: (None, "TimeoutError: blocked procfs read"),
    )

    result = processes.service_thread_members(
        {"cgroup": "/service"}, known_threads={}, process_ids=set(), timeout=1.0
    )

    assert result == {
        "threads": [],
        "inconclusive": [
            "could not inspect owned thread 102: TimeoutError: blocked procfs read"
        ],
    }


def test_cgroup_thread_capture_requires_membership_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cgroup_root = tmp_path / "cgroups"
    (cgroup_root / "service").mkdir(parents=True)
    monkeypatch.setattr(processes, "CGROUP_ROOT", cgroup_root)

    result = processes.service_thread_members(
        {"cgroup": "/service"}, known_threads={}, process_ids=set(), timeout=1.0
    )

    assert result == {
        "threads": [],
        "inconclusive": ["owned cgroup exposes no cgroup.threads membership file"],
    }


def test_disappeared_owned_cgroup_is_empty_even_after_the_time_budget_expires(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cgroup_root = tmp_path / "cgroups"
    cgroup_root.mkdir()
    monkeypatch.setattr(processes, "CGROUP_ROOT", cgroup_root)

    result = processes.service_thread_members(
        {"cgroup": "/service"},
        known_threads={},
        process_ids=set(),
        timeout=0,
    )

    assert result == {"threads": [], "inconclusive": [], "cgroup_gone": True}


def test_cgroup_thread_capture_stops_when_the_global_budget_expires(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cgroup_root = tmp_path / "cgroups"
    cgroup = cgroup_root / "service"
    cgroup.mkdir(parents=True)
    (cgroup / "cgroup.threads").write_text("102\n")
    monkeypatch.setattr(processes, "CGROUP_ROOT", cgroup_root)
    clock = [0.0]

    def monotonic() -> float:
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr(processes.time, "monotonic", monotonic)

    result = processes.service_thread_members(
        {"cgroup": "/service"},
        known_threads={},
        process_ids=set(),
        timeout=0.5,
    )

    assert result == {
        "threads": [],
        "inconclusive": ["owned cgroup thread enumeration exceeded its time budget"],
    }


def test_signal_service_accepts_naturally_removed_transient_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        processes,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "Failed to kill unit: Unit squinch-mc-run.service not loaded."
        ),
    )

    processes.signal_service({"unit": "squinch-mc-run.service"}, signal.SIGTERM)


def test_signal_service_preserves_real_systemd_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        processes,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 1, "", "Access denied"
        ),
    )

    with pytest.raises(InvestigationError, match="Access denied"):
        processes.signal_service({"unit": "squinch-mc-run.service"}, signal.SIGTERM)
