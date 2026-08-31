# FreeTerraForged Branch Map

Reflects the live local branches, remote refs, and in-repository submodule state as of 2026-08-29.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Remote  | Status                                                                                                                                   |
| ------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | tracked | Current production branch. Local, `origin`, and `upstream` are aligned at `4a3ab1c`, and the in-repository worktree is checked out here. |
| `feat/worldgen-compatibility-runtime` | local   | Active compatibility runtime at `8f5ab0a`, based on `4a3ab1c`; its dedicated worktree is clean after the accepted preview correction.    |
| `feat/configurable-strata`            | tracked | Configurable strata/deepslate-band work is pushed, divergent from current production, and requires product QA plus rebasing.             |
| `feat/configurable-shorelines`        | tracked | Configurable shoreline work is pushed, divergent from current production, and requires visual/product QA plus rebasing.                  |

The in-repository `FreeTerraForged` worktree and the parent repository's submodule pointer are on
current `1.21.1`.

The active compatibility runtime and evidence worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. New evidence and
implementation must continue there from the live `upstream/1.21.1` base.
