# Trial Chambers and Other Ocean-Adjacent Structures

## Status: 2026-07-19

Follow-up to `monument-placement-research.md`. ETcodehome's PR #97 review flagged trial chambers
spawning as "large floating blobs because they don't expect oceans deeper than y0." Investigated
whether the monument anchor-fix generalizes here, surveyed every other overworld vanilla structure
for the same class of defect, prototyped and tested a fix, and checked whether the same bug reaches
Ancient City. Root cause is fully proven for Trial Chambers, and a fix (v2, multi-point worst-case
floor sampling + worldDepth-bounded skip logic) is implemented and empirically verified live — see
"Start-height fix" below. Ancient City has the identical blind-start-height mechanism, confirmed
live, and shares the same fix (it's the same generic vanilla hook, scoped to both structure IDs),
but no naturally-occurring floating instance has been found yet across 32 checked samples. Follow-up
direct scans show why: in the tested seed/regions, low RTF ocean floors and the vanilla `deep_dark`
biome climate required by Ancient Cities do not overlap. This is a broader biome/climate interaction
exposed by deep oceans, not only an Ancient City placement issue.

**No single fix covers every ocean-adjacent structure — the underlying problems are genuinely
different per structure**, summarized in the table at the end of this doc.

## Confirmed by direct visual reproduction

Real client, seed `3216933670`, `ocean-depth-test-preset.json` (`worldDepth: 624`, `oceanDepth: 677`
— a valid preset well within the UI's own clamp). At more modest depth settings the trial chamber
protrudes out of the seafloor; at `worldDepth: 624`/`oceanDepth: 677` the same seed/location
produces a trial chamber fully floating in open deep water (screenshot standing directly beneath it
in open blue water, F3 confirming `Deep Ocean` biome).

## Root cause: Trial Chambers

Two independent mechanisms combine to produce the bug, both confirmed by direct measurement, not
inference:

**1. The structure's starting position is picked blind.** `JigsawStructure.findGenerationPoint()`
samples a `start_height` value — for trial chambers, a uniform random pick between absolute Y=-40
and Y=-20 — with no check against real generated terrain, unless the structure also sets an optional
`project_start_to_heightmap` field. Trial chambers don't set it (confirmed from
`trial_chambers.json`). Every other room in the chamber is placed via jigsaw connectors relative to
that first point, so the whole structure's vertical position is decided once, blindly, and never
corrected.

**2. Beardifier's `ENCAPSULATE` terrain adaptation (trial chambers' assigned type) only protects a
~12-block halo around each _individual_ piece, not the structure's combined footprint.** Traced the
actual math in `Beardifier.compute()`:

```java
case ENCAPSULATE -> getBuryContribution(m / 2.0, q / 2.0, n / 2.0) * 0.8;
// getBuryContribution:
double g = Mth.length(d, e, f);
return Mth.clampedMap(g, 0.0, 6.0, 1.0, 0.0);   // hard zero once combined distance >= 6.0
```

`m`, `q`, `n` are each computed as distance outside a single rigid piece's own bounding box (zero if
inside it), halved before the clamp — an effective reach of ~12 blocks from each piece's own edges,
hard zero beyond that. A trial chamber is built from 100+ small individual rooms scattered across a
large combined footprint; the shell around the _combined_ bounding box can be, and is, far outside
any single piece's own halo.

Measured directly with `MixinBeardifierMagnitudeQA` (hooks `Beardifier.compute()`, aggregates total
calls/non-zero calls/sum/max across every real invocation in the shell region — the region excludes
the structure's own combined-bbox interior, since many individual pieces are packed inside it and
would produce expected nonzero noise unrelated to the shell question):

```text
[RTF-QA] Beardifier magnitude summary near TRIAL_CHAMBERS: totalCalls=2476000 nonZeroCalls=0 sum=0.0 maxAbs=0.0
[RTF-QA] Beardifier magnitude summary near TRIAL_CHAMBERS_BASELINE: totalCalls=4105500 nonZeroCalls=0 sum=0.0 maxAbs=0.0
```

Exactly zero at both a floating chamber and a healthy, land-based chamber (`[1392,~,1408]`, same
seed/preset) — 2.4M and 4.1M real samples, no filtering. The halo-gap is universal to the structure
type, not specific to the broken case; it's the same everywhere. What differs is whether RTF's
_other_, unrelated terrain-generation systems happen to fill that shell with solid ground (healthy
chamber) or not (floating chamber, because `start_height` placed it somewhere the real floor is
hundreds of blocks lower than vanilla assumed).

**This is not a Beardifier bug or "too weak" halo** — it's a property of vanilla's `ENCAPSULATE`
design, unrelated to RTF. `oceanDepth` is what exposes it: RTF's pre-PR hard clamp at Y=0 meant the
area between individual pieces' halos was always naturally solid ground anyway, for reasons
unrelated to Beardifier's reach. `oceanDepth` is what newly allows that in-between area to be open
ocean water instead. **Pre-existing vanilla limitation, newly exposed, not newly introduced by this
PR.**

Structure-discovery itself works correctly at both locations — `Beardifier.forStructuresInChunk`
reports up to 115 (floating) and 44 (healthy) rigid pieces per chunk, the expected healthy pattern,
confirmed via `MixinBeardifierDiscoveryQA`.

## Baseline solidity across multiple independent chambers

`MixinTrialChamberQA` samples a shell around a structure's combined bounding box (margin 10, step 2,
excluding the interior) and reports percent solid:

| Chamber                                             | bbox                                     | Solid % |
| --------------------------------------------------- | ---------------------------------------- | ------- |
| Floating (broken)                                   | `(-30843,-59,-34163)-(-30733,15,-34020)` | 0%      |
| `[1392,~,1408]`                                     | `(1307,-46,1315)-(1451,28,1435)`         | 16%     |
| near `(1998,720)`                                   | `(1872,-48,505)-(2011,16,644)`           | 13%     |
| near `(1264,784)`                                   | `(1260,-59,791)-(1403,15,907)`           | 9%      |
| near spawn `[816,~,992]` (`1.21.1` baseline branch) | `(761,-43,969)-(886,31,1085)`            | 21%     |

Healthy solidity varies meaningfully by chamber (9-21%) — not a fixed number — but every healthy
sample is roughly an order of magnitude above the floating chamber's 0%, with no overlap between the
two groups.

## Ocean Ruins and Shipwrecks: correctly depth-aware

**`OceanRuinPieces.OceanRuinPiece.postProcess()`** resamples `OCEAN_FLOOR_WG` at the actual
placement column and repositions to it. **`ShipwreckPieces.ShipwreckPiece.postProcess()`**
(non-oversized path) averages `OCEAN_FLOOR_WG` across the piece's whole footprint (or
`WORLD_SURFACE_WG` if beached). Both run inside `postProcess()`, during the `FEATURES` step — after
`NOISE`/`SURFACE`/`CARVERS` have already produced final terrain, not the earlier density-function
preview `findGenerationPoint()` uses.

Verified with `MixinOceanStructureHeightQA` against two independent, arithmetic-independent checks:
a direct downward block scan for the nearest real solid ground from the placement, and (for
non-beached shipwrecks) a replica of vanilla's own footprint-averaged calculation.

