# FreeTerraForged compatibility-runtime acceptance

This document records the accepted current implementation and its validation surface. The product
and architecture contract is `worldgen-compatibility.md`; detailed runtime behavior belongs in the
companion concept and invariant documents. Live source, dependencies, host state, and retained
artifacts supersede this summary.

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

- The complete preset generator produces 22 unique source fixtures used by 43 scenarios, and preset
  plus derived-registry agreement is recorded in
  `games/minecraft/investigation-state/analysis/preset-fixture-migration-20260903T050500Z/mapping.json`.
  No `rtf_ephemeral` schema, parser, materializer, test, documentation, or patch remains.
- The current source passes 281 Java tests, both loader checks and builds, access-widener
  validation, Architectury transformation, remapping, Mixin application, and production assembly.
- The investigation suite passes 120 tests including slow lifecycle controls; QA passes 426.
  Compileall and both repository and FTF diff checks pass.
- Normal, timeout, cancellation, malformed-result, crash, wrapper-linger, and teardown controls pass
  for server, client, cell-scan, and preset-fixture operations. Every accepted JVM run retires its
  process tree, cgroup, listeners, active state, and owned display runtime.
- The deterministic Fabric/NeoForge matrix covers optional absence, installed-unused mechanisms,
  Regions Unexplored, loader-appropriate Lithostitched, Biolith, TerraBlender, mixed stacks, unseen
  mechanism users, custom sources, owner-serial concurrency, reload, cancellation, unknown nodes,
  malformed providers, ordinary and extended height, structures, carvers, flow fields, ores, surface
  rescue, underground behavior, and C2ME tall worlds.
- Actual world-creation UI runs on both loaders cover shared preview, regeneration, cancellation,
  datapack and dimension changes, server creation, finished chunks, biome identity, generation,
  saving, and clean teardown. NeoForge resolves `nomansland:autumnal_forest`; Fabric resolves the
  Regions Unexplored autumnal-maple biome.
- Large locate operations pin one plan for the complete call. Owner-serial selection remains on that
  plan across replacement, isolated-safe selection may run concurrently, and the next operation
  observes the replacement.
- Cross-loader placement census compiles the same eleven generic chunk-local contracts with no
  failure. Fabric run `20260904T030131Z-18dbe984c4` and NeoForge run `20260904T025923Z-762620f633`
  complete every cliff descendant and retain all resulting write attempts inside the owner chunk
  while ordinary stone and unclassified snow controls preserve vanilla behavior. The analysis is
  retained at
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

Both production JARs pass artifact inspection and packaged optional-absent starts on Fabric
(`20260904T031438Z-10bbafb696`) and NeoForge (`20260904T031544Z-c5567169ee`). Production-remapped
Regions Unexplored/Lithostitched starts pass on Fabric beta5 (`20260904T031644Z-e17eeaa52c`) and
NeoForge beta4 (`20260904T031742Z-8b9d01ba9b`). They contain no probe, development sentinel, stale
Mixin, deleted implementation, retained NeoForge override, bundled optional dependency, Architectury
runtime dependency, or incorrect metadata.

- `ftf-fabric.jar`: `4efd568e4c0cb1e1b843d5a84ab25877a4aa596aabc4d9198fc85cb50cabadb2`
- `ftf-neoforge.jar`: `dec6573bc967d749d781e2dadfc717166f1484123a87825e5bf229e6c1a6438c`

## Current integration boundary

Live upstream is `96c31ee`; merge `437bc9c` integrates its ancestry without adopting obsolete
consumer-side preview interception or the process-wide placement clamp. `UnifiedBiomeSource` owns
possible-biome closure. The placement plan classifies public graph semantics, pins exact root and
nested modifier identities, and activates only for an FTF generator owner.
