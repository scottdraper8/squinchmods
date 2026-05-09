# Phase 3 Lane Plan: P3-RULES

## Header

- phase: 3
- lane: `rules`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Replace structure config models with vegetation rules. Define DTOs, JSON schema, inheritance rules, and global/biome overrides.
- owned paths: `common/src/main/java/com/squinchmods/structurify/common/treeify/rules/**`
- forbidden paths: screens, biome patching, loader metadata.
- dependencies: Phase 1 UI interfaces, Phase 2 classification metadata (rules must represent support flags correctly).

## Deliverable

- builder task: Implement vegetation DTOs, serializers, and load/merge/save logic.
- expected outputs: `rules` DTO set, serializers, config load/save service.
- required deletions or quarantine actions: None yet.

## Traceability

- plan_ids: `P3-RULES-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L363`, `TREEIFY_MIGRATION_REPORT.md#L938`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L289`

## Acceptance Checks

- build/test/manual QA checks: Sample config round-trips cleanly without losing supported fields. Explicit merge/inheritance rules.

## Handoff

- target builder: `rules-schema-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-03/build/BUILD-P3-RULES.md`