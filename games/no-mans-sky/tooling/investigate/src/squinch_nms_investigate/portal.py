"""Observe the planetary portal collision and jump dispatch with Linux hardware counters."""

from __future__ import annotations

import ctypes
import errno
import math
import os
import platform
import select
import struct
import time
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

import pefile

from .errors import InvestigationError
from .game import running_processes
from .paths import sha256_file

# NMS 7.14 (Steam 26540391). Each site is a call instruction and its reviewed target.
# The second call is shared by regular and community portal jumps.
_IMAGE_SHA256 = "092236962ee050e419424699b5c343a0173f7773d5ad0866b7ec366d334c07d4"
_PROC = Path("/proc")
_SITES = {
    "crossing_handler_called": (0x127A31D, 0x1086820),  # cGcPortalComponent::WarpPlayer
    "jump_requested": (0x1086D38, 0x17D1F80),  # cGcSpaceshipWarp::WarpToDistantSystem
}


def _mapped_sites(pid: int, executable: Path) -> dict[str, int]:
    """Verify the actual call instructions at the loaded PE image base, including under ASLR."""
    stat = executable.stat()
    pe = pefile.PE(str(executable), fast_load=True)
    try:
        bases = {pe.OPTIONAL_HEADER.ImageBase}
    finally:
        pe.close()
    ranges = []
    for line in (_PROC / str(pid) / "maps").read_text().splitlines():
        span, perms, offset, device, inode, *_ = line.split(maxsplit=5)
        start, end = (int(n, 16) for n in span.split("-"))
        if "x" in perms:
            ranges.append((start, end))
        major, minor = (int(n, 16) for n in device.split(":"))
        if (
            int(inode) == stat.st_ino
            and os.makedev(major, minor) == stat.st_dev
            and int(offset, 16) == 0
        ):
            bases.add(start)
    with (
        executable.open("rb") as source,
        (_PROC / str(pid) / "mem").open("rb", buffering=0) as mem,
    ):
        header = source.read(128)
        for base in sorted(bases):
            sites = {name: base + site for name, (site, _) in _SITES.items()}
            if not all(
                any(start <= pc and pc + 5 <= end for start, end in ranges) for pc in sites.values()
            ):
                continue
            if os.pread(mem.fileno(), len(header), base) != header:
                continue
            for name, (site, target) in _SITES.items():
                instruction = b"\xe8" + struct.pack("<i", target - site - 5)
                if os.pread(mem.fileno(), 5, sites[name]) != instruction:
                    break
            else:
                return sites
    raise InvestigationError(
        "portal_image_unverified",
        "The mapped NMS portal instructions differ from the supported build",
    )


def _execution_counter(tid: int, address: int) -> int:
    # Linux x86-64 perf_event_attr, PERF_TYPE_BREAKPOINT / HW_BREAKPOINT_X.
    attr = bytearray(128)
    struct.pack_into("=II", attr, 0, 5, len(attr))
    struct.pack_into("=Q", attr, 40, (1 << 1) | (1 << 5) | (1 << 6))  # inherit, user only
    struct.pack_into("=IQQ", attr, 52, 4, address, 8)
    buffer = (ctypes.c_ubyte * len(attr)).from_buffer(attr)
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.syscall(298, ctypes.byref(buffer), tid, -1, -1, 8)  # perf_event_open, CLOEXEC
    if fd < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return fd


def observe(game_root: Path, timeout: float, armed: Callable[[dict], object]) -> dict:
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise InvestigationError(
            "invalid_timeout", "Choose a timeout above zero and at most 600 seconds"
        )
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise InvestigationError(
            "unsupported_portal_trace_host", "Portal observation requires x86-64 Linux / Proton"
        )
    executable = game_root / "Binaries/NMS.exe"
    if sha256_file(executable) != _IMAGE_SHA256:
        raise InvestigationError(
            "unsupported_portal_trace_build",
            "The portal route has not been verified on this NMS executable",
        )
    processes = running_processes()
    if len(processes) != 1:
        raise InvestigationError(
            "portal_client_unavailable", "Load a test save in exactly one NMS client"
        )
    pid = processes[0]["pid"]
    proc = _PROC / str(pid)
    counts: dict[str, list[int]] = {name: [] for name in _SITES}
    seen = dict.fromkeys(_SITES, False)
    try:
        with ExitStack() as close:
            process_fd = os.pidfd_open(pid)
            close.callback(os.close, process_fd)
            exited = select.poll()
            exited.register(process_fd, select.POLLIN)
            sites = _mapped_sites(pid, executable)
            for task in (proc / "task").iterdir():
                for name, pc in sites.items():
                    try:
                        fd = _execution_counter(int(task.name), pc)
                    except OSError as exc:
                        if exc.errno == errno.ESRCH:  # A worker exited during enumeration.
                            break
                        raise
                    close.callback(os.close, fd)
                    counts[name].append(fd)
            if not all(counts.values()):
                raise InvestigationError(
                    "portal_client_unavailable", "The NMS client exited before observation"
                )
            identity = {"pid": pid, "executable_sha256": _IMAGE_SHA256}
            armed(identity)
            deadline = time.monotonic() + timeout
            while True:
                for name, fds in counts.items():
                    if not seen[name]:
                        seen[name] = any(int.from_bytes(os.read(fd, 8), "little") > 0 for fd in fds)
                if seen["jump_requested"] or time.monotonic() >= deadline:
                    return {**identity, **seen}
                if exited.poll(0):
                    raise InvestigationError(
                        "portal_client_unavailable", "The NMS client exited during observation"
                    )
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    except OSError as exc:
        raise InvestigationError(
            "portal_observation_unavailable", f"Linux could not observe this NMS client: {exc}"
        ) from exc
