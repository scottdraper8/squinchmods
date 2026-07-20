# Biome Climate Banding Under Deep RTF Oceans

## Status: 2026-07-19

This is the broader follow-up to the Ancient City `deep_dark` investigation in
`trial-chambers-and-ocean-structures.md`. The Ancient City symptom led to a larger question: do very
deep RTF oceans decouple physical ocean-floor depth from Minecraft's biome `depth` climate band in a
way that can suppress underground/cave biomes under oceans?

Short answer: yes, in the tested seed/presets. The measured effect is broader than Ancient Cities,
but the strongest proof is still `deep_dark` because Ancient Cities give a visible structure
symptom.

### Vanilla source used for comparison

A full decompiled/mapped vanilla 1.21.1 source tree exists locally at
`games/minecraft/reference/sources/1.21.1/official/src/net/minecraft/...` (`1.20.1`/`1.20.4`
siblings also exist). All vanilla file:line citations in this doc are read directly from that tree,
not recalled from memory — see `live-worldgen-investigation-howto.md` §7.

## Source Model

Vanilla underground biome entries in `OverworldBiomeBuilder.addUndergroundBiomes()`
(`games/minecraft/reference/sources/1.21.1/official/src/net/minecraft/world/level/biome/OverworldBiomeBuilder.java:809-826`,
`916-940`, confirmed against decompiled source — see "Vanilla source used for comparison" below):

```text
dripstone_caves: depth 0.2..0.9, continentalness 0.8..1.0
lush_caves:      depth 0.2..0.9, humidity 0.7..1.0
deep_dark:       depth point 1.1, erosion -1.0..-0.375
```

The biome `depth` axis is not "blocks below local terrain surface" in a simple sense. Confirmed at
the exact call site, `Climate.Sampler.sample()` (`.../world/level/biome/Climate.java:456-469`) is a
**raw density-function sample** — it calls `.compute()` on the registered `DEPTH` function (or a
mod's replacement) at the queried position, with no comparison against a heightmap and no
terrain-relative post-processing step anywhere in the call. `MultiNoiseBiomeSource.getNoiseBiome()`
(`.../MultiNoiseBiomeSource.java:60-65`) just forwards to `sample()` and does nearest-neighbor
lookup against registered biome parameter points. Structure biome validation
(`Structure.isValidBiome()`, `.../levelgen/structure/Structure.java:116-126`) calls the same
`getNoiseBiome()` at whatever Y `findGenerationPoint()` produced — for `JigsawStructure`
(`.../levelgen/structure/structures/JigsawStructure.java:107-126`) that is the structure's blind
`start_height`, with zero terrain awareness. This confirms, at the code level, the mechanism the
rest of this investigation and `trial-chambers-and-ocean-structures.md` already established
empirically.

### RTF's DEPTH registration (exact, verified against source)

`common/src/main/java/raccoonman/reterraforged/data/worldgen/preset/PresetNoiseRouterData.java:44-53`:

```java
int worldHeight = properties.worldHeight;
int worldDepth = properties.worldDepth;

ctx.register(NoiseRouterData.CONTINENTS, RTFDensityFunctions.cell(CellSampler.Field.CONTINENT));
ctx.register(NoiseRouterData.EROSION, RTFDensityFunctions.cell(CellSampler.Field.EROSION));
ctx.register(NoiseRouterData.RIDGES, RTFDensityFunctions.cell(CellSampler.Field.WEIRDNESS));

DensityFunction height = NoiseRouterData.registerAndWrap(ctx, HEIGHT, RTFDensityFunctions.cell(CellSampler.Field.HEIGHT));
DensityFunction offset = NoiseRouterData.registerAndWrap(ctx, NoiseRouterData.OFFSET,
    DensityFunctions.add(DensityFunctions.constant(NoiseRouterData.GLOBAL_OFFSET - 0.5F),
        DensityFunctions.mul(RTFDensityFunctions.clampToNearestUnit(height, properties.terrainScaler()), DensityFunctions.constant(2.0D))));
ctx.register(NoiseRouterData.DEPTH,
    DensityFunctions.add(DensityFunctions.yClampedGradient(-worldDepth, worldHeight, yGradientRange(-worldDepth), yGradientRange(worldHeight)), offset));
```

`yGradientRange(range) = 1.0F + (-range / 128.0F)`. `GLOBAL_OFFSET = -0.50375F` (vanilla's own
constant, reused). This registered `DEPTH` is not just a climate axis — it is reused unchanged to
build RTF's actual terrain-carving density (`initialDensity` in `overworld()`, same file lines
81-82, 100), same architecture as vanilla.

