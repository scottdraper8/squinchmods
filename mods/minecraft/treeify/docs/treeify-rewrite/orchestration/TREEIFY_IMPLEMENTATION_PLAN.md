# Treeify Technical Implementation And Orchestration Plan

Date: 2026-05-08

## Purpose

This document is the execution contract for the Treeify overhaul.

It turns the migration analysis in `TREEIFY_MIGRATION_REPORT.md` and the engineering rules in `TREEIFY_REWRITE_CRITERIA.md` into a practical phased plan with:

- implementation phases
- agent orchestration
- non-conflicting ownership
- QA and review loops
- merge gates
- deletion checkpoints

This is explicitly a total overhaul.

The target end state is:

- a clean Treeify mod
- a UI that feels familiar and intuitive in the same way Structurify does
- a codebase that only keeps what is genuinely useful
- no dead code
- no monkeypatched architecture
- no fake portability layers
- no structure-era backend hidden under renamed labels

If this plan conflicts with convenience, convenience loses.

## Governing Documents

The rewrite is controlled by three documents:

1. `TREEIFY_MIGRATION_REPORT.md`
2. `TREEIFY_REWRITE_CRITERIA.md`
3. `TREEIFY_IMPLEMENTATION_PLAN.md`

They have different jobs:

- the migration report is architecture law
- the rewrite criteria is quality law
- this implementation plan is execution law

If any phase result conflicts with either the migration report or the rewrite criteria, the phase is not done.

## Canonical Document Tree

All rewrite control artifacts live under:

- `docs/treeify-rewrite/`

Canonical locations:

- migration report: `docs/treeify-rewrite/governing/TREEIFY_MIGRATION_REPORT.md`
- rewrite criteria: `docs/treeify-rewrite/governing/TREEIFY_REWRITE_CRITERIA.md`
- implementation plan: `docs/treeify-rewrite/orchestration/TREEIFY_IMPLEMENTATION_PLAN.md`
- traceability matrix: `docs/treeify-rewrite/orchestration/TRACEABILITY_MATRIX.md`
- ownership manifest: `docs/treeify-rewrite/orchestration/manifests/OWNERSHIP_MANIFEST.md`
- launch log: `docs/treeify-rewrite/orchestration/logs/AGENT_LAUNCH_LOG.csv`
- phase artifacts: `docs/treeify-rewrite/phases/phase-XX/`
- final whole-project QA passes: `docs/treeify-rewrite/overall-qa/`

This folder tree is part of the orchestration contract.

Agents should write planning, build, and QA artifacts into the phase folders rather than scattering notes at repo root.

## Phase Artifact Structure

Each phase directory uses the same subfolders:

- `planning/`
- `build/`
- `qa/`
- `phase-qa/`

Meaning:

- `planning/`: one planning document per builder slot
- `build/`: builder summaries, implementation notes, and phase-local execution artifacts
- `qa/`: one QA result per builder slot
- `phase-qa/`: one phase-wide review after the planner, builder, and per-builder QA waves finish

Example:

- `docs/treeify-rewrite/phases/phase-03/planning/`
- `docs/treeify-rewrite/phases/phase-03/build/`
- `docs/treeify-rewrite/phases/phase-03/qa/`
- `docs/treeify-rewrite/phases/phase-03/phase-qa/`

After all phases are complete, whole-project QA outputs go under:

- `docs/treeify-rewrite/overall-qa/pass-1/`
- `docs/treeify-rewrite/overall-qa/pass-2/`

## Rewrite Position

The rewrite is not:

- a gentle port
- a compatibility shell around the old structure backend
- a partial rename of Structurify

The rewrite is:

- extraction of useful UI patterns
- construction of a new rules layer
- construction of a new vegetation worldgen backend
- gradual deletion of structure-only systems
- late rename/repackage once the architecture is stable

## Core Architecture

The target architecture remains:

- `ui`
- `rules`
- `worldgen`

### UI

Owns:

- YACL screen framework
- screen state/session state
- detail editors
- view models
- save/apply/reload UX

Must not own:

