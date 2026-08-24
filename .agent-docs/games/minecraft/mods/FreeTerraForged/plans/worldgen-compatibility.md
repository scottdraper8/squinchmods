# FreeTerraForged Worldgen Compatibility

Status: boundary and evidence ledger; no production compatibility runtime is implemented.

This document defines the compatibility rules that future FTF work must preserve. It is not a
provider catalog, a universal callback design, or a record of previous attempts. Update it only when
current source or reproducible evidence changes a boundary, an admitted capability, or an acceptance
gate.

## Objective

FTF should let ordinary consumers work with standard Minecraft worldgen values without learning
which mod supplied them. Compatibility code exists only where an external system owns behavior that
cannot already be consumed from the realized Minecraft object graph.

The common vocabulary is:

- `BiomeSource` and `Holder<Biome>` for realized biome selection;
- `ResourceKey<Biome>` and biome tags for stable identity and classification;
- `Climate.TargetPoint` and `Climate.Sampler` for climate inputs;
- the active `ChunkGenerator`, noise settings, registries, and placed-feature graph for their
  respective worldgen domains; and
- immutable, value-only health records for diagnostics.

Namespace is not provenance. A `minecraft:*` biome may be contributed by another mod, and a modded
namespace does not prove which registration path or behavior owns its selection.

## Architectural boundary

The reusable portion is an owner-scoped control plane, not an untyped plugin framework. It may own:

- discovery and exact capability negotiation;
- activation ordering and lifecycle;
- failure attribution and first-cause health;
- reverse-order cleanup; and
- cache ownership only after every dependency and invalidation event is proven.

The data plane exposes realized Minecraft objects and typed results. Provider classes, private maps,
mutable registries, registration listeners, and provider-specific diagnostics do not cross into
ordinary consumers.

An abstraction is admitted only when a concrete consumer needs it and representative runtime
evidence proves that it preserves behavior. Merely wrapping one existing call is not sufficient
reason to build a broad runtime.

## Ownership and lifecycle

Every compatibility object has one exact owner:

- server behavior is owned by a particular server level, registry epoch, source, generator, and
  settings graph;
- preview behavior is owned by a particular request and by fresh request-owned state where copying
  is proven safe; and
- chunk execution state such as samplers and `NoiseChunk` belongs to that request or chunk.

Server and preview owners never share mutable parameter lists, R-trees, samplers, provider maps,
registries, holders, thread locals, noise chunks, or preview tiles. State closes with its owner and
is defensively cleared at server stopping when applicable.

Ordinary resource reload does not recreate the active worldgen graph. It must not be treated as a
registration replay or as automatic invalidation for a cache whose real inputs remain live.

No semantic cache is currently admitted. A future cache must prove all relevant dimensions,
including seed, dimension, registry identity and generation, source/generator/settings identity,
provider configuration epoch, model revision, owner kind, and close/invalidation behavior.

## Fixed typed facets

Worldgen stages have distinct timing, state, and failure boundaries. They remain separate:

| Facet                     | Contract                                                                                                   |
| ------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Realized source selection | Delegate to an already-realized `BiomeSource` owned by the caller.                                         |
| Biome composition         | Apply only a public, proven composition operation to fresh owner-scoped state.                             |
| Selection decoration      | Wrap selection only where ordering and fallback semantics are explicit.                                    |
| Sampler decoration        | Own seed/settings/chunk or request state; never share it across owners.                                    |
| Candidate classification  | Enumerate only from a timing-safe initialized snapshot; do not call lazy `possibleBiomes()` speculatively. |
| Surface                   | Preserve surface-rule ownership and independently negotiate provider surface behavior.                     |
| Density                   | Remain server-worldgen-only; never reuse density bootstrap state for preview.                              |
| Placed features           | Consume the final active feature graph and preserve feature-specific filters and lifecycle.                |
| Diagnostics               | Publish immutable values only; observation does not make upstream behavior FTF-managed.                    |

A hybrid provider may expose more than one facet only when its public contract and runtime evidence
prove that the domains can be enabled, disabled, and restored independently. Branding, biome IDs,
separate registration calls, or namespaces do not prove separability.

## Realized inputs and provider boundaries

| Input or provider                                     | Current treatment                                                                                                                               |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Vanilla sources and datapack registry values          | Realized neutral input.                                                                                                                         |
| BlackGear Platform and Vanilla Backport climate pairs | Already-realized neutral input. Never replay listeners; contributor provenance is unavailable.                                                  |
| TerraBlender                                          | Composition, sampler, and surface behavior are separate typed capabilities. Each needs its own exact structural and parity gate.                |
| Biolith and No Man's Land                             | No managed runtime facet without a public immutable level/request query or snapshot contract.                                                   |
| Lithostitched and Regions Unexplored                  | Unsupported as a managed facet until a public reversible source/injector contract defines mutation, seed binding, feature order, and cleanup.   |
| Terralith                                             | Treat its overworld source, density, surface, features, and structures as one coupled data graph unless exact artifact evidence proves a split. |
| Nature's Spirit                                       | Realized biome values are passively consumable; independent region/surface ownership is not proven.                                             |
| Still Life and Lithosphere                            | Treat their dimension, settings, density, surface, and feature data as a coupled graph.                                                         |
| Ordinary ore placement                                | Separate placed-feature work. Standard `ore`/`scattered_ore` contracts are neutral inputs; custom feature systems remain unchanged.             |

