# Minecraft Agentic Development Findings

## Status: 2026-09-05

This is the current unresolved backlog for repository-wide Minecraft investigation tooling. It is
not an incident log or a record of completed work. Mod-specific conclusions belong in that mod's
canonical plan, durable operating rules belong in `agentic-development-guide.md`, and raw evidence
belongs in retained run artifacts. Remove an item as soon as its root fix and acceptance evidence
are complete; an empty active section is the intended steady state.

## Active

### `preset-fixture` cannot regenerate any fixture against a plain-`upstream/1.21.1` worktree

Root cause is architectural, not a stale-data nit: `tooling/squinch mc-investigate preset-fixture`
runs `PresetFixtureMain` as a headless Fabric `DataGeneratorEntrypoint`
(`games/minecraft/investigations/reterraforged/cell-scan/src/main/java/org/squinchmods/investigate/rtf/PresetFixtureMain.java`).
Per vanilla's own datagen API (`net.minecraft.data.registries.VanillaRegistries.createLookup()`, and
`FabricDataGenerator#getRegistries()`), a headless data generator can only ever produce a
`HolderLookup.Provider`, never a real `RegistryAccess` — there is no headless bootstrap path that
materializes one. `Datapacks.makePreset` on plain `upstream/1.21.1`
(`common/src/main/java/raccoonman/reterraforged/data/worldgen/Datapacks.java`) still requires an
actual `RegistryAccess` parameter; only the separate, still-incomplete
`feat/worldgen-compatibility-runtime` branch widened it to accept `HolderLookup.Provider` (commit
`c65ee21`, entangled with that branch's broader ETL rewrite, not a narrowly portable change).
Confirmed reproduction: `:fabric:compileSquinchProbeJava` (or `:neoforge:...`) fails with
`incompatible types: Provider cannot be converted to RegistryAccess` at `PresetFixtureMain.java:40`
against a clean `upstream/1.21.1` worktree at `f9c254e`, run `20260904T233637Z-ef737190cc`.

Downstream symptom of the same gap: the shared RTF fixture base,
`games/minecraft/investigations/reterraforged/fixtures/_base/data/reterraforged/reterraforged/worldgen/preset/preset.json`,
predates Preset-codec fields current `upstream/1.21.1` requires (confirmed missing:
`island.mountainHorizontalScale`, `island.volcanismHorizontalScale`,
`island.macroDensityPercentage`) — nobody has been able to regenerate it against upstream since
those fields were added, precisely because `preset-fixture` cannot run there. Any fixture built from
`_base` crashes registry load on an affected worktree with
`IllegalStateException: No key <field> in MapLike[...]` and
`Failed to load datapacks, can't proceed with server load` in the server log. Reproduced with the
`shallow-depth-mountain-control` fixture (`rtf_version = "0.0.6005"`), same worktree, scenario
`ftf-trail-ruins-locate-discovery`, run `20260904T232608Z-9e854008fb`. Concrete added cost: the
crash does not exit the server JVM — it stays alive (observed still running past 420s) rather than
terminating, so the run only ends when the scenario's own `startup` timeout is exhausted and the
tracked systemd unit force-kills the process tree, wasting a full cold Gradle build plus the entire
configured startup timeout with no earlier failure signal.

Root resolution gate: either port a narrowly-scoped, standalone widening of
`Datapacks.makePreset`/`Preset.buildPatch`/`Preset.filterToArmedOnly` from `RegistryAccess` to
`HolderLookup.Provider` onto `upstream/1.21.1` (the `buildPatch`/`buildPatchedRegistries` portion of
commit `c65ee21` only — not `buildPreviewLookups`, which is compat-runtime-specific and unrelated),
or accept that `preset-fixture` is compat-branch-only and document the supported alternative for
every other branch: export a datapack through the real client path
(`PresetConfigScreen.exportAsDatapack` via `WorldCreationContext.worldgenLoadContext()`, driven
headlessly through `tooling/squinch mc-investigate client` with a probe pack that stages
`applyPreset`/exports the resulting `reterraforged-preset.zip`, e.g.
`games/minecraft/investigations/reterraforged/probes/client-world-lifecycle`). Close only once a run
against current upstream tip, using either path, reaches a running server rather than a
registry-load crash. Regardless of which resolution ships, `_base` itself should be regenerated
afterward so it stops being stale for every other consumer.

### `pre-server-preview` probe pack does not compile outside the compat-runtime branch

`games/minecraft/investigations/reterraforged/probes/pre-server-preview/src/main/java/org/squinchmods/investigate/rtf/preview/mixin/MixinWorldCreationUiState.java`
imports fourteen classes from `raccoonman.reterraforged.world.worldgen.runtime.*`
(`MinecraftWorldgenPlanCompiler`, `TerraForgedChunkGenerator`, `WorldgenPreServerFinalizer`, and
others) — a package that exists only on `feat/worldgen-compatibility-runtime`, not on plain
`upstream/1.21.1`. `git log` shows this probe pack has exactly one commit
(`64cc521 feat: complete worldgen compatibility investigation`), so it was written and validated
only against that branch. Reproduced: `:fabric:compileSquinchProbeJava` fails with fourteen
`package raccoonman.reterraforged.world.worldgen.runtime does not exist` errors against a clean
`upstream/1.21.1` worktree at `f9c254e`, run `20260904T234544Z-ee26dec265`. Concrete cost: any
non-compat-branch worktree cannot use this probe pack at all for client/world-creation evidence, and
the failure only surfaces after a full cold client build, not at probe-pack selection time. A
sibling probe pack, `games/minecraft/investigations/reterraforged/probes/client-world-lifecycle`,
covers the same "stage a preset and create a real world" need with zero compat-runtime imports and
is confirmed to compile and run cleanly at the same upstream revision (run
`20260904T234748Z-8b0224b2a5`, status `pass`) — that is the correct probe pack to reach for a
non-compat worktree.

Root resolution gate: either split `pre-server-preview` so its compat-runtime-only pieces
(`MixinWorldCreationUiState` and whatever depends on it) live behind a capability or build variant
that is only compiled in on the compat branch, or explicitly document that this probe pack is
compat-branch-only so it stops being the first thing reached for on other worktrees. No other probe
pack under `games/minecraft/investigations/reterraforged/probes/` has been audited for the same
`raccoonman.reterraforged.world.worldgen.runtime` coupling; that audit is part of closing this.

### Scenario `cleanup_failed` after a large `generate` step can mask fully-valid retained step data

A scenario that force-generates a large, scattered chunk volume (11 regions, 1859 chunks total,
`ftf-trail-ruins-enclosure-scan`, run `20260904T235233Z-3a74d31572`) had every step succeed
(`scenario-summary.json` reports `"state": "succeeded"` and all eleven `terminal_probe` results are
present and complete, `shell_scan_capped: false` throughout) but the top-level command still
returned `error` / `cleanup_failed`, because the final world-save issued over RCON during shutdown
timed out (`"world save: RCON I/O failed: timed out"`, default `[timeouts] shutdown = 180`). This
also left a stale entry under `games/minecraft/investigation-state/active/`, requiring
`mc-investigate doctor --recover` to clear before the worktree could be reused.

Concrete cost: the top-level `state: "error"` gives no signal that every step actually completed and
all data is intact in `scenario-summary.json` — an agent or user could reasonably discard a run's
results as invalid and redo the (expensive, cold-build-plus-1800-chunk) work for nothing. Root
resolution gate: either give heavy-`generate` scenarios a shutdown timeout scaled to the chunk
volume requested, or have the CLI distinguish "steps succeeded, cleanup/save failed" from "steps
failed" in its top-level `state`/`error` fields so retained step data is never conflated with a
failed run.

## Entry rule

Add only a reproducible, repository-wide tooling defect with a concrete cost and a root resolution
gate. Do not add reminders, mod behavior, speculative improvements, completed incidents, or
workarounds. Fold related symptoms into the existing root issue instead of adding another entry.
