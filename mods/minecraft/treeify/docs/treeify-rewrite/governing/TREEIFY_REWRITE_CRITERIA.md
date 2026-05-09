# Treeify Rewrite Engineering Principles And Acceptance Criteria

Date: 2026-05-08

## Purpose

This document defines the engineering rules for the Treeify rewrite and the acceptance criteria for each migration phase.

The intent is simple:

- finish with a real Treeify codebase, not a Structurify fork with renamed labels
- delete obsolete structure-era code instead of carrying it indefinitely
- keep the rewrite honest about capability limits
- make every phase reviewable by QA and code review

This document complements `TREEIFY_MIGRATION_REPORT.md`. If they conflict, this document governs rewrite quality and exit criteria.

## Rewrite Principles

### 1. Delete Instead Of Preserve

The default action for structure-specific runtime code is deletion, not adaptation.

Rules:

- If a class exists only to support structures, structure sets, jigsaw placement, structure spread, or structure debugging, it must be removed or isolated from Treeify runtime paths.
- Replaced code must not remain behind feature flags "just in case."
- Temporary compatibility shims are allowed only if they have:
  - a narrow purpose
  - a named removal phase
  - a tracked follow-up item
- Commented-out legacy code is not an acceptable migration state.

Review checks:

- No new code depends on structure DTOs, structure checkers, or structure-specific mixins.
- `rg -n "TODO|FIXME|legacy|temporary|compat shim" common fabric forge neoforge` shows only intentional, bounded items with a removal note.
- Deleted subsystems are removed from build wiring, resources, and entrypoints, not just left unused.

### 2. No Monkeypatch Rewrite

Treeify must not be built by stacking more invasive patches onto Structurify internals.

Rules:

- No new mixin, accessor, invoker, or wrap-operation is allowed unless there is no stable API or service-layer alternative.
- New mixins may exist only at the worldgen apply edge or loader integration edge, never inside UI or rules code.
- No mixin may be used to pass UI state, config state, or identity metadata through unrelated game classes.
- Do not patch vanilla or library classes to emulate a missing architecture boundary.
- Existing structure-era mixins are presumed guilty and must be deleted unless explicitly justified for Treeify runtime.

Required justification for every surviving or new mixin:

- target class
- purpose
- why an ordinary service or registry approach is insufficient
- whether it is loader-specific
- how it is tested

Review checks:

- `rg -n "mixin|Mixin|Accessor|Invoker|WrapMethod|WrapOperation" common fabric forge neoforge` matches a reviewed allowlist.
- No UI package contains SpongePowered Mixin imports.
- No rules/config package contains SpongePowered Mixin imports.

### 3. Hard Layer Boundaries

The rewrite must separate `ui`, `rules`, and `worldgen`.

Rules:

- UI depends on view models and service interfaces only.
- Rules owns DTOs, serialization, defaults, inheritance, and support metadata.
- Worldgen owns registry discovery, classification, cloning, and biome patching.
- Worldgen must not depend on YACL classes.
- UI must not depend on Minecraft registry inspection classes except for narrow display DTOs supplied by services.
- Rules must not perform file I/O directly from screen callbacks.

Review checks:

- No screen builder calls `Structurify.getConfig()` or equivalent global config singleton.
- No screen builder dispatches `LoadConfigEvent` or writes config directly.
- No worldgen class imports YACL APIs.
- No rules class imports screen classes.

### 4. Honest Capability Surface

Treeify must expose only controls it can apply reliably.

Rules:

- Every discovered vegetation entry must carry classification and support flags.
- Unsupported capabilities must be hidden or explicitly labeled as unsupported or coarse-control only.
- Density must be presented as best-effort scaling, not as a guaranteed exact value.
- Height overrides must be restricted to categories that are actually supported.
- Opaque or mixed vegetation entries must degrade honestly instead of pretending to support species-level editing.

Review checks:

- Discovery output includes classification and support metadata.
- UI labels unsupported controls clearly.
- No config schema field implies universal species-level or height-level support that the backend cannot enforce.

### 5. One Clean Target Before Expansion

Forge 1.20.1 is the first target. Cross-loader parity is not a valid reason to keep bad abstractions.

Rules:

- Shared code must remain loader-agnostic where it is genuinely shared.
- Forge-specific apply logic is acceptable in the first stable backend.
- Fabric and NeoForge parity work must not block deletion of structure-era runtime logic.

Review checks:

- Forge 1.20.1 is the only required release-quality backend before parity claims are made.
- Shared modules do not contain Forge-only concepts unless behind explicit interfaces.

### 6. Traceability Over Cleverness

Every replacement feature or clone must be traceable to a discovered source.

Rules:

