# FreeTerraForged resumption index

This file is a routing index for unfinished FTF work. Read the linked plan completely before
changing its conclusions or implementation. Live Git/worktree state is authoritative when a commit
or status below has moved.

## Cellular archipelago redesign

Active plan:

`.agent-docs/games/minecraft/mods/FreeTerraForged/plans/archipelago-redesign.md`

No implementation branch exists. The redesign replaces alpha-derived island placement with a
cellular model that provides deterministic island identity, real-block shoreline distance,
distance-based shelf/beach/land bands, and stable whole-island continent clearance. Do not ship an
isolated warp-strength reduction or an intermediate island relocation that omits the shelf and
clearance work.

Use seed `3216933670`, the canonical archipelago fixtures, a default-depth control, and the known
regression area around `(230250, 163350)`. Validate continuity, real-block shelf slope, island
count/footprint, whole-island clearance, determinism, chunk boundaries, and generation cost.

## Worldgen compatibility

Single source of truth:

`.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`

The active target is a general FTF-owned worldgen ingestion and normalization layer, not a
biome-preview adapter registry. Supported public/registry/codec-defined inputs should become typed
FTF-owned representations so preview, generation, diagnostics, and other downstream consumers have
no mod-specific logic. The scope includes biome selection and spatial ownership, sampling,
density/noise settings, surface rules, carvers/caves, placed features/ores, structures, ordering,
reload, ownership, and diagnostics. Unknown mod stacks must be safe and diagnosable; private
imperative semantics must not be guessed through reflection or brittle per-mod Mixins. Named mods in
the catalog are a falsification and coverage corpus rather than an allowlist: the runtime must
recognize stable mechanisms, support unseen mods using those mechanisms without code changes, and
bound unsupported mechanisms with actionable diagnostics.

The feasibility boundary is established: a general runtime can normalize declarative graphs and own
public executable leaves, but it cannot independently reproduce hidden imperative state. The
implementation branch now contains the complete ownership runtime: immutable server and preview
owners, tag epochs, the loader-neutral capability SPI, deterministic typed-plan compiler,
machine-readable reports, registered FTF generator root, owned generation stages, request-owned
preview, and FTF-cell provider assignment. Declarative inputs are normalized, registered custom
Minecraft implementations remain opaque executable leaves, custom generators remain opaque roots,
and unsupported facets fail independently with their first concrete cause.

Current evidence and build worktree:

`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`

It is branch `feat/worldgen-compatibility-runtime`, based on current `upstream/1.21.1`
`4a3ab1c5e8f680dc996761908e8904aaca350eb4`, with runtime head
`eb40842a137f9dcb704be52a9283bc2b63bfbe65`. If upstream moves, rebase the clean worktree and
requalify the relevant baselines. The third-party catalog, retained sources, cross-domain
normalization censuses, provider/feature graph runs, preview parity runs, spatial raw grids,
independent decoders, failure controls, and exact implementation gates are all linked from the
canonical plan. Codec extraction is not lifecycle parity: current controls include FTF
initialization divergence, an uninitialized decoded custom source, and a non-fixed-point structure
codec.

Current implementation authority:

- `TerraForgedChunkGenerator` is the registered root and owns biome creation, density, surface,
  carvers, structures, and placed-feature execution through one immutable plan.
- `WorldgenEpoch`, `PreviewRequest`, and `TagEpoch` separate server, request, and tag-binding
  lifetimes. Reload recompiles modifier operations against the unchanged realized base graph and
  atomically rebinds the plan without feeding the previous plan back into compilation.
- `WorldgenCapabilityProvider` is the loader-neutral mechanism SPI. The contained TerraBlender
  provider snapshots public ordered region tables and weights; weighted rendezvous selects exactly
  one provider per final FTF cell and preserves the captured default-table fallback.
- Preview compiles from the selected creation graph and consumes the same plan interfaces as
  generation. The removed Biolith/Lithostitched preview adapters, private accessors, optional
  third-party Mixins, and namespace/class/version dispatch must not return. Its screen cache stores
  only immutable results under the complete selected-graph/tag/capability key; plans, samplers, and
  provider state remain request-owned.
- Preview materializes only its executable facets, filters provable cave candidates without
  constructing underground-region layouts, and pools one terrain and one biome request context per
  editor screen/semantic key. Opaque sources may preview only through the generic fresh
  request-owned source factory contract; missing contracts fail explicitly instead of rendering a
  vanilla-looking substitute.
- Biome rendering consumes one backend `ResolvedTile` operation. The runtime owns coordinate and
  surface mapping, sampler/request construction, cancellation, exact per-worker quart caches, and
  query scheduling; the widget only converts returned biome holders into an ID/color sidecar. Every
  executable plan facet defaults to owner-serial queries and may use isolated parallel reads only
  through an explicit compiled capability. Unknown provider behavior therefore remains serial.
  Unsupported behavior is logged as a backend failure and renders the generic unavailable state;
  provider/factory terminology is not part of the widget contract.
- A final exact vanilla `NoiseBasedChunkGenerator` containing an FTF marker density graph is
  normalized to the FTF root after dimension precedence is resolved. Existing FTF roots and custom
  generator implementations are not coerced.

