# FreeTerraForged worldgen compatibility

This is the architecture contract for future compatibility changes. Read the companion concept and
invariant documents completely:

- [Biome selection and compatibility runtime](../../../../../../games/minecraft/mods/FreeTerraForged.wiki/concepts/biome-selection-and-compatibility-runtime.md)
- [Compatibility invariants](../../../../../../games/minecraft/mods/FreeTerraForged.wiki/concepts/compatibility-invariants.md)

## Product contract

FTF is an ETL boundary for worldgen compatibility:

1. discover stable registry, resource, codec, snapshot, query, and factory inputs;
2. validate and normalize complete accepted semantics into immutable owner-scoped FTF plans; and
3. execute those plans under FTF-owned selection, spatial, ordering, lifecycle, and failure policy.

TerraBlender, Lithostitched, Biolith, loader APIs, vanilla registries, and datapacks are peer input
mechanisms. None remains a runtime authority after acquisition. Preview, generation, diagnostics,
locate, possible-biome enumeration, feature sorting, and structures know only FTF plans and typed
results.

Named third-party mods are a falsification corpus, never an allowlist. An unseen mod using a
supported mechanism must work without a code change. Applicability is selected-graph, dimension,
owner, and facet scoped; merely installing a mechanism must not claim or fail an unused facet.

Unknown or incomplete semantics fail at the narrowest sound facet with an actionable capability
diagnostic. Independent supported facets remain usable. A plausible vanilla-looking substitute is
not an acceptable failure mode.

## Ownership and publication

Each preview request or server dimension owns one immutable identity containing its seed, selected
stem and generator root, frozen registry view, data configuration, settings identity, resource and
tag revision, and mechanism contribution revision. A plan and all executable closures belong to that
identity.

Acquisition adapters may briefly hold third-party state behind an isolated provider boundary.
Published plans never retain mutable registries, event callbacks, provider instances, or mod-owned
samplers. Reload prepares a complete replacement state and atomically publishes it only after every
required invariant passes. A failed replacement leaves the previous state intact and records the
attempted revision and first cause.

Preview and server owners never share mutable mechanism state. Parallel query execution requires an
explicit immutable/isolated contract. Mechanism-owned `OWNER_SERIAL` behavior is preserved; only
FTF-synthesized immutable kernels may be upgraded to isolated parallel reads.

Resource closure is explicit and idempotent. Cache eviction prevents new leases and defers recycling
until existing borrowers release. Closing an owner cancels pending acquisition/generation, drains or
safely retires active work, drops bounded pools and caches, and severs registry/provider graphs.

## Typed plan

The plan keeps compatibility domains independent:

- biome composition and complete possible-output closure;
- candidate-provider selection;
- ordered selection decoration;
- FTF spatial ownership;
- sampler decoration and query policy;
- density settings and noise-fill extent;
- surface rule root and transforms;
- carvers;
- placed-feature schedules, compiled feature identities, and optional adaptations; and
- structures, FTF structure rules, and compiled structure-adaptation identities.

Every applicable provider must publish a plan for each claimed facet. An empty result, conflict,
wrong facet, changed protocol, missing ordering peer, failed constructor, or unsupported semantic
node becomes a bounded facet failure. Plans retain contributor order, execution mode, source shape,
possible outputs, and first-cause diagnostics.

## Selection semantics

The executable selection pipeline contains exactly one candidate-provider plan, zero or more
deterministically ordered mechanism decorators, and one generic FTF surface or underground policy.

FTF computes warped biome cells from its preset. Spatial ownership maps each cell to one provider
domain; that domain's climate table chooses the base biome. Additions/removals transform candidate
tables once. Replacement and region mechanisms receive immutable normalized position, climate, cell,
source, and ordering inputs. Mechanism decorators run before the final FTF policy.

Possible-biome closure includes provider tables, fallback tables, transformed roots, and every
declared decorator output. Carver and placed-feature execution plans compile from that closure. The
immutable decoration snapshot separately retains final generation settings for every registered
biome so structures that place against a locally selected biome remain valid without widening
selection or feature sorting.

Density and biome selection remain separate. High-altitude biome queries may be meaningful where
density is air; density bounds never clip biome sampling.

## Noise-fill contract

Generation always supports the complete intersection of configured noise height and the chunk's
generation height. This full configured-height path is the permanent correctness fallback and uses
the loader-transformed vanilla implementation for allocation, section locking, traversal,
structures, blending, and scheduler behavior.

A reduced density extent may exist only when conservative graph analysis proves equivalence after
holder resolution, visitor transformation, cache/interpolation wrappers, structures, blending, and
extension nodes. Numerical `minValue()`/`maxValue()` values alone are not a vertical proof. Cycles,
unknown functions, unresolved references, or unsupported composition return full height. Extension
is keyed by density-function type/codec, never a mod ID.

