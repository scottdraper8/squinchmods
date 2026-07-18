# RTF Tall-World Height Investigation Caveat

## Status As Of 2026-06-25

This document supersedes the older agentic investigation notes for the `fix/tall-world-scaling`
branch. The original investigation mixed together two different issues:

- a real external-mod cutoff caused by Lithostitched loading Hybrid Aquatic worldgen modifiers that
  wrap/clamp `minecraft:overworld/offset` with vanilla height assumptions
- an RTF/preset design question about how tall-world mountain relief should look when `worldHeight`
  is much larger than the 256-block terrain model

The first issue is not an RTF tall-world math bug. See
`https://github.com/ETcodehome/ReTerraForged/issues/92`.

The useful RTF insight is narrower: RTF intentionally keeps a capped terrain model scale,
historically `min(worldHeight, 256)`. That model drives normalized terrain cells, continent/ocean
layout, biome-adjacent values, previews, and many preset expectations. Changing that model scale
directly causes layout drift and should not be treated as a simple tall-world fix.

## Useful Findings To Keep

- `WorldSettings.Properties.terrainScaler()` returning `min(worldHeight, 256)` is intentional
  compatibility behavior, not merely a forgotten cap.
- `cell.height` can exceed `1.0`; mountain presets can already produce terrain above the base 256
  model. A target column observed during testing had `cell.height ~= 1.68`, which naturally maps to
  about Y 430 in the 256 model.
- Tall mountains are possible through preset tuning. The issue is whether their vertical relief
  should be projected into extra world height automatically or by an explicit preset option.
- `OceanPopulator` clamping ocean heights to `>= 0.0F` is a real limitation for below-zero ocean
  floors. That is separate from mountain scaling and can be kept as an ocean-depth feature.
- `CellSampler.HEIGHT.maxValue()` declaring `1.0` while real heights exceed that is a correctness
  risk if tall-projection density functions rely on declared ranges.

## Findings To Discard Or Treat As Historical Only

- The Y 384 cutoff should not be described as generally caused by Vanilla Backport or RTF's base
  tall-world math. The known cutoff case is Hybrid Aquatic plus Lithostitched.
- The branch's private tall-world density path is not a good fix. It bypasses the registered
  `minecraft:overworld/depth` / `minecraft:overworld/offset` path and can mask external wrapper bugs
  instead of exposing them.
- Setting every tall-world chunk's max height to full `worldHeight` is a performance regression.
  Dynamic max-height should remain per chunk and should estimate projected terrain height, not
  blindly scan the full vertical range.
- Automatic horizontal scaling derived from world height or projection slope is too opinionated for
  default RTF behavior.

## Current Plan

No salvage plan survives from the original `agent-ref/` notes. Re-derive it from the "Useful
Findings To Keep" / "Findings To Discard" sections above and from
`world-height-cutoff-runtime-findings.md` in this same folder before doing further
tall-world-scaling work.
