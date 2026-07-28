# Archipelago Rewrite Scope

## Decision

Implement one durable fix: replace the current alpha-derived archipelago placement and blending with
a cellular design whose shoreline distance is expressed in real blocks.

Do not ship the isolated `sizeNoise` warp-strength change. It modifies a code path that the rewrite
will replace, causes its own coastline relocation, and would expose worlds to two successive
generation changes without a release boundary requiring an interim fix. The tested `0.15F` to
`0.03F` experiment remains useful evidence that the existing high-frequency warp folds; it is not
production work.

The rewrite belongs in a dedicated feature PR and is not part of PR #97. PR #97 can merge first
without requiring a release before this work lands.

## Size and integration boundary

This is a medium-to-large worldgen change. The implementation is likely concentrated in
`ArchipelagoPopulator`, a new cellular-field helper, and constructor wiring in `Heightmap`, but the
risk is dominated by behavioral tuning, performance, and compatibility QA rather than file count. It
will change where every enabled archipelago can occur.

Develop the rewrite in explicit internal phases, but do not merge an intermediate implementation
that relocates islands without also delivering the distance-based shelf and stable continent
exclusion that justify the relocation.

## Required design contract

For a world coordinate, the cellular query must return:

- deterministic island-cell identity and center;
- whether that cell is selected by the density rule;
- a signed or otherwise unambiguous real-block distance to the island shoreline; and
- any per-cell size/shape value needed to preserve the intent of `islandSize`,
  `islandHorizontalScale`, and `islandDensity`.

Use carefully bounded domain warp on the cellular coordinates or shoreline metric for organic
outlines. Define the bound relative to both warp wavelength and cell scale, then verify continuity;
amplitude alone is not proof that a warped field cannot fold.

`Cell.continentDistance` is useful precedent but is not the required value. In the advanced/uplift
continent implementations it measures distance to a Voronoi cell boundary in normalized cell space
before variance and coastal shaping. It is not distance to the rendered main-continent coastline.

## Investigation and implementation sequence

1. **Build reproducible measurement tooling.** Start from the existing QA branch and the workflow in
   `live-worldgen-investigation-howto.md`. Preserve the archipelago profiler in source control
   rather than relying only on prose or transient logs. It must emit machine-comparable summaries
   for fixed seeds, presets, windows, and line profiles.
2. **Characterize current controls.** Record island count, occupied area, approximate radii,
   beach/shelf widths, terrain-type mix, and height deltas over fixed windows. Cover defaults and
   the three canonical archipelago presets. This defines behavioral intent, not coordinate
   compatibility.
3. **Prototype the cellular field in isolation.** Resolve nearest jittered cell, stable cell
   identity, density skip, size variance, and real-block shoreline distance. Compare alternative
   cellular metrics and warp strategies empirically before selecting one.
4. **Convert the island blend to distance bands.** Express shelf, coast/beach, and land transitions
   in blocks. Derive shelf-width scaling from the elevation it must cover and constrain it relative
   to island radius. Do not assume that copying `oceanDepth / DEFAULT_OCEAN_DEPTH` is sufficient;
   measure slope and usable island area across the preset matrix.
5. **Replace pointwise continent fading.** Decide island eligibility and clearance stably per island
   cell, using the real continent generator or another direct coastline query. Do not multiply every
   point by the current narrow `continentEdge` smoothstep: that would preserve Finding 3 after
   island placement becomes cellular.
6. **Port terrain shaping.** Reapply beach variance, cliffs, mountains, volcanoes, erosion,
   weirdness, and `cell.continentEdge`/terrain-type output against the new distance bands.
7. **Tune and validate the complete system.** Only after the full data path works should preset/UI
   ranges be reconsidered. Prefer retaining current serialized fields and mapping their intent onto
   the new model; any codec change requires migration and default-compatibility coverage.

## Continent exclusion acceptance rule

An island must not be partly erased by a rapidly changing per-block fade near a continent. Make the
placement decision stable for the island cell, then ensure the chosen center and radius have enough
clearance from the rendered continent coastline.

Passing `Continent` into the archipelago layer is structurally possible in `Heightmap`, but the
existing `getEdgeValue` exposes a shaped scalar rather than block distance. Candidate clearance
queries must be compared for correctness, continuity, and sampling cost before committing to an API.
A cellular island field alone does not solve this part.

## Empirical validation

Use `games/minecraft/tooling/dev-server` and the QA-mixin workflow documented in
`live-worldgen-investigation-howto.md`. Use detached worktrees pinned to exact commits for strict
before/after builds. Run with fresh worlds whenever the implementation or preset changes.

The matrix must include:

- canonical `very-deep`, Goldilocks, and `worldDepth=16` archipelago presets at seed `3216933670`;
- a default-depth/default-island-settings preset;
- several fixed windows, including the known `(230250, 163350)` area;
- direct heightmap profiles for broad deterministic measurement; and
- generated-chunk inspection for final terrain, biome, surface, fluid, and chunk-boundary outcomes.

Collect and compare:

- continuity of signed shoreline distance and final height;
- shelf width and slope in real blocks at each ocean depth;
- island count, footprint, radius distribution, and response to density/size controls;
- occurrence of adjacent-block ocean-to-peak collapses;
- whole-island continent clearance, including candidate cells near continent boundaries;
- deterministic output across repeated clean runs;
- heightmap sampling cost and real chunk-generation performance; and
- new-world terrain plus old/new chunk-boundary screenshots documenting unavoidable relocation.

Do not filter zero or otherwise uninteresting samples before aggregation. Log sample counts,
skipped/unavailable samples, minima, maxima, and distributions so apparently clean results remain
auditable. Test the profiler itself on the headless server before trusting its output.

## Acceptance criteria

- No fold or discontinuity capable of producing a one-block ocean-to-island collapse.
- Shelf slopes remain within an explicitly chosen bound across the supported ocean-depth range,
  without consuming the island interior at extreme depths.
- Islands near continents are either placed whole with adequate clearance or skipped as a whole.
- Existing island settings retain documented, monotonic, useful behavior.
- Terrain classification, climate inputs, surfaces, fluids, and generated chunks agree with the new
  height field.
- Performance impact is measured and accepted rather than assumed from similarity to continent
  generation.
- The implementation and its QA tooling are reviewable and reproducible from committed sources.

## Non-goals

- No biome climate-banding work; that has its own evidence plan.
- No attempt to preserve exact existing island coordinates.
- No temporary production patch to the outgoing simplex/warp shoreline path.
- No new island settings until a concrete missing control is demonstrated against the cellular
  prototype.
- No claim that existing worlds can cross the generation change without visible chunk boundaries.
