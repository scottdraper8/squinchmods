# Phase 5 Lane Plan: P5-FEATURE-DETAIL

## Header

- phase: 5
- lane: `feature-detail`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Build the feature detail screen for editing global feature rules.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/screen/FeatureDetailScreen.java`
- forbidden paths: Legacy structure screens, worldgen apply backend.
- dependencies: Phase 1 UI Shell, Phase 2 Discovery, Phase 3 Rules.

## Deliverable

- builder task: Implement the detail view for a single vegetation feature.
- expected outputs: Controls for global enabled state, density multiplier, and height delta (where supported).
- required deletions or quarantine actions: None.

## Traceability

- plan_ids: `P5-UI-002`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L965`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L314`

## Acceptance Checks

- build/test/manual QA checks: Controls shown in UI match backend support flags (honest capability surface).

## Handoff

- target builder: `ui-detail-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-05/build/BUILD-P5-FEATURE-DETAIL.md`