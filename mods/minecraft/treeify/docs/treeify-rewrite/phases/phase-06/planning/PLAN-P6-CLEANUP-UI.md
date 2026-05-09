# Phase 6 Lane Plan: P6-CLEANUP-UI

## Header

- phase: 6
- lane: `cleanup-ui`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Delete obsolete structure-era screens and composers.
- owned paths: Deletions in `common/src/main/java/com/squinchmods/structurify/common/config/client/gui/`.
- forbidden paths: New Treeify screens.
- dependencies: Phase 5 Screens completed.

## Deliverable

- builder task: Remove `StructuresConfigScreen.java`, `StructureConfigScreen.java`, `StructureSetsConfigScreen.java`, `StructureSetConfigScreen.java`, and the `structure/` composer package.
- expected outputs: Files deleted.
- required deletions or quarantine actions: `common/.../config/client/gui/structure/` package.

## Traceability

- plan_ids: `P6-CLEANUP-002`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L141`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L156`

## Acceptance Checks

- build/test/manual QA checks: No active Treeify screen imports structure-specific screen classes.

## Handoff

- target builder: `cleanup-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-06/build/BUILD-P6-CLEANUP-UI.md`