# Current-target compatibility qualification

Qualify the compatibility runtime described in the
[worldgen compatibility contract](../refs/worldgen-compatibility-contract.md) against the current
`upstream/1.21.1_unstable` source.

Refresh upstream refs and start from a clean worktree at the current target. The retained
compatibility worktree and its scenario files reproduce an older baseline. Current-target behavior
requires evidence from the clean worktree. Select and explicitly invoke manual scenarios for each
row below; the scenario corpus has no automatic suite runner.

| Coverage area           | Required evidence                                                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Loader packaging        | Fabric and NeoForge production builds, packaged artifact inspection, and startup with optional compatibility mods absent.                                             |
| Provider selection      | Optional mods absent, installed but unused, and active; TerraBlender, Lithostitched, and Biolith paths; mixed providers; and an unseen user of a supported mechanism. |
| Selection and preview   | Same-owner preview and finished-chunk biome agreement, possible-biome closure, locate behavior, and supported surface/underground selection.                          |
| Generation              | Representative carver, structure, placed-feature, ore, flow, and extended-height cases on both loaders.                                                               |
| Ownership and lifecycle | Reload and cancellation behavior, owner replacement, owner-serial selection, isolated-safe concurrency, and cleanup after world creation or failure.                  |
| Failure boundaries      | Unsupported or malformed provider semantics produce bounded, actionable failures while independent supported facets remain usable.                                    |

Use current catalog artifacts and the Minecraft investigation guide for scenario setup, evidence
authority, and run cleanup. Keep exact raw results with their run artifacts only while a current
decision depends on them. Remove this plan when the current-target qualification is complete or
dropped; keep reusable architecture constraints in the contract and reusable scenarios that remain
part of regression coverage.
