# Headless Dev-Server QA: How-To

## Status: 2026-07-22

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

**`forceload add` is capped at 256 chunks per call** (vanilla's own limit) — a region larger than
16x16 chunks errors with `Too many chunks in the specified area` instead of silently truncating.

**Multiple large `forceload` calls issued back-to-back can crash the server via the watchdog**,
confirmed directly (2026-07-20): eight ~200-chunk `forceload` commands sent in one `rcon` invocation
against an expensive preset (RTF's very-deep ocean preset, ~105ms/chunk thread time) blocked the
main thread long enough that vanilla's `ServerWatchdog` killed the process outright — a real crash,
not a timeout warning, with its own crash report. Not a mixin bug; it's the same watchdog that would
fire against unmodified vanilla under enough simultaneous forced generation. Two independent fixes,
use both: pass `--server-properties max-tick-time=-1` to `dev-server start` to disable the watchdog
for the session, and send `forceload` calls one region at a time (each in its own `rcon` invocation,
with a longer `--timeout` — heavy presets can take minutes per region) rather than batched together.
After a watchdog crash, the underlying game process can still be running as an orphaned child (the
same Architectury child-process issue as "Known limitations" in `games/minecraft/tooling/README.md`)
even though the `rcon`/`start` command itself reports failure — check `ps aux | grep KnotServer` and
manually kill it before retrying, and clear the stale `.dev-server-state.json` if `start` refuses to
proceed.

**Checking a single block's type is limited** — there is no vanilla command that returns an
arbitrary block's exact ID. `/data get block <pos>` only works for block _entities_ (chests, signs,
etc.); for a plain block it errors `"The target block is not a block entity"`. The only way to test
via commands is a predicate check against a guessed type:

```bash
games/minecraft/tooling/dev-server rcon <mod> --loader <loader> -- \
  "execute if block <x> <y> <z> minecraft:water run seed" \
  "execute unless block <x> <y> <z> minecraft:water run seed"
```

**Use a command that actually returns text over RCON as the predicate's signal, not `say`.** `say`
broadcasts to chat/console but doesn't populate its own RCON response payload —
`execute if ... run say WATER` executes successfully but comes back empty either way,
indistinguishable from the condition being false. `seed` (or any other command that always prints
something) reliably distinguishes "condition true" (text present) from "condition false" (empty
response).

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

**Never pipe a build through `| tail` (or anything else) and trust the shell's exit code.** A
pipeline's exit status is the _last_ command's, not the build's —
`./gradlew ... | tail -60; echo $?` reports `tail`'s exit code (almost always 0), not gradle's. This
silently masked two real build failures in this session (a Javadoc comment containing `*/`
mid-sentence, which closes the comment early and breaks compilation) — the background task reported
"completed" both times while the build had actually failed. Redirect to a file instead and check its
content directly: `./gradlew ... > build.log 2>&1; echo "EXIT=$?"`, then grep the file for
`BUILD FAILED`/`error:`, or just confirm the expected output artifact (a `.class` file, a fresh jar)
actually exists and is newer than the source. Don't trust "the background task said it completed" as
proof of success by itself.

**`@Shadow`-ing a field declared in the mixin target's _superclass_, not the target class itself,
can fail silently.** Mixin's annotation processor prints "Cannot find target for @Shadow field" as a
warning, not a hard error — the build still succeeds, but the mixin doesn't actually apply the way
you'd expect at runtime. Use an `@Accessor` mixin targeting the class that actually _declares_ the
field instead (the same pattern as accessing any other private/protected field via Mixin) —
accessors resolve correctly regardless of how deep in the hierarchy the field lives.

**When a structure's own `postProcess()` does more than a single-column heightmap sample — footprint
averaging, a secondary uneven-terrain adjustment, anything beyond `getHeight(type, x, z)` — a naive
"resample and diff" QA check produces false positives.** Hit this directly with vanilla shipwrecks:
non-beached shipwrecks average `OCEAN_FLOOR_WG` across their whole footprint, not one column, so a
QA mixin comparing the final placement against a single fresh sample read large, alarming-looking
deltas that turned out to exactly match vanilla's own footprint average once replicated (delta
against the real calculation: exactly zero). Either replicate the actual vanilla arithmetic
precisely, or sidestep needing to at all by checking the real _outcome_ instead — a block-level scan
for actual solid ground near the placement is independent of whichever internal calculation produced
the Y, and answers the question that actually matters ("is this floating") directly.

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

**For validating a fix that only matters once blocks are actually placed (fluid/lava placement,
anything decided by an `Aquifer.FluidPicker` or similar post-generation pass), don't hook generation
at all — forceload the target region first, then poll from a tick hook until the chunks are present,
then read real blocks.** This sidesteps the `WorldGenRegion` hazard above entirely, because by the
time the scan runs the chunks are fully generated ordinary level chunks, not mid-generation ones:

```java
if (!level.hasChunk(chunkX, chunkZ)) {
    return; // still forceloading — try again next tick
}
BlockState state = level.getBlockState(pos); // safe, this is a real generated chunk now
```

