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

## Rescued underground surface features

RTF can rescue a narrow family of conventional surface-search feature pipelines when their original
environment scan finds no target in an extended-height band. The original attempt keeps priority. A
rescue searches the same X/Z column, then repeats the target, block-predicate, and biome checks at
the proposed position. Unknown placement shapes and unsafe modifier orders remain unchanged.

The deterministic per-band budget is part of the density contract. Every failed original scan may
enter rescue policy, but only a scaled subset is scheduled to search; scheduled searches reuse a
run-local X/Z-column and height-band cache when possible. Consequently a policy-entry count is not a
column-search count and must never be reported as “search attempts.” Viability measurements keep
failed entries, budget skips, scheduled searches, physical scans, cache reuse, predicate checks,
discovered surfaces, and successful rescues separate.

A rescued origin must also lie behind the stable RTF terrain envelope. The guard samples a 9-by-9
neighborhood around the origin and requires at least four complete blocks between that origin and
the lowest sampled surface. Surface samples and per-column cutoffs are cached for the active run.
When the active generator does not expose the RTF terrain context, rescue is disabled rather than
guessing from a mutable heightmap.

This proves only that the placement origin is locally protected. Minecraft's generic placed-feature
contract does not expose a trustworthy maximum write footprint for arbitrary configured features, so
later blocks from a large feature can extend beyond the guarded origin. The check is not an
unbounded enclosure or cave-connectivity test.

The maximum-range Spider Nest control confirms that the mechanism addresses its intended case. In a
2,048-block-tall Overworld, repeated 64-chunk runs place roughly 2,940 rescued origins, about 1,860
above Y=256. With rescue disabled, the four affected Biomes O' Plenty decorations produce roughly
1,300 biome-filter passes and 4,100-4,200 observed block-write operations; production rescue
produces roughly 4,200 passes and 10,100-10,400 writes. Sparse windows can legitimately find almost
no eligible surfaces and do not measure global usefulness.

In the high control, all 2,948 returned rescues pass the downstream biome filter and invoke their
configured feature; 2,288 configured placements return success. The 77.6% rescue-to-placement rate
includes feature-internal rejection: corner and hanging cobwebs are effectively 100%, spider eggs
are 95.2%, and stringy cobweb is 16.8%. In the sparse control, both returned rescues become
successful configured placements.

On the same 8-by-8 chunk high control, PR #202 produces 2,261 successful configured placements
versus production's 2,288. The aggregate count changes by only 1.2%, while the exact-position probe
shows that almost all rescue columns change. Placement volume and positional parity are therefore
separate acceptance metrics.

The production rescue mechanism is acceptable as the interim implementation. Normal feature RNG and
chunk-completion order cause bounded repeat variation, but a compatibility change must remain inside
that repeatability envelope rather than systematically replacing X/Z columns. The long-term runtime
plan absorbs rescue as an owner-scoped typed placement node only after exact eligibility, density,
same-column, enclosure, downstream-success, and positional parity are proven.

The current probe's elapsed intervals include instrumentation and are not a production benchmark.
Five fresh-server production versus rescue-disabled observations with the same lightweight placement
probe show no generation-time difference above run noise. A warmed in-process benchmark and
allocation profile are still required for a tight performance bound. The focused retained runs and
counter definitions are linked from the canonical worldgen-compatibility plan.

## Dynamic ordinary ores

In a non-reference FTF Overworld, standard `minecraft:ore` and `minecraft:scattered_ore` placed
features adapt their authored vertical probability mass and expected candidate count to the live
geological frame. The mapping uses the dimension bottom, the fixed deepslate transition at Y `0..8`,
sea level, and the dimension top. A reference frame of `-64..319` with sea level `63` delegates to
the original path exactly.

Eligibility comes from the final active placed-feature graph and the feature's public contract, not
its namespace or supplying mod. A conventional modded ore can therefore participate without an
adapter. A contract is transformed only when it has:

- the standard ore or scattered-ore configured feature and `OreConfiguration`;
- one supported uniform or triangular/trapezoid height provider;
- recognized absolute, above-bottom, or below-top anchors; and
- a placement-modifier order with a safe fanout boundary before independent spatial sampling.

The transform changes only candidate Y and expected candidate multiplicity. It preserves X/Z
sampling, biome membership, decoration order, downstream filters, target-rule order, output states,
deposit size and geometry, and discard-on-air-exposure behavior. Expansion adds independent deposit
origins; it does not enlarge deposits.

Unknown height providers or position transformers, conflicting registrations, malformed frames,
unsafe filter ordering, and unregistered direct features remain unchanged. Custom configured feature
systems—including geodes, retrogen, striated formations, and other mechanisms that happen to write
ore blocks—are outside this behavior. Noise-router large ore veins are also separate.

The live plan is immutable and server-owned. It is activated only for an Overworld whose active
random state is owned by FTF; installing FTF does not alter ordinary generation in another
Overworld. Resource reload does not recreate the active worldgen registry graph, so it does not
reclassify or mutate that plan.

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
