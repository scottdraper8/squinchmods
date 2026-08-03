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
