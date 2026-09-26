# Biome Selection and the Compatibility Runtime

FTF treats biome libraries, loader APIs, registries, and datapacks as input mechanisms. The
compatibility runtime extracts supported inputs, validates their lifecycle and semantics, and copies
them into immutable FTF-owned containers and typed plans. FTF then owns candidate composition,
spatial assignment, ordering, deterministic randomness, preset behavior, and final selection.

Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, structure
predicates, and other consumers use the resulting FTF plan. They do not select a library path or
inspect third-party registries, callbacks, providers, samplers, factories, namespaces, or versions.

## Mechanism generality

Compatibility is generic when an unseen content mod works because it uses a supported public
mechanism. A mod name or namespace is never a dispatch key. Named mods are falsification cases for
mechanism contracts, not members of an allowlist.

An open Java service interface is not automatically a generic compatibility contract. A provider
mechanism is usable only when it defines discovery, identity, ordering, composition, ownership,
revision, reload, removal, failure isolation, and possible-output semantics. FTF normalizes those
semantics into its own protocol; downstream consumers do not retain provider instances.

Codec serialization proves that a custom biome source can cross a data boundary, but not that its
runtime semantics are complete. An executable custom source requires either a complete immutable
snapshot or a pure request-owned factory whose registry, seed, lifecycle, ordering, concurrency, and
failure contracts are proven. FTF represents that seam as `BiomeSourcePlanInput` and
`BiomeSourcePlanInputFactory`: the input declares a stable root identity, a complete possible-output
closure, its query mode, and an owner-scoped query function. It cannot share provider or decorator
candidate semantics unless a separate normalized contract supplies them.

## Selection model

Minecraft multi-noise selection maps temperature, humidity, continentalness, erosion, depth,
weirdness, and offset to biome candidates. FTF supplies the positional climate target and resolves
the final biome through three stages:

1. one candidate-provider plan selects a provider domain and its climate candidate;
2. zero or more mechanism decorators apply normalized replacement or injection rules; and
3. one generic FTF policy resolves the final surface or underground result.

Candidate additions and removals transform the selected root table once. The provider plan names the
domain that owns that table, so peer provider domains retain their authored candidates. Decorators
receive the original candidate, current candidate, complete climate target, position, FTF
spatial-cell identity, and immutable normalized data.

Climate ranges are nearest-neighbor targets, not hard inclusion filters. A terminal depth point can
continue winning beyond its authored range when no closer candidate exists. Shortening a parameter
range does not by itself create a selection boundary.

## FTF-owned spatial map

FTF creates the spatial map used by every normalized provider and decorator:

1. `ClimateModule` applies the preset's warp and scales coordinates by `1 / biomeSize`;
2. the nearest jittered FTF cell supplies `biomeRegionX` and `biomeRegionZ`;
3. the spatial-ownership plan assigns that cell to exactly one provider domain; and
4. the provider's climate table selects the base biome for the sampled target.

TerraBlender region weights, Lithostitched regions, and Biolith replacement proportions are inputs
to this map. Their native spatial layouts do not execute as overlays after FTF selection. Increasing
FTF biome size enlarges the characteristic cell scale; warp changes cell boundaries; climate changes
the candidate selected within the owning domain; edge and region policies act on the same FTF cell
geometry.

The map is represented as immutable provider-domain and spatial-ownership containers plus a
deterministic resolver, not as a separately materialized mutable Minecraft registry. “FTF-owned
containers” is the general description; “registry” should be reserved for an actual Minecraft
registry or explicitly qualified as an internal index.

## Unified runtime authority

An FTF generator exposes one `UnifiedBiomeSource`. The selected source retained inside it is an
acquisition graph, not a second runtime path. Direct biome queries, chunk biome filling, locate,
possible-biome enumeration, feature sorting, and structure biome predicates all resolve through the
atomically published FTF plan.

Runtime selection does not intercept a plain `MultiNoiseBiomeSource`, query a mechanism wrapper, or
fall back to a vanilla generator. Mechanism finalizers may populate the acquisition graph, but they
cannot replace the FTF runtime source after normalization.