**Ocean Ruins — 10 placements across multiple locations, including two in the same extreme
deep-water area as the floating trial chamber:**

```text
type=OceanRuinPiece pos=(-30896,-407,-34240) freshHeight=-407 delta=0 nearestSolidBelow=0
type=OceanRuinPiece pos=(-30688,-569,-34224) freshHeight=-569 delta=0 nearestSolidBelow=1
type=OceanRuinPiece pos=(1347,-25,708)      freshHeight=-15  delta=-10 nearestSolidBelow=0
```

Every instance (including at Y=-407 and Y=-569, well past where a monument or trial chamber breaks)
has real solid ground 0-1 blocks below its placement, no exceptions. The one nonzero raw delta
(`-10`) is not a counterexample — `nearestSolidBelow=0` confirms the piece still sits exactly on
real ground, consistent with `OceanRuinPiece`'s own secondary uneven-terrain adjustment correctly
compensating for this preset's known steep local floor variation.

**Shipwrecks — 2 placements, both non-beached:**

```text
type=ShipwreckPiece pos=(912,5,624)   freshHeight=-14 delta=19 nearestSolidBelow=20 footprintAverageOceanFloorWG=5  deltaVsFootprintAverage=0
type=ShipwreckPiece pos=(1264,12,784) freshHeight=-14 delta=26 nearestSolidBelow=27 footprintAverageOceanFloorWG=12 deltaVsFootprintAverage=0
```

`deltaVsFootprintAverage=0` in both — placement Y matches vanilla's own footprint-averaged
calculation exactly. The large single-column deltas (19, 26) are the expected result of averaging
across a multi-block footprint over this preset's known-uneven terrain, not placement bugs — a
single-column heightmap comparison alone would have misread this as broken.

Ocean ruins and shipwrecks reposition themselves late, from real heightmap data. Ocean monuments
needed a separate fix because their building anchor is hardcoded and guardian spawn overrides use
structure bounds, so moving only during `postProcess()` is too late (see
`monument-placement-research.md`). Trial chambers are not a placement-anchor-timing problem at all —
their issue is the combination of a never-corrected starting height and a halo that doesn't cover
the resulting gap.

## Blast radius: which vanilla structures use `ENCAPSULATE`

`terrain_adaptation` is a single field on each structure's own definition file, applied uniformly to
every piece (not per-piece in the template-pool JSONs). Extracted and read all 30 vanilla structure
definition JSONs directly from the game jar:

| Structure                                                                                                                                                               | `terrain_adaptation`             |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| **Trial Chambers**                                                                                                                                                      | **`encapsulate`** — the only one |
| Ancient City                                                                                                                                                            | `beard_box`                      |
| Villages (all 5 variants), Pillager Outpost, Nether Fossil                                                                                                              | `beard_thin`                     |
| Trail Ruins, Stronghold                                                                                                                                                 | `bury`                           |
| Everything else (Bastion, Mansion, Monument, Ocean Ruins, Shipwrecks, Ruined Portals, Desert Pyramid, End City, Fortress, Igloo, Jungle Pyramid, Mineshafts, Swamp Hut) | omitted → `none`                 |

Trial Chambers is the only vanilla structure using `encapsulate`. Ancient City uses `beard_box`
instead (a different branch of `Beardifier.compute()`); its own gap behavior, if any, hasn't been
read or tested and isn't assumed either way. A targeted fix to the `ENCAPSULATE` case has a blast
radius of exactly one vanilla structure type, with no cross-structure risk (datapack/mod structures
that opt into `encapsulate` themselves would also be affected, outside vanilla's own set).

## Survey: does any other vanilla structure share the start-height defect?

The `ENCAPSULATE` halo-gap explains why nothing corrects a badly-placed trial chamber, but the
starting-height blindness (`start_height` with no `project_start_to_heightmap`) is the more
fundamental, separate mechanism. Checked every overworld-reachable vanilla structure (all 30 minus
End City/Fortress/Nether Fossil, which are End/Nether-only) for whether its placement is ever
corrected against real generated terrain anywhere in its pipeline:

| Structure                                       | Mechanism                                                                    | Reachable by `oceanDepth`? |
| ----------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------- |
| **Trial Chambers**                              | Blind `start_height`, no correction anywhere — **confirmed root cause**      | Yes                        |
| **Ancient City**                                | Same blindness (`start_height: -27`, no projection, no later correction)     | Yes                        |
| Bastion Remnant                                 | Same blindness (`start_height: 33`, no projection)                           | No — Nether-only           |
| Villages, Pillager Outpost, Trail Ruins         | `project_start_to_heightmap` set — self-corrects up front                    | Yes, safe                  |
| Stronghold                                      | Builds fully, then rigidly shifts to the generator's real reported sea level | Yes, safe                  |
| Mineshaft                                       | Same real-sea-level shift (normal) or a real terrain sample (mesa)           | Yes, safe                  |
| Ocean Monument                                  | Was the same blind-anchor defect; fixed in this PR                           | Fixed                      |
| Ocean Ruins, Shipwrecks                         | `postProcess()` resamples real terrain                                       | Yes, safe                  |
| Buried Treasure                                 | `postProcess()` walks block-by-block down until real solid ground            | Yes, safe                  |
| Ruined Portal (all variants, incl. ocean)       | Live block-by-block scan across 4 real terrain columns                       | Yes, safe                  |
| Desert Pyramid, Jungle Temple, Swamp Hut, Igloo | `postProcess()` resamples real terrain and repositions                       | Yes, safe                  |
| Woodland Mansion                                | Real terrain scan up front, plus a gap-fill pass in `afterPlace()`           | Yes, safe                  |

Trial Chambers and Ancient City are outliers, not the norm — the only two overworld structures whose
entire vertical position is decided once, blindly, and never checked again. If a fix is built for
one, the same fix shape directly applies to the other.

## Start-height fix: v1 prototype, v2 implementation, both empirically tested

Trial chambers are underground by design (`start_height` Y=-40..-20, well below sea level) — unlike
ocean monuments, they were never meant to sit at or near the floor surface, so a fix only needs to
land the structure safely underground, not match a specific "on the seafloor" position.

### v1 (superseded): single-column push-down

`MixinJigsawStartHeightFixQA` originally hooked `JigsawStructure.findGenerationPoint()` via
`@ModifyVariable` and corrected the blind `start_height` sample against a single `OCEAN_FLOOR_WG`
sample at the chunk position: `Math.min(sampledY, realFloor - margin)` — only ever pushed down,
never up.

**Dynamic to whatever preset is loaded.** Very-deep preset: corrections fired with real, varying
floor values (-396, -439, -488, -511, -522) at different locations. Shallowest preset: zero
corrections fired — the mechanism correctly recognized the blind sample was already safe there.
Shallow oceans weren't affected by the bug at all: the same location that read 0% solid (floating)
under the very-deep preset read 9% solid (healthy) under the shallowest preset, fix inactive.

**v1 helped but did not solve the known floating case:** before fix, bbox Y-range -59 to 15, 0%
solid; after v1's single-column fix, bbox Y-range -426 to -352, only 1% solid — nowhere near the
9-21% healthy chambers read. The correction anchored the structure's _start_ from a single sampled
column, but the structure sprawls over 100+ blocks with extreme within-footprint floor variance (see
`monument-placement-research.md`), and anchoring one point doesn't guarantee the rest of the
structure — built outward via jigsaw connectors — doesn't wander back into open water elsewhere in
its own footprint.

v1 also had no way to skip generation at all (`@ModifyVariable` can only change a value, not cancel
the method), so a `worldDepth` small enough to invalidate the blind absolute anchor entirely had no
defined behavior.

### v2 (current): multi-point worst-case sampling + worldDepth-bounded skip logic

Rewrote the mixin using
`@Inject(method = "findGenerationPoint", at = @At("HEAD"), cancellable = true)` instead of
`@ModifyVariable`, since only `@Inject` with a cancellable callback can skip generation outright.
The new mixin fully reimplements `findGenerationPoint()`'s few lines for exactly the two target
structures (everything else passes through untouched), calling `JigsawPlacement.addPieces(...)`
(confirmed `public static`, `JigsawPlacement.java:51`) itself once a corrected Y is chosen. Required
shadowing 9 private fields off `JigsawStructure` (`startPool`, `startJigsawName`, `maxDepth`,
`startHeight`, `useExpansionHack`, `projectStartToHeightmap`, `maxDistanceFromCenter`,
`poolAliases`, `dimensionPadding`, `liquidSettings`) via `@Shadow @Final`.

Algorithm:

1. **Sample the real floor across a grid, not one column.** Both structures share
   `max_distance_from_center = 116` (confirmed from their structure JSONs) — vanilla's own bound on
   how far any piece can land from the anchor. Samples `OCEAN_FLOOR_WG` at a 7x7 grid (49 points)
   spanning `±116` blocks on each axis from the chunk origin (`getFirstOccupiedHeight(x, z, ...)`
   samples arbitrary block positions, not just chunk-aligned ones, confirmed in
   `ChunkGenerator.java`), and takes the **deepest** (worst-case) sample. This is the opposite
   convention from the ocean monument fix, correctly: monuments sit _on top of_ the floor and must
   avoid dipping below it anywhere in their footprint, so they anchor to the _highest_ sampled floor
   (see `monument-placement-research.md`); these are _buried_ structures that must stay below the
   floor everywhere in their footprint, so they anchor to the _lowest_.
2. **Correct**: `target = Math.min(sampledY, worstFloor - MARGIN)`, `MARGIN = 10`, only ever pushes
   down, leaves an already-safe blind pick untouched.
3. **Only if step 2 actually changed the value** (`target != sampledY`), bound the corrected Y
   against the dimension's real minimum build height (`heightAccessor().getMinBuildHeight()`, i.e.
   `-worldDepth`) plus a per-structure clearance for how far the structure can extend below its
   anchor. An unmodified blind pick is never second-guessed against world bounds — see "clearance
   calibration" below for why that check specifically had to be gated on "did a correction actually
   happen."
