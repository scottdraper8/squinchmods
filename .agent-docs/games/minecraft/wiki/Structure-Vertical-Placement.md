# Structure Vertical Placement

Vanilla structures use several independent vertical-placement models. The effective Y authority is
the last mechanism that determines or changes final piece positions.

## Common placement models

| Model                         | Examples                                | Behavior                                                                             |
| ----------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------ |
| Fixed piece anchor            | Ocean Monument building                 | A sampled height can affect biome validation without reaching the piece constructor. |
| Blind jigsaw `start_height`   | Trial Chambers, Ancient City            | The initial structure position can be independent of generated terrain.              |
| Up-front heightmap projection | Villages, Pillager Outpost, Trail Ruins | The start follows terrain before pieces are assembled.                               |
| Late footprint resampling     | Shipwrecks, Ocean Ruins                 | `postProcess()` reads generated heightmap data and shifts local placement.           |
| Block-by-block ground search  | Buried Treasure, Ruined Portals         | Placement follows actual blocks during generation.                                   |
| Post-build global shift       | Stronghold and Mineshaft variants       | A complete piece set moves relative to sea level or sampled terrain.                 |

## Footprint extrema

An on-floor structure intersects no sampled terrain at its base when anchored to the highest
relevant floor across its footprint. Mean or median anchors can leave part of a wide base below a
high point.

A buried structure has the opposite constraint: its combined piece bounds lie below the shallowest
surface and above the dimension bottom. Large jigsaw structures can span more than a hundred blocks
from the start, making one anchor-column sample different from the full-footprint extrema.

## Lazy piece builders and random state

`Structure.GenerationStub` can contain a lazy builder consumer. `getPiecesBuilder()` consumes RNG
and is not generally idempotent. Building once and returning the resulting builder preserves the
piece set and random state; building again can create a different structure.

Real piece bounds reflect datapack- or mod-altered jigsaw pools. Fixed clearance estimates describe
only the assumed pool shape.

## Structure state and timing

`StructureStart` and piece bounds participate in spawning, references, and persistence. Movement
during `postProcess()` can occur after those consumers have read the original bounds. Movement
before start finalization keeps generated blocks and structure metadata aligned.

Reload reconstruction is another placement path. A structure rebuilt from saved X/Z/orientation can
recreate a hardcoded Y when its vertical offset is not part of reconstruction.

## Terrain adaptation

Jigsaw terrain adaptation operates around individual rigid pieces. Gaps in a large combined
structure can lie outside each individual piece's effective adaptation halo. This is distinct from
the initial start-height decision.

Heightmap projection samples the start position before the jigsaw graph is assembled. Child pieces
inherit connector-relative positions; they do not independently resample the surface. A child on
high-relief terrain can therefore retain the start's elevation while extending over a much lower
slope.

`BURY` adds density around each rigid piece's ground plane. It is neither an enclosure operation nor
a guarantee that the piece lies below the local surface. If a ground plane is suspended above the
terrain inside its positive adaptation footprint, the added density can create a visible shelf.
Evaluate this geometry per rigid piece over the actual nonzero adaptation footprint; a combined
bounding box or one sample at the structure origin does not establish safety.

Sky-visible shell cells are not, by themselves, a defect oracle for a nominally buried structure.
Some structures intentionally reach the surface. Measure the claimed failure mechanism directly,
such as ground-plane suspension or the terrain blocks introduced by adaptation, and use matched
vanilla controls to distinguish ordinary structure behavior from generator-specific amplification.

When a generator's production density uses filtered, eroded, cached, or tiled terrain data, a
one-column `ChunkGenerator#getBaseHeight` query may not represent the surface that real chunks use.
Placement validation must read the same terrain authority as production density generation.

In vanilla 1.21.1, Trial Chambers uses `encapsulate`, while Ancient City uses `beard_box`.
Adaptation-specific behavior therefore applies to different registered sets.

## Observable state

Sampled start Y, final piece bounds, dimension bounds, footprint heightmaps, final blocks, movement
status, and reconstructed bounds after reload each describe a different stage of structure
placement. A down-only position model also differs from dimensions where the blind start lies below
the world minimum and the valid interval is upward.