The point-query interface does not determine the execution strategy. Chunk biome filling reuses the
biome-cell identity already computed by its request-owned terrain tile. Arbitrary isolated queries
derive that identity through the lightweight biome-region path and may reuse exact owner-keyed
results. Large horizontal and three-dimensional locate operations pin one immutable plan for the
complete invocation and may resolve independent candidates concurrently only when every executed
facet declares isolated reads; result testing and selection retain vanilla order. These are generic
query-shape optimizations and do not grant any content mod downstream authority.

The final provider tables, fallback table, transformed root candidates, and every decorator's
declared outputs form the possible-biome closure. Registry-backed carver and placed-feature
execution plans compile once from that closure. The immutable decoration snapshot retains final
generation settings for every registered biome so local structure placement can decorate a biome
outside the selection closure without widening selection or feature sorting.

## Ownership and lifecycle

- A server `WorldgenEpoch` owns one selected creation graph and contribution epoch.
- A `PreviewRequest` owns one registry view, selected stem, seed, sampler context, cancellation
  state, and request-local caches.
- Resource-layer revision, `TagEpoch`, and contribution revisions independently identify acquired
  inputs and are captured into one replacement transaction.
- The plan, generation settings, and possible-biome set are replaced atomically.

No mutable compatibility state is shared across server, reload, preview, or editor owners unless a
public contract explicitly provides immutable owner-safe data. Reload captures resource, tag, and
contribution identities once, recompiles from the unchanged realized input graph, and publishes all
dependent state together. A failed or regressing capture leaves the previous state visible and
records the rejected input identities. Rejection is dimension-local; one failed owner does not stop
independent dimensions from processing the same reload.

Serial execution is the default. A plan may use parallel preview reads only when every executed
facet declares isolated parallel behavior. Otherwise the complete biome query runs through an
owner-local serial gate. Sampler contributions transform immutable target points at query time, so a
reload may replace their ordered plan stages atomically without mutating or reconstructing the
owner's climate sampler. Caches contain immutable results and include every semantic owner input in
their key.

The exact frozen registry view and selected stem are retained by the preview acquisition generation
and used by the asynchronous factory. The worker never rereads a mutable `WorldCreationContext`. One
prepared context serves terrain and biome modes, and the screen cache retains only results for the
current generation; advancing it closes the superseded prepared owner before another worker is
scheduled, canceled or older workers cannot republish stale state, and a display-only tile retains
no request key or registry graph. Preset-backed and unchanged Lithostitched multi-noise roots carry
the registry-owned candidate search index into the immutable plan rather than reconstructing it.
Surface fallback materializes a distinct exact filtered index lazily, while dispatch indexes are
compiled once into the plan. Server epoch creation is keyed by the selected
`TerraForgedChunkGenerator` root rather than the presence of an FTF density node, allowing unseen
density graphs to remain correct through full-height generation.

The screen captures the preset once per explicit input revision and lazily fingerprints that same
immutable copy. Seed, selected stem, registry view, and data configuration remain independent key
inputs. Owner, terrain-tile, and biome-sidecar producers retain subscriber cancellation state only
while running: one widget can cancel without disrupting identical work required by the other, all
subscribers cancel the producer, and terminal completion releases those requester references.
Storage and admission limits bound completed tiles, sidecars, active generation, queued requests,
and reusable arrays independently.

Spawn search is owner-scoped: preset properties are instance fields, each climate sampler publishes
one atomic search value, and preview operates on a private properties copy. Concurrent owners do not
share spawn position or search policy through process-global state.

Provider discovery and contribution publication use one owner-scoped protocol. A publication has a
stable provider identity, revision, contribution kind, ordering metadata, applicability, possible
outputs, and explicit removal or replacement behavior. A changed revision invalidates the complete
dependent plan; independent facets are not rebuilt from a mixture of epochs.