4. **Skip if there's no safe window.** If `target < minValidY`, cancel with `Optional.empty()`
   rather than force an unsafe placement, same precedent as Woodland Mansion (confirmed directly,
   `WoodlandMansionStructure.java:29-33`). Otherwise use `target` and call
   `JigsawPlacement.addPieces(...)`.

This also resolves the two design gaps from the prior integration pass: the correction is bounded by
the real dimension height (gap 1), and there's no separate "push up" action — an invalid blind
anchor is handled by the same valid-window check as everything else, never by relocating to an
unsafe Y (gap 2). Gap 3 (Ancient City's incidental `deep_dark` biome-check backstop, Trial Chambers
has none) remains true and unaffected — see the Ancient City section below.

### Clearance calibration: two real mistakes caught by testing, not by review

The clearance value (how far below the dimension's minimum build height the structure's own body
needs) went through two wrong iterations before landing on the current one, both caught by actually
running the fix against real presets rather than trusting the design on paper.

**First attempt: `CLEARANCE = 64`, a rough estimate from partial data.** Read as "roughly matches
the 64-74 block total spans of healthy trial chambers already measured in this doc." Live testing at
the very-deep preset showed this was under-conservative: two real corrected placements
(`worstFloor=-511`→`correctedY=-521`, `worstFloor=-522`→`correctedY=-532`) passed the check and
generated, but were never verified against how far those specific structures actually extended below
their anchors — the number was picked before checking whether it was actually safe, not after.

**Second attempt: `CLEARANCE = max_distance_from_center` (116), vanilla's actual enforced bound.**
Confirmed directly in `JigsawPlacement.addPieces()` (`JigsawPlacement.java:127-134`): every piece is
confined to an AABB extending `±max_distance_from_center` in X, Z, _and_ Y from the anchor, so 116
is the true worst-case vanilla allows, not an estimate. This looked like the correct fix for the
first mistake. **Testing the Goldilocks preset (`worldDepth=64`, `oceanDepth=117`) immediately
proved it wrong**: since `max_distance_from_center` (116) exceeds `worldDepth` (64),
`minValidY = getMinBuildHeight() + 116 = 52` — positive, above sea level — and both structures'
blind anchors are always negative (-20 to -40), so `target < minValidY` was true unconditionally,
for every candidate, everywhere in the world, including ordinary dry land with no real floor problem
(`worstFloor=104` in one observed skip line). Since RTF's _default_ `worldDepth` is 64, this would
have made Trial Chambers and Ancient City nearly unable to generate in a normal-depth world — a far
worse regression than the bug being fixed. The check was also flawed independent of the clearance
value: it ran even when `target == sampledY` (no real correction, i.e. vanilla's own default
behavior, which was never the failure mode this fix addresses) — fixed by gating the whole check on
`target != sampledY` (see algorithm step 3 above).

**Final values, measured, not estimated:**

- `ANCIENT_CITY_CLEARANCE = 40`. Ancient City's real vertical extent below its anchor is exactly 37
  blocks in every real instance checked — not a range, an exact constant, because its jigsaw pool
  isn't randomly variable in vertical extent. Confirmed across 34+ independent real instances total:
  the 32 already documented in this doc (anchor Y=-27, bottom Y=-64 every time) plus 2 more matched
  directly this session from corrected (non-default) anchors — `correctedY=-505`→bbox `minY=-542`
  (37 exactly) and `correctedY=-428`→bbox `minY=-465` (37 exactly). 40 adds a 3-block buffer on an
  already-exact measurement.
- `TRIAL_CHAMBERS_CLEARANCE = 48`. Trial Chambers' footprint is randomly assembled per instance, so
  only a bound is possible, not an exact constant. Two real corrected placements were matched
  directly to their measured bounding boxes: `correctedY=-482`→bbox `minY=-502` (20 blocks below
  anchor) and `correctedY=-348`→bbox `minY=-368` (20 blocks below anchor, independently, at a
  different location). 48 covers the observed 20 with real margin for instances not yet measured,
  while staying far below the 64-block `worldDepth` default that made 116 catastrophic.

### Final empirical results (2026-07-19, seed `3216933670`, dev-server, all three reference presets)

Registered `qa.MixinJigsawStartHeightFixQA` in `reterraforged-common.mixins.json`, built clean
(`:fabric:compileJava`, no errors, only pre-existing warnings from unrelated mixins), and tested
against the very-deep, Goldilocks, and shallowest presets — not just the one preset used during
development, specifically to catch preset-dependent regressions like the one above.

