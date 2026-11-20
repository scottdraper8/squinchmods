import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from squinch_nms_investigate import portal
from squinch_nms_investigate.errors import InvestigationError


@pytest.mark.parametrize("timeout", [-1.0, 0.0, 600.01, float("inf"), float("nan")])
def test_timeout_rejected_before_observation(tmp_path, timeout):
    armed = Mock()
    with pytest.raises(InvestigationError) as error:
        portal.observe(tmp_path, timeout, armed)
    assert error.value.code == "invalid_timeout"
    armed.assert_not_called()


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(portal.platform, "system", lambda: "Linux")
    monkeypatch.setattr(portal.platform, "machine", lambda: "x86_64")


@pytest.mark.parametrize(
    ("digest", "processes", "code"),
    [
        ("different", [{"pid": 31}], "unsupported_portal_trace_build"),
        (portal._IMAGE_SHA256, [], "portal_client_unavailable"),
        (portal._IMAGE_SHA256, [{"pid": 31}, {"pid": 32}], "portal_client_unavailable"),
    ],
)
def test_rejects_unverified_build_or_ambiguous_client(
    linux, monkeypatch, tmp_path, digest, processes, code
):
    counter = Mock()
    armed = Mock()
    monkeypatch.setattr(portal, "sha256_file", lambda executable: digest)
    monkeypatch.setattr(portal, "running_processes", lambda: processes)
    monkeypatch.setattr(portal, "_execution_counter", counter)
    with pytest.raises(InvestigationError) as error:
        portal.observe(tmp_path, 600, armed)
    assert error.value.code == code
    armed.assert_not_called()
    counter.assert_not_called()


@pytest.mark.parametrize("corruption", [None, "header", "opcode", "target", "permissions"])
def test_relocated_image_requires_executable_calls_to_both_expected_targets(
    tmp_path, monkeypatch, corruption
):
    source = tmp_path / "NMS.exe"
    header = b"MZ" + bytes(126)
    source.write_bytes(header)
    pid = 37
    proc = tmp_path / str(pid)
    proc.mkdir()
    monkeypatch.setattr(portal, "_PROC", tmp_path)
    monkeypatch.setattr(portal, "_SITES", {"first": (0x100, 0x106), "second": (0x120, 0x124)})
    pe = SimpleNamespace(OPTIONAL_HEADER=SimpleNamespace(ImageBase=0x1000), close=Mock())
    monkeypatch.setattr(portal.pefile, "PE", lambda *args, **kwargs: pe)
    stat = source.stat()
    device = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}"
    perms = "r--p" if corruption == "permissions" else "r-xp"
    (proc / "maps").write_text(f"4000-5000 {perms} 00000000 {device} {stat.st_ino} {source}\n")
    with (proc / "mem").open("wb") as memory:
        memory.seek(0x4000)
        memory.write(bytes(128) if corruption == "header" else header)
        memory.seek(0x4100)
        memory.write(b"\xe8\x01\x00\x00\x00")
        memory.seek(0x4120)
        # A call to 0x4124 from 0x4120 has a signed displacement of -1.
        memory.write(b"\xe9" if corruption == "opcode" else b"\xe8")
        memory.write(bytes(4) if corruption == "target" else b"\xff" * 4)
    if corruption is None:
        assert portal._mapped_sites(pid, source) == {"first": 0x4100, "second": 0x4120}
    else:
        with pytest.raises(InvestigationError) as error:
            portal._mapped_sites(pid, source)
        assert error.value.code == "portal_image_unverified"
    pe.close.assert_called_once()


@pytest.mark.parametrize(("crossings", "jumps"), [(0, 0), (3, 0), (3, 1)])
def test_reports_actual_counters_and_closes_descriptors(
    linux, tmp_path: Path, monkeypatch, crossings, jumps
):
    monkeypatch.setattr(portal, "_PROC", tmp_path)
    monkeypatch.setattr(portal, "sha256_file", lambda executable: portal._IMAGE_SHA256)
    monkeypatch.setattr(portal, "running_processes", lambda: [{"pid": 51}])
    (tmp_path / "51/task/51").mkdir(parents=True)
    (tmp_path / "51/task/52").mkdir()
    sites = {"crossing_handler_called": 0x1000, "jump_requested": 0x2000}
    monkeypatch.setattr(portal, "_mapped_sites", lambda pid, exe: sites)
    descriptors = []

    def counter(tid, address):
        # The second thread saw the crossing. The main thread has no hits.
        count = (crossings if address == 0x1000 else jumps) if tid == 52 else 0
        path = tmp_path / f"{tid}-{address}"
        path.write_bytes(count.to_bytes(8, "little"))
        fd = os.open(path, os.O_RDONLY)
        descriptors.append(fd)
        return fd

    monkeypatch.setattr(portal, "_execution_counter", counter)
    read_end, write_end = os.pipe()
    monkeypatch.setattr(portal.os, "pidfd_open", lambda pid: read_end)
    clock = iter([100.0, 101.0])
    monkeypatch.setattr(portal.time, "monotonic", lambda: next(clock))
    armed = Mock()
    try:
        result = portal.observe(tmp_path, 1, armed)
        armed.assert_called_once_with({"pid": 51, "executable_sha256": portal._IMAGE_SHA256})
        assert result["crossing_handler_called"] == (crossings > 0)
        assert result["jump_requested"] == (jumps > 0)
        assert len(descriptors) == 4
        for fd in [read_end, *descriptors]:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        os.close(write_end)
