# FreeTerraForged resumption index

This file routes active work. Read every linked plan required by the task before changing an
implementation or compatibility conclusion. Live Git, dependencies, and retained artifacts supersede
recorded pointers.

## Worldgen compatibility runtime

- Product and architecture contract:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Active completion plan:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/compatibility-runtime-completion.md`
- Concept:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/biome-selection-and-compatibility-runtime.md`
- Invariants:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/compatibility-invariants.md`
- Worktree: `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`
- Branch: `feat/worldgen-compatibility-runtime`
- Current published branch head: `2c2729c64912a297a76d619bcc2afd7bf719d565`
- Recorded upstream base: `upstream/1.21.1` at `4a3ab1c5e8f680dc996761908e8904aaca350eb4`

The runtime is an ETL boundary. It discovers stable worldgen inputs, normalizes complete accepted
semantics into immutable FTF-owned plans, and makes FTF the only runtime authority. Preview,
generation, diagnostics, locate, possible-biome enumeration, feature sorting, and structures remain
zero-knowledge. Named mods are a falsification corpus, never an allowlist.

### Active objective

Complete the nine dependency-ordered workstreams in `compatibility-runtime-completion.md`.
Correctness and thoroughness determine completion; elapsed time and diff size do not. Execute one
vertical workstream at a time, remove superseded internal paths, and validate its complete
ownership, lifecycle, failure, reload, concurrency, loader, and packaging contract before advancing.

The work is an in-place pre-release refactor. Previously valid presets must continue to load with
intentional defaults and complete copy/construction behavior. Internal classes, APIs, plan shapes,
caches, Mixins, and historical runtime implementation behavior are not compatibility contracts and
must not be retained when they obstruct the correct design.

### Current authorization boundary

The user has authorized autonomous implementation of all nine workstreams through every acceptance
gate. Continue until the program completion gate is satisfied or a concrete external blocker makes
further safe progress impossible. Do not create commits or push further changes until the user
explicitly instructs it; implementation authority does not imply commit or push authority.

Do not start another Minecraft runtime while either retained Fabric JVM (`54343` or `91098`) remains
blocked in uninterruptible kernel teardown. Source tests, builds, artifact inspection,
documentation, and other non-runtime work may continue. Once the host is healthy, rerun every Fabric
runtime gate whose retained run did not complete cleanup; a generated chunk followed by failed
process cleanup is not a complete lifecycle pass.

The healthy-host rerun must include the actual `WorldCreationUiState` client preview path with the
current RU/Lithostitched stack. Exercise repeated regeneration, cancellation, dimension/datapack
changes, and server creation after preview. A source test that invokes the negotiator directly does
not prove this lifecycle. The same current-source matrix must exercise custom-source factories,
owner-serial sampler stages, generator-root ownership (including positive and negative controls),
independent multi-dimension reload publication, installed-unused mechanisms, bounded provider and
unknown-injector failures, C2ME tall-world generation, and packaged optional-absent/mixed-stack
starts before runtime completion can be claimed.

### Resume procedure

1. Inspect parent and compatibility-worktree status, branch/remote tips, upstream, dependency
   catalog, and relevant retained artifacts.
2. Read the product contract and the complete active workstream plan.
3. If upstream or a latest exact-version dependency moved, reacquire it through
   `tooling/squinch third-party` and rerun every affected behavior-bearing gate.
4. Continue from the first incomplete dependency-ordered workstream. Shared probe work is permitted
   only when required to prove that workstream.
5. Use `tooling/squinch mc-investigate` and repository-relative scenarios; never use a personal
   launcher profile.
6. Retain raw observations, logs, grids, calculations, commands, hashes, and cleanup state in run
   artifacts. Keep durable docs current-state and forward-facing.

### Supported and explicit boundaries

- Minecraft registry and codec graphs supply public multi-noise candidates, density/settings,
  surface rules, carvers, biome generation settings, placed features, and structures.
- Loader and library mutations are acquired generically when they are complete before the relevant
  owner compiles. Fabric biome modifications and NeoForge biome modifiers materialize in biome
  generation settings. FrozenLib finalizes its surface callbacks into the selected
  `NoiseGeneratorSettings.surfaceRule()` before a server epoch compiles; surface is not a biome-only
  preview facet. Method-body-only patches that have not materialized remain outside this contract.
- TerraBlender supplies public Overworld provider-domain inputs; FTF owns spatial assignment.
  Applicability follows TerraBlender's public Overworld-regions dimension-type tag rather than a
  literal level-stem key.
- Qualified Lithostitched acquisition resolves a completed creation graph into immutable snapshots;
  preview never invokes callbacks.
- Density-function holder wrappers are graph edges, not dispatchable density-function values.
  Acquisition visitors rebind the referenced value and never call the deliberately unsupported
  `HolderHolder.codec()` method on the edge itself.
- Qualified Biolith acquisition normalizes accepted additions, removals, replacements, and supported
  built-in sub-biome criteria.
- Custom roots are supported through a request-owned `BiomeSourcePlanInput` or pure
  `BiomeSourcePlanInputFactory` with complete possible outputs and a declared query mode. Opaque
  roots without that contract, custom Biolith criteria without a complete immutable contract,
  unknown Lithostitched injector semantics, and private third-party return-value patches remain
  explicit unsupported boundaries until a sound mechanism seam exists.
- Full configured-height noise generation is the authoritative fallback. Any future bounded density
  extent must analyze the finalized router conservatively and return `FULL_HEIGHT` for unknown
  semantics; density extent never clips biome sampling.
- Server ownership is selected by the registered `TerraForgedChunkGenerator` root, not by finding a
  particular FTF density-function node. A custom or vanilla density graph beneath that root still
  initializes the complete compatibility runtime. Conversely, an FTF density node beneath a non-FTF
  generator is rejected explicitly because it has no owner context.
- A preview cache key retains the exact frozen registry view and selected stem used by its worker;
  asynchronous construction never rereads the live world-creation graph. Sampler target transforms
  are immutable plan stages evaluated at query time, and `OWNER_SERIAL` is an executable owner gate
  rather than descriptive metadata.
- Resource, tag, and contribution revisions publish together. A failed or regressing replacement is
  retained as an owner-scoped rejection while the prior immutable plan stays active; it does not
  prevent independent FTF dimensions from processing the same resource reload.

### Upstream PR 208 gate

When PR 208 lands, inspect its final merged commits. Keep the compatibility runtime's unified
source, pre-server Lithostitched acquisition, and plan-owned possible-output closure; do not restore
the old global raw-field `MultiNoiseBiomeSource.possibleBiomes()` interception. Reacquire current
exact mechanism releases and rerun the cross-loader no-server preview, mixed-provider/decorator,
finished-chunk, reload, locate/query, stored-biome, possible-output, and feature-sort gates
specified by the canonical plan.

## Other FreeTerraForged plans

- Cellular archipelago redesign:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/archipelago-redesign.md`
- Configurable shorelines:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-shorelines.md`
- Configurable strata:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-strata.md`
- Branch/worktree map: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`

## Shared references

- Investigation guide: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Third-party catalog: `.squinch/games/minecraft/third-party/artifacts.toml`
- Canonical fixtures: `games/minecraft/investigations/reterraforged/fixtures/`
- Retained runs: `games/minecraft/investigation-state/runs/`
- Runtime tooling: `tooling/squinch mc-investigate --help`
- Acquisition tooling: `tooling/squinch third-party --help`