Composition distinguishes a root provider from additive contributions and ordered transforms. A root
owns one candidate domain, additive contributions merge according to declared algebra, and
transforms run once at their declared stage. Multiple roots, conflicting replacements, and cycles
produce typed capability failures unless the protocol defines an unambiguous composition rule.

## Preview boundary

The preview frontend supplies creation-graph identity, registry and tag epochs, preset, seed,
viewport, zoom, and cancellation. The backend owns request construction, exact tile-to-quart and
surface mapping, climate sampling, capability compilation, bounded caching, and scheduling. It
returns an immutable resolved biome tile plus the biome-ID/color sidecar needed for rendering.

The frontend does not initialize mods, choose a TerraBlender/Biolith/Lithostitched path, inspect
providers or samplers, or construct a plausible fallback. An unsupported applicable facet produces
one backend diagnostic and a generic unavailable preview state. An installed but unused mechanism is
absent from the plan and cannot poison preview.

## Underground selection

FTF separates underground ownership, identity, and shape:

1. ownership decides whether a three-dimensional cell may use cave candidates;
2. identity chooses among candidates valid for its depth stage; and
3. horizontal and vertical size shape both cave-owned and ordinary-background cells.

Candidate roles come from active climate registrations and supported cave tags rather than biome
namespaces. The ordinary background is the active candidate set with recognized cave registrations
removed; it performs a normal climate lookup at the underground position.

Cave ownership fades in beneath a terrain-relative protected layer. The surface envelope covers the
quart biome cell and a lateral border, keeps a hard shell, and then transitions toward configured
coverage. It protects steep walls and overhang-adjacent cells but is not a cave-connectivity test.

With vertical banding enabled, each cave-owned cell selects within its depth stage. Climate
influence controls cave identity, while coverage controls ownership. With banding disabled,
cave-owned cells delegate to the active climate registrations; coverage still controls ownership.

The final FTF underground policy executes after mechanism decorators. Surface preview uses the
corresponding provider-neutral surface policy and excludes only candidates whose underground-only
role is established by typed metadata.

## Mechanism inputs

### Minecraft registries and codecs

Public multi-noise entries provide base candidates. Registered density functions, surface rules,
carvers, generation settings, placed features, structures, pools, processors, and FTF structure
rules retain their public graph identities and executable leaves. Acquisition converts feature IDs,
structure tags, and structure-rule order into immutable plan data; generation does not query those
registries again. A registered biome holder proves identity; it does not prove that a separate
placement mechanism was captured.

Namespace is not provenance. A third-party biome registered under `minecraft` remains an ordinary
holder, and a mod namespace does not imply a special compatibility path.

### TerraBlender

FTF snapshots public Overworld region IDs, positive weights, registration order, climate tables, and
the default fallback into provider-domain containers. Only exact duplicate
`(parameter point, biome)` pairs are removed. Weighted rendezvous assigns one domain to each FTF
cell, and the selected domain's climate table chooses the candidate.

Native TerraBlender uniqueness noise does not execute on the FTF runtime path. TerraBlender supplies
candidate-domain data only and does not own final cave/surface policy or downstream execution.

### Lithostitched

For supported versions, FTF advances Lithostitched's real finalizer once at the completed pre-server
creation-graph boundary against codec-cloned dimension sources. It freezes natural code event output
through public codecs and holder keys, rejects non-repeatable output across the finalizer's
dimension invocations, and normalizes the completed result immediately.

The pre-server acquisition pass is gated by the presence of a selected FTF generator root. A graph
without one does not load compatibility-provider implementations or invoke optional mechanism
finalizers.

The immutable snapshot is bound to the creation graph and contains no biome source, generator,
registry, listener, or mutable mechanism object. Preview reads and rebinds it without invoking
callbacks. If that graph later reaches server finalization, the bridge supplies the frozen emissions
to the real finalizer instead of invoking code listeners again. Dedicated-server graphs retain the
ordinary finalization path. FTF prevents the installed wrapper and feature supplier from becoming a
second runtime authority.

