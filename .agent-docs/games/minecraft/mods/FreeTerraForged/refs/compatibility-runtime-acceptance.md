# FreeTerraForged compatibility-runtime acceptance record

This record defines the accepted implementation and validation surface of the compatibility-runtime
workstream. The product and architecture contract is `../plans/worldgen-compatibility.md`; detailed
runtime behavior belongs in the companion concept and invariant documents. Live source,
dependencies, host state, and retained artifacts supersede this summary.

## Implemented runtime

FTF discovers registry, resource, codec, provider, factory, and mechanism inputs and normalizes them
into immutable owner-scoped plans. One plan owns biome composition, provider selection, spatial
assignment, query policy, density extent, surface rules, carvers, placed-feature schedules, compiled
adaptations, decoration settings, and structures.

Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, and
structures consume only FTF plans and typed results. They do not query third-party registries,
callbacks, providers, or samplers after acquisition. Unsupported semantics fail at the narrowest
sound facet, and full configured-height generation remains the density fallback.

Architectury Loom and its transformer are build-time project machinery. Production FTF has no
Architectury runtime dependency; common compilation uses only the injectables annotations, and the
transformer emits the loader implementation as a self-contained class in each production JAR.

## Accepted verification surface

- Preset fixtures use the complete preset generator. Preset and derived-registry agreement is
  recorded in
  `games/minecraft/investigation-state/analysis/preset-fixture-migration-20260903T050500Z/mapping.json`.
- Both loader builds, access-widener validation, Architectury transformation, remapping, Mixin
  application, and production assembly pass. Acceptance uses maintained Squinch runtime controls and
  inspected production JARs.
- Investigation tooling validates scenario lifecycle and cleanup controls.
- Normal, timeout, cancellation, malformed-result, crash, wrapper-linger, and teardown controls pass
  for server, client, cell-scan, and preset-fixture operations. Every accepted JVM run retires its
  process tree, cgroup, listeners, active state, and owned display runtime.
- The deterministic Fabric/NeoForge matrix covers optional absence, installed-unused mechanisms,
  Regions Unexplored, loader-appropriate Lithostitched, Biolith, TerraBlender, mixed stacks, unseen
  mechanism users, custom sources, owner-serial concurrency, reload, cancellation, unknown nodes,
  malformed providers, ordinary and extended height, structures, carvers, flow fields, ores, surface
  rescue, underground behavior, and tall worlds.
- Actual world-creation UI runs on both loaders cover shared preview, regeneration, cancellation,
  datapack and dimension changes, server creation, finished chunks, biome identity, generation,
  saving, and clean teardown. NeoForge resolves `nomansland:autumnal_forest`; Fabric resolves the
  Regions Unexplored autumnal-maple biome.
- Large locate operations pin one plan for the complete call. Owner-serial selection remains on that
  plan across replacement, isolated-safe selection may run concurrently, and the next operation
  observes the replacement.
- Cross-loader placement census compiles the same eleven generic chunk-local contracts with no
  failure. Both loaders complete every cliff descendant and retain all resulting write attempts
  inside the owner chunk while ordinary stone and unclassified snow controls preserve vanilla
  behavior. The analysis is retained at
  `games/minecraft/investigation-state/analysis/natures-spirit-placement-20260904/analysis.md`.

## Performance and ownership

Chunk biome filling reuses request-owned terrain-cell identities, arbitrary queries use the
lightweight biome-region path, and the aquifer path reuses the noise-stage tile. Matched
fresh-process evidence is retained at
`games/minecraft/investigation-state/analysis/compatibility-performance-20260903T081231Z/comparison.md`.
It finds no retained owner leak or material startup, preview, generation, save, locate, allocation,
or retained-heap regression. All 48 retired owner references clear after forced collection.

Before using JVM timing, allocation, RSS, JFR, startup, shutdown, or cleanup evidence, verify host
health and exact investigation ownership. Never read `/proc/<pid>/stack`.

## Production artifacts

Both production JARs pass artifact inspection and packaged optional-absent starts on both loaders.
Production-remapped Regions Unexplored/Lithostitched starts also pass on both loaders. They contain
no probe, development sentinel, stale Mixin, deleted implementation, retained NeoForge override,
bundled optional dependency, Architectury runtime dependency, or incorrect metadata.

## Current integration boundary

The current PR branch contains the live upstream `1.21.1_unstable` tip and PR #206 is retargeted
there. The merged source uses `UnifiedBiomeSource` for possible-biome closure and FTF-owner-scoped
placement plans. The current merged tip still needs qualification against the complete matrix in the
canonical plan. Fabric and NeoForge production builds and current Nature's Spirit placement probes
pass. The 1.21.1 C2ME artifacts are alpha-channel diagnostics only. The signed-seed C2ME
DFC-on/off/absent matrix passed on both loaders with equal preview, finished-biome, and
finished-block samples; its exact scope and run IDs are retained in
`games/minecraft/investigation-state/analysis/c2me-dfc-20260919/analysis.md`.

The latest release-channel Lithostitched beta6 seam is accepted for packaged Fabric and NeoForge
Regions Unexplored parity: each sampled 256 quart columns with zero preview/finished mismatches and
122 real rocky-reef transitions, and both runs cleaned up. Fabric tag reload and post-rebind
finished-chunk generation also pass. The declarative-only fixture contributes a real injector and
region; fresh owner-local preview acquisition passes on both loaders. An unsupported code-event
injector fails closed during world initialization with its exact type, entry, and bounded capability
code. The Squinch expected-failure control verifies the diagnostic, installed mods, and cleanup.
Exact structural comparisons and run IDs are in
`games/minecraft/investigation-state/analysis/lithostitched-beta6-20260919/analysis.md`. The
remaining current-tip matrix must be judged per the canonical plan and runtime artifacts.
