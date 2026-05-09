# Phase 6 Lane Plan: P6-CLEANUP-WORLDGEN

## Header

- phase: 6
- lane: `cleanup-worldgen`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Delete obsolete structure-era mixins, checks, and worldgen logic.
- owned paths: Deletions in `common/src/main/java/com/squinchmods/structurify/common/mixin/structure/` and `common/src/main/java/com/squinchmods/structurify/common/world/level/structure/`.
- forbidden paths: Forge runtime apply backend.
- dependencies: Phase 4 Runtime completed.

## Deliverable

- builder task: Remove all structure-specific generation mixins and check systems.
- expected outputs: Files deleted.
- required deletions or quarantine actions: `common/.../mixin/structure/`, `common/.../world/level/structure/`.

## Traceability

- plan_ids: `P6-CLEANUP-003`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L202`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L155`

## Acceptance Checks

- build/test/manual QA checks: `rg -n "ChunkGeneratorMixin|StructureManagerMixin" common` shows deletion or isolation.

## Handoff

- target builder: `cleanup-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-06/build/BUILD-P6-CLEANUP-WORLDGEN.md`