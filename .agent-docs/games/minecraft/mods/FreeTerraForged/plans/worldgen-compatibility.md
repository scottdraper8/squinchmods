# FreeTerraForged worldgen compatibility

This plan defines the current compatibility-runtime contract, supported mechanism boundary,
remaining external API boundaries, and requalification gates. Raw observations, logs, generated
grids, source captures, calculations, and individual run results belong in retained investigation
artifacts.

The dependency-ordered implementation and acceptance program is
`compatibility-runtime-completion.md`. That plan must be read completely before changing the
runtime. This document remains the product and architecture authority when an implementation choice
is ambiguous.

The implementation is on `feat/worldgen-compatibility-runtime` in
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. The published head is
`2c2729c64912a297a76d619bcc2afd7bf719d565`, based on `upstream/1.21.1`
`4a3ab1c5e8f680dc996761908e8904aaca350eb4`. Live Git and dependency state always win.

## Product contract

The compatibility runtime is an ETL and execution boundary:

1. discover supported worldgen mechanisms in the selected creation graph;
2. extract complete owner-scoped declarative data or a stable public executable contract;
3. validate provenance, ordering, lifecycle, reload, failure, and concurrency semantics;
4. copy accepted inputs into immutable FTF-owned containers and typed plans; and
5. let zero-knowledge consumers request resolved FTF results.

Once an input is normalized, FTF owns final candidate composition, spatial assignment, deterministic
randomness, ordering, preset interpretation, and execution policy. TerraBlender, Lithostitched,
Biolith, Minecraft registries and codecs, and loader APIs are peer input mechanisms. None remains an
unseen runtime authority.

Named mods are a coverage and falsification corpus, not an allowlist. An unseen mod using a
supported mechanism must work without consumer-specific code. An unsupported mechanism or facet must
fail narrowly and diagnostically rather than corrupt a supported domain or produce a vanilla-looking
substitute.

Correctness and completeness are the completion criteria; elapsed time and diff size are not. This
is a pre-release internal runtime, so replace unsound ownership, lifecycle, composition, or
execution models in place and delete their obsolete paths. Do not preserve internal APIs, plan
shapes, caches, Mixins, or historical implementation behavior by layering another abstraction over
them. Previously valid presets remain the backward-compatibility boundary and must continue to
decode, copy, and construct complete settings with intentional defaults.

Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, structure
predicates, and future consumers are zero-knowledge. They consume FTF plans and results and never
select a mechanism path, replay registration, inspect third-party mutable state, or interpret
mechanism-specific failure terms.

## Active generalization boundary

The runtime is mechanism-generic where a mod finalizes behavior into an ordinary public multi-noise,
registry, codec, generation-settings, surface-rule, carver, feature, or structure graph before
acquisition. A custom biome-source root can additionally participate through a request-owned
`BiomeSourcePlanInput` or pure `BiomeSourcePlanInputFactory` that declares its complete possible
outputs and query mode. Roots without that complete contract fail before preview workers or runtime
consumers start.

Provider discovery is metadata-first, versioned, contribution-typed, deterministically ordered, and
failure-contained before optional implementation classes load. Unique roots, ordered transforms, and
additive contribution shapes are distinct plan contracts. Resource layers, tags, and mechanism
contribution revisions are captured once per owner refresh and publish one replacement plan,
possible-output closure, generation-settings map, execution policy, and diagnostic state atomically.

Qualified Biolith and Lithostitched bridges remain deliberately version-bound where their public
APIs do not expose a complete immutable final snapshot. Unknown criteria, injector kinds, or changed
bridge versions fail at that mechanism facet; they do not create content-mod exceptions. Stable
public loader mutations already materialized in biome/registry graphs and public executable leaves
are acquired generically. A method-body-only private patch is not treated as a public contract.

