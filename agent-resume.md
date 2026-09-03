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
- Local head: `2e56c723877f16eda708ad214f55d55b1b0bdcc4`
- Published branch head: `2c2729c64912a297a76d619bcc2afd7bf719d565`
- Matched live upstream tip: `12e46fc5f8bdf3367723fa7c36ab7e4502272137`

The worktree contains the completed compatibility implementation. Preserve it in place. Do not
reset, reconstruct, clean, stash, or push. Previously valid preset inputs remain a compatibility
boundary; internal pre-release Java APIs and implementations do not.

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
The complete FTF gate passes 270 Java tests and both loader builds. The locked investigation and QA
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

The latest runtime invalidation is cleared. Isolated Lithostitched acquisition captures injectors
without activating the cloned source, Biolith 3.0.11 and 3.0.14 share the qualified immutable
placement contract, and biome-decoration state retains generation settings for every registered
biome while selection and feature sorting remain restricted to the possible-biome closure. Actual
NeoForge UI run `20260903T140541Z-59b46fad70` preserves 23,017 RU preview pixels and creates and
joins the No Man's Land world without the prior structure crash. Fabric UI run
`20260903T141047Z-d70de8f92f` produces the same RU count and preview digest.

Matched live-upstream performance and memory evidence is retained at
`games/minecraft/investigation-state/analysis/compatibility-performance-20260903T081231Z/comparison.md`.
The final implementation has no measured retained owner leak or material regression and is faster
for startup, first finished chunk, and deep/tall finished-chunk generation. The post-fix matched
controls `20260903T141845Z-a3a44b273c` and `20260903T141955Z-936a9baccf` confirm current is 10.38%
faster to ready, 28.72% faster in measured generation, and 26.41% faster overall.

Final packaged optional-absent and mixed-stack runs are `20260903T141355Z-f330d57f85`,
`20260903T141459Z-854e22d335`, `20260903T141559Z-1884fe42e4`, and `20260903T141658Z-2eb5a867c5`.
Artifact inspection is clean. The installed Desktop hashes are:

- Fabric: `0170e66b7b361f95cb319b2711bba1a1cb010c6f328cc0d4b826005c894b0b0b`
- NeoForge: `61c2bdb2530a6f2560c3a064233daa645a5d7bafa02f2dd181cdec6af8e114a5`

The final comment audit leaves no code comments added or modified by the FTF branch and no
post-origin repository code comments except the required procfs kernel-safety explanation.
Repository-wide tooling findings are empty.

## Resume rule

All ordered compatibility-runtime gates are complete. Do not repeat cleared audits or evidence.
Resume only from a live invalidation: changed source, changed qualified dependency, unhealthy host,
failed check, failed runtime result, or an explicitly requested new scope.
