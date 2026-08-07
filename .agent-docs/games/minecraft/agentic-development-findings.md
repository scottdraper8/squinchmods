# Minecraft Agentic Development Findings

## Status: 2026-08-01

Bounded log of general Minecraft-tooling friction — not mod-specific investigation findings (those
live under `mods/<mod>/plans/`), and not a narrative history of how any one investigation went. An
item lives here only while it's unresolved; once fixed, it moves into the resolution table below
with the evidence that closed it. See `agentic-development-guide.md` for the current workflow this
friction fed into.

## Resolved

The `agentic-development-tooling-implementation-plan.md` build (Phases 0-9) closed every concrete
friction point raised by the original `dev-server`-era investigations:

| Friction                                                                                                                                                                                                             | Resolution                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hand-rolled stdin pump to drive a headless server was fragile (stale FIFO readers, Gradle daemon relaying stdin unreliably, dropped command bursts)                                                                  | `mc-investigate start`/`command` authenticate over RCON as part of readiness; no stdin path exists                                                                                                                                       |
| Finding a real target location by blind coordinate search on a live server was slow and unreliable (`/locate` can return noise-space matches far from surface terrain; continent scale assumptions were often wrong) | `cell-scan` (Phase 5): a standalone JVM runs RTF's real preset/tile objects with prediction/RTF-tile authority, no server, seconds instead of a live search loop                                                                         |
| Editing a mod's hardcoded default preset for testing meant a full rebuild + relaunch per change                                                                                                                      | Source-form fixtures + `rtf_ephemeral` JSON Merge Patches materialize a datapack without touching mod source or rebuilding                                                                                                               |
| No documented hazard for reading blocks mid-generation (`WorldGenRegion` throws a hard, unguarded crash outside a narrow radius)                                                                                     | Documented in the guide's Mixin section; `MinecraftProbeHelpers.guardedBlockState` makes the guard the default path in a probe                                                                                                           |
| Deploying the same QA instrumentation across two branches was a manual stash/checkout dance (`gradlew`'s executable bit not persisting across checkout, `stash pop` conflicts)                                       | `compare --before/--after` (Phase 7): disposable detached worktrees, identical injected probe pack on both sides, removed in `finally`                                                                                                   |
| Nothing labeled which generation phase a measurement came from; the same nominal height query could mean different things depending on when it ran                                                                   | Probe protocol's structured `phase` field (`prediction`/`structure-start`/`generation`/`placement`/`finished-chunk`/`reload`), Phase 3                                                                                                   |
| QA world saves needed manual retention/cleanup; generated `world.*` directories piled up                                                                                                                             | Per-run `--retention {discard,keep-on-failure,keep}` plus `clean --older-than-days`/`--apply`, Phase 1                                                                                                                                   |
| A `--no-daemon` Gradle wrapper could remain alive after Minecraft fully saved and exited, consuming the whole shutdown timeout                                                                                       | Teardown now treats bound listeners as the save-in-progress authority and gives a listener-free boundary a 5-second grace period before TERM/KILL, instead of waiting out the full timeout                                               |
| No offline ("no running server") terrain/structure sampler existed; considered but not pursued for lack of reusable registry/bootstrap plumbing                                                                      | `cell-scan` standalone JVM harness, Phase 5                                                                                                                                                                                              |
| No vanilla command reads an arbitrary block's exact type (`/data get block` only works on block entities), so anything beyond a couple of manual predicate checks didn't scale                                       | The structured probe protocol (Phase 3) is the real escape hatch — a probe reads real blocks directly instead of guessing predicates one at a time; the guide still documents the predicate-check trick for genuinely casual spot checks |

## Active

Three items remain, and none is a "not built yet" gap in the completed tooling:

1. **An `rtf_ephemeral` merge patch that changes `world.properties.worldHeight`/`worldDepth`
   produces a datapack whose `preset.json` reflects the patch but whose `minecraft:dimension_type`
   stays at the _base fixture's_ original height/depth.** Materializing an ephemeral preset against
   `vanilla-depth-maximum-ocean` (base `worldHeight = 384`) with a patch setting
   `worldHeight = 1024` produced a real, `lifecycle: succeeded` scenario run whose finished chunks
   were uniformly flat at Y383 with `deep_dark`/`dripstone_caves` biomes at the surface — the
   patched preset's density functions were trying to place terrain above Y900, but the actual
   dimension (`height: 448`, `min_y: -64` in the materialized `dimension_type/overworld.json`, i.e.
   exactly the base fixture's own 384+64) silently capped and misclassified it. Cost about 15
   minutes and two extra full start/generate/stop cycles to diagnose (extracting the materialized
   datapack ZIP and comparing `preset.json` against `dimension_type/overworld.json` was what
   actually found it). **Workaround that works today:** build the merge patch to omit
   `world.properties` entirely (patch every other top-level section, but delete/omit `properties`
   under `world` so it falls through to the base fixture's own value) — pick a base fixture whose
   own `worldHeight`/`worldDepth` already fits the case, rather than trying to override them through
   the patch. **Resolution path:** either document this as a hard constraint on `rtf_ephemeral`
   (`world.properties` height/depth cannot be safely patched, choose your base fixture accordingly),
   or fix `materialize_ephemeral_fixture` to regenerate `dimension_type`/`noise_settings` from the
   fully patched preset instead of carrying them forward unchanged from the base fixture's own
   archived datapack.
2. **`squinch-qa`'s `command-script` executor cannot pin an exact `level-seed`.** This matters for
   reproducing a specific real-world case found worth re-testing under the release-QA matrix. Out of
   scope for `mc-investigate` by design (the "Release QA boundary" in the implementation plan) —
   this belongs to `games/minecraft/tooling/qa/` if it's ever addressed.
3. **Losing sight of _why_ mid-investigation, once live-testing tooling exists and works, is a
   discipline risk, not a tooling gap.** More than once, a proposed measurement would not have
   actually distinguished between the competing hypotheses it was meant to distinguish. No amount of
   tooling prevents this — it needs direct pushback toward "what does this specific result actually
   tell us" rather than accumulating more test infrastructure and data points for their own sake.
   Kept here as a standing reminder rather than something to "fix."

## Entry template

Use this shape when adding a new item. Keep it to what's actually needed to act on it — this is a
log entry, not an investigation writeup.

```markdown
### <short title>

**Symptom:** what actually went wrong or cost real time, stated concretely (not "X is hard").
**Scope:** confirm this is general tooling friction, not a mod-specific finding — if it's the
latter, it belongs in that mod's investigation docs instead, not here. **Cost:** what it actually
cost (a specific detour, a wrong conclusion, a lost run) — skip vague entries that aren't tied to a
real incident. **Resolution path:** what would actually close this, if known.
```

## Promotion and pruning rules

- An active entry is promoted to the resolution table the moment a real tooling change closes it —
  record the fix and the evidence that verified it, not a narrative of how the fix was built (that
  belongs in the implementation plan's evidence log while the work is in progress).
- If an active entry turns out to be about one mod's specific behavior rather than the tooling, move
  it to that mod's investigation docs and remove it from here.
- Don't add an entry for a single one-off annoyance with no plausible general recurrence — this file
  is for friction likely to hit a future investigation again, not everything that went wrong once.
- Condense related resolved entries into one resolution-table row sharing a root cause/fix rather
  than keeping one row per historical incident.
- If this file's active section stays empty for a long stretch, that's the intended steady state —
  do not manufacture entries to keep it populated.
