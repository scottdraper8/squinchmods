# FreeTerraForged compatibility-runtime completion plan

This plan defines the remaining work required to make the compatibility runtime mechanism-generic,
owner-safe, and empirically complete. Read it together with `worldgen-compatibility.md`, which is
the authoritative product and architecture contract. This document is forward-facing: retained run
artifacts contain measurements and observations; this plan contains objectives, dependencies,
decisions, and acceptance gates.

## Completion standard

Correctness and completeness are the only completion metrics. Calendar time, implementation size,
and convenience do not justify weakening an ownership boundary, retaining a known-bad path, guessing
at third-party semantics, or accepting incomplete evidence. Once implementation is authorized, work
continues autonomously through every workstream and acceptance gate. An intermediate diagnosis,
prototype, passing unit suite, single-loader run, or locally plausible result is not completion.

This is a pre-release internal refactor. Preserve compatibility for previously valid preset inputs,
including omitted-field defaults and every preset construction/copy path. Do not preserve an
internal Java API, plan representation, cache, Mixin seam, provider ABI, serialized internal runtime
object, class layout, or historical pre-release generation behavior merely because it already
exists. Replace unsound ownership and lifecycle models in place, delete obsolete paths, and update
their tests and diagnostics. Do not layer a second abstraction over bad code.

The user has authorized autonomous implementation of this plan through its program completion gate.
Commit and push authority is separate from implementation authority; do not commit or push plan or
production changes without an explicit instruction.

## Current acceptance posture

The production design uses full-height request-owned noise extents, metadata-first providers, typed
contribution algebra, transactional owner revisions, request-owned custom-source inputs,
version-gated acquisition Mixins, public TerraBlender dimension-type applicability, graph-owned
generator stages, executable owner-serial query gates, query-time sampler transforms, exact preview
registry/stem ownership, generator-root epoch detection, and diagnostic optional adaptations.
Plan/capability diagnostics use schema version 3 and include the independent resource revision.
Common source tests and both production loaders must remain green as this state is refined.

Density-function visitors must preserve holder/reference nodes as graph edges. In vanilla 1.21.1,
`DensityFunctions.HolderHolder.codec()` deliberately throws; its referenced value is the semantic
node and is already visited by `mapAll`. Type recognition, seed rebinding, and acquisition may
inspect the visited value, but must never attempt codec dispatch on the holder edge.

Program completion is still gated on the runtime matrix below. Do not launch another Minecraft
process while retained Fabric JVMs `54343` or `91098` remain in uninterruptible kernel teardown;
their presence makes cleanup and lifecycle evidence invalid. Continue source, unit, build, artifact,
documentation, and acquisition gates meanwhile. Once the host is healthy, rerun every affected
Fabric/C2ME, reload, mixed-stack, packaged-start, custom-source, and finished-chunk scenario and
retain its clean teardown state. A source-complete implementation is not a substitute for those
runtime gates.

In particular, the healthy-host matrix must execute the real client world-creation preview path, not
only source-level negotiator tests. With the current RU/Lithostitched artifacts it must prepare and
regenerate a preview, cancel work, change selected dimensions and datapacks, then create a server
from the previewed graph. It must also exercise current-source custom-source factories, owner-serial
sampler stages under concurrent queries, positive and negative generator-root ownership, independent
multi-dimension reload publication, installed-unused mechanisms, bounded bad-provider and
unknown-injector failures, tall-world C2ME generation, and packaged starts with optional mechanisms
absent and with the supported mixed stack present.

## Program shape

Maintain all nine workstreams in this one dependency-ordered plan, but execute one coherent vertical
slice at a time. Complete its source investigation, contract, implementation, deletion of superseded
paths, tests, deterministic runtime probes, reload/concurrency gates, loader coverage, and
production artifact inspection before advancing. Shared probe infrastructure may be built when the
active workstream needs it; production changes for later workstreams must not be started
opportunistically.

The dependency order is:

1. evidence and diagnostic foundation;
2. noise-fill correctness and gated density-extent analysis;
3. capability-provider protocol and discovery;
4. composable contribution algebra;
5. owner-scoped lifecycle and revision publication;
6. request-owned custom biome-source acquisition;
7. mechanism-adapter generalization;
8. generator-stage execution seam preservation; and
9. optional semantic adaptations.

