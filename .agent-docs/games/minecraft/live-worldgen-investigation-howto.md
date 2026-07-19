# Headless Dev-Server QA: How-To

## Status: 2026-07-18

Operational companion to `live-worldgen-investigation-retrospective.md` (pain points and process
narrative). The RTF ocean-depth notes under `mods/ReTerraForged/plans/ocean-depth/` are case studies
for this workflow; this doc is the reusable _how_. Worked example throughout is RTF's Fabric dev
environment, but none of this is RTF-specific — same pattern applies to any Fabric/NeoForge mod with
a `runServer` gradle task.

## When to reach for this

Once you have a _specific, real_ case to test (an exact seed, an exact preset/datapack, ideally
already confirmed by a human on a real client) and need to measure or compare something precisely
and repeatably. Not a good tool for open-ended discovery (blind coordinate/seed searching) — that's
slower and less reliable than just testing on a real client first. See the retrospective for why.

## 1. Set up a headless dev server with RCON

Do this once per mod; reuse the run directory afterward.

```bash
cd <mod-repo>/<loader>/run   # e.g. fabric/run — created by a first runServer invocation if it doesn't exist yet
mkdir -p .   # ensure the dir exists before writing into it
printf 'eula=true\n' > eula.txt
printf 'online-mode=false\nenable-rcon=true\nrcon.port=25575\nrcon.password=<pick-anything>\nserver-port=25565\nlevel-seed=<your-seed>\nlevel-name=world\nspawn-protection=0\n' > server.properties
```

To load a specific exported preset/datapack (e.g. one exported from the mod's own in-game preset
editor), drop it in _before_ first launch — Minecraft auto-discovers a datapack placed in
`<level-name>/datapacks/` at world creation, same as a player would:

```bash
mkdir -p world/datapacks
cp /path/to/exported-preset.zip world/datapacks/
```

Launch (from the mod repo root, not the run dir):

```bash
cd <mod-repo>
chmod +x gradlew   # see the branch-switching note below — this doesn't always persist
./gradlew :<loader>:runServer --console=plain > /tmp/server.log 2>&1
```

Run this with a backgrounding mechanism your tool supports (`run_in_background: true` in this
session), then wait for readiness rather than a fixed sleep:

```bash
until grep -qE "RCON running|FAILED|Exception in thread" /tmp/server.log 2>/dev/null; do sleep 3; done
```

**Use `enable-rcon=true` from the start, not a stdin/FIFO pipe.** A hand-rolled stdin pump was tried
first this session and cost real time to multiple layered failures (stale duplicate readers on the
same pipe, Gradle's daemon silently relaying stdin through an internal channel that breaks when a
stale build session shares the daemon, unexplained command drops on bursts of more than a couple of
commands). RCON is a real protocol with per-command request/response framing and had none of these
problems once switched to. No reason to reach for anything else.

## 2. The RCON client

No `mcrcon` (or equivalent) package was available; this ~60-line script was written from scratch and
worked reliably for the whole investigation. Save it once, reuse it:

```python
#!/usr/bin/env python3
"""Minimal Minecraft RCON client. Usage: rcon.py <host> <port> <password> <command...>"""
import socket
import struct
import sys

PACKET_ID = 0


def _send_packet(sock, pkt_type, payload):
    global PACKET_ID
    PACKET_ID += 1
    pid = PACKET_ID
    body = struct.pack("<ii", pid, pkt_type) + payload.encode("utf-8") + b"\x00\x00"
    sock.sendall(struct.pack("<i", len(body)) + body)
    return pid


def _read_packet(sock):
    raw_len = _recv_exact(sock, 4)
    (length,) = struct.unpack("<i", raw_len)
    data = _recv_exact(sock, length)
    pid, pkt_type = struct.unpack("<ii", data[:8])
    payload = data[8:-2].decode("utf-8", errors="replace")
    return pid, pkt_type, payload


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def main():
    host, port, password = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    commands = sys.argv[4:]

    sock = socket.create_connection((host, port), timeout=15)
    try:
        _send_packet(sock, 3, password)  # SERVERDATA_AUTH
        pid, pkt_type, _ = _read_packet(sock)
        if pid == -1:
            print("AUTH_FAILED", file=sys.stderr)
            sys.exit(1)

        for cmd in commands:
            _send_packet(sock, 2, cmd)  # SERVERDATA_EXECCOMMAND
            _, _, payload = _read_packet(sock)
            print(f">>> {cmd}")
            print(payload)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
```

