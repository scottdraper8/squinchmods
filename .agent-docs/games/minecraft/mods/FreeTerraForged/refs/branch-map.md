# FreeTerraForged Branch Map

Reflects the live local branches, remote refs, and in-repository submodule state as of 2026-08-24.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Remote  | Status                                                                                                                                                                  |
| ------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | tracked | Current production base at `dcb2ae0`; local, `origin`, and `upstream` are aligned.                                                                                      |
| `feat/worldgen-compatibility-runtime` | local   | Empty planning placeholder at `2aee90a`, behind current production. It has no compatibility-runtime source changes. Worktree: `/var/tmp/ftf-consolidated-compat-layer`. |
| `feat/configurable-strata`            | tracked | Configurable strata/deepslate-band work at `b8da568`; pushed, divergent from current production, and requires product QA plus rebasing.                                 |
| `feat/configurable-shorelines`        | tracked | Configurable shoreline work at `a5c6c53`; pushed, divergent from current production, and requires visual/product QA plus rebasing.                                      |
| `hotfix/biome-previewer-bugs`         | tracked | Historical merged tip at `2aee90a`; retained because the parent repository currently pins its submodule checkout to this commit.                                        |

The in-repository `FreeTerraForged` submodule remains on `hotfix/biome-previewer-bugs` at `2aee90a`
because the parent repository records that exact submodule commit. Do not advance that checkout or
the parent submodule pointer as a side effect of branch maintenance.

The compatibility evidence checkout is detached at `2aee90a` in
`games/minecraft/investigation-state/worktrees/ftf-compat-runtime-evidence`. Both compatibility
worktrees must be recreated or advanced from live `upstream/1.21.1` before production work begins.
