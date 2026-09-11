# FreeTerraForged branch map

This file records durable branch roles and integration boundaries. Live Git is authoritative; use
`git fetch --all --prune` and inspect the graph before relying on any recorded snapshot. `origin` is
`scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branch roles

| Branch                                | Role                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| `1.21.1`                              | Local production baseline tracking the same-named origin and upstream branches. |
| `feat/worldgen-compatibility-runtime` | Active compatibility worktree and integration branch.                           |
| `fix/c2me-dfc-compatibility`          | Open C2ME DFC behavior and performance workstream.                              |
| `feat/configurable-strata`            | Pushed feature branch awaiting product QA and upstream integration.             |
| `feat/configurable-shorelines`        | Pushed feature branch awaiting visual/product QA and upstream integration.      |

The active compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. Its exact commit and the
current production-tip relationship belong in `agent-resume.md`, where they form one replaceable
state snapshot instead of being duplicated here.

## Integration boundary

The upstream archipelago redesign from PR #207 is integrated in the compatibility branch. The old
local archipelago plan is retired; remaining island and broader biome/terrain work is an open
reconciliation investigation recorded in
`games/minecraft/investigations/reterraforged/analysis/archipelago-biome-surface-followup.md`.

The upstream graph also contains compatibility approaches that the consolidated runtime supersedes:

- PRs #208 and #210 modify `MixinMultiNoiseBiomeSource`. The compatibility runtime removes that
  consumer-side interception and provides possible-biome closure through `UnifiedBiomeSource`.
- PR #212 applies a process-wide `RandomOffsetPlacement` clamp. The compatibility runtime instead
  compiles an FTF-owner-scoped placement contract from public graph shape and exact identities, so
  ordinary generators retain vanilla behavior.

Reconcile later upstream changes by behavior and ownership contract, not by replaying superseded
Mixins. The current product boundary and acceptance gates are in
`../plans/worldgen-compatibility.md`.
