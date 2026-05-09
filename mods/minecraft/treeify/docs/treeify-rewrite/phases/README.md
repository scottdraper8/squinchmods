# Treeify Phase Artifact Layout

Each phase folder contains four wave folders:

- `planning/`
- `build/`
- `qa/`
- `phase-qa/`

## Naming Convention

Recommended file naming:

- planner artifact: `PLAN-P{phase}-{lane}.md`
- builder artifact: `BUILD-P{phase}-{lane}.md`
- builder QA artifact: `QA-P{phase}-{lane}.md`
- phase QA artifact: `PHASE-QA-P{phase}.md`

Examples:

- `phase-02/planning/PLAN-P2-DISCOVERY-A.md`
- `phase-02/build/BUILD-P2-DISCOVERY-A.md`
- `phase-02/qa/QA-P2-DISCOVERY-A.md`
- `phase-02/phase-qa/PHASE-QA-P2.md`

## Rule

Planner, builder, and builder-QA artifacts should stay lane-scoped.

Only the phase QA artifact is allowed to summarize the whole phase.