Later source evidence may prove that two adjacent workstreams require one atomic refactor. That is
allowed only when their ownership or lifecycle contracts cannot be separated soundly. Record the
dependency in this plan before combining them; do not use grouping to avoid independent acceptance
gates.

## Global invariants

Every workstream must preserve these conditions:

- FTF is the only runtime authority after acquisition. Third-party mechanisms are input peers.
- Preview, generation, diagnostics, locate, feature sorting, structures, and other consumers remain
  zero-knowledge.
- Registry and codec graphs, immutable public snapshots, and pure owner-scoped factories are
  preferred. Qualified implementation bridges remain acquisition-only and normalize immediately.
- Applicability is selected-creation-graph, dimension, owner, and facet scoped. Installed-unused
  mechanisms do not claim or fail a facet.
- Unknown semantics fail closed at the narrowest sound boundary. They never produce a plausible
  vanilla-looking substitute.
- An unseen mod using a supported mechanism works without FTF changes. Extension is by stable
  mechanism or registered function type, never by content-mod identity or namespace.
- Immutable plan state, possible outputs, generation settings, revisions, and execution policy are
  published atomically.
- Preview and server owners never share mutable mechanism state. Parallel reads require an explicit
  isolated-parallel contract.
- Density bounds never clip biome sampling. Biome selection and density remain independent facets.
- Previously valid presets continue to decode and construct complete settings. Compatibility is not
  required for superseded internal runtime representations.

## Evidence rules shared by all workstreams

For each behavior-bearing change:

1. Establish the live upstream, branch, dependency, loader, and source truth before implementation.
2. Inspect source or bytecode for every external lifecycle or semantic conclusion.
3. Construct the smallest deterministic probe that distinguishes the proposed contract from the old
   behavior and from a plausible false positive.
4. Retain exact source tree, dirty patch, dependency hashes, configuration, seed, commands, logs,
   calculations, outputs, cleanup state, and run ID.
5. Prove negative controls: installed-unused, unknown type, changed version, failed acquisition,
   reload, cancellation, and conflicting contribution where applicable.
6. Prove deterministic repeat and owner isolation before enabling parallel reads.
7. Compare normalized plans or generated results across Fabric and NeoForge where both loaders
   expose the mechanism.
8. Generate real tiles or finished chunks when a graph probe cannot establish execution parity.
9. Run clean production builds and inspect the final JARs for probes, development sentinels, stale
   Mixins, deleted implementations, and accidentally bundled optional dependencies.
10. Exercise client-only acquisition and cache ownership through the actual world-creation UI;
    directly invoking a resolver or compiler in a source test is supporting evidence, not runtime
    proof of preview lifecycle behavior.

Named mods are falsification cases, not the proof of generality. Every mechanism claim also needs a
synthetic or otherwise independent case that uses the same contract without relying on a known
content-mod name.

## Workstream 1: evidence and diagnostic foundation

### Evidence-foundation objective

Make every later conclusion reproducible against the current runtime. Diagnostics must consume the
same immutable plans as production and must not require serialization of a deliberately
non-serializable runtime root.

### Evidence-foundation investigation

- Inventory all compatibility probes, fixtures, scenario templates, development overlays, and
  production diagnostics against current public signatures and plan ownership.
- Identify probes that call removed resolver overloads, inspect mechanism state directly, serialize
  `UnifiedBiomeSource`, depend on a stale worktree, or conflate registered content with executable
  plan content.
- Establish comparable baselines for vanilla/default height, the 2,048-block preset, C2ME and
  non-C2ME, Fabric and NeoForge, reload, structures, blending, and representative mechanism stacks.
- Define authoritative timing boundaries. Separate process startup, datapack construction, plan
  acquisition, tile generation, noise fill, biome selection, and full finished-chunk latency.

### Evidence-foundation implementation

- Repair or replace stale probes instead of adding compatibility overloads to production solely for
  diagnostics.