- config file I/O
- registry discovery
- worldgen patch logic
- direct config singleton access

### Rules

Owns:

- DTOs
- JSON schema
- inheritance rules
- global defaults
- per-biome overrides
- classification/support metadata

Must not own:

- YACL types
- worldgen mutation
- screen behavior

### Worldgen

Owns:

- vegetation discovery
- feature classification
- biome patching
- placed/configured feature cloning
- Forge apply path

Must not own:

- screen layout
- UI state
- generic rules serialization concerns

## Execution Principles

### 1. Delete First, Preserve Second

If a subsystem exists only because Structurify is a structure mod, it is presumed delete-only unless proven useful to Treeify.

### 2. One Writer Per Owned Path

Every phase has explicit path ownership.

Only the assigned implementation agent writes those files.

QA agents may patch only:

- tests
- review fixes inside the same owned area
- or a dedicated follow-up branch authorized by the orchestrator

In the wave model, this applies per builder slot, not just per phase.

Each planner-builder-QA lane owns one bounded slice.

### 3. Freeze Shared Interfaces Before Parallel Work

Parallel implementation is allowed only after the orchestrator freezes the interface contract those agents depend on.

### 4. No Repo-Wide Rename Until Late

The repo still internally identifies as Structurify.

Renaming too early would create unnecessary churn, merge conflicts, and false progress.

Broad rename work belongs in the final dedicated identity phase.

### 5. No Hidden Legacy Dependencies

New Treeify code must not silently depend on:

- `StructureData`
- `StructureSetData`
- structure-only mixins
- structure check systems
- direct `Structurify.getConfig()`

## Coordination Model

## Wave Model

Every implementation phase runs in ordered waves.

If a phase has `x` builder lanes, it also has:

- `x` planner agents first
- `x` builder agents second
- `x` per-builder QA agents third
- `1` phase QA agent fourth

After all phases complete:

- `1` overall QA pass agent
- `1` second overall QA pass agent

### Wave Order

For each phase:

1. Planning wave
2. Builder wave
3. Per-builder QA wave
4. Phase QA wave

For the whole project:

5. Overall QA pass 1
6. Overall QA pass 2

### Planner To Builder Contract

Each builder lane must have exactly one upstream planning document.

The planner defines:

- the exact scoped task
- the files or paths the builder owns
- dependencies and forbidden touches
- acceptance checks
- required deletions or quarantine actions
- migration-report anchors
- rewrite-criteria anchors

The builder executes against that planning document.

The per-builder QA agent then compares the built result directly against:

- the builder's planning document
- the migration report
- the rewrite criteria

### Phase QA Role

The phase QA agent does not review one builder lane in isolation.

It reviews the phase as a system and compares the combined phase result against:

- this implementation plan
- the migration report
- the rewrite criteria
- the set of planner documents created for that phase

### Whole-Project QA Role

After Phase 8:

- overall QA pass 1 checks whole-project consistency
- overall QA pass 2 rechecks after fixes from pass 1 and acts as a clean final audit

The second pass is not optional. It exists to catch issues introduced while fixing the first pass.

## Roles

### Lead Orchestrator

One lead orchestrator owns:

- sequencing
- path ownership
- interface freezes
- traceability
- merge decisions
- cross-phase consistency

The lead orchestrator is the only agent allowed to decide a phase is complete.

### Planning Agents

Every builder lane gets a dedicated planning agent first.

Planning agents own:

- lane-level task decomposition
- owned-path declaration
- acceptance checks
- deletion obligations
- lane-level traceability

Planning agents do not write production source code.

### Builder Agents

Each builder agent owns one bounded workstream and one write scope.

Builder agents do not merge directly and do not self-approve.

### Per-Builder QA Agents

Each builder lane gets a QA agent who did not author that lane.

Per-builder QA owns:

- comparison against the lane planning document
- lane-level migration-report comparison
- lane-level rewrite-criteria comparison
- lane-level inconsistency detection
- lane-level fix recommendations

### Phase QA Agents

Each phase gets one phase QA agent after all lane QA work is complete.

