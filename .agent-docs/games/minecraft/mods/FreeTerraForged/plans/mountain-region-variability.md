# Mountain Region Variability

Status: PR [ETcodehome/FreeTerraForged#95](https://github.com/ETcodehome/FreeTerraForged/pull/95) is
open at `8c955b6`. Broad standalone QA and targeted finished-chunk QA were run on 2026-08-03 against
an effective merge with upstream `1.21.1` at `b87e9dc`. The feature produces the intended regional
variation and PR #162 resolves the reported uplift-cell transition defect. Maximum variety can
exceed the default preset's configured vertical bounds and create ceiling-clipped mountains. A local
headroom-aware compression fix now passes three broad effective-PR scans and finished-chunk QA and
was pushed to the feature branch in `809ca2a`. This is not a hard-coded Y384 cutoff: a no-mod
control with a taller dimension generated the tested terrain above Y500.

**A separate defect was found on 2026-08-03 in client visual QA**: continuous mountain chains
(`terrain == "mountain_chain"`) could show a sheer, near-vertical cliff mid-chain, unrelated to and
unfixed by either PR #162 or `809ca2a`. Fixed locally in two passes (`Heightmap.java`,
`VariedMountainPopulator.java`) — see "Mountain-chain variant hard-switch defect" below for the root
cause, the corrected fix, and validation evidence. **A second, independent defect was found while
validating the first**: a super-unity fractal gain (1.15) in the shared ridge-noise construction
used by both plain M1 mountains and mountain chains can itself produce near-single-block height
jumps at certain (seed- and scale-dependent) locations, worst at narrow `horizontalScale`. This is
not fixed by the variant-selection work and is not specific to `mountainVariety` — see "Open:
super-unity `perlinRidge` gain sensitivity" below.

## PR relationship and image review

PR #95 adds `mountainVariety`, with `0.0` preserving the existing path and `1.0` selecting
deterministic low, center, and high variants for M1/M2/M3 mountain regions and continuous mountain
chains. The low variants are shorter, wider, and more eroded; the high variants are taller,
narrower, and sharper. A wrapper preserves the outer terrain selector's weighted-array layout.

