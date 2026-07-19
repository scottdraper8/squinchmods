# Trial Chambers and Other Ocean-Adjacent Structures

## Status: 2026-07-18, updated same day with empirical findings

Follow-up to `monument-placement-research.md`. ETcodehome's PR #97 review also flagged trial
chambers spawning as "large floating blobs because they don't expect oceans deeper than y0," while
noting it "may possibly predate this PR but just not be as visible during regular generation" and
wasn't sure it was worth addressing. Investigated whether the monument anchor-fix generalizes here,
and surveyed the other ocean structures (ocean ruins, shipwrecks) to see whether they need any fix
at all.

**Short answer: no single fix covers all of these. Three genuinely different situations.**

This doc originally proposed a "Beardifier structure-discovery integration gap" as the working
hypothesis for trial chambers, based on static code reading alone. That hypothesis was empirically
tested and ruled out. A later direct `Beardifier.compute()` magnitude measurement settled the actual
root behavior: `ENCAPSULATE` protects individual pieces with a small per-piece halo, not a sprawling
multi-piece structure's combined footprint.

## Confirmed by direct visual reproduction (real client, not just code reading)

Reproduced independently on a real client, seed `3216933670`, using the
`ocean-depth-test-preset.json` preset (`worldDepth: 624`, `oceanDepth: 677` — real, valid preset
values, `oceanDepth` well within the UI's own `[10, seaLevel + worldDepth - 10]` clamp):

- At more modest depth settings, the trial chamber's structure visibly **protrudes** out of the
  seafloor rather than sitting flush.
- At `worldDepth: 624` / `oceanDepth: 677`, the same seed/location produces a trial chamber **fully
  floating in open deep water** — confirmed via screenshot standing directly beneath it in open blue
  water, F3 debug overlay confirming `Deep Ocean` biome at that position.

This settled "is this real" definitively before any instrumentation existed. Everything below is
about isolating _why_, not _whether_.

## QA instrumentation built to quantify and isolate root cause

Two mixins, `raccoonman.reterraforged.mixin.qa.*`, built for this investigation (not intended to
ship in the PR — QA-only, unconditionally active, no debug flag gating):

**`MixinTrialChamberQA`** — hooks `ChunkGenerator.applyBiomeDecoration`
(`@Inject(at = @At("TAIL"))`), and for any chunk touching a `TRIAL_CHAMBERS` structure start,
samples a shell of blocks around the structure's real combined bounding box
(`StructureStart.getBoundingBox()`, margin 10, step 2, excluding points inside the structure's own
box), logging:

```text
[RTF-QA] TRIAL_CHAMBERS encapsulation: bbox=(x1,y1,z1)-(x2,y2,z2) solid=N/M (P%) [skippedUnloadedColumns=K]
```

**Real crash bug found and fixed during this work:** the first version read blocks unconditionally,
which crashed the game
(`IllegalStateException: Requested chunk unavailable during world generation`) because a large trial
chamber's combined bounding box can span 10+ chunks, while `WorldGenRegion` (the level type active
during `applyBiomeDecoration`) only allows safe reads within a narrow radius of whatever chunk is
currently generating — `WorldGenRegion.getBlockState()` calls `getChunk()` with no bounds check at
all. Fixed by guarding every column with
`level.hasChunk(SectionPos.blockToSectionCoord(x), SectionPos.blockToSectionCoord(z))` first and
skipping (not counting) anything outside the safe radius, logging the skip count so readings'
completeness is visible. Verified fix against the exact crash scenario (same seed/coords) before
re-shipping — no crash, identical result to the pre-fix reading.

**`MixinBeardifierDiscoveryQA`** — hooks `Beardifier.forStructuresInChunk`
(`@Inject(at = @At("RETURN"))`), and for chunks touching a `TRIAL_CHAMBERS` start, uses the existing
`BeardifierAccessor` (already in RTF's codebase, exposes the private
`pieceIterator`/`junctionIterator` fields) to count how many rigid pieces the _constructed_
`Beardifier` instance actually contains for that chunk — i.e., whether Beardifier's own
structure-discovery sees the trial chamber at all. Iterator is reset
(`pieces.back(Integer.MAX_VALUE)`) after counting so the real generation pass downstream isn't
disturbed. No block reads, no cross-chunk access — safe by construction, no crash risk.

Both jars (`feat/configurable-ocean-depth` + `1.21.1` baseline, each with identical instrumentation)
built and tested on a headless dev server with RCON (`fabric:runServer`, `enable-rcon=true`), using
the same seed/datapack as the client reproduction, before ever shipping to the real-client tester.

## Results

**Floating trial chamber location** (seed `3216933670`, near `-30768,~,-34080`, the same structure
visually confirmed floating):

