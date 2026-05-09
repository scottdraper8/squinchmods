# Treeify Migration Report

Date: 2026-05-08

## Goal

Separate the in-game config UI from Structurify's structure-specific backend, then assess what it would take to repurpose the system for a new mod focused on trees and mushrooms.

First-scope targets:

- global control of tree types and mushrooms
- per-biome control of tree types and mushrooms
- initial implementation target: Forge 1.20.1

This report covers:

- what can be reused directly
- what must be replaced
- what new backend is needed for trees and mushrooms
- build and packaging implications of the migration

## Executive Summary

The UI is reusable, but it is not currently isolated.

Structurify's config screens, custom YACL widgets, and state-preservation logic are good raw material for `treeify`. The backend is not generic worldgen configuration code. It is a structure and structure-set mutation system built around `Structure`, `StructureSet`, `StructurePlacement`, `StructureStart`, and jigsaw internals.

For `treeify`, the correct backend pivot is not "port the structure backend to trees." The correct pivot is:

- keep the YACL screen framework
- replace the config data model
- replace registry discovery
- replace all runtime hooks
- target biome feature lists, placed features, and configured features instead of structures

For Forge 1.20.1, the practical first backend is:

- discover tree and mushroom features from biome generation settings
- support global and per-biome enable/disable
- support global and per-biome density changes
- support height overrides only where the configured feature is directly mutable and clearly classifiable

## Current Architecture

The module is a multiloader Stonecutter project with:

- shared code in `common`
- loader glue in `fabric`, `forge`, `neoforge`
- version profiles under `versions`

Forge 1.20.1 is already a supported build profile:

- `versions/1.20.1/gradle.properties`
- `gradle.properties`

The client config screen is exposed through loader-specific entrypoints:

- Forge: `forge/src/main/java/com/squinchmods/structurify/forge/StructurifyForgeClient.java`
- Fabric Mod Menu: `fabric/src/main/java/com/squinchmods/structurify/fabric/modcompat/ModMenuCompat.java`
- NeoForge: `neoforge/src/main/java/com/squinchmods/structurify/neoforge/StructurifyNeoForgeClient.java`

The common root client bridge is:

- `common/src/main/java/com/squinchmods/structurify/common/StructurifyClient.java`

The current runtime lifecycle is:

1. initialize config and compat in `Structurify.init()`
2. load registry-backed defaults
3. overlay JSON config
4. update live registries by attaching IDs and letting mixins read config at runtime

The key lifecycle classes are:

- `common/src/main/java/com/squinchmods/structurify/common/Structurify.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/StructurifyConfig.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/StructurifyConfigSerializer.java`
- `common/src/main/java/com/squinchmods/structurify/common/registry/StructurifyRegistryManagerProvider.java`
- `common/src/main/java/com/squinchmods/structurify/common/registry/StructurifyRegistryUpdater.java`

## UI Inventory

### Reusable UI Core

These pieces are broadly reusable with moderate cleanup:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreenState.java`
- `common/src/main/java/com/squinchmods/structurify/common/util/YACLUtil.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/OptionPair.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/HolderOption.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/InvisibleOptionGroup.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/DualController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/DualControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/element/DualControllerElement.java`

These provide:

- tabbed YACL shells
- grouped option lists
- paired-field controls
- spacer/invisible grouping primitives
- search and scroll state handling

### Reusable With Refactor

These are reusable patterns, but currently tied to structure terminology or backend globals:

- `common/src/main/java/com/squinchmods/structurify/common/StructurifyClient.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/StructureButtonController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/StructureButtonControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/BiomeStringController.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/BiomeStringControllerBuilder.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/element/BiomeStringControllerElement.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/YACLScreenMixin.java`

These would need:

- renaming away from `Structure*`
- removal of direct calls to `Structurify.getConfig()`
- removal of direct `LoadConfigEvent` / save side effects
- view-model based labels/tooltips instead of structure translation assumptions

### YACL Patches Worth Keeping

The YACL mixin layer is valuable and mostly generic:

- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/CategoryTabAccessor.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/GroupSeparatorEntryAccessor.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/ControllerWidgetMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/OptionListWidgetMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/OptionImplMixin.java`

