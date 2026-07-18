# Mountain Region Variability Design

## Problem

RTF mountains are uniform within a world: every mountain range shares the same parameters, producing
ranges that may use different noise algorithms (M1/M2/M3) but all have the same height envelope,
feature scale, and erosion character. Real geology produces dramatically different shapes within a
single continent — rounded Appalachians vs jagged Tetons, broad mesas vs sharp alpine peaks.

## Architecture Context

The region system works via Voronoi cells (`RegionModule`). Each cell gets one terrain type assigned
at world construction time from a weighted pool (`RegionSelector`). The three mountain algorithms —
M1 (perlinRidge), M2 (worleyEdge clustered), M3 (worleyEdge + terrace) — already go into separate
Voronoi regions via the `unmixable` list in `TerrainProvider`. `RegionLerper` handles smooth
transitions at cell borders.

Because terrain parameters are **baked into each populator at construction time**, the only way to
produce per-region parameter variety is to construct multiple instances with different parameters
and let `RegionSelector` distribute them. This is the approach.

## Design

### The slider

A single `mountainVariety` float (0.0–1.0) added to `TerrainSettings.General`. At 0.0, behavior is
identical to today. Above 0.0, each mountain algorithm type constructs 3 internal variants with
parameters spread around the user's existing settings, wrapped behind a single
`VariedMountainPopulator` pool entry. The user's settings become the **center** of the distribution;
the slider controls the spread width.

The pool stays at 3 mountain entries (one per type: M1/M2/M3), each with the original weight
unchanged. The 3 variants (low/center/high) live inside the wrapper and are selected spatially by a
Perlin noise. This preserves the `RegionSelector` weighted array length — changing it would remap
every Voronoi cell to a different populator (see Implementation Architecture below).

The slider is fully continuous, 0.0–1.0, linear mapping — same as every other float slider in the
mod. No stepping or snapping. Max spread constants per parameter are tuning decisions settled during
the visual tuning pass.

### Parameter axes

Parameters are varied **independently**, not proportionally. Scaling everything together is just
zoom — character change requires parameters to shift relative to each other.

**`verticalScale`** (user-controlled via `mountains.verticalScale`) Max spread ±20%. Height
variation reads clearly even from a distance. Tall+narrow vs short+broad are genuinely different
experiences.

**`horizontalScale`** (user-controlled via `mountains.horizontalScale`) Max spread ±35%. Controls
how compressed or spread out ridge features are. Varied independently from warp — if warp scales
with hScale it's zoom; if warp stays fixed while hScale shifts, the warp becomes more or less
dominant, which is character change.

**`baseScale`** (user-controlled via `mountains.baseScale`) Max spread ±15%. Controls base ground
height contribution. Smaller spread than the others since large baseScale swings can push mountains
below sea level or create floating terrain at extremes.

**fancyMountains erosion strength** When `fancyMountains = true`, `makeFancy()` applies a
noise-domain erosion pass. The base strength is `0.65F` (`DEFAULT_EROSION_STRENGTH`). This is
distinct from the tile-space hydraulic simulation in `WorldFilters` — it runs at noise sample time,
not as a post-process, and only affects mountain populators. With variety > 0 and fancyMountains
enabled, the strength parameter is varied per-instance so some ranges look freshly uplifted and
sharp, others heavily eroded and rounded.

`fancyMountains` stays as a boolean. Strength is a derived parameter that varies internally only
when both fancyMountains is enabled and variety > 0. No preset format change, no migration needed.

### The three variants

At `mountainVariety = v` (where v = 0.0–1.0), three variant profiles are derived from the user's
mountain settings:

| Variant                      | verticalScale | horizontalScale | baseScale     | erosionStrength |
| ---------------------------- | ------------- | --------------- | ------------- | --------------- |
| **Low** (short/wide/eroded)  | × (1 − 0.20v) | × (1 + 0.35v)   | × (1 − 0.15v) | 0.65 + 0.20v    |
| **Center** (user settings)   | unchanged     | unchanged       | unchanged     | 0.65            |
| **High** (tall/narrow/sharp) | × (1 + 0.20v) | × (1 − 0.35v)   | × (1 + 0.15v) | 0.65 − 0.25v    |

