# Phase 2 Lane Plan: P2-DISCOVERY

## Header

- phase: 2
- lane: `discovery`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Replace structure discovery with vegetation discovery and classification. Enumerate biomes, inspect generation-step feature lists, discover tree and mushroom candidates, classify support tiers, and index source biomes and feature provenance.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/worldgen/discovery/**`
- forbidden paths: screens, serializers, Forge apply hooks, legacy structure DTOs (`StructureData`, `StructureSetData`, `WorldgenDataProvider`).
- dependencies: Phase 1 UI interfaces.

## Deliverable

- builder task: Implement `VegetationWorldgenDataProvider`, `VegetationFeatureClassifier`, and `BiomeVegetationIndex`.
- expected outputs: Discovered entries must include feature id, category, source biomes, generation step, and support flags.
- required deletions or quarantine actions: No structure-era discovery code to be modified yet.

## Traceability

- plan_ids: `P2-WORLDGEN-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L457`, `TREEIFY_MIGRATION_REPORT.md#L923`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L274`

## Acceptance Checks

- build/test/manual QA checks: No new dependencies on structure-era models. Discovery output includes classification and support metadata.

## Handoff

- target builder: `catalog-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-02/build/BUILD-P2-DISCOVERY.md`