- Give diagnostics typed plan-report access for source shape, provider order, contribution order,
  lifecycle revision, possible outputs, query mode, density extent, fallback reason, and executable
  graph census.
- Add synthetic fixtures for a custom biome source, two additive providers, a provider discovery
  failure, a late contribution revision, an unknown Biolith criterion, an unknown Lithostitched
  injector, a custom density function, and a generator-method wrapper.
- Keep probe payload and scenario-only code outside production artifacts.

### Evidence-foundation completion gates

- The complete common and investigation-tool test suites pass from a clean current-tip worktree.
- Every retained active scenario uses current production signatures and completes cleanup.
- A full-domain Wilder Wild/FrozenLib run completes without the stale resolver or runtime-source
  serialization failures.
- Probe output identifies unsupported mechanisms by owner, facet, provider, node/type, and first
  cause without exposing third-party objects to consumers.
- Production Fabric and NeoForge JARs contain no probe classes, sentinels, or scenario resources.

## Workstream 2: noise-fill correctness and gated density-extent analysis

### Noise-fill objective

Restore vanilla-authoritative full configured-height noise generation, remove the current split
allocation/traversal clipping state, and establish one immutable request-owned extent contract. A
bounded optimizer is optional and may ship only if its proof is complete and its measured benefit
justifies the complexity.

### Phase A: correctness baseline

- Remove the `fillFromNoise` height redirect, `NoiseChunk.cellCountY` mutation, `MaxHeightUtil`
  coupling, structure-iterator consumption, and any thread-local or transient state used to make
  allocation and traversal disagree with vanilla.
- Introduce a typed immutable noise-fill extent owned by the generation request or equivalent
  execution owner. Initially it always represents the complete intersection of configured noise
  height and chunk generation height.
- Derive allocation bounds, traversal bounds, interpolation cell counts, minimum cell Y, and section
  access from the same extent instance. Reject an extent that is misaligned with the configured cell
  height or lies outside the authoritative generation range.
- Keep density extent out of biome preview and biome sampling. High-altitude biomes remain
  meaningful even where density is air.

### Phase A acceptance

- No noise-fill code consults an FTF terrain tile height or structure maximum to reduce configured
  generation height.
- Vanilla and FTF generate the complete configured vertical range without array/traversal mismatch.
- Fabric and NeoForge pass default-height and 2,048-height finished-chunk generation, with and
  without C2ME, under repeated parallel scheduling.
- Save/reload, datapack reload, tag reload, blending against old chunks, structure terrain
  adaptation, aquifers, caves, and boundary chunks complete without exceptions or missing blocks.
- Allocation and loop probes report the identical immutable extent for every request.

### Phase B: analyzer feasibility study

Do not begin with an implementation assumption. Produce a complete inventory and proof algebra for
the finalized router actually evaluated after holder resolution, `RandomState` visitor mapping,
noise instantiation, interpolation/cache wrapping, blending, aquifer setup, and structure
beardification.

The inventory must cover every vanilla 1.21.1 density-function type, FTF's registered `noise`,
`cell`, `clamp_to_nearest_unit`, and `linear_spline` types, marker/cache wrappers, holder/reference
nodes, and live third-party custom types in the compatibility corpus. For every type, classify:

- whether it exposes a pure child graph;
- whether its numeric range is trustworthy and sufficiently tight;
- whether it is Y-invariant, vertically monotone, vertically bounded, or unknown;
- how it composes positional context, interpolation, caching, and visitors; and
- whether a conservative upper solid-density bound can be proven.

The algebra must define sign-aware composition for add, multiply, minimum, maximum, clamp, mapping,
range choice, spline, gradients, shifted noise, interpolated noise, caches, and all router-specific
wrappers. `minValue()` and `maxValue()` are numerical range inputs, not proof of a vertical cutoff.
Noise capable of reaching positive density at every Y remains unbounded unless a proven dominating
vertical term excludes it.

The study must separately resolve:

- structure beardifier and junction influence, including neighborhood reach and iterator ownership;
- old/new chunk blending and whether it makes the bound request-local;
- interpolation and cell-rounding margins;
- fluid/aquifer behavior relevant to allocated sections;
- registry holder resolution, shared subgraphs, visitor replacement, identity cycles, and malformed
  graphs;
