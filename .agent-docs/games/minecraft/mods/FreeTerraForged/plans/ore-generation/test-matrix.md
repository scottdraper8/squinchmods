<!-- markdownlint-disable MD013 MD038 MD046 -->

# Ore Investigation Test Matrix

This is the current matrix for Minecraft `1.21.1` at FreeTerraForged baseline `908595b`. A row is
current evidence only when the exact artifact and dependency stack is acquired, hash-verified, and
run to a complete terminal result.

## Stable runtime stack

| Component                 | Current compatible stable release |
| ------------------------- | --------------------------------- |
| Fabric Loader             | `0.19.3`                          |
| Fabric API                | `0.116.15+1.21.1`                 |
| NeoForge                  | `21.1.248`                        |
| Create NeoForge           | `6.0.10+mc1.21.1`                 |
| Immersive Ores Fabric     | `1.21.1-1.1.8`                    |
| Immersive Ores NeoForge   | `1.21.1-1.1.9`                    |
| Regions Unexplored Fabric | `0.6.2-fabric-21.1`               |
| Lithostitched Fabric      | `1.7.13-fabric-21.1`              |

The matrix excludes beta and alpha artifacts. BOP `1.21.1`, TerraBlender `1.21.1`, and GlitchCore
`1.21.1` have no stable compatible chain; their newest compatible artifacts are beta-only and are
not stable evidence.

## Current execution results

| Case                           | Loader   | Result                                                                                   | Run                           |
| ------------------------------ | -------- | ---------------------------------------------------------------------------------------- | ----------------------------- |
| Reference survey, 256 chunks   | Fabric   | Passed; complete telemetry                                                               | `20260819T043553Z-017d4a7946` |
| Shallow survey, 256 chunks     | Fabric   | Passed; complete telemetry                                                               | `20260819T043741Z-ca8436f3a9` |
| Extreme survey, 256 chunks     | Fabric   | Passed; complete telemetry                                                               | `20260819T043912Z-414ba9d93c` |
| Standard survey, 64 chunks     | Fabric   | Passed; complete telemetry                                                               | `20260819T044141Z-b331c581ec` |
| Additional seed `12345`        | Fabric   | Passed; non-ocean surface sample                                                         | `20260819T044244Z-7cfd333cc3` |
| Additional seed `987654`       | Fabric   | Passed; non-ocean surface sample                                                         | `20260819T044353Z-8748778df2` |
| Mountain control, seed `12345` | Fabric   | Passed; non-ocean surface sample                                                         | `20260819T044457Z-0fad024d04` |
| Cave control, seed `12345`     | Fabric   | Passed; non-ocean surface sample                                                         | `20260819T044606Z-40cfde9876` |
| Final feature graph census     | Fabric   | Passed; 64 biomes, 285 registry entries, 199 active IDs, 2,755 occurrences, 0 duplicates | `20260819T044729Z-6f1175dba0` |
| Final feature graph census     | NeoForge | Passed; 64 biomes, 285 registry entries, 199 active IDs, 2,755 occurrences, 0 duplicates | `20260819T044811Z-73bcfc6a60` |
| Create ownership               | NeoForge | Passed; zinc and striated paths observed                                                 | `20260819T044902Z-d4b3f472cc` |
| Immersive Ores ownership       | NeoForge | Passed; vibranium path observed                                                          | `20260819T045012Z-ee528caf4b` |
| Immersive Ores ownership       | Fabric   | Passed; parity with NeoForge fixture                                                     | `20260819T045114Z-588bcaec31` |
| Regions Unexplored composition | Fabric   | Passed; 607 redstone writes                                                              | `20260819T045220Z-f78acc02b0` |
| BOP composition diagnostic     | Fabric   | Passed beta diagnostic; 81/81 chunks, 114 possible BOP biomes                            | `20260819T053856Z-8fc73bcdfc` |
| BOP preview parity diagnostic  | NeoForge | Passed beta diagnostic; 81/81 chunks, 0 preview mismatches                               | `20260819T054002Z-ffd09c9707` |

All current runs use finished-chunk authority and complete selected regions. The run manifests are
the authoritative record for exact hashes, effective loader, baseline, fixture, and dirty detached
worktree properties.

## Ownership and composition status

| Candidate                        | Current status                   | Ore interpretation                                                                                |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| Vanilla                          | Clean control                    | Standard `minecraft:ore` / `minecraft:scattered_ore` contract                                     |
| Create                           | Clean additive control           | Zinc is standard `Feature.ORE` plus a custom filter; striated ores use a custom layered feature   |
| Immersive Ores                   | Clean additive control           | Conventional vibranium placed feature; Fabric and NeoForge agree in the fixture                   |
| Regions Unexplored               | Composition case                 | Reuses a vanilla `minecraft:ore` feature; stable runtime passes, but it changes biome composition |
| Biomes O' Plenty                 | Composition case                 | No stable 1.21.1 dependency chain; beta-only candidate, excluded from stable gate                 |
| Lithostitched / Biolith          | Composition/custom-feature cases | Must not be treated as proof of vanilla ore compatibility                                         |
| Mekanism / Immersive Engineering | Later cases                      | Custom systems deferred until the standard boundary is designed                                   |

The BOP beta artifacts and their Fabric/NeoForge TerraBlender and GlitchCore dependencies are now
acquired through the standard pipeline and hash-verified. Their scenarios are valid composition
diagnostics, but remain outside the stable evidence set because Modrinth labels the entire
compatible 1.21.1 chain beta.

## Acquisition rule

Run `tooling/squinch third-party validate` before relying on a stable catalog row. If it reports an
unacquired artifact, acquire the exact catalog artifact through the documented SSH/source workflow
or leave the row explicitly unavailable. A beta diagnostic may use `--include-beta`, but its run and
interpretation must remain explicitly beta; never use it to make a stable row pass. Never use stale
generated JARs or a different release.
