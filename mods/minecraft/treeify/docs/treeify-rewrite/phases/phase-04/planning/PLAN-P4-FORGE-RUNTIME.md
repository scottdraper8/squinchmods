# Phase 4 Lane Plan: P4-FORGE-RUNTIME

## Header

- phase: 4
- lane: `forge-runtime`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Create the Treeify runtime backend for Forge 1.20.1 using Biome Modifiers.
- owned paths: `forge/src/main/java/com/squinchmods/structurify/common/treeify/forge/worldgen/**` (and associated common hooks if needed)
- forbidden paths: Generic UI framework, old structure screens, repo-wide rename.
- dependencies: Phase 2 Discovery, Phase 3 Rules, Phase 4 Clone Factories.

## Deliverable

- builder task: Implement `TreeifyBiomeModifier`, `BiomePatchService`, and integration with Forge registry events.
- expected outputs: Global enable/disable support, per-biome include/exclude, and live apply/update on config reload.
- required deletions or quarantine actions: Documented non-Treeify legacy status for structure mixins.

## Traceability

- plan_ids: `P4-RUNTIME-002`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L469`, `TREEIFY_MIGRATION_REPORT.md#L947`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L299`

## Acceptance Checks

- build/test/manual QA checks: Disabled features are removed from biomes. Per-biome density overrides create/reuse replacements. No new runtime dependency on structure-era backend paths.

## Handoff

- target builder: `forge-runtime-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-04/build/BUILD-P4-FORGE-RUNTIME.md`