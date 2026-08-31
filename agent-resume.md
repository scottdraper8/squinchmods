# FreeTerraForged resumption index

This file routes active FTF work. Read the linked plan before changing an implementation or
compatibility conclusion. Live Git, dependency state, and retained artifacts supersede recorded
pointers.

## Worldgen compatibility runtime

- Plan: `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Concept:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/biome-selection-and-compatibility-runtime.md`
- Invariants:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/compatibility-invariants.md`
- Worktree: `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`
- Branch: `feat/worldgen-compatibility-runtime`
- Recorded base: `upstream/1.21.1` at `4a3ab1c5e8f680dc996761908e8904aaca350eb4`

The branch contains the Runtime Compat Layer MVP. It treats supported worldgen mechanisms as peer
inputs, copies their accepted data into immutable FTF-owned containers and typed plans, and makes
FTF the only runtime authority for selection, spatial layout, ordering, preset behavior, and
execution. Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting,
and structure predicates consume the same FTF-owned runtime source and plan state.

The biome-selection pipeline has exactly one candidate provider, zero or more deterministically
ordered decorators, and one final FTF surface or underground policy. Candidate operations apply once
to the selected root domain. TerraBlender provider domains retain their own candidate tables, and
FTF assigns domains to its warped biome cells so provider boundaries respond to FTF biome size and
warp. Carvers and placed features compile from the final possible-biome closure.

### Supported mechanism boundary

- Minecraft registry and codec graphs provide the base candidate, density, surface, carver, feature,
  and structure inputs supported by their public contracts.
- TerraBlender contributes public region IDs, weights, registration order, climate tables, and the
  default fallback. It is optional and has no downstream execution path.
- Lithostitched's real finalizer runs once against codec-cloned dimensions at the completed
  pre-server creation-graph boundary. Its stable public event output and finalized injectors become
  an immutable graph-bound snapshot; preview reads it without callbacks, and later server
  finalization for the same graph consumes the frozen emissions instead of invoking listeners again.
- Biolith additions, removals, and direct replacements are captured when accepted and are available
  to pre-server preview. Data-origin registrations are replaced on data reload; code registrations
  remain process-owned without duplicate accumulation.
- Applicability is selected-creation-graph and facet scoped. An installed mechanism with no
  applicable contribution does not claim or fail a facet.

### External API boundaries

- Biolith sub-biomes lack an immutable request-owned criterion snapshot or factory covering world
  access, neighbor queries, alternate output, seed/noise, ordering, reload, and concurrency.
- No Man's Land `1.5.12` cave placement patches Biolith's internal replacement return and exposes no
  stable registration or finalized-plan snapshot. It remains unsupported without a per-mod Mixin.
- A third-party failure before FTF owns the selected world remains a dependency boundary, not an FTF
  capability failure.
- Support for biome selection does not imply support for density, surface, carver, feature, or
  structure behavior; each facet keeps its own contract.

### Resume procedure

1. Inspect the worktree status, branch and remote tips, dependency catalog, and relevant retained
   artifacts.
2. If upstream or a latest exact-version dependency moved, reacquire it with
   `tooling/squinch third-party` and requalify every affected behavior-bearing gate.
3. Continue only from the canonical plan's current unsupported boundaries or a newly reproduced
   current-tip defect. Do not reintroduce deleted preview adapters, runtime source interception,
   callback replay, private-field inference, namespace dispatch, or consumer-specific Mixins.
4. Keep raw observations, logs, grids, and calculations in retained artifacts. Keep this file and
   the concept pages current-state only.

Use retained manifests' source-tree and dirty-patch fingerprints when matching evidence; commit IDs
are not stable evidence keys after a history rewrite.

### Lithostitched pre-server acquisition

Latest exact releases are RU `0.6.2`, Lithostitched `1.8.0+beta5` on Fabric and `1.8.0+beta4` on
NeoForge, Biolith `3.0.14`, and No Man's Land `1.5.12`. The latest audit and catalog validation
pass.

The production boundary is generic: `WorldgenPreServerFinalizer` advances providers from the
completed `WorldCreationContext`; preview has no Lithostitched or RU path. The Lithostitched
provider clones every selected dimension source through the public codec, runs the real finalizer,
freezes code injectors and regions, requires repeatable ordered output, and publishes immutable
snapshots containing no source, registry, generator, or callback. Failure is contained as
`lithostitched_pre_server_finalization_failed`. Late event registration invalidates the graph;
request seed changes rebind copied density declarations without callback replay.

Actual pre-server passes are `20260831T103000Z-pre-server-ru-immutable-fabric` and
`20260831T103500Z-pre-server-ru-immutable-neoforge`; both use seed `12345`, run with no server
present, contain 19,211 RU pixels, and produce grid hash
`5e67d1607757b600bd7a06478d379b8b978b49d9c7f8292b0c3bedd9ad735717`. Installed-unused control
`20260831T102500Z-pre-server-lithostitched-unused-final-fabric` contributes no Lithostitched nodes.
Serial/parallel equivalence is `20260831T095058Z-24a7a965b4`; finished-chunk parity is
`20260831T095227Z-8bbae55c36`; reload is `20260831T095315Z-52330c3942`; final mixed runtime
ownership is `20260831T100956Z-27afb0d091`. Clean packaged no-TerraBlender starts are
`20260831T101937Z-197d3ca27b` on Fabric and `20260831T102031Z-e601c7afec` on NeoForge.

Upstream PR 208 is a pending landing gate, not a patch to cherry-pick. At reviewed draft head
`cb654424b2d8b4d848aafd866c3d5280f4f2666e`, its only net change bypasses
`MultiNoiseBiomeSource.possibleBiomes()` through the raw parameter field. When it lands, inspect the
final diff, keep the compatibility branch's deleted legacy source Mixin deleted, retain pre-server
Lithostitched acquisition and plan-owned possible outputs, reacquire latest exact dependencies, and
rerun actual no-server Biolith + Lithostitched + RU previews on both loaders plus the mixed
TerraBlender/Terrestria stack. NML cave/sub-biome behavior remains explicitly unavailable until NML
or Biolith publishes a complete stable snapshot/factory contract; the PR's NML screenshot does not
change that boundary.

### Flow-settings ownership benchmark

The completed comparable benchmark covers the serialization and runtime cost of three historical
implementations:

1. `upstream/1.21.1` at `4a3ab1c5e8f680dc996761908e8904aaca350eb4`;
2. the compatibility runtime at `b65a5312ca93efcc7d28dca761d1fe85bd01b114`; and
3. the world-owned settings candidate that is now part of the compatibility branch.

Commit `19571cafde0bf3409577a4ad9db13e664b83732a` makes the corrected ownership model official. It
stores one immutable flow-settings snapshot on each `Level`, initializes it from that world's
`RTFRandomState`, removes `RTFFlowSettings` from chunk NBT and `ChunkFlowField`, and synchronizes
settings once per player and dimension or when they change. River flow grids remain chunk-owned. The
common test suite and clean Fabric and NeoForge production builds pass.

The retained benchmark probe is
`games/minecraft/investigations/reterraforged/probes/flow-storage-benchmark`. The original scenario
snapshots remain inside each retained run; the one-off active scenario definitions were removed
after promotion. Each uses seed `3216933670`, the `vanilla-depth-maximum-ocean` fixture, and five
disjoint 16 by 16 finished-chunk windows, for 1,280 chunks per variant. The probe records
river-chunk counts, `RTFFlowSettings` tag counts, exact flow-only uncompressed and deflated NBT
sizes, and repeated tag and NBT-write timings.

Use fresh healthy-host runs `20260831T055219Z-9d36310059` (upstream), `20260831T055440Z-045904af9c`
(runtime), and `20260831T055716Z-080b316913` (world-owned) for the comparison. All cover 1,280
finished chunks and completed cleanup. The corrected NeoForge smoke is
`20260831T060024Z-1c0775185b`. The exact distributions, calculations, source deductions, and limits
are retained in
`games/minecraft/investigation-state/flow-settings-benchmark/comparison-20260831.md`.

The complete packet and persisted-storage follow-up uses
`games/minecraft/investigations/reterraforged/probes/flow-storage-network`; its original scenario
snapshots also remain in the retained runs. Retained runs are `20260831T062824Z-069f7336bb`
(upstream), `20260831T063052Z-69ab1b7f6c` (runtime), and `20260831T063318Z-e447085c6b`
(world-owned), all with probe content
`de5237715e0c370cd3095429660d61ade6dfd1a7d5d1349b639a2bbcc5bc137a`. All observed the same 23 river
chunks and identical flow-grid digest. Runtime used 2,032 flow wire bytes. World-owned used 2,009
flow wire bytes plus a 37-byte settings wire frame, so it was 14 bytes larger for the first 23
chunks and saves one measured wire byte per later flow chunk until another settings sync; break-even
is the 38th flow packet per sync. Removing settings from chunk NBT saves 437 uncompressed bytes and
289-294 deflated bytes across the 23 river chunks. It reclaimed one 4 KiB sector in each
candidate-context counterfactual, but sector savings are boundary-dependent.

The measured conclusion is narrow: the world-owned candidate removes 19 uncompressed flow-only NBT
bytes per river chunk and lowers the pooled synthetic tag-plus-NBT-write median from 111.37720 to
74.63827 ns/op. Complete packet encoding shows a small first-sync bandwidth cost followed by a
one-byte-per-measured-flow-packet saving. The five generation windows do not show a generation-speed
improvement, sector allocation cannot be extrapolated from the observed boundary crossing, and no
object-memory saving is claimed without an object-layout measurement.

Focused acceptance covers the promotion gates. Enabled Fabric run `20260831T074811Z-68582b3abd`,
disabled Fabric run `20260831T075047Z-87ef82b1ce`, and enabled NeoForge run
`20260831T075648Z-e6d2a0292f` prove per-Level ownership, old/no-settings NBT handling, enabled and
disabled preset behavior, reload identity, real payload dispatch, duplicate suppression, dimension
transitions, independent Level settings, and unchanged river-grid digest. Packaged production runs
`20260831T080025Z-ac5db66e9e` (Fabric) and `20260831T080311Z-4295c5db1d` (NeoForge) repeat the
loader-specific sync and reload gates from the clean official commit; Fabric additionally reports
zero mismatches across 256 finished-chunk preview samples. The reusable acceptance scenarios now
target the official compatibility worktree.

Do not use `20260831T044952Z-7dcc20f48f` for the cross-variant comparison because the host later
developed blocked kernel tasks and extreme load. Retain `20260831T044450Z-c056f4da8b` as a failed
JFR/cleanup diagnostic and `20260831T045433Z-969e06cb96` as a timed-out runtime attempt.

Benchmark-only native/network diagnostics are retained under
`games/minecraft/investigation-state/flow-settings-benchmark`; they are not production inputs and
must not be used on a healthy host.

## Cellular archipelago redesign

Plan: `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/archipelago-redesign.md`

No implementation branch exists. The target is a cellular island model with deterministic island
identity, real-block shoreline distance, distance-based shelf/beach/land bands, and stable
whole-island continent clearance. Use seed `3216933670`, the canonical fixtures, the default-depth
control, and the known regression area around `(230250, 163350)`.

## Configurable shorelines and strata

- `feat/configurable-shorelines` needs visual/product QA and rebasing. Read
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-shorelines.md`.
- `feat/configurable-strata` needs product QA, resolution of its remaining deepslate/default/UI
  policy, and rebasing. Read
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-strata.md`.

## Shared references

- Branch/worktree map: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Engineering wiki: `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/README.md`
- Canonical fixtures: `games/minecraft/investigations/reterraforged/fixtures/`
- Investigation workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Third-party catalog: `.squinch/games/minecraft/third-party/artifacts.toml`
- Retained runs: `games/minecraft/investigation-state/runs/`
- Runtime tooling: `tooling/squinch mc-investigate --help`

Never run Minecraft from a personal launcher profile. Preserve unrelated parent and worktree
changes.
