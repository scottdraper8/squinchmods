# FreeTerraForged worldgen compatibility

Status: the mechanism-driven compatibility runtime and its ownership foundation are implemented on
`feat/worldgen-compatibility-runtime` at `eb40842`. Generation, preview, diagnostics, provider
selection, and spatial policy consume the same FTF-owned typed plans. Automated
integration/requalification is complete at the recorded upstream tip. Remaining work is
product/visual QA and any third-party public provider contract needed to make an opaque source
request-owned; it is not another compatibility-discovery phase.

Current production and evidence base: `upstream/1.21.1` at
`4a3ab1c5e8f680dc996761908e8904aaca350eb4`, including merged PRs #202 and #204. The implementation
worktree is `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`; rebase it
and requalify affected gates whenever the live upstream tip moves.

## Product contract

The target is an FTF-owned worldgen ingestion and normalization layer. It discovers useful modded
worldgen inputs through public Minecraft/loader registries, codecs, tags, executable interfaces, and
explicit capability contracts; compiles them into immutable FTF-owned plans; and executes those
plans through FTF-owned stages. Preview, generation, diagnostics, and other downstream consumers
must depend only on the plans and never contain mod-specific behavior.

This target covers biome selection and spatial ownership, climate sampling, density/noise settings,
surface rules, carvers and caves, placed features and ores, structures, and lifecycle/diagnostics.
It is not satisfied by migrating the current biome-preview integrations into a cleaner adapter
registry.

Named mods are a falsification and mechanism-coverage corpus, not an allowlist or the architecture's
optimization target. An unseen mod using a supported registry, codec, executable interface, or
capability contract must work without an FTF change. An unseen mechanism must be classified safely
and reported without corrupting supported domains.

The runtime must explain exactly what it normalized, retained as an opaque executable, retained as
an already-initialized root, obtained through a provider contract, or could not support. Semantic
reproduction is possible only where the input exposes enough information through a stable graph,
public executable boundary, or explicit contract. Private imperative code cannot be made
semantically transparent by reflection, bytecode guesses, field-name heuristics, or version-specific
Mixins.

The runtime cannot:

- repair a third-party bootstrap or Mixin failure that occurs before an FTF-owned seam;
- reproduce or independently initialize an arbitrary mod's private mutable state without a stable
  query, factory, or snapshot contract;
- split a datapack's density, noise-settings, surface, feature, and structure graph merely because
  individual registry values can be enumerated; or
- promise semantic parity for an unknown provider from final registry values or biome IDs; or
- claim a normalized FTF implementation when part of the behavior remains hidden in arbitrary
  imperative code.

## Feasibility boundary

The runtime is possible if "handle any mod" means total, safe classification plus automatic support
for standard mechanisms. It is impossible if it means independently reimplement every possible
private behavior. Two mods can publish identical registry/codec graphs and then change generation
through different private state or Mixins; a public-only observer receives identical inputs and
cannot derive two different correct results.

Every facet therefore has one explicit capability state:

| State               | Meaning                                                                                    | Permitted execution                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `NORMALIZED`        | Public declarative structure is sufficient for an FTF-owned typed plan                     | FTF owns traversal, ordering, lifetime, diagnostics, and execution stage                 |
| `OPAQUE_LEAF`       | A registered Minecraft executable object has public semantics but arbitrary implementation | FTF owns the stage and invokes the leaf through its public interface                     |
| `OPAQUE_ROOT`       | A realized generator/source is operational only after an external lifecycle                | Use that already-initialized owner in its original context; do not clone or decompose it |
| `PROVIDER_CONTRACT` | A public mechanism supplies a snapshot/factory and lifecycle rules                         | Compile the supplied values into the relevant typed facets                               |
| `UNAVAILABLE`       | Required behavior is hidden, non-restorable, conflicting, or failed before an FTF seam     | Preserve unrelated facets and emit a bounded first-cause diagnostic                      |

`OPAQUE_LEAF` is still zero-knowledge downstream behavior: consumers see an FTF plan node, not a mod
class. It is not a claim that FTF has reimplemented the leaf's private algorithm. A literal
requirement that all arbitrary Java behavior be translated into native FTF algorithms is impossible;
the public executable boundary is the sound maximum for unknown code.

## Invariants

- Correct behavior and explicit unavailability outrank a permissive fallback that looks compatible.
- Namespace is identity, not provenance. `minecraft:*` values can be third-party contributions.
- Server behavior belongs to an exact worldgen epoch, level, layered registries, tags, source,
  generator, settings graph, seed, and initialized provider state. Preview behavior belongs to one
  request and fresh request-owned state.
- Mutable parameter lists, R-trees, registries, provider maps, samplers, noise chunks, thread
  locals, and preview tiles never cross owners.
- Registration is not replayed. Resource reload does not recreate the active worldgen graph, but tag
  rebinding invalidates any compiled predicate that captured tag membership.
- No cache crosses an owner. The preview screen may retain immutable tiles and biome sidecars only
  under a key containing the selected graph, preset, data configuration, seed, tags, capability
  versions/facets, and biome identities; request-owned activations and samplers are never cached.
  Pipeline decisions are keyed to the final typed pipeline, not a coarser configured object.
- Compatibility never depends on private third-party fields, methods, Mixins, or version allowlists.
  Contained Minecraft access needed to own a vanilla stage is a separate implementation concern and
  must be negotiated by exact class/member shape.
- Failures outside an FTF-owned operation propagate normally. An owned facet retains its first
  cause, closes opened state, and may use only a separately proven safe fallback.
- Diagnostic accessors and bytecode inspection may gather evidence; private internals are not
  promoted to a general production contract.

## Typed plan domains

The stages below have different state, timing, ordering, and failure boundaries. They are not one
generic callback interface.

| Facet                  | Plan input and output                                                  | Boundary                                                                                  |
| ---------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Source selection       | Owner-scoped `BiomeSource`, sampler, and biome holder                  | Delegate through the public source boundary unless a normalized selector contract exists. |
| Biome composition      | Fresh owner-scoped parameter state to realized candidates              | Only public/typed composition operations; no registration replay.                         |
| Provider selection     | Position/climate to a provider-owned candidate domain                  | Preserve weights, fallback, and stage order through a mechanism contract.                 |
| Selection decoration   | Selected/fittest candidates to a decorated result                      | Ordering is explicit; imperative decorators require a query/snapshot contract.            |
| Spatial ownership      | Position to immutable domain ID and transition facts                   | Provider geometry is a separate facet; biome ID does not reveal ownership.                |
| Sampler decoration     | Seed/settings/owner to an owner-scoped sampler                         | Never share a sampler or temporary context between server and preview.                    |
| Density/settings       | Selected noise settings and density graph to terrain samples           | Preserve the selected root; arbitrary roots have no automatic merge algebra.              |
| Surface                | Active surface-rule graph to block state                               | Rules are typed or opaque public leaves; independent from biome/provider selection.       |
| Carvers/caves          | Ordered configured carvers and context to carved chunk                 | Preserve probability, RNG, order, replaceability, and feature-rescue boundaries.          |
| Placed features/ores   | Final biome generation settings and complete `PlacedFeature` pipelines | Key by placed pipeline; preserve step, feature filter, RNG, and modifier order.           |
| Structures             | Structure sets, placements, structures, pools, and processors          | Preserve coupled registry references and public executable leaves.                        |
| Diagnostics/provenance | Any plan node to immutable value-only health/evidence                  | Observation does not transfer ownership or infer provenance from namespace.               |

A provider may expose multiple facets only when each can be independently owned, failed, and
restored. Branding, namespace, or separate registration methods do not prove separability.

## Current runtime ownership

The runtime branch owns the registered `TerraForgedChunkGenerator` root and its biome, density,
surface, carver, structure, and placed-feature stages. `WorldgenEpoch`, `PreviewRequest`, and
`TagEpoch` define the server, preview, and tag-rebind lifetimes. The loader-neutral capability SPI
compiles public inputs into separate typed facets and closes activated provider state in
deterministic reverse order.

