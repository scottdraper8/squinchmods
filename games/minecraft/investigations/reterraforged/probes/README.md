# ReTerraForged investigation probe packs

These packs share the external runtime, request protocol, `ServiceLoader` registration,
`FinishedChunkSelection`, result/completeness model, scenario triggering, and overlay. They retain
different measurements:

- `biome-palette`: stored quart-biome palette and air-center distributions over configurable chunks,
  vertical bounds, steps, and bands. It replaces the useful mechanism from
  `RealChunkBiomeProfileScanner` without its fixed `(80,100)..(95,115)` region, visual targets, log
  stream, or `MinecraftServer` tick Mixin.
- `placement-telemetry`: placement invocation, sampled count, height candidate, biome-filter, and
  surviving write telemetry, keyed by feature and chunk. Its five Mixins hook the generic vanilla
  placement classes (`PlacedFeature`, `HeightRangePlacement`, `CountPlacement`, `BiomeFilter`,
  `WorldGenRegion`) and only capture events — nothing about the pack is cave-specific despite its
  origin in cave-decoration investigation; `feature_ids` selects any registered `PlacedFeature`,
  including standard ores (see `plans/ore-generation-improvements.md` for a worked example). Feature
  IDs, bounds, bands, sampling limits, and output selection are request configuration;
  finished-chunk closure comes from the shared helper.
- `reachability-census`: per-biome finished-chunk selection counts, fitness wins (surface and
  underground), competitive-strength metrics (win margin min/max/mean, strength = volume × margin),
  and classification (REACHABLE/FRAGILE/UNREACHABLE/BANDING_EXCLUDED) with registration-shape
  analysis (isVanillaConventionUnderground membership). Uses the mixin accessor to read the
  MultiNoiseBiomeSource parameter list. Enhanced in Phase 4 with margin tracking and classification
  vocabulary. Also hosts `composition-audit` (Phase 4c): structural analysis of the effective
  parameter tree — per-namespace biome/entry counts, underground convention membership, duplicate
  registration detection, finished-chunk diversity survey (surface vs underground unique biomes,
  biomes outside the parameter tree), and banding health metrics. Zero-knowledge: reports what it
  observes without mod-specific logic, making it usable across any mod stack.
- `climate-inspector`: per-coordinate climate diagnostic — samples Climate.TargetPoint axes
  alongside both finished-chunk and direct-query biomes at explicit coordinates or a grid, detecting
  finished-chunk/direct-query divergence and reporting climate axis values. Built for the biome
  correctness plan's Phase 1 investigation.
- `climate-domain`: dense-grid Climate.Sampler evaluation recording per-axis min/max/mean/percentile
  statistics and 0.005-resolution histograms, without biome selection. Includes convergence tracking
  at expanding radii to verify grid coverage captures the full axis range. Runs on both FTF and
  vanilla-control for direct comparison of climate output distributions (Phase 4a).
- `cell-cache`: RTF runtime horizontal-cell sampling and standalone parity checks from Phase 5.
- `heightmap-delta`: a genuinely new finished-chunk investigation comparing two configured heightmap
  consumers. It was authored without modifying the runtime, dispatcher, engine, or target.

Historical disposition is deliberate:

- Preserve the documented findings from the old biome divergence/profile scanners, but do not
  preserve their fixed coordinates, hardcoded screenshot context cubes, or per-scanner tick Mixins.
- Preserve cave placement event types and forced finished-chunk measurement. Do not extract the
  hardcoded Spider Nest block/biome IDs, fixed `deep/vanilla/high` cutoffs, autonomous forced-chunk
  watcher, log-only dumps, or the `ColumnSurfaceRescue` experimental implementation as generic
  runtime behavior.
- Keep `ColumnSurfaceRescue`, its classifier, and implementation-coupled QA beside the cave topic
  worktree. Their proximity to the experimental fix is useful and the reusable probe boundary does
  not prohibit it.
- Historical QA worktrees remain evidence inputs. Their redundant tick Mixins are not copied into
  any extracted pack; the shared dispatcher replaces them for current investigations.

See `games/minecraft/tooling/investigate/probe-pack-template/README.md` to author another pack.
