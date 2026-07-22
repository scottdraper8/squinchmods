# Resumption prompt: RTF ocean-depth (PR #97) status and open follow-ups

One active thread remains under `games/minecraft/mods/ReTerraForged` (branch
`feat/configurable-ocean-depth`), stemming from PR #97's configurable `oceanDepth`. Read the
relevant doc fully before resuming — this file is an index, not a substitute.

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/
```

## PR #97 status: ready to leave draft

Every checklist item that's actually in scope for this PR is shipped and validated. The PR itself is
still in draft — that's a deliberate manual step left for the user to do, not something waiting on
more work here.

- **Configurable ocean depth** (the core feature) and **Trial Chambers / Ancient City structure
  placement** were shipped in earlier sessions. See `trial-chambers-and-ocean-structures.md`.
- **Extreme ocean floor variation/noise**: root cause was the deep-ocean floor noise's horizontal
  wavelength staying fixed while its vertical range scaled with `oceanDepth`, producing
  proportionally steeper terrain at large depths. Fixed by scaling the noise's horizontal wavelength
  (and warp strength) by the same `oceanDepth / DEFAULT_OCEAN_DEPTH` ratio the vertical range
  already used, in `Populators.makeDeepOcean`. Shipped as `73838b9`, pushed to origin.
- **Conflicting lava level**: shipped earlier (`5173a91`) and retroactively validated this session
  using real block-generation QA (forceload + scan real placed blocks, not a synthetic harness) —
  confirmed no obsidian, correct floor material, and correct lava behavior across both a severe
  conflict case (`oceanDepth=677`) and a mild one (Goldilocks preset). No bugs found.

Two real issues were found during this work that are **not** in scope for this PR and need more
investigation before they can be scoped as their own PRs (see below).

## Island interaction (archipelago) — needs more investigation before scoping a follow-up PR

Full findings are in `island-interaction-investigation.md`. Short version: three distinct mechanisms
contribute to the "near vertical walls aren't ideal" symptom, only one of which is actually caused
by `oceanDepth`:

1. A domain-warp fold in the coastline noise (pre-existing, `oceanDepth`-independent, has a tested
   one-line fix not yet shipped anywhere).
2. The island shelf's width is fixed in alpha-space but the elevation it has to cover scales with
   `oceanDepth` — this one genuinely is caused by this PR's feature.
3. `continentFade`'s blend window is too narrow across every shipped preset's control points —
   pre-existing, `oceanDepth`-independent.

Two isolated-patch attempts for #2 failed for structural reasons (see the doc); the real fix looks
like rebuilding archipelago placement on a cellular/Worley basis (mirroring
`UpliftContinentGenerator`) so "distance to coastline" becomes a first-class value instead of
something inferred from a smoothstepped alpha. That's a bigger, riskier change (relocates every
existing archipelago island) than anything else this session touched.

**What's still needed before writing succinct PR-scoping notes**: whether Finding 1's warp fix
should ship on its own ahead of the larger rewrite (it's a real, isolated bug with no dependency on
it), and rough sizing/sequencing for the cellular rewrite itself. Both are open calls, not technical
unknowns — the mechanism is fully understood, the decision is scope and sequencing.

The three `-archipelago` test presets built for this investigation
(`test-presets/*-archipelago.zip`) are kept — whoever picks up the rewrite will need real,
screenshot-able islands to work against.

## Biome climate-banding — deliberately deferred, zero progress since flagged

Separate, real issue: RTF's `deep_dark`/`dripstone_caves`/`lush_caves` climate eligibility can
become unreachable under very deep, shallow-`worldDepth` oceans, independent of everything else in
this PR. Mechanism is understood at the source-code level (see "Larger Open Question" in
`biome-climate-banding-investigation.md`) and two candidate fix directions are documented (a
formula-derived `oceanDepth` clamp vs. a decoupled climate-only `depth` function) but neither is
built. Next steps are exactly the "Remaining evidence needed" list in that doc (vanilla empirical
baselines, a controlled RTF preset matrix, and the terrain-vs-climate-only `DEPTH` distinction with
blast-radius measurement). Do not start building a fix without that evidence gathered first.

## Practical notes carried forward

- Use `games/minecraft/tooling/dev-server`, not manual Gradle/RCON — see
  `live-worldgen-investigation-howto.md` for the full workflow.
- A full decompiled/mapped vanilla 1.21.1 source tree exists locally at
  `games/minecraft/reference/sources/1.21.1/official/src/` — read it directly for anything
  vanilla-behavior-related rather than reconstructing from memory.
- Reference presets are committed at
  `.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/test-presets/` — see
  `qa-presets.md` for the current list and checksums. Prefer these canonical copies over
  re-exporting or hand-reconstructing.
- `qa/configurable-ocean-depth` (local only, not pushed) carries `feat/configurable-ocean-depth`'s
  full history plus every QA-only mixin built across this whole investigation (ocean-floor-noise
  profiling, live lava-level validation, and the earlier Trial Chambers/Ancient City scanners). Use
  it as the starting point for any future re-verification instead of rebuilding scaffolding from
  scratch. See `refs/branch-map.md`.
- Seed `3216933670` is the standard seed for all of this investigation's reproduction cases.