Phase QA owns:

- phase-plan comparison
- migration-report comparison
- rewrite-criteria comparison
- cross-lane consistency checks
- phase merge recommendation

### Overall QA Agents

There are two final overall QA passes.

Overall QA owns:

- whole-project consistency review
- cross-phase consistency review
- identity and cleanup review
- final merge recommendation for the rewrite as a whole

### Drift QA Agent

In every phase, one QA role checks for:

- legacy imports creeping into new code
- duplicate implementations
- dead-code accumulation
- unplanned growth in structure-era identifiers

## Communication Model

Subagents do not rely on peer-to-peer freeform chat as a core mechanism.

The reliable communication path is:

1. orchestrator defines interfaces and ownership
2. implementation agent writes or updates artifacts
3. orchestrator relays summaries or changed contracts to downstream agents
4. QA agent compares outputs against the governing documents

Practical communication artifacts:

- this implementation plan
- migration report
- rewrite criteria
- traceability matrix
- ownership manifest
- phase QA reports

If live agent-to-agent redirection is used, it should still flow through the orchestrator so the source of truth stays centralized.

## Required Control Artifacts

Before implementation starts, Phase 0 must establish:

- `TREEIFY_IMPLEMENTATION_PLAN.md`
- `TREEIFY_REWRITE_CRITERIA.md`
- `TREEIFY_MIGRATION_REPORT.md`
- traceability matrix
- ownership manifest
- legacy inventory
- launch log

### Launch Log

The launch log exists so orchestration can be visualized later.

It should record:

- phase
- wave
- lane or slot
- agent role
- task summary
- owned paths
- source artifact
- result artifact
- status

The canonical file is:

- `docs/treeify-rewrite/orchestration/logs/AGENT_LAUNCH_LOG.csv`

### Traceability Matrix

Every implementation deliverable needs:

- `plan_id`
- phase
- owner
- owned paths
- acceptance tests
- migration-report anchors
- rewrite-criteria checks
- required deletions

### Ownership Manifest

The orchestrator should maintain a simple table of exclusive write scopes.

Recommended initial ownership shape:

| Scope | Owned By |
|---|---|
| `common/.../config/client`, `common/.../mixin/yacl`, generic YACL helpers | UI framework agent |
| vegetation discovery, classifier, biome index under new `worldgen` packages | catalog agent |
| new config DTOs and serializers under new `rules` packages | rules/schema agent |
| Forge apply path, clone factories, biome patch service | Forge runtime agent |
| new Treeify screens and loader screen adapters | Treeify screen agent |
| repo-wide identity rename and packaging | rename/repackage agent |

### Legacy Inventory

The orchestrator should maintain an explicit list of structure-era systems scheduled for deletion.

Initial inventory source:

- structure DTOs
- structure serializers
- structure generation mixins
- structure checks/debug systems
- structure spread logic
- structure-only UI screens

## Initial Keep vs Delete Position

This section is the starting posture for implementation. It can be refined, but not watered down casually.

### Presumed Keep

These are useful patterns or infrastructure and may survive in adapted form:

- registry/bootstrap patterns
- datapack/resource-pack-backed registry loading patterns
- generic event primitives
- reusable YACL helpers and behavior patches
- reusable screen-shell and controller patterns
- biome/tag picker concepts

Typical source locations:

- `common/.../registry/StructurifyRegistryManagerProvider`
- `common/.../registry/StructurifyResourcePackProvider`
- `common/.../events`
- generic YACL helper and mixin paths

### Presumed Delete

These are structure-era systems and should be treated as delete-first:

- structure config DTOs
- structure serializers
- structure-only screens and composers
- structure runtime mixins
- structure spread logic
- structure check/debug systems
- structure marker APIs used only to attach structure identity/state
- structure-specific commands and debug rendering

Typical source locations:

