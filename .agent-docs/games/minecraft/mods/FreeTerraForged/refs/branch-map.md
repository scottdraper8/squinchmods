# FreeTerraForged branch map

This file records durable branch roles. Live Git is authoritative. `origin` is
`scottdraper8/FreeTerraForged`; `upstream` is `ETcodehome/FreeTerraForged`.

| Branch                                | Role                                                                                                           |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                              | Local production baseline tracking `upstream/1.21.1` and published to `origin/1.21.1`.                         |
| `1.21.1_unstable`                     | Post-v1.0.0 integration baseline tracking `upstream/1.21.1_unstable` and mirrored to `origin/1.21.1_unstable`. |
| `feat/worldgen-compatibility-runtime` | Ongoing runtime implementation branch and worktree.                                                            |
| `feat/configurable-strata`            | Retained unmerged feature branch; parked pending baseline integration and QA.                                  |
| `feat/configurable-shorelines`        | Retained unmerged shoreline feature branch; parked pending baseline integration and QA.                        |

## Post-v1.0.0 integration

FTF v1.0.0 is the released stable line represented by `1.21.1`. After that release, work developed
on fork-owned feature branches is intended to merge into the upstream `1.21.1_unstable` branch. Pull
requests for that work should target `ETcodehome/FreeTerraForged:1.21.1_unstable`; `upstream/1.21.1`
remains the stable release line.

The ongoing compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. Review its exact status
before acting. The compatibility PR branch includes the live `upstream/1.21.1_unstable` tip and
targets that branch. Use the repository operating rules and canonical plan for evidence baselines
and acceptance. The feature plans and [`tooling-scenario-matrix.md`](tooling-scenario-matrix.md)
identify their remaining integration and acceptance work.

## Compatibility boundary

The compatibility runtime remains governed by the
[`worldgen-compatibility.md`](../plans/worldgen-compatibility.md) contract. It requires FTF-owned
immutable plans and typed results; preview, generation, diagnostics, and other downstream consumers
must not depend on third-party registries, providers, callbacks, or samplers. Keep biome selection,
spatial ownership, climate sampling, surface rules, density, placed features, and diagnostics as
separate compatibility domains until evidence proves a shared contract.
