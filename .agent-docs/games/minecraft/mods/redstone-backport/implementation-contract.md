# Redstone Backport implementation contract

## Product direction

The approved direction is a standalone, all-in-one backport of vanilla redstone and relevant
redstone-adjacent systems. Earlier research recommendations to narrow the product to a companion are
**not approved** and must not constrain the implementation. Optional coexistence is useful, but a
companion must not be required merely because it supplies overlapping content.

Existing pre-release behavior has no compatibility guarantee. Replace defective mechanisms at the
root. Use `minecraft:` identifiers for vanilla features and preserve vanilla resource paths and
filenames wherever possible, including resource-pack-facing GUI assets. Third-party source is
investigative material, not the behavioral authority or an unrestricted source of reusable code.

## Scope and baseline

- Published version records now confirm Vanilla Backport reaches **1.16.5 Forge**, with **1.18.2
  Fabric/Forge**, **1.20.1 Fabric/Forge/NeoForge/Quilt** across historical releases, and **1.21.1
  Fabric/NeoForge**. Smallinger's Copper Age Backport publishes **1.20.1 Fabric/Forge** and **1.21.1
  Fabric/NeoForge**. Thus **1.16.5 is a real minimum baseline**, not merely the old aspirational
  roadmap. Historical loader unions do not establish current-release parity; qualify each advertised
  combination. Raw records and exact versions are in
  [active baseline evidence](../../../../../.squinch/scratch/tranches/redstone-backport-release/inputs/research/research/2026-10-27/published-baselines.json).
- Audit every stable Minecraft release between that baseline and the current stable release,
  including intervening bugfix releases. The retained initial manifest observation identifies 26.3
  as stable and 26.4-snapshot-5 as experimental; recheck before release qualification.
- Cover new components and their necessary survival/content systems, analog outputs, automation,
  dispenser/hopper interactions, vibration/observer behavior, musical redstone,
  ticking/chunk-loading changes, and applicable historical fixes. Explicitly classify non-applicable
  changes and optional experiments rather than silently dropping them.
- Stable vanilla is the default parity contract. Experimental snapshot behavior must remain clearly
  separate and must not become a default claim. Where later stable behavior supersedes an earlier
  rule, use an explicit contract rather than enabling contradictory historical behaviors together.
- Populate the actual public feature matrix. Every implemented claim must identify supported target
  versions/loaders and evidence. Planned, implemented-unqualified, and runtime-qualified are
  distinct states.

## Architecture and implementation gates

1. Pin and inspect official vanilla source/data for every mechanism and its introduction/fixes.
   Research notes and third-party source do not substitute for vanilla implementation review.
2. Design collision-free ownership for complete feature families before registry registration. Never
   blindly overwrite another mod's `minecraft:` entries or equate presence with parity. Coexistence
   must be qualified; unsupported overlap needs an actionable diagnostic rather than a corrupt world
   or a duplicate registry crash.
3. Unify common semantics across loaders. In particular, repair Crafter comparator/automation/
   remainders/pulse timing, witch redstone loot and Looting randomness, and qualify the `/tick`
   server-loop, world/entity/chunk, client, and network gates.
4. Keep vanilla namespace/content/resource structure consistent across registry, recipes, loot,
   tags, menus, block entities, models, sounds, textures, networking, and saved state.
5. Do not reuse restricted Vanilla Backport code. Resolve Copper Age Backport's conflicting license
   declarations before any reuse. Independently implement from vanilla contracts and follow the
   [source/asset distribution boundary](asset-provenance.md): preserve the existing project license,
   do not assume official asset redistribution rights, and qualify any legitimate local
   resource-acquisition path instead of bundling unlicensed content or omitting required features.

## Release acceptance

- A complete, reviewed per-release feature inventory and honest public matrix.
- Reproducible clean builds and packaging checks for every advertised target/loader.
- Deterministic mechanism-level tests, including negative cases and save/reload behavior.
- Real server/client qualification where relevant: timing, automation, commands, synchronization,
  placement/orientation, inventories, resource loading, and resource-pack overrides.
- Packaged production JAR inspection proving no investigation instrumentation is shipped.
- Explicitly tested supported coexistence scenarios and rejection of unsupported collisions.
- Current setup/support/configuration/migration/release documentation and CI.
- No release-ready claim while any required test is absent, failed, or inconclusive.

Compilation and static/archive inspection are not runtime qualification. The orchestration's
completion markers are bookkeeping, not release approval. Continue correcting findings until these
gates pass or an actual access/tool/provider/environment blocker prevents safe progress.

## Work ownership and operating boundaries

Production work is in the Redstone Backport Git submodule `games/minecraft/mods/redstone-backport`.
Preserve unrelated parent-repository changes, including FTF, NMS, tooling, and the in-progress site
restructuring.

The active task uses tranche **`redstone-backport-release`**. Select it with
`tooling/squinch --tranche redstone-backport-release ...` or `SQUINCH_TRANCHE`. All task-local
inputs, orchestration output, worktrees, build state, runtime state, and test artifacts belong
beneath the canonical workspace reported by `tooling/squinch tranche path`. The paused workflow and
research inputs have been adopted there; do not recreate the former `.pi/big-build/` task output or
per-game state roots. The removed state-root override must not be restored as a compatibility path.
Hold the tranche's shared lock during orchestration and use the managed Minecraft lifecycle for game
processes.

Shared official/third-party source caches remain outside tranche ownership at
`/var/home/scott/.cache/squinchmods/redstone-backport/`. Official source is under
`vanilla/<version>/src/`, with original resources in `resources/` and provenance in the acquisition
and source/class/resource indexes. All requested stable acquisitions completed, but acquisition is
not semantic review or runtime qualification. Third-party source is under `third-party-sources/`.

- [Initial scope/source audit](refs/scope-and-existing-backports.md)
- [Initial vanilla inventory](refs/vanilla-redstone-update-inventory.md)
- [Active research inputs](../../../../../.squinch/scratch/tranches/redstone-backport-release/inputs/research/README.md)

At completion, promote required behavior into maintained code and CI/CD tests, update the current
engineering references, then clean the task tranche only after verified teardown. Do not preserve an
investigation archive or remove shared caches as part of tranche cleanup.

The environment explicitly denies parent `games/minecraft/reference/`,
`games/minecraft/investigation-state/`, `games/minecraft/qa-state/`, `.agent-docs/tmp/`, and other
listed restricted paths. Do not access those paths directly or through subprocesses, aliases,
symlinks, worktrees, or delegated agents. Newly acquired external inputs may use explicitly
configured, unrestricted task-owned output locations; this does not authorize access to existing
restricted contents. Tool defaults that necessarily touch denied locations must not be invoked. Do
not remove or weaken agent-deny enforcement.
