# Phase 5 Lane Plan: P5-VEGETATION-LIST

## Header

- phase: 5
- lane: `vegetation-list`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Build the vegetation list screen using the Phase 1 shell and Phase 2 discovery data.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/screen/VegetationListScreen.java` (and associated composers)
- forbidden paths: Legacy structure screens, worldgen apply backend.
- dependencies: Phase 1 UI Shell, Phase 2 Discovery, Phase 3 Rules.

## Deliverable

- builder task: Implement the list view of discovered vegetation entries.
- expected outputs: A YACL category or screen that displays all discovered features with their classification and basic enable/disable toggle.
- required deletions or quarantine actions: None.

## Traceability

- plan_ids: `P5-UI-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L964`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L313`

## Acceptance Checks

- build/test/manual QA checks: User can browse discovered vegetation. Navigation to detail screens is wired via callbacks.

## Handoff

- target builder: `ui-list-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-05/build/BUILD-P5-VEGETATION-LIST.md`