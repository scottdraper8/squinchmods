# Resumption prompt: RTF ocean-depth structure fix + biome-banding follow-up

Two independent threads live under `games/minecraft/mods/ReTerraForged` (branch
`feat/configurable-ocean-depth`), both stemming from PR #97's configurable `oceanDepth`. Read the
relevant doc fully before resuming either one — this file is an index, not a substitute.

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/trial-chambers-and-ocean-structures.md
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/biome-climate-banding-investigation.md
```

## Thread 1: Trial Chambers / Ancient City structure placement — investigation complete, shipping prep is next

Root cause proven for both structures (blind, terrain-unaware `start_height`, confirmed via
`trial_chambers.json`/`ancient_city.json`). A fix is implemented and empirically validated across
every tested preset: real floor/surface grid sampling, a real-build-and-measure safety check
(replacing an earlier hardcoded-clearance approach that was tried and rejected — see the doc for
why), and an upward window-rescue capability that recovered 26-29 real Trial Chambers on a preset
that previously produced zero, anywhere. Same mixin, same mechanism, applies identically to both
structures. Full empirical results, constant inventory, and known caveats are in
`trial-chambers-and-ocean-structures.md` — do not re-derive any of this, it's already measured.

**What's actually left** (see that doc's "Not yet done" section for the full list; the two that
matter most):

1. **Production cleanup, the real blocker if this ships.** The fix currently lives as QA-only
   scaffolding: unconditionally verbose logging on every step (corrections, biome checks with biome
   names, per-call timing), and it lives in `raccoonman.reterraforged.mixin.qa` alongside mixins
   that were never meant to ship. Before this goes into a real PR: move
   `MixinJigsawStartHeightFixQA` out of the `qa` package into production code, strip the timing
   instrumentation entirely (that was our own benchmarking tooling), and cut the logging down to
   something a real server wouldn't be spammed by. The QA-only diagnostic mixins
   (`MixinTrialChamberQA`, `MixinBeardifierTimingQA`, `MixinAncientCityQA`,
   `MixinAncientCityCandidateScanQA`, `MixinAncientCityDeepDarkFloorScanQA`) get removed entirely,
   not promoted.
2. **The product/scope call is still open**: does this belong in `feat/configurable-ocean-depth` at
   all, or ship as a documented known limitation instead? Not something to resolve technically.

Smaller, non-blocking items also listed in that doc's "Not yet done": `beard_box` was never read at
the code level (though solidity outcomes suggest it's fine — see the doc's dedicated section on
this), Ancient City was never specifically tested at the mountain preset (architecturally should
behave identically to Trial Chambers, not directly observed), real mob-spawn behavior was proven
architecturally but never watched live, and the reasoned-but-unmeasured constants (`MARGIN`,
`BOUNDARY_TOLERANCE`, `GRID_STEPS_PER_SIDE`) could be tightened with more targeted testing if it's
worth the effort at ship time.

## Thread 2: Biome climate-banding — deliberately deferred, zero progress since flagged

Separate, real issue: RTF's `deep_dark`/`dripstone_caves`/`lush_caves` climate eligibility can
become unreachable under very deep, shallow-`worldDepth` oceans, independent of the
structure-placement bug above. Mechanism is understood at the source-code level (see "Larger Open
Question" in `biome-climate-banding-investigation.md`) and two candidate fix directions are
documented (a formula-derived `oceanDepth` clamp vs. a decoupled climate-only `depth` function) but
neither is built. **This was deliberately set aside this session** ("things to look further into
later on") — next steps are exactly the "Remaining evidence needed" list in that doc (vanilla
empirical baselines, a controlled RTF preset matrix, and the terrain-vs-climate-only `DEPTH`
distinction with blast-radius measurement). Do not start building a fix without that evidence
gathered first.

## Working tree / git state at handoff

As of this handoff, the QA investigation work (all mixins under
`common/src/main/java/raccoonman/reterraforged/mixin/qa/` and
`common/src/main/java/raccoonman/reterraforged/qa/`, plus the `reterraforged-common.mixins.json`
registrations) needs a preservation decision before `feat/configurable-ocean-depth` can be cleaned
up for real shipping work — check `git log`/`git branch` in the RTF submodule for whatever was
actually decided, since this file may be stale on that specific point by the time it's read again.

Documentation updates in `.agent-docs/` and the `games/minecraft/tooling/` fixes (dev-server
port-verification/timeout fixes, README known-limitations section) are durable and were pending a
commit decision to the top-level `squinchmods` `main` branch at the same handoff point — check
`git log` there too rather than trusting this file's snapshot.

## Practical notes carried forward

- Use `games/minecraft/tooling/dev-server`, not manual Gradle/RCON — see
  `live-worldgen-investigation-howto.md` for the full workflow, including known `dev-server` process
  cleanup gaps and their workarounds (also documented in `games/minecraft/tooling/README.md`'s
  "Known limitations").
- A full decompiled/mapped vanilla 1.21.1 source tree exists locally at
  `games/minecraft/reference/sources/1.21.1/official/src/` — read it directly for anything
  vanilla-behavior-related rather than reconstructing from memory.
- Reference presets (very-deep, Goldilocks, shallowest, and this session's hand-reconstructed
  extreme-shallow/mountain preset) are catalogued in `qa-presets.md`, including the technique for
  hand-editing a datapack's `preset.json`/`noise_settings`/`dimension_type` together consistently
  (vanilla requires `min_y`/`height` to be multiples of 16 — a real constraint that broke an earlier
  attempt) rather than needing a fresh RTF UI export every time.
- Seed `3216933670` is the standard seed for all of this investigation's reproduction cases.
