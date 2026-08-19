# FreeTerraForged NeoForge biome-preview fix handoff

Status date: 2026-08-17

This is a handoff for a fresh agent to continue the FreeTerraForged biome-preview work. The current
implementation is not finished. In particular, the NeoForge GUI preview still renders black with
Biolith in the user's No Man's Land setup. Do not treat the passing server probes below as proof
that the client preview is fixed.

## Objective

Make the FreeTerraForged (RTF) preset-editor biome preview correctly display actual registered
Minecraft biome IDs and colors for compatible NeoForge and Fabric companion-mod stacks. The result
must use the same effective prepared cell/climate authority and positional biome-source semantics as
finished runtime chunks. It must preserve TerraBlender weighted regions, Biolith replacements and
sub-biomes, Lithostitched injectors, and exact registered biome holders.

The preview must not merely stop crashing or fall back to composed registrations. A compatible
modded stack must visibly participate in biome selection. An incompatible optional integration may
be disabled only with a clear diagnostic warning and without making the whole preview black.

## Repository and branch

- Parent repository: /var/home/scott/Repos/squinchmods
- FTF submodule: games/minecraft/mods/FreeTerraForged
- FTF branch: hotfix/biome-previewer-bugs
- Current base: origin/1.21.1 at 908595b
- Active preview-fix branch: hotfix/biome-previewer-bugs (PR #186)
- Do not modify, reset, or rewrite other FTF branches.
- Do not reset, discard, stash, or overwrite unrelated dirty parent changes.
- Always inspect both repository statuses before editing.
- Use apply_patch for source/document edits.

The parent and FTF worktrees may contain unrelated and related investigation changes, probes,
catalog edits, documents, and logs. The FTF submodule contains the local preview implementation.
Preserve all of it unless a future agent has a precise reason to edit a particular file.

At handoff time the FTF status includes changes in:

- Common GUI preview classes and the preview cache.
- Preset, TileGenerator, BiomePreviewIntegrations, and BiomePreviewResolver.
- Fabric preview bootstrap/Biolith files.
- NeoForge build metadata, bootstrap, optional compat, mixins, and Biolith accessors.
- New PreviewTileClimateSampler and its common test.

The parent status also includes repository-owned probes/scenarios, third-party catalog changes,
agent documents, and unrelated investigation work. Do not use a broad cleanup command.

## Mandatory operating rules

Do not use the user's Modrinth instance. Do not copy mods from a Modrinth profile and do not run an
instance from it. All third-party acquisition and runtime execution must use the repository tools:

```text
tooling/squinch third-party validate
tooling/squinch third-party acquire ...
tooling/squinch third-party source ...
tooling/squinch mc-investigate ...
```

Use repository-owned catalog entries and scenarios. Pin exact version IDs, filenames, SHA-256
hashes, and dependencies in the catalog when a test stack needs a new artifact. Pinned catalog
entries are reproducibility inputs; they must not become production version allowlists or hardcoded
mod compatibility branches.

Read these before changing the design:

```text
.agent-docs/games/minecraft/agentic-development-guide.md
.agent-docs/games/minecraft/agentic-development-findings.md
.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md
.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/terrain-shaping-and-regions.md
.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/cell-tile-and-lookup-pipeline.md
.agent-docs/games/minecraft/mods/FreeTerraForged/plans/biome-fixing-plan.md
.agent-docs/games/minecraft/mods/FreeTerraForged/plans/biome-preview-pr180-investigation.md
```

The development guide's authority ladder matters: a server probe or standalone RTF tile is not
client visual confirmation. A finished chunk palette is stronger evidence than a generation-hook
observation, and neither replaces looking at the actual preset-editor screen.

## PR #180 history that must be understood

All six PR commits and their messages were read:

- 3b4d0a4 — windswept biome reachability/climate coherence.
- 1455807 — replace the deleted BiomeType preview with actual registered surface biome rendering.
- cf6d753 — merge commit.
- ab52859 — pre-server selector/fallback handling.
- 578a6d5 — initialize Lithostitched biome preview injectors; this changed both shared Preview2D and
  Preview3D from buildPatch() to buildFullPatch().
- 6679f29 — asynchronous preview computation, caching, leases, cancellation, and rasterization
  optimizations.

The important historical mistake is in 578a6d5: Preview2D and Preview3D render all RenderMode
values, not only RenderMode.BIOME. Changing the provider in those shared classes made a
Lithostitched biome requirement affect every terrain diagnostic mode. The latest local patch gates
the full-provider/optional-filter path on RenderMode.BIOME, makes mode transitions regenerate, and
adds the mode to the tile cache key. This was necessary, but the client preview is still broken in
the user's Biolith + No Man's Land stack and the complete GUI pipeline remains unverified.

The earlier asynchronous/caching optimizations should not be casually removed. They are part of the
intended architecture, but their ownership and failure behavior must be audited. Do not solve the
current failure by disabling all parallelism, restoring the old deleted BiomeType model, or making
every mode use the expensive/full biome path.

## Established findings

### 1. Full-provider lazy-holder race

RegistrySetBuilder.PatchedRegistries.full() exposes Minecraft lazy holders. In the 1.21.1 joined
Minecraft classes, RegistrySetBuilder.LazyHolder.value() effectively checks the supplier, reads it
again, invokes it, and clears it without synchronization. Two TileGenerator worker tasks can
interleave so that one observes a non-null supplier and then invokes it after another task has
cleared it. The observed failure is:

```text
Cannot invoke "java.util.function.Supplier.get()" because "this.supplier" is null
```

The stack passes through:

```text
RegistrySetBuilder$LazyHolder.value
Noises$HolderHolder
TerrainPopulator
RegionSelector / RegionLerper / Blender
Heightmap
TileGenerator.generateZoomed
```

This is a generic provider lifetime/publication/concurrency defect. It is not fundamentally a
Lithostitched-only defect. Do not fix it with fewer workers, retry loops, a caught NPE, disabling a
companion mod, or synchronization at one arbitrary call site.

The current local Preset.buildFullPatch() calls a materialize() helper that forces selected preview
registries before the provider is exposed to parallel workers. The selected set currently includes
RTF preset/noise and vanilla density-function/noise-settings registries. This is an investigation
result, not proof that the complete registry closure is correct for every compatible mod stack. A
broad experiment that walked all provider registries failed while encoding vanilla
block/configured-feature references.

The proper ownership model is one fully resolved provider per preview computation/context, built and
materialized before worker fan-out, safely published to those workers, and retired when the screen
context/revision is replaced. No raw single-use full provider should be shared across overlapping
preview requests or screens.

### 2. Preview climate-authority mismatch

The original GUI created an uncached GeneratorContext, made direct RTF CellSampler density
functions, generated a preview tile, and then resolved biome IDs afterward. Runtime chunk palettes
use NoiseChunk.cachedClimateSampler() and prepared/filtered RTF tile cells. Those are not the same
cell/sampler authority.

Repository-controlled BOP evidence:

- Uncached preview context: 121 mismatches out of 59,536 sampled quart columns.
- Controlled cached generator context: 0 mismatches out of 59,536.
- Failing artifact:
  games/minecraft/investigation-state/runs/20260817T084208Z-5d038e6642/scenario-summary.json
- Cached-context artifact:
  games/minecraft/investigation-state/runs/20260817T085211Z-d93869eb17/probe-c2cb5b8a975342d5a37a07f68145594c.jsonl

This does not authorize borrowing a live server generator context for the GUI. It proves that
preview and runtime need the same effective prepared/filtered cells and coordinate semantics.

The current local direction is to make the generated preview Tile the biome climate authority.
PreviewTileClimateSampler reads the prepared tile cell fields at the exact block coordinate, origin,
and zoom used by terrain generation; BiomePreview constructs one sampler for the tile and passes it
through the positional resolver. This is the correct direction, but it must be tested against actual
companion stacks and surface/underground boundaries. Do not hide residual mismatch with thresholds,
offsets, synthetic parameter-list lookups, namespace checks, or hardcoded biome IDs.

### 3. NeoForge preview compatibility is incomplete

Fabric has preview integration classes under:

```text
fabric/src/main/java/raccoonman/reterraforged/fabric/compat/
```

Relevant Fabric components include FabricBiomePreviewIntegrations, BiolithBiomePreviewIntegration,
BiolithPreviewContext, LithostitchedBiomePreviewIntegration, and Biolith preview mixins/accessors.

The local NeoForge work added corresponding optional bootstrap/context/mixins and a Lithostitched
adapter. This is the right conceptual boundary: common preview SPI/resolver and common
RTF/TerraBlender mechanics, with loader-specific optional providers. Do not duplicate all common
TerraBlender logic merely to make package trees symmetrical.

However, the NeoForge implementation has not demonstrated full client compatibility. It uses
structural/reflection capability checks for Biolith and compile-only NeoForge dependencies. That can
prevent a missing class from crashing an installation, but it does not prove that every actual
Biolith selection path or lifecycle read is intercepted. A warning plus a server-probe pass is not
client-preview success.

### 4. BIOME_CELLS is not BiomeType

BIOME_CELLS visualizes the continuous Cell.biomeRegionId / CellSampler.Field.BIOME_REGION diagnostic
field. It is not an authoritative Minecraft biome map and must not be reimplemented as the deleted
BiomeType system. Keep it explicitly labeled as an RTF diagnostic or remove it from the normal mode
cycle if product direction requires; do not use it as a substitute for registered biome rendering.

## Current local implementation

### Common code

The local FTF work currently includes:

- Preset.buildFullPatch() materialization of selected preview registry values before parallel
  generation.
- PreviewTileClimateSampler for tile-backed climate axes.
- BiomePreviewResolver overloads accepting an explicit Climate.Sampler, integration-session activity
  reporting, and TerraBlender selection inspection.
- BiomePreview tile-authority sampling and integration sessions around sidecar resolution.
- TileGenerator.generateZoomed(..., BooleanSupplier cancelled) with worker cancellation and tile
  cleanup on failure.
- PreviewComputationCache with bounded entries, tile leases/refcounts, sidecar deduplication,
  cancellation, and page/screen ownership.
- Mode-specific provider selection in Preview2D and Preview3D: only BIOME selects buildFullPatch()
  and optional filters; other modes select buildPatch() and preserve the old diagnostic tile path.
  The cache key carries the biome-pipeline bit so a tile cannot cross that boundary.
- BIOME_CELLS (RTF diagnostic) labeling.

The last mode-isolation build passed, but it did not constitute visual GUI confirmation.

### Fabric

Fabric bootstrap was moved so preview integration registration is available from common mod
initialization rather than only the client bootstrap. Fabric Biolith and Lithostitched adapters
remain in the Fabric compat package. Fabric BOP and mixed server-side parity probes pass, but the
future agent should still verify the actual screen after any common changes.

### NeoForge

The local NeoForge additions include:

```text
neoforge/src/main/java/raccoonman/reterraforged/neoforge/compat/
neoforge/src/main/java/raccoonman/reterraforged/neoforge/mixin/NeoForgeOptionalMixinPlugin.java
neoforge/src/main/java/raccoonman/reterraforged/neoforge/mixin/MixinBiolith*.java
neoforge/src/main/java/raccoonman/reterraforged/neoforge/mixin/Biolith*Accessor.java
```

RTFNeoForge bootstraps NeoForgeBiomePreviewIntegrations. The optional mixin plugin dynamically
checks whether Biolith is loaded and whether the required structural classes/members exist; it does
not contain a production version allowlist. The NeoForge Biolith context snapshots replacement and
sub-biome request data and redirects Biolith's replacement-noise/seedlet reads during a preview
session. The NeoForge Lithostitched adapter creates isolated preview generator state and binds
seed-dependent FastNoise configuration.

The current NeoForge build script has a compile-only Biolith dependency on 3.0.14-neoforge and a
compile-only Lithostitched dependency on 1.7.13-neoforge-21.1. This is a significant point for
critical review: the approved NeoForge runtime parity scenario uses Biolith 3.0.11, not 3.0.14. Do
not silently regard compiling against 3.0.14 while testing/running 3.0.11 as a stable API contract.
Either prove the adapter is genuinely binary/source compatible across the needed API shape, or align
the supported build/runtime pair and document the exact compatibility boundary. Do not turn this
into a production mod-version switchboard.

## Runtime evidence and limitations

All runtime artifacts below were acquired/run through repository tooling and retained under
games/minecraft/investigation-state/runs/.

Passing evidence:

- NeoForge vanilla, latest provider fix run: 20260817T102135Z-9b182e500b — 256/256, zero mismatches.
- NeoForge BOP/TerraBlender: 20260817T101244Z-c78df946ad — 59,536/59,536, zero mismatches; BOP IDs
  appeared and TerraBlender region counts were recorded. This was before only-no-op
  capability/build-target adjustments and was a server-side actual resolver-path probe, not a GUI
  screenshot.
- NeoForge Biolith 3.0.11: 20260817T104302Z-4fe8a43224 — 256/256, zero mismatches; active
  integration reterraforged:biolith-neoforge. This proves the isolated probe path for a plain
  Biolith stack, not the user's Biolith + No Man's Land GUI path.
- Fabric BOP: 20260817T103905Z-235fd68334 — 59,536/59,536, zero mismatches.
- Fabric mixed stack: 20260817T103347Z-55a3cffe22 — 400/400, zero mismatches; active Biolith
  integration.

Known failures/limitations:

- NeoForge Biolith 3.0.14: 20260817T095709Z-fb7076ee3d — Biolith's own MixinNoiseHypercube target
  fails against Climate.ParameterPoint before RTF preview initialization. The catalog marks it
  diagnostic-only. Do not “fix” this by hiding the failure in RTF.
- NeoForge Lithostitched/Regions Unexplored: 20260817T100931Z-8b25d43266 — Lithostitched's own
  common.BeardifierMixin targets a missing lambda$forStructuresInChunk$2 layout in NeoForge
  21.1.219; RTF's adapter never runs. The catalog marks NeoForge Lithostitched 1.7.13-neoforge-21.1
  diagnostic-only and RU dependent on it. This is an external runtime incompatibility until a
  matching LS/NeoForge pair is found.
- The user's current NeoForge client with Biolith through No Man's Land still shows a completely
  black preview. No repository catalog entry currently identifies the exact No Man's Land artifact
  and dependency stack. Its exact loader/version/hash must be captured and added through the
  repository acquisition workflow before drawing conclusions about that stack.
- No server-side probe can prove that the preset-editor screen successfully uploads/renderers its
  texture. The latest source was compiled and tested, but the black-screen report is client visual
  evidence that remains unresolved.

The latest locally built NeoForge jar was produced with:

```bash
cd /var/home/scott/Repos/squinchmods/games/minecraft/mods/FreeTerraForged
./gradlew :common:test :neoforge:build
```

It was copied to:

```text
/var/home/scott/Desktop/ftf-neoforge-pr180.jar
```

Latest copied jar SHA-256:

```text
d9bfd5c3f491e2f3e280f837260fc4dde99a1ddf4f1741476afdf0e103cd4888
```

The build passes with existing TerraBlender mixin-remap/deprecation warnings. Treat those warnings
as items to audit, not as proof that the mixins work at runtime.

## Critical review of the current NeoForge compatibility design

The following points should be challenged rather than assumed:

1. Plain Biolith parity is not No Man's Land parity. A 256/256 server probe only proves one
   registered placement graph. No Man's Land may exercise different Biolith request sets,
   replacement noise, seedlets, sub-biome criteria, dimension placement, or initialization timing.
   The next agent must capture the exact stack and trace the actual biome-source call from the GUI
   through the Biolith implementation used by that stack.

2. Structural reflection is a safety gate, not an integration contract. BiolithPreviewCapabilities
   checks class/member shape, but a class can expose all named fields while changing their meaning,
   initialization timing, or selection path. Capability detection must be followed by an end-to-end
   active-integration assertion. If the required Biolith behavior has no stable public API, the
   adapter must explicitly define the supported API shape and fail with a precise diagnostic when it
   is not present; do not silently fall back while reporting success.

3. The compile/runtime mismatch is suspect. NeoForge compiles against Biolith 3.0.14 while the
   approved runnable parity stack is 3.0.11. This may be harmless for the referenced API, but it is
   not established. Inspect the exact source/jar members and make the supported boundary honest.
   Version IDs may be pinned in test catalogs, but production logic must not contain arbitrary
   mod-version branches.

4. Thread-local redirection must cover the real execution scope. The current context is scoped
   around sidecar resolution, but the agent must prove that every Biolith read of replacement noise,
   seedlets, request maps, and sub-biome state occurs within that scope, on the same thread or with
   explicit context propagation. A thread-local that does not cross an executor boundary is a silent
   wrong-biome bug; a global mutable replacement state is a race. Prefer an immutable, seed-scoped
   snapshot passed through a narrowly scoped adapter, with a lock only where the external API forces
   global state.

5. Bootstrap timing must be separated from preview-session construction. Registering an adapter in
   the NeoForge mod constructor is acceptable only if it does not snapshot Biolith state there. The
   actual placement/request/noise snapshot must be built after the isolated preview registries and
   selected dimensions exist, immediately before biome resolution, and must be discarded with that
   preview revision.

6. The full-provider fix must be tested with the actual GUI worker fan-out. The current selected
   registry materialization is plausible but not proven for No Man's Land. Add a repeated parallel
   full-provider test that exercises the exact TileGenerator.generateZoomed and resolver path, then
   verify that the provider is not shared after a preset/seed/screen change. Do not solve this by
   serializing all generation.

7. The mode boundary must remain explicit. Only RenderMode.BIOME needs the full provider, biome
   integration sessions, tile climate sampler, and optional filters required for parity.
   Terrain/height/river/diagnostic modes should retain their established provider and filter path.
   Any shared cache or prepared context must include the provider/pipeline authority in its key and
   lifetime; a common class is fine, an implicit common authority is not.

8. Warnings must explain the actual state. A black texture with only a background log is not a
   usable fallback. The UI or retained diagnostic artifact should distinguish provider setup
   failure, tile generation failure, biome resolver failure, optional integration inactive, and
   successful active integration. This is observability, not a substitute for fixing the cause.

## Recommended investigation and solution sequence

### Phase A: establish the exact failure

1. Re-read the required documents and inspect both statuses. Do not reset or clean the worktrees.
2. Inspect the exact NeoForge client log corresponding to the black No Man's Land screen. Find the
   first exception, not only the final black texture. Search for the existing Failed handling 2D
   preview generation pipeline / Failed handling 3D preview generation pipeline messages and all
   causes. If the client log is unavailable, add temporary structured diagnostics to the preview
   failure boundary and retain the run; do not swallow the exception.
3. Add the exact No Man's Land NeoForge artifact and dependencies to the repository catalog using
   pinned IDs/hashes and third-party acquire. Do not manually copy a jar or use the Modrinth
   profile. Record the exact NeoForge, Biolith, No Man's Land, TerraBlender, and RTF versions.
4. Use third-party source to inspect the exact Biolith/No Man's Land source or retained source
   checkout. Identify the actual positional biome-source call and all Biolith
   placement/noise/request paths used by the failing stack.
5. Compare a plain Biolith server probe, a No Man's Land server probe, and the actual GUI resolver
   path. Record active integration IDs, selected TerraBlender region, exact holder/ID, surface Y,
   sampler authority, provider authority, and fallback/warning state for the same coordinates.

### Phase B: repair the architecture

1. Keep the mode boundary in Preview2D/Preview3D. Do not revert to buildPatch() for BIOME and do not
   use buildFullPatch() for all modes.
2. Define a clear preview-provider owner/revision object. It should own the fully resolved provider,
   prepared generator context, tile authority, and optional integration session inputs for one
   screen/seed/preset/registry revision. Build/materialize once, safely publish, and close/discard
   on revision change. Avoid static mutable state and unbounded caches.
3. Resolve the required full-provider registry closure deliberately. Materialize the registries and
   holder values actually reachable by the preview generator and companion adapters before WORLD_GEN
   fan-out. Add a test that repeatedly evaluates the full-provider path in parallel.
4. Make the generated preview tile the climate authority for all biome resolver axes that correspond
   to RTF prepared cells. Verify coordinate conversion at tile edges, negative coordinates, zoom,
   quart conversion, surface height clamping, and underground classification against runtime.
5. Replace any implicit global Biolith state read with an immutable preview-session snapshot or a
   precisely scoped context whose propagation is proven. The session must include all replacement,
   sub-biome, seed-dependent-noise, and dimension-placement information required by the actual
   Biolith path. Use registered data dynamically; never special-case No Man's Land or any namespace.
6. Make NeoForge mixins target the exact runtime members/descriptors used by the supported Biolith
   API. Validate that optional mixins are absent when the mod is absent, and that an incompatible
   shape produces an explicit inactive warning rather than a false active integration or a black
   screen. If compatibility requires an exact external version pair, encode that as catalog/test
   compatibility metadata and documentation, not arbitrary production ID checks.
7. Treat Lithostitched separately. The RTF adapter cannot repair Lithostitched's own failed
   BeardifierMixin. Find a genuinely compatible NeoForge/Lithostitched pair through the catalog, or
   report it as externally blocked. Do not add a catch, disable Lithostitched, or add a version hack
   to make the current incompatible jar appear supported.

### Phase C: prove the fix

Run focused tests and builds:

```bash
tooling/squinch third-party validate
cd games/minecraft/mods/FreeTerraForged
./gradlew :common:test :fabric:build :neoforge:build
```

Use repository-owned scenarios through tooling/squinch mc-investigate scenario. At minimum, retain
artifacts for:

- Vanilla Fabric and NeoForge.
- TerraBlender/BOP Fabric and NeoForge.
- Plain Biolith Fabric and NeoForge.
- The exact No Man's Land + Biolith NeoForge stack.
- A mixed TerraBlender/Biolith/Lithostitched stack wherever the exact runtime catalog is actually
  compatible.
- One repeated full-provider/parallel preview-resolver stress case.
- One preview-tile-climate versus finished-chunk palette comparison at identical positions and
  surface authority.

For every stack compare:

- Preview-resolved holder identity and exact namespaced biome ID.
- Finished chunk quart-biome palette.
- Selected TerraBlender region and weighted selection data.
- Biolith replacement/sub-biome activity.
- Lithostitched injector activity.
- Provider and climate-sampler authority.
- Fallback/warning state.
- Surface versus underground classification.

Inspect logs for hidden fallback warnings and first-cause exceptions. Run tooling/squinch
mc-investigate inspect-artifact on the final jar. Build/copy a new desktop jar only after the source
and runtime evidence match, and record the exact command, seed, versions, hashes, artifact paths,
and outcomes in the investigation plan.

## Things explicitly forbidden

- Hardcoded biome IDs, namespaces, coordinate corrections, or No Man's Land exceptions.
- BOP-specific, Biolith-specific, Lithostitched-specific, Regions Unexplored-specific, or Biomes
  We've Gone-specific selection hacks.
- Replacing positional biome queries with a synthetic parameter-list lookup.
- Using a live server generator context as a permanent GUI dependency.
- Reducing worker parallelism or serializing the whole preview to hide the provider race.
- Catching NullPointerException, retrying, or synchronizing one arbitrary call site.
- Disabling Biolith, TerraBlender, Lithostitched, No Man's Land, or another companion mod as the
  definition of success.
- Making BIOME_CELLS an authoritative biome map or resurrecting BiomeType.
- Production version allowlists whose only purpose is to make one jar pass.
- Running or copying from the Modrinth profile.
- Broad destructive git commands that could erase the dirty parent investigation.

## Honest current conclusion

The common design direction—mode-scoped full provider, pre-materialized provider ownership,
generated-tile climate authority, common preview SPI, and loader-specific optional adapters—is
reasonable. The current NeoForge implementation is not yet trustworthy for the user's actual
Biolith + No Man's Land client stack. The plain Biolith server probe passing is useful evidence but
does not resolve the black GUI. The next agent should begin with the exact client failure and the
actual No Man's Land artifact/runtime matrix, then critically rework the NeoForge Biolith session
and mixin/lifecycle boundary rather than adding another compatibility exception.
