# FreeTerraForged outstanding pre-release work

Remove an item when its implementation and validation are complete.

## Metadata

- Replace NeoForge's hard-coded version with `version="${version}"`. Update `neoforge/build.gradle`
  to expand `META-INF/neoforge.mods.toml`, not the nonexistent `META-INF/mods.toml` target.
- Change Fabric's nonexistent `assets/freeterraforged/icon.png` reference to the packaged root
  `logo.png`.
- Preserve Fabric's author list (`dags`, `Won-Ton`, `etcodehome`, `psiber`), align NeoForge authors
  to `dags,Won-Ton,etcodehome,psiber`, and retain `raccoonman` in NeoForge credits for ReTerraForged
  attribution.
- Give both loaders the same README-consistent product description: “FreeTerraForged is a
  community-driven fork of ReTerraForged for modern Minecraft, providing highly customizable
  Overworld terrain generation and continuing the TerraForged lineage.”

Preserve the mod ID, display name, project URLs, NeoForge icon, Fabric version placeholder, and
TerraForged/ReTerraForged migration, provenance, license, and copyright identifiers.

## Compatibility and diagnostics

- Malformed and unknown underground-biome registrations do not reach a complete actionable
  diagnostic boundary. TerraBlender composition diagnostics return literal zeros for unknown-entry
  and classification-failure counts, production logging omits those terms, ordinary layout counts
  have no production consumer, and malformed source entries can fail while constructing the original
  parameter list before local null screening. Define and validate a bounded failure and diagnostic
  policy before changing production behavior.
- The surface preview resolver does not apply the existing `SurfaceBiomeFilter`, and
  `PreviewBiomeQueryContext` has no production caller. Use the retained exact-product preview probe
  with a behavior-bearing compatibility registration to bound the visible impact before designing a
  fix.
- Production builds report Mixin remap warnings for TerraBlender and world-generation targets.
  Establish whether the affected optional Mixins apply correctly at runtime.

## World identity and preset ownership

- `WorldSettings.Properties.spawnType`, `spawnX`, and `spawnZ` are static even though their codec,
  copy method, editor, and active-preset spawn initialization treat them as per-preset properties.
  Loading or constructing another preset can overwrite the selected preset's spawn configuration.
  Restore instance ownership and validate preset round trips, concurrent preset presence, initial
  world creation, and saved-world spawn authority in a dedicated change.

## Reliability and cleanup

- `FTFPlacementModifiers` registers the serialized path `fast_poission`. This resembles a spelling
  error, but changing a registry identifier can break existing data. Make an explicit compatibility
  decision before editing it.
- `PresetConfigScreen.copyToZip` catches an archive-write `IOException`, prints it, and returns;
  `exportAsDatapack` then deletes its temporary tree and logs a successful export. A real archive
  failure can therefore be presented as success. Propagate the failure and validate the user-facing
  result.
- `RuntimeRegistryExporter` has no production caller. Its codec error callback also discards the
  error text. Remove the unused implementation or define its ownership and surface codec failures.
- `PresetListPage` names the ReTerraForged migration directory constant `LEGACY_FTF_PRESET_PATH`
  even though it is initialized through `ConfigUtil.legacy_rtf`. The behavior must remain
  legacy-compatible, but the internal symbol should be clarified.
