# Extended-Height Worlds

Minecraft dimensions can have minimum Y, height, and generation depth values that differ from the
vanilla Overworld. Vertical values retain different meanings across these dimensions.

## Coordinate categories

| Category                     | Examples                                                    | Meaning                                                                          |
| ---------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Dynamic world bound          | maximum and minimum build height                            | A property of the active dimension.                                              |
| Normalized terrain scale     | density or cell height mapped through a compatibility scale | A model coordinate that can remain fixed while output exceeds its nominal range. |
| Sea-level-relative threshold | beaches, underwater surfaces, aquifers                      | An offset whose absolute Y changes with sea level.                               |
| Bottom/top-relative anchor   | `above_bottom`, `below_top`                                 | A coordinate expressed relative to one dimension boundary.                       |
| Intentional absolute band    | ore curves, biome identity, structure design elevation      | Content whose fixed Y contributes to its distribution or identity.               |
| Legacy hard limit            | a literal `255` acting as a build ceiling                   | A fixed coordinate standing in for a dimension property.                         |

`ChunkGenerator.getGenDepth()` is a size rather than an absolute maximum Y. Its corresponding upper
coordinate is `minY + genDepth`.

## Capped terrain models

A generator can retain a normalized terrain-model scale for preset compatibility while allowing
normalized values above `1.0`. A 256-block model with a value of `1.68`, for example, maps above
Y 400. The model scale is therefore not necessarily a terrain ceiling.

Changing a model scale affects every consumer of that model, including continent and ocean layout,
biome climate, previews, and final terrain. Height, horizontal layout, and biome identity can all
move together. Source-terrain controls for vertical scale, width, and summit character affect a
narrower part of the pipeline.

Registered density functions form the graph visible to datapacks and integration mods. A private
density-router path forms a second graph and can produce different behavior from registered worldgen
wrappers.

## System-specific vertical behavior

Added vertical volume has different effects across world-generation systems:

- Cave-decoration attempts become less dense when a fixed count spans a larger interval.
- Ore distributions remain resource-balance curves tied to their individual providers.
- Carver origins control shape frequency rather than the full set of carved blocks.
- Surface thresholds can encode sea level, biome appearance, or an absolute material band.
- Structure position can come from start height, piece constructors, heightmaps, block searches, or
  later piece movement.
- Biome climate beyond vanilla's deepest registrations follows nearest-neighbor behavior unless
  additional candidates exist.

These systems share vertical space but not a common scaling rule.

## Runtime boundaries

Different runtime artifacts expose different state:

| Boundary                        | State represented                             |
| ------------------------------- | --------------------------------------------- |
| Codec and dimension properties  | configured bounds and decoded values          |
| Density or terrain lookup       | source model output                           |
| Biome-source lookup             | selection output for one sampler path         |
| Generated chunk biome palette   | biomes stored by the chunk-generation sampler |
| Heightmaps and structure starts | generated spatial metadata                    |
| Finished blocks and fluids      | final stored world state                      |
| Client rendering                | visual and interaction behavior               |

Unavailable or incomplete chunks contain less information than completed chunks; absence of data is
not equivalent to absence of a generated feature.
