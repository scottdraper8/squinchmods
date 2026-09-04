# FreeTerraForged Branch Map

This file records the current local/remote relationship. Verify live Git before relying on it.
`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Current state                                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | The local in-repository worktree is at `4a3ab1c`. Live `upstream/1.21.1` is `96c31ee`.                        |
| `feat/worldgen-compatibility-runtime` | The active worktree and `origin` are at `d63e097`. Upstream `96c31ee` is an ancestor through merge `ca6459b`. |
| `feat/configurable-strata`            | Pushed, divergent from production, and awaiting product QA and upstream integration.                          |
| `feat/configurable-shorelines`        | Pushed, divergent from production, and awaiting visual/product QA and upstream integration.                   |

The active compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`.

## Upstream integration boundary

The upstream-only graph contains three merged compatibility changes:

- [PR 208](https://github.com/ETcodehome/FreeTerraForged/pull/208) and
  [PR 210](https://github.com/ETcodehome/FreeTerraForged/pull/210) modify
  `MixinMultiNoiseBiomeSource`. The compatibility runtime deletes that consumer-side interception
  and provides possible-biome closure through `UnifiedBiomeSource`, so those patches do not apply to
  the current architecture.
- [PR 212](https://github.com/ETcodehome/FreeTerraForged/pull/212) replaces the older reflective
  `MixinSquarePlacement` workaround with a process-wide `RandomOffsetPlacement` clamp. The current
  runtime deletes the old workaround and its accessor. The replacement is not acceptable because it
  changes ordinary placement for non-FTF generators and lacks an exact placed-feature plan identity.

Merge `ca6459b` integrates the upstream ancestry while retaining the deleted
`MixinMultiNoiseBiomeSource`, omitting upstream's process-wide `MixinRandomOffsetPlacement`, and
retaining the compatibility runtime's Mixin configuration. The branch instead compiles a generic
FTF-owner-scoped chunk-local placement contract from public graph shape and exact identities.
