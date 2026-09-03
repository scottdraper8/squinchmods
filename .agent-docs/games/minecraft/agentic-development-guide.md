# Minecraft Agentic Development Guide

## Status: 2026-08-01

Operational entry point for the tight Minecraft development/investigation loop, run through
`tooling/squinch mc-investigate`. This replaces the old ad hoc `dev-server` script and its companion
how-to; nothing here requires reading history to use. Case studies that used this workflow live
under `mods/<mod>/plans/`; this doc is the reusable process, not any one investigation's findings.
If something about the tooling itself surprises you (not a mod-specific finding), record it in
`agentic-development-findings.md` rather than expanding this file — see the last section.

Worked examples throughout are RTF's Fabric/NeoForge dev environment, but the tool is not
RTF-specific — the same pattern applies to any Fabric/NeoForge mod with a `runServer` Gradle task.
RTF-specific pieces (`cell-scan`, fixtures, reusable probe packs) are called out explicitly.

## When to reach for this

Once you have a _specific, real_ case to test (an exact seed, an exact preset/datapack, ideally
already confirmed by a human on a real client) and need to measure or compare something precisely
and repeatably. Do not start a dedicated server for open-ended coordinate discovery on RTF worlds —
use the standalone `cell-scan` funnel below first, then reserve the server for bounded confirmation.

## The authority ladder

Every command in this system labels its own authority. Passing a lower rung never proves a higher
one — an RTF cell scan cannot prove final blocks, and a mocked/cold query cannot prove process
teardown or loader behavior. Reach for the cheapest rung that can genuinely answer the question,
then cross the real boundary before calling an investigation finished:

1. **Pure logic** — reading source, static analysis, parsing. No Minecraft process involved.
2. **RTF prediction** — `cell-scan` preview/adaptive mode, RTF's exact `generateZoomed(..., false)`
   path run in a standalone JVM. Fast, no server, but explicitly a prediction, never finished-world
   truth.
3. **RTF tile** — `cell-scan --mode tile`, RTF's real horizontal cell/`TileGenerator` model. Still
   standalone, still not final blocks; it is the RTF horizontal-cell-model authority, not more.
4. **Generation hook** — a probe or Mixin observing an in-progress generation phase
   (`structure-start`, `generation`, `placement`). Real Minecraft, but the object graph
   mid-generation can differ from the finished result (see the `WorldGenRegion`/cold-scan hazards
   under "Writing QA-only debug instrumentation" below).
5. **Finished chunk** — a real, fully generated `LevelChunk` read after `squinch:finished-chunks`
   (or an equivalent terminal probe) confirms it reached `FullChunkStatus.FULL`. This is the
   authority used for block/biome placement claims.
6. **Client visual confirmation** — a human actually looking at it. Still the most trustworthy check
   for "is this a real, player-facing problem," and often faster than server-side reproduction for
   initial discovery (see the findings doc).

Every structured result (`probe`, `scenario`, `cell-scan`, `compare`) records which rung it's
speaking from — `authority: "prediction"`, `"rtf-horizontal-cell-model"`, `"generation"`, or
`"finished-chunk"` — so you never have to infer it from context.

## 1. Fast discovery: the RTF coarse-to-finished-chunk funnel

Do not start a server to search a large RTF coordinate space. Run `cell-scan` against an exact
worktree, seed, and source fixture first — it uses the selected worktree's real compiled `Preset`,
noise bootstrap, `GeneratorContext`, and `TileGenerator` classes in a small standalone JVM, and
fails explicitly rather than silently falling back to a live server if that bootstrap boundary can't
be established:

```bash
tooling/squinch mc-investigate cell-scan \
  --project games/minecraft/mods/FreeTerraForged \
  --preset games/minecraft/investigations/reterraforged/fixtures/vanilla-depth-maximum-ocean/fixture.toml \
  --seed 12345 --mode adaptive --bounds -4096 -4096 4096 4096 \
  --sample-step 16 --predicate 'height:>=:0.15' \
  --field height,height_blocks,terrain,continent_edge \
  --refine-count 2 --refine-step 8 --exact-tile --json
```

