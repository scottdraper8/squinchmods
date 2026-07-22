# Island Interaction (Archipelago) Under Deep RTF Oceans

## Status: 2026-07-22

Investigation into PR #97's "Island Interaction" checklist item ("near vertical walls aren't ideal,
ideally should fade over a wider area. Is this a preset config issue?"). Originally suspected to be
the same root cause as "Extreme Ocean Floor Variation/Noise" (also on the checklist). That symptom
turned out to have a clean, isolated fix (see `pr-97-ocean-floor-noise-comment-draft.md` /
`Populators.makeDeepOcean`). Island Interaction did not. What follows is why: three distinct,
independently-confirmed contributing mechanisms, only one of which is actually caused by
`oceanDepth`, and a case for why a real fix needs to rebuild part of the archipelago system rather
than patch it. **Not fixed in this PR** - this doc is the equivalent of
`biome-climate-banding-investigation.md` for this feature: real findings, no shipped fix, flagged
for a dedicated follow-up PR.

## Background

None of the three committed QA test presets (`very-deep.zip`, `goldilocks.zip`,
`mountain-worldDepth16.zip`) actually had archipelago turned on (`island.enableArchipelago: false`
in all three, confirmed by reading the raw preset JSON - this field lives at the top level of
`Preset`, not nested under `world`, which is easy to miss). Built three `-archipelago` variants
(same data, `island` block replaced with `IslandSettings.makeDefault()`) specifically to get real,
screenshot-able islands for this investigation; they're alongside the originals in `test-presets/`.

Seed used throughout: `3216933670` (matches the existing QA convention).

## Method

Same QA-mixin approach as the ocean-floor-noise and structure investigations (see
`live-worldgen-investigation-howto.md`): a throwaway mixin hooks `MinecraftServer.tickServer`, grabs
the live per-preset `Heightmap` via `RTFRandomState.generatorContext()`, and calls
`heightmap.applyTerrain(cell, x, z)` directly - the actual production code path, no chunk generation
or forceload needed. Used both a controlled/synthetic harness (fixed seed, hand-built `Levels`/
`ArchipelagoPopulator`, sweeping `oceanDepth` with everything else held constant, to isolate causal
variables) and a live harness against the real per-preset generator (to confirm findings hold with
real seed/settings and to get real, teleportable coordinates).

## Finding 1: coastline noise fold (confirmed, has a clean fix, not shipped in this PR)

`ArchipelagoPopulator`'s island shape (`sizeNoise`) is built from a base simplex noise put through
three chained domain warps ("A high-frequency warp at the end to 'ruffle' the edges, preventing
smooth, perfect arcs" per the existing code comment). The innermost warp's strength-to-scale ratio
is `0.15/0.08 = 1.875` - the warp moves the sample point by almost _double_ its own wavelength.
Domain warping folds space on itself once strength exceeds wavelength, and a fold is exactly what a
smoothstep-based alpha value can't survive without a visible seam.

Confirmed directly, real island, real seed, no synthetic setup: at `(230250, 163350)` in
`very-deep-archipelago.zip`, terrain is `island_mountains` at Y=252. One block away, at
`(230250, 163351)` — sorry, `163351` in the actual log — terrain is `deep_ocean` at Y=18 (oceanDepth
63 baseline) or Y=-406 (oceanDepth 677). Same exact fold, present at _both_ depths, confirming it's
not caused by ocean depth - it's a pre-existing bug in the warp itself.

Fix tested: reduce that warp's strength multiplier from `0.15F` to `0.03F` (ratio 0.375, in line
with the other two warps in the same chain, 0.25 and 0.6). Re-profiled the same location afterward:

```text
oceanDepth=677, before fix: 163350:240:island_mountains  163351:-406:deep_ocean   (one-block, 646-Y collapse)
oceanDepth=677, after fix:  163136:-429  163137:-429 ... 163138:45  163139:63:island (smooth, ~8-block ramp)
```

The fold is real and the fix works exactly as expected. **Not included in this PR** because it's one
piece of a larger picture (below), and shipping it alone without the other two pieces wouldn't
actually resolve "near vertical walls aren't ideal" for the cases that prompted the original
comment.