```text
[RTF-QA] TRIAL_CHAMBERS encapsulation: bbox=(-30843,-59,-34163)-(-30733,15,-34020) solid=0/106560 (0%) [skippedUnloadedColumns=0]
```

Reproduced twice (before and after the crash fix), identical result both times. Zero solid blocks
across the entire ~106k-point sample of the shell around the structure. Not a partial/patchy
degradation — total absence of solid terrain around it.

**Baseline, land-based trial chamber, plain `1.21.1`** (same seed, near spawn `[816,~,992]`, where
`oceanDepth` doesn't exist and floor is always clamped at Y=0 — this scenario can never physically
produce a floating chamber):

```text
[RTF-QA] TRIAL_CHAMBERS encapsulation: bbox=(761,-43,969)-(886,31,1085) solid=21374/100530 (21%)
```

Caveat on this number: trial chambers are large, multi-room structures with a lot of their own
normal interior air space within their combined bounding box, so 21% is _not_ necessarily "what
fully healthy looks like" — it may just reflect how much of the sampled shell falls inside the
structure's own irregular footprint. One data point; not yet confirmed as representative via
repeated sampling.

**Beardifier discovery check, both locations:** structure-discovery works correctly. For the
floating trial chamber specifically, individual chunks reported up to **115 rigid pieces found** by
`Beardifier.forStructuresInChunk`, with many other chunks in the 30-113 range and only chunks on the
structure's periphery (outside the `isCloseToChunk(chunkPos, 12)` filter) reporting 0, exactly as
expected. The near-spawn baseline chamber showed the same healthy pattern (up to 44 pieces per
chunk).

## Magnitude measurement — settled, not a guess anymore

Built `MixinBeardifierMagnitudeQA`, hooking `Beardifier.compute()` directly
(`@Inject(at = @At("RETURN"))`) and tracking aggregate stats (total calls, non-zero calls, sum, max
absolute value) for every real invocation within the floating trial chamber's region during actual
generation — not a synthetic single-point probe, every call the real generator made. Deliberately
did _not_ filter out zero values before aggregating (an earlier draft of this instrumentation did,
and would have silently hidden the actual finding).

**Result, floating trial chamber location:**

```text
[RTF-QA] Beardifier magnitude summary near TRIAL_CHAMBERS: totalCalls=14500 nonZeroCalls=0 sum=0.0 maxAbs=0.0
```

Beardifier _is_ being invoked constantly in this exact region — 14,500+ real calls, confirming the
marker-substitution mechanism genuinely wires in the real `Beardifier` instance during density
computation, exactly as the earlier code reading predicted. But every single call returned **exactly
zero**, not "small." That rules out "magnitude mismatch" as originally framed (a weak-but-present
contribution) — this is "contributes nothing at all" in the sampled region, which needed a different
explanation.

**Traced `Beardifier.compute()`'s actual math to find it** (`ENCAPSULATE` is trial chambers' terrain
adaptation type):

```java
case ENCAPSULATE -> getBuryContribution(m / 2.0, q / 2.0, n / 2.0) * 0.8;
// getBuryContribution:
double g = Mth.length(d, e, f);
return Mth.clampedMap(g, 0.0, 6.0, 1.0, 0.0);   // hard zero once combined distance >= 6.0
```

`m`, `q`, `n` are each computed as distance _outside a single rigid piece's own bounding box_ (zero
if inside it) — not the structure's combined bounding box. Halved before the distance check, this
gives `ENCAPSULATE` an effective influence radius of roughly **12 blocks from each individual
piece's own edges**, then a hard clamp to exactly zero beyond that.

**This is the actual root cause, and it reconciles both measurements cleanly.** A trial chamber is a
large, sprawling structure built from many small individual rooms (confirmed earlier: up to 115
separate rigid pieces in a single chunk). Beardifier protects a ~12-block halo around _each
individual piece_, not the structure's overall footprint. The solidity scan sampled the margin
around the structure's _combined_ bounding box — for a sprawling multi-piece structure, that
combined-box margin can be, and evidently is, far outside any single piece's own 12-block halo, even
while still "near the structure" in the loose sense a human would use. Same reason the magnitude
probe landed exactly zero everywhere it sampled in that region.

**This is not "Beardifier is broken" or "too weak."** It's that Beardifier's design protects the
immediate vicinity of individual structure pieces, not a large multi-piece structure's full outer
perimeter — a property of vanilla's Beardifier design in general, unrelated to RTF or this PR. What
`oceanDepth` does is expose it: it's the first scenario where "far from any individual piece, but
still within the structure's rough footprint" can be open water instead of naturally-solid ground,
which it always was before for reasons that had nothing to do with Beardifier's reach at all.