ETcodehome's first screenshots showed abrupt-looking preview boundaries that were less concerning in
game. Larger scale settings then exposed sheer, rectilinear terrain walls both in the preview and in
finished terrain. PR [#162](https://github.com/ETcodehome/FreeTerraForged/pull/162) subsequently
isolated a pre-existing uplift-continent defect:

- the same division remained after reducing noise, warp, and jitter contributions;
- switching from `UPLIFT` to `MULTI` removed it;
- adjacent uplift cells could bleed into the selected cell's height calculation; and
- replacing that edge calculation removed the division in PR #162's comparison image.

PR #162 explicitly cites PR #95's large-scale screenshots as a likely instance of the same defect.
The geometry also matches: both sets show long, sheer cuts aligned to a cellular boundary rather
than the softer Voronoi terrain-region blend. PR #162's fix commit is `587f4b6`, merged to `1.21.1`
by `77df3ae`.

PR #95's head itself still ends at `8c955b6`; GitHub evaluates it against the advanced base. Local
QA therefore used the clean, local-only merge `f087529` (`qa/pr95-effective-20260803`) to represent
the effective PR tree. Do not push that merge as a replacement for the feature head without first
deciding how PR #95 should be refreshed.

## QA inputs and authority

The broad scans used the real compiled `Preset`, noise bootstrap, `GeneratorContext`, and
`generateZoomed` path through `mc-investigate cell-scan`. They are horizontal terrain-model
predictions, not final-block proof. Full CSV grids were retained so adjacent samples could be
classified by terrain-region and uplift-cell ownership.

The main input was the `vanilla-depth-maximum-ocean` fixture, whose terrain settings are otherwise
the current defaults (`UPLIFT`, `terrainRegionSize = 1200`, fancy mountains enabled). Maximum
variety was applied as an ephemeral merge patch. Three seeds were scanned over 65,536 × 65,536 block
windows, 65,536 samples per seed:

- `-2410519835783799016` — the seed documented by PR #162;
- `12345`; and
- `8675309`.

Two larger-scale inputs were also used:

- enlarged horizontal scale: `terrainRegionSize = 4000`, `globalHorizontalScale = 2.0`, and mountain
  `horizontalScale = 3.0`, over a 131,072 × 131,072 block window; and
- deliberate transition stress: the same region/global scales plus mountain `weight = 5.0`,
  `baseScale = 1.5`, and `verticalScale = 2.0`.

The stress input exceeds normal vertical expectations and is evidence only for edge behavior. It is
not a recommended preset. Two one-chunk Fabric scenarios crossed the real loader, registry, chunk,
and stored-heightmap boundary for the highest default-scale prediction.

## Variability result

The feature's core layout and variation behavior works as intended.

On the PR #162 seed, a variety-off and maximum-variety comparison of 65,536 matching coordinates
found:

- zero coordinate, continent-field, terrain-region-ID, or terrain-region-edge mismatches;
- 5,191 changed sampled heights overall;
- 2,250 of 5,525 highland samples changed (40.72%);
- 57.69% of M1, 62.77% of M2, 57.37% of M3, and 41.91% of mountain-chain samples changed; and
- both shorter and taller outcomes: highland deltas ranged from -216 to +281 blocks.

Sampled M1/M2/M3 region peaks contained lower, near-center, and higher outcomes:

| Terrain       | Region IDs | Lower | Near center | Higher | Peak-delta range |
| ------------- | ---------: | ----: | ----------: | -----: | ---------------: |
| `mountains_1` |         51 |    13 |          32 |      6 |      -188 to 135 |
| `mountains_2` |         47 |    10 |          24 |     13 |       -57 to 101 |
| `mountains_3` |         52 |    13 |          22 |     17 |      -161 to 173 |

The outer selector layout is preserved, which is the important compatibility invariant. Sixty-five
of 65,536 final terrain labels changed only at shoreline thresholds (35 beach→ocean, 28 ocean→beach,
and 2 coast→ocean), consistent with mountain-chain height changes reaching those columns rather than
a remapped terrain-region selector.

Across the three maximum-variety seeds, the scans sampled 459 M1/M2/M3 region IDs and produced
substantial highland variation without a single uplift-cell boundary classified as highland.

## Transition result

The specific sheer transition reported on PR #95 was not found after PR #162.

At the default scale, adjacent highland samples crossing terrain-region boundaries were no more
abrupt than samples inside regions:

| Seed                   | Boundary p99 / max | Interior p99 / max |
| ---------------------- | -----------------: | -----------------: |
| `-2410519835783799016` |          154 / 246 |          178 / 298 |
| `12345`                |          162 / 272 |          165 / 326 |
| `8675309`              |          160 / 286 |          178 / 307 |

These are block-height differences between samples 256 blocks apart, so they describe broad slope
change rather than a one-block cliff. Boundary mean jumps were also lower than interior highland
means for all three seeds.

The amplified negative control was more discriminating. Before PR #162, the 131,072-block scan found
14 highland-adjacent edges crossing uplift-cell ownership, with a maximum 327-block jump over 512
blocks. The effective PR tree found zero such crossings. For other uplift-cell edges, the p99 jump
fell from 95 to 34 blocks and the maximum from 383 to 215. A 4,096 × 4,096 refinement at 16-block
spacing around the old worst broad candidate reduced the maximum non-highland uplift-edge jump from
76 blocks before the fix to 9 after it.

The enlarged-horizontal-scale scan also stayed in the same broad height envelope as the default
maximum-variety scans (maximum prediction 484), rather than reproducing the old cellular wall.

Conclusion: the evidence supports PR #162's diagnosis. PR #95 does increase ordinary mountain slope
variance, as intended, but it does not leave a distinct terrain-region seam signature in the scanned
areas. Visual client confirmation remains appropriate before merge, but the original transition
report is no longer an identified code blocker.

## Configured-height headroom finding and local fix

Maximum variety can push otherwise-default mountain chains through their preset's configured
dimension ceiling.

For the PR #162 seed, the raw model produced:

| Setting         | Samples ≥ Y320 | Samples ≥ Y384 | Maximum |
| --------------- | -------------: | -------------: | ------: |
| Variety off     |             24 |              1 |     387 |
| Maximum variety |            111 |             19 |     486 |

The two other maximum-variety seeds produced maxima of 499 and 460, with 108–117 samples at or above
Y320 and 14–22 at or above Y384. Existing terrain can already overshoot occasionally, but maximum
variety materially increases both the frequency and magnitude.

The highest varied candidate in the default-height comparison was `(32000, 1536)`: prediction 486
with maximum variety versus 271 with variety off. Finished-chunk Fabric evidence makes the impact
concrete:

- maximum variety: all 256 columns in the chunk had `WORLD_SURFACE_WG = 383`; the sampled top blocks
  were stone or coal ore, producing a completely flat ceiling-cut summit;
- variety off: the same 256 columns ranged from Y248 to Y278, with no columns at or above Y319.

That run's resolved preset has `worldHeight = 384` and `worldDepth = 64`. Its generated Overworld
dimension therefore spans Y-64 through Y383, so Y383 is the real top block. The raw terrain model
was trying to place the peak higher than the configured dimension; the finished chunk did not
encounter an independent Y384 terrain clamp.

### Issue #92 and mod-isolation cross-check

Issue [#92](https://github.com/ETcodehome/FreeTerraForged/issues/92) documents a different failure
mode: Lithostitched can apply another mod's worldgen modifier to `minecraft:overworld/offset`, and a
bad clamp there can flatten mountains at Y384 even when the dimension itself has more vertical
headroom. The reported Hybrid Aquatic 1.5.5 files wrapped the Overworld offset in `minecraft:clamp`;
that explains why issue #92 can produce a Y384 plane in a taller world.

That cause was not present in these QA runs:

- the recorded runtime contained ReTerraForged, Minecraft, Fabric Loader/API modules, MixinExtras,
  and the generated QA probe only; Lithostitched, Hybrid Aquatic, and TerraBlender were absent;
- the run materialized exactly one generated datapack, and its archive contains no `lithostitched`,
  `hybrid-aquatic`, or `worldgen_modifier` entry; and
- its `minecraft:overworld/offset` density function is ReTerraForged's generated height function,
  not an external Lithostitched wrapper.

A controlled rerun changed only the configured vertical range to `worldHeight = 1024` and
`worldDepth = 1024`, retaining the seed and maximum-variety terrain settings. The raw prediction at
`(32000, 1536)` remained 486, demonstrating that preset height did not alter or clamp the terrain
model. The finished chunk at that exact coordinate ranged from Y449 to Y486, rather than the
default-height run's uniform Y383, and all 256 columns passed Y384. A second finished chunk around
the taller scan's highest candidate ranged from Y502 to Y542. This directly rules out a general Y384
cutoff in PR #95.

The finding was therefore narrow but real: `mountainVariety = 1.0` consumed more headroom than the
otherwise-default 384-height preset provided, producing a flat cut at that preset's actual ceiling.
It was separate from both issue #92 and the uplift-cell transition fix.

### Local implementation

The feature working tree now applies a continuous `TerrainCeiling` transform after uplift hydrology,
erosion, smoothing, and corrections. This position is necessary because uplift is added after the
individual mountain populators. The transform:

- is constructed only when `mountainVariety > 0.0`, leaving the exact `0.0` compatibility path
  untouched;
- derives its normalized limits from the preset's real `worldHeight` and the existing terrain
  scaler;
- reserves 16 surface blocks in ordinary-height worlds;
- begins linear compression 112 blocks below that reserved target, preserving ordering and useful
  relief through the expected overflow range; and
- transitions with a matching slope into an asymptotic final eight-block tail, so even extreme
  custom settings remain below the target without a hard flat clamp.

The transform applies uniformly to final terrain heights. This is intentional: mountain-blended
columns can retain a final label such as `coast` even when mountain variety raised them by more than
130 blocks. Conditioning on `terrain.isMountain()` would miss those columns and introduce a new
category-edge discontinuity.

### Fix validation

The same three 65,536-sample effective-PR scans were repeated at maximum variety:

| Seed                   | Before maximum | Fixed maximum | Before ≥ Y384 | Fixed ≥ Y368 / Y384 |
| ---------------------- | -------------: | ------------: | ------------: | ------------------: |
| `-2410519835783799016` |            486 |           349 |            19 |               0 / 0 |
| `12345`                |            499 |           355 |            14 |               0 / 0 |
| `8675309`              |            460 |           339 |            22 |               0 / 0 |

Only 460–500 of 65,536 samples per seed changed, because lower terrain remains below the compression
start. The final curve did not recreate the transition problem: highland terrain-region boundary
maxima were 204–206 blocks per 256-block sample interval, while interior maxima were 225–235.

At `(32000, 1536)`, the authoritative finished chunk changed from all 256 columns at Y383 to a
Y334–Y349 surface containing 16 distinct height levels. The ceiling collision is gone and 15 blocks
of local relief remain.

The 1024-height control stayed completely unchanged: its 65,536-row CSV is byte-for-byte identical
before and after the fix, including the Y544 maximum. Its exact finished chunk remains Y449–Y486.
Thus taller presets keep their full mountain expression instead of being normalized toward the
default height.

No automated acceptance blocker remains in the tested scope. Client-side visual review of several
compressed high variants is still appropriate before merging PR #95.

## Mountain-chain variant hard-switch defect

Client visual QA on 2026-08-03 (seed `7193149640`, a user-authored "Modern Earthlike 3D Rivers"
preset, `mountainVariety = 1.0`, `terrainRegionSize = 5000`, `continentType = UPLIFT`) showed sheer,
striated cliff walls in-game and in a top-down elevation render — a dead-straight, unbroken
north-south line separating dramatically different terrain textures for the full visible map extent.
Raising `globalHorizontalScale` (2.5 → 5.0) and mountain `horizontalScale` (4.5 → 10.0) in a
follow-up preset did not soften it.

A standalone `cell-scan` (`mode=preview`, exact preset JSON, seed `7193149640`, 1024×1024 window at
4-block resolution around the reported location) found a real ~450-block height cliff (910 → 466
blocks) over a single 4-block step, running straight for the full 1024-block sampled window. On both
sides, `continent_id`, `continent_edge`, and `terrain_region_id` were identical — ruling out both
the uplift-cell defect PR #162 fixed and ordinary terrain-region edges, which the earlier QA in this
document already validated as smooth.

Root cause, confirmed by direct source reading (not just the scan):

- `Heightmap.java:132-171` (the `mountainVariety > 0.0` branch) builds three independently-seeded
  height variants (`chainLow`, `chainCenter`, `chainHigh`) for `mountain_chain` terrain and selected
  among them with a **separate, standalone Perlin noise field** (`chainSelector`, originally at
  `Heightmap.java:165-167`), wavelength `terrainRegionSize * 3`, sampled at an offset unrelated to
  `terrainRegionId` or `continent_id`.
- `VariedMountainPopulator.apply()` buckets that noise value into an index and called only
  `this.variants[index].apply(cell, x, z)` — a **hard, unblended switch**, unlike every other
  transition in the pipeline (`ContinentLerper2`, `Blender`, `RegionLerper` all explicitly
  `NoiseUtil.lerp` across a band; see `RegionLerper.java:16-41`). Because `chainSelector`'s
  zero-crossing is independent of `terrainRegionId`, it could fall in the middle of a terrain-region
  cell, far from any place blending machinery keyed on `cell.terrainRegionEdge` ever runs.
- The M1/M2/M3 (non-chain) variant path is different and not affected: it's built with the 2-arg
  `VariedMountainPopulator` constructor (`TerrainProvider.java:82-114`), which keys the same hard
  switch off `cellHash(cell.terrainRegionId, ...)` — constant within one terrain-region cell, so a
  variant only changes at a terrain-region cell boundary. M1/M2/M3 live inside `RegionSelector`,
  which `RegionLerper` (`Heightmap.java:130`) wraps directly — near a cell's edge, `RegionLerper`
  fades _that cell's own selected populator_ (variant choice included) toward a shared,
  position-independent "border" populator; because every cell converges on that same border value at
  its own edge, continuity follows without `RegionLerper` ever needing to know the neighbor's
  specific content. This matches the earlier finding in this document that boundary jumps were no
  worse than interior ones for M1/M2/M3.
- `chainSelector`'s wavelength depends only on `terrainRegionSize`, never on `horizontalScale` or
  `globalHorizontalScale` — which is why widening those settings in the follow-up preset did not
  reduce the cliff's sharpness (it can change how far apart cliffs are, not whether the switch
  itself is blended).
- `809ca2a`'s `TerrainCeiling` compression (the fix for the separate headroom finding above) is a
  per-column, purely vertical, monotonic function of `cell.height` alone with no horizontal
  blending, so it cannot mask or fix this discontinuity either.

### Fix, in two passes

**First pass (incomplete):** switched the chain's variant selection to reuse
`cellHash(terrainRegionId)` directly (`VariedMountainPopulator`'s existing 2-arg constructor, same
as M1/M2/M3), on the reasoning that this reuses an already-safe mechanism. Rebuilding and rescanning
the exact reported coordinates showed byte-for-byte identical numbers to before the fix — the
mosaic's `terrainRegionId` at that exact spot turned out to be genuinely constant across the whole
sampled span, and forcing pure `chainHigh` with zero switching machinery reproduced the same cliff,
proving it wasn't a switching artifact at that location at all (see "Open: super-unity `perlinRidge`
gain sensitivity" below for what that one actually was). Investigating the boundary case _properly_
(a 65,536-sample broad scan, not just the one originally reported spot) exposed the real gap:
`mountains` (the chain) is never wrapped by `RegionLerper` — it's blended into the mosaic separately
via `Blender(mountainShape, terrainBlend, mountains, 0.3F, 0.8F, 0.575F)` (`Heightmap.java:171`),
whose control signal is the `mountainShape` silhouette mask, unrelated to `terrainRegionEdge`. So
tying the chain's variant to `terrainRegionId` moved _where_ the switch happens without plugging it
into any blending — measured boundary-crossing deltas (max 702 / p99 702 / median 291 over 78
same-window sample pairs, seed `7193149640`) were just as bad as before.

**Second pass (validated):** `VariedMountainPopulator` gained a second constructor,
`VariedMountainPopulator(TerrainPopulator[] variants, TerrainPopulator edgeReference, float weight)`,
used only for the chain (`Heightmap.java`, `chainCenter` passed as `edgeReference`). `apply()` still
selects a variant via `cellHash(terrainRegionId, ...)`, but when `edgeReference != null`, it blends
the selected variant toward `edgeReference` as `cell.terrainRegionEdge` approaches a region boundary
— `RegionLerper`'s own "fade to a shared reference" technique, applied directly inside the chain's
own populator since the chain has no other opportunity to receive it. The M1/M2/M3 2-arg constructor
path is untouched (`edgeReference == null` skips the new branch entirely).

### Validation

Same seed (`7193149640`), same preset, same 65,536-sample broad scan
(`--bounds -31744 -31744 32768 32768`), before vs. after the second pass:

|                                           | Before (first pass) | After (second pass) |
| ----------------------------------------- | ------------------: | ------------------: |
| Boundary-crossing max / p99 / median      |     702 / 702 / 291 | 465 / 465 / **116** |
| Interior (same region) max / p99 / median |      680 / 374 / 64 |      493 / 339 / 73 |

A second seed (`12345`, same preset) confirmed the same pattern (boundary median 104 vs. interior
median 76 — no longer dramatically worse), ruling out seed-specific luck. Personality distribution
across distinct chain-bearing regions was checked directly (not assumed): 7 regions for seed
`7193149640` → {low: 1, center: 3, high: 3}; 9 regions for seed `12345` → {low: 6, center: 1, high:
2} — real variety across regions in both cases, not a fixed pick.

Finished-chunk confirmation crossed from prediction to real generated blocks: an `rtf_ephemeral`
scenario (base fixture `vanilla-depth-maximum-ocean`, merge patch = the full reported preset minus
`world.properties` — see the tooling-friction entry on why `world.properties` had to be excluded)
force- generated the exact 3-chunk region spanning the originally reported cliff and sampled every
column with `squinch:finished-chunk-palette` (`sample_step = 1`, `example_limit = 1000`). At the
exact coordinates that predicted a 910→466 cliff before the fix, real finished blocks read a smooth
367→367→…→366→366→… →365 descent — no jump. Across all 768 sampled columns in the region, the
largest adjacent-block height delta was 6 blocks, ordinary terrain variation.

Retained evidence: `20260803T221036Z-fc14b12691` (original defect scan),
`20260803T233134Z-419669d44b` (first-pass broad scan + heatmap, before second pass),
`20260803T233518Z-254a63c27e` (second-pass broad scan + heatmap), `20260803T233717Z-7d70d5afd5`
(second seed confirmation), `20260803T234612Z-05561a5dfb` (finished-chunk scenario run).

## Open: steep terrain within high-variant mountain chains

Found while validating the fix above, at the exact originally reported coordinates
(`x = 2645-2649, z = 793`, seed `7193149640`). Not fixed by either pass above.

`terrain_region_id` and `terrain_region_center_x/z` are bit-identical on both sides of this specific
cliff (confirmed both by field comparison and by directly forcing the code to use pure `chainHigh`
with every switching mechanism removed — same cliff, byte-for-byte). At 1-block resolution the
transition is a literal single-block jump (x=2646 → 910, x=2647 → 465). Disabling `makeFancy` (the
erosion/warp post-process) did not remove it (848 → 516 at the same spot). Narrow `horizontalScale`
alone, with otherwise-default settings, produced only a mild 23-block step, not hundreds.

A broad 65,536-sample scan (seed `7193149640`) found this is not a one-off: 937 same-region adjacent
sample pairs inside `mountain_chain` terrain showed max delta 680, p99 374 (i.e. present, and not
rare, even entirely inside one already-safe personality, unrelated to the variant-boundary work
above).

### Correction: this is variety-induced, not a pre-existing shared-code defect

An earlier version of this section attributed the cliff to "super-unity `perlinRidge` gain
sensitivity" in the shared `makeMountains` ridge noise (gain 1.15 > 1.0) and characterized it as
pre-existing and variety-independent. That framing had more confidence than the evidence supported
and is corrected here.

**The critical test**: the cliff at x=2646-2647 does not appear at the same coordinates and seed
without `mountainVariety` enabled. If the mechanism were purely the shared ridge noise's gain, it
should manifest regardless of variety. It doesn't.

**What actually changes with the high variant**: the high variant's parameter combination compounds
three effects that make the underlying noise much more cliff-prone:

1. `horizontalScale` narrowed by 35% at max variety (`* (1.0 - 0.35)` = `* 0.65`). In
   `makeMountains`, `scaleH = round(610 * settings.horizontalScale)`, so narrower scale means
   steeper noise gradients per block. With the test preset's `horizontalScale = 10.0`, `scaleH`
   drops from 6100 to 3965.
2. Erosion strength reduced from 0.65 to 0.40, substantially weakening the `makeFancy` smoothing
   pass that would otherwise attenuate sharp features.
3. The chain path in `Heightmap.java` passes `globalVerticalScale * settings.verticalScale` to
   `makeMountainChain`, and then `TerrainPopulator.make` applies `settings.verticalScale` again as
   `heightScale`. This double-application is present in both variety and non-variety chain paths
   (it's by design for chains to be taller), but the high variant amplifies it:
   `verticalScale = 2.2 * 1.2 = 2.64` gives a total height multiplier of roughly
   `1.3 * 2.64 * 2.64 ≈ 9.06` vs the center variant's `1.3 * 2.2 * 2.2 ≈ 6.29` — 44% taller.

These three effects are inherent to how the high variant shapes its parameters. The shared ridge
noise with gain 1.15 may contribute, but the earlier experimental evidence did not isolate it as the
root cause — Sonnet's Test 2 (single octave, no cascade) reported a 198-block jump, but the noise
scales involved (`scaleH ≈ 3965`, `globalHorizontalScale = 5.0`, effective sample spacing ≈ 0.00005
per block) make that magnitude implausible for a single octave of smooth Hermite-interpolated Perlin
noise. The experimental methodology was likely contaminated by other parts of the pipeline.

**Not yet fixed.** The variant-selection fix (one variant per terrain region, blended at edges) is
correct. The remaining problem is that the high variant's parameter combination pushes terrain into
a cliff-producing regime. Candidate directions: constrain how far `mountainVariety`'s high formula
can narrow `horizontalScale` and/or reduce erosion; or cap the total vertical amplification for
chains. Manual client visual QA is needed to assess severity before deciding on a fix direction.

## Retained local evidence

Artifacts are under `games/minecraft/investigation-state/runs/` and are ignored by Git:

| Run ID                        | Evidence                                 |
| ----------------------------- | ---------------------------------------- |
| `20260803T165742Z-0b6d656fc4` | Variety-off broad control                |
| `20260803T165806Z-be9082083d` | Maximum-variety broad scan, PR #162 seed |
| `20260803T170415Z-8ec6e6971a` | Maximum-variety broad scan, seed 12345   |
| `20260803T170432Z-1f834fe4d3` | Maximum-variety broad scan, seed 8675309 |
| `20260803T170352Z-0ddbf6575f` | Enlarged-horizontal-scale scan           |
| `20260803T165851Z-bb9556b9a6` | Amplified pre-PR-#162 negative control   |
| `20260803T165823Z-6f9539df04` | Amplified effective-PR scan              |
| `20260803T170242Z-8c37dd8534` | High-resolution pre-fix refinement       |
| `20260803T170257Z-ebac477ec7` | High-resolution post-fix refinement      |
| `20260803T170615Z-3fcaf83876` | Maximum-variety finished peak            |
| `20260803T170729Z-272d2c0dfa` | Variety-off finished peak control        |
| `20260803T193234Z-788b791115` | Taller-dimension raw scan control        |
| `20260803T193310Z-7c6250843d` | Taller-dimension finished peak control   |
| `20260803T193552Z-3e9b9659d5` | Exact-coordinate taller finished control |
| `20260803T200137Z-e9fcdf6ec7` | Fixed broad scan, PR #162 seed           |
| `20260803T200158Z-0b085dd301` | Fixed broad scan, seed 12345             |
| `20260803T200219Z-786a196145` | Fixed broad scan, seed 8675309           |
| `20260803T200316Z-cfb2f83ee8` | Fixed exact-coordinate finished control  |
| `20260803T195809Z-cff5a36840` | Fixed taller-dimension dormancy scan     |