**Very-deep preset (`worldDepth=624`, `oceanDepth=677`) — known floating-chamber basin now correctly
and precisely skips, adjacent candidates in the same basin do not:**

```text
start-height skip:       structure=TRIAL_CHAMBERS chunk=(-1923,-2130) worstFloor=-568 target=-578 minValidY=-576
start-height correction: structure=ANCIENT_CITY    chunk=(-1929,-2136) worstFloor=-569 correctedY=-579
start-height correction: structure=ANCIENT_CITY    chunk=(-1912,-2136) worstFloor=-567 correctedY=-577
```

The exact historically-known floating chamber location fails by 2 blocks (`target=-578` vs.
`minValidY=-576`) under the calibrated clearance — narrow and precise, not the blanket "nothing
generates in this whole basin" result the over-conservative 116-based version produced. Immediately
adjacent Ancient City candidates in the same basin, with comparable floor depths, correctly proceed
instead of being blanket-rejected.

**Real burial confirmed for both structures, not just skip behavior:**

| Structure                             | worstFloor | correctedY | Measured solidity          | Fully sampled?                                              |
| ------------------------------------- | ---------- | ---------- | -------------------------- | ----------------------------------------------------------- |
| Trial Chambers near `(-30352,-33664)` | -472       | -482       | 26%                        | yes, 0 unloaded columns                                     |
| Trial Chambers near `(1998,720)`      | -338       | -348       | 24%                        | yes                                                         |
| Ancient City near `(-30344,-34281)`   | ~-511      | ~-521      | 20% (18% top / 22% bottom) | no, 8538 unloaded columns, but well above the healthy floor |

**No regression on any previously-documented healthy reference location** (both structures, six
locations total): measured 9%, 13%, 26%, 34% (Trial Chambers) and 12%/11%, 13%/13% top/bottom
(Ancient City) — all within or above prior baseline ranges.

**Goldilocks preset (`worldDepth=64`, `oceanDepth=117`) — confirms the fix no longer breaks normal
generation in a shallow-worldDepth preset:**

Two Trial Chambers generated with no correction needed at all (blind pick already safe) and measured
27% and 30% solid — proving normal, vanilla-equivalent generation continues to work. 10 candidates
(both structures) correctly skipped, each with a real, logged floor problem forcing a correction
that then failed the (now correctly narrow) safety margin — none were blanket/unconditional skips.

**Shallowest preset (`worldDepth=128`, `oceanDepth=10`)** — export was missing from the Modrinth
profile (see `qa-presets.md`), reconstructed by hand-editing a copy of the very-deep datapack's
`preset.json`/`noise_settings`/`dimension_type` to consistent `worldDepth=128`/`oceanDepth=10`
values (internal consistency between RTF's own claimed `worldDepth` and the dimension's actual
`min_y` double-checked before use, exactly the kind of mismatch this whole investigation is about).
Zero corrections fired, matching the original v1 finding — confirms the fix doesn't touch
already-healthy shallow-ocean generation.

