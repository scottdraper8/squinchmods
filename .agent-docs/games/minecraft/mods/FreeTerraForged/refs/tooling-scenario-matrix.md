# FreeTerraForged tooling and scenario matrix

This matrix records retained scenario ownership. Live Git and scenario TOML are authoritative. The
compatibility runtime is ongoing; configurable strata and shorelines are parked.

| Workstream                            | Scenario ownership                                         | Compact fixture inputs                                                           | Probe status                                                                                                            |
| ------------------------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `upstream/1.21.1`                     | Production loader smoke and underground-biome distribution | `vanilla-depth-maximum-ocean`, compiled default ocean depth                      | Compile current-API packs on both loaders; underground distribution probe compiles against the current Fabric baseline. |
| `feat/worldgen-compatibility-runtime` | Ongoing branch-owned compatibility scenarios               | Biolith, Lithostitched, deep/shallow/maximum-range controls, and preset variants | Compatibility packs use the branch-owned runtime source tree and both loaders.                                          |
| `feat/configurable-strata`            | Parked until deliberate integration with current baseline  | Deep ocean, shallow mountain, short-top, and maximum-vertical-range controls     | Model evidence and finished-chunk block evidence remain part of its QA gate.                                            |
| `feat/configurable-shorelines`        | Parked until deliberate integration with current baseline  | Deep/shallow shoreline controls and parameterized preset variants                | Model evidence and finished-chunk surface evidence remain part of its QA gate.                                          |

Each fixture definition is `fixture.toml` plus a complete `preset.json`. Scenario execution
generates the full registry tree through the selected worktree's real FTF exporter into ignored
`investigation-state` storage. Do not use prebuilt archives or tracked generated-registry caches as
production inputs.

Compatibility-runtime probe packs require their branch-owned source paths. Do not add a second
package tree, alias, source fallback, or path shim. Integrate feature workstreams with the current
baseline before compiling their branch-owned probes as current evidence.
