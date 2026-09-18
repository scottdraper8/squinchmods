# Cell, Tile, and Lookup Pipeline

`Cell` is the shared mutable state passed between terrain construction, river/hydrology, filters,
biome-adjacent sampling, previews, standalone lookup, and surface features. Adding a field is a
pipeline change, not a local data-class change.

## Field contract

The field contract consists of:

1. one clearly identified writer stage;
2. units and sentinel/default meaning;
3. `copyFrom()` propagation;
4. reset/default behavior; and
5. identified consumers that run after the writer.

Zero is unambiguous only when it means “no contribution.” An explicit `NONE` gives enums the same
property. Multiple carvers or populators touching one cell produce either defined accumulation such
as `max` or order-dependent last-writer-wins behavior.

Fields copied from another fork without a current writer or reader are dead state. Their presence
obscures pipeline ownership and suggests behavior that is not present.

## Heightmap and tile generation

`Heightmap` constructs source cell state from preset settings and seeded noise. River/hydrology and
later terrain passes may overwrite fields. Values captured before an overwrite represent source
terrain, while values captured afterward represent the later pass.

`TileGenerator` applies filters over neighborhoods and caches tiles for runtime generation. A
neighbor-dependent filter receives distinct in-bounds-present and absent/out-of-range states.
Returning an absent sentinel for an in-bounds snapshot makes a continuity pass silently accumulate
no support.

## `WorldLookup`

`WorldLookup` is the standalone/cache-miss path. Semantic equivalence with the tile path exists only
for stages reproduced there. A simplified fallback applying older coast, biome, or surface logic
creates preview/runtime disagreement.

Neighborhood-dependent evaluators have different results with a bounded sampled neighborhood and a
single-cell approximation. Cache-null paths using the full lookup retain tile-path semantics;
crashes and silent downgrades represent different behavior.

## Authority boundaries

- Direct heightmap application: source terrain and broad discovery.
- Filtered tile: exact horizontal terrain model after neighborhood filters.
- Runtime tile cache: production model state used during chunk generation.
- Finished chunk: stored biome palettes, heightmaps, structures, fluids, and blocks.

Each boundary supports claims about its own state. Direct lookup correctness does not establish that
the cached chunk sampler or surface feature received the same data.