Stage acquisition is owner-boundary specific. Fabric biome modifications and NeoForge biome
modifiers are complete in biome generation settings before either preview or server plans consume
them. FrozenLib's public surface event is finalized by FrozenLib into
`NoiseGeneratorSettings.surfaceRule()` during server level creation, before FTF compiles the server
epoch; FTF captures the resulting rule graph and its registered condition leaves without knowing
Wilder Wild or another event consumer. Biome preview deliberately does not compile or execute the
surface facet. An arbitrary generator-method wrapper that has not produced a finalized graph is not
silently claimed as a normalized input; only outer calls preserved by delegation continue as method
hooks.

Ore scaling, surface rescue, and underground roles are conservative optional adaptations. Their
typed plan diagnostics report transformed, delegated, and pass-through inputs plus bounded
inspection failures. Unsupported shapes execute unchanged. Applicability is based on the active FTF
owner, vertical frame, tags, registered function type, and proven pipeline shape—not a content-mod
namespace or literal `minecraft:overworld` key.

Noise fill permanently uses the complete configured-height intersection. The finalized request
expression does not currently justify a bounded analyzer, so unknown and custom density functions
remain correct without integration code.

## Honest feasibility boundary

FTF can own semantics only when it can obtain a complete representation of them. Registry identity,
codec availability, and observed generation do not by themselves prove that another owner can
reproduce code registrations, final ordering, load predicates, weights, noise, reload behavior, or
thread safety.

Each plan facet uses one of these capability states:

| State               | Meaning                                                                             |
| ------------------- | ----------------------------------------------------------------------------------- |
| `NORMALIZED`        | Complete stable inputs were copied into typed FTF data and FTF owns execution.      |
| `OPAQUE_LEAF`       | A registered public executable leaf remains inside an FTF-owned stage.              |
| `OPAQUE_ROOT`       | A custom realized root keeps behavior that cannot be decomposed soundly.            |
| `PROVIDER_CONTRACT` | A public mechanism snapshot or factory supplies a proven owner-scoped contract.     |
| `UNAVAILABLE`       | Required semantics are missing, conflicting, changed, or failed before an FTF seam. |

Use the least coupled complete input: registries/resources/codecs, immutable public snapshots, pure
owner-scoped queries or factories, then a version-qualified mechanism bridge at a documented
boundary. Normalize bridge output immediately. Never use private-field inference, heuristic
reflection, callback replay, namespace dispatch, or per-consumer compatibility Mixins as a
production contract.

Invoking a mechanism finalizer against an isolated graph proves that data can be produced. It is a
reusable request contract only when callback purity or bounded side effects, ownership,
repeatability, exactly-once behavior, ordering, reload, cancellation, concurrency, and later server
reuse are also guaranteed.

## Runtime ownership

### Owners and publication

- `WorldgenEpoch` owns one server creation graph and realized contribution epoch.
- `PreviewRequest` owns one pre-server request graph, registry view, seed, sampler context,
  cancellation state, and request-local caches.
- Resource-layer revision, `TagEpoch`, and mechanism contribution revisions are independent input
  identities captured into one transactional replacement.
- `WorldgenRuntimeBinding` atomically publishes the plan, generation settings, and complete
  possible-biome set as one state.
- Reload recompiles from the unchanged realized input graph; compiled output is never fed back as
  the next input.

Mutable registries, callbacks, provider maps, samplers, noise chunks, and temporary mechanism state
do not cross owners. Parallel queries are enabled only when every executed facet declares isolated
parallel reads; otherwise the plan executes the complete query under one owner-local serial gate.
The selected `TerraForgedChunkGenerator` root establishes server ownership independently of the
shape of its density router. Density-function markers may require that owner, but do not decide
whether the owner exists.

`FlowSettings.CurrentPresetState` is not part of the runtime because a process-global current preset
cannot belong to a specific worldgen owner. Each `Level` owns one immutable flow-settings snapshot
initialized from its `RTFRandomState`, while river flow grids remain chunk-owned. Settings are
absent from chunk NBT and the per-chunk flow payload and are synchronized once per player and
dimension or when they change. Preview and effect consumers read the FTF-owned Level snapshot and do
not acquire settings from a process-global preset or a third-party runtime. This ownership must not
alter river geometry or flow-vector calculation.