Preview/adaptive output has prediction authority; an exact tile has RTF-horizontal-model authority.
Neither is a generated chunk. The result artifact contains aggregate distributions and a bounded
`scan.top_candidates` shortlist instead of a raw million-row dump; available fields span height,
terrain/type, continent, river, temperature/moisture, erosion, weirdness, water table, and
terrain/biome region. `--mode tile --tile-size 3` invokes RTF's actual runtime tile filter/border
calculation instead of the preview path. Every scan artifact records the exact seed, resolved
preset, target HEAD/dirty status, harness hashes, Minecraft/RTF/Java versions, a fingerprinted
classpath, cold/warm/Gradle wall timings, and a deterministic result hash — repeated identical scans
are deterministic.

The live exit-gate evidence illustrates the cost shape without inventing a threshold: an adaptive
scan inspecting 256 coarse cells, refining two regions, and performing exact-tile follow-up took
2.80 seconds cold / 0.42 seconds warm inside the JVM (8.03 seconds including Gradle launch), versus
about 18 seconds to start the comparable Fabric server before its first scenario step. Use the
recorded evidence for the search scale at hand rather than treating these machine-specific numbers
as guarantees.

To confirm the standalone RTF-tile model actually matches what the live server generates, run the
canonical parity scenario, which selects the external `probes/cell-cache` pack and compares
standalone factor-3 samples against RTF's live runtime tile cache at identical coordinates:

```bash
tooling/squinch mc-investigate scenario \
  .squinch/games/minecraft/mods/FreeTerraForged/scenarios/rtf-cell-cache-cross-check.toml --json
```

To turn discovery into finished-world evidence, point a scenario generation step at the scanner's
retained result file instead of hand-picking bounds:

```toml
[[steps]]
id = "generate-shortlist"
type = "generate"
unit = "block"
candidate_file = "/exact/run/artifact/cell-scan-result.json"
candidate_limit = 2
authority = "finished-chunk"
terminal_probe = "squinch:finished-chunks"
```

The runner reads `scan.top_candidates`, floors negative coordinates correctly, deduplicates by
chunk, force-generates each selected chunk, and runs the chosen terminal probe against every one.
The funnel is: preview prediction → optional exact RTF tile → bounded real generation →
finished-chunk probe. Only the last stage is finished-world truth.

## 2. Running a real server and scenario

### One-off server, for exploratory RCON

