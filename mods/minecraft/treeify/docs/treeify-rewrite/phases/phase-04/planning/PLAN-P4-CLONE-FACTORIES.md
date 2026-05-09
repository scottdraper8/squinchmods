# Phase 4 Lane Plan: P4-CLONE-FACTORIES

## Header

- phase: 4
- lane: `clone-factories`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Implement placed and configured feature cloning to allow per-biome divergence.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/worldgen/clone/**`
- forbidden paths: Generic UI framework, old structure screens, repo-wide rename.
- dependencies: Phase 2 Discovery, Phase 3 Rules.

## Deliverable

- builder task: Implement `PlacedFeatureCloneFactory` and `ConfiguredFeatureCloneFactory`.
- expected outputs: Factories that can deep-clone features, preserving original provenance and allowing modification of density (placement modifiers) and height (configured feature fields).
- required deletions or quarantine actions: None.

## Traceability

- plan_ids: `P4-RUNTIME-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L476`, `TREEIFY_MIGRATION_REPORT.md#L484`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L126`

## Acceptance Checks

- build/test/manual QA checks: Source provenance is preserved for replacements. Reviewers can trace which original biome feature produced a replacement.

## Handoff

- target builder: `clone-factory-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-04/build/BUILD-P4-CLONE-FACTORIES.md`