### One runtime source

`TerraForgedChunkGenerator` and its `UnifiedBiomeSource` are the only runtime biome authority for an
FTF world. The original selected biome source is retained only as an acquisition graph. Chunk biome
filling, direct queries, `/locate biome`, possible-biome enumeration, feature ordering, and
structure biome predicates converge on the same atomically published FTF plan.

There is no plain `MultiNoiseBiomeSource` interception path, mechanism-owned runtime wrapper,
source-activation layer, old generator-root migration, or vanilla-generator fallback for FTF
terrain. A custom non-FTF generator is not coerced into an FTF root.

### Plan facets

The immutable plan keeps independent contracts for:

- biome composition;
- candidate-provider selection;
- selection decoration;
- spatial ownership;
- sampler decoration;
- density settings;
- surface rules;
- carvers;
- placed features; and
- structures.

Supporting one facet never grants support to another. A selection failure does not silently replace
a valid surface or feature graph, and a valid biome identity does not imply that its placement or
generation settings were captured.

### Noise-fill extent

The configured noise/dimension intersection is the authoritative generation extent. FTF validates
that immutable full-height request value and delegates allocation, cell counts, interpolation,
traversal, section locking, blending, and structure density to the one transformed upstream
`fillFromNoise` implementation. They never derive a smaller bound from an FTF terrain tile, a
thread-local value, or independently walked structure state. The safe production value is the
complete configured height.

A bounded extent is an optional optimization, not a compatibility requirement. It may be selected
only by conservative analysis of the finalized density router after holder resolution, runtime
visitor transformation, interpolation/cache wrapping, structures, and blending. Numerical
`minValue()` and `maxValue()` alone do not prove a vertical cutoff. Unknown functions, extension
types, cycles, unresolved references, structures, blending, or composition rules return full height.
An optional analyzer extension is keyed by density-function type/codec rather than mod ID. An unseen
custom density function therefore remains correct without integration, but receives no clipping
unless its type supplies a complete proof.

Density extent never limits biome sampling. High-altitude biome selection can remain meaningful
where the density result is air, and the density and selection facets retain independent ownership,
reload, diagnostics, and acceptance gates.

### Selection pipeline

The final selection pipeline has:

1. exactly one candidate-provider plan;
2. zero or more deterministically ordered mechanism decorators; and
3. exactly one generic FTF surface or underground policy.

Candidate additions and removals transform the selected root candidate table once. The provider plan
identifies the one domain that owns that table; peer domains retain their authored candidates.
Decorators receive the original candidate, current candidate, complete climate target, position, FTF
cell identity, and immutable normalized inputs. Mechanism decorators execute in compiled order
before the final FTF policy.

The provider tables, fallback table, transformed root table, and every decorator's declared outputs
form the final possible-biome closure. Registry-backed carvers and placed features compile once from
that closure, so a biome introduced only through a supported placement mechanism retains its
registered generation settings.

### FTF spatial authority

FTF computes warped biome cells from its preset biome size and warp settings. Spatial ownership maps
those cell coordinates to one provider domain, then that domain's climate table chooses a base
biome. Normalized replacements and regions use the same FTF cell identity and deterministic
FTF-owned randomness.

This is intentionally not native TerraBlender, Lithostitched, or Biolith geometry. Those mechanisms
supply IDs, climate constraints, eligibility, weights, priorities, regions, and replacement meaning;
FTF owns the final map. Modded placement therefore responds to FTF biome size, warp, edges, climate,
and region policy instead of being written over the result as a second spatial layer.

## Mechanism support

### Minecraft registries and codecs

Public multi-noise entries form the normalized base candidate table. Selected noise settings,
surface rules, configured carvers, biome generation settings, placed features, structure sets,
structures, template pools, and processors retain their public registry identities and executable
leaves. Namespace is identity, not provenance.