Final gates on 2026-08-29 are green on clean runtime commit `eb40842` and upstream `4a3ab1c`: 118
common tests, 71 investigation-tool tests, the full Fabric/NeoForge build, clean production-JAR
inspections, Fabric/NeoForge tag reloads `20260829T092022Z-0d31258cb1` and
`20260829T092120Z-c8a8701895`, and cross-loader BOP preview parity `20260829T161825Z-195e750faa` and
`20260829T161345Z-f793dd2291` with 59,536 sampled quart columns per loader, zero
mismatches/fallbacks, and zero underground preview selections. Their probe phases are 8.059 s and
8.256 s; the prior Fabric path was 11.454 s. Complete control normalization is
`20260829T002348Z-225af2e83e`; the 512-by-512 spatial run is `20260829T002435Z-fdfdfafb49` with zero
provider-only boundaries. The canonical plan contains the remaining corpus run IDs and
production-artifact inspection results.

Clean zoom-150 batch equivalence is `20260829T193326Z-824fec22c1` on Fabric and
`20260829T193455Z-fbff21db65` on NeoForge. Each compares all 65,536 returned pixels with the former
serial request path and repeats the batch: both mismatch counts are zero, with 2.84/2.96-second
batch times versus 34.80/35.05 seconds serial (12.26x/11.85x). Clean finished-chunk batch parity is
`20260829T193621Z-b8d881fc67` and `20260829T193736Z-eaa6ca4c1e`: one complete zoom-1 tile resolves
in 62.49/69.72 ms and matches 4,096 quart columns across 256 finished chunks per loader exactly.

Primary third-party conclusions were live-audited against the latest exact 1.21.1 loader releases on
2026-08-29. Fabric RU 0.6.2 + Lithostitched 1.8.0-beta5 generates 256/256 production chunks, but its
realized injector source exposes no complete public request-owned preview factory; the runtime now
reports that opaque-root boundary explicitly (`20260829T160921Z-2f4245fdf1`). Terrestria 7.0.3
chooses Biolith when Biolith is loaded. Biolith's public API registers replacements but exposes no
owner-scoped snapshot/query/factory for the resulting selection state, so Terrestria generation can
contain its biomes while isolated preview cannot soundly reproduce them
(`20260829T161029Z-d87b6d10e3`). Current NeoForge Lithostitched/Biolith and No Man's Land's
bundled-Biolith path fail required third-party Mixins before an FTF-owned seam. No Man's Land 1.5.12
is not Biolith-free when installed alone because its production jar embeds Biolith 3.0.11. Older
releases are not compatibility substitutes. BWG 2.6.0 has an upstream existing-config
double-registration failure; canonical BWG behavior scenarios use a managed first-start config state
and its no-FTF isolation is linked from the plan.

Do not replay provider registration, infer provenance from namespace, traverse private object graphs
for semantics, add a cache with an incomplete key, or merge selection, sampler, spatial, surface,
density, and feature failure domains. Pre-FTF third-party bootstrap failures propagate normally.

Automated compatibility-runtime gates are complete at the commits and upstream tip recorded above.
Remaining work is product/visual QA with exact seed, coordinates, Y, preset, loader, and mod set;
requalification if live upstream or a behavior-bearing dependency changes; and adoption of a public
request-owned provider factory if an opaque source such as Lithostitched exposes one. Do not replace
that missing contract with a named adapter, private-state extraction, registration replay, or silent
vanilla fallback. New compatibility critiques should be separated by facet and owner, reproduced
with current-release tooling, and corrected only when current evidence establishes an FTF-owned
failure.

## TerraBlender and FTF biome-region alignment

