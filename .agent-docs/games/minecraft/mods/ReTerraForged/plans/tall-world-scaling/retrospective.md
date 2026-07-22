# Tall-World Scaling — Retrospective

## Status: 2026-07-18

`fix/tall-world-scaling` (branch, local + `scottdraper8/ReTerraForged` remote) has been deleted. Its
closed PR (#90, "Attempted scaling fix for mountains & feature add for deeper oceans") already
reflects that the work was abandoned as a single unit. This file replaces the two earlier, much
longer investigation docs (`world-height-cutoff-investigation.md`,
`world-height-cutoff-runtime-findings.md`) — the bulk of their content described an implementation
that was later deliberately rejected; only the durable findings below survived into the branches
that actually shipped.

## What the branch split into

- **Ocean floor depth below Y=0** → `feat/configurable-ocean-depth` (PR #97). Not built on top of
  the tall-world branch's commit (`deea518`) — that commit was judged "majority throwaway" and the
  feature was rewritten from scratch. See `../ocean-depth/ocean-depth-design.md`.
- **Mountain height/shape in tall worlds** → `feat/mountain-region-variability`. Also not built on
  the tall-world branch's commit (`5e28063`, "Fix tall-world mountain scaling") — that whole
  approach (automatic tall-world projection + automatic mountain-width multipliers) was explicitly
  rejected in favor of simpler, user-facing controls (`horizontalScale`, `summitSpread`). See
  `../mountain-variability/mountain-scaling-and-summit-shaping.md`, "Incorrect Earlier Approaches."

There is no remaining "tall-world-scaling" work — both halves of the original problem are now owned
by the branches above.

## Durable findings worth keeping

- The Y≈384–448 terrain cutoff some users saw was **not** an RTF bug. It's caused by Lithostitched
  loading Hybrid Aquatic worldgen modifiers that wrap/clamp `minecraft:overworld/offset` with
  vanilla height assumptions. See `https://github.com/ETcodehome/ReTerraForged/issues/92`. If this
  resurfaces, don't re-investigate RTF's own math first — check for those two mods.
- `WorldSettings.Properties.terrainModelHeight()` (née `terrainScaler()`) intentionally returns
  `min(worldHeight, 256)`. This is a terrain-model compatibility scale — it drives normalized
  terrain cells, continent/ocean layout, biome-adjacent values, and preview rendering — not merely a
  forgotten height cap. Do not change it to track `worldHeight` directly; that was tried and caused
  layout drift (continent/ocean/biome placement all shifted).
- `cell.height` can already exceed `1.0` under ordinary preset tuning (observed `~1.68` on a
  mountain preset, mapping to roughly Y 430 in the 256-scale model). Tall mountains don't require a
  dedicated tall-world density projection — they're already possible through `verticalScale` /
  `baseScale` preset controls, which is why `feat/mountain-region-variability` could solve mountain
  character without reviving the projection machinery.
- The `OceanPopulator` hard clamp to `>= 0.0F` was a real, independent limitation — unrelated to
  mountain scaling — and is exactly what became the `oceanDepth` feature.

## Rejected approach — do not revive

The deleted branch's mountain fix built a full tall-world density projection: a private
`PresetNoiseRouterData.tallTerrainOffset()` bypass of the registered `overworld/depth` path, a
`tallTerrainHorizontalScale()` compensation threaded through every mountain populator, debug
instrumentation (`WorldHeightDebug`, gated `MixinRandomState`/`MixinNoiseBasedChunkGenerator`
probes), and a `CellSampler.HEIGHT.maxValue()` widened to `16.0`. It went through six iterations
chasing blade-like vertical mountain walls before being judged not worth the complexity and
correctness risk (private density bypasses mask, rather than expose, external wrapper bugs like the
Lithostitched case above). None of it shipped. If tall-world mountain shape becomes a problem again,
start from `mountain-scaling-and-summit-shaping.md`'s simpler model, not this one.