- `common/.../config/data/Structure*`
- `common/.../config/serialization/Structure*`
- `common/.../config/client/gui/Structure*`
- `common/.../config/client/gui/structure/*`
- `common/.../mixin/structure/*`
- `common/.../mixin/compat/*` where compat exists only for structures
- `forge/.../mixin/compat/*` where compat exists only for structures
- `common/.../world/level/structure/*`
- `common/.../commands/StructurifyCommand`
- `common/.../debug/*` if it remains structure-only

### Presumed Freeze Until Final Rename

These should be touched only in the identity phase unless an earlier phase absolutely requires a narrow adapter change:

- `settings.gradle.kts`
- `gradle.properties`
- loader metadata files
- package namespace roots
- assets namespace
- mixin config filenames

## Phase Plan

## Phase 0: Planning And Control Setup

### Objective

Create the execution contract and control artifacts before code changes begin.

### Deliverables

- implementation plan
- ownership manifest
- traceability matrix
- legacy inventory
- launch log format
- phase folder usage rules
- planner, builder, and QA templates
- phase templates for QA reports

### Owned Paths

- documentation only

### Must Not Touch

- source code

### QA Role

- Traceability QA

### Exit Gate

- every planned workstream maps to migration-report sections
- every phase has clear acceptance criteria
- every future write scope has a named owner
- the document tree and logging model are in place

## Phase 1: Extract Generic UI Framework

### Objective

Split reusable UI infrastructure from Structurify domain behavior.

### Scope

- extract neutral screen shell behavior
- extract session/state handling
- extract reusable controllers/widgets
- preserve similar UX shape without binding to structure DTOs
- introduce service interfaces for UI data and apply/save behavior

### Deliverables

- neutral UI package structure
- service interfaces for catalog, save/apply, and session state
- migrated generic YACL helpers and mixins
- no direct `Structurify.getConfig()` in new UI code

### Owned Paths

- generic UI framework paths
- YACL helper/mixin paths
- session and service interface paths

### Must Not Touch

- discovery logic
- rules DTOs
- Forge runtime apply logic
- repo metadata

### Parallelism

- solo phase
- interface freeze is required before Phases 2 and 3

### Wave Count

- planner lanes: 2
- builder lanes: 2
- per-builder QA lanes: 2
- phase QA lanes: 1

### QA Roles

- UI architecture QA
- drift QA

### Exit Gate

- generic UI compiles
- new UI framework has no direct config singleton access
- new UI framework has no load/save side effects
- service contracts are frozen for downstream phases

## Phase 2: Build Vegetation Discovery And Classification

### Objective

Replace structure discovery with vegetation discovery.

### Scope

- enumerate biomes
- inspect generation-step feature lists
- discover tree and mushroom candidates
- classify support tiers
- index source biomes and feature provenance

### Deliverables

- vegetation catalog service
- feature classifier
- biome vegetation index
- support flags and classification metadata

### Owned Paths

- new `worldgen` discovery packages

### Must Not Touch

- screens
- serializers
- Forge apply hooks

### Parallelism

- may run in parallel with Phase 3 after Phase 1 interfaces freeze

### Wave Count

- planner lanes: 2
- builder lanes: 2
- per-builder QA lanes: 2
- phase QA lanes: 1

### QA Roles

- discovery QA
- architecture QA
- drift QA

### Exit Gate

- Forge 1.20.1 discovery snapshot is stable
- direct vs selector vs mixed vs opaque entries are classified
- provenance of discovered entries is recorded

## Phase 3: Build Rules Layer And Config Schema

### Objective

Replace structure config models with vegetation rules.

### Scope

- new DTOs
- JSON schema
- defaults and inheritance rules
- load/merge/save behavior
- migration-safe support metadata

### Deliverables

- `rules` DTO set
- serializers
- config load/save service
- round-trip validation coverage or explicit manual QA recipe

### Owned Paths

- new `rules` packages
- config serialization packages

### Must Not Touch

- screens
- biome patching
- loader metadata

### Parallelism

- may run in parallel with Phase 2 after Phase 1 interfaces freeze

### Wave Count

- planner lanes: 2
- builder lanes: 2
- per-builder QA lanes: 2
- phase QA lanes: 1

### QA Roles