Custom registered leaves remain opaque only through their public executable contract. A custom root
whose lifecycle cannot be reproduced remains an opaque root and is not partially reconstructed.

### Loader and library stage materialization

Loader APIs and library events are input mechanisms only when their results are complete at the
owner's acquisition boundary:

- Fabric biome modifications and NeoForge biome modifiers produce final carver and feature lists in
  biome generation settings. The compiler reads those realized settings and preserves registered
  custom leaves, so an unseen content mod using those APIs needs no FTF integration.
- FrozenLib's server-level finalizer invokes its public surface callbacks and exposes the composed
  result from the selected noise settings' ordinary `surfaceRule()` getter. Server-epoch compilation
  occurs after that finalization and retains the composed graph. The callback registry and mutable
  FrozenLib storage do not enter the FTF plan.
- A library callback that runs only after plan compilation, or a private Mixin that changes only a
  method body or return local, has not supplied an acquirable input. It remains outside the affected
  facet unless the mechanism publishes a stable snapshot, pure owner-scoped factory, or public typed
  execution hook.

This classification is by lifecycle and public contract, not library or content-mod name. A rule,
feature, carver, structure, or placement implementation may remain an opaque executable leaf after
its containing graph is acquired; downstream consumers still receive only the FTF-owned plan.

### TerraBlender

The provider snapshots each public Overworld region's ID, positive weight, registration order, and
climate table, plus the default-table fallback. Only exact duplicate `(parameter point, biome)`
pairs are removed. Deterministic weighted rendezvous assigns one provider domain to each final FTF
cell; provider boundaries are therefore a subset of FTF cell boundaries.

Applicability follows TerraBlender's public Overworld-regions dimension-type tag and a selected
multi-noise acquisition root. The literal level-stem key is not an applicability contract, so a
custom tagged Overworld-like FTF dimension participates automatically. Nether regions remain outside
FTF's documented TerraBlender provider-domain scope.

TerraBlender contributes candidate-domain data only. Its native uniqueness noise does not execute on
the FTF runtime path, it does not own the generic cave/surface policy, and it is not a required FTF
dependency. Surface-rule integration is a separate facet.

### Lithostitched

The qualified bridge accepts Lithostitched `1.8.0+beta5` on Fabric and `1.8.0+beta4` on NeoForge. It
normalizes point additions, full and partial replacements, force placement, alternate-layout
dispatch, dimensions, resolved load predicates, priorities, climate and bound density criteria,
regions, memberships, weights, and possible outputs. Injector priority is deterministic, with
injector ID as the equal-priority tie-break. Regions use FTF-cell rendezvous.

At the completed pre-server `WorldCreationContext` boundary, the provider codec-clones the selected
dimension graph and advances Lithostitched's real finalizer against that isolated graph. The bridge
captures each natural code-event emission through the public injector codecs and holder keys,
requires repeated dimension invocations to produce identical ordered output, and publishes no
mutable source, registry, generator, callback, or criterion object. It then normalizes the resulting
declarative and code contributions into an immutable snapshot bound to the original creation-graph
source identity. Preview only reads and rebinds that snapshot; it never invokes a Lithostitched or
RU callback.

Pre-server provider discovery and finalization run only when the selected creation graph contains a
`TerraForgedChunkGenerator` root. A graph with no FTF root does not load provider implementations or
invoke mechanism finalizers merely because an optional library is installed.

If the same generator graph reaches normal server startup, the version-qualified bridge supplies the
frozen emissions to the real finalizer instead of invoking the listeners again. A dedicated server
or another graph with no pre-server resolution uses the ordinary mechanism finalizer. Late event
registration invalidates pre-server products. A changed seed rebinds retained density declarations
to the new request seed without callback replay. An installed Lithostitched with no applicable
contribution remains absent from the plan.

