# ReTerraForged investigation probe packs

These packs share the external runtime, request protocol, `ServiceLoader` registration,
`FinishedChunkSelection`, result/completeness model, scenario triggering, and overlay. They retain
different measurements:

- `biome-palette`: stored quart-biome palette and air-center distributions over configurable chunks,
  vertical bounds, steps, and bands. It replaces the useful mechanism from
  `RealChunkBiomeProfileScanner` without its fixed `(80,100)..(95,115)` region, visual targets, log
  stream, or `MinecraftServer` tick Mixin.
- `cave-placement`: placement invocation, sampled count, height candidate, biome-filter, and
  surviving write telemetry, keyed by feature and chunk. Its five Mixins only capture events.
  Feature IDs, bounds, bands, sampling limits, and output selection are request configuration;
  finished-chunk closure comes from the shared helper.
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
