# Hydrology and Shore Geometry

FTF has several distinct water/coast concepts. Keeping them separate prevents a fix for one system
from distorting another.

## Hydrology fields

`cell.waterTable` and continent-scale modifiers are inputs to continental hydrology. The continent
model's hydrology function resolves the local water surface; the raw table is not a block Y.

Current uplift/wetland integration uses complex water height with:

```java
ContinentalHydrology.getComplexWaterHeight(
    cell.waterTable,
    cell.globalContinentScale,
    cell.continentSizeModifier
)
```

The resolved local water surface has a shared unit contract across river carving and shoreline
consumers. With an absolute normalized-height contract, adding global sea level produces a second
offset.

## River geometry

`UpliftRiverCarver` owns channel, bank, valley-floor, and fadeout geometry. The unwarped channel
distance and warped valley-wall distance have different purposes. Its final radii and heights are
the current geometry; similarly named fields from older carvers can have different meanings.

Normalized metadata has these derivations:

- width derives from channel/zone radii;
- depth derives from water-to-bed difference;
- bank height derives from water-to-valley-floor difference;
- alpha derives from position within the corresponding zone; and
- multiple carvers combine by explicit dominance/maximum rules.

Convert normalized height differences through `Levels.scale(...)` when the downstream contract is in
blocks.

## Wetlands versus lakes

FTF wetlands are mounded lowlands, not ordinary radial lakes. A distance-to-center shore signal is a
proxy rather than exact physical shoreline distance. Wetland morphology and shore classification are
separate stages with independent representations.

## Coastline concepts

- Main continent coast: driven by continent/control-point fields.
- Ocean floor: driven by ocean populators and `oceanDepth`.
- Archipelago shoreline/shelf: driven by island shape and island-to-ocean blend.
- River/wetland shore: driven by local hydrology and carver geometry.

These fields can meet spatially but do not share one scale or alpha. Ocean depth alone does not
define island shelf width. A beach classifier consumes source geometry and cannot make a
discontinuous source field continuous.

## Shore classification boundary

A shoreline evaluator classifies already-generated geometry and selects material; a surface feature
paints the resolved result. Geometry, classification, continuity, and painting are separate stages.

Neighbor continuity depends on the same evaluator state in tile and standalone lookup paths.
Explicit `NONE` defaults distinguish absent shore state, and stable registry IDs preserve serialized
meanings.