`DensityFunctions.HolderHolder` is a graph edge whose referenced value is visited. Its `.codec()`
method deliberately cannot be used and must never be dispatched.

## Mechanism contracts

### Minecraft and loader materialization

Public registries and codecs supply candidate tables, settings, density graphs, surface rules,
carvers, biome generation settings, placed features, structures, and FTF structure rules during
acquisition. Feature IDs, structure tags, and structure-rule order become immutable plan data;
generation never re-queries their registries. Fabric biome modifications and NeoForge biome
modifiers are accepted after they materialize into registered biome generation settings.
Loader/library hooks attached to public generator stages are preserved by delegating to those stages
while substituting immutable plan inputs.

Method-body-only patches that expose no complete stable snapshot remain outside the contract. They
must not be inferred from private fields or recreated by replaying registration events.

Selecting an FTF world preset retains its generator, dimension type and density settings when a
datapack declares a vanilla noise generator for the same dimension. The declaration contributes its
public biome-source graph before preview/server ownership is established. Other generator subclasses
require an explicit composition contract; silently discarding their behavior is not supported.
Creation-UI reload re-encodes selected inputs without obsolete acquired biome holders, then
reacquires the new declarations. Normal world persistence retains both selected and acquired inputs.

New FTF preset exports explicitly request `bundled_biome_domains` surface acquisition. The
contiguous bundled-mod resource suffix beneath the marker contributes complete surface roots. Public
loader metadata and known-pack identity establish origin, not content-mod names or implementation
classes. Minecraft's filtered resource stack is authoritative. User/unknown-origin roots are
replacement barriers; their shadowed payloads are not opened. Old markers without a policy keep
highest-lower `replace` semantics, and unmarked authored settings remain unchanged. When no lower
input exists, the marker's explicit vanilla fallback applies. Nested explicit inheritance descends
the stack acyclically.

Supported finite biome discriminators define domains. Higher-priority roots own overlaps; lower
roots recover otherwise missing domains. The highest root owns the default domain. Each selected
domain executes its complete authored root, including guards, order and fallback. Disjoint dispatch
prevents a null result from falling through into another root. Unknown executable nodes can remain
inside a proven finite biome guard; required unbounded opaque analysis fails rather than guessing. A
single root requires no domain analysis. Acquisition traverses known rule-child positions only,
never opaque condition or rule payloads that happen to resemble FTF markers.

Only surface behavior is imported, not companion density or dimension geometry. Referenced noise and
biome resources bind to ordinary frozen registry winners, not per-pack private registries. Immutable
provenance records resource, pack, priority, fingerprint and domain. The typed codec materializes
the root before publication and rejects actual failed acquisition snapshots when compiling the
surface facet; unrelated preview facets remain available. No resource manager, pack object or loader
callback is retained for generation. FTF strata remain a separately authored rule.

### TerraBlender

TerraBlender supplies public Overworld candidate-domain inputs. Applicability follows its public
dimension-type tag. FTF owns final cell assignment and spatial policy; native TerraBlender geometry
is not replayed downstream.

### Lithostitched

Declarative inputs are acquired from public registries, load predicates, and codecs without using
the internal finalizer bridge. Code-registered inputs require the isolated finalizer bridge because
Lithostitched does not publish a complete finalized snapshot or request-owned resolver. Mechanism
release numbers are provenance only and must never form an acceptance allowlist.

The code-listener bridge is enabled by an atomic structural check of its complete event and
finalizer seam, not by a version string. An unchanged implementation therefore works across releases
without an FTF edit. Event registration records whether the selected process has code contributions;
only then may pre-server acquisition invoke the isolated finalizer. If the inspected seam changes,
its Mixins are not partially applied and an observed code contribution receives a bounded
bridge-contract failure. Merely installing Lithostitched remains non-applicable, and declarative
extraction remains independent of that failure.

The acquisition bridge must establish purity, repeatability, ordering, owner isolation, reload, and
concurrency. Preview uses an isolated generator shell and frozen/rebound holder graph; it never
replays callbacks downstream. Add-points, force, dispatch, partial replacement, and full replacement
are accepted only from the mechanism's finalized active set or an equivalent public load-predicate
evaluation against the same immutable declaration snapshot. A false predicate is inactive; a
predicate or codec failure becomes a bounded Lithostitched facet failure. Unknown injector semantics
fail that facet.

NeoForge holder rebinding follows graph edges and canonical registry identities. Never restore or
run the stale retained NeoForge runtime override.

### Biolith

Accepted additions, removals, replacements, and supported built-in sub-biome criteria normalize to
ordered immutable decorators. Custom criteria require a complete immutable criterion contract;
otherwise only that semantic boundary fails. Biolith and Lithostitched contributions compose by
declared plan order rather than content-mod identity.

### Custom sources

