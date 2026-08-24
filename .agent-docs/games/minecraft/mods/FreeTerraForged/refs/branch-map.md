# FreeTerraForged Branch Map

Reflects the live local branches and in-repository submodule state as of 2026-08-24.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                                | Remote  | Status                                                                                                                                                   |
| ------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | tracked | Current production base at `734c054`; synchronized with upstream and pushed to `origin/1.21.1`.                                                          |
| `feat/worldgen-compatibility-runtime` | local   | Source-clean investigation branch at `2aee90a`; its tree is identical to production merge `734c054`. Worktree: `/var/tmp/ftf-consolidated-compat-layer`. |
| `feat/ore-contract-classifier`        | tracked | Dynamic ore implementation at `0a0b05e`, pushed to origin. Implementation review, player A/B QA, and final release verification remain.                  |
| `feat/configurable-strata`            | tracked | Active configurable strata/deepslate-band work at `b8da568`. No PR opened; needs product QA and rebasing before submission.                              |
| `feat/configurable-shorelines`        | tracked | Active configurable shoreline work at `a5c6c53`. No PR opened; needs visual/product QA and rebasing before submission.                                   |
| `hotfix/biome-previewer-bugs`         | tracked | Hotfix tip `2aee90a`; PR #186 is merged into `1.21.1` through merge commit `734c054`.                                                                    |

The in-repository `FreeTerraForged` submodule remains on `hotfix/biome-previewer-bugs` at `2aee90a`
and must not be modified because the parent repository records that exact submodule commit. The
worldgen compatibility investigation uses `/var/tmp/ftf-consolidated-compat-layer`; runtime evidence
uses `games/minecraft/investigation-state/worktrees/ftf-compat-runtime-evidence`.

## `qa/` vs `fix/` convention

Mostly superseded, not obsolete. It was created to stop QA Mixins from being lost uncommitted in a
branch's working tree — that risk is now handled structurally instead: instrumentation lives in an
external probe pack (`games/minecraft/investigations/reterraforged/probes/`), injected into the dev
build via a Gradle overlay that never touches tracked mod source. Most new investigation work should
use a probe pack, not a `qa/` branch.

A `qa/<topic>` + `fix/<topic>` split is still the right call when in-progress production code and QA
logic tightly coupled to that specific code genuinely need to evolve together and the
instrumentation isn't generalizable enough to extract.
