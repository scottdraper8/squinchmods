# Compatibility Invariants

## Preset codecs

An explicit codec default allows old presets to load when a setting is absent. A nested setting
participates in behavior only when `copy()` and every preset-construction path carry it. A
compatibility default reproduces old output; a behavior-changing default opts old presets into new
output.

Unknown fields from another fork do not imply behavioral compatibility. Two forks sharing a mod ID
and ancestry can still have incompatible preset schemas and cell models.

## Seed stability

Seed draw order is world layout. A new `Seed.next()` call before an existing draw relocates every
downstream seeded field. Isolated offset seeds leave the baseline construction sequence unchanged.

## Registry IDs and enum ordering

Appending new terrain registrations preserves existing IDs; inserting them can reinterpret stored
values. Separately, enum/category ordinal comparisons may encode dominance. Serialized ID and
logical ordering are independent compatibility dimensions.

## Mutable cell state

A `Cell` field participates consistently only when initialization, copying, reset, writer units,
reader units, and pipeline order agree. Fields copied from another fork without a current writer or
consumer are inert scaffolding that obscures compatibility.

## Loader and Minecraft version boundary

Loader-neutral worldgen logic lives in `common`; Fabric and NeoForge differences sit behind the
registration and biome-modifier abstractions. Minecraft-version API differences and internal RTF
fork divergence are separate porting dimensions, and internal divergence is often the larger one.

## Compatibility runtime ownership

The compatibility runtime is an ETL boundary. It discovers stable worldgen mechanisms, extracts
complete owner-scoped data or public executable contracts, validates them, and normalizes them into
immutable FTF-owned containers and typed plans. Once normalized, FTF owns final selection, spatial
assignment, ordering, and preset policy. TerraBlender, Lithostitched, Biolith, loader APIs, and
vanilla/datapack registries are peer inputs rather than authorities.

Registry identity, codec availability, and observed generation are distinct from extraction
completeness. A generated modded biome proves that a live pipeline can place it; it does not prove
that an isolated request can reproduce final code registrations, ordering, load predicates, weights,
noise, lifecycle, or reload semantics.

Absence of a public finalized snapshot does not prove isolated resolution is impossible. A mechanism
finalizer that can run against a supplied request-owned graph establishes feasibility, but not
automatically a production contract. Its completeness, callback purity or bounded side effects,
repeatability, exactly-once behavior, ordering, seed/noise ownership, reload behavior, and
concurrency must be proven before runtime acquisition may depend on it.

Preview, generation, diagnostics, and future consumers are zero-knowledge. They consume FTF plans
and results and never select a third-party mechanism path. Any unavoidable version-qualified
mechanism bridge remains inside runtime acquisition, normalizes immediately, and fails closed when
its proven contract changes. Private-field semantic inference, registration replay, and per-mod
consumer Mixins are not compatibility contracts.

Server-finalization bridges observe one mechanism-owned boundary after all data and code
contributions are collected and do not replay callbacks. Pre-server request resolution is a
different lifecycle and must have its own proven contract; a post-server snapshot does not establish
preset-editor availability. Any qualified early-finalization resolver remains inside acquisition,
never in the preview consumer. A snapshot is usable only when its mechanism version, dimension or
dimension type, world identity, seed, completion state, holder ownership, and possible outputs match
the FTF owner. Snapshot data is copied before publication and rebound to the request's registries
without retaining mutable source collections.

A process-global callback list is not itself a request-owned factory merely because it can mutate an
isolated generator. A qualified mechanism finalizer may be advanced at acquisition only when FTF
contains its mutation in a codec-cloned graph, freezes public outputs, proves stable ordered output
across natural repeated invocations, invalidates on late registration, and substitutes those frozen
outputs when the same graph later finalizes. Preview still never invokes callbacks. Without those
properties, the acceptable seam remains an immutable resolved snapshot or pure owner-scoped factory.

Capability applicability is creation-graph scoped. Loader-global mechanism presence cannot claim a
facet or fail a request without evidence that the selected graph contains or requires that
mechanism's contribution.

The selected generator has exactly one runtime biome authority. Vanilla direct queries, biome
location, possible-biome enumeration, feature sorting, structures, and chunk biome filling must
observe the same FTF-owned source and immutable plan. Mechanism sources remain acquisition inputs;
they must not be installed on the generator after normalization. Possible outputs are part of the
same atomically replaced runtime state as the plan so reload cannot expose mismatched query and
enumeration epochs.

Candidate composition is applied once to the selected root table. A provider plan explicitly names
the domain that owns that table. Candidate operations must not be replayed across unrelated provider
domains, and acquisition sources must never form a second runtime query path.

Registry-backed carver and placed-feature plans compile from the final possible-biome closure, not
from the earlier acquisition source. Provider candidates, fallback and composition candidates, and
declared decorator outputs all participate. These graph-dependent facets materialize once after
selection planning, while an explicit provider-owned facet replacement remains independent.

An actual pre-server request exposes contributed outputs when the mechanism has a stable
registration snapshot. A loaded mechanism with no contribution applicable to that creation graph is
absent from the plan rather than becoming an unavailable facet.

Source container encounter order is semantic only when the mechanism defines it as semantic.
Unspecified hash iteration is normalized by complete typed keys. Authored priority, target order,
weights, proportions, and explicit conflict rules remain inputs; implementation accidents do not.
Equal-priority or equal-distance decisions require a documented deterministic tie-break.

FTF tag reload and mechanism contribution reload are distinct epochs. A tag reload may rebind an
unchanged realized contribution snapshot. It must not pretend to reload a mechanism that explicitly
finalizes placement only at server start. Such a mechanism enters changed contribution data through
the next server worldgen epoch.

Two-dimensional surface placement, three-dimensional cave placement, density injection, surface
rules, carvers, features, and structures remain separate facets. Supporting one facet through a
mechanism never grants implicit support to the others.

## External worldgen wrappers

Registered density and surface functions expose one graph to RTF, datapacks, and integration mods.
Private bypasses create a second graph, which can hide wrapper defects and omit valid external
modifications.

Fast-path equivalence depends on exact preconditions such as region count, namespace set, and
registry ownership. Absence of observed modded content does not establish those preconditions.

A terrain cutoff can originate outside RTF's terrain model. In particular, worldgen modifiers loaded
through Lithostitched can wrap `minecraft:overworld/offset` with vanilla-height assumptions; Hybrid
Aquatic has produced this failure mode. The registered density graph and active wrappers therefore
explain some vanilla-derived cutoffs even when `terrainModelHeight()` and source terrain remain
valid.

## Generated-world compatibility

Changing terrain, biome scheduling, feature reach, or structure position changes new chunks.
Existing chunks retain stored data. Exact coordinate stability is a separate compatibility property
from successful old-world loading.
