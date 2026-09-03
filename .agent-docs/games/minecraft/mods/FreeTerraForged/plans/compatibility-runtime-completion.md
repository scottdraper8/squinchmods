# FreeTerraForged compatibility-runtime completion

This is the current acceptance state. The product and architecture contract is
`worldgen-compatibility.md`; the companion concept and invariant documents remain required reading.
Live Git, dependency, host, and retained-run state supersede recorded pointers.

## Completion standard

Correctness, completeness, architectural soundness, and empirical proof are the completion metrics.
Replace unsound internals in place, preserve previously valid preset inputs, and keep downstream
consumers zero-knowledge. Do not commit or push without explicit user authorization.

## Current implementation

The compatibility branch implements evidence and diagnostics, full-height noise, provider discovery,
contribution algebra, owner/reload publication, custom sources, mechanism acquisition, public
generator-stage execution, immutable biome decoration and structures, compiled feature adaptations,
and bounded preview/generation/cache/pool ownership as one runtime.

FTF owns normalized immutable plans after acquisition. Preview, generation, diagnostics, locate,
feature sorting, and structures do not query third-party runtime state. Unsupported semantics fail
at the narrowest sound facet, and full configured height remains the density fallback.

Architectury is not an FTF runtime dependency. Architectury Loom and the transformer remain
build-time project machinery for the existing platform method split; common compilation uses only
the injectables annotations. The Architectury 13.0.8 catalog entry is diagnostic-only and appears
solely in matched upstream performance controls.

## Acceptance state

The host recovered cleanly from PID 63400. The baseline is retained at
`games/minecraft/investigation-state/analysis/host-recovery-20260903T041531Z/healthy-baseline.md`.
Normal, timeout, cancellation, malformed-result, crash, wrapper-linger, and teardown controls pass
for server, client, cell-scan, and preset-fixture ownership. Fabric and NeoForge operations retire
their exact processes, cgroups, listeners, display runtimes, managed files, and active state.

The complete generator produced 22 unique source-form fixtures used by all 43 migrated scenarios.
Preset and derived-registry agreement is recorded in
`games/minecraft/investigation-state/analysis/preset-fixture-migration-20260903T050500Z/mapping.json`.
The obsolete `rtf_ephemeral` schema, parser, materializer, tests, documentation, and patches are
absent.

The final source gate passes 270 common Java tests, both loader checks/builds, access-widener
validation, both Architectury transforms, remapping, Mixin application, and production assembly. The
locked investigation suite passes 119 tests including slow lifecycle cases; QA passes 426; Python
compileall and both repository/FTF diff checks pass. The branch-wide comment audit leaves no added
or modified FTF code comments and no post-origin repository code comments except the required kernel
procfs safety explanation.

The retained deterministic matrix covers optional absence, installed-unused mechanisms, current RU,
loader-appropriate Lithostitched, Biolith, TerraBlender, mixed stacks, unseen mechanism users,
custom sources, owner-serial concurrency, reload, cancellation, unknown nodes, malformed providers,
ordinary and extended-height generation, structures, carvers, flow fields, ores, surface rescue,
underground behavior, C2ME tall worlds, and clean retirement. Actual world-creation UI evidence was
obtained only through `mc-investigate client`, including Fabric run `20260903T075818Z-d85575c9e5`
and the corresponding retained NeoForge/UI matrix.

The final follow-up closes the No Man's Land/Biolith invalidation. Isolated Lithostitched
acquisition captures declarations without activating its cloned source; Biolith 3.0.11 and 3.0.14
are qualified against the same placement contract; and the immutable decoration plan retains final
generation settings for every registered biome, including biomes referenced locally by structures.
Selection pipelines and feature sorting remain limited to the possible-biome closure. NeoForge UI
run `20260903T140541Z-59b46fad70` preserves 23,017 RU preview pixels through repeated 2D/3D and
datapack-reload cycles, creates the combined No Man's Land world, and joins without the former
structure crash. Fabric UI run `20260903T141047Z-d70de8f92f` produces the same RU count and digest.

The final aquifer optimization reuses the noise-stage owned tile instead of taking a tile-cache read
lease for every fluid column. Fabric performance runs and NeoForge full-height run
`20260903T090158Z-4dfda2aa75` validate the final path. Matched current-versus-live-upstream
measurements and JFR evidence are retained at
`games/minecraft/investigation-state/analysis/compatibility-performance-20260903T081231Z/comparison.md`.
Current preview latency is within run variance while allocating 13.7% less; all 48 retired owner
references clear. Current startup is 14.56% faster, first finished chunk is 34.49% faster, and the
final deep/tall window median is 45.83% faster. No current retained leak or material regression was
found.

Post-fix matched runs `20260903T141845Z-a3a44b273c` and `20260903T141955Z-936a9baccf` use the same
live upstream tip, Java, loader, mod set, fixture, seed, heap, settings, and healthy host. Current
reaches ready in 15.415 seconds versus 17.201 seconds, measures generation in 2.896033 seconds
versus 4.062625 seconds, and completes the probe in 3.169933 seconds versus 4.307588 seconds:
improvements of 10.38%, 28.72%, and 26.41% respectively.

Exact-version release-or-prerelease qualification is current for the behavior-bearing 1.21.1
Fabric/NeoForge dependency set. The all-catalog release-only query has no Fabric BOP result because
that release is published as beta; explicit release-or-prerelease qualification reports the pinned
BOP 21.1.0.14 as current on both loaders.

## Production artifacts

Both exact production JARs pass artifact inspection with no probe, development sentinel, stale
Mixin, deleted implementation, stale NeoForge override, bundled optional dependency, or metadata
finding. The final inspection result is retained at
`games/minecraft/investigation-state/analysis/compatibility-runtime-final-20260903T091106Z/artifact-inspection.json`.
Packaged optional-absent runs `20260903T141355Z-f330d57f85` and `20260903T141459Z-854e22d335`,
NeoForge RU/Lithostitched run `20260903T141559Z-1884fe42e4`, and Fabric unseen-mechanism run
`20260903T141658Z-2eb5a867c5` all pass and cleanly retire.

The atomically installed Desktop artifacts are:

- `ftf-fabric.jar`: `0170e66b7b361f95cb319b2711bba1a1cb010c6f328cc0d4b826005c894b0b0b`
- `ftf-neoforge.jar`: `61c2bdb2530a6f2560c3a064233daa645a5d7bafa02f2dd181cdec6af8e114a5`

## Program state

All ordered gates are complete. The tooling findings Active section is empty, semantic results have
no unexplained mismatch, performance and retirement evidence show no current leak or material
regression, and no investigation-owned process, listener, cgroup member, display runtime, or active
state survives. Further work is required only if live source, dependencies, host state, or a new
runtime result invalidates this acceptance state.