`tooling/squinch mc-investigate start` writes `eula.txt`/`server.properties` (backing up and
restoring the target's originals), picks free server/RCON ports, authenticates over RCON as part of
readiness, and gives every launch a unique run ID, artifact directory, and run-derived world/level
name. Every `start` creates its own fresh world — there is no shared default world and no `--fresh`
flag to remember:

```bash
tooling/squinch mc-investigate start --project games/minecraft/mods/<mod> --loader <loader> \
  --seed <your-seed>
```

`--project` is an exact path to the target worktree, not a mod name resolved under
`games/minecraft/mods/` by convention — this works identically whether or not the worktree lives
under that directory at all. `--datapack` is repeatable, for loading one or more exported
presets/datapacks (e.g. exported from a mod's own in-game preset editor):

```bash
tooling/squinch mc-investigate start --project games/minecraft/mods/<mod> --loader <loader> \
  --seed <your-seed> --datapack /path/to/exported-preset.zip
```

See `start --help` for the rest (`--server-property key=value`, explicit
`--server-port`/`--rcon-port`, `--timeout`, `--retention {discard,keep-on-failure,keep}`). Add
`--json` to any command for the versioned `cli-output-v1.json` envelope.

```bash
tooling/squinch mc-investigate command --project games/minecraft/mods/<mod> --loader <loader> \
  -- "<command1>" "<command2>" ...
```

`command` sends commands sequentially against the tracked active server for that project/loader (no
host/port/password bookkeeping needed), waits for each response, and prints both — reliable for
multiple commands in one invocation since RCON has real per-command framing. To start, run one batch
of commands, and always stop in a single call, use `run --command "..." --command "..."` instead of
a separate `start`/`command`/`stop` sequence.

**RCON, not a stdin/FIFO pipe, is why this works reliably.** A hand-rolled stdin pump was tried
historically and cost real time to layered failures (stale duplicate readers on the same pipe,
Gradle's daemon relaying stdin through an internal channel that breaks when a stale build session
shares the daemon, unexplained command drops on bursts of commands). RCON has real per-command
request/response framing and none of these problems; `start` authenticates over it as part of its
own readiness check.

### Scenarios, for anything repeatable

For anything beyond one-off exploration, write a scenario instead of a manual start/command/stop
sequence:

```bash
tooling/squinch mc-investigate scenario \
  .squinch/games/minecraft/mods/FreeTerraForged/scenarios/smoke.toml --json
```

Every repository-owned project, datapack, fixture, patch, and probe path in the TOML is
repository-root-relative (`games/minecraft/...`) and resolves from the repository root rather than
the caller's directory. Scenario schema version 1 requires an exact seed and ordered steps, and
supports command, generation, and selected-probe steps; multiple datapacks; server properties;
startup/step/shutdown timeouts; retention; required runtime mods; managed runtime configuration
files; and response/region/terminal expectations. Use `[[runtime_files]]` with a repository-relative
`source` and a `target` below `config/` when a scenario must vary a generated mod configuration. The
runner fingerprints the source, backs up the target, installs the input before launch, and restores
the original on every cleanup path. Use a top-level `runtime_absent_files` array of `config/` paths
when first-start behavior requires a generated configuration not to exist; those targets receive the
same backup and restoration guarantees. A generation step has `generation` authority unless it names
a selected terminal probe and explicitly requests `finished-chunk` authority — force-load
acknowledgment alone is never labeled finished-chunk proof. Each run's manifest fingerprints the
scenario, Git HEAD and dirty patch, untracked inputs, datapacks, Java, Gradle wrapper/build inputs,
loader, JVM environment arguments, launch command, and the runtime mod list parsed from the real
loader log. A crash, fatal server condition, timeout, assertion failure, missing or non-passing
probe terminal, incomplete scan, or cleanup failure makes the command nonzero — never a superficial
success.

An RTF scenario names one retained source-form fixture with `rtf_fixture = ".../fixture.toml"`. The
runner deterministically materializes it, copies the generated ZIP into the run artifacts, and
records the semantic metadata, complete resolved preset, logical source hash, and archive hash.
Additional independent datapacks stay a repeatable `datapacks = [...]` array. Do not use partial
preset overrides for runtime evidence. A valid variant must be generated completely through FTF's
preset datapack generator and retained as a source-form fixture before a scenario uses it. See
`games/minecraft/investigations/reterraforged/fixtures/` for fixtures named by their current
condition rather than an incident or historical nickname.

### Actual world-creation UI

Use `mc-investigate client` for pre-server preview and integrated-client evidence. It launches
Fabric or NeoForge in an artifact-owned run directory under an isolated headless Wayland display; it
never uses a personal launcher profile or the project's ordinary run directory. Declare runtime
catalog artifacts with `--artifact`, compile-only mechanism APIs with
`--compile-artifact ID:LOADER:named|loader`, probe inputs with `--probe-env SQUINCH_NAME=value`, and
required result basenames with `--result-env SQUINCH_NAME=result.json`. Runtime companions are not
implicit compile dependencies. Success requires every result object to report `status: "pass"`, an
unchanged target worktree, and complete process/display cleanup.

### Common RCON usage patterns

**Confirm the world state before trusting anything else:**

```bash
tooling/squinch mc-investigate command --project games/minecraft/mods/<mod> --loader <loader> -- "seed"
```

**Force-generate a specific region before querying it** (structures/terrain don't exist to query
until chunks are actually generated — `/locate` finds a theoretical position, it doesn't generate
anything). Prefer the dedicated `generate` command, which tiles the region into legal maximum
16x16-chunk `forceload` calls, waits for finished `LevelChunk` promotion, and removes its own
force-load region during teardown:

```bash
tooling/squinch mc-investigate generate --project games/minecraft/mods/<mod> --loader <loader> \
  --unit chunk --bounds <minX> <minZ> <maxX> <maxZ>
```

A raw `forceload add <minX> <minZ> <maxX> <maxZ>` RCON command via `command` still works for a
single region within the 256-chunk vanilla cap, but `generate` is preferred since it tiles
automatically and guarantees cleanup. `forceload add` is capped at 256 chunks per call (vanilla's
own limit) — a region larger than 16x16 chunks errors with `Too many chunks in the specified area`
instead of silently truncating.

**Multiple large `forceload` calls issued back-to-back can crash the server via the watchdog.**
Eight ~200-chunk `forceload` commands sent in one invocation against an expensive preset (RTF's
deep-world ocean stress condition, ~105ms/chunk thread time) blocked the main thread long enough
that vanilla's `ServerWatchdog` killed the process outright — a real crash, not a timeout warning,
with its own crash report. Not a mixin bug; it's the same watchdog that fires against unmodified
vanilla under enough simultaneous forced generation. Two independent fixes, use both: pass
`--server-property max-tick-time=-1` to `start`/`run` to disable the watchdog for the session, and
prefer `generate` (which sends regions serially, tiling to the legal 16x16-chunk maximum
automatically) or send `command`-level `forceload` calls one region at a time (with a longer
`--timeout` — heavy presets can take minutes per region) rather than batching them. After a watchdog
crash, `mc-investigate` validates exact process identities and owns the complete Gradle/game tree in
a dedicated user-systemd control group rather than trusting a possibly-stale PID or leaving an
orphaned `KnotServer` child running; if a crash still leaves state that `stop` can't resolve, run
`mc-investigate doctor --recover` rather than manually hunting `ps`/`ss` output.

**Checking a single block's type is limited** — there is no vanilla command that returns an
arbitrary block's exact ID. `/data get block <pos>` only works for block _entities_ (chests, signs,
etc.); for a plain block it errors `"The target block is not a block entity"`. The only way to test
via commands is a predicate check against a guessed type, and `say` does not work as the signal
(broadcasts to chat/console but doesn't populate its own RCON response payload — indistinguishable
from the condition being false). Use a command that always returns text, like `seed`:

```bash
tooling/squinch mc-investigate command --project games/minecraft/mods/<mod> --loader <loader> -- \
  "execute if block <x> <y> <z> minecraft:water run seed" \
  "execute unless block <x> <y> <z> minecraft:water run seed"
```

This does not scale to "what block is this" without knowing what to guess — for anything beyond a
handful of manual spot-checks, submit a probe instead (below).

**Stopping cleanly:**

```bash
tooling/squinch mc-investigate stop --project games/minecraft/mods/<mod> --loader <loader>
```

Sends RCON `stop`, falls back to killing the validated owned process (TERM escalating to KILL) if it
doesn't respond, resolves the exact listener owner if a port remains bound, and reports cleanup
failure as a failed run rather than a warning followed by a false success.

## 3. Probes: structured, repeatable measurement

Once manual command-based probing stops scaling — you need automatic, precise, repeatable
measurement rather than one-block-at-a-time guessing — submit a probe instead of hand-rolling a tick
hook, a log marker, and a completion check every time. The probe runtime is injected into
development runs by an external Gradle init overlay; it adds no tracked target source or resources.
Requests appear atomically under `<loader>/run/.squinch-investigate/requests/`; the runtime claims
them on the Minecraft server thread and atomically publishes JSONL transcripts under `results/`.
Every transcript record carries the run, request, probe, and probe-version identity, and exactly one
final record has terminal state `pass`, `fail`, `inconclusive`, or `error` — plus its observation
phase (`prediction`, `structure-start`, `generation`, `placement`, `finished-chunk`, `reload`) and
`inspected`/`skipped`/`completeness` counts. Logs stay diagnostics; the structured terminal is the
authority the CLI and scenario runner act on.

```bash
tooling/squinch mc-investigate probe --project games/minecraft/mods/<mod> --loader <loader> \
  --probe-id squinch:finished-chunk-palette --probe-version 1 --config path/to/config.json --json
```

Built-in probes, registered in
`probe-runtime/src/main/java/org/squinchmods/investigate/BuiltinProbes.java`:

- `squinch:finished-chunks` (config: `bounds`, `unit`, `max_wait_ticks`) — waits for every requested
  chunk to reach real `LevelChunk` status; the finished-chunk generation authority scenarios select.
- `squinch:finished-chunk-palette` (config: `bounds`, `unit`, `sample_heightmap`, `sample_step`,
  `max_wait_ticks`, `top_k`, `example_limit`, `predicates`) — a generic finished-chunk surface
  scanner (block/biome/height histograms, predicate matches/examples) built entirely from the shared
  `MinecraftProbeHelpers`. `pass` only if every chunk became a real `LevelChunk` in time; otherwise
  `inconclusive` with bounded `not_ready_examples` and honest completeness — never false success.
- `squinch:runtime-smoke`, `squinch:partial-control`, `squinch:exception-control`,
  `squinch:isolation-control`, `squinch:stop-flush-control` are protocol negative/positive controls,
  not investigation probes.

Reusable RTF investigation packs live under `games/minecraft/investigations/reterraforged/probes/`
(`biome-palette`, `placement-telemetry`, `cell-cache`, `heightmap-delta`) — see that directory's
README for their historical disposition, and
`games/minecraft/tooling/investigate/probe-pack-template/README.md` for authoring a new one. **Most
real findings in this codebase's history came from a purpose-built probe at the exact consumer, not
a generic scanner, and that stays true here.** The system makes a new probe cheaper and safer to
write — build/source injection without editing production files, one trigger/lifecycle mechanism,
server-thread and finished-chunk scheduling helpers, safe `WorldGenRegion` guards, structured
results — but it does not decide, and should not try to decide:

- which consumer or generation phase must be observed;
- which Mixin target and injection point actually answers the question;
- what data distinguishes the competing hypotheses; or
- what constitutes pass, fail, or inconclusive for this particular investigation.

Do not reach for a declarative config-only measurement when the real answer requires reading the
actual mechanism. A small amount of bespoke probe code that directly observes the real consumer is
preferable to a generic aggregation that measures the wrong layer.

Before publishing a normal production build, inspect its exact JAR path — this hashes and opens
every JAR, then rejects the development sentinel, injected probe classes, the probe Mixin
configuration, or generated loader-metadata references to that configuration:

```bash
tooling/squinch mc-investigate inspect-artifact \
  games/minecraft/mods/<mod>/fabric/build/libs/<artifact>-*.jar --json
```

## 4. Writing QA-only debug instrumentation (Mixins)

Write a throwaway debug Mixin, compiled directly into the mod jar via the probe overlay (not gated
behind a debug flag — it's a QA-only build, not meant to ship). The lessons below are about the
Minecraft/Mixin mechanism itself, independent of which launcher runs the build.

**Never pipe a build through `| tail` (or anything else) and trust the shell's exit code.** A
pipeline's exit status is the _last_ command's, not the build's —
`./gradlew ... | tail -60; echo $?` reports `tail`'s exit code (almost always 0), not Gradle's, so a
real build failure can still report "completed." A Javadoc comment containing `*/` mid-sentence
(closes the comment early, breaks compilation) is one concrete way this hides a failure silently.
Redirect to a file instead and check its content directly:
`./gradlew ... > build.log 2>&1; echo "EXIT=$?"`, then grep for `BUILD FAILED`/`error:`, or confirm
the expected output artifact (a `.class` file, a fresh jar) actually exists and is newer than the
source.

**`@Shadow`-ing a field declared in the mixin target's _superclass_, not the target class itself,
fails silently.** Mixin's annotation processor prints "Cannot find target for @Shadow field" as a
warning, not a hard error — the build still succeeds, but the mixin doesn't apply the way you'd
expect at runtime. Use an `@Accessor` mixin targeting the class that actually _declares_ the field
instead — accessors resolve correctly regardless of how deep in the hierarchy the field lives.

**A structure's `postProcess()` doing more than a single-column heightmap sample — footprint
averaging, a secondary uneven-terrain adjustment, anything beyond `getHeight(type, x, z)` — makes a
naive "resample and diff" QA check produce false positives.** Vanilla shipwrecks are a real example:
non-beached ones average `OCEAN_FLOOR_WG` across their whole footprint, not one column, so comparing
final placement against a single fresh sample reads a large, alarming delta that's actually zero
once the real footprint average is replicated. Either replicate the real vanilla arithmetic exactly,
or sidestep needing to at all by checking the real _outcome_ instead — a block-level scan for solid
ground near the placement is independent of whichever calculation produced the Y, and answers the
question that actually matters ("is this floating") directly.

**The hazard that causes a real crash, not just a wrong answer:** if your hook fires _during active
chunk generation_ (any hook inside a structure/feature-generation callback, e.g. a
`ChunkGenerator.applyBiomeDecoration` injection), reading a block via `level.getBlockState(pos)` is
only safe within a narrow radius of whatever chunk is _currently_ generating. `WorldGenRegion`, the
level type active at that point, calls `getChunk()` with **no bounds check at all** —
`WorldGenRegion.getBlockState()` throws a hard crash
(`IllegalStateException: Requested chunk unavailable during world generation`) the instant you read
outside that radius. A large jigsaw structure's bounding box can easily span 10+ chunks, well past
that safe radius. **Guard every read**, and use `MinecraftProbeHelpers.guardedBlockState` in a probe
rather than an unguarded call:

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
partial — this is exactly why probe results carry `inspected`/`skipped`/`complete` fields.

**For validating a fix that only matters once blocks are actually placed** (fluid/lava placement,
anything decided by an `Aquifer.FluidPicker` or similar post-generation pass), don't hook generation
at all — force-generate the target region first (`generate`, or a scenario's `finished-chunk`
authority), then read real blocks once chunks are confirmed `FULL`. This sidesteps the
`WorldGenRegion` hazard entirely, because by the time the read runs the chunks are ordinary
generated level chunks, not mid-generation ones.

**Biome fixes need the same finished-chunk rule: read `LevelChunk.getNoiseBiome()`, not a standalone
`BiomeSource` prediction.** A cold query and the real chunk generator can use different sampler
objects even when both look internally consistent — RTF's dynamic banding once attached
configuration to `RandomState.sampler()`, while `NoiseBasedChunkGenerator.doCreateBiomes()` actually
fills the chunk palette from `NoiseChunk.cachedClimateSampler()`, so cold queries showed the
intended bands while finished chunks stayed unbanded. `squinch:finished-chunk-palette` implements
the fix as a reusable pattern: force-generate at most a 16x16-chunk region, poll on the server
thread until every target is a real `LevelChunk`, read every stored quart cell with
`getNoiseBiome(quartX, quartY, quartZ)`, and compress each vertical column into biome runs. Keep the
scan on the server thread — `getChunkNow()` deliberately returns `null` off-thread — and scan the
full quart grid rather than undersampling; a 16x16 region is a few thousand cells, trivial next to
the cost of generating the chunks in the first place. When a cold scan and finished chunks disagree,
find which sampler/context the real consumer constructs before touching thresholds.

**Don't silently filter out "boring" results before aggregating.** Dropping zero-valued samples to
reduce log noise can hide the single most important finding — "this returns exactly zero, always,"
not "sometimes small," reads very differently. Track _everything_ (total count, non-zero count, sum,
max) and report one periodic/final summary, not a per-call line filtered to only the cases that
seemed interesting in advance.

**Pick the hook based on every consumer, not just where blocks get written.** A late `postProcess()`
hook is enough if the only thing that matters is visible block placement; it is not enough when
other vanilla systems read structure metadata independently — ocean monuments are the concrete case:
moving blocks in `MonumentBuilding.postProcess()` fixed the visible structure, but guardian spawning
still read the old (unmoved) structure bounds, because spawn overrides consult
`StructureStart`/piece bounds saved earlier, not the final blocks. Moving the monument during
`STRUCTURE_STARTS` instead fixed both. Before calling a structure fix complete, check: where the
visible blocks are placed; where `StructureStart`/piece bounding boxes are created and saved;
whether spawn overrides, maps, locators, or other systems read those bounds; and whether a
reload/regeneration path (e.g. `regeneratePiecesAfterLoad(...)`) reconstructs pieces later from
saved data rather than replaying generation.

**Label measurement timing in the log marker/result itself.** A height sample at structure-start
time and one during `postProcess()` can both be valid measurements that mean different things — this
is exactly what the probe protocol's `phase` field encodes structurally instead of leaving it to a
free-text log marker.

**Registration:** add the mixin's package-relative name to the mod's `*.mixins.json` `"mixins"` list
(check the existing file for the package/naming convention — RTF's is flat short-name-per-entry with
dot-separated subpackages, e.g. `"qa.MixinFoo"` for `raccoonman.reterraforged.mixin.qa.MixinFoo`).

**Two QA mixins targeting the same class with an identically-named-and-signatured field or method
silently collide** — Sponge Mixin merges them into the target class with no warning, and only one
implementation fires at runtime. `MinecraftServer` is the highest-risk target (every "run this scan
on server tick" mixin reaches for it independently), and the symptom is confusing rather than
obviously wrong: the build succeeds, the mod loads, and one scan's log just never appears or reports
values that don't match its own code. Prefix every QA-mixin member with something unique to that
specific mixin/investigation, not a generic `started`/`run`/`init` — this class of bug is exactly
why the probe runtime now owns one shared `MinecraftServer` tick dispatcher instead of one per
probe.

## 5. Exact before/after comparison

For "does this fix actually change behavior," don't manually create a worktree, copy the same Mixin
into it, check out an exact commit, build, and remember to clean it up. Run a comparison with full
40-character commit SHAs and one scenario:

```bash
tooling/squinch mc-investigate compare \
  --project games/minecraft/mods/FreeTerraForged \
  --before <parent-sha> --after <fix-sha> \
  --scenario .squinch/games/minecraft/mods/FreeTerraForged/scenarios/rtf-biome-palette-benchmark.toml \
  --expect different --json
```

This creates two temporary detached worktrees under `investigation-state/worktrees/`, injects the
identical probe pack into both, runs them sequentially (worldgen benchmarks don't tolerate
contention, so before/after runs are locked against overlap by default), and requires identical
scenario-input and injected-probe fingerprints on both sides. Request IDs, timestamps,
polling/timing fields, and placement CPU time are excluded from behavioral equality; list order and
all remaining numbers stay exact. The comparison artifact retains both normalized sides, recursive
field-level differences, exact commit/tree identities, and code/environment/input/probe/timing
fingerprints. Clean temporary worktrees are removed in `finally`; a failed side or an unexpectedly
modified worktree is preserved and reported rather than force-removed — no persistent baseline
worktree survives a clean run, but diagnostic state survives a broken one. Existing result files can
still be compared directly with `compare --left FILE --right FILE`.

**Pin to the exact commit, not a branch tip.** The fix commit itself for "after," its immediate
parent for "before" — a live branch tip almost always carries later, unrelated commits layered on
top (in one case, ~15 of them, including an unrelated fix from the same investigation), which
silently weakens the comparison from "does this commit work" to "does this commit plus everything
else that happened to land afterward work."

`compare` covers the common case: the same probe pack, run against two exact commits. For anything
outside that — comparing something that isn't a probe-pack scenario, or working with a mod that
doesn't have the probe overlay wired up yet — the underlying pattern is still a **worktree, not
stash/checkout**: `git worktree add --detach <path> <exact-sha>` behaves identically to a normal
worktree for building, with none of the historical stash-based failure modes (`gradlew`'s executable
bit not reliably persisting across a branch checkout, `git stash pop` not cleanly restoring an
untracked file across a branch switch when there's also a conflicting tracked-file change).

## 6. Profiling and repeated measurements

Establish host health before collecting performance or memory evidence: inspect load, memory and
swap pressure, investigation ownership, bound ports, and surviving JVM process states. A JVM in
uninterruptible teardown, pathological load, failed prior cleanup, or incomplete profiler output
invalidates wall-clock, allocation, RSS, startup, shutdown, and lifecycle comparisons. Preserve the
failed run as labeled diagnostic evidence, recover or restart the host, and repeat the affected
measurements under matched clean conditions. Functional source evidence and deterministic outputs
remain separate claims; they do not rehabilitate contaminated timing or memory data.

For "is it actually faster," set `repeat` and a nonzero `offset = [x, z]` on a scenario's generation
step — the parser requires every translated coordinate window to be disjoint (repeating the same
window mostly measures loaded/cached behavior, not generation cost) and caps one step at 20
observations. Each observation retains its exact bounds plus generation/probe/total seconds; the
step reports every value alongside median, minimum, maximum, and range — never one number hiding the
variance. Set `jfr = true` on any step to record only that step with the owned Minecraft JVM; the
resulting nonempty, hashed `.jfr` lands under that run's `profiles/` directory and is referenced by
both the scenario result and manifest. Lifecycle timing separately records startup, verified
world-open, generation, probe, save, and shutdown — never folded into one number.

Do not describe a timed `forceload`/generation window as server startup time — start the dedicated
server first, wait for readiness, then time generation against a _previously ungenerated_ coordinate
window. Seed, preset, loader, mod set, JVM arguments, window size, and machine load must match
between runs; one wall-time result shows impact, repeated fresh windows establish a range. Use a
profiler alongside wall time when attributing cause, not as a replacement for it — in the RTF
TerraBlender case, identical 64-chunk windows showed a large wall-time reduction, while JFR
independently showed the relevant biome-resolution hotspot falling from 38.8% to 1.24% of execution
samples and a redundant namespaced surface dispatcher disappearing from sampled stacks. That
combination is much stronger evidence than either one alone.

## 7. Artifacts, retention, and cleanup

Generated state lives beneath `games/minecraft/investigation-state/` and is ignored by Git. Every
run owns a unique ID, artifact directory, log, manifest, command stream, and summary; every world
gets a run-derived level name — no launch overwrites a previous run's log or silently reuses its
world. Target `eula.txt`/`server.properties` are backed up and restored. The launcher invokes a
non-executable wrapper as `bash ./gradlew`, uses `env.sh`, disables reusable Gradle daemons for the
launch command, and never changes the wrapper's tracked mode.

Every JVM-bearing operation uses a unique user-systemd service and recursively enumerates its
control group. The exact unit intent becomes durable `launching` ownership before `systemd-run` is
spawned, wrapper identity enriches that owner immediately after spawn, and main-PID discovery
advances it instead of opening an unrecorded process interval. Teardown validates Linux process
start identities before signaling, removes only force-load regions recorded by the run, and treats
any remaining process/listener/file/world/display cleanup problem as a failed run, not a warning.
Preparation checks active ownership before creating run artifacts and rolls back partial
managed-file staging. All blocking teardown phases share the caller's one monotonic timeout budget;
no phase restarts that budget. If an owned process enters uninterruptible sleep, the run retains
bounded kernel diagnostics and active recovery state; do not probe its procfs stack, because a state
transition can make that read block the observer too. `doctor --recover` is the explicit recovery
path for retained incomplete state. Retention is explicit per run via
`--retention {discard,keep-on-failure,keep}` (default `discard`). Use
`mc-investigate clean --older-than-days <n>` (dry run by default; add `--apply` to delete) to prune
kept runs — it rejects active runs, symlinks, foreign manifests, and paths outside the owned state
root, and deletes directly after validation; there is no speculative trash layer.

If driving this from an agent session with background task tracking, background tasks and scheduled
wakeups don't automatically clean themselves up just because the underlying process died — verify
and explicitly stop/cancel anything still shown as "running" that shouldn't be.

## 8. Reading vanilla Minecraft and mod source for comparison

A full decompiled/mapped vanilla source tree already exists on this machine — do not reconstruct
vanilla behavior from memory or guess at it; read it directly:

```text
games/minecraft/reference/sources/<minecraft-version>/official/src/net/minecraft/...
```

Other Minecraft-version siblings may also exist under the same `reference/sources/` root for
older-version comparisons. This is genuine decompiled source (confirmed present, not a guess) —
prefer it over web search or training-data recall whenever comparing a mod's worldgen/mixin behavior
against vanilla's actual implementation.

The same root has a `mods/` sibling per version —
`reference/sources/<minecraft-version>/mods/<mod-name>/` — for third-party mod source, checked out
from that mod's own public repository at whichever branch/tag targets the version in the path. It is
populated on demand (there is no `mc-source` equivalent for mods; clone directly with `git`) and
exists for exactly the same reason as `official/`: read a mod's real, current source when
investigating compatibility rather than trusting a linked commit that may already be stale or a
memory of how the mod used to work.

Always clone shallow and sparse — `--depth 1 --filter=blob:none`, then `git sparse-checkout set` to
only the directories actually needed. `--depth 1` is not optional: a non-shallow `blob:none` clone
still pulls the branch's entire commit history, which for an actively developed mod can be tens of
megabytes even with no blob content. To update to whatever the mod has since published, delete the
directory and re-clone with the same recipe rather than `git fetch`/`git pull` in place — re-cloning
is cheap at this scale and is the only way to guarantee the old commit doesn't linger alongside the
new one. See `.agent-docs/games/minecraft/README.md` for the exact command sequence. Neither
`official/` nor `mods/` is committed — treat any given checkout as disposable.

## Recording new friction

If something about the tooling itself — not a mod-specific finding — surprises you, costs real time,
or exposes a gap, record it in `agentic-development-findings.md` using its entry template, rather
than expanding this guide with narrative. This file documents the completed, current workflow; the
findings doc is where unresolved general friction accumulates until it's fixed or promoted into this
guide as a real change.