At v=1.0: low produces mountains 20% shorter, 35% wider, with heavy erosion (0.85); high produces
20% taller, 35% narrower peaks with sharp ridgelines (0.40 erosion). Center is always identical to
the unvaried baseline.

### Variant selection

Each mountain system uses the selector that fits its architecture:

**Voronoi terrain regions (TerrainProvider pool):** Uses a hash of `cell.terrainRegionId` to pick
the variant. The `terrainRegionId` is a Voronoi cell hash (float 0–1) set by `RegionModule` before
the populator runs. A decorrelated integer hash (`cellHash`) maps this to a variant index. This
gives exactly 33% of regions each variant with no spatial bias — cells near spawn have the same
distribution as cells anywhere else. No noise period to tune, no origin bias.

The hash must be decorrelated from `terrainRegionId` because `RegionSelector.get()` maps
`terrainRegionId` to a pool index via `round(identity * maxIndex)`. Values that select the same
mountain populator are in a narrow band (e.g., [0.237, 0.289]). Using the raw value for variant
selection would lock every region of the same mountain type to the same variant. The integer hash
(`Float.floatToIntBits` → multiply-shift-xor) breaks this correlation.

**Mountain chain overlay (Heightmap/Blender):** Uses a Perlin noise selector with a coordinate
offset. The chain is continuous terrain with no Voronoi cell identity, so spatial noise is the only
option. Period = `terrainRegionSize * 3` (in terrain-scaled coordinate space). The coordinate offset
(`terrainRegionSize * 1.37, terrainRegionSize * 0.89`) shifts the evaluation point away from the
Perlin grid, eliminating the structural zero at the world origin. The offset uses irrational-ish
fractions so it scales with the preset and never lands on a grid point.

The Perlin distribution still slightly favors center (~45% vs ~27% each for low/high) due to its
bell-shaped output distribution. This is acceptable for continuous terrain where sharp boundaries
would look wrong.

### What is NOT varied

**`FilterSettings` (tile-space hydraulic erosion + smoothing)** — these run as a post-process over
the entire tile and have no concept of which Voronoi region they're operating on. They are already
terrain-type-aware through `Modifier.erosionModifier()` on a per-cell basis, which is sufficient.
Varying them per-region would require restructuring the filter pipeline. Leave them alone.

**`SurfaceSettings`** — rock/dirt depth and steepness thresholds. Affects surface material, not
terrain shape. Out of scope.

**Internal noise construction params** (lacunarity, warp strength, etc.) — meaningful variation in
these would require threading new parameters through the `makeMountains*` signatures and exposing
them to users. If phase 1 (the four axes above) proves insufficient for visible character
difference, this is the next place to look. Not in scope for initial implementation.

## Compatibility

`mountainVariety` uses `optionalFieldOf` with default `0.0`. All existing presets load unchanged and
behave identically until the user adjusts the slider. The `fancyMountains` boolean codec is
untouched.

## Implementation Architecture — VariedMountainPopulator

During QA, adding 9 separate mountain entries to the populator pool (3 variants × 3 types) changed
the `RegionSelector` weighted array length. Since `RegionSelector.get()` maps `cell.terrainRegionId`
to an index via `round(identity * maxIndex)`, any change to array length remaps **every** Voronoi
cell to a different populator — shifting the entire terrain layout. Mountains became flatlands; the
Blender's erosion LERP between the (now wrong) terrain region and the mountain chain produced
Plains/Meadow biomes on 800+ block peaks.

**Fix:** `VariedMountainPopulator` wraps 3 `TerrainPopulator` variants (low/center/high) behind a
single pool entry. The pool stays at 3 mountain entries with original weights. See "Variant
selection" section above for how each system picks the active variant.

**Seed isolation:** Center instances consume seeds from the main seed (identical consumption to
variety=0). Low/high variant instances use an isolated offset seed that doesn't advance the main
counter. Downstream operations see the same seed state regardless of variety.

**Two independent mountain systems covered:**

