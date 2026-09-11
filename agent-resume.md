# FreeTerraForged compatibility-runtime resumption

This is the current routing and acceptance state. Live source, dependency, process, and retained
evidence supersede it.

## Read first

- Product contract:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Accepted implementation:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/compatibility-runtime-acceptance.md`
- Runtime model:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/biome-selection-and-compatibility-runtime.md`
- Invariants:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/compatibility-invariants.md`
- Branch relationship: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Investigation guide: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Repository-wide tooling findings: `.agent-docs/games/minecraft/agentic-development-findings.md`

The active worktree is `games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility` on
`feat/worldgen-compatibility-runtime` at `a967784`. Preserve every dirty change. Do not reset,
reconstruct, clean, stash, commit, or push without current authorization.

## Current runtime

- FTF is the consolidated compatibility authority after acquisition.
- Preview, generation, diagnostics, locate, possible-biome enumeration, feature sorting, and
  structures consume immutable FTF-owned plans and results.
- Supported mechanism contracts are generic; content-mod identities are coverage cases, not dispatch
  keys.
- Lithostitched release numbers are provenance, not an allowlist. Declarative inputs use public
  registries/codecs independently; code listeners activate a structurally inspected, all-or-nothing
  acquisition bridge only when a listener contribution has been observed.
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

Current Lithostitched `1.8.0+beta6` evidence passes installed-unused preview parity on Fabric
(`20260909T051757Z-8e36274e07`) and NeoForge (`20260909T051918Z-05b4e6f3f0`), declarative registry
acquisition on Fabric (`20260909T052157Z-b507f8102d`), and Regions Unexplored code-listener preview
parity on Fabric (`20260909T052253Z-0035c1f0e7`) and NeoForge (`20260909T052343Z-880bc4d779`). The
pre-fix structural-detector failure is retained only as failure evidence at
`20260909T052020Z-2d8a33e989`. Current probe-clean Desktop artifact hashes are Fabric
`e5983b061a0aab6700d607502006ddda8d40956a531e3fcdfa33156d84d9cf1c` and NeoForge
`28815ea5960c63e77d02b6736e67ef77c8b029cbf9e0eacb184fcbed7f2654a1`.

Before any JVM-bearing evidence, verify uptime/load, memory/swap, exact prior PIDs, JVMs, owned
processes, cgroups, active state, listeners, display runtimes, and bounded Fabric/NeoForge
status/doctor results. Never read `/proc/<pid>/stack`.

## Upstream boundary

The upstream archipelago implementation is already present in the compatibility branch. The older
local archipelago redesign is therefore retired as an implementation target. At this snapshot,
local, origin, and upstream `1.21.1` are at `9e6992c`, while the compatibility branch is at
`a967784`. Verify live Git before using those identifiers as an integration boundary.

The active worldgen work is reconciliation and evidence gathering across separate domains: terrain
and surface output, biome/continentalness selection, structure placement, and mob spawning. The
initial reports involve islands, but a newer continental/coastal control point means the suspected
biome/continentalness issue must not be assumed to be island-specific. The open record is
`games/minecraft/investigations/reterraforged/analysis/archipelago-biome-surface-followup.md`. Use
its complete preset snapshot and focused worldgen mod snapshot for reproduction. The reported
screenshots cannot be attributed to the updated compat artifact until the loaded FTF JAR is checked:
the captured profile has the older NeoForge hash while the rebuilt compat artifact has a different
hash.

The accepted tree retains the deleted `MixinMultiNoiseBiomeSource` path and omits upstream's
process-wide `RandomOffsetPlacement` clamp. The replacement is the generic owner-scoped compiled
placement contract described above; it has no content-mod dispatch and does not alter other
generators.

## Resume rule

Do not repeat cleared audits or matrices unless source, dependency, compiler, test, runtime, or host
state invalidates them. Continue only from a new source, dependency, host, QA, or runtime result.
