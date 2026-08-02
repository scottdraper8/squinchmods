# ReTerraForged Branch Map

Current state as of 2026-08-02, after the `agentic-development-tooling-implementation-plan.md` Phase
11 GitOps cleanup. Only branches that actually exist (locally or on `origin`) are listed; reverify
before relying on it long-term.

## Branches

| Branch                               | Origin     | Tip       | Status                                                                                                                                                                                                                                                                                             |
| ------------------------------------ | ---------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                             | tracked    | `f1322e6` | Production base — merge of PR #152. Upstream (`ETcodehome`) has since advanced to `f9b2ec0`; resync before the next production merge.                                                                                                                                                              |
| `fix/dynamic-cave-feature-placement` | tracked    | `1d0dccf` | Open [PR #154](https://github.com/ETcodehome/ReTerraForged/pull/154). Clean.                                                                                                                                                                                                                       |
| `qa/dynamic-cave-feature-placement`  | local only | `8929a29` | Cave-feature QA instrumentation for PR #154. Live-tested (52 features, complete telemetry). Clean.                                                                                                                                                                                                 |
| `feat/mountain-region-variability`   | tracked    | `8c955b6` | mountainVariety slider. Refreshed onto current `1.21.1` — rebuilt and live-boot-tested. The reusable terrain-region model is in `wiki/concepts/terrain-shaping-and-regions.md`; remaining product QA stays with the feature branch.                                                                |
| `feat/configurable-strata`           | tracked    | `ff1eed1` | Configurable strata/deepslate band. Refreshed onto current `1.21.1`; the TerraBlender surface-rule registration is composed with the merged underground-biome-banding initialization. Both loaders compile and a real Fabric server boot passed. See `plans/configurable-strata.md`.               |
| `feat/configurable-shorelines`       | tracked    | `6368dbb` | Beach/shoreline subsystem port. Refreshed onto current `1.21.1`; shoreline metadata was integrated with the current uplift-river carver and wetland water levels use current complex hydrology. Both loaders compile and a real Fabric server boot passed. See `plans/configurable-shorelines.md`. |

Worktrees: `ReTerraForged` (`1.21.1`), `ReTerraForged-cave-feature-fix`
(`fix/dynamic-cave-feature-placement`), and `ReTerraForged-cave-feature-qa`
(`qa/dynamic-cave-feature-placement`). Product WIP branches do not have idle worktrees.

## `qa/` vs `fix/` convention

Mostly superseded, not obsolete. It was created to stop QA Mixins from being lost uncommitted in a
branch's working tree — that risk is now handled structurally instead: instrumentation lives in an
external probe pack (`games/minecraft/investigations/reterraforged/probes/`), injected into the dev
build via a Gradle overlay that never touches tracked mod source. Most new investigation work should
use a probe pack, not a `qa/` branch.

A `qa/<topic>` + `fix/<topic>` split is still the right call when in-progress production code and QA
logic tightly coupled to that specific code genuinely need to evolve together and the
instrumentation isn't generalizable — `qa/dynamic-cave-feature-placement` is the live example
(`ColumnSurfaceRescue` and its classifier stay on the QA branch deliberately, not extracted).
