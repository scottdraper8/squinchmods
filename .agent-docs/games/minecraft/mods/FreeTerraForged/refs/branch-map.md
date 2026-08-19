# FreeTerraForged Branch Map

Reflects the live local branches and in-repository submodule state as of 2026-08-18.

`origin` is `scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

## Branches

| Branch                         | Remote  | Status                                                                                                  |
| ------------------------------ | ------- | ------------------------------------------------------------------------------------------------------- |
| `1.21.1`                       | tracked | Current production base, pinned to `908595b`; synchronized with upstream and pushed to `origin/1.21.1`. |
| `feat/configurable-strata`     | tracked | Active configurable strata/deepslate-band work. No PR opened; needs rebasing before submission.         |
| `feat/configurable-shorelines` | tracked | Active configurable shoreline work. No PR opened; needs rebasing before submission.                     |
| `hotfix/biome-previewer-bugs`  | tracked | Active biome-preview follow-up; pushed to `origin`, PR #186 open upstream.                              |

The in-repository `FreeTerraForged` submodule is on `hotfix/biome-previewer-bugs`. The branch is
intentionally still under development. Use `git branch -vv` in the submodule for its current tip.

## `qa/` vs `fix/` convention

Mostly superseded, not obsolete. It was created to stop QA Mixins from being lost uncommitted in a
branch's working tree — that risk is now handled structurally instead: instrumentation lives in an
external probe pack (`games/minecraft/investigations/reterraforged/probes/`), injected into the dev
build via a Gradle overlay that never touches tracked mod source. Most new investigation work should
use a probe pack, not a `qa/` branch.

A `qa/<topic>` + `fix/<topic>` split is still the right call when in-progress production code and QA
logic tightly coupled to that specific code genuinely need to evolve together and the
instrumentation isn't generalizable enough to extract.
