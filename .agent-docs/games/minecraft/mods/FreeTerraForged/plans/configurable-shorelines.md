# Configurable Shorelines

Status: implemented on `feat/configurable-shorelines` at `6368dbb`; both loaders compile and a real
Fabric server boot passed. Visual tuning and product QA remain open.

The reusable shoreline data model and its surface-material consumer are described in
[`hydrology-and-shore-geometry.md`](../wiki/concepts/hydrology-and-shore-geometry.md),
[`cell-tile-and-lookup-pipeline.md`](../wiki/concepts/cell-tile-and-lookup-pipeline.md), and
[`surface-rules-and-materials.md`](../wiki/concepts/surface-rules-and-materials.md). This plan keeps
the feature-specific integration boundary and acceptance work.

## Current integration boundary

- Preserve the current `1.21.1` uplift-river and wetland terrain implementations.
- Emit river shoreline metadata from the final river-zone geometry.
- Derive wetland water surfaces through current complex continental hydrology.
- Store absolute normalized water levels and convert normalized height deltas through active
  `Levels` scaling.
- Keep beach evaluation independent of TerraBlender biome-region selection.

## QA gate

Use same-seed before/after worlds and include:

- warm, cold, rocky, and muddy ocean coasts;
- narrow and wide uplift rivers, including mouths;
- wetlands with different mound/water shapes;
- deep and shallow ocean presets;
- chunk-border continuity;
- material frequency and abrupt neighbor transitions; and
- preview/standalone lookup versus finished-chunk surface blocks.

Specifically evaluate the known coarse river alpha gradients and wetland distance-to-center proxy. A
server boot is an integration smoke test, not visual acceptance.

## Follow-up boundary

### Modded beach materials

Registry- or data-driven modded beach materials are a separate extension. If implemented:

- Replace the fixed material set with a registry mapping resource-location IDs to surface/filler
  block-state pairs; mods register additional materials at init, default weight `0.0` unless a
  preset overrides it.
- Key palette weights by resource location (not an enum) so material selection iterates a weight map
  instead of hardcoded cumulative thresholds.
- Resolve blocks from the registry at feature-init time with a safe fallback to the vanilla entry if
  a registered material's block isn't loaded (mod removed).
- For full flexibility, support data-driven material rules (biome tags, temperature/moisture range,
  altitude band, mod-supplied predicates) as an ordered list of condition-material pairs, falling
  back to the weighted palette.
- No TerraBlender-specific integration is needed for the material system itself — beach placement
  already runs on `Cell` data during raw generation, independent of biome selection, so
  TerraBlender-added biomes get beach treatment automatically through their terrain classification
  and climate values.

### True bank/shore landform geometry

Today, river and lake shorelines are primarily a paint/coverage-and-alpha-gradient behavior layered
on top of already-computed channel/basin geometry (the "known coarse river alpha gradients and
wetland distance-to-center proxy" called out in the QA gate above) — widening a river or lake shore
control mostly widens _where paint is allowed to apply_, not the underlying terrain shape. Ocean
shoreline geometry is closer to true landform treatment since it derives from `continentEdge`/coast
terrain.

A cleaner long-term model keeps three concerns fully separate per shoreline type, and treats
river/lake shores the same way ocean coast is already treated:

- **Waterbody size** — river channel width/depth, lake basin size/depth. Unaffected by shore
  settings.
- **Shore landform width/shape** — actual terrain-height shaping outside the channel/basin edge,
  driven by its own width/falloff controls, computed upstream of painting (not fabricated by
  coverage or surface depth). Should widen or narrow visible terrain, not just paint eligibility.
- **Material painting** — coverage, surface depth, and palette, applied only inside the
  already-shaped landform band.

If this gets implemented, keep landform-width, eligibility-gate (slope/height/width/depth/bank
range), and paint-coverage controls visually and semantically distinct in the settings UI — tooltip
each control with which category it belongs to (waterbody size / landform width / paint spread /
eligibility gate) so a slider like "coverage" can't be mistaken for a width control.