Vanilla's equivalent (`NoiseRouterData.java:133-176`):

```text
DEPTH  = yClampedGradient(-64, 320, 1.5, -1.5) + OFFSET
OFFSET = -0.50375 + spline(CONTINENTS, EROSION, RIDGES_FOLDED)     // TerrainProvider.overworldOffset
```

**Structural comparison.** Vanilla's `OFFSET` spline is a pure function of `CONTINENTS`/`EROSION`/
`RIDGES_FOLDED` — the exact same 2D density functions independently registered as the `CONTINENTS`/
`EROSION`/`RIDGES` climate axes and read directly by `Climate.Sampler`. Value and climate axis are
the same measurement family, by construction.

RTF's `offset` instead comes from `CellSampler.Field.HEIGHT` (`cell.height`,
`world/worldgen/densityfunction/CellSampler.java:125-131`), populated by RTF's own 2D procedural
macro-elevation pipeline (`Heightmap.applyTerrain()`: continent/region/mountain-chain populators
blended against ocean populators that read `oceanDepth` directly, plus hydrology) — architecturally
separate from the 3D density chain that actually carves solid/air. Critically, `cell.height` is
_also_ a separate RTF-internal field from the ones read by the other climate axes:

```text
CellSampler.Field.EROSION    -> cell.erosion    (CellSampler.java:173-178) — independent of cell.height
CellSampler.Field.WEIRDNESS  -> cell.weirdness  (CellSampler.java:180-186) — independent of cell.height
CellSampler.Field.CONTINENT  -> derived from cell.continentEdge, but branches on cell.terrain
                                 (isDeepOcean()/isShallowOcean()) and cell.height for the beach
                                 threshold (CellSampler.java:132-171) — partially height-correlated
```

So `deep_dark`'s eligibility requires **both** `depth` point 1.1 **and** `erosion` in
`-1.0..-0.375`. RTF's `depth` axis is derived from the same terrain-height field as the real ocean
floor (so it can, in principle, track floor depth), but `erosion` is a wholly independent RTF noise
field with no relationship to how deep the floor is. Under a low-floor column, whether `erosion`
also happens to land in `deep_dark`'s band is essentially an independent coincidence, not something
that co-occurs reliably with low floors. This is consistent with the extreme-preset floor-relative
data below: `lush_caves` (depth + humidity only) recovered under low-floor columns once depth
climbed back into the underground band, but `deep_dark` and `dripstone_caves` (both requiring depth
plus a second, height-unrelated axis) did not.

### Why depth itself failed to recover in the Goldilocks preset, but did in the extreme preset

`offset` is a **per-column constant** (it doesn't vary with sampled Y — only the `yClampedGradient`
term does). `ClampToNearestUnit.computeClamped()`
(`world/worldgen/densityfunction/ClampToNearestUnit.java:49-52`) just quantizes `cell.height` to a
`1/terrainScaler` grid; it is not a `[-1,1]` clamp despite the name. `terrainScaler()` defaults to
`min(worldHeight, 256)` (`WorldSettings.java:145-147`). For a deep-ocean column, `cell.height` sits
near its most negative normalized value, so `offset ≈ (GLOBAL_OFFSET - 0.5) + 2*(-1) ≈ -3.0` — a
large negative constant for that column, mirroring vanilla's own behavior of pushing `offset` very
negative under deep terrain (which is _correct_ for the terrain-density half of the shared `DEPTH`
function: it keeps that column open water/air at moderate Y).

The gradient term must climb back up from that constant to reach `depth ≈ 1.1`/`0.2..0.9`, and it
can only climb as Y decreases toward `-worldDepth` (the gradient's fixed range is
`[yGradientRange (worldHeight), yGradientRange(-worldDepth)]`, i.e. roughly `[-1.5, 1.5]` scaled by
how far `worldDepth` is from 128). In vanilla's fixed 384-block-tall world, even a maximally
negative offset still leaves generous room between any realistic ocean floor and the hard `y=-64`
floor for the gradient to recover underground/bottom depth values. **RTF's configurable `worldDepth`
breaks that guarantee**: when `oceanDepth` is pushed close to `worldDepth` (the Goldilocks preset's
`oceanDepth=117` against `worldDepth=64` is an extreme ratio), the real floor sits close to the
absolute world bottom, leaving too little remaining Y-range for the gradient term to climb back into
underground bands before running out of world. This is exactly what the measured data shows:

