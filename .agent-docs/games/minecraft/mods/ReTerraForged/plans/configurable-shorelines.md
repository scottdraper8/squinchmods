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

Registry- or data-driven modded beach materials are a separate extension. If implemented, key
weights by resource location, provide safe missing-block fallbacks, and allow biome/climate rules
without hardcoding integrations into the base evaluator.