Usage: `python3 rcon.py localhost 25575 <password> "<command1>" "<command2>" ...` — sends commands
sequentially, waits for each response before sending the next, prints both. Multiple commands in one
invocation is reliable (unlike the old stdin/FIFO approach) since RCON has real per-command framing.

## 3. Common RCON usage patterns

**Confirm the world state before trusting anything else:**

```bash
python3 rcon.py localhost 25575 <password> "seed"
```

**Force-generate a specific region before querying it** (structures/terrain don't exist to query
until chunks are actually generated — `/locate` finds a theoretical position, it doesn't generate
anything):

```bash
python3 rcon.py localhost 25575 <password> "forceload add <minX> <minZ> <maxX> <maxZ>"
```

**Checking a single block's type is limited** — there is no vanilla command that returns an
arbitrary block's exact ID. `/data get block <pos>` only works for block _entities_ (chests, signs,
etc.); for a plain block it errors `"The target block is not a block entity"`. The only way to test
via commands is a predicate check against a guessed type:

```bash
python3 rcon.py localhost 25575 <password> \
  "execute if block <x> <y> <z> minecraft:water run say WATER" \
  "execute unless block <x> <y> <z> minecraft:water run say NOT_WATER"
```

This does not scale to "what block is this" without knowing what to guess — for anything beyond a
handful of manual spot-checks, write instrumentation instead (below).

**Stopping cleanly** — `stop` alone was not always sufficient this session; the server occasionally
didn't fully exit (still holding its RCON/server ports minutes later), which then broke the _next_
launch with a port-bind failure. Always verify, and force-kill if needed:

```bash
python3 rcon.py localhost 25575 <password> "stop"
sleep 6
pkill -9 -f "TransformerRuntime" 2>/dev/null   # or your loader's equivalent process pattern
pkill -9 -f ":<loader>:runServer" 2>/dev/null
ss -tlnp 2>/dev/null | grep -E "<rcon-port>|<server-port>"   # must be empty before relaunching
```

## 4. Writing QA-only debug instrumentation (Mixins)

Once manual command-based probing stops scaling (need automatic, precise, repeatable measurement
rather than one-block-at-a-time guessing), write a throwaway debug Mixin, compiled directly into the
mod jar. Not gated behind a debug flag — it's a QA-only build, not meant to ship.

**The one hazard that matters and cost a real crash this session:** if your hook fires _during
active chunk generation_ (any hook that runs inside a structure/feature-generation callback, e.g. a
`ChunkGenerator.applyBiomeDecoration` injection), reading a block via `level.getBlockState(pos)` is
only safe within a narrow radius of whatever chunk is _currently_ generating. `WorldGenRegion`, the
level type active at that point, calls `getChunk()` with **no bounds check at all** —
`WorldGenRegion.getBlockState()` throws a hard crash
(`IllegalStateException: Requested chunk unavailable during world generation`) the instant you read
outside that radius, not a graceful failure. A structure's full extent can easily span far more
chunks than that safe radius (a large jigsaw structure's combined bounding box spanned 10+ chunks in
this investigation). **Guard every read:**

```java
if (!level.hasChunk(SectionPos.blockToSectionCoord(x), SectionPos.blockToSectionCoord(z))) {
    // skip this point — don't count it, don't crash
    continue;
}
BlockState state = level.getBlockState(pos);
```

