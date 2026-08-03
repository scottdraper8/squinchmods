# Features and Structure Placement

## Placed features

A `PlacedFeature` generates candidate origins and passes them through modifiers. `BiomeFilter` and
configured-feature logic run later. Distinguish:

- candidate origin range;
- biome-filter acceptance;
- configured-feature internal validation; and
- final block writes.

A configured feature can write outside its origin Y or reject an otherwise valid origin with its own
absolute-height check. Changing an outer height provider cannot repair an internal rejection.

Vertical adaptation based on modifier semantics groups registrations by behavior rather than by
registry name. Cave decoration, ores, springs, carvers, and structures have different density and
balance meanings, so a global “scale with world height” transform changes them in different ways.

Added candidates drawn from Minecraft's main random stream perturb later decoration. Keeping the
baseline candidate on the existing stream and deriving extension decisions from isolated stable
inputs leaves later main-stream draws unchanged.

## Structures use different authorities

There is no common structure-height fix:

- some constructors hardcode a piece Y;
- some jigsaw structures sample a blind `start_height`;
- some project the start to a heightmap;
- some resample terrain during `postProcess()`;
- some search real blocks; and
- some build first, then shift a complete piece set.

The effective Y authority is the last of these mechanisms that determines or changes the final piece
position.

## On-floor versus buried extrema

For an on-floor structure, the highest relevant floor across the footprint is the conservative
anchor that leaves no sampled terrain intersecting its base.

A buried structure's valid window lies below the lowest relevant surface and above the dimension
bottom. Its extrema are opposite those of an on-floor structure and apply across the combined piece
footprint.

One anchor-column sample is insufficient for large jigsaw structures.

## Build once when inspecting real pieces

`Structure.GenerationStub` may contain a lazy builder consumer. Calling `getPiecesBuilder()`
consumes RNG and is not generally idempotent. If code builds early to inspect the actual bounding
box, return that already-built builder to vanilla rather than allowing a second build with advanced
random state.

Real piece bounds reflect datapack- or mod-altered pools, while fixed clearance estimates and a
theoretical maximum jigsaw radius do not. Local surface clearance over the real X/Z footprint can
therefore differ from clearance over the theoretical radius.

## Timing and persisted bounds

Moving blocks during `postProcess()` occurs after spawning, references, or saved structure state may
have consumed `StructureStart` and piece bounds. Moving parent and child pieces before start
finalization keeps those bounds aligned with generated blocks.

Reload reconstruction is a separate placement path. Rebuilding pieces from saved X/Z/orientation can
recreate a hardcoded anchor when the vertical offset is absent from reconstruction.

## Existing chunks

Biome palettes, placed decoration, and structures are stored in generated chunks. A logic change
affects new generation; it does not retroactively relocate or redecorate existing chunks.