Preview compiles from the selected `WorldCreationContext` graph. It does not reconstruct a vanilla
generator or run per-mod initialization. Standard multi-noise sources are normalized from their
public registry/codec graph. An opaque realized source can participate only through the generic
`WorldgenCapabilityProvider.previewSource` contract, which must return a fresh request-owned source
and then compile the identical executable root as `SOURCE_SELECTION` with `PROVIDER_CONTRACT`
provenance. Conflicting factories, realized-instance reuse, mismatched roots, and partial lifecycle
failures are rejected and closed. TerraBlender is supplied by its contained public mechanism
provider. The former process-global integration registry, Biolith/Lithostitched private accessors,
and optional third-party Mixins are absent.

The editor screen owns at most one terrain and one biome request context for the current semantic
key, so page navigation, panning, and zooming do not reconstruct registry views, generator context,
or a worldgen plan. Plan compilation is purpose-scoped: biome preview materializes only source,
composition, provider, selection-decoration, spatial, and sampler facets. It removes provable cave
candidates from the surface table without constructing underground regions. Generation-only density,
surface, carver, feature, and structure facets remain in the selected generator root.

The screen-scoped computation cache contains only immutable results and leased tiles. Its revision
key covers seed, encoded preset, data configuration, full selected `LevelStem`, tag contents,
capability identity/version/facets, and sorted biome identities. The compiled preview plan, sampler,
provider tables, and activation remain inside the `PreparedContext` request owner and are closed
after outstanding leases finish.

Biome rendering is a zero-knowledge consumer of one backend surface-tile result. The runtime owns
the decorated sampler, exact tile-to-quart/surface mapping, per-worker request state and cache,
cancellation, and scheduling. It resolves the authoritative FTF cell at Minecraft's quart origin and
returns biome holders that become an immutable ID/color sidecar. The widget never receives provider
domains, selection-provider diagnostics, query modes, or plan internals. Technical failures are
logged through the preview failure path and render only the generic unavailable state.

The original zoom complaint was not additional plan/bootstrap work. The retained client trace
`games/minecraft/investigation-state/manual-client-runs/20260829T171726Z-preview-trace/latest.log`
shows a fixed 256-by-256 preview issuing 65,536 unique sequential quart selections at zoom 150;
biome-sidecar selection consumed 44-46 seconds while request construction, tile generation, and
rasterization were small. Zoom changes sample spacing, not pixel count. The backend batch keeps all
65,536 exact queries but partitions deterministic row bands across isolated worker requests only
when every executed facet opts into concurrent reads. Unknown capability implementations remain on
the serial path.

## Mechanism coverage corpus

| Example                                              | Mechanism exercised                                                                          | Expected capability                                                                                                      |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Vanilla and datapacks                                | Dynamic registries, selected roots, tags, codecs, resource layers                            | `NORMALIZED` graph with public executable leaves                                                                         |
| TerraBlender consumers                               | Weighted regional selection before climate winner; independent spatial/sampler/surface hooks | `PROVIDER_CONTRACT` through TerraBlender's public mechanism APIs                                                         |
| Biolith                                              | Imperative post-selection replacement/sub-biome decoration                                   | `UNAVAILABLE` for isolated reconstruction until a public snapshot/query contract exists                                  |
| Lithostitched / Regions Unexplored                   | Registry/source injection plus mutable seed binding                                          | Realized registry values are usable; isolated injector facet is unavailable without reversible public lifecycle          |
| Terralith and Still Life/Lithosphere                 | Coupled datapack biome, density, surface, feature, and structure replacements                | Preserve selected graph as one authority; do not partially merge by namespace                                            |
| Wilder Wild/FrozenLib                                | Custom registered surfaces/features/placements plus imperative structure alias mutation      | Public leaves are opaque; non-fixed-point codec nodes cannot be cloned                                                   |
| Moderner Beta                                        | Custom registered generator/source whose provider is initialized at server-start             | Operational instance is `OPAQUE_ROOT`; isolated codec clone is unavailable                                               |
| Nature's Spirit                                      | Custom carvers/features/placements/structures plus TerraBlender selection                    | Domain-specific registered leaves plus provider contract                                                                 |
| Terrestria                                           | Biolith replacement APIs when Biolith is loaded; otherwise TerraBlender regions              | Registered leaves plus the selected mechanism's capability; current Biolith selection is unavailable to isolated preview |
| YUNG's Cave Biomes                                   | Cave biome, custom features, structure type/placement                                        | Cave/feature/structure plans; not a biome-only adapter                                                                   |
| Create, Immersive Ores, Mekanism, and other ore mods | Final placed-feature pipelines and config-aware executable leaves                            | Placed-feature plan with opaque public leaves                                                                            |

These examples cover major 1.21.1 mechanisms but do not bound future support. Any mod using the same
mechanisms receives the same classification regardless of identity.

## Current critique disposition

The reported symptoms cross distinct owners and facets. Their current classifications are:

| Concrete claim                                                                                | Classification                                                                              | Facet and owner                                                                                                             | Current conclusion                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Preview recompiles excessively, renders underground regions, and refreshes on page navigation | Valid for the pre-correction preview path; handled                                          | Preview compilation and lifecycle, owned by `PreviewRequest`/editor screen                                                  | Purpose-scoped compilation omits generation facets and underground-region construction. Screen-owned request pooling retains one terrain and one biome context across pages, pan, and zoom under the complete semantic key. Constructors do not build duplicate semantic keys. The remaining zoom-150 delay was 65,536 exact serial selections, not recompilation. Backend-owned isolated batches now return the same 65,536 values in 2.84/2.96 s instead of 34.80/35.05 s in clean Fabric/NeoForge equivalence runs, with exact repeats and no serial mismatches; finished-chunk batch parity is also exact. |
| Initial/deep/tall generation is slower than upstream                                          | Valid before owner-local memoization; contradicted by the corrected current runtime         | Climate sampling and FTF spatial lookup, owned by `WorldgenEpoch`/sampler                                                   | The three-observation deep/tall control is 25.561 s median upstream (`20260829T083242Z-61c6d467d6`) and 25.300 s runtime (`20260829T083526Z-1469c1f250`) for 81 chunks and 298,080 quart cells per observation from Y -600 through 319. Startup is 22.848 s upstream and 22.868 s runtime (`20260829T075019Z-e3f1f7ff5e`) after removing repeated plan construction.                                                                                                                                                                                                                                           |
| No Man's Land/Biolith biomes are absent or tiny in preview/world                              | Unsupported as an FTF preview-versus-generation conclusion on current releases              | Third-party bootstrap before an FTF owner; intended later facets are source selection and selection decoration              | No Man's Land 1.5.12 embeds Biolith 3.0.11 when no external Biolith is installed, so that stack is not Biolith-free. Current external Biolith 3.0.14 fails its required `MixinNoiseHypercube` before FTF; the embedded path then fails No Man's Land's required structure-state Mixin before world creation. No older artifact is used as a compatibility substitute.                                                                                                                                                                                                                                          |
| Terrestria generates but is absent from preview when Biolith is installed                     | Valid and explicitly bounded                                                                | Biolith owns imperative selection decoration; preview is owned by `PreviewRequest`                                          | Terrestria 7.0.3 detects Biolith and registers replacements through Biolith rather than TerraBlender. Biolith 3.0.14 exposes registration calls but no public immutable query/snapshot/factory for its realized replacement criteria, ordering, seed, and noise. In `20260829T161029Z-d87b6d10e3`, `/locate` finds `terrestria:japanese_maple_forest` at `[-1472,163,2128]`, while the fixed preview window selects only `minecraft:overworld` and contains vanilla biomes. Registry presence cannot reconstruct the missing placement semantics.                                                              |
| Regions Unexplored biomes exist in generation but not preview                                 | Valid and explicitly bounded                                                                | Lithostitched realized opaque source owns source selection/selection decoration; preview would be owned by `PreviewRequest` | Fabric RU 0.6.2 + Lithostitched 1.8.0-beta5 generates successfully, while preview fails explicitly because `InjectorBiomeSource` exposes no complete public request-owned factory/snapshot (`20260829T160921Z-2f4245fdf1`). The generic provider factory boundary exists; no RU-specific adapter or silent vanilla fallback is used.                                                                                                                                                                                                                                                                           |
| RU biomes ignore FTF biome size                                                               | Partially valid                                                                             | FTF owns spatial cells; Lithostitched owns imperative substitutions inside the realized source                              | Current RU production grids at sizes 50 and 2000 (`20260829T081533Z-9ab17a5f30`, `20260829T081809Z-6101d32073`) reduce FTF-cell edges from 126,021 to 3,523, proving FTF scaling. Interior biome-change edges remain 25,981 and 13,872, proving a separate Lithostitched selection-decoration scale inside enlarged cells. Rewriting those positions without a public displacement/footprint/order/RNG contract would repeat the rejected PR #202 error.                                                                                                                                                       |
| The shown shattered-glacier/Ice-Spikes boundary proves a transition bug                       | Unsupported from the image alone                                                            | Surface/feature appearance is distinct from source selection and FTF spatial ownership                                      | Current BWG grids show the named adjacency on an FTF-cell/interior boundary, never a provider-only boundary. Exact seed, coordinates, Y, and preset are required for a surface-level parity probe; biome names and a rendered seam do not identify which facet failed.                                                                                                                                                                                                                                                                                                                                         |
| Chunk failures are a general FTF-runtime regression                                           | Unsupported by current FTF-owned evidence                                                   | Failure owner must be resolved before assigning a worldgen facet                                                            | Current Fabric RU generation completes 256/256 chunks (`20260829T081235Z-0f35905d9b`); deep/tall and BOP gates also complete. Retained NeoForge parent-chunk traces reproduce with a vanilla `NoiseBasedChunkGenerator` control, while current Lithostitched/Biolith/NML failures occur in required third-party Mixins before an FTF seam.                                                                                                                                                                                                                                                                     |
| Only vanilla biomes scale                                                                     | Contradicted for FTF spatial ownership; partially valid for independent imperative overlays | Spatial ownership versus selection decoration                                                                               | BWG size 50/225/900/2000 grids reduce FTF-cell edges 126,021/29,687/8,011/3,523 with zero provider-only boundaries. TerraBlender consumers therefore scale with FTF cells. Lithostitched's internal replacements remain a separately diagnosed overlay rather than evidence that FTF scaling is inactive.                                                                                                                                                                                                                                                                                                      |

