# FreeTerraForged worldgen compatibility

This plan defines the current compatibility-runtime contract, supported mechanism boundary,
remaining external API boundaries, and requalification gates. Raw observations, logs, generated
grids, source captures, calculations, and individual run results belong in retained investigation
artifacts.

The implementation is on `feat/worldgen-compatibility-runtime` in
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. The recorded head is
`52fa36cad2dfea8a6db9d6a29d31bee905080ef3`, based on `upstream/1.21.1`
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

Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, structure
predicates, and future consumers are zero-knowledge. They consume FTF plans and results and never
select a mechanism path, replay registration, inspect third-party mutable state, or interpret
mechanism-specific failure terms.

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
- `TagEpoch` owns tag-bound recompilation independently of contribution registration.
- `WorldgenRuntimeBinding` atomically publishes the plan, generation settings, and complete
  possible-biome set as one state.
- Reload recompiles from the unchanged realized input graph; compiled output is never fed back as
  the next input.

Mutable registries, callbacks, provider maps, samplers, noise chunks, and temporary mechanism state
do not cross owners. Parallel queries are enabled only when every executed facet declares isolated
parallel reads; otherwise execution remains owner-serial.

`FlowSettings.CurrentPresetState` is not part of the runtime because a process-global current preset
cannot belong to a specific worldgen owner. Commit `19571cafde0bf3409577a4ad9db13e664b83732a` stores
one immutable flow-settings snapshot per `Level`, initialized from that world's `RTFRandomState`,
while river flow grids remain chunk-owned. Settings are absent from chunk NBT and the per-chunk flow
payload and are synchronized once per player and dimension or when they change. Preview and effect
consumers read the FTF-owned Level snapshot and do not acquire settings from a process-global preset
or a third-party runtime.

The comparable Fabric benchmark supports that target. Across 1,280 finished chunks per variant, the
runtime stored 23 settings tags for the same 23 river chunks for which upstream and the world-owned
candidate stored none. The candidate removed 437 uncompressed flow-only NBT bytes, 19 bytes per
river chunk, and reduced the pooled synthetic tag-plus-NBT-write median from 111.37720 to 74.63827
ns/op. Five generation windows did not show a generation-speed improvement, and no object-layout
measurement exists. The retained comparison is
`games/minecraft/investigation-state/flow-settings-benchmark/comparison-20260831.md`; authoritative
runs are `20260831T055219Z-9d36310059`, `20260831T055440Z-045904af9c`, and
`20260831T055716Z-080b316913`, with NeoForge smoke `20260831T060024Z-1c0775185b`.

Complete play-packet and persisted-chunk evidence is retained in `20260831T062824Z-069f7336bb`,
`20260831T063052Z-69ab1b7f6c`, and `20260831T063318Z-e447085c6b`. All three produced the same
ordered flow-grid digest. For 23 river packets, runtime used 2,032 threshold-256 wire bytes; the
world-owned candidate used 2,009 flow bytes plus a 37-byte settings synchronization, 14 bytes more
for the initial sample. It then saves one measured wire byte per flow packet while settings remain
unchanged and breaks even on the 38th packet per synchronization. The chunk tag costs 437
uncompressed and 289-294 deflated bytes across the 23 river chunks. Removing it reclaimed one 4 KiB
Anvil sector in each candidate-context counterfactual, but that allocation result depends on whether
a chunk lies near a sector boundary.

This ownership change does not alter river geometry or flow-vector calculation. Enabled Fabric run
`20260831T074811Z-68582b3abd`, disabled Fabric run `20260831T075047Z-87ef82b1ce`, and enabled
NeoForge run `20260831T075648Z-e6d2a0292f` cover enabled and disabled presets, save/reload identity,
old/no-settings NBT, real player payload dispatch, duplicate suppression, dimension transitions,
independent Level settings, and unchanged river-grid data. Clean packaged runs
`20260831T080025Z-ac5db66e9e` and `20260831T080311Z-4295c5db1d` repeat the loader-specific sync and
reload gates from the promoted commit; the Fabric run also proves 256/256 preview-to-finished-chunk
samples match.

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

### TerraBlender

The provider snapshots each public Overworld region's ID, positive weight, registration order, and
climate table, plus the default-table fallback. Only exact duplicate `(parameter point, biome)`
pairs are removed. Deterministic weighted rendezvous assigns one provider domain to each final FTF
cell; provider boundaries are therefore a subset of FTF cell boundaries.

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

Sub-biome registrations are detected but unavailable because the public criterion object is not an
immutable request-owned factory for its world access, neighbor lookup, alternate output, seed/noise,
ordering, reload, and concurrency behavior.