- config/schema QA
- architecture QA
- drift QA

### Exit Gate

- config round-trips cleanly
- inheritance and defaults behave correctly
- schema does not imply unsupported capabilities

## Phase 4: Build Forge 1.20.1 Worldgen Apply Backend

### Objective

Create the real Treeify runtime backend for Forge 1.20.1.

### Scope

- biome patch service
- placed feature clone factory
- configured feature clone factory
- Forge biome-modifier-backed apply path where appropriate
- fallback runtime replacement logic where needed

### Deliverables

- global enable/disable support
- per-biome include/exclude
- density overrides
- supported height overrides
- reload/apply integration

### Owned Paths

- Forge runtime paths
- worldgen apply paths
- clone factories

### Must Not Touch

- generic UI framework
- old structure screens
- repo-wide rename

### Dependencies

- requires Phase 2 and Phase 3 merged

### QA Roles

- runtime/worldgen QA
- architecture QA
- drift QA

### Wave Count

- planner lanes: 2
- builder lanes: 2
- per-builder QA lanes: 2
- phase QA lanes: 1

### Exit Gate

- Forge 1.20.1 runtime path works for first-scope targets
- supported controls actually affect worldgen
- unsupported controls are surfaced honestly
- no new runtime dependency on structure-era backend paths

## Phase 5: Build New Treeify Screens

### Objective

Bind the new UI framework to the new rules and worldgen services.

### Scope

- vegetation list screen
- feature detail screen
- biome override screens
- save/apply flow
- loader screen adapters

### Deliverables

- working Treeify config UI
- familiar Structurify-style navigation
- view-model bindings to new services

### Owned Paths

- new Treeify screen packages
- loader UI adapters

### Must Not Touch

- legacy backend internals
- repo-wide rename

### Parallelism

- may overlap late with Phase 4 only after runtime service interfaces freeze

### Wave Count

- planner lanes: 3
- builder lanes: 3
- per-builder QA lanes: 3
- phase QA lanes: 1

### QA Roles

- UX/integration QA
- architecture QA
- drift QA

### Exit Gate

- user can browse discovered vegetation
- user can edit rules
- save/apply flow routes through new services
- no new screen is backed by structure DTOs

## Phase 6: Delete Legacy Structure Systems

### Objective

Remove superseded Structurify runtime and screen code.

### Scope

- delete structure DTOs no longer needed
- delete structure serializers no longer needed
- delete structure-only screens
- delete structure-only mixins and checks
- remove dead assets and build references

### Deliverables

- clean legacy reduction
- updated build wiring
- updated resource references

### Owned Paths

- all legacy delete targets approved by orchestrator

### Must Not Touch

- no net-new feature work

### QA Roles

- drift QA
- architecture QA

### Wave Count

- planner lanes: 3
- builder lanes: 3
- per-builder QA lanes: 3
- phase QA lanes: 1

### Exit Gate

- replaced legacy systems are removed, not merely unused
- builds and runtime no longer depend on structure-era paths

## Phase 7: Rename And Repackage

### Objective

Finish identity conversion only after the architecture is stable.

### Scope

- mod id
- package namespace
- metadata
- assets namespace
- mixin config names
- docs and branding

### Deliverables

- Treeify identity across build, metadata, code, and assets

### Owned Paths

- repo-wide identity and packaging files

### Must Not Touch

- no large feature additions

### Parallelism

- solo phase
- no other active implementation branches

### Wave Count

- planner lanes: 2
- builder lanes: 2
- per-builder QA lanes: 2
- phase QA lanes: 1

### QA Roles

- identity/packaging QA
- drift QA

### Exit Gate

- no unintended `Structurify` identity remains outside allowlisted migration docs
- build and runtime still work

## Phase 8: Final Consistency And Hardening

### Objective

Run a final whole-project review against all three governing documents and fix any residual inconsistencies.

### Scope

- consistency fixes
- dead-code cleanup
- documentation sync
- final verification recipes

### Deliverables

- final QA matrix
- final allowlist for intentional historical references, if any

