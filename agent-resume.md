# FreeTerraForged compatibility-runtime resumption

This is the current routing and acceptance state. Live Git, dependency, process, and retained-run
state supersede this file. Read the linked plans and required concepts before changing compatibility
conclusions.

## Scope and authority

- Product contract:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Completion evidence:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/compatibility-runtime-completion.md`
- Required concepts:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/biome-selection-and-compatibility-runtime.md`
  and `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/compatibility-invariants.md`
- Investigation guide: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Repository-wide tooling backlog: `.agent-docs/games/minecraft/agentic-development-findings.md`
- Worktree: `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`
- Branch: `feat/worldgen-compatibility-runtime`
- Local head: `4acd142b93d318d9e306b71e760dd6ee8777992e`
- Published branch head: `2c2729c64912a297a76d619bcc2afd7bf719d565`
- Matched live upstream tip: `12e46fc5f8bdf3367723fa7c36ab7e4502272137`

The worktree is intentionally dirty with the completed compatibility implementation. Preserve it in
place. Do not reset, reconstruct, clean, stash, commit, or push. Previously valid preset inputs
remain a compatibility boundary; internal pre-release Java APIs and implementations do not.

## Non-negotiable design

- FTF is the consolidated runtime authority after acquisition.
- Preview, generation, diagnostics, locate, feature sorting, and structures consume immutable
  FTF-owned plans and results without third-party knowledge.
- Stable mechanisms are supported without a content-mod allowlist.
- Unknown semantics fail at the narrowest sound facet.
- Full configured-height noise generation remains the permanent correctness fallback.
- `DensityFunctions.HolderHolder` is a graph edge; never dispatch its `.codec()`.
- Never restore or run the retained stale NeoForge runtime override.
- Architectury is build-time platform transformation only. FTF has no Architectury runtime
  dependency; the cataloged 13.0.8 JAR is a diagnostic-only matched-upstream control.

## Current acceptance state

The recovered-host baseline is
`games/minecraft/investigation-state/analysis/host-recovery-20260903T041531Z/healthy-baseline.md`.
PID 63400 is absent, the host is healthy, and the complete process-ownership matrix passes. Before
future JVM evidence, repeat bounded load, memory/swap, exact PID, cgroup, listener, display,
active-state, `status`, and `doctor` checks. Never read `/proc/<pid>/stack`.

The 22 generated fixtures and 43 scenarios are mapped at
`games/minecraft/investigation-state/analysis/preset-fixture-migration-20260903T050500Z/mapping.json`.
The complete FTF gate passes 269 Java tests and both loader builds. The locked investigation and QA
suites pass 119 and 426 tests respectively; compileall and diff checks pass. Exact-version
release-or-prerelease qualification is current for the behavior-bearing dependency set.

The deterministic server and actual `mc-investigate client` matrices pass across optional-absent,
installed-unused, RU, Lithostitched, Biolith, TerraBlender, mixed, unseen-mechanism, custom-source,
reload/concurrency/cancellation/failure, structure/feature/surface/ore/flow/underground, ordinary,
extended-height, and C2ME domains on their applicable loaders. The completed static-audit ledger for
preview ownership and caches, sampler publication and query caches, provider/custom-source
acquisition, Biolith, Lithostitched, reload publication, chunk/tile ownership, extended-height
placement, decoration, structures, features, and Mixins remains authoritative. Reopen an area only
after a new edit or failed compiler, test, or runtime result invalidates it.

Matched live-upstream performance and memory evidence is retained at
`games/minecraft/investigation-state/analysis/compatibility-performance-20260903T081231Z/comparison.md`.
The final implementation has no measured retained owner leak or material regression and is faster
for startup, first finished chunk, and deep/tall finished-chunk generation.

Final packaged optional-absent and mixed-stack runs are `20260903T090424Z-061cce2789`,
`20260903T090531Z-df6534bcc8`, `20260903T090621Z-bc3710d9af`, and `20260903T090732Z-de4d86e37b`.
Artifact inspection is clean. The installed Desktop hashes are:

- Fabric: `bfb46a2ae9c463585c56e5d994d0f8598fdd5127f2a1b5435840c75a86307ec1`
- NeoForge: `ac688fd085a43680affb8a6bf850babc47d6abb08a4fab427917a421bb187877`

The final comment audit leaves no code comments added or modified by the FTF branch and no
post-origin repository code comments except the required procfs kernel-safety explanation.
Repository-wide tooling findings are empty.

## Resume rule

All ordered compatibility-runtime gates are complete. Do not repeat cleared audits or evidence.
Resume only from a live invalidation: changed source, changed qualified dependency, unhealthy host,
failed check, failed runtime result, or an explicitly requested new scope.
