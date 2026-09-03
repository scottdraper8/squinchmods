# FreeTerraForged Branch Map

Reflects the live local branches, remote refs, and in-repository submodule state. Verify live Git
before relying on this summary.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Remote  | Current state                                                                                                                                                                                                             |
| ------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | tracked | Local and `upstream` are aligned at `4a3ab1c`; the in-repository worktree is checked out here.                                                                                                                            |
| `feat/worldgen-compatibility-runtime` | tracked | Local is `4acd142`, one commit ahead of `origin` at `2c2729c`, with active uncommitted completion/performance work; based on `4a3ab1c`. Continue through the canonical compatibility plans without committing or pushing. |
| `feat/configurable-strata`            | tracked | Pushed, divergent from production, and awaiting product QA and rebase.                                                                                                                                                    |
| `feat/configurable-shorelines`        | tracked | Pushed, divergent from production, and awaiting visual/product QA and rebase.                                                                                                                                             |

The in-repository `FreeTerraForged` worktree and the parent repository's submodule pointer are on
current `1.21.1`.

The active compatibility runtime and evidence worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. New evidence and
implementation must continue there from the live `upstream/1.21.1` base.

Inspect the compatibility worktree's live status before rebasing, building, or starting further
implementation. Live Git supersedes this map.