Unknown injector kinds, changed versions, clone failures, owner mismatches, non-repeatable event
output, and finalization failure produce bounded applicable-facet diagnostics. Failed acquisition
does not abort the world-creation UI or publish a partial snapshot.

### Biolith

The qualified `3.0.14` bridge copies additions, removals, direct replacements, and sub-biome
registrations when Biolith accepts them. Applicability is dimension and contribution scoped.
Additions are sorted by the complete climate tuple and biome key; removals transform the root table;
direct replacement proportions become deterministic FTF-cell weighted choices including the authored
vanilla residual.

Data-origin registrations are cleared before Biolith re-registers them. Code registrations remain
process-owned, exact duplicates are removed, and tag reload recompiles an immutable owner copy.
Preview requests read snapshots without consuming registration or changing later server startup.

Built-in sub-biome criteria are normalized immediately into an immutable FTF-owned tree using the
qualified version's public accessors. The tree represents boolean composition, climate value and
deviation ranges, center/edge ratios, original and next-distinct candidate tests, alternate direct
replacement results, biome keys or tags, and ocean-relative depth from immutable owner bounds and
sea level. Evaluation uses the selected provider's immutable candidate table and target point; it
does not retain or call a Biolith criterion, world, callback, holder cache, placement object, or
noise generator. Sub-biome request order is the mechanism's stable biome-key order. Replacement
range adjustments deliberately do not import Biolith's local-noise policy because direct placement
is owned by FTF-cell rendezvous.

## Remaining external boundaries

### Custom Biolith criteria

An unrecognized criterion implementation has no complete immutable FTF evaluation contract. The
qualified adapter rejects it during acquisition and fails only selection decoration with
`biolith_criterion_contract_unsupported`; it does not serialize ambiguous codec output, invoke the
criterion later, or inspect private state. A future custom criterion requires a stable immutable
snapshot or pure owner-scoped factory covering all of its inputs, ordering, reload, cancellation,
and concurrency.

### Third-party patches inside mechanism selection

No Man's Land `1.5.12` uses Biolith built-in criteria for its ordinary replacements and sub-biomes,
which the qualified adapter can represent. Separately, NML adds cave outputs by injecting directly
into Biolith's internal `DimensionBiomePlacement.getReplacement` return. It does not register a
placement, replacement, or sub-biome criterion that Biolith or FTF can snapshot, and the behavior
depends on Biolith fittest nodes plus private return-local state. The public Biolith codec and
registration surface therefore cannot represent this contribution. Supporting it requires NML to
publish a stable registration or factory contract, or Biolith to expose a complete final
selection-plan snapshot. FTF does not add a per-mod Mixin or silently claim those cave outputs.

### Failures before FTF ownership

A loader or third-party Mixin failure that occurs before an FTF generator and plan exist is a
dependency boundary. Verify the latest exact-version release and retain the failed-before-FTF
evidence, but do not describe it as an FTF runtime failure or add a workaround that guesses private
mechanism state.

### Upstream PR 208 landing gate

FreeTerraForged PR 208 was reviewed at draft head `cb654424b2d8b4d848aafd866c3d5280f4f2666e`. Its
net change intercepts `MultiNoiseBiomeSource.possibleBiomes()` and reads the raw parameter field.
The reported blank-preview symptom is relevant, but Mojang 1.21.1 does not perform the described
registry-lookup cast in that method. The source-supported interaction is that Lithostitched calls
the delegate's `possibleBiomes()` during finalization and Biolith uses that query to trigger lazy
point injection. The PR changes that trigger order, but its global raw-field interception, repeated
set construction, and silent exception fallback are not a compatibility-runtime contract.

When PR 208 lands on upstream `1.21.1`:

- inspect the final merged commits rather than assuming the reviewed draft is unchanged;
- merge or rebase the upstream history, but keep the compatibility branch's deletion of the old
  `MixinMultiNoiseBiomeSource` preview-ownership path and do not port the raw-field
  `possibleBiomes()` interceptor;
