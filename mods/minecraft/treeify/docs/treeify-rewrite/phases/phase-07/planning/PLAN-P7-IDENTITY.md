# Phase 7 Lane Plan: P7-IDENTITY

## Header

- phase: 7
- lane: `identity`
- planner: `Gemini`
- date: 2026-05-08

## Scope

- objective: Complete the conversion from Structurify to Treeify across all identity and packaging files.
- owned paths: `settings.gradle.kts`, `gradle.properties`, loader metadata (`mods.toml`, `fabric.mod.json`), mixin configs, and package roots.
- forbidden paths: None (solo phase).
- dependencies: All implementation phases (1-5) and cleanup (6) completed.

## Deliverable

- builder task: 
    1. Update `gradle.properties`: `mod.id=treeify`, `mod.group=com.squinchmods.treeify`.
    2. Update `settings.gradle.kts`: `rootProject.name = "treeify"`.
    3. Rename package roots from `com.squinchmods.structurify` to `com.squinchmods.treeify`.
    4. Rename mixin configs (e.g., `structurify-common.mixins.json` -> `treeify-common.mixins.json`).
    5. Update loader metadata files with new mod name, ID, and URLs.
- expected outputs: Repository identifying as Treeify.
- required deletions or quarantine actions: Old `structurify` package directories.

## Traceability

- plan_ids: `P7-IDENTITY-001`
- migration report anchors: `TREEIFY_MIGRATION_REPORT.md#L836`, `TREEIFY_MIGRATION_REPORT.md#L971`
- rewrite criteria anchors: `TREEIFY_REWRITE_CRITERIA.md#L328`

## Acceptance Checks

- build/test/manual QA checks: `rg -n "structurify" .` matches only approved historical references. Project builds and runs as Treeify.

## Handoff

- target builder: `rename-agent`
- output artifact path: `docs/treeify-rewrite/phases/phase-07/build/BUILD-P7-IDENTITY.md`