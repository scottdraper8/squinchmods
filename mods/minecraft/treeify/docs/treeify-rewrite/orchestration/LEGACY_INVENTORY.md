# Treeify Legacy Inventory

Date: 2026-05-08

This inventory tracks Structurify-era systems that must be deleted, replaced, or deliberately kept during the Treeify overhaul.

The default posture is delete-first for structure-specific runtime code. A keep decision is valid only when the code has direct value for Treeify after structure terminology and coupling are removed.

## Status Values

| Status | Meaning |
|---|---|
| `keep-refactor` | Useful concept, but must move behind Treeify naming and boundaries. |
| `replace` | Required capability, but the current implementation is structure-bound. |
| `delete` | Structure-only code with no intended Treeify runtime role. |
| `freeze` | Do not touch until the identity or packaging phase. |
| `review` | Needs phase-specific confirmation before delete or keep. |

## Inventory

| Area | Current Paths | Status | Replacement Owner | Notes |
|---|---|---|---|---|
| Root config screen shell | `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreen.java` | `replace` | Phase 1 UI shell lane | Keep the YACL screen shape and state behavior, remove direct config singleton and load/save side effects. |
| Screen state persistence | `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructurifyConfigScreenState.java`, `common/src/main/java/com/squinchmods/structurify/common/mixin/yacl/**` | `keep-refactor` | Phase 1 UI state lane | Preserve generic state behavior with Treeify naming and documented YACL mixin justification. |
| Generic YACL helpers | `common/src/main/java/com/squinchmods/structurify/common/util/YACLUtil.java`, `common/src/main/java/com/squinchmods/structurify/common/config/client/api/option/**`, `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/DualController*` | `keep-refactor` | Phase 1 UI state lane | Keep only helpers that are domain-neutral after extraction. |
| Structure row controller | `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/StructureButtonController.java`, `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/StructureButtonControllerBuilder.java` | `replace` | Phase 1 UI shell lane | Rebuild as a neutral enabled-row/detail-button controller. |
| Biome picker | `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/BiomeStringController.java`, `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/builder/BiomeStringControllerBuilder.java`, `common/src/main/java/com/squinchmods/structurify/common/config/client/api/controller/element/BiomeStringControllerElement.java` | `replace` | Phase 1 UI state lane, Phase 2 discovery lane | Keep UX pattern, replace `WorldgenDataProvider` dependency with service-supplied options. |
| Structure list and detail screens | `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/StructuresConfigScreen.java`, `StructureConfigScreen.java`, `StructureSetsConfigScreen.java`, `StructureSetConfigScreen.java` | `delete` | Phase 5 screen integration lane | Replaced by vegetation catalog and detail screens. |
| Structure option composers | `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/structure/**` | `delete` | Phase 5 screen integration lane | Jigsaw, spread, flatness, overlap, and structure biome checks do not map to Treeify. |
| Structure DTOs | `common/src/main/java/com/squinchmods/structurify/common/config/data/Structure*.java`, `common/src/main/java/com/squinchmods/structurify/common/config/data/structure/**` | `delete` | Phase 3 rules lane, Phase 6 cleanup lane | Replaced by vegetation rule DTOs and support metadata. |
| Structure serializers | `common/src/main/java/com/squinchmods/structurify/common/config/serialization/Structure*.java`, structure check serializers | `delete` | Phase 3 rules lane, Phase 6 cleanup lane | Replaced by Treeify rule serializers. |
| Worldgen defaults provider | `common/src/main/java/com/squinchmods/structurify/common/config/data/WorldgenDataProvider.java` | `replace` | Phase 2 discovery lane | Current provider exposes structure and biome defaults; Treeify needs vegetation catalog services. |
| Registry manager/resource pack loading | `common/src/main/java/com/squinchmods/structurify/common/registry/**` | `review` | Phase 2 discovery lane, Phase 4 runtime lane | Useful pattern, but must not preserve structure registry mutation behavior. |
| Structure runtime APIs | `common/src/main/java/com/squinchmods/structurify/common/api/StructurifyStructure*.java`, `StructurifyWithStructureSet.java`, `StructurifyRandomSpreadStructurePlacement.java` | `delete` | Phase 6 cleanup lane | Structure identity/state APIs must not survive into Treeify runtime. |
| Generic option APIs | `common/src/main/java/com/squinchmods/structurify/common/api/StructurifyOption.java`, `StructurifyListOption.java` | `review` | Phase 3 rules lane | Keep only if they become domain-neutral Treeify rule primitives. |
| Structure generation mixins | `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/**`, `common/src/main/java/com/squinchmods/structurify/common/mixin/StructureManagerMixin.java`, `ChunkGeneratorMixin.java`, `LevelChunkMixin.java` | `delete` | Phase 4 runtime lane, Phase 6 cleanup lane | Replaced by vegetation apply path and documented worldgen hooks. |
| Structure compat mixins | `common/src/main/java/com/squinchmods/structurify/common/mixin/compat/**`, loader compat mixin paths | `delete` | Phase 6 cleanup lane | Structure-mod compatibility is out of scope for Treeify. |
| Structure check/debug runtime | `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/**`, `common/src/main/java/com/squinchmods/structurify/common/debug/**` | `delete` | Phase 6 cleanup lane | Not relevant to vegetation control. |
| Commands | `common/src/main/java/com/squinchmods/structurify/common/commands/StructurifyCommand.java` | `replace` | Phase 5 or Phase 7 | Keep command concept only if Treeify needs catalog/debug commands. |
| Loader entrypoints | `fabric/**`, `forge/**`, `neoforge/**` entrypoints and metadata | `freeze` | Phase 7 identity lane | Narrow adapter changes only before the final identity phase. |
| Build metadata and namespace | `settings.gradle.kts`, `gradle.properties`, loader metadata, asset namespace, mixin config filenames | `freeze` | Phase 7 identity lane | Avoid broad rename churn until the architecture is stable. |

## Review Rules

- Any `keep-refactor` item must lose structure terminology before final sign-off.
- Any `review` item must become `keep-refactor`, `replace`, or `delete` before Phase 6 exits.
- Any surviving mixin must be listed in a phase QA report with target, purpose, loader scope, and justification.
- Any deleted subsystem must also be removed from build wiring, resource files, and entrypoints when the owning phase reaches cleanup.
