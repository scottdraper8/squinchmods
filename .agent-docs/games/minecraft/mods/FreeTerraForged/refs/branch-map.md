# FreeTerraForged branch map

This file records durable branch roles and integration boundaries. Live Git is authoritative; use
`git fetch --all --prune` and inspect the graph before relying on any recorded snapshot. `origin` is
`scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branch roles

| Branch                                | Role                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| `rename`                              | PR #225 namespace/branding qualification branch; tracks `upstream/rename`.      |
| `1.21.1`                              | Local production baseline tracking the same-named origin and upstream branches. |
| `feat/worldgen-compatibility-runtime` | Active compatibility worktree and integration branch.                           |
| `feat/configurable-strata`            | Pushed feature branch awaiting product QA and upstream integration.             |
| `feat/configurable-shorelines`        | Pushed feature branch awaiting visual/product QA and upstream integration.      |

The active compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. Its exact commit and the
current production-tip relationship belong in `agent-resume.md`, where they form one replaceable
state snapshot instead of being duplicated here.

The clean detached PR #225 qualification worktree is
`games/minecraft/investigation-state/worktrees/ftf-rename-qa`. The NeoForge baseline smoke uses it
because the nested source's ordinary NeoForge run directory contains intentionally retained,
undeclared compatibility jars; investigation isolation must not delete or silently load them.

The `rename` branch is currently the only listed branch using Java root `etcodehome.freeterraforged`
and mod/resource ID `freeterraforged`. The feature workstreams still descend from the pre-rename
`1.21.1` tree. Their current scenarios and runtime-specific probe packs are retained as branch-owned
inputs, but they cannot produce post-rename evidence until each branch is deliberately integrated
with `rename`. A detached merge trial on 2026-09-11 produced conflicts across the runtime, preview,
Mixin, and loader layers, so this is a production integration task, not a tooling alias or
package-compatibility problem. See `tooling-scenario-matrix.md`.

## Integration boundary

The upstream archipelago redesign from PR #207 is integrated in the compatibility branch. The old
local archipelago plan is retired; remaining island and broader biome/terrain work is an open
reconciliation investigation recorded in
`games/minecraft/investigations/freeterraforged/analysis/archipelago-biome-surface-followup.md`.

The upstream graph also contains compatibility approaches that the consolidated runtime supersedes:

- PRs #208 and #210 modify `MixinMultiNoiseBiomeSource`. The compatibility runtime removes that
  consumer-side interception and provides possible-biome closure through `UnifiedBiomeSource`.
- PR #212 applies a process-wide `RandomOffsetPlacement` clamp. The compatibility runtime instead
  compiles an FTF-owner-scoped placement contract from public graph shape and exact identities, so
  ordinary generators retain vanilla behavior.

Reconcile later upstream changes by behavior and ownership contract, not by replaying superseded
Mixins. The current product boundary and acceptance gates are in
`../plans/worldgen-compatibility.md`.