## Finding 2: shelf width doesn't scale with oceanDepth (confirmed, no clean fix found yet)

Once the fold above is fixed, the coastline itself is smooth - but the _shelf_ portion of the
island→ocean blend (the transition from raw ocean floor up to a near-surface "shelf" depth, before
the beach/land blend takes over) is driven by `smoothStep(0, shelfEnd, islandAlpha)`
(`ArchipelagoPopulator.apply()`). `shelfEnd` is a fixed alpha-space window (~0.04-0.35, from
`beachWidth`). How many real blocks that alpha window covers is set purely by how fast the coastline
noise changes across space - which has nothing to do with `oceanDepth`. But the elevation the shelf
phase needs to cover (raw ocean floor, which scales with `oceanDepth` via
`Populators.makeDeepOcean`, up to a near-surface shelf target that does _not_ scale with
`oceanDepth`) grows directly with it. Same fixed number of blocks, ever-taller drop.

Measured directly at a real (post-fold-fix) island: a 493-block rise compressed into about 8 real
blocks at `oceanDepth=677`. This _is_ caused by `oceanDepth`, confirming the reviewer's instinct
that something here really is depth-driven, just not through the mechanism originally guessed.

### Attempts and why they didn't produce a clean fix

1. **Widen the coastline noise's own frequency by `oceanDepth/63`.** Works dimensionally (matches
   the same `depthScale` pattern already used for `Populators.makeDeepOcean`), but re-testing showed
   it also makes the entire island proportionally larger and moves its position, since the same
   noise field determines both the island's macro shape and its edge sharpness - you can't widen one
   without the other using a single warped-simplex field. Confirmed empirically: a previously-found
   island edge at `(230250, 163350)` had no edge left anywhere in a 300-block window after this
   change - the coastline had moved.

2. **Local-gradient distance estimate** (measure the coastline noise's own slope at the query point,
   use `value/slope` as an estimated distance to the threshold crossing, without touching the noise
   itself). Mathematically appealing - it's the standard "distance-from-a-level-set" trick - but it
   breaks down exactly where it's needed most: `smoothStep` is _exactly_ flat (zero value and zero
   slope) far from any island, so the distance estimate becomes 0/0 there and reads as "we're
   already at the edge" across all of open ocean, producing an _immediate_ jump instead of a smooth
   ramp (confirmed: `-429 → 57` in a single block, worse than the original bug).

3. **Bounded numerical search** (sample the real `islandAlpha` at a few points outward from the
   query position, bisect toward the actual threshold crossing, no derivative/degenerate-case risk
   since only real function values are read). More robust than (2), and it did successfully filter
   out the 0/0 problem - but produced unstable results in practice: at a real test location,
   measured distance jumped from ~50 blocks to ~2 blocks between two adjacent query points. Traced
   this to a second, independent finding (below), not a bug in the search itself - the search was
   correctly reporting a genuinely-unstable _actual_ `islandAlpha`, not an artifact of the
   technique.

## Finding 3: `continentFade`'s window is too narrow, and this is `oceanDepth`-independent

While debugging (3) above, direct instrumentation of the exact values at the unstable location
showed `continentFade` itself swinging from `0.0005` to `0.31` (over 600x) across the same 10 blocks
where the instability showed up - while the `continentEdge` value it's built from moved by a
completely unremarkable `0.0997 → 0.0904` over that same span (a normal, gentle change for a
large-scale continent field). The cause:
`continentFade = 1 - smoothStep(islandCoast, deepOcean, continentEdge)`, and
`islandCoast`/`deepOcean` sit only `0.026` apart by default. A smooth, gentle change in the
underlying value, passed through a narrow window, produces a sharp change in the output - a
smaller-scale version of exactly the same "narrow window doesn't scale to the real distance it needs
to cover" problem as Finding 2, just via a completely different field (`continentFade`, not the
coastline noise).

**Checked whether this is a preset-authoring issue rather than a bug**: it is not. Every one of the
8 `ControlPoints` instances in the mod's own shipped `Presets.java` (lines 24, 68, 112, 157, 201,
245, 300, 523) uses an `islandCoast`/`deepOcean` gap between roughly `0.009` and `0.028`. This is
the mod's actual out-of-the-box behavior, not something a user has to misconfigure to hit.