- Goldilocks (little room below floor): `undergroundDepth=0` at every fixed Y **and** at `floor-16`,
  `floor-64`, `floor-128` — the gradient never recovers.
- Extreme preset (`worldDepth=624`, huge room below floor even for deep columns):
  `undergroundDepth=0` at `floor-16` but `undergroundDepth=35577` out of `35641` low-floor columns
  (99.8%) by `floor-64`/ `floor-128` — the gradient recovers once there's enough room, exactly as
  the offset-plus-gradient math predicts.

This reframes the working hypothesis: RTF did **not** decouple `DEPTH` from real terrain the way a
purely cached/precomputed heightmap would. It preserved vanilla's architecture (gradient +
terrain-derived offset, reused for both climate and actual terrain density) reasonably faithfully.
The mismatch is that vanilla's fixed, shallow world height always provided enough headroom below any
realistic floor for `depth` to recover into underground bands, and RTF's configurable extreme depths
can shrink or eliminate that headroom — a scaling problem in how much below-floor room the model
needs, not a fundamentally wrong choice of what feeds `DEPTH`. Separately, `deep_dark` specifically
is further constrained by `erosion`, which has no relationship to floor depth in either vanilla or
RTF — that part of the mismatch is inherent to vanilla's biome design, not something RTF changed.

## Method

QA scanner: `MixinAncientCityDeepDarkFloorScanQA`, broadened to log biome-depth bands in addition to
Ancient City `deep_dark`/low-floor overlap.

Common parameters:

```text
seed=3216933670
center=(0,0)
radius=65536
step=512
columns=66049
low-floor threshold: approx RTF floor <= -27
Ancient City validation Y: -27
```

The scanner samples:

- Fixed absolute Y slices: `minY+4`, `minY+16`, `minY+64`, `-64`, `-48`, `-40`, `-27`, `-16`, `0`,
  `32`.
- Floor-relative slices for low-floor columns only: `floor - 16`, `floor - 64`, `floor - 128`,
  clamped to `minY + 4`.
- Strict climate-band counts: bottom-depth, underground-depth, deep-dark climate, dripstone climate,
  lush climate.
- Actual biome counts: `deep_dark`, `dripstone_caves`, `lush_caves`.

The actual biome counts are authoritative for "what biome did the source choose." The strict
climate-band counts are diagnostic; nearest-neighbor climate selection can still choose a biome even
when one axis falls just outside the ideal box.

## Goldilocks Preset Results

Preset:

```text
worldDepth=64
oceanDepth=117
seaLevel=63
minY=-64
```

Summary:

```text
columns=66049
lowFloorColumns=9712
deepDarkColumnsAtY-27=1492
deepDarkLowFloorOverlapAtY-27=0
minApproxFloor=-51
minApproxFloorAmongDeepDark=133
```

At every fixed Y slice, low-floor columns had zero bottom-depth hits, zero underground-depth hits,
and zero actual cave/underground biome hits:

```text
fixedY=-64: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-60: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-48: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-40: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-27: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-16: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=0:   lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=32:  lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
```

Floor-relative samples also had zero underground/cave biome hits:

```text
floor-16:  sampleY=-60..-43, lowFloor=9712, undergroundDepth=0, deepDarkBiome=0, dripstoneBiome=0, lushBiome=0
floor-64:  sampleY=-60..-60, lowFloor=9712, undergroundDepth=0, deepDarkBiome=0, dripstoneBiome=0, lushBiome=0
floor-128: sampleY=-60..-60, lowFloor=9712, undergroundDepth=0, deepDarkBiome=0, dripstoneBiome=0, lushBiome=0
```

Interpretation: with vanilla-depth Goldilocks, the deepest legal oceans leave very little vertical
space below the lowest ocean floors, and those low-floor columns never enter underground or bottom
biome bands in the sampled Y range. `deep_dark`, `dripstone_caves`, and `lush_caves` all exist in
the world overall, but not in the sampled low-ocean columns.

## Extreme Preset Results

Preset:

```text
worldDepth=624
oceanDepth=677
seaLevel=63
minY=-624
```

Summary:

```text
columns=66049
lowFloorColumns=35641
deepDarkColumnsAtY-27=1480
deepDarkLowFloorOverlapAtY-27=0
minApproxFloor=-592
minApproxFloorAmongDeepDark=133
```

At Ancient City's validation band and nearby vanilla-ish underground bands, low-floor columns still
had zero bottom/underground biome hits:

```text
fixedY=-64: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-48: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-40: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-27: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=-16: lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=0:   lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
fixedY=32:  lowFloor bottomDepth=0 undergroundDepth=0 deepDarkBiome=0 dripstoneBiome=0 lushBiome=0
```

Near absolute world bottom, cave/bottom biomes can exist under low-floor columns:

```text
fixedY=-620: lowFloor bottomDepth=30012 undergroundDepth=5565 deepDarkBiome=25878 dripstoneBiome=0 lushBiome=1098
fixedY=-608: lowFloor bottomDepth=28360 undergroundDepth=7098 deepDarkBiome=23902 dripstoneBiome=0 lushBiome=1376
fixedY=-560: lowFloor bottomDepth=18827 undergroundDepth=14325 deepDarkBiome=12401 dripstoneBiome=0 lushBiome=2760
```

Floor-relative samples show the key nuance:

```text
floor-16:  sampleY=-608..-43,  lowFloor=35641, undergroundDepth=0,     deepDarkBiome=0, dripstoneBiome=0, lushBiome=0
floor-64:  sampleY=-620..-91,  lowFloor=35641, undergroundDepth=35577, deepDarkBiome=0, dripstoneBiome=0, lushBiome=6028
floor-128: sampleY=-620..-155, lowFloor=35641, undergroundDepth=35577, deepDarkBiome=0, dripstoneBiome=0, lushBiome=6028
```

Interpretation: the extreme preset does not eliminate all underground biomes under oceans. It pushes
the meaningful bottom/cave bands much farther down. At `Y=-27`, Ancient City cannot see those bands.
Immediately below the local ocean floor (`floor-16`), low-floor columns still behave as non-cave
biome climate. Deeper below the floor (`floor-64`/`floor-128`), underground depth returns for nearly
all low-floor columns, but the actual cave biome selected in this sample is only `lush_caves`; no
`deep_dark` or `dripstone_caves` appears in the floor-relative low-ocean samples.

## Conclusions

1. The `deep_dark`/low-ocean clash is proven at structure-relevant Y. Both Goldilocks and extreme
   presets show zero `deep_dark` overlap with low ocean floors at `Y=-27`.
2. The broader biome-banding issue is real. Low ocean floors can be physically deep while sampling
   as surface/ocean-like on biome `depth` near the floor.
3. Goldilocks suppresses all sampled vanilla cave biomes under low ocean floors because the floor is
   near the world bottom and the biome-depth coordinate never enters cave/bottom bands there.
4. Extreme depth moves cave/bottom biome bands far below the Ancient City band. It can recover
   underground biomes near absolute bottom or far below the floor, but not in a way that helps
   Ancient Cities, and not evenly across vanilla cave biomes.
5. This should be treated as a general biome-climate compatibility issue, not only an Ancient City
   issue.

## Larger Open Question

The data above proves a mismatch in tested RTF presets. It does not yet prove the correct
replacement model.

**Update (2026-07-19): the source-reading step below is now done**, against a confirmed local
decompiled vanilla 1.21.1 tree (see "Vanilla source used for comparison" above) and RTF's actual
`PresetNoiseRouterData`/`CellSampler` code (see Source Model above, with exact file:line citations).
That reading **refutes the original hypothesis as stated** and replaces it with a narrower one:

```text
Original hypothesis (superseded): if RTF makes terrain vertically dynamic, the biome-depth climate
model may need to become relative to RTF's local terrain/floor/usable-underground range, rather than
mostly absolute world Y plus a terrain-height offset.

Refuted by: RTF's DEPTH is already architecturally terrain-relative in the same way vanilla's is
(yClampedGradient + a per-column offset derived from terrain height, reused for both the climate axis
and the actual terrain-carving density). RTF did not decouple DEPTH from terrain the way a cached,
independent heightmap sample would.

Refined hypothesis (current): the offset's magnitude for a deep-ocean column scales with how far below
"normal" the terrain height is, and the compensating yClampedGradient term can only recover from that
offset if there is enough remaining Y-range between the floor and the world's absolute bottom
(-worldDepth). Vanilla's fixed, shallow world (384 blocks) always guaranteed that headroom for any
realistic floor. RTF's configurable worldDepth/oceanDepth can shrink or eliminate that headroom when
oceanDepth is pushed close to worldDepth (proven: Goldilocks, oceanDepth=117 vs worldDepth=64, has zero
depth recovery even 128 blocks below the floor; the extreme preset, with much more room below its
floors, recovers underground depth for ~99.8% of low-floor columns by floor-64/floor-128). Separately,
deep_dark's erosion requirement is independent of floor depth in both vanilla and RTF — that part of
the mismatch is inherent to vanilla's biome design, not an RTF regression, and is not fixable by
touching DEPTH alone.
```

