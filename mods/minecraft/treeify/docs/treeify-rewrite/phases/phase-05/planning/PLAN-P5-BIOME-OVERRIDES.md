# Phase 5 Lane Plan: P5-BIOME-OVERRIDES

## Header

- phase: 5
- lane: `biome-overrides`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Build biome-specific override screens.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/screen/BiomeOverrideScreen.java`
- forbidden paths: Legacy structure screens, worldgen apply backend.
- dependencies: Phase 1 UI Shell, Phase 1 Biome Picker, Phase 3 Rules.

## Deliverable

- builder task: Implement screens for managing per-biome rules.
- expected outputs: UI for adding/removing features from a biome and overriding density/height.
- required deletions or quarantine actions: None.

## Traceability

- plan_ids: `P5-UI-003`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L966`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L315`

## Acceptance Checks

- build/test/manual QA checks: User can navigate from a feature or global view to biome-specific overrides.

## Handoff

- target builder: `ui-overrides-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-05/build/BUILD-P5-BIOME-OVERRIDES.md`