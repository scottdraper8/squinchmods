# FreeTerraForged compatibility-runtime resumption

This is the current routing and acceptance state. Live source, dependency, process, and retained
evidence supersede it.

## Read first

- Product contract:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Accepted implementation:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/compatibility-runtime-completion.md`
- Runtime model:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/biome-selection-and-compatibility-runtime.md`
- Invariants:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/compatibility-invariants.md`
- Branch relationship: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Investigation guide: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Repository-wide tooling findings: `.agent-docs/games/minecraft/agentic-development-findings.md`

The active worktree is `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility` on
`feat/worldgen-compatibility-runtime` at `d63e097`. Preserve every dirty change. Do not reset,
reconstruct, clean, stash, commit, or push without current authorization.

## Current runtime

- FTF is the consolidated compatibility authority after acquisition.
- Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, and
  structures consume immutable FTF-owned plans and results.
- Supported mechanism contracts are generic; content-mod identities are coverage cases, not dispatch
  keys.
- Query operations pin one plan. Chunk filling reuses request-owned cell identities, while arbitrary
  queries use the lightweight biome-region path and obey the plan's concurrency mode.
- Registry-backed decoration and structure inputs compile into immutable plan identities and do not
  return to live registries during generation.
- Unknown semantics fail at the narrowest sound facet. Full configured-height generation remains the
  permanent density fallback.
- Chunk-local placement correction is compiled only for an exact registered root with one
  whole-chunk scatter and a supported nested random-selector pipeline. Execution wraps only the
  compiled nested offset identities within the active FTF owner chunk. Unknown and unclassified
  pipelines retain vanilla behavior; `RandomOffsetPlacement` is never clamped globally.
- Never dispatch `.codec()` on `DensityFunctions.HolderHolder`, restore the stale NeoForge runtime
  override, or add an Architectury runtime dependency.

## Accepted state

The current source and production artifacts satisfy every compatibility-runtime acceptance gate. The
Java suite, both loader builds/checks, Mixin application, preset generator, investigation and QA
suites, deterministic compatibility matrix, actual Fabric/NeoForge world-creation UI, matched
performance/retained-heap comparison, packaged starts, artifact inspection, and clean retirement all
pass. The retained evidence index is
`games/minecraft/investigation-state/analysis/preset-fixture-migration-20260903T050500Z/mapping.json`;
the matched performance record is
`games/minecraft/investigation-state/analysis/compatibility-performance-20260903T081231Z/comparison.md`;
and the cross-loader placement record is
`games/minecraft/investigation-state/analysis/natures-spirit-placement-20260904/analysis.md`.
Current production artifact hashes and packaged qualification runs are recorded in
`games/minecraft/investigation-state/analysis/compatibility-runtime-final-20260904/artifacts.json`.

Before any JVM-bearing evidence, verify uptime/load, memory/swap, exact prior PIDs, JVMs, owned
processes, cgroups, active state, listeners, display runtimes, and bounded Fabric/NeoForge
status/doctor results. Never read `/proc/<pid>/stack`.

## Upstream boundary

Live `upstream/1.21.1` is `96c31ee`, and its ancestry is integrated by merge `ca6459b`. The accepted
tree retains the deleted `MixinMultiNoiseBiomeSource` path and omits upstream's process-wide
`RandomOffsetPlacement` clamp. The replacement is the generic owner-scoped compiled placement
contract described above; it has no content-mod dispatch and does not alter other generators.

## Resume rule

Do not repeat cleared audits or matrices unless source, dependency, compiler, test, runtime, or host
state invalidates them. Continue only from a new source, dependency, host, QA, or runtime result.