Remaining evidence needed before proposing a fix:

- Vanilla empirical baselines: sample normal and large-biomes vanilla worlds across fixed Y and
  floor-relative Y to confirm the same "offset can be more negative than the gradient can recover
  from within the available headroom" mechanism doesn't already occur in vanilla at its most extreme
  legal ocean/valley depths — i.e. confirm this really is a _scaling_ problem introduced by
  configurable depth, not a preexisting vanilla edge case RTF merely inherited.
- Compare RTF presets across a controlled matrix now that the mechanism is known: for a range of
  `oceanDepth`/`worldDepth` ratios, measure the minimum below-floor headroom (in blocks) needed for
  `depth` to recover into `0.2..0.9`/`1.1`, and compare that against how much headroom each preset
  actually leaves (`worldDepth - oceanDepth`, roughly).
- Determine whether changing the registered `NoiseRouterData.DEPTH` formula (e.g. capping how
  negative the terrain-height offset can get, or rescaling `yGradientRange` differently) would also
  alter terrain density in RTF, since `depth` is reused unchanged for `initialDensity`/terrain
  carving — versus whether a narrower climate-only depth adjustment (a second, climate-only
  function, diverging from the terrain-density one) is possible without vanilla-compatibility risk.
- Measure blast radius explicitly: vanilla cave biome distribution, surface biome distribution,
  Ancient City biome validation, and any TerraBlender/modded biome parameter points that use the
  `depth` axis.

The end product should not be "make Deep Dark spawn under oceans." It should be an evidence-backed
answer to whether RTF's vertical worldgen model and Minecraft's biome-depth model are semantically
aligned when world height/depth are configurable — and the answer is now more specific than before:
the architecture is aligned, but the below-floor headroom the model needs to work correctly does not
automatically scale with user-configured `oceanDepth`/`worldDepth` the way vanilla's fixed
dimensions made unnecessary to think about.

## Fix Implications

Do not jump straight to a new biome source. RTF currently preserves vanilla `MultiNoiseBiomeSource`
and feeds it RTF density functions, which is important for datapacks, TerraBlender, and modded-biome
compatibility.

The less invasive direction is to experiment with the density function feeding
`NoiseRouterData.DEPTH` so biome-depth better tracks local RTF terrain/floor in very deep oceans.
That is still risky: it can move every vanilla and modded biome that depends on the `depth` climate
axis.

Now that the mechanism is known (see Larger Open Question), the concrete levers worth prototyping
are: the offset formula in `PresetNoiseRouterData.java:52` (currently
`2 * clampToNearestUnit(height, terrainScaler)`, unbounded in how negative it can get as terrain
drops), and/or the `yGradientRange` endpoints in `PresetNoiseRouterData.java:53` (currently scaled
`1 ± range/128`, fixed regardless of how much `oceanDepth` eats into `worldDepth`). Either could be
adjusted to preserve a minimum below-floor headroom regardless of preset, but both are shared with
the terrain-density computation (`initialDensity`), so any change must be checked against surface
terrain shape, not just biome placement.

Regression tests should include:

- Vanilla `deep_dark`, `dripstone_caves`, and `lush_caves` distributions under oceans and inland.
- Ancient City acceptance at `Y=-27`.
- Floor-relative cave-biome distribution under low oceans.
- Modded/TerraBlender cave biomes that register climate-parameter points using the `depth` axis.

## Fix Design Options (2026-07-19 follow-up)

Two candidate fix directions were compared, not yet implemented or chosen. Both are legitimate; they
solve different problems.

### Option A — dynamic, formula-derived `oceanDepth` clamp (conservative)

The existing `WorldSettingsPage` clamp (`oceanDepth` max `= seaLevel + worldDepth - 10`) already
encodes the right _idea_ — cap `oceanDepth` so the floor can't get too close to the world's absolute
bottom — it just uses an arbitrary flat 10-block margin instead of one derived from the actual
`DEPTH` math. That formula is traceable in closed form:

```text
cell.height (worst case, deepest ocean column) ≈ (seaLevel - oceanDepth) / worldHeight
                                                   [Populators.java:31, via Levels.water()]
offset  = (GLOBAL_OFFSET - 0.5) + 2 * cell.height   [quantization aside]
depth(Y) = gradient(Y) + offset, gradient's slope is exactly 1/128 per block regardless of preset
```

Solving `depth(-worldDepth) >= threshold` (0.2 for any underground biome, 1.1 for `deep_dark`'s
exact point) for `oceanDepth` gives a legal-range formula that is a function of `seaLevel`,
`worldDepth`, _and_ `worldHeight` together — not a flat block count. A hand-derived version of this
formula landed close to, but not exactly matching, the observed 0%-recovery behavior at the
Goldilocks preset, because the noise blend/warp/clamp stages inside `Populators.makeDeepOcean`
(hills/canyons Perlin blend between the `lower`/`upper` bounds) shift the realized worst-case
`cell.height` by an amount not yet traced precisely by hand. A small calibration pass (a handful of
RTF-only scans across `oceanDepth`/`worldDepth`/`worldHeight` combinations — not vanilla baselines,
vanilla can't construct this config) would pin down the correction factor before hardcoding a
replacement constant.

**Effect:** preserves the current coupling — deep oceans still require deep worlds to show deep
biomes near their floor. It's a UI/validation-only change (touches `WorldSettingsPage`'s clamp
calculation, not any density function), so it carries **zero risk** to existing worlds' terrain
shape or to any biome's `depth`-axis blast radius elsewhere — it only tightens what a _new_ world
creation is allowed to configure. Lower effort, lower risk, but a real functional limitation if the
product goal is "any configured world depth should be able to show its own deep biomes."

### Option B — decoupled climate-only `depth` function (more capable, more invasive)

Confirmed directly against vanilla source: `NoiseRouter`
(`games/minecraft/reference/sources/1.21.1/official/src/net/minecraft/world/level/levelgen/NoiseRouter.java:7-23`)
is a record with **independent fields** for `depth` (read by `Climate.Sampler`, drives biome
selection) versus `initialDensityWithoutJaggedness`/`finalDensity` (drives actual terrain carving).
RTF's `PresetNoiseRouterData.overworld()` currently feeds the _same_ registered `DEPTH` density
function object into both — a design choice inherited from vanilla's own pattern (which also reuses
one `depth` function for both, for geological/climate consistency), not a structural requirement.

This means it is technically feasible to register a **second, purpose-built density function**, fed
only into `NoiseRouter.depth` (the climate slot), that is floor-relative rather than
absolute-world-Y-relative — e.g. saturating over a small fixed number of blocks below the local
floor, independent of `worldDepth`/`worldHeight`/`oceanDepth`. The existing `DEPTH` function that
feeds `initialDensity`/`finalDensity` would stay completely untouched, so **already-generated
terrain shape, cave carving, and everything currently generated is unaffected** — only what biome
_selection_ sees would change.

Two real costs, not deal-breakers but requiring deliberate handling:

- **Blast radius is biome-selection-wide, not cave-biome-only.** Every vanilla and
  TerraBlender/modded biome that registers a `depth`-axis parameter point — not just
  `deep_dark`/`dripstone_caves`/ `lush_caves` — would see the new function's values. The new
  function must still return ≈0 at the actual generated surface and negative above it, or surface
  biome selection breaks. Needs checking against the full biome parameter table, not just the three
  cave biomes this investigation has focused on.
- **Smoothness matters for `MultiNoiseBiomeSource`'s nearest-neighbor selection.** The new function
  should be built from an already-smooth 2D noise field per column (`cell.height`, as used today) —
  not from the actual post-cave/aquifer generated floor, which is noisy — to avoid patchy/jittery
  biome boundaries at chunk-to-chunk scale.

`deep_dark` specifically would still not become common under this design — its `erosion` requirement
is unchanged and remains independent of floor depth in both vanilla and RTF, so this only makes
`deep_dark` reliably _possible_ under any preset, not ubiquitous.

### Status

Neither option is implemented. Option A is the safer near-term mitigation if scoping the immediate
ocean-depth PR narrowly; Option B is the better long-term answer if the product goal is world-depth
independence for deep biomes, but is a larger, separate follow-up (new density function, biome
parameter table audit, smoothness/seam testing) — not something to fold into the current PR without
its own dedicated investigation pass.

## Raw Log Artifacts

Temporary raw logs from the final runs:

```text
/tmp/rtf-biome-bands-goldilocks-20260719.log
/tmp/rtf-biome-bands-extreme-20260719.log
```