The comparison investigation originating from
[FreeTerraForged issue #198 — TerraBlender region mismatch with FTF biome region](https://github.com/ETcodehome/FreeTerraForged/issues/198)
is closed for the compatibility-runtime architecture.

The native upstream comparison path selects TerraBlender's weighted zoomed region map independently
of FTF's biome-cell map. Retained 512x512 maps at FTF biome sizes 50, 225, and 900 show that BOP's
TerraBlender region counts are identical at every size while FTF-only boundary edges fall from
122,673 to 7,794. TerraBlender-only boundaries change the final biome 36%-39% of the time for BOP,
and their mean FTF edge value is indistinguishable from ordinary interior. Nature's Spirit and BWG
reproduce the same cross-cutting behavior. FTF edge resampling therefore does not shape these
visible boundaries. At fixed FTF size 225, native TerraBlender sizes 2, 3, and 4 produce 23,042,
13,176, and 7,509 TerraBlender-only edges respectively while retaining high boundary-change rates
and interior-like FTF edge values. The native setting controls provider-domain scale but cannot
integrate its transitions with FTF geometry.

Nature's Spirit repeats Ice Spikes across all five provider tables, so Ice Spikes can merge across
provider boundaries that terminate region-specific biomes. Runtime topology confirms occasional
cross-domain merging, but not a universal or unique Ice Spikes size defect; FTF-only controls also
produce comparably large Ice Spikes components.

The runtime makes FTF spatial ownership authoritative through its contained public TerraBlender
mechanism provider. It snapshots registered tables, stable IDs, weights, fallback, and order into
request/epoch-owned plan data. Weighted rendezvous deterministically assigns exactly one provider to
each final FTF biome-cell key; adjacent same-provider cells are not merged into a second geometry.
Provider boundaries are therefore a subset of FTF cell boundaries and inherit FTF biome size, warp,
edge, and edge-resampling behavior. Native TerraBlender geometry remains a comparison control, not a
runtime policy. The retained 512-by-512 authority grid reports zero provider-only boundaries, and
the final Fabric/NeoForge BOP preview gates each report 59,536 exact samples with zero mismatches or
provider fallbacks.

## Configurable shorelines and strata

- `feat/configurable-shorelines` is implemented and needs visual/product QA plus rebasing before
  submission. Read `plans/configurable-shorelines.md`.
- `feat/configurable-strata` is implemented and needs product QA, its remaining deepslate/default/UI
  policy decisions, and rebasing before submission. Read `plans/configurable-strata.md`.

## PR #202 cave-rescue interaction

PR #202 head `fab9160a95955f0b0a3d80b5713fcaffc41f7f0b` entered upstream at
`38601673a7ec5976ee6c5979adc3dd234289d970` and remains in current tip `4a3ab1c`. It contributes no
public mechanism or typed data: its `MixinSquarePlacement` recursively reflects through private
graphs, recognizes semantic field-name fragments, caches configured-feature classifications
globally, and clamps vanilla 0..15 candidates to 2..13.

Retained exact comparisons show that its child-feature guard makes the Nature's Spirit cliff case
inert while unrelated `snow_patch` writes change from 883 to 655, all six rescue pipelines are
misclassified from vertical `ySpread`, and only 81 of 2,924 exact production rescue positions remain
in the height-targeted comparison. The runtime branch keeps #202 in its ancestry but removes the
Mixin and its registration. It preserves authored placement coordinates and public leaves until
typed displacement, footprint, ownership, RNG, and ordering closure is available. Current-upstream
Nature's Spirit run `20260829T005459Z-eabe670800` succeeds for 16/16 chunks with full 0..15
`InSquarePlacement` output and reports 65 heuristic false-positive candidates. Detailed comparison
runs and the replacement contract remain in the canonical plan.

## PR #204 preview optimization interaction

PR #204 merged into upstream as `4a3ab1c`. The runtime is rebased on it but removes its static
seed/registry-access initialization cache, reconstructed vanilla generator, manual mod
initialization, private Biolith/TerraBlender adapters, parallel opaque-provider queries, approximate
zoom stride, incomplete cache key, signed-short palette, weakly bounded cache, common-pool `join`,
and named Biolith version gates. Those choices violate request ownership, selected-root authority,
capability concurrency, exact quart/surface sampling, bounded-cache requirements, or mechanism-only
dispatch.

The runtime incorporates the safe findings: exact collision-checked worker-local quart memoization,
an immutable String palette with `int` indices, reuse of the already-computed complete
selected-graph/tag/capability cache key, and registration-order-preserving removal of only exact
duplicate TerraBlender `(parameter point, biome holder)` pairs. The request path also reuses the
prepared FTF cell at the exact quart origin and one shared tile lookup across climate fields;
preview constructors defer semantic-key work until a request exists. The runtime batches the full
tile behind its consumer-neutral API and parallelizes only facets whose compiled plans declare
isolated concurrent reads. Fabric/NeoForge parity, equivalence, and reload run IDs are listed above.
The old test-only PR #204 comparison jars are `/var/home/scott/Desktop/ftf-previewer-fabric.jar` and
`/var/home/scott/Desktop/ftf-previewer-neoforge.jar`; they are legacy comparison artifacts, not
current runtime authority. `/var/home/scott/Desktop/ftf-fabric.jar` and
`/var/home/scott/Desktop/ftf-neoforge.jar` were rebuilt from clean runtime commit `eb40842` on
upstream `4a3ab1c`, copied from the remapped production outputs, compared byte-for-byte with those
outputs, and inspected for the required runtime classes and prohibited private adapters/probe
payloads. These Desktop paths remain convenience artifacts; source commits, build command,
inspection result, and retained run IDs are the durable authority. Do not record hashes for these
ephemeral jars.

## Shared operating rules

- Branch/worktree map: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Engineering wiki: `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/README.md`
- Canonical fixtures: `games/minecraft/investigations/reterraforged/fixtures/`
- Investigation workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Tooling findings: `.agent-docs/games/minecraft/agentic-development-findings.md`
- Mapped Minecraft source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Retained third-party source: `games/minecraft/reference/sources/1.21.1/mods/`
- Runtime tooling: `tooling/squinch mc-investigate --help`

The shared FTF checkout tracks current `upstream/1.21.1` at `4a3ab1c`; the runtime worktree is six
commits ahead at `eb40842`. Parent `main` records the current upstream pointer, critique probes, and
current-state documentation; live Git remains authoritative. Preserve unrelated parent changes. Use
repository-relative scenario projects, check investigation status before and after every run, and
never run Minecraft from a personal launcher profile.