Zero exceptions across all three presets and all test runs. (`dev-server` process-cleanup gaps hit
repeatedly during this testing are tooling issues, not mixin issues — tracked in
`games/minecraft/tooling/README.md`'s "Known limitations", not duplicated here.)

### Safety check redesign: measuring the real generated structure instead of estimating its size

The hardcoded per-structure clearances above (`ANCIENT_CITY_CLEARANCE=40`,
`TRIAL_CHAMBERS_CLEARANCE=48`) have a structural weakness independent of how well-calibrated they
are: they go stale the moment a datapack or mod changes either structure's actual size, of which
several exist for Trial Chambers. Replaced with a design that measures the real generated structure
instead of estimating it.

**Mechanism.** `Structure.GenerationStub` (`Structure.java:231`) is:

```java
record GenerationStub(BlockPos position, Either<Consumer<StructurePiecesBuilder>, StructurePiecesBuilder> generator)
```

— it can hold either a lazy "build later" consumer or an already-built result.
`JigsawPlacement.addPieces(...)` (unchanged from before) returns the lazy form; `getPiecesBuilder()`
(`Structure.java:236-242`) forces the consumer to run and is **not idempotent** — every call re-runs
the random piece-selection logic against the structure's `RandomSource`, consuming its state. The
new mixin logic:

1. Computes `target` via the same floor-grid worst-case sampling as before (unchanged).
2. Cheap biome pre-check at `target`, replicating `Structure.isValidBiome()`
   (`Structure.java:116-126`) early — vanilla runs this exact check anyway immediately after
   `findGenerationPoint()` returns; doing it first avoids paying for real piece placement on
   candidates that would be discarded by biome validation regardless.
3. Calls `JigsawPlacement.addPieces(...)`, then calls `.getPiecesBuilder()` **exactly once** to
   force the real random piece placement to run now, and reads
   `StructurePiecesBuilder.getBoundingBox()` (`StructurePiecesBuilder.java:73-74`) — the real, exact
   combined bounding box of whatever pieces actually got placed for this specific instance.
4. If `realBbox.minY()` sits within `BOUNDARY_TOLERANCE` (8, a heuristic constant, not a measured
   one) of the dimension's real minimum build height plus the structure's own declared
   `dimension_padding` (`this.dimensionPadding.bottom()`, read per-structure, not assumed — Trial
   Chambers declares `10` in its own JSON, Ancient City uses vanilla's default `0`), that indicates
   the real placement got constrained by the world boundary and likely looks truncated — cancel with
   `Optional.empty()`.
5. Otherwise, re-wrap the **already-built** `StructurePiecesBuilder` as
   `new Structure.GenerationStub(position, Either.right(builder))` and return that. This is the part
   that must not be skipped: if the original lazy consumer form were returned instead, vanilla's own
   later call to `getPiecesBuilder()` (inside `Structure.generate()`) would re-run the random
   placement a second time with an already-advanced RNG state, silently producing a _different_
   structure than the one just measured, and paying the placement cost twice.

**`MARGIN` and `BOUNDARY_TOLERANCE` serve genuinely different purposes, not the same kind of "safety
margin" twice.** `MARGIN` (step 1, `=10`) operates _before_ anything is generated — it's the buffer
used when picking the initial candidate `target`: anchor 10 blocks below the real floor found, not
exactly at it. `BOUNDARY_TOLERANCE` (step 4, `=8`) operates _after_ the real structure has already
been built — it judges whether the _real, measured_ result looks truncated (its bottom sitting
suspiciously close to the world's actual buildable floor) rather than estimating in advance whether
it will fit. Neither is empirically derived; both are reasoned constants carried without specific
tuning.

**Why this doesn't reintroduce the ocean monument timing bug.** The monument bug came specifically
from moving the building position in `MonumentBuilding.postProcess()` — a late chunk-decoration
phase that runs _after_ `StructureStart` (and the bounding box mob-spawn overrides read from) had
already been finalized elsewhere. Vanilla's `Structure.generate()` builds the one and only
`StructureStart` immediately after `findValidGenerationPoint()` returns, by calling
`getPiecesBuilder()` on whatever stub that returned (`Structure.java:94-97`). This mixin calls that
same `getPiecesBuilder()` itself, _earlier_, from inside `findGenerationPoint()` — the very method
`generate()`'s sequence starts with — and hands back the identical already-built result. There is no
window in which stale bounds could be read, because nothing is built or recorded before this mixin's
decision runs; the bounds `generate()` uses for `StructureStart` are, by construction, the exact
same bounds already measured here.

**Performance: measured, not assumed.** Benchmarked both designs under identical heavy load (a
~6000-chunk forced area) with `System.nanoTime()` instrumentation:

| Design                         | n   | avg   | p50   | p90   | max   |
| ------------------------------ | --- | ----- | ----- | ----- | ----- |
| Hardcoded clearance (previous) | 34  | 258ms | 259ms | 357ms | 523ms |
| Real bounding box (current)    | 34  | 277ms | 266ms | 390ms | 752ms |

Both are dominated by the unchanged floor-grid sample (49 `getFirstOccupiedHeight` calls; both
designs' minimums are ~85-86ms, confirming that's the shared floor). A follow-up run isolated the
real piece-build step specifically: of 30 candidates, 20 (67%) were rejected by the cheap biome
pre-check and never paid for real piece placement at all; the 10 that proceeded averaged 99ms for
the real placement + bounding-box read. Weighted across all candidates that's roughly +20-30ms
average — the biome pre-check optimization is doing real, necessary work, not a theoretical nicety.

**Correctness confirmed on both sides.** Real burials measured after the redesign matched the prior
design's results almost exactly (Trial Chambers 24%/26% solid at the same two previously-measured
deep corrections; Ancient City 11-14% at the two known-healthy reference locations, no regression).
The real-bbox skip path itself was confirmed firing correctly against the Goldilocks preset (tight
headroom by design): 4 real placements measured genuinely truncated (e.g.
`target=-33 realBboxMinY=-41 minValidY=-38` — the real structure's body only extended 8 blocks below
its anchor before running out of room) and were correctly rejected, while 2 other real placements in
the same run measured healthy (12%, 26% solid) and were correctly kept. Zero exceptions across every
test run this session.

One outcome worth noting: the known floating-chamber basin's Trial Chambers candidate is rejected by
the _biome pre-check_, not the real-bbox check — confirmed directly (not inferred) by logging the
actual biome name at both the corrected and blind position: its corrected position (`Y=-578`, very
close to the world's absolute bottom) resolves to `minecraft:deep_dark`, which Trial Chambers'
`has_structure/trial_chambers` tag explicitly excludes. The two adjacent Ancient City candidates in
the same basin (`Y=-577`, `Y=-579`) resolve to `deep_cold_ocean` and `deep_ocean` respectively — not
a contradiction, genuinely different biomes at genuinely different (if nearby, ~100-150 block apart)
columns, consistent with RTF's `biomeSize=225` climate parameter.

### Ancient City: proven moved past what vanilla would produce, not just re-validated in place

Three real corrections were traced end-to-end by logging the biome vanilla's own _blind_ `Y=-27`
would have seen at the same column, compared against the biome actually used (the corrected Y):

| Chunk           | Blind `Y=-27` biome (unfixed vanilla) | Corrected Y | Corrected biome | Measured solidity                   |
| --------------- | ------------------------------------- | ----------- | --------------- | ----------------------------------- |
| `(-1889,-2135)` | `deep_cold_ocean`                     | `-536`      | `deep_dark`     | 17%                                 |
| `(-161,152)`    | `lukewarm_ocean`                      | `-428`      | `deep_dark`     | 9-13% (natural run-to-run variance) |
| `(-155,176)`    | `lukewarm_ocean`                      | `-505`      | `deep_dark`     | 17%                                 |

All three: vanilla's own unfixed logic checks biome at the fixed, shallow `Y=-27` and finds an
ordinary ocean biome there — it would never generate an Ancient City at any of these three locations
at all. The fix checks biome at the real corrected depth instead and finds `deep_dark` there,
producing real, healthy, buried Ancient Cities vanilla's own logic would never produce. This is
direct, logged proof, not an inference from the correction firing.

**Important correction to how that result should be read against the earlier biome-banding
investigation below — it does not resolve or supersede that finding.** The banding investigation
already established two things, not one: (1) at the fixed `Y=-27`, low ocean floors and `deep_dark`
climate are anti-correlated (zero overlap across 155,018 low-floor / 23,787 `deep_dark` columns
sampled), and (2) in the _extreme_ preset (`worldDepth=624`) specifically, `deep_dark` climate
recovers near the world's absolute bottom (already measured: `fixedY=-620: deepDarkBiome=25878`).
The three successful corrections above — landing `deep_dark` at `Y=-428` to `-536` in that same
`worldDepth=624` preset — are a direct, concrete confirmation of finding (2), not an independent
result and not evidence that finding (1) was merely a "wrong Y checked" artifact. The same broad
scan already found **zero** `deep_dark`/low-floor overlap at _every_ sampled Y band in the
Goldilocks preset (`worldDepth=64`), including near that preset's own (much shallower) world bottom
— because `worldDepth=64` isn't deep enough for the recovery effect in finding (2) to occur at all.
So this same fix, run against Goldilocks, would be expected to find corrections that keep failing
biome validation (floating → absent, not floating → healthy) — a materially different,
preset-dependent outcome from the very-deep preset result above. This has not yet been directly
tested in Goldilocks specifically; worth doing before treating "Ancient City relocation succeeds" as
preset-independent.

### Confirmed the real-bbox skip fires identically regardless of biome (ocean vs. dry land)

Built and tested a second reconstructed preset, `worldDepth=16` (the smallest value legal under
vanilla's `NoiseSettings` codec, which requires `min_y`/`height` to be multiples of 16 — an earlier
`worldDepth=20` attempt failed server startup with
`IllegalStateException: height has to be a multiple of 16`, a real constraint not caught until it
broke), `worldHeight=384` kept tall so real mountains remain possible, combined with a dense Trial
Chambers `structure_set` override (`spacing=8, separation=3`, vanilla default is
`spacing=34, separation=12`, confirmed by extracting vanilla's own `trial_chambers.json` from the
client jar rather than guessing) to make candidates dense enough to sample broadly in one pass.

Result: 140 real candidates, **100% skipped**, split roughly evenly across clearly-dry-land biomes
(`plains`, `savanna`, `jungle`, `bamboo_jungle`, `dripstone_caves`, `lush_caves` — 66 candidates)
and ocean biomes (`ocean`, `cold_ocean`, `deep_ocean`, `deep_cold_ocean`, `deep_frozen_ocean`,
`beach` — 64 candidates). Zero corrections fired at all (the blind sample is already the deepest
option available once `worldDepth` is this small, so the floor-grid sample never finds anything to
correct toward). This directly confirms the real-bbox safety check treats ocean and dry-land columns
identically — previously only asserted from the code (`OCEAN_FLOOR_WG` reads real solid ground
everywhere), not demonstrated with real non-ocean examples. The test came out too extreme to also
show a _successful_ placement for comparison (nothing fit anywhere at `worldDepth=16`) — resolved
below, once the fix could actually try somewhere other than straight down. (A `dev-server`
process-cleanup gap specific to failed `start` attempts also turned up while building this preset —
see `games/minecraft/tooling/README.md`'s "Known limitations", not duplicated here.)

### Upward window rescue: sampling both directions instead of only ever pushing down

The push-down-only design above has a real gap: it never tries anywhere other than straight down
from the blind sample, so in a `worldDepth` small enough that even the blind anchor doesn't fit in
the dimension (confirmed above — the `worldDepth=16` test's 100% skip rate spanned dry land just as
much as ocean), there is no way to recover, even where a perfectly good spot exists nearby — e.g.
tucked into a mountain instead of underwater.

**Mechanism**, extending the algorithm above:

1. The existing floor-grid sample (`max_distance_from_center`-radius, 7x7 points) is extended to
   track both the deepest point found (`worstFloor`, unchanged) _and_ the shallowest point found
   (`bestSurface`, new) in the same single pass — no second grid sample needed.
2. The naive target (`Math.min(sampledY, worstFloor - MARGIN)`, unchanged) is checked against two
   bounds: `minWorldY` (the dimension's real minimum build height, plus its declared
   `dimension_padding`, plus `BOUNDARY_TOLERANCE` — the same formula already used for the post-build
   check, now also used pre-build) and `maxLocalY` (`bestSurface - MARGIN`). `MARGIN` is reused on
   both sides rather than having a separate constant per side: "how much solid material should
   separate the structure from real terrain" is the same question whether it's asked from the floor
   or the surface, and there's no measured reason for the two answers to differ. If the naive target
   already falls inside that window, nothing changes — this reproduces the original push-down-only
   behavior exactly for every case already validated above.
3. If it falls outside the window but a valid window exists elsewhere in the column
   (`minWorldY <= maxLocalY`), retarget to the middle of that window — maximum slack in both
   directions for whatever the real (still randomly assembled, for Trial Chambers) structure turns
   out to need. If no valid window exists at all, skip immediately, before paying for a real piece
   build already known to be doomed.
4. Everything after that — biome pre-check, the real build, reading the real bounding box — is
   unchanged, except the post-build check now also verifies the real _top_ isn't at or above
   `maxLocalY`, mirroring the existing bottom check, using the same real-measurement philosophy:
   don't estimate whether it will poke through, verify whether it actually did.

This applies identically to both Trial Chambers and Ancient City — same mixin, same method, no
separate implementation needed for either structure.

**Empirical results (2026-07-20, seed `3216933670`), `worldDepth=16` mountain preset that previously
produced 140 candidates and 100% skips.** Run twice, once at each `BOUNDARY_TOLERANCE` value, same
seed and preset so the same 153 candidates (140 Trial Chambers, 13 Ancient City) appear both times:

|                                                         | `BOUNDARY_TOLERANCE=16` | `BOUNDARY_TOLERANCE=8` |
| ------------------------------------------------------- | ----------------------- | ---------------------- |
| Trial Chambers window-rescues                           | 140                     | 140                    |
| Rejected, real bottom too close to world floor          | 19                      | 13                     |
| Rejected, real top too close to local surface           | 75                      | 75                     |
| Rejected, no valid window existed at all                | 0                       | 0                      |
| Ancient City biome pre-check rejects                    | 13                      | 13                     |
| **Accepted by the fix (rescues minus both rejections)** | 46                      | 52                     |
| Confirmed via the solidity scanner                      | 26                      | 29                     |
| Solidity range measured                                 | 3-29%                   | 4-31%                  |

The bottom-side rejection count moved exactly as expected — a smaller tolerance is a less strict
check, so fewer real placements get rejected for it (19 → 13), while the surface-side count is
unaffected (75 in both runs), since `BOUNDARY_TOLERANCE` only appears in the bottom-side formula.
The "accepted by the fix" row and the "confirmed via the solidity scanner" row are genuinely
different numbers, not a rounding gap: the mixin's own logic accepted 46 (then 52) real structures
outright, with no rejection logged for them, but the separate QA solidity scanner
(`MixinTrialChamberQA`) only independently confirmed 26 (then 29) of those within this run's
forceloaded/decorated area — a scanner coverage limit, not evidence the other accepted structures
are broken (the mixin never rejected them, and zero exceptions occurred either run).

Real mountain terrain example, `BOUNDARY_TOLERANCE=8` run (`worstFloor=104`, `bestSurface=167`, both
far above sea level), correctly retargeted to `Y=83`, well clear of both bounds. The surface-side
rejection stayed roughly 5-6x more common than the bottom-side rejection across both tolerance
values — `maxLocalY` and `minWorldY` compare against different kinds of reference points (locally
sampled terrain vs. the dimension's fixed global floor) and both already use the same `MARGIN`
constant, so this isn't evidence `MARGIN` needs to differ per side. More likely: mountain terrain
has more local variance (jagged peaks within the sampling radius) than the ocean-floor cases the
bottom-side check was mostly validated against.

**Regression-tested against both previously-validated presets, zero behavior change found:**

- Very-deep preset: the known basin behaves identically (`windowRescued=false` — the naive push-down
  target already falls inside the valid window, same as before Design B existed), rejected via the
  same biome pre-check as before. All previously-measured healthy baselines matched or slightly
  exceeded prior numbers (Trial Chambers 26/32/24/12/9%, Ancient City 20/11/15%). Zero
  window-rescues fired anywhere in this preset's test area at all (deep, roomy ocean columns never
  need the rescue path) — confirms zero behavior change for the case already extensively validated.
- Goldilocks preset (tight by design): 5 window-rescues attempted, `0` "no window at all" skips
  (every column had _some_ theoretical window, just often too narrow for the real structure), 2
  correctly biome-rejected, 1 correctly rejected for a real top-too-close-to-surface result, 1
  correctly rejected for a real bottom-too-close-to-floor result, 1 passed every check and was
  accepted (real build ran, no rejection fired, though it wasn't picked up by the solidity scanner
  in this run's forceload coverage). The two pre-existing healthy baselines were unchanged (12%,
  27%). Consistent with Goldilocks being a genuinely tight preset — more rescues get attempted than
  the old design would have tried, but most still correctly fail given how little room actually
  exists there.

Zero exceptions across all three preset runs.

## Ancient City / deep_dark: structure defect exists, but biome climate blocks the screenshot

`MixinJigsawStartHeightFixQA` fires identically for Ancient City via the same shared mechanism — a
real placement candidate in this seed would have generated broken
(`sampledY=-27 floor=-439 correctedY=-449`, ~130 blocks from the known floating trial chamber).

**Ancient cities only spawn in the `deep_dark` biome** (`BiomeTags.HAS_ANCIENT_CITY` contains
exactly that one biome, confirmed from `BiomeTagsProvider.java`). Vanilla registers `deep_dark` in
`OverworldBiomeBuilder.addUndergroundBiomes()` as a bottom biome:

```text
temperature: full range
humidity: full range
continentalness: full range
erosion: levels 0-1 (-1.0..-0.375)
depth: point 1.1
weirdness: full range
```

The important naming trap is that Minecraft's biome `depth` climate axis is not "how far below the
local ocean surface/floor am I." `Climate.Sampler.sample()` evaluates six density functions at the
queried biome coordinate. `MultiNoiseBiomeSource` then picks the nearest registered biome climate
point. In other words, `deep_dark` does not ask whether there are enough solid blocks above or below
the local ocean floor; it asks whether the climate point at Ancient City's validation Y is near the
bottom-depth/low-erosion `deep_dark` point.

RTF feeds separate cell-derived fields into those vanilla climate axes:

```text
NoiseRouterData.CONTINENTS -> CellSampler.Field.CONTINENT
NoiseRouterData.EROSION    -> CellSampler.Field.EROSION
NoiseRouterData.RIDGES     -> CellSampler.Field.WEIRDNESS
RTF height/floor            -> CellSampler.Field.HEIGHT, a separate terrain-height field
```

So a column can have a very low physical ocean floor while still being an ocean/surface-like biome
climate column at `Y=-27`. Deep ocean terrain and bottom/deep-cave biome climate are related through
the noise router, but the real ocean floor does not mechanically drag `deep_dark` down with it.

This is now proven empirically, not assumed. A broad one-shot scanner
(`MixinAncientCityDeepDarkFloorScanQA`) sampled seed `3216933670`, corrected vanilla-depth
Goldilocks preset (`worldDepth=64`, `oceanDepth=117`), dense Ancient City spacing, center `(0,0)`,
radius `65536`, step `128`, biome Y `-27`:

```text
columns=1050625
deepDarkColumns=23787
approxDeepFloorColumns=155018
approxDeepFloorColumnsAmongDeepDark=0
exactDeepFloorColumnsAmongDeepDark=0
hits=0
minApproxFloor=-53
minApproxFloorAmongDeepDark=133
```

Then the same scanner logged the actual climate axes:

```text
lowFloorBottomDepthColumns=0
lowFloorDeepDarkErosionColumns=0
lowFloorBottomDepthAndDeepDarkErosionColumns=0
lowFloorStats=count=155018 continentalness=-1.000/-0.950/-0.379 erosion=-1.100/-1.066/0.445 depth=-0.396/-0.242/-0.193 weirdness=-1.100/0.024/1.100
deepDarkStats=count=23787 continentalness=-0.040/0.959/1.000 erosion=-0.577/-0.401/0.064 depth=1.057/1.504/3.244 weirdness=-0.881/-0.013/0.880
```

That proves all three necessary facts in the sampled area: low ocean floors exist, `deep_dark`
exists, and they do not overlap because the low-floor columns do not satisfy `deep_dark`'s bottom
depth or low-erosion climate requirements. The low floors are physically deep but biome-climate
shallow/surface-like.

This changes the earlier Ancient City interpretation. The missing screenshot is not evidence that
Ancient City itself requires N blocks below the ocean floor. It is evidence that this preset/seed
combination makes very low ocean floors and Ancient City-valid `deep_dark` horizontally
anti-correlated. This is a broader biome-placement consequence of deep RTF oceans: if terrain height
is pushed far below the vanilla-ish shape expected by the biome climate router, some
bottom/underground biome opportunities can disappear from those low-ocean areas.

`deep_dark` is the proven case because Ancient Cities give it an observable structure symptom, but
it is not the only vanilla biome using the biome `depth` climate axis. Vanilla also registers
`dripstone_caves` and `lush_caves` as underground biomes in `OverworldBiomeBuilder`:

```text
dripstone_caves: depth 0.2..0.9, continentalness 0.8..1.0
lush_caves:      depth 0.2..0.9, humidity 0.7..1.0
deep_dark:       depth point 1.1, erosion -1.0..-0.375
```

So the general risk is not "Ancient Cities are special." The general risk is that very deep RTF
ocean terrain can be physically deep while still sampling as surface/ocean-like on the biome `depth`
axis, which may suppress vanilla cave/underground biomes in those low-ocean columns. This broader
banding question is now measured in `biome-climate-banding-investigation.md`: Goldilocks low-ocean
columns had zero `deep_dark`, `dripstone_caves`, or `lush_caves` hits at all sampled fixed and
floor-relative Y bands; the extreme preset recovered some `deep_dark` near absolute world bottom and
some `lush_caves` far below the local floor, but still had zero low-floor cave-biome hits at Ancient
City's `Y=-27` band. Modded cave or underground biomes that register through vanilla/TerraBlender
climate parameters could be affected the same way if they depend on the `depth` axis, but that
remains a compatibility risk to test per mod.

A likely fix would not require replacing vanilla `MultiNoiseBiomeSource`. RTF already preserves that
model and feeds it RTF density functions (`CONTINENTS`, `EROSION`, `RIDGES`, `DEPTH`, etc.), which
is important for datapack, TerraBlender, and modded-biome compatibility. The less invasive direction
is to adjust the density function that feeds `NoiseRouterData.DEPTH` so that biome-depth better
tracks RTF's local terrain/floor in very deep oceans. That would still be a broad biome-distribution
change and should be regression-tested against vanilla cave biomes and modded climate-parameter
biomes.

The original extreme preset (`worldDepth=624`, `oceanDepth=677`) has now been rerun with the broader
coarse scanner in `biome-climate-banding-investigation.md`. Older direct scans had already proved
the same practical failure in the original searched area: low floors were common, `deep_dark`
columns existed, and overlap was zero:

```text
center=(-30768,-34080), radius=1024, step=16, threshold floor<=-64:
columns=16641 deepDarkColumns=1319 deepFloorColumns=11502 hits=0 cells=0

center=(-30768,-34080), radius=8192, step=32, threshold floor<=-27:
columns=263169 deepDarkColumns=9097 deepFloorColumnsAmongDeepDark=0 hits=0
```

The newer coarse rerun extends that: at `Y=-27`, low-floor columns again had zero bottom-depth, zero
underground-depth, and zero actual cave-biome hits.

**Searched for a live, confirmed-floating or protruding instance and found none in 32 real, verified
samples.** Two real instances at default vanilla spacing (`spacing: 24, separation: 8`), both
verified via `/locate`. A temporary QA-only datapack overriding
`data/minecraft/worldgen/structure_set/ancient_cities.json` to `spacing: 6, separation: 2` (~16x
density, layered alongside the RTF preset in the same datapack zip, standard technique, doesn't
touch biome logic or RTF code) surfaced 30 more real instances in the same explored area.
`MixinAncientCityQA` reports solidity split by Y-band (top half vs. bottom half of the structure's
bounding box, not just one aggregate number) specifically to catch _partial protrusion_ — Ancient
City's vertical extent is fixed and shallow (start Y=-27, bottom Y=-64 in every instance checked)
compared to trial chambers, so a deep-water instance could plausibly have its lower half still in
real ground while its upper half pokes into open water, which an aggregate-only reading would
average away.

All 32 samples read consistently healthy on both bands (e.g. top=25%/bottom=24%, top=13%/bottom=13%,
top=28%/bottom=26% — no case anywhere close to a floating or asymmetric-protrusion signature). This
doesn't mean the blind-start-height defect cannot manifest for Ancient City — the mechanism is
proven. It means the real, biome-validated Ancient Cities found so far are in `deep_dark` regions
under high terrain, not in low-ocean regions where the defect would become visible. A naturally
occurring floating/protruding Ancient City probably requires either a different seed/preset where
low floor and `deep_dark` climate overlap, or a boundary case where the Ancient City anchor passes
in high-terrain `deep_dark` while part of the structure footprint extends into adjacent low ocean.

## Beardifier.compute() performance: not a bottleneck

Checked whether `Beardifier.compute()`'s call volume was a real performance problem, prompted by an
unrelated, real, already-fixed RTF issue (ETcodehome/ReTerraForged#69/#98, sculk generation — Spark
profiling confirmed 48% of a profiled sample, requiring an architecture rewrite).

`MixinBeardifierTimingQA` wraps every `compute()` call with `System.nanoTime()` (thread-local
start-time stash, since `compute()` runs on chunk-generation worker threads) across a heavy
synthetic workload (568 chunks forceloaded across 3 regions on a 32-core machine, ~63 seconds of
real generation):

```text
totalCalls=268,600,000 totalMs=15,555 avgNanosPerCall=57
```

15.6 seconds of summed time across many parallel worker threads over a ~63 second burst — on the
order of 1-3% of wall-clock time even under pessimistic overlap assumptions, not sculk's 48%.
57ns/call matches the source: a loop over a handful of nearby pieces doing simple floating-point
arithmetic, no block I/O, no cross-chunk access. Not a bottleneck.

## Not yet done

- **The start-height fix (multi-point worst-case floor sampling + real-bounding-box safety check +
  upward window rescue) is implemented and empirically validated across all three reference
  presets** — see "Final empirical results" and "Upward window rescue" above. Still QA-only,
  unconditionally active, not gated behind a debug flag, and not cleaned up for a real PR (see
  "Reproduction reference" below for what to remove before this branch goes anywhere real).
- Three reasoned-but-unmeasured constants remain: `MARGIN = 10` (minimum bury depth, used both
  pre-build for target selection and post-build for the top-side check — one constant covers both
  the floor side and the surface side, since it's the same question asked from opposite ends),
  `BOUNDARY_TOLERANCE = 8` (post-build: how close the real bottom can sit to the world's real
  minimum build height before being treated as truncated), and `GRID_STEPS_PER_SIDE = 3` (grid
  resolution for the floor/surface sample, 7x7 points — a performance/precision tradeoff rather than
  a safety margin, but still an arbitrary choice). None are empirically derived; all are candidates
  for tightening if this ships.
- Whether any fix belongs in `feat/configurable-ocean-depth` at all, versus documented as a known
  limitation, is an open product/scope call — not resolved here.
- No naturally-occurring floating/protruding Ancient City has been visually confirmed for a PR
  screenshot; 32 real samples checked, all healthy on both aggregate and Y-band readings. With the
  skip logic active, a genuinely floating Ancient City may now be structurally impossible to produce
  in this seed's most extreme basin (it would skip instead) — the missing screenshot is even less
  likely to be findable going forward, which is the intended outcome, not a gap to chase further.
- Current climate-axis proof was run against the corrected vanilla-depth Goldilocks preset. Older
  extreme-preset scans proved no `deep_dark`/low-floor overlap in the searched region, but did not
  log which climate axis caused the separation.
- Whether `beard_box` (Ancient City's terrain adaptation) has an analogous per-piece gap remains
  unread and untested; nothing here depends on it either way.
- `dev-server stop`'s child-process cleanup gap (see "Final empirical results" above) is a tooling
  issue found during this testing pass, not fixed here.

## Summary table

| Structure      | Depth-aware today? | Root cause if not                                                                                                                                                                 | Confidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ocean Monument | Fixed in RTF       | Hardcoded absolute anchor (`Y=39`), sampled height discarded                                                                                                                      | High — code-confirmed, live-verified, fixed by `b687932`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Ocean Ruins    | **Yes**            | n/a                                                                                                                                                                               | High — empirically verified via direct block-level ground scan, 10 placements including extreme deep water, zero exceptions                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Shipwrecks     | **Yes**            | n/a                                                                                                                                                                               | High — empirically verified against vanilla's own footprint-averaged calculation, exact match in both measured placements                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| Trial Chambers | Fixed (QA-only)    | Blind `start_height` with no terrain check, combined with `ENCAPSULATE`'s per-piece-only halo                                                                                     | High — reproduction, discovery, and magnitude measurement confirmed at both a floating and a healthy chamber, code-traced to the exact mechanism; fix empirically verified live across all three reference presets (real corrected burials measuring 20-30% solid, healthy baselines unchanged, a real-bounding-box safety check confirmed both correctly rejecting genuinely truncated placements and correctly accepting healthy ones, the exact known-floating location no longer generates, a Goldilocks-preset over-triggering regression caught and fixed before landing) |
| Ancient City   | Unconfirmed live   | Same blind `start_height` as trial chambers, but real instances require `deep_dark`; current scans show low ocean floors and `deep_dark` climate do not overlap in tested regions | High on mechanism and biome-climate separation; unconfirmed on real-world manifestation (no floating/protruding instance found yet)                                                                                                                                                                                                                                                                                                                                                                                                                                             |

## Reproduction reference

- Seed `3216933670`. Very-deep preset:
  `~/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset.zip`
  (oceanDepth=677, worldDepth=624, seaLevel=63). Shallowest preset: same directory,
  `ocean-depth-test-preset-shallowest.zip` (oceanDepth=10, worldDepth=128). Both checksum-verified
  against `qa-presets.md`.
- Known coordinates: floating trial chamber `[-30768,~,-34080]`; healthy trial chambers
  `[1392,~,1408]`, near `(1998,~,720)`, near `(1264,~,784)`, near spawn `[816,~,992]` (`1.21.1`
  baseline branch); ocean ruins near `(1024,~,640)`, `(2048,~,720)`, and two in the same deep-water
  region as the floating chamber (`(-30896,~,-34240)`, `(-30688,~,-34224)`); shipwrecks near
  `(912,~,624)` and `(1264,~,784)`; real Ancient Cities (all healthy, both aggregate and Y-band) at
  `[-31824,~,-33344]` and `[-31472,~,-33376]` (default spacing), plus 30 more found via the dense
  spacing datapack in the region roughly `-31900,-33700` to `-31000,-33150`.
- Dense Ancient City datapack: override `data/minecraft/worldgen/structure_set/ancient_cities.json`
  to `spacing: 6, separation: 2` (vanilla default is `24, 8`), packaged into the same datapack zip
  as the RTF preset (a second `data/` path added into the existing zip, since `dev-server` currently
  stages one `--datapack` file at a time). Confirmed working: doesn't disturb the RTF preset's own
  content, produces real, biome-validated instances at ~16x the default density.
- Use `games/minecraft/tooling/dev-server` (start/stop/rcon subcommands) for launches — seeded,
  datapack-staged, RCON-driven, verified teardown. See `games/minecraft/tooling/README.md` and
  `live-worldgen-investigation-howto.md`.
- QA mixin source (`common/src/main/java/raccoonman/reterraforged/mixin/qa/`) is temporary
  investigation scaffolding, QA-only and unconditionally active, not meant to ship as-is. Current
  registered set includes `MixinTrialChamberQA`, `MixinBeardifierTimingQA`, `MixinAncientCityQA`,
  `MixinAncientCityCandidateScanQA`, `MixinAncientCityDeepDarkFloorScanQA`, and (as of the v2 fix,
  2026-07-19) `MixinJigsawStartHeightFixQA` — now registered and active by default, since it's the
  actual fix, not just a diagnostic scanner. Remove this scaffolding and revert `mixins.json` before
  this branch goes anywhere real, but note `MixinJigsawStartHeightFixQA` specifically would need to
  be reworked into a non-QA, permanent mixin rather than simply deleted, if the fix is kept.
