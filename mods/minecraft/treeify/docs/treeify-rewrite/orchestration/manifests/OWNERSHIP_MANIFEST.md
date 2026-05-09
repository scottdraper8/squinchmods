# Treeify Ownership Manifest

This manifest assigns exclusive write scopes by phase and lane.

## Required Fields

| phase | lane | role | owner | owned_paths | forbidden_paths | upstream_plan_artifact | qa_artifact |
|---|---|---|---|---|---|---|---|
| 1 | `ui-shell` | planner | Helmholtz | `docs/treeify-rewrite/phases/phase-01/planning/PLAN-P1-UI-SHELL.md` | production source paths | n/a | n/a |
| 1 | `ui-state-controls` | planner | Russell | `docs/treeify-rewrite/phases/phase-01/planning/PLAN-P1-UI-STATE-CONTROLS.md` | production source paths | n/a | n/a |
| 1 | `ui-shell` | builder | unassigned | `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/shell/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/model/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/service/ConfigUi*.java`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/service/TreeifyConfig*.java`, `docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-SHELL.md` | `forge/**`, `fabric/**`, `neoforge/**`, legacy structure runtime paths, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/control/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/state/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/option/**` | `phases/phase-01/planning/PLAN-P1-UI-SHELL.md` | `phases/phase-01/qa/QA-P1-UI-SHELL.md` |
| 1 | `ui-state-controls` | builder | unassigned | `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/state/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/control/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/option/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/service/BiomeChoice*.java`, `docs/treeify-rewrite/phases/phase-01/build/BUILD-P1-UI-STATE-CONTROLS.md` | `forge/**`, `fabric/**`, `neoforge/**`, legacy structure runtime paths, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/shell/**`, `common/src/main/java/com/squinchmods/structurify/common/treeify/ui/model/**` | `phases/phase-01/planning/PLAN-P1-UI-STATE-CONTROLS.md` | `phases/phase-01/qa/QA-P1-UI-STATE-CONTROLS.md` |

## Rules

- Only one builder lane owns a write scope at a time.
- QA agents review but do not expand the write scope without orchestrator approval.
- Shared files must be frozen until their owning phase.
- Phase 1 builder lanes create new Treeify packages under the current `com.squinchmods.structurify.common` root. Broad package identity changes remain frozen until Phase 7.
| 2 | `discovery` | builder | catalog-agent | `common/src/main/java/com/squinchmods/structurify/common/treeify/worldgen/discovery/**` | legacy paths | `phases/phase-02/planning/PLAN-P2-DISCOVERY.md` | `phases/phase-02/qa/QA-P2-DISCOVERY.md` |
| 3 | `rules` | builder | rules-schema-agent | `common/src/main/java/com/squinchmods/structurify/common/treeify/rules/**` | legacy paths | `phases/phase-03/planning/PLAN-P3-RULES.md` | `phases/phase-03/qa/QA-P3-RULES.md` |
| 4 | `clone-factories` | builder | clone-factory-agent | `common/src/main/java/com/squinchmods/structurify/common/treeify/worldgen/clone/**` | legacy paths | `phases/phase-04/planning/PLAN-P4-CLONE-FACTORIES.md` | `phases/phase-04/qa/QA-P4-CLONE-FACTORIES.md` |
| 4 | `forge-runtime` | builder | forge-runtime-agent | `forge/src/main/java/com/squinchmods/structurify/common/treeify/forge/worldgen/**` | legacy paths | `phases/phase-04/planning/PLAN-P4-FORGE-RUNTIME.md` | `phases/phase-04/qa/QA-P4-FORGE-RUNTIME.md` |
