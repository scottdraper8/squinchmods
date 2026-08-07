# Archipelago Redesign

Status: planned; no implementation branch exists.

The reusable region-selection and shoreline-distance models are described in
[`terrain-shaping-and-regions.md`](../wiki/concepts/terrain-shaping-and-regions.md) and
[`hydrology-and-shore-geometry.md`](../wiki/concepts/hydrology-and-shore-geometry.md). This file
contains the feature-specific decisions and remaining work.

## Goal

Replace alpha-derived island placement and blending with a cellular design that exposes a stable
island identity and shoreline distance in real blocks. The complete change must deliver all three:

1. continuous island geometry without domain folds;
2. shelf, beach, and land widths expressed in blocks and tuned across ocean depth; and
3. stable whole-island clearance from rendered continents.

Do not ship the tested isolated warp-strength reduction. The redesign replaces that path, and an
intermediate patch would move coastlines twice without solving shelf scaling or island clipping.

## Required model

For every world coordinate, the cellular query must provide:

- deterministic island-cell identity and center;
- stable density/skip decision per cell;
- signed or otherwise unambiguous shoreline distance in blocks; and
- per-cell size/shape values preserving the intent of island size, horizontal scale, and density.

Organic warp must be bounded relative to wavelength and cell scale. `Cell.continentDistance` is
precedent, not the required answer: it is normalized distance to an underlying Voronoi boundary, not
the rendered continent coastline.

## Implementation sequence

1. Commit a reproducible profiler for current island count, area, radius, shelf width, terrain type,
   and line profiles.
2. Characterize current controls with fixed seeds and canonical presets.
3. Prototype nearest jittered-cell resolution, identity, density skip, size variance, and block
   distance independently of terrain shaping.
4. Convert shelf, beach, and land blends to distance bands. Derive shelf width from the elevation it
   must cover and constrain it relative to island radius.
5. Replace pointwise `continentFade` with one stable clearance decision per island cell.
6. Port cliffs, mountains, volcanoes, erosion, weirdness, terrain classification, and climate.
   **Constraint from `biome-fixing-plan.md` #160 fix**: the climate port must preserve island-beach
   shore-biome selection. The #160 fix removed a hardcoded `BiomeType.SAVANNA` assignment for
   `ISLAND_BEACH` cells in `ClimateModule.java` and added coast continentalness
   (`Continentalness.COAST.mid()`) for `ISLAND_BEACH` in `CellSampler.CONTINENT`. Without these,
   island beaches revert to forced savanna or receive inland continentalness that prevents shore
   biomes (beach, snowy_beach) from winning vanilla biome selection. Verify that the redesign's
   equivalent code produces coast-range continentalness and real sampled temperature/humidity for
   island shoreline terrain. **ISLAND/ISLAND_MOUNTAINS continentalness must not map to FAR_INLAND.**
   Currently these terrain types fall through to the default inland path in
   `CellSampler.CONTINENT.read()`, producing FAR_INLAND continentalness that causes cold islands to
   select continental biomes (snowy_taiga) instead of more coastal ones. The redesign should
   constrain island-interior continentalness to the COAST–NEAR_INLAND range while preserving a
   center-to-edge gradient. (Deferred from `biome-fixing-plan.md` Phase 3 as an aesthetic
   improvement that belongs in the redesign.) **Island temperature must be coherent with surrounding
   ocean.** Island temperature is currently sampled independently from surrounding ocean via
   `ClimateModule`'s biome-region center sampling. A warm island beach can directly border frozen
   ocean when a temperature zone boundary crosses the island's footprint. The redesign's climate
   port should either inherit island temperature from surrounding ocean, constrain it to within one
   band, or blend at boundaries — whichever approach falls out of the new cellular model's
   per-island identity. (Deferred from `biome-fixing-plan.md` Phase 3.) **Shelf erosion must be
   derived, not inherited from OceanPopulator.** Currently, `ArchipelagoPopulator` only sets
   `cell.erosion` for land cells (`islandAlpha >= shelfEnd`); shelf cells keep `OceanPopulator`'s
   hardcoded `-1.1F`. This value feeds into Minecraft's density functions via `CellSampler.EROSION`,
   producing maximum terrain density steepness. The -1.1 compounds the steep-wall problem (mechanism
   #2 above): the same extreme steepness is applied regardless of whether the shelf drops 30 blocks
   or 1000 blocks. Replacing -1.1 with a constant like `Erosion.LEVEL_4.mid()` (0.25) does soften
   the coastline but changes island shape unpredictably — the correct value depends on the physical
   shelf geometry. Derive shelf erosion from the actual shelf slope (vertical drop / horizontal
   distance), lerping between a steep-shelf and gentle-shelf erosion value. This belongs in the
   distance-band conversion (step 4), not as a standalone patch.
7. Tune only after the complete data path works.

## Validation

Use seed `3216933670`, the fixtures under
`games/minecraft/investigations/reterraforged/fixtures/archipelago/`, a default control, and the
known regression area around `(230250, 163350)`.

Measure:

- adjacent-sample continuity and maximum height delta;
- shelf width and slope in real blocks across ocean depths;
- island count, footprint, radius, and monotonic response to settings;
- stable whole-island continent clearance;
- preview/tile/generated-chunk agreement;
- deterministic repeated output;
- fluid, biome, surface, and chunk-boundary behavior; and
- generation and scanning cost.

## Acceptance gate

- No fold capable of a one-block ocean-to-peak collapse.
- Shelf slopes stay within an explicitly chosen bound without consuming the island interior.
- Islands near continents are accepted whole with clearance or skipped whole.
- Existing settings retain useful, documented meanings.
- Performance and old/new chunk-boundary impact are measured and accepted.
- Exact old island coordinates are not required.
- Island shoreline terrain selects shore biomes (beach, snowy_beach, stony_shore) via coast-range
  continentalness and real sampled temperature/humidity — not forced savanna (#160 regression
  guard).
- Island interior continentalness stays within COAST–NEAR_INLAND, not FAR_INLAND.
- Island temperature is coherent with surrounding ocean — no frozen_ocean directly abutting a warm
  island beach due to an independent temperature sample.
