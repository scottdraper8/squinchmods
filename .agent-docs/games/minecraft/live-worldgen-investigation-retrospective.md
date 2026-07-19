# Live Worldgen Investigation Retrospective

## Status: 2026-07-18

Not a plan — a record of how a real, extended live-investigation session actually went (RTF
ocean-depth PR, ocean monuments, and the trial chamber floating-structure bug), written down for
whoever next builds out squinchmods tooling to have real pain points to work from instead of
guessing. The technical findings live in the RTF ocean-depth docs; this doc is about the _process_,
not the RTF-specific result.

Case studies from this session:

- `mods/ReTerraForged/plans/ocean-depth/monument-placement-research.md`
- `mods/ReTerraForged/plans/ocean-depth/trial-chambers-and-ocean-structures.md`

## What this session actually needed to do

Confirm and quantify reported worldgen bugs on real seeds/presets, then isolate root causes among
several code-level hypotheses — requiring a real, running instance of the game with the mod loaded,
not just static code reading.

## Pain points, roughly in the order they showed up

**Driving a headless dev server via raw stdin is fragile in ways that cost a lot of time.** Tried
piping commands into `./gradlew :fabric:runServer` through a named FIFO. Hit, in sequence: a stale
server process that didn't fully exit after `stop` and kept a second reader on the same FIFO,
silently stealing commands sent to what looked like a fresh session; Gradle's daemon-based execution
relaying stdin through its own internal pipe in a way that broke once a stale build session was
sharing the daemon; and, even after removing the daemon (`--no-daemon`), bursts of more than a
couple of commands sent in quick succession being unreliably dropped for reasons never fully
root-caused. Each of these looked like "the bug is real" (e.g. "there's no ocean anywhere") before
turning out to be "the command never actually reached the server." **RCON** (Minecraft's actual
built-in remote-command protocol — proper per-command request/response framing, no shared-reader
ambiguity, no daemon relay) turned out to be the right tool from the start and should have been
reached for immediately instead of hand-rolling stdin plumbing. No `mcrcon`-equivalent package was
available, so this ended up as a ~60-line hand-written Python client.

**No way to read an arbitrary block's exact type via vanilla commands.** `/data get block <pos>`
only works for block _entities_ (chests, signs, etc.) — for a plain block like stone or water it
errors "The target block is not a block entity." There's no vanilla "tell me what block this is"
query. The only way to test what's at a coordinate via commands is guessing specific block-type
predicates one at a time (`execute if block x y z minecraft:water`), which is slow, and silently
incomplete if you don't happen to guess the right block.

**Finding a real target location (ocean, a specific structure) by blind coordinate search is
expensive.** Burned real time sweeping outward from spawn checking for water before the actual
problems became clear: `/locate biome` can return a match based on 3D noise-parameter space that
doesn't correspond to visible surface terrain at all (returned coordinates at Y values far from sea
level); a world's continent scale can be far larger than assumed, so "still land at 5000+ blocks in
every direction" can be entirely normal rather than a sign something's broken; and
`SpawnType .CONTINENT_CENTER` deliberately biases spawn toward the most inland point of a landmass
regardless of how much ocean exists elsewhere, actively working against a "just search near spawn"
strategy.

**Editing a mod's hardcoded default preset for testing means a full rebuild + relaunch per change**
— each cycle a couple of minutes. Switched to hand-authoring a preset JSON that matched the mod's
real config schema (verified field-by-field against the actual codec definitions and the actual
import-parsing code path, not assumed from the schema alone) and handing it to the person with the
real client, who could preview/adjust/export it live using the mod's own GUI tooling — much faster
than continuing to blind-tune values on a headless server and rebuild each time.

**Client-side reproduction was consistently faster and more trustworthy than anything done
server-side**, for confirming whether a bug was real at all. The headless server became genuinely
useful only _after_ a concrete, real, reproducible case (exact seed + exact exported datapack)
existed to test against — as a tool for precise, automatable follow-up measurement, not as the tool
for original discovery.

**Custom debug instrumentation (compiled into a QA-only build) was the actual unlock for getting
objective, automatic, quantified answers** instead of manual one-block-at-a-time command probing —
but building it safely required understanding a Minecraft-specific hazard that wasn't obvious going
in: reading blocks during active chunk generation (inside a structure/feature-generation hook) is
only safe within a narrow radius of whatever chunk is _currently_ generating; reading further throws
a hard crash (`IllegalStateException: Requested chunk unavailable during world generation`), not a
graceful failure. First version of the instrumentation didn't know this, scanned a structure's full
bounding box (which can span 10+ chunks), and crashed the tester's real game. Fixed by guarding
every read with a chunk-availability check first. Costly lesson to learn after shipping rather than
before.