- **Voronoi terrain regions** (`TerrainProvider` pool → `RegionSelector`): M1/M2/M3 entries wrapped
  in `VariedMountainPopulator` (cell-identity mode — no selector noise, uses hashed
  `terrainRegionId`). Offset seed: `terrainSeed.offset(713)`.
- **Mountain chain overlay** (`Heightmap.make()` → `Blender`): Single `makeMountainChain` call
  wrapped in `VariedMountainPopulator` (spatial-noise mode — Perlin selector with coordinate
  offset). Center uses `mountainSeed`, variants use `mountainSeed.offset(719)`. When
  `mountainShape > 0.8`, the Blender uses the chain exclusively — without this, variety had zero
  effect on the most prominent mountains.

**Not covered (intentionally):** `ArchipelagoPopulator` — island mountains have their own dedicated
settings (`IslandSettings`) and are not governed by the terrain mountain parameters.

## Implementation Steps

1. Add `mountainVariety` float to `TerrainSettings.General` with
   `optionalFieldOf("mountainVariety", 0.0F)` — DONE
2. Add slider to General section of `TerrainSettingsPage` — DONE
3. `Populators.makeFancy()`: accept `float erosionStrength` parameter instead of hardcoded `0.65F`;
   backward-compatible overloads for existing call sites — DONE
4. `Populators.makeMountainChain()`: add overload accepting `float erosionStrength` — DONE
5. `Populators.makeMountains()`, `makeMountains2()`, `makeMountains3()`: add overloads accepting
   `float erosionStrength` — DONE
6. `VariedMountainPopulator`: new `CellPopulator` + `WeightedPopulator` with two modes:
   cell-identity mode (hashes `cell.terrainRegionId` for variant selection) and spatial-noise mode
   (Perlin selector with coordinate offset). Delegates `apply()` to the selected variant — DONE
7. `TerrainProvider.addVariedMountains()`: when `mountainVariety > 0`, build 3 variants per type
   (low/center/high with independent parameter spread), wrap each type's 3 variants into a
   `VariedMountainPopulator` (cell-identity mode) with original weight; center uses main seed,
   low/high use `terrainSeed.offset(713)` — DONE
8. `Heightmap.make()`: when `mountainVariety > 0`, build 3 mountain chain variants with spread
   parameters, wrap in `VariedMountainPopulator` (spatial-noise mode with coordinate offset), pass
   to Blender as `mountains`; center uses `mountainSeed`, variants use `mountainSeed.offset(719)`;
   selector period = `terrainRegionSize * 3`, offset =
   `(terrainRegionSize * 1.37, terrainRegionSize * 0.89)` — DONE
9. Visual tuning pass — confirm spread constants produce meaningful differentiation at 0.25 and
   clear differentiation at 0.5

## QA Guide

### How the slider interacts with variant selection

The `mountainVariety` slider and the variant selector are independent systems:

- The **variant selector** is deterministic per world seed + coordinates. For Voronoi terrain
  regions, it's a hash of the cell identity (`terrainRegionId`). For the mountain chain, it's a
  seeded Perlin noise. Either way, the selection does NOT change when the slider value changes —
  same seed, same coords, same variant regardless of slider.
- The **slider** controls the _magnitude of spread_ between variants. At 0.5, low is 10%
  shorter/17.5% wider; at 1.0, low is 20% shorter/35% wider. The slider scales how different the
  variants are, not which one is chosen.
- The **center variant** always uses the user's unmodified settings. Since center = baseline
  regardless of slider value, any location where the selector picks center will look identical at
  variety=0, 0.5, and 1.0. This is by design, not a bug.

**Consequence for testing:** If you test the same seed at the same coordinates with variety=0, 0.5,
and 1.0, and all three look identical, the selector picked center at those coords. This does NOT
mean the feature is broken — but with the cell-hash selector, each region has only a 33% chance of
being center, so most test locations will show differences. To confirm the feature works:

1. Compare two worlds (same seed, variety=0 vs variety=1.0) at the same coordinates — 67% of
   mountain regions will show visible differences
2. If you happen to land on a center region, travel to an adjacent mountain range — it will almost
   certainly be a different variant

### Testing near spawn