**Confidence: high.** This is a real code trace matching two independent empirical measurements
(structure-discovery counts, solidity percentages, and now direct Beardifier magnitude), not
elimination-based inference. The one thing not yet done: confirming this same "combined-box margin
falls outside individual piece halos" pattern holds for the healthy near-spawn baseline chamber too
(would be expected to, since the mechanism is generic, but not directly measured there).

## Causation framing (what this means for "does this PR cause the bug")

Precise version, not the shorthand: the underlying mechanism (Beardifier's per-piece, ~12-block
influence radius, which doesn't cover a large multi-piece structure's full combined footprint) is
unchanged vanilla behavior — this PR didn't modify Beardifier, and directly confirmed it still
correctly discovers affected structures and is still actively invoked during density computation.
But before this PR, RTF's hard clamp at Y=0 meant the area between individual pieces' Beardifier
halos was always naturally solid ground anyway, for reasons unrelated to Beardifier's reach —
nothing ever exposed the gap. `oceanDepth` is what newly allows that in-between area to be open
ocean water instead. **Pre-existing limitation, newly exposed, not newly introduced** — matching
ETcodehome's original "may predate this PR" suspicion, now with empirical, code-traced support
rather than speculation.

## Not yet done

- Confirming the same "combined-box margin falls outside individual piece halos" pattern on the
  healthy near-spawn baseline chamber (expected to hold, not directly measured there).
- Repeated baseline sampling on `1.21.1` (more than one trial chamber) to establish what a genuinely
  "healthy" solidity percentage looks like, since 21% may not be representative.
- No RTF code fix has been written or proposed as a concrete patch. Given the actual mechanism is
  now understood precisely, options include: a `StructureProcessor`-style fix that extends solid
  terrain between nearby pieces rather than relying on Beardifier's per-piece reach (conceptually
  similar to the leg-extension approach from `monument-placement-research.md`, adapted for a
  multi-piece structure); or accepting this as an inherent property of large jigsaw structures that
  RTF's `oceanDepth` merely exposes, not something worth fixing at the generator level. Neither
  evaluated for feasibility or cost yet.
- Given ETcodehome already flagged this as low-priority ("not sure it's worth addressing"), whether
  any fix belongs in `feat/configurable-ocean-depth` at all, versus documented as a known
  limitation, is still an open call for the PR — this doc doesn't resolve that, only the technical
  root cause.

## Ocean Ruins and Shipwrecks: already correctly depth-aware, no fix needed

Checked both, expecting to find the same missing-floor-tracking problem as monuments. They don't
have it — and use a _better_ technique than what was proposed for monuments.

**`OceanRuinPieces.OceanRuinPiece.postProcess()`:**

```java
int i = worldGenLevel.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, this.templatePosition.getX(), this.templatePosition.getZ());
this.templatePosition = new BlockPos(this.templatePosition.getX(), i, this.templatePosition.getZ());
```

**`ShipwreckPieces.ShipwreckPiece.postProcess()`** (non-oversized path):

```java
Heightmap.Types types = this.isBeached ? Heightmap.Types.WORLD_SURFACE_WG : Heightmap.Types.OCEAN_FLOOR_WG;
// averages worldGenLevel.getHeight(types, x, z) across the piece's footprint
this.adjustPositionHeight(this.isBeached ? this.calculateBeachedPosition(i, randomSource) : j);
```

(The oversized-piece path uses `Structure.getMeanFirstOccupiedHeight`/`getLowestY` earlier in
`generatePieces` instead, same idea, different call site for a footprint too big for normal
world-gen-region bounds.)

Both re-sample height and reposition themselves **inside `postProcess()`**, which runs during the
`FEATURES` chunk-status step — _after_ `NOISE`/`SURFACE`/`CARVERS` have already produced the real,
finalized terrain for that region. `worldGenLevel.getHeight(...)` at that point is an actual
heightmap lookup on generated blocks, not the early on-demand density-function preview
`findGenerationPoint()` uses (see `monument-placement-research.md`'s performance section — that
preview is accurate but is still a preview, computed before `CARVERS`/`SURFACE` run). The
`postProcess()`-time resample has no such caveat at all: it's the latest possible point, reading
already-final terrain.

This means ocean ruins and shipwrecks should already correctly track RTF's variable `oceanDepth`
floor with zero RTF-side changes. If QA finds otherwise, the bug would be somewhere RTF-specific
(e.g. `Heightmap.Types.OCEAN_FLOOR_WG` not being populated correctly for RTF-generated chunks at
`postProcess` time), not a missing floor-tracking mechanism — the mechanism vanilla uses here is
already exactly the fix that would be wanted. Not yet empirically tested the way trial chambers
were.

## Ocean Structure Comparison

Ocean ruins and shipwrecks confirm that vanilla already has floor-aware ocean-structure placement
patterns, but they do not imply one shared fix for every structure:

- Ocean ruins and shipwrecks reposition themselves late, during placement, from real heightmap data.
- Ocean monuments needed a separate fix because their building anchor is hardcoded and guardian
  spawn overrides use structure bounds, so moving only during `postProcess()` is too late.
- Trial chambers are not a placement-anchor problem at all; their exposed issue comes from
  `ENCAPSULATE` only protecting individual pieces.

See `monument-placement-research.md` for the final monument implementation and why it uses an
earlier structure-start hook instead of a pure `postProcess()` adjustment.

## Blast radius: which vanilla structures use ENCAPSULATE

Directly checked, not assumed. `terrain_adaptation` is a single field on each structure's own
definition file (`data/minecraft/worldgen/structure/<name>.json`) — one value for the whole
structure, applied to every piece uniformly. It is NOT set per-piece in the template-pool JSONs
(those only carry `projection`: `rigid`/`terrain_matching`). Extracted and read all 30 vanilla
structure definition JSONs directly from the real game jar
(`~/.gradle/caches/neoformruntime/artifacts/minecraft_1.21.1_client.jar`,
`data/minecraft/worldgen/structure/*.json`) rather than assuming from the pool JSONs, since the pool
JSONs turned out not to carry this field at all.

Results — every vanilla structure that declares `terrain_adaptation` explicitly:

| Structure                                                                                                                                                                              | `terrain_adaptation`                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trial Chambers**                                                                                                                                                                     | **`encapsulate`** — the only one                                                                                                                            |
| Ancient City                                                                                                                                                                           | `beard_box`                                                                                                                                                 |
| Villages (all 5 biome variants), Pillager Outpost, Nether Fossil                                                                                                                       | `beard_thin`                                                                                                                                                |
| Trail Ruins, Stronghold                                                                                                                                                                | `bury`                                                                                                                                                      |
| Everything else (Bastion, Mansion, Monument, Ocean Ruins, Shipwrecks, Ruined Portals (all variants), Desert Pyramid, End City, Fortress, Igloo, Jungle Pyramid, Mineshafts, Swamp Hut) | field omitted → defaults to `none` (confirmed via `Structure.StructureSettings.DEFAULT.terrainAdaptation = TerrainAdjustment.NONE` in `Structure.java:249`) |

**Trial Chambers is the only vanilla structure using `encapsulate`.** Ancient City looks
superficially similar (also a large multi-piece underground jigsaw structure) but runs a different
branch of `Beardifier.compute()` (`beard_box`, not `encapsulate`) — the specific per-piece-halo gap
mechanism documented above for `ENCAPSULATE` does not automatically apply to it; `beard_box`'s own
gap behavior (if any) hasn't been read or tested and shouldn't be assumed either way without
checking `Beardifier.java`'s `BEARD_BOX` case specifically.

Practical implication: a targeted fix to the `ENCAPSULATE` case in `Beardifier.compute()` (or an
RTF-side mixin around it) has a blast radius of exactly one vanilla structure type — Trial Chambers
— with no vanilla cross-structure risk. (Datapack/mod-added structures that opt into `encapsulate`
themselves would also be affected, but that's outside vanilla's own set.)

## Summary table

| Structure      | Depth-aware today? | Root cause if not                                                                                                                                                                                                                | Confidence                                                                                                         |
| -------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Ocean Monument | Fixed in RTF       | Hardcoded absolute anchor (`Y=39`), sampled height discarded                                                                                                                                                                     | High (code-confirmed, live-verified, fixed by `b687932`)                                                           |
| Ocean Ruins    | **Yes**            | n/a                                                                                                                                                                                                                              | Moderate (code-confirmed, not empirically tested)                                                                  |
| Shipwrecks     | **Yes**            | n/a                                                                                                                                                                                                                              | Moderate (code-confirmed, not empirically tested)                                                                  |
| Trial Chambers | No                 | Beardifier's `ENCAPSULATE` contribution has a ~12-block halo per individual piece, not the structure's combined footprint; the gap between pieces was always naturally solid pre-PR, `oceanDepth` newly exposes it as open water | High — reproduction, discovery, and direct magnitude measurement all confirmed, code-traced to the exact mechanism |

## Reproduction reference (for picking this back up later)

- Seed `3216933670`, preset `ocean-depth-test-preset.json` (`worldDepth: 624`, `oceanDepth: 677`,
  `SpawnType: CONTINENT_CENTER`), floating trial chamber near `-30768,~,-34080`.
- QA jars on the user's Desktop from the original client-side trial-chamber testing were temporary
  investigation artifacts and should not be treated as current production builds.
- The trial-chamber QA mixin source was temporary investigation scaffolding. It has been removed and
  unregistered from the shippable RTF branch; reapply it manually from these notes or git history if
  the trial-chamber investigation is resumed.
