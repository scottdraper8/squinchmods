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

Use `games/minecraft/tooling/dev-server` — it writes `eula.txt`/`server.properties`, picks free
server/RCON ports, waits for readiness, and prints connection info, all in one step:

```bash
games/minecraft/tooling/dev-server start <mod> --loader <loader> --seed <your-seed> --fresh
```

To load a specific exported preset/datapack (e.g. one exported from the mod's own in-game preset
editor), pass it directly — it's staged into `<level-name>/datapacks/` before first launch, the same
place Minecraft auto-discovers a datapack at world creation:

```bash
games/minecraft/tooling/dev-server start <mod> --loader <loader> --seed <your-seed> --fresh \
  --datapack /path/to/exported-preset.zip
```

`--fresh` regenerates the world if one already exists under the same `--level-name` (default
`world`) — required the first time, or whenever the seed/datapack/instrumentation changes; omitting
it against an existing world is a deliberate refusal, not a silent reuse. See `dev-server --help`
for the rest (`--level-name`, `--server-properties key=value ...`, explicit
`--server-port`/`--rcon-port`).

**RCON, not a stdin/FIFO pipe, is why this works reliably.** A hand-rolled stdin pump was tried
first historically and cost real time to multiple layered failures (stale duplicate readers on the
same pipe, Gradle's daemon silently relaying stdin through an internal channel that breaks when a
stale build session shares the daemon, unexplained command drops on bursts of more than a couple of
commands). RCON is a real protocol with per-command request/response framing and has none of these
problems. `dev-server` enables it by default; there's no reason to reach for anything else.

## 2. Running commands

```bash
games/minecraft/tooling/dev-server rcon <mod> --loader <loader> -- "<command1>" "<command2>" ...
```

Sends commands sequentially against the server `start` already launched (reading connection info
from its state file, so no host/port/password bookkeeping is needed), waits for each response before
sending the next, and prints both. Multiple commands in one invocation is reliable since RCON has
real per-command framing.

## 3. Common RCON usage patterns

**Confirm the world state before trusting anything else:**

```bash
games/minecraft/tooling/dev-server rcon <mod> --loader <loader> -- "seed"
```

**Force-generate a specific region before querying it** (structures/terrain don't exist to query
until chunks are actually generated — `/locate` finds a theoretical position, it doesn't generate
anything):

```bash
games/minecraft/tooling/dev-server rcon <mod> --loader <loader> -- "forceload add <minX> <minZ> <maxX> <maxZ>"
```

**Checking a single block's type is limited** — there is no vanilla command that returns an
arbitrary block's exact ID. `/data get block <pos>` only works for block _entities_ (chests, signs,
etc.); for a plain block it errors `"The target block is not a block entity"`. The only way to test
via commands is a predicate check against a guessed type:

```bash
games/minecraft/tooling/dev-server rcon <mod> --loader <loader> -- \
  "execute if block <x> <y> <z> minecraft:water run say WATER" \
  "execute unless block <x> <y> <z> minecraft:water run say NOT_WATER"
```

This does not scale to "what block is this" without knowing what to guess — for anything beyond a
handful of manual spot-checks, write instrumentation instead (below).

**Stopping cleanly:**

```bash
games/minecraft/tooling/dev-server stop <mod> --loader <loader>
```

Sends RCON `stop`, falls back to killing the process if it doesn't respond, and — the specific fix
for a real historical failure mode (`stop` alone not always fully exiting, still holding its
RCON/server ports minutes later and breaking the _next_ launch with a port-bind failure) — verifies
the ports are actually free before reporting success, warning explicitly if they aren't.

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

- `dev-server start --fresh` deletes the world save for you before regenerating with a new
  seed/preset/instrumentation — no manual `rm -rf` needed.
- `dev-server stop` confirms no server process survived and that the RCON/server ports are actually
  free before reporting success, warning explicitly if they aren't — no manual `ps`/`ss` checking
  needed.
- If preserving old runs for comparison, rename the world directory deliberately and clean it up
  afterward. Archived `world.*` directories still pile up and still need manual cleanup —
  `dev-server` doesn't manage retention of anything beyond the single active `--level-name`.
- If driving this from an agent session with background task tracking, background tasks and
  scheduled wakeups don't automatically clean themselves up just because the underlying process died
  — verify and explicitly stop/cancel anything still shown as "running" that shouldn't be.