Unlike the previous Perlin-only implementation, there is **no systematic center bias near spawn**.
The cell-hash selector gives uniform 33/33/33 distribution regardless of world position. You can
test at spawn and expect the same variant distribution as anywhere else.

The mountain chain (continuous terrain, Perlin-based) uses a coordinate offset that eliminates the
origin-zero bias. The value at spawn depends on the world seed — different seeds will show different
variants at the same coordinates.

### Recommended QA approach

**Use the `Mountain Variety QA` preset** in the `[TEST] RTF Fabric 1.21.1 - Mouta` profile. It has
`terrainRegionSize: 800`, `mountainVariety: 1.0`, high mountain weight, and small continents.

**Binary "does it work?" test:**

1. Create world A with the QA preset (variety=1.0 baked in)
2. Create world B with the same seed and a copy of the QA preset with `mountainVariety: 0.0`
3. Fly to the same coords in both — most mountain regions will show visible height, width, and biome
   label differences

**Same-seed cross-instance test (key minutia):** When comparing the same seed at the same
coordinates across instances with different variety levels:

- The same VARIANT is always selected (the selector is seed+location-dependent, not
  slider-dependent)
- At variety=0 there is no VariedMountainPopulator — the base populator runs directly
- At variety=0.5 and variety=1.0, the same variant is selected, but with different magnitudes
- If the selected variant is center: all three instances look identical (center = baseline)
- If the selected variant is low: variety=0.5 and variety=1.0 look different from variety=0 AND from
  each other (0.5 has half the spread of 1.0)
- If the selected variant is high: same logic as low

**What to look for:**

- **Height**: High variant is 20% taller, low variant is 20% shorter than the no-variety world at
  the same peaks
- **Peak width**: High variant is 35% narrower (tighter spires), low variant is 35% wider (broader
  ridges)
- **Biome labels**: Jagged Peaks / Frozen Peaks (high variant, erosion 0.40) vs Meadow / Stony Peaks
  (low variant, erosion 0.85) at peaks that would otherwise be the same biome
- **Erosion character**: With `fancyMountains: true`, high variant peaks look sharper, low variant
  looks more weathered

**"Does the variety feel good?" test:**

- Fly in a straight line across the variety=1.0 world. Different Voronoi regions will have different
  mountain character — some tall and sharp, some broad and eroded, some unchanged. Within a few
  regions you should encounter visibly different ranges.

**Within-seed vs cross-seed testing:**

- **Within a single seed**: Travel between mountain ranges. Different Voronoi cells will have
  different variants. The mountain chain variant changes spatially based on the Perlin selector
  (period = `terrainRegionSize * 3`).
- **Cross-seed**: Different seeds produce different variant assignments everywhere. Two seeds with
  the same variety level will have different distributions of low/center/high across their mountain
  regions.

## Files Modified

| File                           | Changes                                                                                                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TerrainSettings.java`         | Added `mountainVariety` field to `General` inner class (codec, constructor, copy)                                                                                    |
| `RTFTranslationKeys.java`      | Added `GUI_SLIDER_MOUNTAIN_VARIETY` key                                                                                                                              |
| `en_us.json`                   | Added slider label and tooltip strings                                                                                                                               |
| `TerrainSettingsPage.java`     | Added `mountainVariety` slider widget (0.0–1.0)                                                                                                                      |
| `Populators.java`              | Added `DEFAULT_EROSION_STRENGTH` constant; erosionStrength overloads for `makeFancy`, `makeMountains`, `makeMountains2`, `makeMountains3`, `makeMountainChain`       |
| `VariedMountainPopulator.java` | New class: `CellPopulator` + `WeightedPopulator` wrapper with dual-mode variant selection (cell-identity hash for Voronoi regions, Perlin+offset for mountain chain) |
| `TerrainProvider.java`         | Added `addVariedMountains()` with spread constants; variety branch in `generateTerrain()`; uses cell-identity mode VariedMountainPopulator (no selector noise)       |
| `Heightmap.java`               | Added mountain chain variety branch in `make()` with `VariedMountainPopulator` (spatial-noise mode, Perlin selector with coordinate offset)                          |
| `Presets.java`                 | Updated all 8 `General` constructor calls with `mountainVariety` parameter                                                                                           |
