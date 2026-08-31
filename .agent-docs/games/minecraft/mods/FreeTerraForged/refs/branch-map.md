# FreeTerraForged Branch Map

Reflects the live local branches, remote refs, and in-repository submodule state. Verify live Git
before relying on this summary.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Remote  | Status                                                                                                                                                                                                                        |
| ------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | tracked | Current production branch. Local, `origin`, and `upstream` are aligned at `4a3ab1c`, and the in-repository worktree is checked out here.                                                                                      |
| `feat/worldgen-compatibility-runtime` | tracked | Runtime Compat Layer MVP with Level-owned flow settings and pre-server Lithostitched acquisition at `52fa36c`, based on `4a3ab1c`; the current contract and external mechanism boundaries are recorded in the canonical plan. |
| `feat/configurable-strata`            | tracked | Configurable strata/deepslate-band work is pushed, divergent from current production, and requires product QA plus rebasing.                                                                                                  |
| `feat/configurable-shorelines`        | tracked | Configurable shoreline work is pushed, divergent from current production, and requires visual/product QA plus rebasing.                                                                                                       |

The in-repository `FreeTerraForged` worktree and the parent repository's submodule pointer are on
current `1.21.1`.

The active compatibility runtime and evidence worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. New evidence and
implementation must continue there from the live `upstream/1.21.1` base.

Inspect the compatibility worktree's live status before rebasing, building, or starting further
implementation. Live Git supersedes this map.
