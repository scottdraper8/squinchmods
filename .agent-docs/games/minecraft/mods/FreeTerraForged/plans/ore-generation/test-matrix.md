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
| Dynamic realization smoke      | Fabric   | Passed; 16 chunks, per-call deposits, rejection attribution, write survival, host volume | `20260820T011923Z-b68cded721` |
| Dynamic cave realization smoke | Fabric   | Passed; 16 chunks, exposure rejection and later-write survival                           | `20260820T011703Z-e619b1e3cc` |
| Dynamic realization smoke      | NeoForge | Passed; 4 chunks, loader-parity hook/schema validation                                    | `20260820T012239Z-8ca5056a3f` |
| Final ordinary-ore contract census | Fabric | Passed; 53 possible biomes, 30 contracts, 22 executable supported, 8 final blacklist-only | `20260820T022423Z-012961b5de` |
| Host/material reference control | Fabric | Passed; 16 chunks, material-aware eligible-host and realized-write attribution | `20260820T023302Z-f50ae12d61` |
| Host/material shallow control | Fabric | Passed; 16 mountain chunks, stone/strata/deepslate host composition | `20260820T023356Z-5bf4df8a41` |
| Host/material deep control | Fabric | Passed; 16 chunks, 4,128,768 finished blocks scanned | `20260820T023447Z-8e5f47d73f` |
| Host/material maximum control | Fabric | Passed; 16 chunks, 8,388,608 finished blocks and 6,325,093 eligible hosts | `20260820T023542Z-3a37e5bbaa` |
| Host/material short-top control | Fabric | Passed; 16 chunks, top contraction boundary | `20260820T023654Z-1ef2026db2` |
| Revised fanout deep smoke | Fabric | Passed; independent X/Z fanout before Height | `20260820T030533Z-1db8919c02` |
| Reference baseline identity | Fabric | Passed; clean baseline core telemetry | `20260820T030724Z-4c33a0383a` |
| Reference prototype identity | Fabric | Core telemetry exactly matched baseline; runner teardown fault after result | `20260820T030831Z-ddabe6382f` |
| Transform reference, 16 chunks | Fabric | Passed; new survival-by-Y schema | `20260820T031839Z-26b90be2e5` |
| Transform shallow, 16 chunks | Fabric | Passed; contraction and survival-by-Y | `20260820T031935Z-44ed6b4ff4` |
| Transform deep, 16 chunks | Fabric | Passed; expansion and host composition | `20260820T032028Z-12d7fa3abb` |
| Transform maximum, 16 chunks | Fabric | Passed; maximum-height linear density | `20260820T032652Z-3a67c76d2b` |
| Transform reference, 256 chunks | Fabric | Passed; large-sample candidate and host normalization | `20260820T032957Z-6c872d6125` |
| Transform shallow, 256 chunks | Fabric | Passed; same-seed realized concentration comparison | `20260820T033120Z-03797f634e` |
| Scattered ore deep composition | Fabric | Passed; scaled calls, no hosts/writes in selected deep-ocean band | `20260820T033729Z-7342dc86f0` |
| Scattered ore maximum | Fabric | Passed; 996 calls and 1,252 surviving raw-gold writes | `20260820T034030Z-dba88727b7` |
| Dynamic ore NeoForge smoke | NeoForge | Passed; common deep-frame diamond/tuff runtime path | `20260820T034152Z-1064c66227` |
| Create standard/custom boundary | NeoForge | Passed; zinc transformed, custom filter retained, striated feature unchanged | `20260820T034330Z-bc7899491a` |
| Immersive Ores standard/custom boundary | Fabric | Passed; vibranium transformed, geode path unchanged | `20260820T034438Z-567293d6ff` |
| Transform short ceiling, 256 chunks | Fabric | Passed; upper coal/iron contraction and authored above-top tails | `20260820T034952Z-499c64076d` |
| Post-reload maximum smoke | Fabric | Core passed with exact candidate telemetry; cleanup recovered after host Python fault | `20260820T035254Z-abba0a9687` |
| Post-reload maximum smoke | NeoForge | Passed with complete cleanup; candidate histograms exactly match Fabric | `20260820T035453Z-3e044efc9b` |
| Non-FTF ownership control | Fabric | Passed; vanilla Overworld remained inactive with FTF installed and emitted no dynamic-ore inventory | `20260820T040555Z-f5a91603da` |
| Actual FTF ownership smoke | NeoForge | Passed; `RTFRandomState` ownership activated 22 transforms for frame `-624..383` | `20260820T040642Z-3b26a4828b` |
| Maximum timing repetition 1, baseline | Fabric | Passed; generation `8.155s`, full probe `11.075s`, complete cleanup | `20260820T041340Z-b609bb46bd` |
| Maximum timing repetition 1, dynamic | Fabric | Server/probe/cleanup passed; generation `8.862s`; host wrapper faulted after durable completion | `20260820T041456Z-97cc2e4314` |
| Maximum timing repetition 2, baseline | Fabric | Passed; generation `8.165s`, full probe `12.662s`, complete cleanup | `20260820T041637Z-3c8786f97d` |
| Maximum timing repetition 2, dynamic | Fabric | Passed; generation `9.182s`, full probe `13.468s`, complete cleanup | `20260820T041748Z-095ff4d775` |

All current runs use finished-chunk authority and complete selected regions. The run manifests are
the authoritative record for exact hashes, effective loader, baseline, fixture, and dirty detached
worktree properties.

The older survey/ownership rows are retained baseline evidence. The `20260820T03...` transform rows
are formula validation and include configured-feature calls, per-call deposits, target/exposure
rejection, final-write survival by Y, and opt-in target-rule host/output denominators where listed.
Candidate totals validate the mechanical transform; surviving writes per host opportunity explain
realization without becoming a production feedback term.

Runs `20260820T030831Z-ddabe6382f` and `20260820T035254Z-abba0a9687` are noncanonical only because
the host Python 3.14 runner faulted during process teardown after valid terminal probe results. The
latter was recovered through `mc-investigate doctor --recover`; the equivalent NeoForge reload run
completed normally. Canonical formula conclusions use the clean rows wherever an equivalent exists.
Run `20260820T041456Z-97cc2e4314` likewise has a successful durable server summary and complete
cleanup but a post-completion host-process exit `139`; its timing is retained only as an explicitly
qualified member of the matched performance sample.

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