Runtime data mining is feasible where the final selected registries, codecs, tags, public executable
interfaces, or an explicit provider expose complete semantics. That is the runtime's ETL layer: it
normalizes those inputs once into FTF-owned typed plans and executes them itself. Mining registry
entries alone is not enough for a hidden imperative overlay: two mods can expose the same public
graph and select different results from private mutable state. Such a facet requires a complete
public snapshot/factory/query contract, remains an already-realized opaque root in its original
owner, or reports `UNAVAILABLE`; integrating named mods through private adapters would be less
general and less correct than this boundary.

## Current-tip evidence

All successful spatial grids use seed/coordinates fixed by their retained scenarios, exact FTF cell
lookup and surface Y, final positional biome selection, 4-neighbor topology, and raw row-major
gzip/base64 int32 fields with SHA-256 dictionaries. The independent decoder
`games/minecraft/investigations/reterraforged/analysis/spatial_grid_analysis.py` verifies the hash
and recomputes component and transition metrics without probe code. Finished generated control
chunks had zero stored-versus-direct mismatches in every successful grid.

### Spatial controls and TerraBlender boundary behavior

The 512x512 grids sample every 8 blocks over 4,088 by 4,088 blocks (262,144 points).

| Stack / FTF biome size               | Run                           | Components | TB-only edges | Change fraction at TB-only edges | Mean FTF edge: TB-only / interior | FTF-only edges |
| ------------------------------------ | ----------------------------- | ---------: | ------------: | -------------------------------: | --------------------------------: | -------------: |
| FTF control / 50                     | `20260828T045701Z-7f308ba029` |      1,046 |             0 |                                0 |                               n/a |        126,021 |
| FTF control / 225                    | `20260828T045310Z-5a191c63a4` |        543 |             0 |                                0 |                               n/a |         29,687 |
| FTF control / 900                    | `20260828T045847Z-38f4f2fb64` |        601 |             0 |                                0 |                               n/a |          8,011 |
| BOP / 50                             | `20260828T050047Z-bd93ce7315` |      1,329 |        10,619 |                           39.10% |                       .598 / .599 |        122,673 |
| BOP / 225 / TB size 2                | `20260828T061929Z-4fe90854d2` |        866 |        23,042 |                           40.41% |                       .561 / .560 |         28,296 |
| BOP / 225 / TB size 3                | `20260828T050236Z-5901d52861` |        588 |        13,176 |                           36.43% |                       .560 / .560 |         28,896 |
| BOP / 225 / TB size 4                | `20260828T062131Z-8b08a4f2a1` |        498 |         7,509 |                           40.40% |                       .552 / .560 |         29,194 |
| BOP / 900                            | `20260828T050428Z-95c46f82b1` |        730 |        13,750 |                           37.55% |                       .541 / .541 |          7,794 |
| Nature's Spirit / 50                 | `20260828T050648Z-7cdd284ac2` |      1,304 |        12,230 |                           31.95% |                       .595 / .599 |        122,182 |
| Nature's Spirit / 225                | `20260828T050838Z-28b0a72c85` |        784 |        15,141 |                           35.96% |                       .553 / .560 |         28,759 |
| Nature's Spirit / 900                | `20260828T051029Z-fcccd5fe59` |        729 |        15,809 |                           26.68% |                       .540 / .541 |          7,751 |
| BWG 2.6.0 / 225 / first-start config | `20260828T071337Z-c8cf79d91c` |        944 |        13,563 |                           38.30% |                       .551 / .560 |         28,815 |

The result is conclusive for current native behavior:

- TerraBlender's region field is unchanged when FTF biome size changes. In BOP the four region
  sample counts are exactly `73,330 / 93,856 / 66,207 / 28,751` at all three FTF sizes.
- At fixed FTF size 225, changing native TerraBlender size from 2 to 3 to 4 reduces TB-only edges
  from 23,042 to 13,176 to 7,509 and final-biome components from 866 to 588 to 498. FTF-only edges
  remain near 28k-29k. The native knob changes provider-domain scale, not ownership integration.
- FTF cell-boundary frequency changes by roughly 16x between size 50 and 900, while
  TerraBlender-only boundary frequency remains near 11k-16k.
- At TerraBlender-only boundaries the mean FTF `biomeRegionEdge` is effectively the same as ordinary
  interior. At FTF-only boundaries it is about .113 at size 225 and .031 at size 900.
- A final biome change occurs at roughly 27%-41% of TerraBlender-only adjacencies, far above the
  2%-6% interior rate. FTF edge resampling therefore does not recognize or shape these visible
  provider transitions.
- The same mechanism appears in BOP, Nature's Spirit, and BWG. It is architectural rather than a
  single biome-pack defect.

TerraBlender 4.1.0.8 implements a separate zoomed region map. Its configured region-size increment
adds a normal zoom and therefore doubles characteristic scale. The generated default is
`overworld_region_size = 3`. BOP registers weights 10, 8, and 2 in addition to vanilla weight 10;
Nature's Spirit registers five regional tables at default weight 4 in addition to vanilla 10; BWG
registers three regions at default weight 8 in addition to vanilla 10. A finite-window share is not
expected to equal the theoretical weight exactly. Native sizes 2 and 4 preserve the same high
TB-boundary biome-change rate and the same interior-like FTF edge value as size 3; scale tuning
cannot make FTF transition shaping recognize those boundaries.

Native TerraBlender selection is correct relative to TerraBlender's contract, but it does not make
FTF biome size or transition geometry authoritative over visible provider boundaries. The runtime's
product contract therefore selects FTF-owned spatial ownership: ingest TerraBlender's public
provider tables, weights, fallback, and stage order, then assign exactly one provider to each FTF
biome cell through the generic provider/spatial plan. The winning warped-Voronoi lattice coordinate
is the stable cell key. Assignment uses a provider-plan salt and stable provider identity, rather
than generation RNG or the existing `biomeRegionId` value, so it is query-order independent and does
not couple provider choice to another cell random channel. Adjacent cells assigned the same provider
remain distinct FTF cells; no second grouping scale or hidden merged geometry is created. Native
TerraBlender geometry and simple region-size coupling remain comparison controls, not target runtime
policies.

### Ice Spikes and micro-biomes

Nature's Spirit repeats Ice Spikes in two climate slots in each of its five regional tables and the
vanilla table. It is therefore region-invariant while many Nature's Spirit biomes are
region-variant. Ice Spikes can join across a TerraBlender boundary that terminates neighboring
biomes, making the screenshot's proposed mechanism plausible.

