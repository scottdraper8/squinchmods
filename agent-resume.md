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

This remains an evidence-backed boundary, not a production runtime. The local
`feat/worldgen-compatibility-runtime` branch and its worktree contain no compatibility-layer source
changes and are behind current production. Before implementation, recreate or advance the worktree
from live `upstream/1.21.1`. Existing worktree:

`/var/tmp/ftf-consolidated-compat-layer`

The detached evidence worktree is also on the older base and must be refreshed before new scenarios:

`games/minecraft/investigation-state/worktrees/ftf-compat-runtime-evidence`

The forward rules are:

- consume already-realized Minecraft objects before adding provider adapters;
- keep selection, sampler, candidates, surface, density, and placed features as separate typed
  facets;
- key lifecycle state to exact server-level or preview-request ownership;
- never replay registration, infer provenance from namespace, mutate live provider state for a
  preview, or add an unproven semantic cache; and
- admit an abstraction only for a concrete consumer with exact parity evidence.

No production source change, branch push, or PR is authorized by the investigation alone.

## Configurable shorelines and strata

- `feat/configurable-shorelines` is implemented and needs visual/product QA plus rebasing before
  submission. Read `plans/configurable-shorelines.md`.
- `feat/configurable-strata` is implemented and needs product QA, its remaining deepslate/default/UI
  policy decisions, and rebasing before submission. Read `plans/configurable-strata.md`.

## Shared operating rules

- Branch/worktree map: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Engineering wiki: `.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/README.md`
- Canonical fixtures: `games/minecraft/investigations/reterraforged/fixtures/`
- Investigation workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Tooling findings: `.agent-docs/games/minecraft/agentic-development-findings.md`
- Mapped Minecraft source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Retained third-party source: `games/minecraft/reference/sources/1.21.1/mods/`
- Runtime tooling: `tooling/squinch mc-investigate --help`

The shared FTF submodule checkout remains at `hotfix/biome-previewer-bugs` `2aee90a` because that is
the parent repository's recorded submodule commit. Do not alter it or the parent submodule pointer.
Preserve unrelated parent changes. Use repository-relative scenario projects, check investigation
status before and after every run, and never run Minecraft from a personal launcher profile.
