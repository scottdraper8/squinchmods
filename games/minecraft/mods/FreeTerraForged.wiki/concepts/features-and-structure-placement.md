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

Fabric biome modifications and NeoForge biome modifiers are visible to FTF through the final biome
generation settings rather than through content-mod adapters. Registered custom configured-feature
and placement leaves execute through their public contracts. This keeps the mechanism generic: an
unseen mod using the loader API participates without its namespace or implementation class being
recognized by FTF.

Surface-rule libraries have a different boundary. A library such as FrozenLib that completes its
callbacks into `NoiseGeneratorSettings.surfaceRule()` before server-epoch compilation is acquired as
one composed surface graph. FTF does not retain or replay the callbacks. A hook that remains only a
late method-body patch is not graph materialization and requires a stable typed execution seam
before FTF can claim support for that facet.

Vertical adaptation based on modifier semantics groups registrations by behavior rather than by
registry name. Cave decoration, ores, springs, carvers, and structures have different density and
balance meanings, so a global “scale with world height” transform changes them in different ways.

Added candidates drawn from Minecraft's main random stream perturb later decoration. Keeping the
baseline candidate on the existing stream and deriving extension decisions from isolated stable
inputs leaves later main-stream draws unchanged.

## Cross-chunk placement

`RandomOffsetPlacement` is part of a feature's declared position transform. A variable horizontal
spread can intentionally cross the chunk containing its input position, so its presence alone does
not prove an invalid pipeline and does not authorize a global clamp.

Dense whole-chunk features can expose seams when a later offset moves an origin outside the region
that will execute or retain it. Diagnosis must distinguish candidate generation, modifier output,
biome-filter rejection, configured-feature rejection, writable-region clipping, and final block
writes.

FTF compiles a chunk-local contract only when a registered root has one whole-chunk scatter, all
other root modifiers preserve X/Z, its configured feature is a vanilla random selector, and every
nested pipeline is supported. The plan retains the exact root and nested offset object identities.
An active FTF placement wraps only those nested offsets modulo the root chunk. This preserves a
whole-chunk uniform distribution; clamping would concentrate candidates at edges. Other features,
unknown graphs, and non-FTF generators retain their original placement behavior.

## Rescued underground surface features

FTF can rescue a narrow family of conventional surface-search feature pipelines when their original
environment scan finds no target in an extended-height band. The original attempt keeps priority. A
rescue searches the same X/Z column, then repeats the target, block-predicate, and biome checks at
the proposed position. Unknown placement shapes and unsafe modifier orders remain unchanged.

The deterministic per-band budget is part of the density contract. Every failed original scan may
enter rescue policy, but only a scaled subset is scheduled to search; scheduled searches reuse a
run-local X/Z-column and height-band cache when possible. Consequently a policy-entry count is not a
column-search count and must never be reported as “search attempts.” Viability measurements keep
failed entries, budget skips, scheduled searches, physical scans, cache reuse, predicate checks,
discovered surfaces, and successful rescues separate.

A rescued origin must also lie behind the stable FTF terrain envelope. The guard samples a 9-by-9
neighborhood around the origin and requires at least four complete blocks between that origin and
the lowest sampled surface. Surface samples and per-column cutoffs are cached for the active run.
When the active generator does not expose the FTF terrain context, rescue is disabled rather than
guessing from a mutable heightmap.

This proves only that the placement origin is locally protected. Minecraft's generic placed-feature
contract does not expose a trustworthy maximum write footprint for arbitrary configured features, so
later blocks from a large feature can extend beyond the guarded origin. The check is not an
unbounded enclosure or cave-connectivity test.

Surface rescue remains an independent placed-feature policy. It may enter a compatibility plan as an
owner-scoped typed placement node only when exact eligibility, density, same-column, enclosure,
downstream-success, and positional behavior are part of the proven contract.

Validation must distinguish policy entries, budget skips, physical scans, cache reuse, biome-filter
passes, configured-feature invocation, successful placement, block writes, and exact X/Z positions.
Sparse windows do not measure global usefulness, and probe elapsed intervals are not production
benchmarks. Focused measurements belong in retained investigation artifacts.

## Dynamic ordinary ores

In a non-reference FTF generation owner, standard `minecraft:ore` and `minecraft:scattered_ore`
placed features adapt their authored vertical probability mass and expected candidate count to the
live geological frame. The mapping uses the dimension bottom, the fixed deepslate transition at Y
`0..8`, sea level, and the dimension top. A reference frame of `-64..319` with sea level `63`
delegates to the original path exactly.

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

Acquisition indexes each transform by the exact placed-feature value and its stable holder key.
Execution consumes that immutable identity index rather than querying the placed-feature registry;
missing, direct, or conflicting identity delegates to vanilla.

The live plan is immutable and server-owned. It is activated only when the active generator, random
state, vertical frame, and placed-feature occurrence belong to the same FTF owner; it does not
dispatch by a literal dimension key. Installing FTF does not alter another generator. Resource
reload captures a new owner input revision and atomically replaces the plan only after successful
reclassification.

## Structures use different authorities

FTF structure-rule order and tag-derived jigsaw adaptation identity are acquisition-time structure
plan data. A structure-generation invocation pins one immutable plan snapshot, so generation does
not query structure registries or combine rule/adaptation values from different reload epochs.

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