The measured conclusion is narrower than the screenshot claim:

- Nature's Spirit size 50: 1,112 Ice Spikes samples in 15 components; largest 410 samples = 26,240
  block2 and spans three TerraBlender regions and 20 FTF cells.
- Nature's Spirit size 900: 979 samples in six components; largest 684 = 43,776 block2 and spans two
  TerraBlender regions but one FTF cell.
- Nature's Spirit size 225, 1,048,576-point grid `20260828T051413Z-dc9be4fddd`: 200 samples in three
  components; largest 195 = 12,480 block2, one TerraBlender region and three FTF cells. Its 58,817
  TerraBlender-only edges changed biome 40.80% of the time.
- The FTF-only controls already contain Ice Spikes components of 26,240 and 43,776 block2 at sizes
  50 and 900.

Ice Spikes is not generally or uniquely oversized in these windows; several ocean and ordinary biome
components are much larger. Its repeated cross-table slots allow occasional cross-domain merging, so
it is a useful sentinel for policy tests, not proof by itself of a special Ice Spikes bug.

### Realized provider and feature graphs

Current-tip graph censuses all reported zero duplicate active feature occurrences:

| Stack                          | Run                           | Climate composition                                                             | Final feature graph                                                       |
| ------------------------------ | ----------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Terrestria                     | `20260828T052115Z-972251cf5f` | 7,611 entries / 71 biomes; one TB provider region                               | 85 biomes, 343 registered features, 247 active unique / 3,799 occurrences |
| BWG 2.6.0 / first-start config | `20260828T071211Z-761b490795` | Base table remains vanilla 7,593 / 53; four TB regions own post-table selection | 120 biomes, 458 registered, 356 active / 5,784 occurrences                |
| Wilder Wild                    | `20260828T052259Z-08ec19ff59` | 29,404 / 83; 21,153 Wilder Wild entries                                         | 94 biomes, 843 registered, 555 active / 5,447 occurrences                 |
| Terralith                      | `20260828T052356Z-09d124ef70` | 1,713 / 148; 898 Terralith entries                                              | 159 biomes, 832 registered, 578 active / 7,612 occurrences                |
| Still Life                     | `20260828T052445Z-4f55421982` | 3,988 / 109; 3,980 Still Life entries                                           | 172 biomes, 555 registered, 392 active / 7,995 occurrences                |
| Vanilla Backport               | `20260828T055559Z-a81592cf6e` | 7,604 / 55, all `minecraft:*`; two TB regions and one replaced cave slot        | 67 biomes, 318 registered, 225 active / 2,952 occurrences                 |

BWG proves that the base climate table does not expose regional ownership. Vanilla Backport proves
that namespace does not expose contributor provenance and that provider behavior may operate at a
cave-selection stage.

### Preview, cave, and feature execution

- Final clean-source Fabric and NeoForge BOP preview parity runs are `20260829T161825Z-195e750faa`
  and `20260829T161345Z-f793dd2291`: 59,536 exact quart columns per loader, zero mismatches, zero
  provider fallbacks, zero underground preview selections, and complete cleanup on both loaders.
- Current Fabric RU/Lithostitched generation succeeds, while isolated preview reports the missing
  request-owned factory in `20260829T160921Z-2f4245fdf1`. Historical private-adapter and
  empty-registry controls are not current compatibility authority.
- YUNG's Cave Biomes with latest YUNG API 5.1.8: `20260828T070956Z-982f451300`, 99 finished chunks
  and 77,616 quart samples; `yungscavebiomes:lost_caves` appeared 1,876 times from Y -62 to 130.
- Create: `20260828T054755Z-8d81aa87b9`, 64 chunks; zinc invoked and succeeded in all chunks with
  5,448 writes (2,773 zinc, 2,675 deepslate zinc).
- Immersive Ores Fabric `20260828T054858Z-6c41917c45` and NeoForge `20260828T055002Z-c6d46f417f`:
  64/64 successful vibranium-ore invocations and 1,323 writes on each loader; vanilla diamond/iron
  also remained active.

These establish that ordinary third-party ores and cave biomes participate through their realized
typed graphs. They do not justify emulating those providers in a biome compatibility adapter.

Merged upstream PR #202 (head `fab9160`, upstream merge `3860167`) is a negative design control, not
an ingestible worldgen contract. Its reflective object-graph walker classifies all six rescue
pipelines as horizontally unsafe because their intentional vertical `ySpread = +/-1` field contains
`spread`. It changes `InSquarePlacement` X/Z before rescue and reduces two rescues/enclosure checks
plus three successful feature invocations to zero in both the production and latest Nature's Spirit
stacks. Its child-feature stop also hides Nature's Spirit's nested cliff displacement: a targeted
comparison has zero `stone_cliff` differences while unrelated `snow_patch` writes fall from 883
to 655. The configured-feature cache key remains coarser than the placed pipeline. In the
height-targeted BOP control it retains similar aggregate rescue volume but preserves only 81 of
2,924 exact production rescue positions; two production repeats preserve 2,674 of 2,924. This proves
that aggregate counts can hide systematic candidate relocation. The same 8-by-8 chunk control
records 2,288 successful configured placements from 2,948 production rescues and 2,261 from 2,882
pull-request rescues. The 1.2% aggregate placement difference is within observed fresh-world
variation; the systematic position replacement is not. Production rescue yields 2,924-2,948 rescues
per run, including roughly 1,860 above Y 256, while a rescue-disabled control cuts observed writes
from 10,322-10,420 to 4,128-4,226. The sparse `43,302 for 2` observation means 43,302 failed scans
entered policy, 4,907 searches were scheduled, 4,796 physical scans ran, and both returned rescues
became successful configured placements. Production rescue remains acceptable interim behavior and
the parity authority until the typed runtime plan owns the same semantics. Retained comparisons:
`compare-20260828T131106Z-1edd437e25`, `compare-20260828T131624Z-2b00f75b16`, and
`compare-20260828T132430Z-ce7f948c80`.

The runtime branch therefore keeps #202 in its Git ancestry but removes `MixinSquarePlacement` and
its Mixin registration. It preserves the realized placed-feature pipelines and authored candidate
coordinates until typed displacement, footprint, ownership, and exact RNG/order closure justify a
spatial rewrite. Current-upstream Nature's Spirit run `20260829T005459Z-eabe670800` completes 16/16
chunks with the full vanilla 0..15 `InSquarePlacement` domain and reports 65 pipelines that #202's
heuristic would classify as unsafe. Generic reflection, semantic field-name matching, and
cross-facet/coarse caches remain prohibited runtime mechanisms.

### Upstream preview optimization boundary

PR #204 merged as `4a3ab1c5e8f680dc996761908e8904aaca350eb4`. Its performance measurements identify
real repeated work, but its ownership model does not replace the runtime preview path:

- its static initialization cache is keyed only by `RegistryAccess` object identity and seed, has no
  called invalidation path, and retains realized generators, sources, and provider state across
  requests;
- it reconstructs `NoiseGeneratorSettings.OVERWORLD`, a vanilla generator, and mod-specific
  Biolith/TerraBlender state instead of compiling the selected active root;
- its parallel biome queries do not inherit Biolith's thread-local session, and no provider
  concurrency contract makes the other opaque leaves safe for common-pool execution;
- its zoom-dependent coarse stride aliases arbitrary non-quart-aligned preview centers and reuses
  one surface Y across cells whose height can differ;
- its reduced cache key omits the selected graph, tag contents, biome identities, and capability
  versions, while codec failure collapses to an empty-string collision; and
- its eldest-entry exception can leave the cache above its bound after leases release, its palette
  index is a signed `short`, and nested common-pool submission plus `join` weakens cancellation and
  lifecycle control.

The runtime admits the public, semantics-preserving optimizations: exact repeated quart-coordinate
queries use collision-checked worker-local memo tables; immutable sidecars use a String palette with
`int` indices; the already-computed complete cache key flows into request compilation; and
TerraBlender snapshots remove only exact duplicate `(Climate.ParameterPoint, biome holder)` pairs
while preserving registration order. Provider-table deduplication never removes distinct values at
the same climate point. Every facet remains sequential unless its capability explicitly declares
isolated parallel reads; the executor proceeds concurrently only when all facets used by the query
do so. No approximate spatial sampling or cross-request realized-state cache is used.

