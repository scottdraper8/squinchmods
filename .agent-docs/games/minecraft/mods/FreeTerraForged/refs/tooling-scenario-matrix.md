# FreeTerraForged tooling and scenario matrix

This is the current ownership map for tracked investigation inputs. Live Git and scenario TOML are
authoritative when either changes.

| Workstream                            |                            Scenario ownership | Compact fixture inputs                                                                             | Probe status                                                                                      |
| ------------------------------------- | --------------------------------------------: | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `rename` / PR #225                    |                      2 loader smoke scenarios | `vanilla-depth-maximum-ocean`; any catalog preset may be passed to `preset-fixture` or `cell-scan` | 14 current-API packs compile together on both loaders                                             |
| `feat/worldgen-compatibility-runtime` |     161 FTF scenarios plus 6 vanilla controls | Biolith, Lithostitched, deep/shallow/maximum-range controls, and parameterized preset variants     | 14 packs require the branch-owned compatibility-runtime source tree                               |
| `feat/configurable-strata`            | no runnable scenario until rename integration | deep ocean, shallow mountain, short-top, and maximum-vertical-range controls                       | use `cell-scan` for model evidence and finished-chunk probes for block evidence after integration |
| `feat/configurable-shorelines`        | no runnable scenario until rename integration | deep/shallow shoreline controls and parameterized preset variants                                  | use `cell-scan` for model evidence and finished-chunk surface probes after integration            |

The catalog contains 29 fixture definitions: each is only `fixture.toml` plus a complete
`preset.json`. Scenario execution generates the full registry tree through the selected worktree's
real FTF exporter into ignored `investigation-state` storage and retains the generator run ID and
hashes. No prebuilt old-namespace archive or tracked generated registry cache is a production input.

The 14 compatibility-runtime probe packs intentionally fail their `required_source_paths` gate on
the `rename` branch because PR #225 does not contain that runtime. They likewise cannot compile on
the unintegrated feature branch after the tooling namespace change. Do not add a second package
tree, alias, source fallback, or path shim. Integrate the production branches first, then compile
and run these same packs against the integrated source.

Historical scenarios tied only to superseded biome-climate, cave-rescue, trail-ruins, and dated
upstream-control worktrees are not part of the active corpus. Their retained run artifacts remain
the evidence record.