- reload and seed ownership; and
- C2ME scheduling and whether analysis can be computed once before concurrent allocation/traversal.

Unknown, cyclic, unresolved, impure, version-changed, or unsupported behavior returns `FULL_HEIGHT`.
It is never assigned a guessed bound.

### Optional extension protocol

If source evidence shows that custom density types need an extension seam, define a registry keyed
by density-function type or codec. An analyzer supplies a pure conservative proof for that function
type and immutable children; it never dispatches by mod ID. A mod with an unknown custom function
remains correct automatically through `FULL_HEIGHT`, although it receives no clipping optimization.

### Phase B go/no-go gate

Retain the analyzer only when all of the following are true:

- every recognized transfer rule has tests against exhaustive or adversarial sampled controls;
- unknown and custom-node controls always fall back to full height;
- structures, blending, holder graphs, reload, and concurrency have complete ownership proofs;
- bounded and full-height generation produce identical blocks, fluids, heightmaps, structures,
  carvers, features, and errors over representative default and tall-world windows; and
- healthy-host measurements show a stable material benefit outside run variance and large enough to
  justify the permanent complexity.

If any condition fails, delete the prototype and keep the immutable extent permanently
`FULL_HEIGHT`. A correct no-go decision completes the analyzer investigation.

### Density-analyzer decision

The production contract is permanently `FULL_HEIGHT` unless a future evidence cycle reopens this
gate. No bounded analyzer belongs in the runtime at present. This is a correctness decision, not a
deferred compatibility requirement:

- The finalized codec graph contains constants and Y gradients that can be proven directly; unary
  clamp/map nodes; sign-sensitive add, multiply, minimum, and maximum nodes; conditional range
  choices; splines; noise and shifted-noise samplers; marker/cache wrappers; holder roots; blending
  markers; and seed-instantiated visitors. FTF additionally registers `noise`, `cell`,
  `clamp_to_nearest_unit`, and `linear_spline`. A useful proof would have to retain transfer rules
  for every one of these shapes and return unknown for every foreign type.
- Numerical `minValue()`/`maxValue()` ranges are insufficient to prove a vertical cutoff. Noise,
  shifted noise, range branches, splines, multiplication across zero, and a foreign node can remain
  positive at arbitrarily high configured Y unless a separately proven dominating term excludes
  them.
- The density router is not the complete request expression. `RandomState` replaces holders and
  noise markers, `NoiseChunk` adds interpolation/cache wrappers, the request supplies blending, and
  structure beardification supplies a neighborhood-dependent density contribution. Therefore a bound
  computed only from the retained `NoiseGeneratorSettings` root is not an upper-bound contract for
  the expression actually evaluated by the request.
- Holder identity graphs require cycle and unresolved-reference handling; blending makes the proof
  chunk-history dependent; structures require immutable neighborhood reach and junction evidence;
  and C2ME requires the result to exist before allocation and traversal are scheduled. Any missing
  proof correctly collapses to full height.
- Healthy-host 2,048-height measurements found only a 1.58% median end-to-end difference, within run
  variance. That does not satisfy the material-benefit gate for retaining several independent proof
  algebras and their permanent version surface.

Consequently there is no density-function analyzer registry or per-mod upper-bound API. Unknown and
custom density nodes remain correct without integration code because the request-owned
`NoiseFillExtent` represents the complete configured-height intersection and the transformed
upstream `fillFromNoise` implementation remains the allocation, traversal, blending, structure, and
scheduling authority. Density extent is never reused for biome sampling.

## Workstream 3: capability-provider protocol and discovery

### Provider-protocol objective

Turn the nominally open provider SPI into a versioned, bounded, mechanism-oriented acquisition
protocol. A malformed or incompatible provider must not poison unrelated owners or facets before
capability diagnostics exist.

### Provider-protocol design

- Define protocol identity and compatibility negotiation independently of a provider's mechanism
  version.
- Separate lightweight provider metadata discovery from loading implementation classes that may
  reference absent optional dependencies.
- Validate provider ID, protocol version, owner types, facets, contribution kinds, ordering edges,
  query mode, and lifecycle requirements before compilation.