One backend surface-tile operation now owns biome resolution, scheduling, cancellation, and result
assembly. Each worker gets an isolated `TileBiomeRequest`, sampler, tile lookup shared across the
five climate fields, and quart cache. It reuses prepared FTF cells and derives each cell at the
quart origin rather than a pixel center. The accepted cross-loader equivalence and finished-chunk
gates are exact, while zoom-150 resolution improves by 11.85x-12.26x. Preview constructors defer
semantic-key construction until a request is made.

Climate-candidate presence is not used to infer a missing imperative overlay. FTF deliberately emits
mushroom-fields continentalness below `-1`, so a hard-coded `[-1,1]` reachability diagnostic was
both false and architecturally unsound. Capability unavailability must come from an observed missing
contract or failed operation, not a guessed sampler range.

The runtime branch contains the upstream merge and current correction at `eb40842`. It excludes the
Biolith private preview context and TerraBlender private `MixinParameterList`, restores exact
trimming after leases release, retains the complete cache key and request owners, and removes
Biolith-specific loader version gates. The only retained #204-only source change outside the
already-adopted findings is a row-offset micro-optimization in texture upload; it has no worldgen or
lifecycle semantics.

### Cross-domain normalization census

`worldgen-normalization-census` inventories the selected overworld generator/source; reachable
biomes, configured/placed features, carvers, structures, structure sets, density functions;
registered dispatch types; codec round trips; resource-pack layers; and an isolated generator clone.
It uses registry codecs and typed holders for evidence. Its string-reference candidates are only a
conservative diagnostic because the same identifier can exist in multiple registries; production
dependency traversal must remain typed.

| Stack                     | Run                           | Active objects | Codec operation failures | Resource keys / overrides | Clone result                                                           |
| ------------------------- | ----------------------------- | -------------: | -----------------------: | ------------------------: | ---------------------------------------------------------------------- |
| FTF control               | `20260828T083033Z-a91fccffec` |            474 |                        0 |                1,000 / 25 | classes equal; 867/867 biome and 475/960 density mismatches            |
| Biomes O' Plenty          | `20260828T083415Z-4f3a23ed0c` |            959 |                        0 |                1,671 / 25 | possible-biome set differs; 867/867 biome mismatches                   |
| Biolith                   | `20260828T083505Z-9060bafaec` |            474 |                        0 |                1,000 / 25 | graph is identical to control; imperative decorator is not represented |
| Nature's Spirit           | `20260828T083549Z-3e2852492e` |            932 |                        0 |                1,550 / 81 | custom carvers/features exact; provider state absent from clone        |
| YUNG's Cave Biomes        | `20260828T083633Z-9fdd9c56e4` |            512 |                        0 |                1,039 / 25 | custom cave features/structure types exact; provider state absent      |
| Create NeoForge           | `20260828T083719Z-6428eca37f` |            478 |                        0 |                1,006 / 25 | custom ore feature and config placement exact                          |
| Terralith + Lithostitched | `20260828T083804Z-86133ba1b2` |          1,615 |                        0 |                2,465 / 88 | graph exact; 476/960 density mismatches after isolated FTF init        |
| Moderner Beta             | `20260828T083858Z-1ab6729e7e` |            304 |                        0 |                 1,079 / 0 | clone's first biome query throws: provider is null                     |
| Still Life + Lithosphere  | `20260828T083944Z-fa2bd504cc` |            794 |                        0 |                1,705 / 63 | coupled replacement graph exact; isolated FTF lifecycle diverges       |
| Wilder Wild               | `20260828T084039Z-2b83787e5b` |          1,239 |                        0 |                2,084 / 25 | one structure codec is not a canonical fixed point                     |

The graph test is broad but deliberately not interpreted as behavioral parity:

- The FTF control encodes and decodes every object exactly, yet the decoded generator loses all
  sampled biome behavior. `MixinChunkMap` brackets construction with a thread-local and initializes
  `RTFRandomState` only at `ChunkMap` tail; `MixinRandomState` otherwise substitutes zero-valued
  cell markers. Codec success cannot reconstruct this lifecycle.
- TerraBlender stacks expand the selected graph correctly, but provider selection lives outside it.
  BOP contributes 670 resource keys while its decoded possible-biome set still changes.
- Biolith changes selection without adding any selected resource or registry object to the control
  census. Registry enumeration cannot discover an imperative decorator's semantics.
- Moderner Beta's codec reconstructs the correct custom generator and source classes. Its normal
  Fabric `SERVER_STARTING` lifecycle calls `initProvider(seed)` on both; the codec does not. The
  isolated source therefore throws because `biomeProvider` is null. A generic runtime cannot infer
  this method or event from the codec.
- Wilder Wild calls FrozenLib's public `RandomPoolAliasApi` to add a trial-chamber alias. Decoding
  the already-mutated structure and encoding it includes the added target; decoding that result adds
  the target again. Twenty-nine of 30 structures reach a canonical fixed point, while
  `minecraft:trial_chambers` does not. Codec availability is not a clone-safety guarantee.

Minecraft's built-in dispatch registries cover biome sources, chunk generators, density-function
types, surface rules/conditions, features, placement modifiers, carvers, structure types, and
structure placements. Their public executable interfaces provide mod-neutral leaf boundaries:
`BiomeSource.getNoiseBiome`, `DensityFunction.compute`, surface rule/condition factories,
`PlacementModifier.getPositions`, `Feature.place`, `WorldCarver.carve`, `Structure.generate`, and
`StructurePlacement.isStructureChunk`. FTF can own stage execution without understanding each leaf's
implementation.

The selected dynamic graph includes biome, configured carver/feature, density, noise settings/noise,
placed feature, structure/set, pools/processors, presets, and level stems. Resource-pack layers can
attribute declarative files and show overwritten roots, but loader mutations are not resource layers
and a lower layer is not a semantically valid partial alternative.

### Pre-FTF failures

- Fabric RU 0.6.2 + Lithostitched 1.8.0-beta5 is behavior-qualified in a production-remapped server:
  256/256 chunks finish in `20260829T081235Z-0f35905d9b`. Its preview boundary is an explicit
  opaque-source diagnostic, not a bootstrap failure.
- NeoForge RU 0.6.2 + the latest compatible NeoForge Lithostitched release, 1.8.0-beta4, fails its
  required `BeardifierMixin` target before an FTF-owned seam (`20260829T083134Z-3880a6e275`).
- Current NeoForge Biolith 3.0.14 fails its required `MixinNoiseHypercube` targets missing
  `Climate.ParameterPoint.lambda$static$7` before FTF or preview initialization
  (`20260829T053245Z-93943bb298`).
- Current No Man's Land 1.5.12 contains a jar-in-jar Biolith 3.0.11 dependency, so omitting an
  external Biolith jar does not exercise a Biolith-free path. That current embedded path then fails
  No Man's Land's required `ChunkGeneratorStructureStateMixin` target before world creation
  (`20260829T054632Z-ea754cf01a`); its declared refmap is absent from the production jar.

These are current-release acquisition-pipeline results. Older artifacts are not retained as
substitute compatibility conclusions or production workarounds.

### Third-party lifecycle boundary

BWG 2.6.0's generated `world_generation.json` changes its next-start feature graph. With no config,
the default stack registers 25 biome modifications and generates a new world. If the file exists,
BWG constructs its config twice, calls its non-idempotent modifier initializer twice, registers 50
modifications, and a new world fails with duplicate BWG placed-feature identities. The same failure
was reproduced with FTF absent. Focused run `20260828T072705Z-04aa61a424` reported 25 distinct
duplicate placements before the cycle, without an observer failure. Primary BWG scenarios therefore
use a managed first-start control; FTF must not hide the third-party failure. See
`games/minecraft/investigations/reterraforged/analysis/bwg-2.6.0-config-bootstrap.md`.

### Lithostitched capability boundary

Current Fabric Lithostitched 1.8.0-beta5 registers codecs and biome-source types, but its final
`InjectorBiomeSource` behavior depends on an imperative injector/region lifecycle. The public codec
serializes the delegate source rather than the complete initialized injector state, `clone()` is a
shallow source operation, seed binding is mutable, and no public complete snapshot, reversible
activation, or fresh request factory is exposed. RU constructs this state through code/event/config
paths rather than a complete declarative injector resource graph. Public `getNoiseBiome` is a sound
executable boundary only for the already-realized owner; it does not make that mutable server root
safe to share with preview.