- preserve pre-server Lithostitched finalization, immutable mechanism snapshots, and
  `WorldgenBiomeSelection.possibleBiomes()` as the sole runtime possible-output authority;
- reacquire the then-current exact Biolith, Lithostitched, RU, TerraBlender, and Terrestria
  releases;
- run actual no-server `WorldCreationContext` previews with Biolith plus Lithostitched and RU on
  both supported loaders, then add TerraBlender and Terrestria to exercise mixed provider and
  decorator ordering; and
- require RU pixels, complete plan possible outputs, deterministic repeated previews, finished-chunk
  parity, locate/query/stored-biome parity, feature-sort closure, and no `ClassCastException` before
  accepting the upstream merge.

PR 208's No Man's Land screenshot is not evidence that NML's private cave semantics are captured.
NML's ordinary Biolith replacements and sub-biomes are covered by the qualified built-in contract;
the cave return-value patch remains the private third-party boundary described above. It becomes
supported only when NML publishes a stable registration/factory contract or Biolith exposes a
complete immutable final selection snapshot.

## Preview contract

The preview frontend supplies creation-graph identity, registry and tag epochs, preset, seed,
viewport, zoom, and cancellation. The backend returns an immutable resolved biome tile and rendering
sidecar. The frontend does not initialize mods, choose mechanisms, inspect samplers or providers,
filter mechanism outputs, or construct a fallback image.

The backend owns exact tile-to-quart mapping, surface-height lookup, request/sampler construction,
bounded caching, cancellation, and approved parallel scheduling. A capability failure renders one
generic unavailable state while the backend report retains the responsible owner, mechanism, facet,
and missing contract.

### Preview performance boundary

The editor preview is entirely client-side and pre-server; it sends no preview payload over the
network. Its first request currently fingerprints the preset, selected level stem, tags, and biome
keys, compiles the purpose-scoped plan, generates the terrain tile, resolves 65,536 biome pixels,
and builds a rendering sidecar. Density, surface-rule, carver, feature, and structure plans are not
materialized for `BIOME_PREVIEW`.

The runtime compiles an explicit immutable, purpose-owned surface-preview climate query policy. It
omits underground banding adjustment and the generation sampler cache while retaining the FTF
sampler context and final surface-biome filter. Normal worldgen compiles the separate policy that
retains both behaviors. Capability providers cannot override the owner's purpose policy. Preview,
generation, diagnostics, and third-party providers remain zero-knowledge: the frontend consumes only
the compiled plan and immutable resolved tile.

The generic query kernel also compiles constant single-provider dispatch, provider-domain lookup,
and rendezvous identifier hashes once; reuses prepared tile cells instead of repeating spatial
lookups; omits the quart cache when every preview pixel has a unique quart coordinate; fills the
typed result array directly; and stores unsigned 16-bit palette indices plus one color per palette
entry in the rendering sidecar. Performance changes must retain selection parity, deterministic
serial/parallel equivalence, and owner isolation.

The cache identity retains the preset encoding, selected-stem encoding, tags, contribution revision,
data configuration, seed, and exact frozen registry-view identity. It also retains the selected
`LevelStem` object used by asynchronous construction, so a worker cannot combine an earlier cache
key with a later live creation graph. The registry object is the owner-issued revision boundary;
enumerating every biome ID is unnecessary and would duplicate registry data. Further cursor or cache
specialization must not weaken this immutable ownership.

These changes belong in runtime plan compilation and its generic execution kernel. They must not
introduce mod-specific preview paths, downstream mechanism inspection, callback replay, or private
state access.

## Requalification gates

Run every affected gate when the branch, upstream base, exact-version dependency, extraction
contract, or plan semantics changes.

### Extraction and lifecycle

- Enumerate declarative, code-registration, event, wrapper, and reload contribution paths.
- Exercise synthetic unseen providers, custom source factories, multiple additive contributors, and
  unknown registered node types so named corpus mods are not the only proof of generality.