- Make optional ordering edges inert when the peer is absent. Report required missing peers,
  duplicate IDs, cycles, linkage failures, and constructor failures as bounded acquisition failures.
- Ensure preview asks only providers whose metadata declares a relevant owner/facet/factory, rather
  than invoking every discovered provider indiscriminately.
- Define whether external providers are a supported public API. If they are, publish and test the
  ABI; if they are not, retain providers as internal mechanism adapters and do not imply ecosystem
  extensibility.

### Provider-protocol completion gates

- Synthetic external providers can participate without editing FTF when they implement the declared
  protocol.
- Bad-provider controls fail only their applicable owner/facet whenever sound containment is
  possible.
- Absent optional mechanisms load clean production servers on both loaders.
- Discovery order is deterministic and independent of classpath enumeration.
- Protocol-version, mechanism-version, and contribution-contract failures are distinguishable in
  diagnostics.

## Workstream 4: composable contribution algebra

### Contribution-algebra objective

Replace the accidental one-provider-per-facet rule with typed composition. Preserve unique ownership
where semantics require one root while allowing ordered peer contributions where the mechanism is
actually additive or transformational.

### Contribution-algebra investigation

For every facet, classify its contribution shape from source evidence:

- unique root;
- ordered transformation stages;
- unordered immutable set;
- keyed replacement;
- executable leaf collection; or
- unsupported composition.

At minimum, distinguish candidate root from candidate transformations, provider-domain root from
selection decorators, density-settings root from density transformations or analysis proofs,
surface-rule root from ordered rule transformations, and sampler query policy from additive sampler
inputs. Do not generalize carvers, features, or structures until their exact ordering and conflict
semantics are proven.

### Contribution-algebra implementation

- Encode contribution kind in the provider contract and typed plans.
- Give every ordered stage a stable typed identity, priority/order semantics, declared possible
  outputs where relevant, and a deterministic conflict rule.
- Reject multiple unique roots explicitly without treating valid additive peers as root conflicts.
- Preserve first-cause diagnostics while reporting all rejected contributors that are safe to
  inspect.
- Compute query concurrency as the conservative intersection of every executed stage.
- Remove singleton bookkeeping and tests that encode accidental cardinality as architecture.

### Contribution-algebra completion gates

- Two independent synthetic contributors compose in the proven order for every newly composable
  facet.
- Conflicting roots, duplicate stage IDs, cycles, missing outputs, and changed query modes fail
  deterministically.
- TerraBlender, Biolith, and Lithostitched mixed stacks retain exact selection and possible-output
  closure.
- Unknown content mods using an already supported contribution kind require no FTF code change.

## Workstream 5: owner-scoped lifecycle and revision publication

### Lifecycle objective

Replace integration-specific refresh triggers with a generic owner-scoped lifecycle contract that
publishes one coherent immutable state for creation, preview, server start, reload, cancellation,
and close.

### Lifecycle design

- Define immutable identities or monotonic revisions for resource layers, tags, mechanism
  contributions, provider protocol, selected dimensions, seed/noise binding, and any analysis
  product.
- Specify which changes rebuild acquisition inputs, which rebind an immutable snapshot, which
  recompile only tag-dependent plans, and which require a new worldgen epoch.
- Make compilation transactional: a replacement plan, possible-output set, generation settings,
  execution modes, diagnostics, and noise extent become visible together or not at all.
- Define cleanup and cancellation for request-owned sources and provider resources.
- Eliminate process-global semantic freshness and integration-specific calls that merely happen to
  refresh the right plan today.

### Lifecycle completion gates

- Repeated previews, concurrent previews, seed changes, dimension changes, datapack reload, tag
  reload, contribution changes, failed replacement, cancellation, server startup after preview, and
  world close have deterministic ownership tests.
- A failed recompile leaves the previous complete state visible and reports the rejected revision.
- No owner observes a plan from one revision with possible outputs or generation settings from
  another.
- Biolith and Lithostitched use the generic revision/publication model; their adapters do not expose
  lifecycle knowledge downstream.

## Workstream 6: request-owned custom biome-source acquisition

### Custom-source objective