The runtime therefore mines all public declarative inputs it can, retains the realized source as an
opaque root for generation, and requires a provider-contract factory for an isolated preview owner.
It does not persist or replay historical TerraBlender integration data, scan private fields, call
internal injector managers, or infer replacement geometry from biome namespaces. NeoForge's current
required-Mixin failure remains outside any FTF owner and propagates normally.

## Runtime architecture

### Ownership model

`WorldgenEpoch` is the immutable server-side authority for one world bootstrap. It contains the
selected dimension stem, realized generator/source, frozen worldgen registry views, resource-layer
fingerprint, seed/settings identity, tag epoch, and capability results. Mutable samplers, random
states, noise chunks, provider tables, and thread locals are owned beneath the epoch and never
placed in identity records.

`PreviewRequest` is a separate owner built from the selected `WorldCreationContext`. It may use only
factories proven to create fresh request state. An already-initialized server root cannot be shared
with it, and an opaque custom root without a preview factory reports its affected preview facets as
unavailable. Preview consumes the same plan interfaces as generation; it does not initialize mods.

`TagEpoch` changes when reload rebinds registry tags. Minecraft loads and freezes WORLDGEN and
DIMENSIONS registry layers during world bootstrap. `/reload` rebuilds reloadable resources and
updates tags on the existing registries; it does not rebuild the active generator, biome source, or
`RandomState`. Plans containing late-bound tag lookups remain valid. Plans that compile tag
membership are invalidated and recompiled against the same `WorldgenEpoch`.

Every activation is owner-scoped and `AutoCloseable`, opened in declared deterministic order and
closed exactly once in reverse order. Partial-open failure rolls back already-opened state. No
process-global semantic registry or result cache is part of the runtime.

### Plan compiler

The compiler runs once per owner and produces a `WorldgenPlan` with separately typed domain plans:

1. Capture the selected final roots and typed holder graph. The final registry graph is execution
   authority; namespace and lower resource layers are diagnostic provenance only.
2. Discover registered dispatch types and public executable interfaces without inspecting object
   fields. Unknown implementations of known public types become opaque leaves.
3. Negotiate optional mechanism providers through a public loader-neutral SPI. Each provider
   declares exact facets, owner type, stage ordering, factory/snapshot semantics, and cleanup.
4. Compile normalized nodes, opaque leaves/roots, provider nodes, and unavailability into separate
   domain plans. A failure in one domain does not erase another domain's supported graph.
5. Validate required references, ordering, cycles, owner compatibility, and clone/factory safety.
   Codec round trip alone never establishes lifecycle or fixed-point safety.
6. Publish immutable plans plus a machine-readable capability/provenance report. Downstream code
   receives only domain interfaces and value objects.

The dependency graph is built from typed holders and codec nodes. String scanning, field names,
reflection, namespace inference, and configured-feature-level classification are prohibited.

### Generator ownership

FTF needs a registered generator root—preferably a `TerraForgedChunkGenerator` extending the vanilla
noise generator contract where that preserves ecosystem expectations—to own the public generation
stages. It should delegate unchanged behavior first, then execute compiled plans at explicit public
stage boundaries: noise fill, surface, carvers, biome decoration, and structures. This creates one
FTF seam instead of interjecting into arbitrary leaves globally.

Contained Minecraft access may still be necessary where vanilla does not expose enough state, but
third-party private internals are never a stage boundary. Existing leaf Mixins are retired only when
the owned stage has parity evidence; this is an ownership refactor, not a mechanical Mixin deletion.

FTF can import declarative noise settings and execute registered density/surface leaves beneath its
own root. It cannot generically merge the terrain semantics of an unrelated custom generator with
FTF terrain. Such a generator is either used as an opaque root in its own preset, adapted through a
public provider contract, or reported unavailable for FTF terrain composition.

### Domain compilation rules

- Biomes: preserve selected source behavior as an opaque root unless composition is declarative or a
  provider exposes candidates, order, weights, fallback, and ownership. Biome IDs do not identify
  the selecting provider or spatial domain.
- Density/noise: preserve the selected `NoiseGeneratorSettings` and typed density graph as a coupled
  root. No generic algebra exists for merging two density routers or overwritten roots.
- Surface: compile the active rule graph; registered custom rules/conditions execute as opaque
  leaves. Provider-specific surface hooks require their own capability.
- Carvers/caves: compile final biome carver steps and invoke registered carvers through their public
  interface. Cave-biome selection, carvers, placed cave features, and rescue/enclosure policy remain
  distinct nodes. The current production surface rescue is the interim behavioral authority; runtime
  ownership must preserve its eligibility, budget, same-column selection, reservation, enclosure,
  downstream placement, and RNG semantics before replacing its hooks.
- Placed features/ores: compile the complete typed DAG from biome step through every placement
  modifier, selector/decorator child, configured feature, target predicate, and public executable
  leaf. Preserve holder identity, modifier order, feature-filter position, and RNG consumption. A
  configured feature referenced by two placed pipelines never shares a pipeline decision.
- Placement geometry: known typed modifiers contribute separate X/Z and Y displacement envelopes;
  known configured features or explicit capabilities may contribute read and write footprints.
  Vertical displacement never implies horizontal risk. Unknown custom modifiers or feature
  footprints remain opaque and are ineligible for a spatial rewrite rather than being guessed from
  field names, reflection, or namespace.
- Placement ownership: an eligible transformed pipeline retains its authored candidate coordinates
  and random draws. The plan assigns each source-chunk/feature/attempt event one deterministic owner
  and executes it once at a stage with a proven complete halo or deferred buffer for its declared
  footprint. It does not clamp candidates into an interior rectangle. If complete traversal,
  ownership, or footprint closure cannot be proven, the realized vanilla pipeline runs unchanged and
  the spatial correction is reported unavailable.
- Structures: preserve structure sets, placements, structures, pools, processors, and aliases as a
  coupled typed graph. Non-fixed-point nodes run from the realized graph and are not codec-cloned.
- Diagnostics: every node records identity, mechanism, owner, capability state, first cause, and
  declarative resource layers where available. It does not claim loader mutation provenance that
  cannot be observed.

### Ordering, RNG, and conflicts

Ordering is a typed partial order over named stage contracts. Duplicate provider IDs, unknown
constraints, and cycles fail compilation. Incidental map iteration and registration replay are not
ordering mechanisms.

Generation RNG streams belong to the exact vanilla/FTF stage and pipeline order. Normalization must
not pre-sample, reorder, deduplicate by configured feature, or execute a leaf twice. Preview uses
separate deterministic request state and is never evidence that finished-chunk RNG/order is equal.

Candidate displacement, configured-feature writes, and biome/spatial ownership are separate facts. A
complete placement plan must prove all three before relocating execution. This is the common
boundary for Nature's Spirit cliff features, cave rescue, ores, and unseen mods using the same
mechanisms; none receives a mod- or biome-specific exception.

Resource precedence selects one active graph. Overwritten lower layers may be reported and diffed,
but are not automatically imported as compatible alternatives: a datapack can couple one biome to
density, noise, surface, features, structures, tags, pools, and processors. Partial composition is
allowed only through a typed operation whose closure and conflict behavior are proven.

No realized semantic state is cached across owners. The screen-scoped preview result cache keys
immutable tiles and sidecars by the complete selected graph, provider capability versions/facets,
seed/settings, tags, preset, data configuration, and biome identities. A changed dependency creates
a new `PreparedContext`; teardown closes the old request after its leases drain. Server tag reload
recompiles against the unchanged realized base graph and atomically installs a new plan under the
same `WorldgenEpoch`.

## Runtime implementation

The information-gathering boundary is closed. Public Minecraft registries, codecs, holders, and
executable interfaces feed an FTF-owned runtime on branch `feat/worldgen-compatibility-runtime` at
`eb40842`, based on upstream `4a3ab1c5e8f680dc996761908e8904aaca350eb4`. The production architecture
is:

1. `WorldgenEpoch`, `PreviewRequest`, and `TagEpoch` provide immutable server-bootstrap,
   request-local, and tag-binding ownership. Mutable sampler and provider state never crosses an
   owner.
2. `WorldgenCapabilityProvider` is the loader-neutral mechanism SPI. `WorldgenPlanCompiler`
   validates provider identity, owner support, typed ordering constraints, conflicts, and cycles;
   activation opens deterministically and rolls back or closes exactly once in reverse order.
