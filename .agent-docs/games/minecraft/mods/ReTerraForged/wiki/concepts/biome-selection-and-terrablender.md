# Biome Selection and TerraBlender

## Climate model

Minecraft selects multi-noise biomes from temperature, humidity, continentalness, erosion, depth,
weirdness, and offset. Within a vertical column, depth is the primary Y-varying coordinate; the
others are largely horizontal fields.

Climate parameter ranges are nearest-neighbor targets, not hard inclusion filters. A terminal depth
registration can continue winning below its declared point when no closer candidate exists. Merely
shortening a range does not create a lower boundary.

RTF climate mappings have these relationships:

- surface fields remain stable near terrain;
- underground depth is surface-relative and aligned with terrain depth;
- ocean and land continentalness blend across configured coast controls rather than switch at a hard
  seam; and
- erosion needed for biome selection is captured before river/climate passes overwrite the terrain
  value.

Altering a density function shared with terrain redistributes both biomes and terrain.

## Underground candidate scheduling

Vanilla-convention cave registrations are recognizable structurally by their depth/weirdness shape.
RTF retains each biome's original parameter points for entry selection and distinguishes semantic
roles such as shallow cave versus bottom-only candidate.

RTF's `UndergroundBiomeBanding` recognizes only points whose weirdness is the full `-1..1` span and
whose depth is either the vanilla underground span `0.2..0.9` or the bottom point `1.1`. It leaves
nonmatching registrations untouched and disables redistribution when fewer than two candidates are
available. This structural boundary is what permits convention-following modded cave biomes without
turning biome IDs into policy.

The dynamic depth limit is derived from `(worldDepth + min(worldHeight, 256)) / 128`. Band count
uses square-root scaling for usable vertical space and inverse Biome Size, capped at 32; underground
horizontal noise uses `0.25 * 225 / biomeSize`. A surface-relative buffer, capped at 24 blocks,
keeps scheduled cave candidates away from the terrain surface. These formulas belong together:
changing only one changes either vertical variety, horizontal footprint, or surface bleed.

Horizontal climate fitness affects the entrance to underground bands. It cannot by itself produce
vertical variety because the same horizontal inputs recur at every Y. Deeper scheduling therefore
has an explicit ownership policy; a horizontal phase field makes its transitions spatially coherent.

Unknown custom placement conventions remain on the original biome source rather than entering the
convention-based schedule.

## Runtime integration paths

There is more than one climate-sampler path:

- direct `BiomeSource` queries;
- `RandomState` sampling;
- `NoiseChunk.cachedClimateSampler()`, which fills real chunk biome palettes; and
- TerraBlender regional parameter trees and positional selection.

Generated chunk palettes use the cached chunk sampler. Direct queries and generated chunks can
therefore differ when only the direct path carries a change.

The current implementation seams are `UndergroundBiomeBanding`, `MixinMultiNoiseBiomeSourceCache`
for the plain source, `MixinParameterList` for TerraBlender's per-region trees, and the
`MixinRandomState`/`MixinNoiseChunk` sampler-context propagation. Together they form the
preset-context and layout data path.

## TerraBlender

TerraBlender selects a positional region before resolving that region's climate list. That
positional region remains the owner of underground selection; substituting the default region
changes regional biome ownership at depth.

Some integrations register parameter points into the shared list after TerraBlender captures
regional trees. RTF composes legitimate late global additions into each applicable regional tree,
including duplicates and original registrations.

When exactly one region exists, uniqueness noise has no semantic work. When multiple regions exist,
the normal positional selector remains authoritative.

## Surface-rule interaction

TerraBlender biome-region setup and surface-rule registration can share the same
`MixinParameterList` initialization seam. Successful initialization composes both behaviors within
one Overworld preset lookup; independent method-body replacement loses one behavior.

A namespaced surface-rule wrapper has equivalent behavior without dispatch only when its namespace
set is exactly the vanilla namespace. Empty, unknown, multiple, or modded sets retain TerraBlender
dispatch, including when wrappers are nested by Lithostitched.
