# Underground Biome Climate

Minecraft's multi-noise biome source selects from temperature, humidity, continentalness, erosion,
depth, weirdness, and offset registrations. Depth is the main Y-varying coordinate; the other fields
are largely column-like.

## Nearest-neighbor registrations

Climate parameter ranges are nearest-neighbor targets rather than hard inclusion filters. A biome
registered at the deepest vanilla depth can continue winning below that point when no deeper
candidate is closer. Shortening a declared range does not create a lower boundary.

An extended-depth layout has several independent properties:

- behavior near the terrain surface;
- structural recognition of compatible underground candidates;
- distinction between shallow cave and bottom-only roles;
- vertical ownership through added depth; and
- treatment of unknown custom placement conventions.

Horizontal climate coordinates alone tend to select one winner for an entire vertical column. A
depth-owned schedule adds vertical changes, while a horizontal phase field gives those transitions
spatial coherence.

## Climate and terrain coordinates

A climate-depth offset shifts underground biome selection physically. At a depth gradient of `1/128`
per block, an offset of `0.205` corresponds to about 26 blocks.

Continentalness, humidity, and erosion can still create distribution changes after depth mapping is
correct. A hard selector between independent ocean and land climate fields creates a seam where the
fields disagree; a blended representation transitions across an interval. Terrain-relative erosion
captured before later river or climate overwrites represents a different landform state from the
overwritten value.

A terrain depth density function shared with biome climate affects both systems when stretched.

## Integration paths

Biome selection can pass through:

- direct `BiomeSource` queries;
- cached climate samplers used to fill chunk biome palettes;
- TerraBlender per-region parameter trees; and
- parameter points registered after an early regional-tree capture.

These paths can contain different parameter sets or preset context. TerraBlender selects a
positional region before resolving climate, so its regional tree remains part of deep selection.
Late global registrations affect regional selection only when they are composed into the applicable
trees.

Namespaced surface-rule dispatch has equivalent vanilla-only behavior when the namespace set is
exactly the vanilla namespace. Empty, unknown, multiple, and modded sets represent different
dispatch states.

## Stored and sampled biomes

A cold biome-source query describes direct selection for that sampler. `NoiseChunk`'s cached climate
sampler determines the biome palette written during chunk generation. The stored palette is the
authoritative biome state of a completed chunk.

Correct stored biome palettes do not imply decoration, because placed-feature candidate generation,
filters, and configured-feature logic form a later pipeline described in
[Placed-feature vertical distributions](Placed-Feature-Vertical-Distributions.md).