Known clean server evidence:

- TerraBlender with Biomes O' Plenty realizes and generates its biome selections on the production
  tree (`20260820T182443Z-caa5486933`).
- BlackGear Platform with Vanilla Backport realizes 55 possible biomes and 7,604 parameter entries,
  including `minecraft:pale_garden` and `minecraft:sulfur_caves` (`20260820T184249Z-fb1fdc1164`).
  This is direct evidence that namespace is not provenance.
- Biolith 3.0.14 with No Man's Land 1.5.12 fails in Biolith's NeoForge bootstrap Mixin before a
  server, FTF selection, or provider realization exists (`20260820T183826Z-67a491a4ab`).
- The catalogued Fabric Lithostitched 1.7.13 and Regions Unexplored 0.6.2 pair reaches the RU entry
  point but fails on a removed Fabric API class before injector registration
  (`20260820T184546Z-b69d1921cd`).

The latter two failures are upstream/runtime compatibility failures. FTF must not suppress them,
replay registration, or invent fallback worldgen on their behalf.

## Failure and capability policy

1. If a provider is absent, do not register or apply its managed facet.
2. If a required class, member, descriptor, instruction, or runtime value shape is missing, mark
   only that facet inactive and report the exact requirement.
3. If behavior fails inside an FTF-owned activation or operation, retain the first cause, mark that
   facet failed, close what was opened, and use only a previously proven-safe model.
4. Provider or core failures outside an owned boundary propagate normally; do not relabel them as
   optional-integration failures.
5. Private accessors and bytecode inspection may establish evidence but are not production APIs.
6. Do not use broad catches, version allowlists, namespace heuristics, or process-global mutable
   compatibility state.
7. Any unavoidable temporary context must define exact ownership, nesting, thread rules, conditional
   restoration, and exception-safe cleanup.

Optional Mixins must be partitioned by facet. The same exact capability result drives both Mixin
application and runtime activation. Mod presence or `@Pseudo` alone is insufficient when a member,
instruction, or runtime value shape can differ.

## Preview boundary

Preview is a consumer of worldgen compatibility, not the architecture's owner. It should query the
same semantic selection stages as generated-world behavior while owning its own safe model.

Current source does not prove a universal copy operation: non-multi-noise sources may be returned by
identity, and retaining an active noise-settings holder may preserve server-owned state. Before any
preview model is called isolated, tests must prove source, generator, settings, registry, sampler,
and temporary provider state ownership.

If safe copying is unavailable, expose an honest degraded or unavailable preview. Do not mutate live
registry/provider state speculatively and do not claim parity from a fallback result.

## Next implementation gate

There is no authorized production implementation. Begin any implementation or new runtime evidence
from the live upstream production tip in an isolated clean worktree; do not assume an existing
investigation checkout is current.

The first implementation must be justified by a concrete consumer. The maximum safe initial scope
is:

1. immutable owner/request identity and value-only facet health;
2. a narrow selection port that delegates to an already-realized source without changing its result;
   and
3. migration of one consumer, with exact before/after parity.

That slice must not initialize a provider, replay registration, enumerate candidates early, copy an
unproven source, mutate registries/sources, install a semantic cache, or alter selection ordering.
Provider behavior is admitted only in later independently tested facets.

Before any behavior-changing facet, require:

- unit coverage for owner isolation, immutable results, lifecycle transitions, first-cause
  retention, and reverse cleanup;
- exact structural/bytecode checks for every optional Mixin group;
- common tests plus Fabric and NeoForge builds;
- vanilla, TerraBlender/BOP, and Platform/Vanilla Backport parity, including Pale Garden and Sulfur
  Caves by exact biome ID;
- absent and structurally incompatible provider cases;
- concurrent preview requests and preview-close followed by integrated-server generation;
- finished-chunk biome ID and color authority rather than cold-query-only claims; and
- production artifact inspection proving no investigation classes or Mixins shipped.

## Required upstream contracts

- Biolith: immutable owner-scoped replacement/sub-biome query or snapshot with cleanup and
  concurrency semantics.
- No Man's Land: a lookup contract compatible with its declared Biolith dependency range.
- Lithostitched: public reversible source/injector composition with seed, feature-order, and cleanup
  rules.
- TerraBlender: stable public contracts for independently negotiated composition, sampler, and
  surface behavior.
- Platform or vanilla: contributor identity only if a real consumer demonstrates that provenance is
  required.
