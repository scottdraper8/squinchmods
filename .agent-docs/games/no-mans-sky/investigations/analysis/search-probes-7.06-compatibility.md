# Search Probes compatibility review: No Man's Sky 7.06

**Reviewed:** 2026-10-06

**Static result:** native bindings and observed layouts mapped to 7.06

**Runtime result:** bounded Steam Proton acceptance passed; final package verification recorded
below

## Live executable

The public Steam installation is build `25732212`, version 7.06. Its executable is 88,560,712 bytes
with SHA-256 `13d5060d4efb9d2a6a6b1b349bc4257231056cc2a055df4bb15d816262cc3499`. Hello Games
released [Cosmos 7.06](https://www.nomanssky.com/2026/10/cosmos-7-06/) on October 5, 2026. The patch
notes list gameplay fixes and a PC crash fix; the executable itself remains the authority for native
compatibility.

Search Probes 0.1.1 has a 7.06 exact-build guard and current native bindings. Bounded Steam Proton
acceptance covers search semantics, worker parity, resource ownership, Guide opening, navigation,
save reload and ordinary shutdown. Current measurements were collected on a degraded host and
support semantic/hash conclusions only. Native Windows desktop remains untested.

## Native binding map

The old addresses below identify the 7.04 product bindings. Current addresses are preferred virtual
addresses in the 7.06 executable.

| Contract                         |          7.04 |          7.06 |
| -------------------------------- | ------------: | ------------: |
| Region buffer constructor        | `0x1404C3090` | `0x1404C5620` |
| Region populate                  | `0x14135D7B0` | `0x141367810` |
| Region buffer destructor         | `0x1404C2E90` | `0x1404C5420` |
| Query constructor                | `0x14044FA10` | `0x14044FD50` |
| Query destructor                 | `0x140316F00` | `0x140316F80` |
| Query address classifier         | `0x141323590` | `0x14132D5E0` |
| Solar `GenerateQueryInfo`        | `0x14163D6F0` | `0x141649D10` |
| Planet `GenerateQueryInfo`       | `0x141680070` | `0x14168C640` |
| Solar context initializer        | `0x14163D4C0` | `0x141649AE0` |
| Planet query-context constructor | `0x1413AE660` | `0x1413B8C90` |
| Planet address getter            | `0x14166B2D0` | `0x1416778A0` |
| Resource-table release           | `0x1404B0C10` | `0x1404B2DF0` |
| Gameplay allocator free          | `0x142C13B60` | `0x142C1F570` |
| Player update hook               | `0x1413EAE90` | `0x1413F54F0` |
| Guide/navigation mission starter | `0x1409B1950` | `0x1409B8E00` |
| Mission selection                | `0x1409BA140` | `0x1409C15F0` |
| Scan-event lookup                | `0x1404E4510` | `0x1404E6BC0` |
| Scan-event dispatcher hook       | `0x1412D40E0` | `0x1412DE0A0` |
| Building resolver hook           | `0x1412DB840` | `0x1412E57C0` |
| Planet destination filter hook   | `0x1412DE8A0` | `0x1412E8850` |
| Registration hook                | `0x141697BE0` | `0x1416A41B0` |

The former region candidate `0x141545EF0` was the wrong function. The current `Populate` target
`0x141367810` is reached from the current region enumeration caller after the same constructor and
before the matching destructor. Its reachable implementation retains the 9,241-byte region
population contract; the product's `0x260`-byte initialized region buffer still covers the fields
used by enumeration.

The query classifier is `0x14132D5E0`, not the superficially similar address builder at
`0x141362670`. The game's current solar-query routine at `0x141659A50` calls the classifier and then
the current solar `GenerateQueryInfo`; it reads the same planet totals at query offsets `+0x760` and
`+0x764`, and the same metadata pointer at `+0x1038`. The classifier body is 234 bytes in both
builds and retains the writes through `+0x760`. The query destructor still releases allocations at
the observed `+0x3670` and `+0x36A0` fields; `0x36C0` bytes remains sufficient storage.

The planet context constructor retains its `0xC10` size and the resource-vector offsets used by the
product. The planet-info generator still reads the planet array at data-root `+0x520570`; the solar
query path and solar-context initialization still use data-root `+0x521180`. The live planet source
table array remains at `+0x3210` and uses the current resource-cache manager.

## Moved process state and resource ownership

The application singleton pointer cell moved to image base `+0x6E8D708`; the singleton object used
by the lifecycle hook is image base `+0x6E8D6D0`. Its data-root field moved to application
`+0x72AFB0`. The loaded address at application `+0xC1A0`, difficulty at `+0x315A2C`, current planet
array at data-root `+0x520570`, and solar resources at data-root `+0x521180` remain at their
observed offsets. The current language global is image base `+0x6E14168`.

Solar resource initialization uses the resource-cache object at image base `+0x7489480`. Object
table acquisition uses the adjacent cache object at `+0x7489710` and epoch at `+0x7489858`; the
current helper reached from the object-table path is `0x1416C7660`. Resource release uses
`0x1404B2DF0`. The current allocator singleton is image base `+0x500A050`; direct free calls use
`0x142C1F570` with that singleton as `RCX`.

The application scan-event manager remains at application `+0x4DE450`. The mission manager moved to
application `+0x847BB0`; current call sites use its vector fields at `+0x1C4/+0x1C8` and selection
field at `+0x250`. The scan-event name remains at `+0x228`, but `UAsList` moved from `+0x418/+0x420`
to `+0x428/+0x430`, and `SolarSystemLocation` moved from `+0x47C` to `+0x48C`. Both navigation
validation paths now use those current offsets. The initial address-only candidate failed this check
during bounded runtime acceptance and was rejected. The current dispatcher reads these same fields
in `20261006T232418Z-exe-functions-ba3f8920`; the live owned event confirmed them.

The native allocator TLS index is image base `+0x6E10C68`. Allocator fields within that TLS module
moved to `+0x1940/+0x1944/+0x1948`; its enabled flag is image base `+0x5292041`. The developer
thread probe now reads the current fields. Raw current-image disassembly is in
`20261006T235100Z-search-probes-7.06-release/audit-native-layouts.json`.

## Raw evidence

The exact executable identity accompanies each retained static run under
`games/no-mans-sky/investigation-state/runs/`. Key runs include:

- `20261006T230855Z-exe-functions-1750dc8c`, `20261006T230917Z-exe-functions-d379713a`, and
  `20261006T231645Z-exe-functions-5b853947` for the region and lifecycle mappings.
- `20261006T231456Z-exe-functions-f6a6755f` for the application singleton and current constructor.
- `20261006T232555Z-exe-functions-66b2f2a3` and `20261006T232555Z-exe-functions-4227a85b` for solar
  and planet query-info functions.
- `20261006T233539Z-exe-functions-0428a0b4` and `20261006T215741Z-exe-functions-5ccb4f2f` for the
  classifier call and current solar-query caller.
- `20261006T233148Z-exe-functions-0f3e2b64` and `20261006T232923Z-exe-functions-f6dcce3e` for the
  moved mission-manager field and selector.
- `20261006T233428Z-exe-functions-5a36354c` for the object-table source array, resource-cache
  object, and epoch accesses.
- `20261006T233125Z-exe-functions-12bca32b` and the current-image scan for the unchanged difficulty
  field and moved language global.

The prior 7.04 package/install record is
[`release-verification.json`](../../../../../games/no-mans-sky/investigation-state/runs/20260927T213746Z-search-probes-ui-release/release-verification.json).

## Native mission metadata correction

Current table loading at `0x140EB15ED` loads NPC missions into its `+0xD8` table and Wiki missions
into `+0xE0`. Its reachable chain explicitly writes `IsProceduralAllowed` at definition `+0x4B5` for
every NPC mission (`0x140EB2093`). An authored false value, capitalization change and scalar
overwrite cannot override this post-load assignment. The game export omits the procedural and
recurring runtime flags. The title generator at `0x140A6DE20` otherwise has a seed-dependent chance
of replacing the authored title with an NPC title; the flavour description is also affected.

The destination definition now joins the nine Guide definitions in `WIKIMISSIONTABLE.EXML`.
`NPCMISSIONTABLE.EXML` is removed. The merged export proves exactly one owned destination in Wiki
and none in NPC. Native definition bytes show the procedural flag disabled, with the authored
“Search Probe Target” title and description. Saved-route loading, native abandonment, fresh
creation, exact route publication and duplicate rejection pass. No additional executable hook or
unrelated mission/faction override was needed. Runtime-only flags were removed from authored Guide
entries; the unused static marker tag is omitted. All authored mission leaves match the actual game
export.

The table-loader evidence is in `20261007T005424Z-exe-functions-69895749`. The whole reachable
unwind chain matters: checking only the initial fragment misses the post-load writes.

## Current runtime acceptance

Raw release evidence is retained in
[`20261006T235100Z-search-probes-7.06-release`](../../../../../games/no-mans-sky/investigation-state/runs/20261006T235100Z-search-probes-7.06-release/).

| Gate                    | Evidence and scope                                                                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Save restriction        | Visual Galaxies 1–50 selection; loaded address `0x1FF7F7FF7FF`; only backed-up `save.hg`/`save2.hg` used                                                                                          |
| Expensive worker parity | 1,000 systems / 4,754 planets, identical four blue-sky/floating-island addresses at 1/2/4/8/16 workers; 1,213 object scans                                                                        |
| Representative controls | Any, purple, Earthlike, anomaly multiselect, resources All/Any, weather/storm/flora/fauna and minimum-planet negative control; `controls/runtime-matrix-summary.json`                             |
| Resource ownership      | Live solar/planet bytes and shared filename-map header unchanged, existing references balanced and new references zero; `controls/native-resource-checks.json`                                    |
| Cache and continuation  | Cold/cached/disjoint searches, zero-generation cache hits, cancellation/resumption, 21,000 systems in separate bounded searches with a 16,384-system ceiling; `controls/cache-bound-summary.json` |
| Guide                   | New UI creation, existing hidden UI reopening, criteria synchronization, empty slot/error display; retained JSON and screenshots                                                                  |
| Navigation              | Exact remote seed/route, duplicate rejection, native abandonment, saved-route loading and corrected labels; `wiki-native-log.png`, `controls/wiki-new-navigation.json`                            |
| Reload                  | Generation advances, caches and active progress clear, player identity and destination persist; completed visible cards intentionally remain; `controls/reload-after.json`                        |
| Ordinary lifecycle      | Steam self-start without injection and native Quit to Desktop close NMS and Rust UI; no signals used                                                                                              |
| Build and assets        | 70 existing Rust tests, Windows GNU production build, three authored assets compile/decompile, and mission leaves match the actual merged export                                                  |

Local-planet arrival/completion, live travel during a search, every enum's positive case, and the
historical independent fresh-native oracle were not repeated on 7.06. Historical 7.04 measurements
and broader reference coverage remain versioned in the release plan and product validation notes. No
timing, RSS, allocation or throughput conclusion is drawn from this update review.

## Release verification

The final archive, installed file hashes, direct-game links to both Amethyst sources, process
teardown and exact restoration of the four save files and two settings files are recorded in
[`release-verification.json`](../../../../../games/no-mans-sky/investigation-state/runs/20261006T235100Z-search-probes-7.06-release/release-verification.json).
The original candidate that accidentally retained the 7.04 bootstrap is quarantined outside `dist`;
it is rejected evidence. Only the final canonical 0.1.1 package is the release artifact.
