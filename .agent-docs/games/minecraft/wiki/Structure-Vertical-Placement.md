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

In vanilla 1.21.1, Trial Chambers uses `encapsulate`, while Ancient City uses `beard_box`.
Adaptation-specific behavior therefore applies to different registered sets.

## Observable state

Sampled start Y, final piece bounds, dimension bounds, footprint heightmaps, final blocks, movement
status, and reconstructed bounds after reload each describe a different stage of structure
placement. A down-only position model also differs from dimensions where the blind start lies below
the world minimum and the valid interval is upward.