3. `MinecraftWorldgenPlanCompiler` captures the final selected graph into separately typed source,
   biome, provider, selection-decoration, spatial, sampler, density, surface, carver,
   placed-feature, and structure plans. Capability reports distinguish normalized data, opaque
   leaves, opaque roots, provider contracts, and unavailable facets with the first concrete cause.
4. The registered `TerraForgedChunkGenerator` owns biome creation, density fill, surface building,
   carvers, structure starts, and placed-feature decoration. It preserves Minecraft's public leaf
   execution, holder identity, feature-sort schedule, registry structure order, and stage RNG.
5. Density and surface retain the selected `NoiseGeneratorSettings` graph as a coupled root. A final
   exact vanilla `NoiseBasedChunkGenerator` is normalized only when its public density graph
   contains an FTF marker. Existing FTF roots and custom generator implementations remain unchanged;
   the latter are opaque roots unless a provider supplies a safe factory.
6. Preview compiles from the selected `WorldCreationContext` graph, obtains fresh request-owned
   activation and sampler state, and consumes the same domain plans as generation. One backend
   surface-tile operation owns coordinates, exact surface/quart mapping, worker-local samplers and
   caches, cancellation, and scheduling. Its compiled per-facet execution contract defaults to
   owner-serial and permits isolated parallel reads only when every queried facet explicitly
   declares immutable shared state and worker-confined mutable state. The widget receives only
   resolved biome values and never provider mechanics. Per-mod preview integration maps, manual mod
   initialization, Biolith/Lithostitched private accessors, and optional third-party Mixins are
   absent.
7. The contained TerraBlender mechanism provider snapshots public registered region order, stable
   IDs, positive weights, climate tables, and the index-zero default table. Weighted rendezvous
   assigns one provider to each final FTF cell; deferred results query the captured default table
   with the same climate target. Native TerraBlender region noise does not execute on the FTF path.

Tag reload retains the worldgen epoch and realized base graph, advances `TagEpoch`, recompiles
tag-dependent operations, activates the replacement, and atomically rebinds generator and
`RandomState`. Compilation always reads the root's realized pre-plan biome settings; the previous
plan is never used as compiler input or modified a second time. `/reload` still does not rebuild the
worldgen or dimensions registries.

## Acceptance gates

### Core and arbitrary-mod behavior

- Deterministic compilation; duplicate/cycle rejection; typed-reference validation; immutable
  reports; exact first cause; partial-open rollback; nested/concurrent owners; close-once/reverse
  cleanup, including cleanup exceptions.
- Synthetic unseen mods for every capability state: registered custom leaf, declarative graph,
  lifecycle-dependent custom root, explicit provider factory, hidden imperative mutation,
  non-fixed-point codec, and two placed pipelines sharing one configured feature.
- No test identifies a mod by namespace/class/version to obtain ordinary mechanism support. Removing
  a corpus mod and adding an unseen implementation of the same public type must need no code change.
- Unsupported domains fail closed with actionable diagnostics while independent supported domains
  continue. Bootstrap/Mixin failures before an FTF seam propagate unchanged.

### Behavioral parity

- Exact selected graph and registry-type census before/after for control, TerraBlender, Biolith,
  Terralith, Still Life, Wilder Wild, YUNG's Cave Biomes, Create, and a custom generator.
- Direct query, preview, and finished-chunk biome IDs across surface and cave Y; concurrent
  previews; preview close followed by integrated/dedicated generation; server-world teardown and new
  epoch.
- Density samples, generated height/block tiles, surfaces, carver masks, cave-biome palettes,
  feature invocation/write counts, ore distributions, structure starts/placements/pools, and exact
  deterministic world hashes over fixed seeds/windows.
- Feature and structure ordering plus RNG-consumption probes. No duplicate active features, rescue
  false positives, or codec-clone side effects.
- Placed-feature spatial rewrites compare exact candidate/rescue positions and finished writes, not
  only aggregate counts. Cave-rescue probes reconcile policy entries, budget skips, scheduled and
  physical searches, cache reuse, discovered surfaces, enclosure decisions, and successes across
  sparse, reference-height, and maximum-height fixtures.
- `/reload` tag rebinding tests and new-world/full-bootstrap tests; no claim that `/reload` rebuilds
  worldgen registries.
- Fabric and NeoForge parity where the third-party stack itself reaches an FTF-owned seam.

### Spatial policy

- Provider assignment is a pure function of world/plan identity, the final FTF biome-cell lattice
  coordinate, stable provider identity, and registered positive weight. Use deterministic weighted
  rendezvous assignment: derive an independent uniform `u` in `(0, 1]` from the plan salt, cell key,
  and provider ID; select the provider minimizing `-log(u) / weight`, with stable provider ID as the
  exact-tie breaker. A provider therefore has theoretical share `weight / totalWeight`, and adding
  or removing a provider does not remap cells whose winning existing provider is unaffected.
- There is no finite-window quota or corrective reassignment. Weight conformance is established by
  the assignment construction and deterministic property tests; multi-seed/window counts are
  distribution diagnostics and are evaluated against their multinomial sampling bounds, not an
  arbitrary required percentage from one map.
- Preserve TerraBlender's public stage semantics: snapshot regions in registration order, select a
  provider domain, query that provider's climate table, and resolve `DEFERRED_PLACEHOLDER` through
  the index-zero default table with the same climate target. Invalid identity, weight, table, or
  default state fails the provider facet closed instead of inventing a fallback.
- A provider ID is constant for every query resolving to the same final FTF cell key, including
  preview and generation. Provider changes with an unchanged FTF cell key and provider-only raw-grid
  edges must both be exactly zero. Existing FTF cell-edge values and edge re-sampling are the
  transition policy; no TerraBlender-specific transition threshold is introduced.
- Connected-component, perimeter/area, small-component, region-share, domain-span, transition, and
  FTF-edge metrics from retained raw grids.
- Ice Spikes plus region-variant biomes as sentinels, not biome-specific special cases.
- Surface, underground/cave, density, and feature checks remain independent from spatial selection.
- Client/visual QA follows numeric parity and measures transitions/micro-biomes rather than serving
  as the sole authority.

### Build and artifact

- `common:test`, Fabric build, NeoForge build, clean-worktree verification, and production-JAR
  contamination inspection.
- Benchmark compiler/bootstrap cost, generation windows, memory retention, and preview requests;
  profile before attributing a regression.
- Latest exact Minecraft 1.21.1 loader releases reacquired and audited under release policy, or
  release-or-prerelease only when the project publishes no compatible stable release. Older pins
  remain labeled failure-boundary/regression controls only.

### Current acceptance evidence

- Core unit coverage is 118 passing common tests. It covers deterministic provider ordering,
  duplicate and cycle rejection, immutable plans/reports, first-cause serialization, activation
  rollback and reverse close, weighted rendezvous properties, plan indexing, preview lease ownership
  and pooling, purpose-scoped compilation, shared exact tile lookup, exact owner-keyed quart/cell
  memoization, request-owned source negotiation, ordered exact provider-entry deduplication,
  custom-root normalization boundaries, feature classification, ore contracts, explicit query-mode
  compilation, conflict/failure downgrade, deterministic row-band execution, cancellation, and exact
  worker-local quart caching.
- The investigation harness has 71 passing tests, including scenario cleanup, process identity,
  recovery, production Fabric launch parsing, RCON, probe protocol, tiling, generic source spatial
  analysis, comparison, and production-artifact inspection.
- Fabric and NeoForge BOP preview parity are exact over 59,536 sampled quart columns per loader with
  zero mismatches, zero provider fallbacks, and zero underground preview selections on clean runtime
  commit `8f5ab0a` and upstream `4a3ab1c`: `20260829T161825Z-195e750faa` and
  `20260829T161345Z-f793dd2291`. Both use the prepared-tile request path and
  `selected-graph-with-request-patches` authority; their probe phases are 8.059 s and 8.256 s.
- Clean Fabric/NeoForge zoom-150 batch equivalence runs `20260829T193326Z-824fec22c1` and
  `20260829T193455Z-fbff21db65` compare all 65,536 returned pixels with the former serial
  `TileBiomeRequest` path and repeat the batch. Both report zero serial/parallel mismatches and zero
  repeat differences. Batch time is 2.84/2.96 seconds versus 34.80/35.05 seconds serial, a
  12.26x/11.85x speedup without approximate stride or omitted queries.
