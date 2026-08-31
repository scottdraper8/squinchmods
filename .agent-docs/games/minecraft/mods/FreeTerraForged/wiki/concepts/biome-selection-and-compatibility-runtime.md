# Biome Selection and the Compatibility Runtime

FTF treats biome libraries, loader APIs, registries, and datapacks as input mechanisms. The
compatibility runtime extracts supported inputs, validates their lifecycle and semantics, and copies
them into immutable FTF-owned containers and typed plans. FTF then owns candidate composition,
spatial assignment, ordering, deterministic randomness, preset behavior, and final selection.

Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, structure
predicates, and other consumers use the resulting FTF plan. They do not select a library path or
inspect third-party registries, callbacks, providers, samplers, factories, namespaces, or versions.

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

The final provider tables, fallback table, transformed root candidates, and every decorator's
declared outputs form the possible-biome closure. Registry-backed carvers and placed features
compile once from that closure. A biome introduced only through Biolith or Lithostitched therefore
retains its registered generation settings without giving those mechanisms authority over feature
execution.

## Ownership and lifecycle

- A server `WorldgenEpoch` owns one selected creation graph and contribution epoch.
- A `PreviewRequest` owns one registry view, selected stem, seed, sampler context, cancellation
  state, and request-local caches.
- A `TagEpoch` owns tag-bound recompilation.
- The plan, generation settings, and possible-biome set are replaced atomically.

No mutable compatibility state is shared across server, reload, preview, or editor owners unless a
public contract explicitly provides immutable owner-safe data. Tag reload recompiles from the same
realized contribution snapshot. Contribution reload and tag reload are separate epochs.

Serial execution is the default. A plan may use parallel preview reads only when every executed
facet declares isolated parallel behavior. Caches contain immutable results and include every
semantic owner input in their key.

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
carvers, generation settings, placed features, structures, pools, and processors retain their public
graph identities and executable leaves. A registered biome holder proves identity; it does not prove
that a separate placement mechanism was captured.

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
FTF-cell choices with the authored replacement proportion and vanilla residual.

Data-origin entries are replaced during data reload; code entries remain process-owned and exact
duplicates are removed. Preview reads immutable snapshots without consuming registration or
affecting later server startup.

Sub-biome placement remains unavailable because Biolith exposes no immutable request-owned factory
covering criterion world access, neighbor queries, alternate outputs, seed/noise, ordering, reload,
and concurrency. The runtime reports that applicable facet rather than inferring private criterion
state.

No Man's Land `1.5.12` cave placement is a separate unsupported boundary: it patches Biolith's
internal replacement return rather than registering snapshot-visible data. FTF cannot preserve that
behavior from Biolith's public inputs and does not infer it from private locals or add a per-mod
Mixin.

## Capability and failure policy

Applicability is selected-creation-graph, dimension, and facet scoped. Loader-global installation is
never sufficient to claim a facet. Providers normalize only complete supported inputs and fail
closed when a qualified version or contract changes.

An unknown behavior fails only its affected facet unless continuing would corrupt another facet.
Failures before an FTF generator and plan exist remain dependency failures. No capability failure
may silently install another source, discard a valid peer facet, or render a vanilla-only result.

## Surface-rule independence

Biome selection and surface rules are separate facets. A TerraBlender or Lithostitched selection
contract does not grant surface-rule support, and a surface-rule wrapper does not establish biome
placement semantics. The surface facet executes the selected public rule graph as-is; it does not
infer or bypass namespace dispatch from biome-selection state.
