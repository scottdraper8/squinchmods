# Phase 1 Lane Plan: P1-UI-SHELL

## Header

- phase: 1
- lane: `ui-shell`
- planner: `P1-UI-SHELL`
- date: 2026-05-08
- planner owned path: `docs/treeify-rewrite/phases/phase-01/planning/PLAN-P1-UI-SHELL.md`

## Scope

Objective:

- Define the builder plan for extracting a neutral Treeify config screen shell and freezing the first UI service contracts.
- Preserve the useful Structurify/YACL screen shape: tabbed root screen, grouped option categories, parent screen navigation, and a similar enabled-row/detail-button interaction.
- Remove direct structure-domain assumptions from the new shell contract.
- Ensure the shell can later consume vegetation catalog/detail view models without depending on discovery, rules serialization, or runtime worldgen mutation.

In scope for the builder:

- Add a new neutral Treeify UI shell package.
- Add small UI-facing service interfaces for catalog snapshots, pending edits, save/apply actions, and screen session state.
- Add neutral view-model records/interfaces needed by the shell.
- Consume a neutral boolean-plus-detail button controller only through the control lane once that lane provides it.
- Add a root shell builder that accepts injected services and tab composers.
- Provide a temporary no-op or placeholder tab only if needed to compile the shell before vegetation screens exist.

Out of scope for the builder:

- No vegetation discovery.
- No vegetation config schema.
- No Forge biome modifier or runtime apply logic.
- No loader metadata or repo identity rename.
- No deletion of legacy structure screens in this lane.
- No migration of biome picker internals unless the orchestrator assigns that to this lane later.

## Builder Owned Paths

The builder for this lane should own only these production paths:

- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/shell/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/service/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/model/**`

Builder notes and execution artifacts should go here:

- `mods/minecraft/treeify/docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-SHELL.md`

QA for this lane should write here:

- `mods/minecraft/treeify/docs/treeify-rewrite/phases/phase-01/qa/QA-P1-UI-SHELL.md`

## Forbidden Paths

The builder must not edit:

- `mods/minecraft/treeify/forge/**`
- `mods/minecraft/treeify/fabric/**`
- `mods/minecraft/treeify/neoforge/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/data/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/serialization/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/mixin/structure/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/world/level/structure/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructuresConfigScreen.java`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureConfigScreen.java`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetsConfigScreen.java`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetConfigScreen.java`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/util/YACLUtil.java`
- `mods/minecraft/treeify/settings.gradle.kts`
- `mods/minecraft/treeify/gradle.properties`
- loader metadata files, mixin json files, assets, and language files

Read-only inspection of those paths is allowed when needed.

## Source Files To Inspect

Primary UI shell sources:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreenState.java`
- `common/src/main/java/com/squinchmods/structurify/common/StructurifyClient.java`

Primary controller sources:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/StructureButtonController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/StructureButtonControllerBuilder.java`

Read-only context for screen composition:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructuresConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetsConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetConfigScreen.java`

Read-only context for generic helpers and future state lane coordination:

- `common/src/main/java/com/squinchmods/structurify/common/util/YACLUtil.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/OptionPair.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/HolderOption.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/InvisibleOptionGroup.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/DualController.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/**`

## Proposed New Package Paths

Use Treeify naming even though the old Structurify package still exists elsewhere.

- `com.squinchmods.structurify.common.treeify.ui.shell`
- `com.squinchmods.structurify.common.treeify.ui.service`
- `com.squinchmods.structurify.common.treeify.ui.model`
- `com.squinchmods.structurify.common.treeify.ui.control`

The package root stays under `com.squinchmods.structurify.common` during Phase 1 because broad identity/package renaming is frozen until Phase 7.

Suggested class names:

- `TreeifyConfigScreen`
- `TreeifyConfigScreenFactory`
- `TreeifyConfigScreenContext`
- `TreeifyConfigTabComposer`
- `TreeifyConfigSession`
- `ConfigUiCatalogService`
- `ConfigUiEditService`
- `ConfigUiSaveService`
- `ConfigUiApplyResult`
- `ConfigUiCatalogSnapshot`
- `ConfigUiCategoryView`
- `ConfigUiEntryView`
- `ConfigUiEntrySupport`
- `ConfigUiDetailRoute`

Avoid names such as `Structure*`, `StructureSet*`, `WorldgenDataProvider`, `Manager`, and `Helper` in this lane.

## Interface Contracts To Freeze

The builder must keep these contracts small and UI-facing. They are allowed to live in `ui.service` and `ui.model` during Phase 1. Later phases may implement them from rules/worldgen services.

### `ConfigUiCatalogService`

Purpose:

- Provide immutable catalog snapshots to the UI.
- Hide registry discovery and data-source details from screen builders.

Required shape:

```java
public interface ConfigUiCatalogService {
	ConfigUiCatalogSnapshot getCatalogSnapshot();
}
```

`ConfigUiCatalogSnapshot` should expose:

- root title translation key or title `Component`
- category views for global controls and vegetation entries
- optional support/status summary

It must not expose:

- `StructureData`
- `StructureSetData`
- `WorldgenDataProvider`
- registry lookup objects
- YACL objects

### `ConfigUiEditService`

Purpose:

- Provide mutation methods for pending UI edits without tying controls to config file objects.

Required responsibilities:

- read boolean enabled state for an entry
- set boolean enabled state for an entry
- report whether an entry has unsaved changes
- reset one entry or all pending edits if the shell needs that action

It must use neutral ids, preferably string ids or a small `ConfigUiEntryId` record.

### `ConfigUiSaveService`

Purpose:

- Own save/apply/reload requests that the shell can call from YACL callbacks.

Required shape:

```java
public interface ConfigUiSaveService {
	ConfigUiApplyResult savePendingChanges();
	ConfigUiApplyResult discardPendingChanges();
	ConfigUiApplyResult reloadFromSource();
}
```

Rules:

- The shell may call this interface from a save action.
- The shell must not call `config::save` directly.
- The shell must not dispatch `LoadConfigEvent` directly.
- The service implementation is out of scope for this lane.

### `TreeifyConfigSession`

Purpose:

- Replace static mutable screen state with a session-scoped object.

Required responsibilities:

- remember current tab id
- remember per-screen search text
- remember per-screen scroll amount
- remember collapsed group state
- provide save/load methods for a generated `YACLScreen`

Coordination:

- Implementation details that depend on `YACLUtil` or YACL mixins should be coordinated with the Phase 1 UI state lane.
- This lane may define the session contract and a minimal shell dependency on it.

### `TreeifyConfigTabComposer`

Purpose:

- Allow the root shell to assemble tabs without knowing whether a tab is global controls, vegetation catalog, biome override controls, or a temporary placeholder.

Required shape:

```java
public interface TreeifyConfigTabComposer {
	void compose(YetAnotherConfigLib.Builder builder, TreeifyConfigScreenContext context);
}
```

Rules:

- Composers may use YACL because they are UI-layer classes.
- Composers must consume `TreeifyConfigScreenContext`, not global config singletons.

## Acceptance Checks

Required static checks:

- `rg -n "Structurify.getConfig\\(|config::save|LoadConfigEvent" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui` returns no hits.
- `rg -n "StructureData|StructureSetData|WorldgenDataProvider|StructurifyRegistryManagerProvider" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui` returns no hits.
- `rg -n "com\\.squinchmods\\.structurify\\.common\\.config\\.data|com\\.squinchmods\\.structurify\\.common\\.registry" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui` returns no hits.
- `rg -n "org\\.spongepowered\\.asm\\.mixin" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui` returns no hits.
- `rg -n "structure|Structure|structure set|StructureSet" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui` returns no hits except in comments that explicitly reference legacy source files in migration notes. Prefer zero hits in production code.

Required compile check:

- Run the narrowest available Gradle compile/check task for the current Treeify project if dependency resolution is already available locally.
- If Gradle attempts network access or dependency downloads, stop and record the blocker in `BUILD-P1-UI-SHELL.md`; do not widen scope.

Required manual review checks:

- The root shell accepts injected services/context.
- The root shell can be generated without touching the old `StructurifyConfig`.
- The shell has no file I/O.
- Any detail navigation owned by the shell uses neutral routes or callbacks.
- Detail navigation is represented as a neutral route/callback.
- No legacy files are deleted in this lane.

## Required Deletions And Deferred Deletions

Required deletions in this lane:

- None.

Deferred deletions:

- `StructureButtonController.java` and `StructureButtonControllerBuilder.java` are replaced conceptually by the state-controls lane, but deletion belongs to the later phase that removes legacy structure screens.
- `StructurifyConfigScreen.java` remains until loader entrypoints and screen integration are moved to Treeify-owned shell paths.
- `StructuresConfigScreen.java`, `StructureConfigScreen.java`, `StructureSetsConfigScreen.java`, and `StructureSetConfigScreen.java` remain until Phase 5 screen integration replaces their runtime use.
- `StructurifyClient.java` static config screen state remains until the shell is wired by an owning integration phase.
- YACL mixins and `YACLUtil` are reviewed by the UI state lane, not this lane.

## Migration Report Anchors

- `TREEIFY_MIGRATION_REPORT.md#L81`: UI inventory starts.
- `TREEIFY_MIGRATION_REPORT.md#L87`: current root config screen shell is reusable raw material.
- `TREEIFY_MIGRATION_REPORT.md#L99`: useful tabbed YACL shell behavior.
- `TREEIFY_MIGRATION_REPORT.md#L105`: reusable-with-refactor UI pieces are tied to structure terminology or backend globals.
- `TREEIFY_MIGRATION_REPORT.md#L119`: remove `Structure*` naming.
- `TREEIFY_MIGRATION_REPORT.md#L120`: remove direct `Structurify.getConfig()` calls.
- `TREEIFY_MIGRATION_REPORT.md#L121`: remove `LoadConfigEvent` and save side effects from UI construction.
- `TREEIFY_MIGRATION_REPORT.md#L141`: structure-specific screens should not be migrated as-is.
- `TREEIFY_MIGRATION_REPORT.md#L162`: current hard UI/backend couplings.
- `TREEIFY_MIGRATION_REPORT.md#L178`: static mutable UI state should become session state.
- `TREEIFY_MIGRATION_REPORT.md#L344`: UI layer responsibilities.
- `TREEIFY_MIGRATION_REPORT.md#L354`: UI depends only on view models and service interfaces.
- `TREEIFY_MIGRATION_REPORT.md#L907`: Phase 1 creates the neutral UI package.
- `TREEIFY_MIGRATION_REPORT.md#L911`: YACL shell builder is part of Phase 1.

## Rewrite Criteria Anchors

- `TREEIFY_REWRITE_CRITERIA.md#L66`: hard layer boundaries.
- `TREEIFY_REWRITE_CRITERIA.md#L72`: UI depends on view models and service interfaces only.
- `TREEIFY_REWRITE_CRITERIA.md#L76`: UI avoids Minecraft registry inspection classes except display DTOs supplied by services.
- `TREEIFY_REWRITE_CRITERIA.md#L81`: no screen builder calls global config singletons.
- `TREEIFY_REWRITE_CRITERIA.md#L82`: no screen builder dispatches load events or writes config directly.
- `TREEIFY_REWRITE_CRITERIA.md#L250`: Phase 1 UI framework extraction.
- `TREEIFY_REWRITE_CRITERIA.md#L258`: generic screen shell and reusable YACL helpers live in neutral packages.
- `TREEIFY_REWRITE_CRITERIA.md#L260`: UI entrypoints use injected services instead of direct config singleton access.
- `TREEIFY_REWRITE_CRITERIA.md#L261`: direct `LoadConfigEvent` dispatch from UI construction is removed.
- `TREEIFY_REWRITE_CRITERIA.md#L262`: direct `config::save` callbacks from screen builders are removed.
- `TREEIFY_REWRITE_CRITERIA.md#L263`: static mutable screen instances are replaced with session-scoped state.
- `TREEIFY_REWRITE_CRITERIA.md#L267`: required QA grep for UI coupling.

## Exact Builder Instructions

1. Read this lane plan, the migration report anchors, the rewrite criteria anchors, and the legacy inventory entries for root config shell and screen state.
2. Inspect the listed source files, but do not edit legacy Structurify source in this lane.
3. Create the new Treeify packages under the builder owned paths only.
4. Implement the minimal UI model records/interfaces needed for the neutral shell contracts.
5. Implement `ConfigUiCatalogService`, `ConfigUiEditService`, `ConfigUiSaveService`, `TreeifyConfigSession`, and `TreeifyConfigTabComposer`.
6. Implement a `TreeifyConfigScreen` or `TreeifyConfigScreenFactory` that accepts a parent `Screen`, a `TreeifyConfigScreenContext`, and one or more `TreeifyConfigTabComposer` instances.
7. Ensure the YACL builder save callback calls only `ConfigUiSaveService.savePendingChanges()` or a local context method that delegates to that service.
8. Do not call `Structurify.getConfig()`, `LoadConfigEvent`, `config::save`, `WorldgenDataProvider`, or registry providers from the new UI package.
9. Keep all detail opening as callback/route behavior. Do not create vegetation detail screens in this lane.
10. If a placeholder tab is needed for compilation or manual launch, label it with Treeify UI terminology and keep it isolated to `ui.shell`.
11. Run the acceptance checks above and record results in `docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-SHELL.md`.
12. Update the traceability row status only if the orchestrator assigns that artifact to the builder. Otherwise, mention the needed matrix update in the build artifact.

## Builder Handoff Summary

The builder should finish with a compile-ready neutral UI shell and service contract surface. The result should make later vegetation catalog and rules builders able to provide data to the UI without importing YACL, without reusing structure DTOs, and without hiding config load/save side effects inside screen construction.