These add:

- access to YACL internals for state persistence
- description-aware search
- better search scroll behavior
- label mutation support for spacer rows

### Structure-Specific Screens To Replace

These screens should not be migrated as-is:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructuresConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetsConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructureSetConfigScreen.java`

These composers are also structure-domain specific:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/BiomeCheckOptions.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/DistanceFromWorldCenterOptions.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/FlatnessCheckOptions.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/OverlapCheckOptions.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/JigsawOptions.java`

## Current UI/Backend Coupling

The UI is not cleanly separate today.

### Hard Couplings

- screens bind directly to `Structurify.getConfig()`
- screens use `config::save` directly in YACL builders
- the root screen invokes `LoadConfigEvent` before screen construction
- saving triggers file I/O and live registry updates
- list contents come from `WorldgenDataProvider`
- biome options come from live registry-backed worldgen data

The main coupling points are:

- `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreen.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/StructurifyConfig.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/WorldgenDataProvider.java`
- `common/src/main/java/com/squinchmods/structurify/common/registry/StructurifyRegistryManagerProvider.java`

### State/Singleton Couplings

The client side also has static mutable state in:

- `StructurifyClient`
- `StructuresConfigScreen`
- `StructureSetsConfigScreen`

That should be replaced with:

- a UI session object
- injected view-model providers
- stateless screen builders where possible

## Backend Inventory

### Data Model That Must Be Replaced

These are structure-shaped and should not survive into `treeify` unchanged:

- `common/src/main/java/com/squinchmods/structurify/common/config/data/StructureLikeData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/StructureNamespaceData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/StructureData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/StructureSetData.java`

These leaf DTOs are also structure semantics:

- `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/JigsawData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/FlatnessCheckData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/BiomeCheckData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/OverlapCheckData.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/DistanceFromWorldCenterCheckData.java`

### Serializers That Must Be Replaced

- `common/src/main/java/com/squinchmods/structurify/common/config/serialization/StructureDataSerializer.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/serialization/StructureNamespaceDataSerializer.java`
- `common/src/main/java/com/squinchmods/structurify/common/config/serialization/StructureSetDataSerializer.java`

The serializer pattern is reusable, but the schema is not.

### Registry Discovery That Must Be Rewritten

The current discovery backbone is:

- `common/src/main/java/com/squinchmods/structurify/common/config/data/WorldgenDataProvider.java`

This class currently:

- enumerates structures
- enumerates structure namespaces
- derives `StructureData` from `Structure.biomes()`, `step()`, and `terrainAdaptation()`
- derives `StructureSetData` from placements and weighted entries
- detects jigsaw-like structures
- contains hardcoded structure/mod exceptions

This is one of the largest rewrite points.

### Runtime Hooks That Must Be Replaced

These mixins are the heart of the current structure backend and do not map directly to vegetation:

- `common/src/main/java/com/squinchmods/structurify/common/mixin/ChunkGeneratorMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/StructureManagerMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/StructureMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/StructureSetMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/StructureSelectionEntryMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/placement/StructurePlacementMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/placement/RandomSpreadStructurePlacementMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/jigsaw/JigsawStructureMixin.java`

Optional compatibility mixins are also structure-only:

- `common/src/main/java/com/squinchmods/structurify/common/mixin/compat/RepurposedStructuresModifySpreadMixin.java`
- `common/src/main/java/com/squinchmods/structurify/common/mixin/compat/YungJigsawStructureMixin.java`
- `forge/src/main/java/com/squinchmods/structurify/forge/mixin/compat/StructureGelApiModifySpreadMixin.java`

### Runtime Check System That Must Be Replaced

These systems assume `StructureStart`, `StructurePiece`, bounding boxes, and section claims:

- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructureChecker.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructureDistanceFromWorldCenterCheck.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructureFlatnessCheck.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructureBiomeCheck.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructureOverlapCheck.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/checks/StructurePieceSampler.java`
- `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/StructureSectionClaim.java`

These do not transfer directly to trees or mushrooms.

## What Can Stay On The Backend

These pieces are still useful as infrastructure or patterns:

- loader lifecycle pattern
- config load/update event pattern
- registry bootstrap pattern
- datapack/resource-pack-backed registry loading
- generic biome holder conversion utilities

Main classes worth reusing or adapting:

- `common/src/main/java/com/squinchmods/structurify/common/events/common/LoadConfigEvent.java`
- `common/src/main/java/com/squinchmods/structurify/common/events/common/UpdateRegistriesEvent.java`
- `common/src/main/java/com/squinchmods/structurify/common/events/base/EventHandler.java`
- `common/src/main/java/com/squinchmods/structurify/common/registry/StructurifyRegistryManagerProvider.java`
- `common/src/main/java/com/squinchmods/structurify/common/registry/StructurifyResourcePackProvider.java`
- `common/src/main/java/com/squinchmods/structurify/common/util/BiomeUtil.java`
- `common/src/main/java/com/squinchmods/structurify/common/util/ChunkPosUtil.java`

Important note:

`StructurifyRegistryManagerProvider` already loads:

- `BIOME`
- `CONFIGURED_FEATURE`
- `PLACED_FEATURE`
- `STRUCTURE`
- `STRUCTURE_SET`

That means the registry bootstrap already has the right general shape for `treeify`, even though current consumers only use the structure side.

## Recommended Treeify Backend Model

## High-Confidence Direction

For Forge 1.20.1, `treeify` should target biome feature graphs, not structure registries.

The main runtime entities should be:

- `Biome`
- `BiomeGenerationSettings`
- `PlacedFeature`
- `ConfiguredFeature`
- `PlacementModifier`

The primary generation step of interest is:

- `GenerationStep.Decoration.VEGETAL_DECORATION`

### Why This Is The Right Pivot

Trees and mushrooms are not generated through the structure pipeline.

They typically appear as:

- placed features referenced by biomes
- configured features behind those placed features
- selectors or composite vegetation features
- placement-modifier stacks controlling frequency/count/chance/noise behavior

Because of that, the closest analogue to Structurify's structure model is:

- discover vegetation candidates from biome feature lists
- expose them as configurable entries
- patch biome feature lists and feature instances at runtime

## Recommended Layer Split

The clean separation point is:

- `UI`
- `rules`
- `worldgen`

### UI Layer

Responsibilities:

- YACL screens
- navigation state
- biome/tag pickers
- detail editors
- save/apply/reload controls

The UI layer should depend only on view models and service interfaces.

### Rules Layer

Responsibilities:

- config DTOs
- serialization
- inheritance rules
- global defaults
- biome overrides
- feature classification metadata

This layer should know nothing about YACL and nothing about runtime mixins.

### Worldgen Layer

Responsibilities:

- registry discovery
- feature classification
- biome feature replacement
- placed/configured feature cloning
- apply/reload integration

This layer should know nothing about screen layout.

## Suggested Treeify Data Model

The current structure model should be replaced with something closer to:

- `VegetationConfig`
- `VegetationFeatureData`
- `BiomeVegetationData`
- `ConfiguredVegetationVariantData`

Suggested top-level config shape:

```json
{
  "general": {
    "disable_all_trees": false,
    "disable_all_mushrooms": false,
    "global_tree_density_multiplier": 1.0,
    "global_mushroom_density_multiplier": 1.0
  },
  "features": [
    {
      "name": "minecraft:trees_birch",
      "category": "tree_selector",
      "is_disabled": false,
      "density_multiplier": 1.0,
      "enable_height_override": false,
      "height_delta": 0
    }
  ],
  "biomes": [
    {
      "name": "minecraft:birch_forest",
      "disabled_features": [],
      "added_features": [],
      "feature_density_overrides": {},
      "feature_height_overrides": {}
    }
  ]
}
```

The exact schema can change, but the key distinction should remain:

- global feature-level control
- biome-specific feature overrides

## Forge 1.20.1 Apply Strategy

There are two viable worldgen-application strategies for the first implementation.

### Option A: Runtime Registry Patching

This is closest to Structurify's current architecture.

Approach:

- inspect biomes and feature lists directly
- cache patched biome feature lists
- clone placed/configured features when overrides diverge
- apply changes through a runtime service after config load/save

Pros:

- aligns with the existing Structurify architecture
- potentially more portable later across loaders
- does not force Forge-only concepts into the rules layer

Cons:

- more custom runtime mutation code
- more custom cache invalidation logic
- more direct interaction with MC internals

### Option B: Forge BiomeModifier Backend

This is the most Forge-native implementation path for the first release.

Approach:

- model rules as biome feature replacement operations
- use Forge `BiomeModifier` behavior to remove and add `PlacedFeature`s during biome modification
- use `Phase.REMOVE` to strip unwanted tree/mushroom features
- use `Phase.ADD` to inject replacement `PlacedFeature`s
- register any custom biome-modifier serializer or codec on the Forge side if stock add/remove behavior is not enough

Pros:

- idiomatic for Forge 1.20.1
- cleaner apply model for a Forge-only first release
- less pressure to mutate live biome internals directly

Cons:

- Forge-specific backend
- later Fabric or NeoForge parity will need a different worldgen apply implementation
- complex inheritance or dynamic per-session overrides may require a custom modifier instead of only stock modifiers

### Recommendation

For the first Forge 1.20.1 release:

- keep `UI` and `rules` loader-agnostic
- implement the `worldgen` apply layer as Forge-specific
- prefer a biome-modifier-backed apply service where possible
- fall back to custom runtime feature cloning and replacement only where biome modifiers are too coarse

That gives the first version the lowest-risk apply mechanism without contaminating the UI and rules layers with Forge-only details.

## Suggested Runtime Services

### Registry And Discovery

Replace `WorldgenDataProvider` with something like:

- `VegetationWorldgenDataProvider`

Responsibilities:

- enumerate all biomes
- inspect biome feature lists by generation step
- discover candidate tree and mushroom entries
- classify entries
- capture default per-biome feature membership
- capture default density-related placement modifiers
- capture height-capable configured features where possible

### Runtime Update Layer

Replace `StructurifyRegistryUpdater` with something like:

- `VegetationRegistryUpdater`

Responsibilities:

- bind IDs or metadata to biomes/features if needed
- rebuild cached vegetation mappings when registries reload
- support live apply on config save

For Forge 1.20.1, this service can own:

- biome-modifier generation or registration
- replacement feature holder assembly
- cache invalidation when rules change

### Biome Patch Layer

Add something like:

- `BiomeFeaturePatchService`

Responsibilities:

- build patched feature lists per biome
- remove disabled tree/mushroom features
- inject enabled features into additional biomes
- swap in per-biome cloned placed/configured features where overrides require divergence

If the Forge backend uses biome modifiers, this service becomes the rule-resolution and feature-construction layer feeding those modifiers.

### Clone Factories

Add:

- `PlacedFeatureCloneFactory`
- `ConfiguredFeatureCloneFactory`

Responsibilities:

- clone placed features when density must differ per biome
- clone configured features when height must differ
- preserve original IDs and source relationships for traceability

## Recommended Feature Classification

The backend should classify vegetation candidates into categories such as:

- `DIRECT_TREE`
- `TREE_SELECTOR`
- `DIRECT_HUGE_MUSHROOM`
- `MUSHROOM_PATCH`
- `MIXED_VEGETATION`

This matters because support quality differs by category.

## Capability Matrix

| Capability | Best Hook | Confidence | Notes |
|---|---|---|---|
| Global enable/disable trees | biome feature list filtering | High | good v1 target |
| Global enable/disable mushrooms | biome feature list filtering | High | huge mushrooms easier than small patch mushrooms |
| Per-biome include/exclude | biome feature list patching | High | direct and practical |
| Global density | placed feature placement modifier adjustment | High | multiple modifier types need handling |
| Per-biome density | per-biome cloned placed features | Medium-High | shared placed features require cloning |
| Height override | configured feature cloning/mutation | Medium | only reliable for directly classifiable tree configs |
| Species-level control inside selectors | selector graph rewrite | Medium-Low | main complexity wall |

## What "Tree Types" Means In Practice

This is the main design risk.

High confidence:

- many vanilla and modded trees are not represented as one simple universal "tree type" object
- some are direct tree features
- some are selector features that choose among multiple sub-features
- some are part of mixed vegetation graphs

Implication:

For v1, the safest public abstraction is not "every species everywhere."

The safest abstraction is:

- per feature entry
- per biome
- with a best-effort tree/mushroom classification

You can still present friendly names like oak, birch, spruce, huge_red_mushroom where classification is clear.

## Density Control

Density is feasible, but it is not a single field.

The system will need to inspect and potentially mutate placement modifiers such as:

- count-based placement
- rarity/chance placement
- noise-based placement

Recommended v1 behavior:

- expose a density multiplier
- apply it only to known modifier types
- leave unsupported modifiers unchanged
- mark entries as partially scalable when exact scaling is not possible

UI recommendation:

- present density as `0.0x` to `2.0x` or `Sparse / Normal / Dense`
- avoid implying that density is a universal exact field

## Height Control

Height is more constrained than density.

High confidence:

- height is generally configured in the configured feature, not the placed feature
- direct tree configs can often be mutated
- huge mushrooms may also be mutable if their config is direct and identifiable

Main limitation:

- selector trees and mixed vegetation features may not support clean per-type height control

Recommended v1 behavior:

- support height overrides only for direct tree configs
- optionally huge mushrooms if the config is straightforward
- mark selectors and mixed vegetation as unsupported or partially supported

## Mushroom Scope Recommendation

Treat mushrooms as two separate categories:

- huge mushrooms
- small patch mushrooms

Huge mushrooms are better first-scope targets.

Small mushrooms are often patch-style vegetation and can be mixed into broader vegetation features, which makes clean classification and isolated control harder.

## Modded Worldgen Compatibility

The intended model is that `treeify` should behave as much like an interactive datapack as practical.

That means:

- discover worldgen content from loaded registries and biome generation data
- avoid hardcoding support around a small vanilla-only vegetation list
- treat modded trees and mushrooms as first-class candidates when they appear in standard worldgen structures
- resolve rules against loaded data, then apply worldgen replacements or overrides

This is already aligned with the proposed registry-driven discovery and patching model, but the compatibility target should be stated explicitly:

- `treeify` should load vegetation definitions from the active modded worldgen environment
- `treeify` should not require bespoke per-mod UI code just to see most modded vegetation entries
- `treeify` should degrade by capability tier when modded worldgen becomes more composite or opaque

### What Compatibility Means Here

Compatibility does not mean that every modded tree will always appear as a perfectly isolated species entry.

Compatibility means:

- the discovery layer should find candidate tree and mushroom worldgen entries from loaded biome feature graphs
- the UI should surface those entries as configurable units
- the apply layer should be able to remove, replace, or override those entries when their structure is understood

The quality of control then depends on how that vegetation is represented by the modded worldgen data.

### Compatibility Tiers

#### Tier 1: Direct Feature Compatibility

Best case.

The modded tree or mushroom appears as:

- a distinct `PlacedFeature`
- backed by a distinct `ConfiguredFeature`
- referenced in biome generation in a straightforward way

For this tier, `treeify` should usually support:

- enable/disable
- per-biome include/exclude
- density overrides
- height overrides where the underlying configured feature supports them

#### Tier 2: Selector Compatibility

Moderate case.

The modded vegetation appears through:

- selector features
- weighted alternatives
- grouped vegetation entries that choose among several sub-features

For this tier, `treeify` should usually support:

- coarse feature-level enable/disable
- coarse per-biome include/exclude
- some density control

But it may not reliably support:

- isolated per-species controls for every branch
- isolated height control for only one branch of a selector

#### Tier 3: Mixed Vegetation Compatibility

Hard case.

The modded vegetation is embedded inside:

- mixed vegetation graphs
- patch features that combine multiple content types
- custom bundled worldgen entries where trees or mushrooms are not separable cleanly

For this tier, `treeify` may only support:

- whole-entry enable/disable
- limited density adjustment

And it may need to mark entries as:

- partially supported
- coarse-control only
- unsupported for height or per-species editing

#### Tier 4: Opaque Custom Feature Compatibility

Worst case.

A mod may use highly custom feature logic where tree identity, density, or placement rules are not cleanly exposed through normal configured or placed feature structures.

For this tier, `treeify` should aim to:

- detect the entry
- classify it as opaque or unsupported
- avoid corrupt or misleading controls

The system should prefer honest limited support over pretending every control works.

### Worldgen Impact Expectations

The proposed approach is designed to minimize worldgen disruption by operating on discovered vegetation entries rather than trying to replace all vegetation logic wholesale.

That said, worldgen impact still matters in several ways:

- removing or replacing feature entries can change biome composition noticeably
- cloned placed features can diverge per biome, which is intended but increases the number of effective feature variants
- cloned configured features for height overrides can produce biome-specific tree variants that no longer match their original shared definitions
- selector-heavy vegetation may only be controllable at a coarse level, which means edits can affect a group of related outcomes together

This is still broadly comparable to an interactive datapack approach:

- inspect loaded worldgen
- compute overrides
- apply controlled replacements

But it is not zero-impact. It changes generated results by design.

### Design Requirement For Compatibility

To preserve broad mod compatibility, the discovery and apply layers should follow these rules:

1. Prefer registry inspection over hardcoded species knowledge.
2. Preserve original feature references when no override is needed.
3. Clone only when per-biome or per-feature divergence is required.
4. Track provenance so each replacement knows which original feature it came from.
5. Surface support level in the UI instead of assuming all discovered entries support all controls.

### Recommended UI Implications

The UI should reflect compatibility honestly.

Each discovered vegetation entry should eventually expose metadata such as:

- classification: direct tree, selector, huge mushroom, patch, mixed, opaque
- support flags: biome override, density override, height override
- notes: coarse control only, partial support, unsupported height

That will let `treeify` feel interactive and data-driven like Structurify without overpromising uniform control across all modded worldgen implementations.

## UI Migration Requirements

The current UI should be split into two layers.

### Layer 1: Generic UI Framework

Keep or extract:

- screen shell
- YACL helpers
- custom YACL widgets
- state capture/restore
- biome picker

This layer should know nothing about:

- structures
- trees
- worldgen registries
- config save side effects

### Layer 2: Domain Screen Builders

Replace current structure builders with vegetation builders such as:

- `VegetationConfigScreen`
- `VegetationFeaturesScreen`
- `VegetationFeatureConfigScreen`
- `BiomeVegetationScreen`

These should consume view models from a backend service interface instead of touching config singletons directly.

## Required UI Separation Work

1. Remove direct `Structurify.getConfig()` access from screen builders.
2. Remove direct `LoadConfigEvent` dispatch from UI entrypoints.
3. Replace `config::save` side effects with an injected save/apply service.
4. Replace static mutable UI state with session-scoped state objects.
5. Rename structure-labeled widgets and tooltip assumptions.
6. Convert screen builders to accept view-model providers.

## Required Backend Replacement Work

1. Replace structure config DTOs with vegetation DTOs.
2. Replace structure serializers with vegetation serializers.
3. Replace `WorldgenDataProvider` with vegetation discovery.
4. Replace structure/set registry updater logic with vegetation registry update logic.
5. Replace all structure-generation mixins with biome feature and feature placement hooks.
6. Replace structure check systems with vegetation-relevant validation.
7. Replace random spread and weight logic with placed-feature density logic.

## Recommended Forge 1.20.1 Scope

### Strong V1 Scope

- direct tree features
- tree selector features at coarse entry level
- huge mushrooms
- global enable/disable
- per-biome include/exclude
- global density multipliers
- per-biome density overrides
- direct-config height override only

Apply mechanism recommendation for this scope:

- Forge biome modifiers for add/remove
- custom feature cloning for density and height divergence

### Defer To Later

- full selector graph species-level editing
- universal modded tree species control
- small mushroom patch fine-grained editing everywhere
- highly custom vegetation graphs
- cross-loader parity before Forge 1.20.1 is stable

## Build And Packaging Implications

The folder was renamed, but the module is still structurify internally.

Current identity is spread across:

- `settings.gradle.kts`
- `gradle.properties`
- `fabric.mod.json`
- `forge/src/main/resources/META-INF/mods.toml`
- `neoforge` mod metadata
- package names under `com.squinchmods.structurify`
- mixin config names like `structurify-common.mixins.json`

Important examples:

- `settings.gradle.kts` sets `rootProject.name = "structurify"`
- `gradle.properties` sets `mod.id=structurify`
- `gradle.properties` sets `mod.group=com.squinchmods.structurify`

If `treeify` becomes its own real mod, the migration requires:

- new mod id
- new package namespace
- new metadata strings and URLs
- renamed mixin config files
- renamed resources/assets namespace

This is separate from the UI/backend split, but it should be planned together.

## Concrete Migration Plan

### Phase 1: Extract UI Framework

Create a neutral UI package and move these concepts into it:

- YACL shell builder
- search/scroll/group state preservation
- dual-field controls
- boolean+detail-button control
- invisible groups and spacing helpers
- biome/tag picker

At the same time, introduce interfaces such as:

- `ConfigUiCatalogService`
- `ConfigUiSaveService`
- `ConfigUiSession`

The current structure screens should be left in place until replacement vegetation screens exist.

### Phase 2: Create Vegetation Catalog

Build:

- `VegetationWorldgenDataProvider`
- `VegetationFeatureClassifier`
- `BiomeVegetationIndex`

Output should include:

- feature id
- feature category
- source generation step
- source biomes
- density-control support flags
- height-control support flags

### Phase 3: Create Vegetation Config Schema

Build:

- vegetation config DTOs
- serializers
- load/merge/save logic
- migration-safe defaults

### Phase 4: Replace Runtime Hooks

Build:

- biome feature patch service
- placed feature clone factory
- configured feature clone factory
- live apply/update path on config save

### Phase 5: Build Treeify Screens

Build screens for:

- global vegetation controls
- feature list
- feature detail
- biome-specific overrides

### Phase 6: Rename And Repackage

After architecture is stable:

- rename mod id
- rename packages
- rename assets namespace
- rename mixin configs
- update loader metadata

## Main Risks

1. Tree type classification is not universal.
2. Shared placed features force cloning for per-biome divergence.
3. Density is approximate across heterogeneous placement modifiers.
4. Height override support will be uneven across feature categories.
5. Small mushrooms are harder than huge mushrooms.
6. Some existing UI code assumes structure-specific translation keys and symbols.

## Recommendation

Proceed with a clean split:

- extract the UI framework first
- do not try to generalize the structure backend
- implement a new vegetation backend centered on biome feature lists
- launch Forge 1.20.1 first with coarse but reliable tree and huge-mushroom controls

The current codebase is a strong source for:

- UI architecture
- registry/bootstrap patterns
- config lifecycle patterns

It is not a strong source for:

- direct runtime logic for trees and mushrooms

## Deliverable Summary

The minimal realistic migration outcome for first release is:

- reusable YACL UI framework extracted from Structurify
- new vegetation config schema
- Forge 1.20.1 backend for trees and mushrooms
- global and per-biome controls
- density controls
- selective height controls

That is feasible.

Trying to preserve the structure runtime model instead of replacing it would increase complexity and slow the project down.