Trigger the `forceload add <minX> <minZ> <maxX> <maxZ>` RCON command yourself before the scan starts
running, then let the mixin's own polling loop (same `hasChunk` check, just outside any generation
callback) decide when to actually read. This was the only reliable way to confirm a fluid-placement
fix's real, physically-placed output (verifying zero obsidian and correct floor material at specific
columns) rather than re-deriving what the fix's own function _should_ return.

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

**Two QA mixins targeting the same class with an identically-named-and-signatured field or method
silently collide — Sponge Mixin merges them into the target class with no warning, and only one
implementation actually ends up firing at runtime.** Hit this three separate times across different
QA mixins in one investigation, always targeting `MinecraftServer` (a natural, shared hook point for
"run this scan on server tick") from multiple independent throwaway mixins, each independently named
a field `rtf$started` or a method `rtf$maybeStart` without checking what sibling QA mixins already
declared. The build succeeds, the mod loads, and the symptom is confusing rather than obviously
wrong (the log for one scan just never appears, or appears with values that don't match what that
mixin's own code should produce) — there's no error pointing at the actual cause. Prefix every
QA-mixin member with something unique to that specific mixin/investigation, not a generic
`started`/`run`/`init`, especially for anything hooking a commonly-shared class like
`MinecraftServer` or `NoiseChunk` that other QA mixins are also likely to target.

## 5. Applying the same instrumentation across multiple branches

Needed when comparing behavior between a baseline branch and a feature branch. **Use a git worktree,
not stash/checkout** — confirmed working cleanly in practice (a stash-based dance was tried in an
earlier session and hit real problems: the executable bit on `gradlew` doesn't reliably persist
across a branch checkout, and `git stash pop` doesn't cleanly restore an untracked file across a
branch switch when there's also a conflicting tracked-file change, e.g. that same permission diff on
both branches). A worktree sidesteps all of that entirely by giving the baseline branch its own real
directory and working tree, with no stash/checkout choreography at all:

```bash
# from the feature branch, with instrumentation already written and working there:
git worktree add ../<mod>-baseline <baseline-branch>   # e.g. ../ReTerraForged-baseline 1.21.1

# copy the same QA mixin source + mixins.json registration line into the worktree
mkdir -p ../<mod>-baseline/<mixin-package-dir>
cp <mixin-package-dir>/*.java ../<mod>-baseline/<mixin-package-dir>/
# edit ../<mod>-baseline/<mixins.json path> to add the same registration line

cd ../<mod>-baseline
chmod +x gradlew
./gradlew :<loader>:build -q
cp <loader>/build/libs/<artifact>-<version>-fabric-<mc-version>.jar <destination>.jar
cd -

# clean up when done — this also drops the copied QA mixin files and never touches the
# baseline branch's own git history:
git worktree remove ../<mod>-baseline --force
```

If placing the worktree as a sibling under the mods directory (e.g. `games/minecraft/mods/`), tools
like `dev-server` that resolve mods by literal directory name under that path can address it
directly by its worktree folder name, same as any other mod checkout — no special-casing needed.

**For a strict before/after comparison of one specific fix, pin the worktree to the exact commit,
not a branch tip.** `git worktree add --detach <path> <exact-sha>` (the fix commit itself for
"after", its immediate parent for "before") guarantees the only difference between the two built
jars is that one commit — a live branch tip almost always carries later, unrelated commits layered
on top (in one case, ~15 of them, including an unrelated fix from the same investigation), which
silently weakens the comparison from "does this commit work" to "does this commit plus everything
else that happened to land afterward work." Detached-HEAD worktrees behave identically to normal
ones for building; there's no reason to ever build a before/after pair from branch tips when the
actual commits being compared are known.

## 6. Cleanup checklist between test runs

- `dev-server start --fresh` deletes the world save for you before regenerating with a new
  seed/preset/instrumentation — no manual `rm -rf` needed.
- **`dev-server stop`/`start` have known process-cleanup gaps — manual `ps`/`ss` checking is still
  needed in practice.** See "Known limitations" in `games/minecraft/tooling/README.md` for both
  failure modes and their workarounds; don't assume a stop or a failed start actually cleaned up.
- If preserving old runs for comparison, rename the world directory deliberately and clean it up
  afterward. Archived `world.*` directories still pile up and still need manual cleanup —
  `dev-server` doesn't manage retention of anything beyond the single active `--level-name`.
- If driving this from an agent session with background task tracking, background tasks and
  scheduled wakeups don't automatically clean themselves up just because the underlying process died
  — verify and explicitly stop/cancel anything still shown as "running" that shouldn't be.

## 7. Reading vanilla Minecraft source for comparison

A full decompiled/mapped vanilla source tree already exists on this machine — do not reconstruct
vanilla behavior from memory or guess at it; read it directly:

```text
games/minecraft/reference/sources/1.21.1/official/src/net/minecraft/...
```

`1.20.1/official` and `1.20.4/official` siblings also exist under the same `reference/sources/` root
for older-version comparisons. This is genuine decompiled source (confirmed present, not a guess) —
prefer it over web search or training-data recall whenever comparing a mod's worldgen/mixin behavior
against vanilla's actual implementation.