A custom biome source is supported when it provides a fresh request-owned source or pure
`BiomeSourcePlanInputFactory`, complete possible outputs, canonical registry holders, and a declared
query mode. A direct custom-source root and candidate-table root are mutually exclusive. Opaque
sources without this contract fail acquisition rather than being serialized, reflected, or queried
through preview-specific special cases.

## Preview contract

One editor screen owns one immutable preset capture and one lazily enriched prepared owner per
semantic input generation. The 2D and 3D widgets share it. Navigation and render-mode changes may
reuse an owner when acquisition inputs are unchanged; preset, seed, selected dimension, datapack,
registry, tag, settings, or contribution changes advance ownership.

Cancellation is subscriber-aware: one widget cannot cancel shared work still needed by another, but
all-subscriber cancellation stops owner, tile, and sidecar construction. Completed tiles, sidecars,
pending requests, active generations, admission waiters, and pooled arrays are bounded. Eviction
never recycles a tile beneath a raster, widget, surface pass, or chunk stage lease.

Biome preview compiles only biome composition, provider selection, selection decoration, spatial
ownership, and sampler decoration. It does not materialize density, surface, carvers, placed
features, or structures. The actual world-creation UI is the authoritative lifecycle boundary;
direct resolver tests are supporting evidence only.

## Optional adaptations

Optional ore scaling, surface-feature rescue, underground enclosure, flow fields, structures, and
extended-height placement activate only from immutable plan classification and an active FTF
generator owner. Global Mixins reject non-FTF generators before registry, codec, plan, ThreadLocal,
or allocation work. Unknown pipelines execute their original public behavior unless correctness
requires a narrow explicit failure.

Canonical extended-height surface placement retains the exact modifier identity of a downward,
same-column, exact-air-to-solid scan in the compiled plan; upward, tag-defined, shifted, or unknown
pipelines remain on their original behavior. Execution does not re-encode codecs per placement. Full
configured-height generation remains the fallback regardless of these adaptations.

A non-constant `RandomOffsetPlacement` is ordinary public placement behavior, not evidence that a
feature is defective. FTF never clamps it globally. Chunk-local correction is compiled only for a
registered root with one whole-chunk scatter, otherwise position-preserving root modifiers, a
vanilla random-selector configured feature, and supported nested pipelines containing exact
horizontal offset identities. During that root's active FTF scope, nested outputs wrap modulo the
owner chunk; wrapping preserves whole-chunk density instead of piling results on an edge. Direct,
missing, conflicting, and unknown identities retain their original behavior. The contract is
selected by graph semantics, not a mod or namespace.

Modifier-free, direct built-in erosion roots in RAW_GENERATION are lowered to an owner-local
surface-column schedule. Terrain preparation must finish before neighboring decoration can paint the
chunk. Materialization retains the original configured root, radius-one biome eligibility,
feature-sort index and seed, and removes only those roots from late biome feature settings. It does
not mutate registered biome settings or globally suppress ErodeFeature. Custom subclasses, placement
modifiers, nested configured graphs and roots explicitly used in later stages retain their authored
execution. Replacement plans materialize a new schedule before atomic publication.

Underground biome protection covers the entire block footprint of a quart biome cell, including
vanilla biome smoothing and adjacent exposed faces, rather than relying only on vertical depth at
one point. The bounded terrain envelope retains the existing vertical safety/transition and
configured world ceiling. Distant prediction cannot force tile generation. Loaded-terrain and
unfiltered-prediction cache entries are distinct, owner-local, bounded, and do not retain tile
leases. The loaded query uses its owned local terrain tile's filter halo; neighboring tile load
order must not change the envelope or switch it back to unfiltered prediction at a tile boundary.

## CI qualification contract

CI qualification should cover the following behaviors against the supported exact versions:

- deterministic extraction, ordering, owner isolation, reload, cancellation, and narrow failures;
- preview/server separation and actual Fabric/NeoForge world-creation UI behavior;
- custom sources, installed-unused mechanisms, unknown nodes, provider failures, mixed stacks,
  datapack/dimension changes, independent dimensions, tall worlds, and finished chunks;
- full-height and extended-height parity, including placement and structure behavior;
- bounded result/queue/active/pool memory and collectable retired owners after GC;
- matched fresh-process current-versus-control startup, acquisition, compilation, tile generation,
  biome resolution, rasterization, noise fill, finished-chunk, allocation, and retained-heap data;
- clean shutdown with no process, cgroup member, listener, active state, or display runtime; and
- cross-loader production builds whose JARs contain no probes, sentinels, stale Mixins, deleted
  implementations, or bundled optional dependencies.

Use task-local inputs and outputs while implementing or debugging these checks, then discard them
when the active work is complete. Keep the behavior in CI/CD tests and use this document as the
current contract, not as a run archive.