**For structure bugs, moving blocks is not always enough.** The first ocean-monument fix moved the
visible monument during `MonumentBuilding.postProcess()`, which was late enough to write the blocks
in the intended place. It was still the wrong pipeline point for the full behavior, because guardian
spawn overrides consult the structure start/piece bounds. That produced a split result: blocks at
the adjusted Y, spawn area still around vanilla `Y=39`. The working fix moved the monument during
structure-start generation, before those bounds were saved and later used by spawn logic.

**Reload/regeneration paths need their own trace for vanilla structures.** Ocean monuments have a
special `OceanMonumentStructure.regeneratePiecesAfterLoad(...)` path that rebuilds the monument from
saved X/Z/orientation and reintroduces the vanilla hardcoded `Y=39` unless corrected. Static source
reading found that path; live testing found the placement problem. Both mattered. Future structure
fixes should explicitly ask "what reconstructs this after load?" before assuming generation-time
movement is the whole fix.

**Building/deploying the same instrumentation across two branches repeatedly is its own manual
dance** right now: stash, checkout, recreate the (deliberately uncommitted, QA-only) mixin file and
its registration line by hand, build, copy the jar out, then reverse all of it to get back to a
clean branch state — complicated further by a build script's executable bit not persisting across
branch checkouts, so it needs re-setting every switch, which then conflicts with git stash if the
stash also touched that file.

**Real risk of losing sight of _why_ mid-investigation, once live-testing tooling exists and
works.** More than once, a proposed test would have measured something without actually
distinguishing between the competing hypotheses it was meant to distinguish (e.g., proposing to
disable one code path without first confirming that code path could even affect the observed
symptom). Needed direct pushback, more than once, to redirect back to "what does this specific
result actually tell us" rather than continuing to accumulate more test infrastructure and data
points for their own sake.

## How data actually got collected, in practice

- Static reading of a full decompiled vanilla Minecraft source tree already available in-repo
  (`games/minecraft/reference/sources/`), plus the mod's own source, to understand exact mechanisms
  _before_ testing anything — this was reliable and fast throughout, no pain points here.
- Cloning and reading other mods' actual source directly (several ocean/terrain mods, a structure
  mod) to compare real implementations, rather than trusting READMEs or memory.
- A headless Fabric dev server (`./gradlew :fabric:runServer`), eventually driven via RCON with a
  small hand-written Python client once stdin-based approaches proved unreliable.
- Custom QA-only Mixin instrumentation, compiled directly into a mod jar, once manual per-block
  command probing stopped scaling — required a rebuild+relaunch cycle to iterate, but far more
  scalable than commands once the approach was debugged.
- Real client-side testing by a human tester (screenshots, F3 coordinates, an exported datapack from
  the mod's own preset-editor GUI) — this was the actual decisive evidence at every "is this real"
  checkpoint, and also how config values got validated against a live preview instead of guessed at
  blind on a headless server.
- A hand-authored config file matching the mod's real schema, handed to the tester to load into
  their own client rather than continuing to iterate on a server-side guess.
- Separate measurements by generation phase. For the monument fix, structure-start-time height
  samples and placement-time heightmap reads were both useful, but they answered different
  questions. Treating them as interchangeable would have hidden the structure-bounds/spawn issue.

## Loose implications for tooling (not a plan, just what stood out)

- A reliable, reusable RCON client/wrapper would have saved real time — this was hand-rolled from
  scratch mid-investigation.
- The existing QA `command-script` executor doesn't currently let a test pin a `level-seed`, which
  matters a lot for reproducibility once a specific real-world case is found worth re-testing.
- An "offline, no running server" terrain/structure sampler — reusing whatever a mod's own preview
  tooling already does internally — was considered mid-session as a way to avoid repeated
  spin-up/tear-down cycles just to check where something is, but wasn't pursued because the
  registry/bootstrap plumbing it would need wasn't already available as reusable infrastructure.
- Nothing currently captures or documents the "safe to read blocks only within a narrow radius
  during active generation" hazard anywhere a future debug-mixin author would see it before hitting
  it live.
- The current process for building a throwaway QA-only mixin across multiple branches (stash /
  checkout / recreate by hand / build / copy / reverse) is manual and error-prone enough that it
  happened identically, by hand, more than once in this session alone.
- QA/debug tooling should make it easy to label which generation phase a measurement came from
  (`STRUCTURE_STARTS`, `FEATURES`/`postProcess`, delayed after generation, reload). The same nominal
  height query can have different implications depending on when it runs.
- QA world saves need lifecycle management. Renaming worlds to preserve failed/intermediate runs was
  useful during the investigation, but the generated `world.*` directories had to be manually
  audited and deleted afterward. A future runner should make cleanup/retention explicit.