`hasChunk(int, int)` is a safe boolean check (chessboard distance from the currently-generating
chunk against the current generation step's dependency radius) — it never throws. Log how many
points got skipped alongside the result, so a reading's completeness is visible rather than silently
partial.

**Test the instrumentation itself against the exact target scenario on the headless server before
ever shipping it anywhere** — this is what would have caught the crash before it reached a real
tester. Launch, forceload the target area, watch the log for your marker _and_ for crash signatures
in the same wait:

```bash
until grep -qE "<your-log-marker>|FATAL|Exception generating" /tmp/server.log 2>/dev/null; do sleep 2; done
```

**Don't silently filter out "boring" results before aggregating.** An early draft of one measurement
in this investigation filtered out zero-valued samples to reduce log noise — which would have hidden
the single most important finding ("this returns exactly zero, always," not "sometimes small"). If
tracking aggregate stats, track _everything_ (total count, non-zero count, sum, max) and log a
periodic summary, not a per-call line filtered to only the cases that seemed interesting in advance.

**Pick the hook based on every consumer, not just where blocks get written.** For structures, a late
`postProcess()` hook may be enough if the only thing that matters is the visible block placement. It
is not enough when other vanilla systems read structure metadata. Ocean monuments proved this:
moving the blocks in `MonumentBuilding.postProcess()` fixed the visible monument, but guardian
spawning still used the old structure bounds. Moving the monument during `STRUCTURE_STARTS` fixed
both the blocks and the bounds used by spawn overrides.

When investigating or fixing structure placement, explicitly check:

- where the visible blocks are placed
- where the `StructureStart` and piece bounding boxes are created/saved
- whether mob spawn overrides, maps, locators, references, or other systems read those bounds
- whether the structure has a reload/regeneration path that reconstructs pieces later

**Label measurement timing in the log marker itself.** `OCEAN_FLOOR_WG` at structure-start time and
`OCEAN_FLOOR_WG` during `postProcess()` can both be valid measurements, but they do not mean the
same thing. Use marker names like `generation sample`, `placement sample`, `delayed sample`, or
`reload` instead of a generic "height" log line.

**Registration:** add the mixin's package-relative name to the mod's `*.mixins.json` `"mixins"` list
(check the existing file for the package/naming convention — RTF's is flat short-name-per-entry with
dot-separated subpackages, e.g. `"qa.MixinFoo"` for `raccoonman.reterraforged.mixin.qa.MixinFoo`).

## 5. Applying the same instrumentation across multiple branches

Needed when comparing behavior between a baseline branch and a feature branch. This was a fully
manual dance this session and is worth automating if this pattern recurs:

```bash
# on the feature branch, with instrumentation already written and working:
git stash -u                         # preserves both tracked (mixins.json) and untracked (new mixin file) changes
git checkout <baseline-branch>
chmod +x gradlew                     # executable bit does NOT reliably persist across a branch checkout
mkdir -p <mixin-package-dir>
# recreate the mixin file(s) by hand (git stash's untracked-file entry doesn't cleanly `pop` across
# a branch switch if there's also a conflicting tracked-file change, e.g. the same gradlew permission
# diff on both branches) — simplest to just re-write the file content directly rather than fight it
# add the same registration line to this branch's mixins.json
./gradlew :<loader>:build -q
cp <loader>/build/libs/<artifact>-<version>-fabric-<mc-version>.jar <destination>.jar

# clean up before returning:
git checkout -- <mixins.json path>
rm -rf <mixin-package-dir>
git checkout <feature-branch>
chmod +x gradlew
git stash pop                        # if this fails specifically on the gradlew permission conflict,
                                      # it still restores the untracked mixin file; just re-add the
                                      # mixins.json registration line by hand and `git stash drop`
```

## 6. Cleanup checklist between test runs

- Delete the world save before changing seed/preset/instrumentation and relaunching:
  `rm -rf <loader>/run/world`.
- If preserving old runs for comparison, rename them deliberately and clean them up afterward.
  Archived `world.*` directories pile up quickly, and right now this is a manual cleanup step.
- Confirm no server process survived a `stop`:
  `ps aux | grep -iE "runServer|Knot|TransformerRuntime"`.
- Confirm the RCON/server ports are actually free before relaunching:
  `ss -tlnp 2>/dev/null | grep -E "<rcon-port>|<server-port>"`.
- If driving this from an agent session with background task tracking, background tasks and
  scheduled wakeups don't automatically clean themselves up just because the underlying process died
  — verify and explicitly stop/cancel anything still shown as "running" that shouldn't be.