Remove the effective `MultiNoiseBiomeSource` preview allowlist by defining the smallest complete
public snapshot or pure finalization-factory contract that can create an isolated request-owned
selection input.

### Custom-source investigation

- Inventory custom source models in the corpus and synthetic controls: wrappers around multi-noise,
  alternate parameter tables, hierarchical/provider sources, positional query-only sources, and
  sources with mutable server or registry dependencies.
- Determine which models can normalize into existing candidate/provider/decorator plans and which
  require a new typed selection root.
- Distinguish serialization from semantics. A codec is useful for cloning but is not proof that FTF
  can own candidate enumeration, possible outputs, ordering, lifecycle, or concurrent queries.
- Inspect public factories/finalizers before declaring a source impossible. Do not infer private
  fields or execute a realized server-owned source in preview.

### Custom-source implementation target

- Keep the public multi-noise codec extractor as the generic base mechanism.
- Add a request-owned source acquisition contract capable of returning either immutable normalized
  plan inputs or a proven owner-scoped executable root with complete possible outputs and lifecycle.
- Require a fresh identity for every preview request unless the contract explicitly proves immutable
  shared state and worker-confined mutable state.
- Keep exactly one final source/root owner while allowing composition stages from workstream 4.
- Refuse opaque custom roots with a typed missing-factory diagnostic.

### Custom-source completion gates

- Ordinary multi-noise sources retain byte/plan parity.
- A synthetic unseen wrapper works through the public factory without FTF consumer changes.
- A query-only mutable source fails before preview workers start and leaves no leaked resources.
- Possible outputs, locate, direct queries, preview, finished chunks, features, and structures agree
  for supported custom roots.
- Repeated/concurrent preview, cancellation, reload, and server-after-preview ownership pass.

## Workstream 7: mechanism-adapter generalization

### Mechanism-adapter objective

Reduce exact implementation and version coupling in TerraBlender, Biolith, and Lithostitched without
weakening their proven semantics or creating per-content-mod integrations.

### TerraBlender scope

- Verify whether contribution applicability can be derived from public region registration rather
  than the `minecraft:overworld` identity heuristic.
- Define supported dimensions and region types from FTF product scope rather than accidental current
  checks.
- Retain public IDs, weights, order, candidate tables, fallback, and FTF-owned spatial policy.

### Biolith scope

- Determine whether Biolith exposes a stable criterion snapshot, visitor, codec algebra, or pure
  evaluation factory covering custom registered criterion types.
- Prefer a public type-driven criterion extension to concrete implementation-class dispatch.
- If no complete seam exists, keep custom criteria explicitly unavailable; do not invoke mutable
  criterion objects downstream or add content-mod Mixins.
- Replace required internal Mixins only when a public acquisition/finalization seam proves complete.

### Lithostitched scope

- Determine whether injector codecs or a public finalized plan can provide typed behavior without
  concrete implementation-class checks or exact wrapper class names.
- Preserve isolated pre-server finalization, frozen natural emissions, repeatability, seed
  rebinding, and later server reuse.
- Unknown injector types remain unavailable until their codec/type supplies complete immutable
  semantics; they are never interpreted by namespace.

### Mechanism-adapter completion gates

- Known content-mod corpus results are reproduced through mechanism contracts, but synthetic users
  of those contracts also pass.
- Version changes fail during bounded provider negotiation rather than Mixin application where the
  upstream API permits that containment.
- No provider retains third-party mutable criteria, registries, sources, listeners, worlds, or
  generators after acquisition.
- Unsupported NML cave return patch and any equivalent private patch remain explicit until their
  owner publishes a complete contract.

## Workstream 8: generator-stage execution seam preservation

### Generator-stage objective

Ensure FTF's ownership of surface, carvers, biome decoration, and structures preserves every stable
loader or library contract represented by finalized graphs or public execution hooks. Do not restore
third-party runtime authority merely to preserve a method interception accident.

### Generator-stage investigation

- Diff vanilla, Fabric API, current NeoForge, and representative library execution for
  `createBiomes`, `fillFromNoise`, `buildSurface`, `applyCarvers`, `applyBiomeDecoration`, and
  `createStructures`.
