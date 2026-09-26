#!/usr/bin/env python3
"""
Fake Minecraft server for QA tests.

Emits the server-ready line, responds to pregen tool commands with both
chunksmith and chunky completion lines, and exits cleanly on 'stop'.

Supported env vars:

FAKE_SUPPRESS_TOOL_COMPLETION=1: exit immediately after receiving a pregen
command without printing completion lines, simulating a tool that hangs or
errors. This causes watch_for_tool_completion to raise ToolNotDoneError.

FAKE_IGNORE_STOP=1: don't exit when 'stop' is written to stdin, forcing the
caller's wait_for_exit() to hit its timeout and kill the process.

FAKE_NO_READY=1: never print the "Done (" ready line. The process just blocks
reading stdin (without producing output) until the caller's watchdog kills it,
simulating a server that never becomes ready (or crashes before doing so).

FAKE_CLOSE_STDIN_AFTER_READY=1: close stdin, *then* print the ready line and
sleep, simulating a process whose stdin pipe has gone away (e.g. crashed
right after boot) so that a subsequent write from the caller raises
BrokenPipeError/OSError. Stdin is closed strictly before the ready line is
printed (rather than after) so the caller -- which only writes after it
observes the ready line on stdout -- can never race the close: by the time
it sees "Done (", our stdin is already gone. Uses os.close(0) rather than
sys.stdin.close(): the latter doesn't reliably release the underlying fd
(empirically verified -- the caller's write can still succeed afterwards),
whereas os.close(0) deterministically does.

FAKE_CRASH_REPORT_DIR=/path: directory where the fake server should write
crash reports when one of the FAKE_WRITE_CRASH_* flags is enabled.

FAKE_WRITE_CRASH_BEFORE_READY=1: write a crash report before hanging in
FAKE_NO_READY mode.

FAKE_WRITE_CRASH_ON_STOP=1: write a crash report immediately before handling
stop.
"""

import os
import sys
import time

SUPPRESS = os.environ.get("FAKE_SUPPRESS_TOOL_COMPLETION", "0") == "1"
IGNORE_STOP = os.environ.get("FAKE_IGNORE_STOP", "0") == "1"
NO_READY = os.environ.get("FAKE_NO_READY", "0") == "1"
CLOSE_STDIN_AFTER_READY = os.environ.get("FAKE_CLOSE_STDIN_AFTER_READY", "0") == "1"
CRASH_REPORT_DIR = os.environ.get("FAKE_CRASH_REPORT_DIR")
WRITE_CRASH_BEFORE_READY = os.environ.get("FAKE_WRITE_CRASH_BEFORE_READY", "0") == "1"
WRITE_CRASH_ON_STOP = os.environ.get("FAKE_WRITE_CRASH_ON_STOP", "0") == "1"


def write_crash_report(name):
    if not CRASH_REPORT_DIR:
        return
    os.makedirs(CRASH_REPORT_DIR, exist_ok=True)
    with open(os.path.join(CRASH_REPORT_DIR, name), "w", encoding="utf-8") as f:
        f.write("fake crash for test\n")


if NO_READY:
    if WRITE_CRASH_BEFORE_READY:
        write_crash_report("crash-before-ready.txt")
    # Never announce readiness; just hang so the caller's watchdog has to
    # kill us once its timeout elapses.
    time.sleep(3600)
    sys.exit(1)

if CLOSE_STDIN_AFTER_READY:
    os.close(0)
    print("[Server thread/INFO]: Done (0s)!", flush=True)
    time.sleep(3600)
    sys.exit(1)

print("[Server thread/INFO]: Done (0s)!", flush=True)

for line in sys.stdin:
    cmd = line.strip()
    if cmd == "stop":
        if WRITE_CRASH_ON_STOP:
            write_crash_report("crash-on-stop.txt")
        if IGNORE_STOP:
            continue
        print("[Server thread/INFO]: Stopping the server", flush=True)
        sys.exit(0)
    if cmd in {"tick freeze", "/tick freeze"}:
        print("[Server thread/INFO]: The game is frozen", flush=True)
    if cmd in {"tick query", "/tick query"}:
        print("[Server thread/INFO]: The game runs normally", flush=True)
    if cmd in {"tick step 1", "/tick step 1"}:
        print("[Server thread/INFO]: Stepping 1 tick", flush=True)
    if "redstone_backport:crafter" in cmd:
        print("[Server thread/INFO]: Changed the block at 0, 64, 0", flush=True)
    if cmd in {"data get block 0 64 0 id", "/data get block 0 64 0 id"}:
        print(
            '[Server thread/INFO]: 0, 64, 0 has the following block data: "redstone_backport:crafter"',
            flush=True,
        )
    if any(kw in cmd for kw in ("pregen", "chunksmith", "chunky", "radius", "start")):
        if SUPPRESS:
            sys.exit(0)
        print("[Chunksmith]: Pregeneration complete.", flush=True)
        print(
            "[Chunky] Task finished for minecraft:overworld. "
            "Processed: 289 chunks (100.00%), Total time: 0:00:01",
            flush=True,
        )

sys.exit(0)