Normalized semantics include additions, force, alternate-layout dispatch, partial and full
replacement, priority, load predicates, dimensions, climate and density criteria, region membership,
weights, and possible outputs. Equal priority uses injector ID as the deterministic tie-break;
regions use FTF-cell rendezvous.

Late listener registration invalidates pre-server products, seed changes rebind immutable density
declarations, and acquisition failures remain bounded capability diagnostics rather than UI crashes.
This qualified finalizer bridge is version-contained acquisition logic; downstream consumers remain
unaware of Lithostitched and RU.

### Biolith

For the qualified version, FTF copies accepted additions, removals, direct replacements, and
sub-biome registrations at the public registration boundary. Additions and removals transform the
selected root domain once. Direct replacements run later as decorators and use deterministic
FTF-cell weighted intervals with the authored replacement proportion and vanilla residual. The
selected interval and its deterministic sample remain immutable plan data for replacement-relative
sub-biome criteria.

Data-origin entries are replaced during data reload; code entries remain process-owned and exact
duplicates are removed. Preview reads immutable snapshots without consuming registration or
affecting later server startup.

For qualified built-in sub-biome criteria, acquisition copies the criterion tree into immutable
FTF-owned records. Evaluation uses only the selected provider's candidate table and target, owner
height bounds and sea level, and FTF's direct-replacement interval/sample. This preserves the
qualified center, edge, and alternate behavior after direct replacement without retaining or
invoking Biolith criteria, callbacks, placement objects, worlds, or native local noise. Unknown
custom criteria fail the applicable selection facet with a typed diagnostic instead of crossing the
ownership boundary.

No Man's Land `1.5.12` ordinary replacements and sub-biomes use the supported Biolith built-ins. Its
cave placement is a separate unsupported boundary: it patches Biolith's internal replacement return
rather than registering snapshot-visible data. FTF cannot preserve that behavior from Biolith's
public inputs and does not infer it from private locals or add a per-mod Mixin.

## Capability and failure policy

Applicability is selected-creation-graph, dimension, and facet scoped. Loader-global installation is
never sufficient to claim a facet. Providers normalize only complete supported inputs and fail
closed when a qualified version or contract changes.

An unknown behavior fails only its affected facet unless continuing would corrupt another facet.
Failures before an FTF generator and plan exist remain dependency failures. No capability failure
may silently install another source, discard a valid peer facet, or render a vanilla-only result.

An unknown executable registry leaf may still remain valid when Minecraft's public graph can execute
it unchanged. Optional analysis or adaptation for that leaf is unavailable unless its semantics are
proven; lack of an optimization must not be reported as lack of basic execution support.

## Surface-rule independence

Biome selection and surface rules are separate facets. A TerraBlender or Lithostitched selection
contract does not grant surface-rule support, and a surface-rule wrapper does not establish biome
placement semantics. The surface facet executes the selected public rule graph as-is; it does not
infer or bypass namespace dispatch from biome-selection state.

## Density extent

Each noise-fill request owns one immutable vertical extent used by both allocation and traversal.
The authoritative fallback is the complete configured noise height. No mutable or thread-local
height override may couple chunk allocation to a separate loop decision.

A bounded extent is an optional optimization derived from the finalized density-router graph. The
analyzer composes conservative, sign-aware proofs across recognized density-node semantics and
holder references, handles cycles safely, and returns full height for every unknown or unprovable
node. An extension is registered per density-function type or codec, never per content mod. A
density proof cannot clip biome sampling because density and biome selection are independent facets.

## Generator execution seams

Acquisition preserves public executable graphs, but a generator may still bypass a public method by
capturing an earlier graph or invoking a leaf directly. Compatibility audits therefore classify each
worldgen stage as delegated, captured, or bypassed. A method-only hook is not considered supported
until generated-chunk evidence proves that the active generator reaches it. A necessary adapter
belongs at the narrow stage boundary and must preserve public graph identity rather than
reconstructing mod behavior.
