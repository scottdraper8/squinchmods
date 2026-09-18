# FreeTerraForged investigation probe packs

These packs share the external runtime, request protocol, `ServiceLoader` registration,
`FinishedChunkSelection`, result/completeness model, scenario triggering, and overlay. They retain
different measurements:

- `biome-palette`: stored quart-biome palette and air-center distributions over configurable chunks,
  vertical bounds, steps, and bands.
- `placement-telemetry`: placement invocation, sampled count, height candidate, biome-filter, and
  surviving write telemetry, keyed by feature and chunk. Its hooks cover generic placement classes
  (`PlacedFeature`, `HeightRangePlacement`, `CountPlacement`, `BiomeFilter`) plus the chunk-section
  write path used directly by vanilla `OreFeature` (`BulkSectionAccess` and `LevelChunkSection`). It
  only captures events — nothing about the pack is cave-specific despite its origin in
  cave-decoration investigation; `feature_ids` selects any registered `PlacedFeature`, including
  standard ores. Feature IDs, bounds, bands, sampling limits, and output selection are request
  configuration; finished-chunk closure comes from the shared helper.
- `reachability-census`: per-biome finished-chunk selection counts, fitness wins (surface and
  underground), competitive-strength metrics (win margin min/max/mean, strength = volume × margin),
  and classification (REACHABLE/FRAGILE/UNREACHABLE/BANDING_EXCLUDED) with registration-shape
  analysis (isVanillaConventionUnderground membership). Uses the mixin accessor to read the
  MultiNoiseBiomeSource parameter list. Also hosts `composition-audit`: structural analysis of the
  effective parameter tree — per-namespace biome/entry counts, underground convention membership,
  duplicate registration detection, finished-chunk diversity survey (surface vs underground unique
  biomes, biomes outside the parameter tree), and banding health metrics. Zero-knowledge: reports
  what it observes without mod-specific logic, making it usable across any mod stack.
- `climate-inspector`: per-coordinate climate diagnostic — samples Climate.TargetPoint axes
  alongside both finished-chunk and direct-query biomes at explicit coordinates or a grid, detecting
  finished-chunk/direct-query divergence and reporting climate axis values.
- `climate-domain`: dense-grid Climate.Sampler evaluation recording per-axis min/max/mean/percentile
  statistics and 0.005-resolution histograms, without biome selection. Includes convergence tracking
  at expanding radii to verify grid coverage captures the full axis range. Runs on both FTF and
  vanilla-control for direct comparison of climate output distributions.
- `cell-cache`: FTF runtime horizontal-cell sampling and standalone parity checks.
- `heightmap-delta`: finished-chunk comparison of two configured heightmap consumers.

Pack ownership boundaries:

- Fixed coordinates, screenshot context, product-specific IDs and thresholds, autonomous chunk
  watchers, and log-only dumps belong in scenarios or focused worktree evidence, not reusable packs.
- `ColumnSurfaceRescue`, its classifier, and implementation-coupled QA belong only to the cave topic
  worktree; they are not shared runtime or probe infrastructure.
- Reusable packs use the shared dispatcher and finished-chunk selection boundary rather than owning
  server tick Mixins.

See `games/minecraft/tooling/investigate/probe-pack-template/README.md` to author another pack.