## Remaining external boundaries

### Biolith sub-biomes

The smallest sufficient API is an immutable criterion snapshot or pure owner-scoped factory that
covers world and neighbor access, alternate results, seed/noise state, order, reload, cancellation,
and concurrency. Until then, a captured sub-biome registration fails only selection decoration with
`biolith_sub_biome_factory_missing`.

### Third-party patches inside mechanism selection

No Man's Land `1.5.12` adds its cave outputs by injecting directly into Biolith's internal
`DimensionBiomePlacement.getReplacement` return. It does not register a placement, replacement, or
sub-biome criterion that Biolith or FTF can snapshot, and the behavior depends on Biolith fittest
nodes plus private return-local state. The public Biolith codec and registration surface therefore
cannot represent this contribution. Supporting it requires NML to publish a stable registration or
factory contract, or Biolith to expose a complete final selection-plan snapshot. FTF does not add a
per-mod Mixin or silently claim those cave outputs.

### Failures before FTF ownership

A loader or third-party Mixin failure that occurs before an FTF generator and plan exist is a
dependency boundary. Verify the latest exact-version release and retain the failed-before-FTF
evidence, but do not describe it as an FTF runtime failure or add a workaround that guesses private
mechanism state.

## Preview contract

The preview frontend supplies creation-graph identity, registry and tag epochs, preset, seed,
viewport, zoom, and cancellation. The backend returns an immutable resolved biome tile and rendering
sidecar. The frontend does not initialize mods, choose mechanisms, inspect samplers or providers,
filter mechanism outputs, or construct a fallback image.

The backend owns exact tile-to-quart mapping, surface-height lookup, request/sampler construction,
bounded caching, cancellation, and approved parallel scheduling. A capability failure renders one
generic unavailable state while the backend report retains the responsible owner, mechanism, facet,
and missing contract.

## Requalification gates

Run every affected gate when the branch, upstream base, exact-version dependency, extraction
contract, or plan semantics changes.

### Extraction and lifecycle

- Enumerate declarative, code-registration, event, wrapper, and reload contribution paths.
- Exercise actual pre-server `WorldCreationContext` compilation before any server finalizer.
- Prove installed-unused mechanisms are not applicable.
- Cover repeated and concurrent previews, multiple seeds and dimensions, cancellation, cleanup,
  reload, and server startup after preview.
- Prove snapshots match owner, dimension, seed, version, holder registry, contribution epoch, and
  output coverage, and retain no mutable mechanism source or registry.
- Fail unknown or changed inputs once, at the applicable facet.

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

## Evidence index

Match retained manifests by source tree, dirty patch, and input fingerprints; commit IDs alone are
not stable evidence keys after a history rewrite. Current pre-server and lifecycle evidence
includes:

- `20260831T103000Z-pre-server-ru-immutable-fabric`: actual Fabric world-creation context, seed
  `12345`, no server, 19,211 RU pixels, normalized composition and decoration.
- `20260831T103500Z-pre-server-ru-immutable-neoforge`: the equivalent NeoForge result with the same
  grid hash.
- `20260831T102500Z-pre-server-lithostitched-unused-final-fabric`: installed-unused control with no
  Lithostitched capability nodes.
- `20260831T095058Z-24a7a965b4`: 65,536-pixel serial/parallel equivalence with zero mismatches.
- `20260831T095227Z-8bbae55c36`: preview versus 16 finished chunks with zero biome mismatches.
- `20260831T095315Z-52330c3942`: owner-preserving tag reload with complete cleanup.
- `20260831T100956Z-27afb0d091`: final mixed Lithostitched/Biolith runtime ownership and
  stored-chunk checks.
- `20260831T101937Z-197d3ca27b`: clean packaged Fabric start without TerraBlender, including 16
  finished chunks and zero preview mismatches.
- `20260831T102031Z-e601c7afec`: clean packaged NeoForge start without TerraBlender, including
  server-list, reload, and flow-settings acceptance checks.

- Third-party catalog: `.squinch/games/minecraft/third-party/artifacts.toml`
- Retained third-party sources: `games/minecraft/reference/sources/1.21.1/mods/`
- Mapped Minecraft source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Repository scenarios: `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/`
- Canonical fixtures and probes: `games/minecraft/investigations/reterraforged/`
- Retained runs and manifests: `games/minecraft/investigation-state/runs/`
- Focused analyses and comparison artifacts: `games/minecraft/investigation-state/`
- Investigation workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Tooling: `tooling/squinch mc-investigate --help` and `tooling/squinch third-party --help`
