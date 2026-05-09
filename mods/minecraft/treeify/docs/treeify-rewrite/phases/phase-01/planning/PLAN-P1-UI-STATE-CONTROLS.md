# PLAN-P1-UI-STATE-CONTROLS

## Header

- phase: Phase 1, Extract Generic UI Framework
- lane: `ui-state-controls`
- planner: `P1-UI-STATE-CONTROLS`
- date: 2026-05-08
- plan_ids: `P1-UI-002`
- upstream docs:
  - `docs/treeify-rewrite/governing/TREEIFY_MIGRATION_REPORT.md`
  - `docs/treeify-rewrite/governing/TREEIFY_REWRITE_CRITERIA.md`
  - `docs/treeify-rewrite/orchestration/TREEIFY_IMPLEMENTATION_PLAN.md`
  - `docs/treeify-rewrite/orchestration/TRACEABILITY_MATRIX.md`
  - `docs/treeify-rewrite/orchestration/manifests/OWNERSHIP_MANIFEST.md`

## Scope

This lane extracts the reusable UI state and control primitives from Structurify into neutral Treeify UI packages. It covers screen state persistence, YACL option helper primitives, neutral paired controls, a neutral boolean row controller with a detail button, and the service boundary needed by a biome picker. It does not build Treeify vegetation screens and does not implement vegetation discovery.

The builder must keep the Structurify UX pattern where it is useful: searchable YACL lists, expandable groups, compact boolean rows with a detail button, paired controls, and biome dropdown presentation. The output must be clean Treeify UI infrastructure that can be consumed by the separate `ui-shell` lane and later vegetation screens.

## Owned Paths

The builder for this lane may write only these production paths:

- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/state/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/control/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/option/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/service/**` only for the biome-picker service interfaces defined in this plan

The builder may also write its own build summary:

- `mods/minecraft/treeify/docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-STATE-CONTROLS.md`

## Forbidden Paths

Do not edit these paths in this lane:

- `mods/minecraft/treeify/forge/**`
- `mods/minecraft/treeify/fabric/**`
- `mods/minecraft/treeify/neoforge/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui/screen/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/data/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/mixin/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/registry/**`
- `mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/world/**`
- build files, mod metadata, mixin configs, resources, generated version profiles

If a needed integration requires one of these paths, stop and record it in the build artifact as a dependency on the `ui-shell` lane or a later phase. Do not widen this lane locally.

## Source Files To Inspect

The builder should inspect these legacy files and copy only the reusable ideas:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreenState.java`
- `common/src/main/java/com/squinchmods/structurify/common/util/YACLUtil.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/OptionPair.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/HolderOption.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/InvisibleOptionGroup.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/DualController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/DualControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/element/DualControllerElement.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/StructureButtonController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/StructureButtonControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/BiomeStringController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/BiomeStringControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/element/BiomeStringControllerElement.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/CategoryTabAccessor.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/GroupSeparatorEntryAccessor.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/ControllerWidgetMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/OptionListWidgetMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/OptionImplMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/YACLScreenMixin.java`

Use these files only as legacy references for behavior and pitfalls:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructuresConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/StructurifyClient.java`
- `forge/src/main/java/com/squinchmods/structurify/forge/StructurifyForgeClient.java`

## Proposed New Package Paths

Create neutral Treeify packages under the current transitional Java root:

- `com.squinchmods.structurify.common.treeify.ui.state`
- `com.squinchmods.structurify.common.treeify.ui.control`
- `com.squinchmods.structurify.common.treeify.ui.control.builder`
- `com.squinchmods.structurify.common.treeify.ui.control.element`
- `com.squinchmods.structurify.common.treeify.ui.option`
- `com.squinchmods.structurify.common.treeify.ui.service`

Do not perform the broad `structurify` to `treeify` Java root rename in Phase 1. That remains a late identity phase.

## Contracts To Freeze

These names are the contract for the builder unless compilation requires a narrow adjustment. If an adjustment is made, document the reason in the build artifact.

### Screen State

Package: `com.squinchmods.structurify.common.treeify.ui.state`

- `TreeifyScreenState`
  - record fields: `String lastSearchText`, `double lastScrollAmount`, `Map<String, Boolean> collapsedGroups`
  - purpose: immutable snapshot of one YACL screen/category state

- `TreeifyScreenStateStore`
  - method: `void save(YACLScreen screen)`
  - method: `void restore(YACLScreen screen)`
  - method: `void clear()`
  - method: `Optional<TreeifyScreenState> get(String screenKey)`
  - purpose: session-scoped state holder keyed by stable screen title or caller-provided key

- `TreeifyYaclStateAccess`
  - static helper methods are acceptable if final and stateless
  - purpose: isolate YACL internals used to read search text, scroll amount, and group expansion state
  - may depend on the existing generic YACL accessors but must not introduce new mixins in this lane

The builder must handle null `OptionListWidget` defensively. The current `StructurifyConfigScreen.saveScreenState` assumes the option list exists; the new helper must not crash if a category has not initialized its list.

### Option Helpers

Package: `com.squinchmods.structurify.common.treeify.ui.option`

- `TreeifyOptionPair<K extends Option<?>, V extends Option<?>>`
  - equivalent purpose to legacy `OptionPair`

- `TreeifyHolderOption<T>`
  - equivalent purpose to legacy `HolderOption`

- `TreeifyInvisibleOptionGroup`
  - equivalent purpose to legacy `InvisibleOptionGroup`

- `TreeifyLabelOptions`
  - static factory for spacer and named spacer label options
  - replaces the generic pieces of `YACLUtil.createEmptyLabelOption`

These types must not import `StructureData`, `StructureSetData`, `WorldgenDataProvider`, `StructurifyConfig`, `LoadConfigEvent`, or any screen composer.

### Neutral Paired Control

Package: `com.squinchmods.structurify.common.treeify.ui.control`

- `TreeifyDualController<K extends Option<?>, V extends Option<?>>`
- `TreeifyDualControllerBuilder<K extends Option<?>, V extends Option<?>>`
- `TreeifyDualControllerElement`

Behavior to preserve:

- split available width between two child controls
- format value as first value plus separator plus second value
- provide one reset action only when both child options can reset
- preserve search, focus, mouse, keyboard, narration, and scroll delegation

Required cleanup from legacy behavior:

- guard nullable reset button before event delegation
- fix duplicate second-child `charTyped` delegation
- make `matchesSearch` check both first and second child widgets
- implement focus state honestly instead of always returning `false`
- avoid raw magic text where a named constant is clearer

### Neutral Row Detail Button Control

Package: `com.squinchmods.structurify.common.treeify.ui.control`

- `TreeifyBooleanDetailController`
- `TreeifyBooleanDetailControllerBuilder`
- `TreeifyBooleanDetailControllerElement`

Contract:

- wraps a YACL boolean controller with a compact detail button on the right
- uses neutral item terminology, not structure terminology
- callback type: `void open(YACLScreen parentScreen, String itemId)`
- accepts a preformatted tooltip `Component` or a formatter `Function<String, Component>`
- does not translate with `LanguageUtil.translateId("structure", ...)`
- does not assume the detail button opens a structure screen

The legacy gear symbol can be preserved in Phase 1 if it compiles cleanly, but the public class names and callback names must be neutral.

### Biome Picker Boundary

Package: `com.squinchmods.structurify.common.treeify.ui.service`

- `BiomeChoice`
  - record fields: `String id`, `Component displayName`, `Optional<Identifier> previewImage`
  - purpose: UI-ready biome option with no registry lookup needed by the controller

- `BiomeChoiceProvider`
  - method: `List<BiomeChoice> choices()`
  - method: `List<BiomeChoice> search(String query, int limit)`
  - method: `Optional<BiomeChoice> byId(String id)`
  - purpose: service boundary supplied later by discovery/rules code

Package: `com.squinchmods.structurify.common.treeify.ui.control`

- `TreeifyBiomeController`
- `TreeifyBiomeControllerBuilder`
- `TreeifyBiomeControllerElement`

Contract:

- the controller receives a `BiomeChoiceProvider`
- the controller does not call `WorldgenDataProvider.getBiomes()`
- the controller does not inspect Minecraft registries
- the element may render an optional preview image from `BiomeChoice.previewImage()`
- unknown or missing preview images must degrade to no image or a neutral unknown image without throwing
- search must match raw biome id and display name

The provider boundary is intentionally UI-facing. Later worldgen discovery owns the real biome registry scan and can adapt its output to this interface.

## Acceptance Checks

The builder must run or document why they could not run:

- `rg -n "WorldgenDataProvider|StructureData|StructureSetData|LoadConfigEvent|StructurifyConfig|getConfig\\(" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui`
- `rg -n "structure|Structure|jigsaw|structure set|StructureSet" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui`
- `rg -n "org.spongepowered.asm.mixin|Mixin|Accessor|Invoker|WrapOperation|WrapMethod" mods/minecraft/treeify/common/src/main/java/com/squinchmods/structurify/common/treeify/ui`
- compile check for the active 1.20.1 target if practical in the builder environment

Expected results:

- first command returns no matches
- second command returns no matches in public type names, public method names, or user-facing translations; incidental comments in the build summary are irrelevant
- third command returns no matches
- no new UI code writes config files, dispatches load events, or calls save/apply services directly
- new state store is instance scoped, not static mutable global state
- new controllers compile against the existing YACL version profile
- `TreeifyBiomeController` works from `BiomeChoiceProvider`, not live registry globals
- any reliance on existing YACL accessors is documented in `BUILD-P1-UI-STATE-CONTROLS.md`

Manual QA recipe to document:

- open a YACL screen using the extracted state store once the `ui-shell` lane wires a test screen
- type in search, scroll, collapse at least one group, open a detail screen, return, and confirm state restores
- verify the boolean detail row still toggles the boolean when the row body is clicked and invokes the callback only when the detail button is clicked
- verify biome search matches both namespaced ids and translated display names once a provider is available

## Required Deletions And Deferred Deletions

Required in this lane:

- no production deletions are required in Phase 1 for this lane
- no legacy classes should be modified in place
- no legacy structure screen composers should be repointed to the new controls in this lane

Deferred deletions:

- delete or retire `common/.../config/client/api/controller/StructureButtonController.java` after Treeify vegetation screens use `TreeifyBooleanDetailController`
- delete or retire `common/.../config/client/api/controller/builder/StructureButtonControllerBuilder.java` after migration
- delete or retire `common/.../config/client/api/controller/BiomeStringController.java` and its builder/element after `TreeifyBiomeController` is wired
- delete or retire legacy `DualController*`, `OptionPair`, `HolderOption`, `InvisibleOptionGroup`, and generic pieces of `YACLUtil` once all consumers move
- keep existing `common/.../mixin/yacl/**` untouched during this lane; later QA must decide whether each generic YACL mixin survives under an allowlist

Do not delete structure UI/backend files in Phase 1. Those deletions belong to later phases once replacement rules and worldgen code exist.

## Migration Report Anchors

- `TREEIFY_MIGRATION_REPORT.md#L83`: reusable UI core inventory
- `TREEIFY_MIGRATION_REPORT.md#L105`: reusable with refactor inventory
- `TREEIFY_MIGRATION_REPORT.md#L124`: generic YACL patches worth keeping
- `TREEIFY_MIGRATION_REPORT.md#L158`: current UI/backend coupling
- `TREEIFY_MIGRATION_REPORT.md#L162`: hard UI/backend couplings to remove
- `TREEIFY_MIGRATION_REPORT.md#L178`: static/singleton state couplings to replace
- `TREEIFY_MIGRATION_REPORT.md#L344`: UI layer target responsibilities
- `TREEIFY_MIGRATION_REPORT.md#L653`: modded worldgen compatibility goal that requires data-driven UI boundaries
- `TREEIFY_MIGRATION_REPORT.md#L682`: compatibility tiers that must surface as support metadata later
- `TREEIFY_MIGRATION_REPORT.md#L793`: support flags that downstream UI must be able to represent

## Rewrite Criteria Anchors

- `TREEIFY_REWRITE_CRITERIA.md#L40`: no monkeypatch rewrite
- `TREEIFY_REWRITE_CRITERIA.md#L66`: hard UI/rules/worldgen layer boundaries
- `TREEIFY_REWRITE_CRITERIA.md#L86`: honest capability surface
- `TREEIFY_REWRITE_CRITERIA.md#L134`: code health and Treeify terminology
- `TREEIFY_REWRITE_CRITERIA.md#L153`: deletion policy
- `TREEIFY_REWRITE_CRITERIA.md#L202`: mixin acceptance bar
- `TREEIFY_REWRITE_CRITERIA.md#L212`: phase code health requirements
- `TREEIFY_REWRITE_CRITERIA.md#L228`: screen state must be session scoped
- `TREEIFY_REWRITE_CRITERIA.md#L250`: Phase 1 extract UI framework gate

## Exact Builder Instructions

1. Read this plan and the five upstream docs listed in the header.
2. Confirm no other builder owns the same paths before editing.
3. Create new Treeify classes only under the owned paths in this plan.
4. Port behavior by reading legacy code, not by moving legacy files wholesale.
5. Implement `TreeifyScreenState`, `TreeifyScreenStateStore`, and `TreeifyYaclStateAccess` first.
6. Implement option helper classes second.
7. Implement the dual controller third, fixing the null reset-button and delegation bugs during extraction.
8. Implement the boolean detail controller fourth, replacing all structure terminology with neutral item/detail terminology.
9. Implement `BiomeChoice`, `BiomeChoiceProvider`, and the biome controller last.
10. Do not wire the new classes into `StructurifyClient`, loader entrypoints, or legacy structure screens.
11. Do not add or edit mixins.
12. Do not call `Structurify.getConfig()`, `LoadConfigEvent`, `WorldgenDataProvider`, registry providers, or config save methods from the new UI classes.
13. Run the acceptance `rg` commands and a compile check if practical.
14. Write `docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-STATE-CONTROLS.md` with files touched, commands run, deviations, and deferred deletions.
15. If a required method signature differs from this plan for YACL compatibility, document the exact reason and keep the conceptual contract intact.

## Builder Output Artifact

The builder must produce:

- `docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-STATE-CONTROLS.md`

The per-builder QA agent will compare that artifact and the implementation against this plan, the migration report, and the rewrite criteria.
