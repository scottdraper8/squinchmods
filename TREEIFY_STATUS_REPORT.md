# Treeify Rewrite Status Report
Date: 2026-05-08

## Accomplishments
- **Core Architecture Rewrite:** Successfully moved from a structure-bound backend to a clean `ui` / `rules` / `worldgen` separation.
- **Identity Conversion:** Completed the repository-wide rebranding from `Structurify` to `Treeify` and namespace migration from `com.faboslav` to `com.squinchmods`.
- **UI Framework Extraction:** Extracted the YACL UI shell, state persistence, and controllers into neutral packages.
- **Worldgen Backend:** Implemented a new vegetation-discovery engine and Forge BiomeModifier apply path for Minecraft 1.20.1+.
- **Config & Rules Layer:** Implemented DTOs, serializers, and inheritance-aware rule logic.
- **Build Hardening:** Upgraded the project to Gradle 9.5.0, implemented performance optimizations (16GB heap, G1GC), and resolved all deprecation warnings.

## Objective
The goal is to enable the Treeify configuration GUI to populate automatically from the Main Menu (without requiring a world to be loaded) by implementing a registry loader that simulates the server environment, similar to the legacy utility we deleted in Phase 6.

## Current Obstacle: Build Failure (Compilation)
We are currently blocked by compilation errors in `TreeifyResourcePackProvider.java` across multiple Minecraft versions (1.21.x and 26.1.2).

### The Technical Issues:
1.  **Missing `PermissionSet`:** The `WorldLoader.InitConfig` constructor in newer Minecraft versions requires a `PermissionSet` object. We have not been able to resolve the correct import path (`net.minecraft.server.permissions.PermissionSet` or `net.minecraft.commands.PermissionSet` are not resolving consistently across all Stonecutter profiles).
2.  **`Util` Symbol Resolution:** `net.minecraft.Util` (used for `backgroundExecutor()`) is failing to resolve in certain versions, likely due to obfuscation differences or package moves in modern Minecraft versions.
3.  **API Divergence:** Different Minecraft versions (1.20.1 vs 1.21.x vs 26.x) have significantly different constructors for `PackConfig` and `InitConfig`, making it difficult to write a single source-compatible file without more specific Stonecutter version guards.

### Path Forward:
- [ ] Determine the exact package for `PermissionSet` and `Util` using a small script to scan the `loom` classpath.
- [ ] Refactor `TreeifyResourcePackProvider` to use more granular Stonecutter version guards if necessary to isolate version-specific constructors.