Crucially, **this mechanism does not depend on `oceanDepth` at all** - it's a function of
`continentScale` and the fixed control-point gap. It would produce a sharp-ish island edge at the
default `oceanDepth=63` too, wherever an island happens to sit near a continent-fade boundary. It's
a real, pre-existing archipelago bug, just not one this PR's ocean-depth feature caused or made
worse.

## Why this needs a rewrite, not a third patch

Stepping back from the three findings above: the recurring problem is that "distance to the
coastline" is not a first-class, directly-available value anywhere in the archipelago code. It has
to be inferred after the fact from a value built for a different purpose (an alpha threshold), which
is exactly why fixes (1) and (2) under Finding 2 both failed in different ways, and why Finding 3
exists at all (the same "threshold, not distance" pattern, just applied to `continentEdge` instead
of the coastline noise).

The continent generator (`UpliftContinentGenerator`) doesn't have this problem: it's built on a
Voronoi/cellular search, and `continentDistance` (an actual Euclidean-style distance to the nearest
cell center) falls out of that computation as a natural byproduct, not something bolted on. RTF
already uses the same cellular technique elsewhere too (`Noises.worleyEdge`, used for some mountain
shapes in `Populators.makeMountains2/3`) at a cost the engine already pays for continents on every
single terrain cell in the world - it would not be a more expensive technique than what's already
running today.

Rebuilding archipelago island shape on the same cellular basis (islands placed at jittered cell
centers, shelf/beach/land widths expressed and scaled in real blocks against a real distance, rather
than reverse-engineered from a smoothstepped alpha) would fix Findings 2 and 3 by construction and
make Finding 1's whole warp-fold class of bug structurally impossible, instead of three separate
patches layered on code that was never designed to expose the thing all three actually need.

This is a bigger, riskier change than anything else in this investigation:

- Archipelago has been a shipped, live feature since `v0.0.6004` (confirmed via `git tag --contains`
  on the commit that introduced `ArchipelagoPopulator`), so switching the underlying placement noise
  would relocate every existing island in every world that has archipelago turned on, not just
  smooth its edges. That's a materially bigger compatibility hit than Finding 1's warp-strength fix
  alone, which only changes edge behavior while leaving islands roughly where they already are.
- Getting the "organic, ruffled" coastline look right on a cellular base takes real, careful warp
  tuning of its own (the continent generator already proves this is achievable, but it isn't free).
- Island density/distribution (currently `densityNoise`, a separate gating field) would need
  rethinking against a cellular placement scheme too, likely following the same pattern
  `UpliftContinentGenerator.shouldSkip()` already uses to omit some cells.

## Recommendation

Treat this the same way `biome-climate-banding-investigation.md` treats its own finding: real,
confirmed, worth fixing, but scoped as its own PR rather than bolted onto this one. Candidate next
steps for that future PR:

- Prototype archipelago on a Worley/cellular base (mirroring `UpliftContinentGenerator`'s pattern),
  with shelf/beach/land widths expressed in real blocks from the start.
- Once distance is a first-class value, apply the same `oceanDepth`-scaling principle already proven
  for `Populators.makeDeepOcean` to the shelf width specifically.
- Fix `continentFade`'s narrow window as part of the same pass, using the same real-distance
  approach, rather than as a separate patch.
- Revisit per-island edge-steepness _variance_ (volcanic islands rising sharply vs. gentle sloped
  ones) as a deliberate feature once distance is real and cheap to query - a coarse,
  `continentFade`- style auxiliary noise is the right tool for that variance specifically (cheap,
  doesn't need to track fine coastline detail), just not for the distance measurement itself.
- Confirm before shipping whether Finding 1's warp-strength fix should still land independently in
  the meantime, since it's a real, isolated bug fix with no dependency on the larger rewrite - worth
  a decision in that future PR, not assumed here.

## Status

Not fixed in this PR. Findings 1-3 above are confirmed via direct empirical testing against the real
production code path (not simulated), using the same seed/coordinate methodology as the rest of this
investigation. No code changes from this investigation are included in the ocean-depth PR;
`ArchipelagoPopulator.java` and `Heightmap.java` were reverted back to their pre-investigation
state.
