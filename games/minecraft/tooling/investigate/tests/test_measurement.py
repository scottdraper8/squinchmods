from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from squinch_minecraft_investigate.errors import InvestigationError
from squinch_minecraft_investigate.measurement import (
    capture_measurement_files,
    extract_metrics,
    snapshot_measurement_files,
    wait_for_measurement,
)


def test_wait_capture_and_extract_metric(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log_path = run_dir / "server.log"
    log_path.write_text("old completion\n", encoding="utf-8")
    report = run_dir / "reports" / "result.txt"
    report.parent.mkdir()
    report.write_text("old=1\n", encoding="utf-8")
    before = snapshot_measurement_files(run_dir, ["reports/result.txt"])
    log_start = log_path.stat().st_size

    def produce() -> None:
        time.sleep(0.1)
        report.write_text("wall_seconds=12.5\nchunks=1000\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as output:
            output.write("benchmark complete\n")

    thread = threading.Thread(target=produce)
    thread.start()
    result = wait_for_measurement(
        log_path=log_path,
        log_start=log_start,
        run_dir=run_dir,
        capture_files=["reports/result.txt"],
        before_files=before,
        wait_for_log=r"benchmark complete",
        fail_on_log=[r"benchmark failed"],
        timeout=3,
        health_check=lambda: None,
    )
    thread.join()

    assert result["completion_match"] == "benchmark complete"
    assert "old completion" not in result["log_text"]
    captured = capture_measurement_files(
        run_dir, tmp_path / "artifacts", ["reports/result.txt"]
    )
    assert captured[0]["sha256"]
    metrics = extract_metrics(
        [
            {
                "id": "wall_seconds",
                "source": "reports/result.txt",
                "pattern": r"wall_seconds=([0-9.]+)",
                "group": 1,
                "value_type": "float",
                "unit": "seconds",
            },
            {
                "id": "completion",
                "source": "server.log",
                "pattern": r"(benchmark complete)",
                "group": 1,
                "value_type": "string",
                "unit": None,
            },
        ],
        run_dir=run_dir,
        command_log=result["log_text"],
    )
    assert metrics["wall_seconds"]["value"] == 12.5
    assert metrics["completion"]["value"] == "benchmark complete"


def test_extract_metrics_supports_optional_all_matches_and_grouped_numbers(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    report = run_dir / "result.txt"
    report.write_text(
        "worker=a work=1,234.5\nworker=b work=987.0\n",
        encoding="utf-8",
    )

    metrics = extract_metrics(
        [
            {
                "id": "worker_names",
                "source": "result.txt",
                "pattern": r"worker=([^ ]+)",
                "group": 1,
                "value_type": "string",
                "unit": None,
                "match": "all",
            },
            {
                "id": "worker_milliseconds",
                "source": "result.txt",
                "pattern": r"work=([0-9,.]+)",
                "group": 1,
                "value_type": "float",
                "unit": "milliseconds",
                "match": "all",
            },
            {
                "id": "optional_missing",
                "source": "result.txt",
                "pattern": r"missing=([0-9]+)",
                "group": 1,
                "value_type": "int",
                "unit": None,
                "required": False,
            },
        ],
        run_dir=run_dir,
        command_log="",
    )

    assert metrics["worker_names"]["value"] == ["a", "b"]
    assert metrics["worker_milliseconds"]["value"] == [1234.5, 987.0]
    assert metrics["worker_milliseconds"]["count"] == 2
    assert "optional_missing" not in metrics


def test_wait_fails_on_configured_log_marker(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log_path = run_dir / "server.log"
    log_path.write_text("", encoding="utf-8")

    def produce() -> None:
        time.sleep(0.05)
        log_path.write_text("benchmark failed: cycle\n", encoding="utf-8")

    thread = threading.Thread(target=produce)
    thread.start()
    with pytest.raises(InvestigationError) as caught:
        wait_for_measurement(
            log_path=log_path,
            log_start=0,
            run_dir=run_dir,
            capture_files=[],
            before_files={},
            wait_for_log=r"benchmark complete",
            fail_on_log=[r"benchmark failed"],
            timeout=3,
            health_check=lambda: None,
        )
    thread.join()
    assert caught.value.code == "measurement_failed"


def test_capture_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvestigationError) as caught:
        snapshot_measurement_files(tmp_path, ["../escape.txt"])
    assert caught.value.code == "invalid_measurement_path"