### QA Roles

- whole-project QA agent
- architecture QA
- drift QA

### Wave Count

- planner lanes: 1
- builder lanes: 1
- per-builder QA lanes: 1
- phase QA lanes: 1

### Exit Gate

- implementation matches plan
- implementation matches migration report
- implementation satisfies rewrite criteria

## QA Loop Per Phase

Every phase follows the same loop:

1. Orchestrator issues scoped task with path ownership.
2. Implementation agent delivers code and a short completion summary.
3. QA agent compares the result against:
   - phase acceptance criteria
   - migration-report anchors
   - rewrite-criteria rules
4. QA agent marks each item:
   - `done`
   - `partial`
   - `missing`
5. If partial or missing items exist:
   - QA may patch within the approved scope, or
   - orchestrator sends the findings back to the implementation agent
6. Phase closes only when the QA matrix is fully green.

In the wave model, steps 2 through 6 happen once per builder lane first, then once again at phase scope.

## PR And Review Contract

Every implementation PR or patchset should include:

- `Plan IDs completed`
- `Migration report anchors satisfied`
- `Rewrite criteria checks satisfied`
- `Files intentionally left legacy`
- `Required follow-up deletions`
- `Manual QA performed`

Every QA report should include:

- acceptance criteria status
- migration-report consistency status
- rewrite-criteria consistency status
- drift findings
- merge recommendation

## Merge Gates

A phase cannot merge unless all of the following are true:

1. The owned path rule was respected.
2. The acceptance tests or QA recipe were executed.
3. The QA matrix is green.
4. Legacy impact is accounted for.
5. No unapproved cross-scope changes occurred.
6. All builder-lane planner documents exist for that phase.
7. All builder-lane QA reports exist for that phase.
8. The phase QA report exists and is green.

## Build And Verification Gates

Minimum verification per relevant phase:

- `./gradlew build`

Forge runtime phases should also include:

- Forge 1.20.1 smoke verification
- config screen open/save/apply check
- worldgen sanity check for at least:
  - global disable
  - per-biome include/exclude
  - density override
  - supported height override

If automation is incomplete, the phase must still ship with a reproducible manual verification recipe.

## Conflict Avoidance Rules

To keep subagents from colliding:

1. No shared-file edits outside owned scope.
2. Freeze `settings.gradle.kts`, `gradle.properties`, loader metadata, and mixin config filenames until the identity phase.
3. Prefer additive new packages before destructive rewrites in early phases.
4. Use one-writer ownership for:
   - `StructurifyClient`
   - loader entrypoints
   - config root services
5. Repo-wide renames happen only when no other implementation branch is open.

## Dead-Code Control Rules

To prevent the rewrite from turning into a messy hybrid:

1. Every replacement must name the legacy subsystem it supersedes.
2. Every superseded subsystem must either be deleted in the same phase or assigned a deletion owner in the next phase.
3. Track identifier drift with searches such as:
   - `rg -n "Structurify|structurify|StructureData|StructureSet|Jigsaw" common fabric forge neoforge`
4. Growth in those results is a failure unless explicitly owned by the rename phase or a documented legacy bridge.

## Definition Of Done

Treeify is done only when all of the following are true:

- the UI resembles Structurify in usability, not in backend coupling
- the active backend is vegetation-focused, not structure-focused
- structure-era runtime systems are deleted or fully isolated from Treeify runtime
- new code obeys the `ui` / `rules` / `worldgen` split
- Forge 1.20.1 is release-quality for the defined first scope
- unsupported vegetation cases are surfaced honestly
- the repo identity is Treeify, not Structurify
- no dead legacy code remains because it was easier to keep than remove

Additionally:

- every phase folder contains the artifacts required by its wave model
- the launch log can reconstruct who did what in which phase and wave
- both overall QA passes are green

## Immediate Next Action

Phase 0 is complete once this document is accepted and the orchestrator derives two supporting artifacts from it:

- traceability matrix
- ownership manifest

After that, implementation should start with Phase 1, not with runtime hooks and not with repo-wide rename.