- Exercise actual pre-server `WorldCreationContext` compilation before any server finalizer.
- Prove installed-unused mechanisms are not applicable.
- Cover repeated and concurrent previews, multiple seeds and dimensions, cancellation, cleanup,
  reload, and server startup after preview.
- Prove snapshots match owner, dimension, seed, version, holder registry, contribution epoch, and
  output coverage, and retain no mutable mechanism source or registry.
- Fail unknown or changed inputs once, at the applicable facet.

### Density extent

- Require one immutable extent identity and identical allocation/traversal bounds for every request.
- Prove complete configured-height generation on default and 2,048-height presets on Fabric and
  NeoForge, with and without C2ME, including structures, blending, aquifers, reload, and parallel
  scheduling.
- If bounded analysis is retained, enumerate every recognized vanilla and FTF node and prove its
  conservative transfer rule; unknown, custom, cyclic, unresolved, or impure nodes must select full
  height.
- Require full-height and bounded paths to produce identical blocks, fluids, heightmaps, structures,
  carvers, features, and errors over representative windows.
- Keep bounded analysis only after healthy-host end-to-end measurements establish a stable material
  benefit outside run variance. A proven no-go with permanent full height is an acceptable completed
  outcome.

### Selection semantics

- Cover additions, removals, targets, full and partial replacements, force, dispatch, priorities,
  equal-priority ties, conflicts, dimensions, load predicates, regions, weights, and density/noise
  criteria.
- Prove one candidate provider, ordered decorators, and one final FTF policy.
- Prove candidate operations affect only the selected root domain.
- Prove exact possible-output coverage and graph-closed carver/feature compilation.
- Prove deterministic repeat, serial/parallel equivalence, and cross-loader normalized equivalence.

### Runtime and product behavior

- Compare actual editor output with exact finished-chunk surface biome holders.
- Prove FTF biome size, warp, edges, and climate affect representative Lithostitched, Biolith,
  TerraBlender, registry-only, and vanilla inputs.
- Require zero mechanism-only spatial boundaries where FTF owns placement.
- Verify locate, direct queries, stored chunk palettes, possible-biome enumeration, feature sorting,
  and structure predicates use the unified runtime source.
- Validate representative vanilla, BOP, BWG, Wilder Wild, Vanilla Backport, RU, and Terrestria
  controls without treating them as an allowlist.
- Preserve regression coverage for Level-owned flow toggles across enabled and disabled presets,
  save/reload, client sync, dimensions, and chunks whose NBT predates the settings byte; require
  unchanged river and flow-vector data.

### Build and packaging

- Run the complete common and investigation-tool test suites.
- Build clean Fabric and NeoForge production artifacts.
- Inspect exact production JARs for probe payloads, development sentinels, bundled optional
  mechanisms, stale mixins, and deleted compatibility implementations.
- Start packaged servers on both loaders without TerraBlender.
- Record source tree, dirty patch, dependency manifest, scenario inputs, logs, grids, calculations,
  artifact paths, and SHA-256 values in retained artifacts.
- Remove superseded internal paths, compatibility overloads, stale Mixins, dead tests, and alternate
  runtime authorities before declaring a workstream complete.

## Evidence locations

Match retained manifests by source tree, dirty patch, dependency hashes, scenario inputs, and output
fingerprints. Commit IDs alone are not stable evidence keys after a history rewrite. Raw results
remain in the following locations rather than this forward-facing plan:

- Third-party catalog: `.squinch/games/minecraft/third-party/artifacts.toml`
- Retained third-party sources: `games/minecraft/reference/sources/1.21.1/mods/`
- Mapped Minecraft source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Repository scenarios: `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/`
- Canonical fixtures and probes: `games/minecraft/investigations/reterraforged/`
- Retained runs and manifests: `games/minecraft/investigation-state/runs/`
- Focused analyses and comparison artifacts: `games/minecraft/investigation-state/`
- Investigation workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Tooling: `tooling/squinch mc-investigate --help` and `tooling/squinch third-party --help`