- Inventory hooks that mutate registries/settings before compilation, hooks implemented by
  executable leaves, and hooks that wrap only a generator method body.
- For every bypassed public loader hook, identify its authoritative input and move acquisition or
  invocation to the FTF-owned stage where semantics can be preserved.
- Treat arbitrary third-party Mixins around vanilla internals as evidence, not automatically as a
  public compatibility contract.

### Generator-stage implementation

- Prefer executing captured registered surface rules, carvers, placed features, placements,
  structures, pools, and processors through their public leaf interfaces.
- Add loader-neutral typed stage hooks only when a stable loader/public contract cannot be
  represented by the finalized graph.
- Keep loader differences behind Fabric/NeoForge abstractions.
- Delete duplicate vanilla reimplementations where delegation can preserve FTF authority and the
  complete public hook chain; otherwise maintain one audited FTF implementation with parity tests.

### Generator-stage completion gates

- Vanilla stage order, random seeding, writable bounds, crash context, side effects, and feature
  sorting match the supported contract.
- Fabric biome modifications, NeoForge biome modifiers, FrozenLib surface rules, custom registered
  leaves, structure-placement conditions, and synthetic method-hook controls are each classified and
  proven or explicitly diagnosed.
- Finished chunks demonstrate surface, carver, feature, structure, heightmap, and palette parity for
  representative mixed stacks on both loaders.

## Workstream 9: optional semantic adaptations

### Optional-adaptation objective

Make FTF-specific ore scaling, surface rescue, and underground classification mechanism-oriented,
conservative, and diagnostically honest. These adaptations may enhance supported content but must
never be required for the underlying registered content to execute.

### Ore adaptation

- Define a public typed placement contract for vertically scalable ores from configured feature,
  placement stages, height provider, dimension frame, and safe fanout semantics.
- Analyze by registered function/type semantics, not mod or feature namespace.
- Unsupported ore shapes execute unchanged and report why no tall-world transform was applied.

### Surface rescue

- Prove the exact placement pipeline conditions under which same-column rescue preserves authored
  probability, filters, block predicates, biome checks, randomness, and attempt count.
- Unknown pipelines execute once through their ordinary public placed-feature contract and receive
  no rescue.

### Underground classification

- Prefer typed active climate registrations and standard/common tags over biome namespaces.
- Define how custom mechanisms may declare surface-only, cave, depth-stage, or unknown roles without
  per-mod code.
- Unknown role must not silently become a cave or be removed from surface selection without proof.

### Optional-adaptation completion gates

- Synthetic unseen registered types receive an adaptation only through the documented type contract.
- Unsupported controls execute unchanged with bounded diagnostics.
- Default-height and tall-world ore distributions, surface placements, and underground ownership
  match the declared policy across loaders, reload, and representative mixed stacks.
- Removing an optional adaptation leaves base registered execution correct.

## Program completion gate

The compatibility-runtime completion program is done only when all nine workstreams satisfy their
individual gates and a final clean integration matrix proves:

- previously valid presets load and copy with intended defaults;
- vanilla, registry-only, TerraBlender, Biolith, Lithostitched, loader-modified, custom-source,
  custom-leaf, and unknown-node controls behave according to their declared contracts;
- preview and finished chunks agree where preview represents the same domain;
- locate, direct biome queries, stored palettes, possible outputs, feature sorting, structures,
  density, surface, carvers, and features use one atomically published FTF plan;
- repeated and concurrent owners, reload, cancellation, failure, server-after-preview, and close
  retain no mutable cross-owner state;
- full-height generation is the permanent safe fallback and bounded density analysis, if retained,
  never changes generated results;
- Fabric and NeoForge production builds and packaged server starts pass with optional mechanisms
  absent and with the supported mixed stacks present; and
- obsolete runtime paths, compatibility shims, superseded Mixins, stale diagnostics, and dead tests
  are removed rather than left as alternate authorities.

If a stable external contract is demonstrably unavailable, completion means retaining an explicit
narrow `UNAVAILABLE` boundary with actionable diagnostics and evidence of why guessing would be
unsound. It never means implementing a per-mod private-state workaround.