- Cloned placed/configured features must record source identity or provenance metadata in the model or service layer.
- Reviewers must be able to answer which original biome feature produced a replacement.
- Cache invalidation must be explicit when rules change.

Review checks:

- Clone factories document source-to-clone relationships.
- Runtime update code shows clear invalidation points.

### 7. Code Health Is Part Of The Rewrite

The rewrite is not done when behavior works but the architecture is still contaminated.

Rules:

- New Treeify code must use Treeify naming, package boundaries, and terminology.
- New code must not introduce additional static mutable UI state.
- New code must not introduce direct screen-to-file-save coupling.
- New code must not keep structure terminology in neutral interfaces.
- Public types should encode purpose clearly; generic names like `Manager`, `Helper`, or `Util` require concrete justification.
- Orphaned assets, metadata, and mixin configs from Structurify must be removed by the rename/repackage phase.

Review checks:

- New packages and type names follow Treeify vocabulary.
- Static mutable fields are limited to explicit lifecycle singletons with justification.
- `rg -n "Structurify|structure set|structure spread|jigsaw" common fabric forge neoforge` shrinks phase by phase and reaches only intentional historical references by the final phase.

## Deletion Policy

The rewrite will be judged by what it removes as much as by what it adds.

### Must Delete

- structure-specific DTOs once vegetation DTOs replace them
- structure serializers once vegetation serializers replace them
- structure generation mixins not required by Treeify
- structure spread logic
- structure check/debug systems
- UI code that binds directly to global config state
- dead Structurify resources, metadata, and naming after repackage

### May Survive Temporarily

- generic YACL helper code extracted from Structurify
- generic registry/bootstrap code that still serves Treeify
- loader entrypoints that still bridge into the old naming during a bounded transition phase

### Forbidden End State

- two active backends for the same concern
- new Treeify screens backed by old Structurify DTOs
- "temporary" legacy folders with no removal date
- structure runtime code still shipping because nobody deleted it

QA/review pass:

- Confirm each replaced subsystem has an explicit delete-or-keep decision.
- Confirm "keep" decisions are tied to Treeify runtime value, not migration convenience.

## Anti-Monkeypatch Rules

These are hard constraints, not suggestions.

### Allowed

- loader entrypoint glue
- biome/worldgen patch hooks with written justification
- YACL behavior patches that remain generic and are required for UI framework behavior

### Disallowed

- patching screens or widgets to fetch global config implicitly
- patching runtime classes to store Treeify config/session state
- patching structure classes just to reuse old Structurify behavior
- adding new accessor chains to avoid writing a real service boundary

### Mixin Acceptance Bar

A mixin survives review only if all of the following are true:

- its target and purpose are documented
- it is the narrowest practical hook
- a service/interface alternative was considered and rejected with reason
- it has a direct test or a manual verification recipe
- it is in a loader or worldgen patch package, not in domain-neutral code

## Code Health Requirements

The following are required for any phase marked done.

### Architecture

- One direction of dependency: `ui -> rules interfaces`, `worldgen -> rules`, never `rules -> ui`.
- Service interfaces are small and named by responsibility.
- No new circular package dependencies.

### Naming

- New code uses `Treeify` or neutral names, not `Structurify`.
- Domain names reflect vegetation, biome features, placement modifiers, and support tiers.
- Historical names may remain only in untouched legacy code scheduled for deletion.

### State Management

- No new static mutable screen state.
- Screen state is session-scoped.
- Save/apply flows are explicit services, not hidden side effects.

### Tests And Verification

- Every new phase introduces at least one executable verification path or a written manual QA recipe.
- Reviewers can verify feature discovery, config load/save, and apply behavior independently.
- If automated coverage is not practical for a phase, the PR must include a reproducible manual verification checklist.

### Cleanup

- No commented-out legacy blocks.
- No duplicate implementations left active.
- No obsolete resources or metadata left referenced by build files.

## Migration Checkpoints And Phase Gates

Each phase has a specific meaning of done. "Compiles" is not enough.

### Phase 1: Extract UI Framework

Objective:

- isolate reusable UI infrastructure from Structurify domain behavior

Done means:

- generic screen shell, state management, and reusable YACL helpers live in neutral packages
- structure-specific screen composers are no longer the only consumers of the framework
- UI entrypoints use injected services instead of direct config singleton access
- direct `LoadConfigEvent` dispatch from UI construction is removed
- direct `config::save` callbacks from screen builders are removed
- static mutable UI screen instances are removed or replaced with session-scoped state

QA/review criteria:

- `rg -n "Structurify.getConfig\\(|config::save|LoadConfigEvent" common/src/main/java/**/config/client common/src/main/java/**/gui` returns no active UI-layer hits
- screen builders accept service/view-model inputs
- YACL mixins kept for the framework are generic and documented

