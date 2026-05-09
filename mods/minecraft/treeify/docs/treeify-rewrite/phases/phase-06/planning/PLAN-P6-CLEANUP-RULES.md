# Phase 6 Lane Plan: P6-CLEANUP-RULES

## Header

- phase: 6
- lane: `cleanup-rules`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Delete obsolete structure-era DTOs and serializers.
- owned paths: Deletions in `common/src/main/java/com/squinchmods/structurify/common/config/data/` and `common/src/main/java/com/squinchmods/structurify/common/config/serialization/`.
- forbidden paths: New Treeify rules and UI.
- dependencies: Phase 3 Rules completed.

## Deliverable

- builder task: Remove all Java files related to `StructureData`, `StructureSetData`, and their serializers.
- expected outputs: Files deleted from the filesystem.
- required deletions or quarantine actions: `StructureData.java`, `StructureSetData.java`, `StructureNamespaceData.java`, etc.

## Traceability

- plan_ids: `P6-CLEANUP-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L917`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L153`

## Acceptance Checks

- build/test/manual QA checks: `rg -n "StructureData|StructureSetData" common` shows no hits in production code.

## Handoff

- target builder: `cleanup-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-06/build/BUILD-P6-CLEANUP-RULES.md`