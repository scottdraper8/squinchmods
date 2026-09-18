# FreeTerraForged branch map

This file records durable branch roles. Live Git is authoritative. `origin` is
`scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

| Branch                                | Role                                                                                    |
| ------------------------------------- | --------------------------------------------------------------------------------------- |
| `1.21.1`                              | Local production baseline tracking `upstream/1.21.1` and published to `origin/1.21.1`.  |
| `feat/worldgen-compatibility-runtime` | Ongoing runtime implementation branch and worktree.                                     |
| `feat/configurable-strata`            | Retained unmerged feature branch; parked pending baseline integration and QA.           |
| `feat/configurable-shorelines`        | Retained unmerged shoreline feature branch; parked pending baseline integration and QA. |

The ongoing compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. Review its exact status
before acting. Its current branch tip predates the newly synced baseline; reconcile it deliberately
before treating branch-owned probes as current evidence. Start new production evidence from a clean
worktree based on the live `upstream/1.21.1` tip. The feature plans and
[`tooling-scenario-matrix.md`](tooling-scenario-matrix.md) identify their remaining integration and
acceptance work.

## Compatibility boundary

The compatibility runtime remains governed by the
[`worldgen-compatibility.md`](../plans/worldgen-compatibility.md) contract. It requires FTF-owned
immutable plans and typed results; preview, generation, diagnostics, and other downstream consumers
must not depend on third-party registries, providers, callbacks, or samplers. Keep biome selection,
spatial ownership, climate sampling, surface rules, density, placed features, and diagnostics as
separate compatibility domains until evidence proves a shared contract.