### Phase 2: Create Vegetation Catalog

Objective:

- replace structure discovery with vegetation discovery and classification

Done means:

- a vegetation discovery provider enumerates biome vegetation candidates from loaded registries
- discovered entries include feature id, category, source biomes, generation step, and support flags
- classification distinguishes at least direct trees, selectors, huge mushrooms, patch/mixed, and opaque cases
- the discovery layer does not depend on old structure DTOs

QA/review criteria:

- reviewer can inspect a discovery output example for at least vanilla Forge 1.20.1 content
- `rg -n "StructureData|StructureSetData|WorldgenDataProvider" common/src/main/java` shows no new dependencies from vegetation discovery code to structure-era models
- classification and support flags are consumed through explicit DTOs

### Phase 3: Create Vegetation Config Schema

Objective:

- create a Treeify-native config model and persistence layer

Done means:

- vegetation DTOs replace structure-shaped config in the new path
- serializers validate defaults and preserve unsupported fields only intentionally
- global rules and biome overrides have explicit precedence rules
- config schema encodes support honestly and does not promise unavailable controls

QA/review criteria:

- sample config round-trips without losing supported fields
- invalid values are corrected or rejected predictably
- reviewer can point to explicit merge/inheritance rules for global vs biome overrides
- no new screen code depends directly on JSON field wiring

### Phase 4: Replace Runtime Hooks

Objective:

- make Treeify apply vegetation rules through a dedicated backend instead of structure hooks

Done means:

- biome patching or biome-modifier application exists for the supported Forge scope
- placed/configured feature cloning is limited to cases that need divergence
- source provenance is preserved for replacements
- cache invalidation is explicit when config or registries reload
- structure generation mixins are no longer part of Treeify runtime behavior

QA/review criteria:

- reviewer can trace how a disabled feature is removed from a biome
- reviewer can trace how a per-biome density override creates or reuses a replacement
- `rg -n "ChunkGeneratorMixin|StructureManagerMixin|StructureSetMixin|JigsawStructureMixin|RandomSpreadStructurePlacementMixin" common forge neoforge fabric` shows either deletion or documented non-Treeify legacy status
- surviving runtime hooks have written justification

### Phase 5: Build Treeify Screens

Objective:

- ship a Treeify-native UI on top of the new services

Done means:

- screens exist for global controls, feature list, feature detail, and biome overrides
- controls shown in UI match backend support flags
- unsupported height/species controls are not presented as universally available
- applying changes calls a save/apply service, not hidden singleton mutations

QA/review criteria:

- reviewer can navigate from a feature entry to biome-specific overrides without touching legacy structure screens
- UI labels or disables unsupported controls accurately
- no active Treeify screen imports structure-specific screen classes

### Phase 6: Rename And Repackage

Objective:

- finish as Treeify, not as a renamed folder containing Structurify internals

Done means:

- mod id, package namespace, metadata, assets namespace, and mixin config names are renamed for Treeify
- shipped resources do not advertise Structurify except where historical attribution is intentionally preserved
- internal references to Structurify remain only in migration notes, changelog history, or explicitly retained third-party attribution

QA/review criteria:

- `rg -n "structurify" .` matches only approved historical references, migration docs, or third-party provenance
- build metadata files use Treeify identity consistently
- mixin config names, service registration files, and asset namespaces match the new mod identity

## Global Definition Of Done

The rewrite is done only when all of the following are true:

- Treeify has a Treeify-native config schema
- Treeify has a Treeify-native vegetation discovery and apply backend
- the UI framework is separated from domain/runtime side effects
- the supported Forge 1.20.1 feature set works through the new path
- legacy structure runtime code is deleted or provably disconnected from Treeify runtime
- identity, packaging, and metadata are renamed consistently
- remaining unsupported worldgen cases are labeled honestly

It is not done if any of the following remain true:

- old Structurify runtime logic still powers core Treeify behavior
- Treeify screens still mutate structure config directly
- rewrite progress depends on undocumented mixin behavior
- QA cannot determine whether a feature is unsupported or simply broken

## Review Pass Template

Use this checklist in PR review or QA signoff.

- `Deletion`: Replaced subsystems were deleted or explicitly isolated.
- `Layering`: UI, rules, and worldgen boundaries are clean.
- `Monkeypatches`: Every surviving/new mixin is justified and reviewed.
- `Config`: Schema is vegetation-native and round-trips cleanly.
- `Runtime`: Apply path uses Treeify backend, not structure backend.
- `Honesty`: UI and config expose only supported controls.
- `Identity`: Treeify naming and packaging are consistent for the current phase.
- `Verification`: Tests or manual QA recipes exist for the phase claims.

If any item fails, the phase is not done.