- Clean Fabric/NeoForge finished-chunk batch runs `20260829T193621Z-b8d881fc67` and
  `20260829T193736Z-eaa6ca4c1e` resolve one complete zoom-1 tile in 62.49/69.72 ms and compare 4,096
  surface quart columns across 256 finished chunks per loader. Both have zero biome mismatches, zero
  provider fallbacks, and zero underground preview selections.
- Fabric and NeoForge reload runs `20260829T092022Z-0d31258cb1` and `20260829T092120Z-c8a8701895`
  preserve the epoch and bootstrap inputs, advance the tag sequence once, replace the plan
  atomically, retain 2,625 feature pipelines, 159 carver pipelines, and 34 structures, generate
  after rebind, and verify cleanup.
- The final control census `20260829T002348Z-225af2e83e` is complete for 474 codec objects with zero
  JSON mismatches or codec-operation failures. Still Life `20260829T000043Z-013c475db9` proves that
  a datapack-selected exact vanilla noise root containing the FTF density marker is normalized;
  Moderner Beta `20260829T000257Z-0a3b243e61` proves a registered custom root remains unchanged.
  Terralith/Lithostitched `20260828T234556Z-553c9c93f9` and Wilder Wild
  `20260829T000152Z-816f2db108` retain complete selected-graph, feature, and composition checks.
- The 512-by-512 BOP spatial run `20260829T002435Z-fdfdfafb49` samples 262,144 points over 4,088
  blocks per axis. Provider-only adjacent edges are exactly zero, finished-chunk parity is 16/16,
  and the public provider contract is active. Provider transitions are therefore a subset of final
  FTF cell transitions.
- Current-upstream Nature's Spirit placement run `20260829T005459Z-eabe670800` completes 16/16
  chunks, preserves the authored 0..15 `InSquarePlacement` distributions, and identifies the 65
  false-positive candidates of #202's reflective heuristic. YUNG's cave biomes, Biolith, Create,
  standard and custom ore stacks, structure ordering, failure-boundary controls, and native
  TerraBlender comparison geometries retain their focused run IDs in the evidence locations below.
  Latest NeoForge RU/Biolith stacks that fail before an FTF seam remain propagated failures rather
  than synthesized compatibility.
- `./gradlew --no-daemon build` passes for common, Fabric, and NeoForge from clean commit `eb40842`
  on upstream `4a3ab1c`. Production inspection reports both loader JARs clean. They contain the
  generator root, owner/plan types, and capability service, with no probe sentinel, injected probe
  class, probe Mixin configuration, generated probe metadata, or PR 202's `MixinSquarePlacement`.
  Source commit, upstream base, build command, inspection result, and retained run IDs identify an
  accepted build; ephemeral local archive hashes are not maintained.

Current tooling validates 42 exact artifacts and 30 source records. The live audit on 2026-08-29
uses the exact 1.21.1 loader and stable-first release policy: BOP 21.1.0.14, TerraBlender 4.1.0.8,
GlitchCore 2.1.0.2, and Still Life 0.1.1 use their latest compatible prerelease because no
compatible stable exists; Biolith 3.0.14, Nature's Spirit 2.2.5, YUNG's Cave Biomes 3.1.1, Create
6.0.10, Terralith 2.6.2, Wilder Wild 4.2.1, and Moderner Beta 4.1.10 use their latest compatible
stable. RU 0.6.2 uses Fabric Lithostitched 1.8.0-beta5 and NeoForge 1.8.0-beta4 under the same
release-channel policy. Older acquired pins remain diagnostic-only controls and are never used as
production compatibility substitutes.

## Provider contracts

- FTF SPI: loader-neutral, mechanism-oriented facet registration with immutable snapshot/factory,
  owner/lifecycle, ordering, cleanup, and diagnostic contracts. Consumer mods are not named by the
  downstream plan API.
- TerraBlender: public `Regions` and `Region` APIs expose ordered stable IDs, positive weights, and
  the regional parameter entries produced by `addBiomes`. `IExtendedParameterList` confirms the
  stage contract: choose a regional tree, query it, and resolve `DEFERRED_PLACEHOLDER` through the
  index-zero default tree. A contained mechanism module snapshots those values; FTF, not
  TerraBlender's uniqueness noise, owns spatial assignment.
- Biolith: immutable owner-scoped replacement/sub-biome query or snapshot with documented seed,
  ordering, cleanup, and concurrency semantics. Registration-only APIs are insufficient.
- Lithostitched: public request-owned source/injector factory or reversible snapshot plus seed
  binding, ordering, cache, and cleanup semantics.
- Custom generators/sources: an optional FTF capability provider may supply a fresh initialized
  preview factory or typed composition facets. Without one, the live instance remains an opaque
  root.
- Contributor provenance is not required for execution. If a future diagnostic needs it, obtain it
  from loader/resource metadata rather than namespace inference.

## TerraBlender spatial ownership

`/var/home/scott/Desktop/Tb Integration.txt` correctly identifies that TerraBlender's native
weighted region map and FTF's cells are independent and that replaying provider registrations into
FTF cells would risk weights, size, order, and fallback. Public mechanism-level integration is
possible without private TerraBlender Mixins. The runtime metrics also establish that native
TerraBlender-only boundaries are behavior-bearing and receive interior-like FTF edge values, so
FTF's current transition shaping does not cover them.

The target is a public TerraBlender mechanism provider that snapshots registered tables, weights,
fallback, and ordering into generic plan data. FTF's spatial plan assigns one provider to each final
FTF biome-cell key and supplies the existing FTF transition facts used by biome selection, preview,
diagnostics, and other consumers. The provider table selected for a cell is queried with FTF's
climate target; a deferred placeholder is resolved through the captured default table. No downstream
consumer sees TerraBlender or a mod-specific region type.

Native TerraBlender geometry and documented size coupling remain evidence controls. Neither
satisfies the product contract because both leave final provider boundaries outside FTF's spatial
authority. The implementation must not hardcode BOP, Nature's Spirit, Ice Spikes, or another
consumer. Runtime topology does not show Ice Spikes to be uniquely oversized; its repeated
provider-table slots make it a useful cross-domain sentinel. The screenshot's broader
observation—micro-biomes and abrupt transitions when independent region fields do not align—is
supported by the boundary metrics. Spatial design is no longer an information-gathering question:
the FTF cell is the ownership unit, weighted assignment is deterministic and isolated from
generation RNG, registered weights define the theoretical distribution rather than a finite-map
quota, default-table fallback preserves the provider contract, and provider-only boundaries are
forbidden. The production runtime implements that contract; the current acceptance measurements
above are its authority. Native TerraBlender geometry remains only a regression/comparison control.

## Evidence locations

- Scenarios: `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/`
- Artifact/source catalog: `.squinch/games/minecraft/third-party/artifacts.toml`
- Raw retained runs: `games/minecraft/investigation-state/runs/`
- Normalization probe:
  `games/minecraft/investigations/reterraforged/probes/worldgen-normalization-census/`
- Normalization analysis:
  `games/minecraft/investigations/reterraforged/analysis/worldgen_normalization_analysis.py`
- Spatial probe: `games/minecraft/investigations/reterraforged/probes/spatial-compatibility/`
- Spatial analysis: `games/minecraft/investigations/reterraforged/analysis/spatial_grid_analysis.py`
- Third-party source: `games/minecraft/reference/sources/1.21.1/mods/`
- Cave interaction probe:
  `games/minecraft/investigations/reterraforged/probes/in-square-cave-interaction/`
- Cave interaction scenarios: `rtf-pr202-cave-rescue-interaction.toml`,
  `rtf-pr202-cave-rescue-interaction-natures-spirit.toml`,
  `rtf-pr202-natures-spirit-cliff-interaction.toml`, `rtf-cave-rescue-high-bop.toml`,
  `rtf-cave-rescue-high-bop-pr202.toml`, `rtf-cave-rescue-high-bop-disabled-control.toml`, and
  `rtf-cave-rescue-high-bop-cost.toml`
- Cave downstream authority: production `20260828T145308Z-318c55444f`, PR #202
  `20260828T150806Z-d214e0a525`, and sparse production `20260828T145554Z-15fc864b54`
