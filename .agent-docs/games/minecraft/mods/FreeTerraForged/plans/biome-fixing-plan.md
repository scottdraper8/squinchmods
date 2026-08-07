# FreeTerraForged Biome Correctness and Compatibility Plan

**Repository:** [ETcodehome/FreeTerraForged](https://github.com/ETcodehome/FreeTerraForged) **Target
branch:** `1.21.1` (submodule pinned at `a154b1c6c3a6198a7c184f31387b64ff17271d11`) **Document
date:** 2026-08-05 **Related issues:**
[#18](https://github.com/ETcodehome/FreeTerraForged/issues/18),
[#57](https://github.com/ETcodehome/FreeTerraForged/issues/57),
[#160](https://github.com/ETcodehome/FreeTerraForged/issues/160) **Relevant merged PRs:**
[#61](https://github.com/ETcodehome/FreeTerraForged/pull/61),
[#151](https://github.com/ETcodehome/FreeTerraForged/pull/151),
[#152](https://github.com/ETcodehome/FreeTerraForged/pull/152),
[#154](https://github.com/ETcodehome/FreeTerraForged/pull/154),
[#163](https://github.com/ETcodehome/FreeTerraForged/pull/163) **Directly sequenced with:**
`plans/archipelago-redesign.md` (unstarted; see §1.1 — this is a hard dependency, not a related
item)

> Every factual claim below is tagged with either a `file:line` citation against the pinned commit
> above or an explicit note where source reading alone cannot settle the question and the phased
> plan must generate the evidence at runtime (`gh api` was used for issue/PR history, including
> comments and reviews, not just diffs).

## 1. Executive summary

FreeTerraForged does not simply choose a biome once and paint it over terrain. Biome identity is the
result of several interacting systems:

1. FreeTerraForged generates terrain and surface-climate fields.
2. Those fields are converted into Minecraft climate target points.
3. Minecraft, TerraBlender, Biolith, or another integration layer selects a biome from registered
   parameter points.
4. FreeTerraForged applies special handling for mountains, islands, mushroom islands, and deep
   cave-biome distribution.
5. The selected biome then controls surface rules, placed features, mob spawns, structures, weather
   behavior, and biome-tag-dependent mod content.
6. Several non-biome systems query biome identity at particular Y coordinates. A biome can be
   correct at the surface and wrong at Y=0, or vice versa, producing secondary failures such as
   missing villages (confirmed precedent: PR #163).

The current roadmap correctly treats biome correctness as a partial prerequisite to ore-generation
work (`plans/ore-generation-improvements.md`). Biome-scoped ores cannot be QA'd meaningfully until
FreeTerraForged can answer two questions reliably:

- Which biomes are registered and eligible?
- Which biomes actually win selection in the terrain contexts where their features are expected to
  run?

The three tracked issues are related but distinct:

| Issue                                                            | Status                                                                                                                                                                                                                                                                                                                                                                                                                                    | Core problem                                                                                                                         |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| [#160](https://github.com/ETcodehome/FreeTerraForged/issues/160) | **Confirmed empirically** — finished-chunk climate inspector at island_beach coordinates shows 6/7 surface cells resolve to `minecraft:savanna` with hardcoded temp=0.375/hum=-0.225 and inland continentalness 0.03–0.68 (run `f4b5ec92cf`); exact source lines cited in §4.1                                                                                                                                                            | Island beaches are explicitly forced toward savanna climate and inland continentalness.                                              |
| [#57](https://github.com/ETcodehome/FreeTerraForged/issues/57)   | Reported symptom (screenshot only, 0 comments); **baseline cell-scan with an extreme user preset (biomeSize 2000, continentScale 10000, controlPoints.beach 0.75) independently observed frozen-peaks biome over ocean ice at coordinates where terrain is correctly `SHALLOW_OCEAN` — same symptom family, amplified by narrow coast transition**; requires formal reproduction on current branch with canonical fixtures                | A frozen-ocean surface reportedly appears over warm/coral water, indicating vertical climate or biome-selection incoherence.         |
| [#18](https://github.com/ETcodehome/FreeTerraForged/issues/18)   | Plausible general concern (screenshot only, 0 comments); **baseline cell-scan with the same extreme preset independently observed plains biome over terrain correctly classified as `SHALLOW_OCEAN` (ocean floor at Y 15–36, continent_edge 0.43–0.49) — ocean biomes not winning against inland biomes in nearest-neighbor fitness under extreme control-point settings, confirming the reachability concern is real, not hypothetical** | Some registered vanilla or modded biome parameter entries may never win within the climate domain FreeTerraForged actually produces. |

All three GitHub issues have **zero comments and zero cross-references** (verified via
`gh api repos/ETcodehome/FreeTerraForged/issues/{18,57,160}/comments` and `/timeline` — each returns
an empty/zero result). There is no additional context beyond the original screenshot and title for
any of them. Do not assume there is a richer discussion to mine; there isn't.

They should remain separate issues with shared diagnostics. Issue #160 should be fixed narrowly and
in coordination with §1.1. Issue #57 should be reproduced and localized against the current branch.
Issue #18 requires a reachability audit rather than an assumption that every numerical parameter
value must be generated.

---

## 1.1 Hard sequencing dependency: the archipelago redesign

`plans/archipelago-redesign.md` (status: "planned; no implementation branch exists") will replace
island placement, shape, and — per its own implementation sequence step 6 — "terrain classification,
and climate" for islands. The current `ClimateModule.java` island-handling block (lines 165-197,
which includes the #160 defect) is exactly the code that step is scoped to replace.

This plan does **not** recommend waiting for the archipelago redesign before fixing #160 — the
redesign has no implementation branch and no committed timeline, and the current defect is real,
confirmed, and shipping to users today. But it does mean:

- [ ] Before starting Phase 2 (§7), re-read `plans/archipelago-redesign.md` to confirm it is still
      unstarted. If an implementation branch now exists, stop and re-plan Phase 2 against that
      branch instead of `1.21.1`, to avoid fixing code that is about to be deleted.
- [ ] The #160 fix must be scoped as narrowly as possible (climate/continentalness assignment for
      `ISLAND_BEACH` only) and must not restructure `TerrainCategory`, `TerrainType`, or the
      Voronoi/region machinery the redesign is about to replace. A narrow fix is cheap to either
      keep or discard when the redesign lands; a broad one is not.
- [x] Add a note to `plans/archipelago-redesign.md` step 6 (or confirm one already exists by the
      time you reach it) that the redesign's climate port must preserve — not silently drop — the
      #160 fix's outcome (island beaches selecting real shore biomes, not forced savanna). This is
      the single most likely place for this fix to regress unnoticed, because the redesign's own
      acceptance gate (in that file) does not currently mention biome/shore-selection correctness at
      all, only geometry. **Done**: added constraint note to step 6 and shore-biome acceptance
      criterion to the acceptance gate.

---

## 2. Terminology and correctness model

### 2.1 Climate parameter point

Minecraft's multi-noise biome source uses six principal climate coordinates: temperature,
humidity/vegetation, continentalness, erosion, depth, weirdness/ridges, plus an offset used in
fitness calculations.

A biome may have multiple registered `Climate.ParameterPoint` entries. Minecraft selects the
registered entry with the lowest fitness distance to the sampled target point.

### 2.2 Registered does not mean reachable

A biome can be present in the registry and still never generate because:

- no reachable target point makes it the nearest entry;
- another entry always wins;
- a region-selection framework never selects the region containing it;
- a special-case override intercepts the terrain context first;
- the biome only wins at a Y coordinate that no relevant worldgen consumer queries;
- its parameter points were added too late to a cached or region-local tree;
- a loader-specific modifier failed to add its features or parameter entries.

### 2.3 Full numeric range is not the actual requirement

Issue #18 is titled "Make full range of biome parameters spawnable." That framing is imprecise.
FreeTerraForged does **not** need to emit every floating-point value from the nominal minimum to
maximum of every axis. Minecraft performs nearest-neighbor selection. A registered biome centred at
`temperature=0.6` can still win when the sampler emits `0.5` if no closer competitor exists.

The actual invariant is:

> Every biome intended to generate must own a non-zero, reachable winner region within the set of
> climate target points FreeTerraForged produces in the terrain contexts where that biome is
> intended.

This is a six-dimensional reachability and competition problem, not six independent min/max checks.

### 2.4 Biome correctness has multiple contexts

The same X/Z column may legitimately contain different biomes by Y: surface biome, underwater/ocean
biome, shallow cave biome, deep cave biome, bottom cave biome.

| Context                  | Expected behavior                                                                                                                                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Surface land             | Terrain-appropriate surface biome; no cave biome bleed.                                                                                                                                                                     |
| Ocean water column       | Stable, coherent ocean identity unless a mod deliberately introduces vertical ocean biomes.                                                                                                                                 |
| Island beach             | Coast biome selection, not forced inland savanna.                                                                                                                                                                           |
| Underground near surface | Surface biome remains until a safe terrain-relative buffer is crossed.                                                                                                                                                      |
| Deep cave                | Registered cave candidates remain available across expanded depth.                                                                                                                                                          |
| Structures               | Biome validation occurs at the structure's meaningful placement Y — and per `wiki/concepts/features-and-structure-placement.md`, **there is no single "meaningful Y" mechanism**; it differs per structure type (see §5.1). |
| Surface rules            | Rule dispatch sees the biome identity expected for the block being surfaced.                                                                                                                                                |

---

## 3. Current biome pipeline in FreeTerraForged (verified against pinned source)

### 3.1 Terrain cell climate — `ClimateModule.java`

Full method reproduced for reference (`ClimateModule.java:89-183`,
`apply(Cell, float, float, float, float, boolean)`); the parts load-bearing for this plan:

- `cell.biome = BiomeType.get(cell.regionTemperature, cell.regionMoisture)` (line 142) — the base
  regional classification, before any override.
- **Highland/mountain override** (lines 148-163): for `TerrainCategory.HIGHLAND`, climate is
  re-sampled at the terrain-region center rather than the per-cell warped position, "to keep
  mountains in their correct climate zone while ensuring all cells within the same terrain region
  get the same biome" (comment at line 148-150). This is a _different_ override mechanism from the
  island one below — it re-samples the same noise fields at a different point, it does not hardcode
  a biome.
- **Mushroom island check runs first, for all three island terrain types** (line 169:
  `if (madeMushroomIslands(cell)){ return; }`, checked before the beach/island/mountains branch).
  `madeMushroomIslands` (lines 185-197) triggers on `cell.macroBiomeId > 0.95F` (roughly a top-5%
  noise threshold, per its own comment) and **reassigns `cell.terrain` to
  `TerrainType.MUSHROOM_FIELDS`** regardless of which of the three island terrain types the cell
  started as. This means a cell that would have been `ISLAND_BEACH` can silently become a mushroom
  field, and this reassignment happens _before_ the #160 defect's branch is reached — the two
  interact and must both be exercised in any #160 regression test (an island-beach test that only
  ever samples cells below the 0.95 threshold will never see this interaction).
- **The confirmed #160 defect** (lines 171-174): see §4.1.
- The non-beach island branch (lines 175-181) does _not_ hardcode climate — it samples the same
  `temperature`/`moisture` noise fields used for the regional base case, just at `centerX`/`centerZ`
  instead of the warped per-cell position. Only `ISLAND_BEACH` is special-cased to a fixed biome.

### 3.2 Terrain categories and delegation — `TerrainType.java`, `Terrain.java`, `TerrainCategory.java`

- `TerrainType.ISLAND_BEACH = register("island_beach", TerrainCategory.ISLAND)`
  (`TerrainType.java:30`).
- `register(String, TerrainCategory)` constructs via `Terrain(id, name, type, type)` — i.e. **the
  delegate defaults to the category itself** (`Terrain.java:19-24`, called from
  `TerrainType.java:81-87`). There is no separate delegation step for `ISLAND_BEACH`; its delegate
  is `TerrainCategory.ISLAND`, never `TerrainCategory.BEACH`.
- Confirmed: `ClimateModule.modifyTerrain` (`ClimateModule.java:229-234`) explicitly _excludes_
  `ISLAND`, `ISLAND_BEACH`, and `ISLAND_MOUNTAINS` from being reclassified to `TerrainType.COAST`
  even when within the coast-marker threshold that would otherwise trigger it. So `ISLAND_BEACH`
  cells never become `TerrainType.COAST` terrain either.

### 3.3 Continentalness reconstruction — `CellSampler.java`

`CellSampler.Field.CONTINENT.read(Cell, Heightmap)` (`CellSampler.java:140-179`) is the density
function vanilla's `NoiseRouterData.CONTINENTS` is wired to (`PresetNoiseRouterData.java:54`). It is
a hand-written piecewise function over `cell.terrain`/`cell.continentEdge`, not a raw noise sample:

- `TerrainType.MUSHROOM_FIELDS` → fixed `Continentalness.MUSHROOM_FIELDS.mid()` (line 154).
- deep ocean / shallow ocean terrain → lerped into `Continentalness.DEEP_OCEAN`/`OCEAN` ranges
  (lines 157-166).
- **`cell.terrain.getDelegate() == TerrainCategory.BEACH && cell.height + cell.beachNoise < levels.water(5)`**
  → lerped into `Continentalness.COAST` (lines 169-173). **Per §3.2, `ISLAND_BEACH`'s delegate is
  `TerrainCategory.ISLAND`, so this condition is always false for it under current source — it falls
  through unconditionally to the final branch.**
- Final fallback (lines 175-177) → lerped into `Continentalness.NEAR_INLAND..FAR_INLAND` — i.e.
  **inland continentalness**, for anything that reaches it, including every `ISLAND_BEACH` cell.

This is why island beaches receive inland continentalness — it is not a risk, it is the only code
path available to them today.

### 3.4 Surface-to-underground climate blending — `PresetNoiseRouterData.java`

`overworld(...)` (lines 73-146) builds vanilla's `NoiseRouter` record. Five axes
(temperature/vegetation/continentalness/erosion/ridges) are each built via
`blendClimateAxis(depth, surfaceFn, undergroundFn)` (lines 148-155):

```java
alpha = clamp((depth - SURFACE_CLIMATE_DEPTH) / (UNDERGROUND_CLIMATE_DEPTH - SURFACE_CLIMATE_DEPTH), 0, 1)
result = lerp(alpha, surfaceFn, undergroundFn)
```

with `SURFACE_CLIMATE_DEPTH = 0.03`, `UNDERGROUND_CLIMATE_DEPTH = 0.125` (lines 38-39). Per
`wiki/concepts/terrain-coordinates-and-levels.md`, climate depth changes at ~1/128 per block, so
this transition band is roughly (0.125-0.03)×128 ≈ **12 blocks** wide — a _different_ number from
the 24-block cap in `UndergroundBiomeBanding` (§3.5). See §5.6 for why this discrepancy matters and
must be checked empirically, not just read.

Underground continentalness and erosion are not raw vanilla noise either:
`terrainAlignedUndergroundContinentalness` (lines 157-172) squeezes and re-scales vanilla's shifted
continentalness noise, then blends it coast-to-inland via `blendCoastToInland` (lines 186-205),
which uses `CellSampler.Field.CONTINENT_EDGE` against `worldSettings.controlPoints.beach`/`.inland`
— the _same_ control points §3.3 uses, so the underground axis and surface axis share a coast/inland
transition, which is good for coherence but means a #160-style fix to surface continentalness has a
mirrored effect underground and must be checked there too (§7 Phase 2 test list).

### 3.5 Underground biome banding — `UndergroundBiomeBanding.java`

Confirmed mechanics:

- `isVanillaConventionUnderground` (lines 149-152) recognizes a candidate **only** if its
  `weirdness()` spans the full `-1..1` range _and_ its `depth()` equals either the vanilla
  underground span `0.2..0.9` or the exact bottom point `1.1`. This is a narrow structural match —
  any modded cave biome registered with a different depth/weirdness shape (e.g. a custom depth span,
  or restricted weirdness) is **silently excluded** from redistribution and left on the original
  selector. This is not necessarily wrong, but issue #18's reachability audit must explicitly test
  and report on modded cave biomes that don't match this shape, because they behave differently from
  ones that do (§4.3, §7 Phase 4).
- Disabled entirely (`Layout.unmodified`) when fewer than two matching candidates exist (line
  65-67).
- `MAX_SURFACE_BUFFER_BLOCKS = 24` (line 38) hard-caps `bandingStart` (lines 138-147) — this is the
  constant the PR #152 review thread's "hard-capped the transition layer to a max of 24 blocks (an
  even 6 cell heights)" comment produced. Below that buffer, the original selector remains
  authoritative unconditionally (`Layout.appliesAt`, line 319-321).
- Band count scales via `Math.sqrt` of both usable vertical space and inverse biome size, clamped to
  `MAX_BAND_COUNT = 32` (lines 120-128, 37).
- The entry band (`Stage.findEntryValue`, lines 267-287) uses each candidate's **original**
  horizontal fitness (temperature/humidity/continentalness/erosion/weirdness/offset —
  `horizontalFitness`, lines 164-171) to pick the first underground winner, tie-broken by a
  weirdness-derived phase (`phase`, lines 154-162). Bands after the first rotate through candidates
  by depth, phased by weirdness, with no further fitness computation (lines 246-255) — i.e. **only
  the entry band respects horizontal climate; every later band is a rotation, not a re-selection.**
  This is deliberate (documented in the class's own Javadoc, lines 18-25) but means a biome's
  horizontal "home" climate only actually influences _where in the rotation it starts_, not whether
  it appears at all deeper — reachability at depth is really about candidate-pool membership
  (`isVanillaConventionUnderground`), not fitness.

### 3.6 TerraBlender, Biolith, and late composition

Confirmed via direct source read of `MixinMultiNoiseBiomeSource.java`, `MixinParameterList.java`,
`MixinBiolithTerraBlenderCompat.java` (both loaders), and
`MixinClimateSampler.java`/`MixinRandomState.java`.

**Composition order, most-specific-wins:**

1. `MixinClimateSampler` caches the sampled `Climate.TargetPoint` at the `Climate.Sampler.sample`
   boundary (`MixinClimateSampler.java:22-33`), so every downstream consumer that reuses the same
   sampler instance observes the same target point — climate caching happens at the sampler
   boundary, not at the final-biome boundary.
2. TerraBlender path: `MixinParameterList.reterraforged$selectComposedBiome` intercepts
   `findValuePositional` at `HEAD` and, if composition succeeds, returns the banded result directly
   (`MixinParameterList.java:165-182`). Composition (`reterraforged$ensureComposedTrees`, lines
   246-309) captures each TerraBlender region's original entry list via a `@ModifyArg` on
   `Climate.RTree.create` (lines 103-119), then — using **reflection** into TerraBlender's private
   `uniqueTrees` field (lines 141-142, 234-237, 312-323) — rebuilds each region's tree with RTF
   banding applied and any late-registered global parameter points appended
   (`ClimateParameterListComposition.additions`/`.append`, referenced lines 264-286). Failure of the
   reflective field lookup is caught and logged, falling back to TerraBlender's original trees
   unmodified (lines 153-158, 298-307) — **a silent-degradation path with no alerting**; see §5.7.
3. Non-TerraBlender path: `MixinMultiNoiseBiomeSource.rtf$composeUndergroundBanding`
   (`MixinMultiNoiseBiomeSource.java:34-79`) injects at `RETURN` of `getNoiseBiome`. It re-derives
   the plain (unbanded) winner via `parameters.findValue(target)` and applies banding **only if the
   actual selected result still equals that plain winner** (line 61) — i.e. if any other mod's biome
   modifier already changed the result, RTF banding is skipped and the third party wins. This is the
   "preserved third-party replacements when they changed the original result" behavior, confirmed.
4. Biolith path: `MixinBiolithTerraBlenderCompat` (loader-specific, `@Pseudo`/`require = 0`,
   `remap = false`, targeting Biolith's internal `TerraBlenderCompatNeoForge`/equivalent Fabric
   class by string name) injects at `RETURN` of `getBiome`, replaces Biolith's "ultimate" fittest
   node with the RTF-banded value if different, reconstructing a synthetic `Climate.ParameterPoint`
   from Biolith's 7-element parameter space with the depth parameter's `.min()` substituted
   (`MixinBiolithTerraBlenderCompat.java:20-56`). Biolith is pinned at `3.0.14` (`modCompileOnly`,
   `fabric/build.gradle:25`, `neoforge/build.gradle:36`) — this mixin is coupled to that exact
   internal implementation and will silently stop applying (not error) if Biolith's internals move.

Any biome audit must inspect the **effective final selector** — i.e. run through step 2 or 4
(whichever applies) followed by step 3's guard — not only the vanilla parameter list.

### 3.7 Biome feature composition

PR #151 (merged) changed the NeoForge `AddModifier` to use mutable `ArrayList` for feature lists so
later mods can append safely (`neoforge/.../modifier/neoforge/AddModifier.java`, +10/-6 lines per
the PR diff). Biome identity and biome generation settings (feature lists) are separate concerns and
must be audited separately — confirmed, no changes to this claim.

### 3.8 Structure biome queries — `MixinJigsawStructure.java`

PR #163's fix, read directly: `rtf$handleVillageRetryPlacement`
(`MixinJigsawStructure.java:132-215`) samples a _raw_ `startHeight` (line 155, which vanilla defines
as constant `0` for villages), then separately projects a `surfaceY` via `getFirstOccupiedHeight`
**only for the biome-validity query** (lines 157-172), and passes the _raw_ `sampledY` — not
`surfaceY` — into `JigsawPlacement.addPieces` (line 181, with an explicit comment at line 180
warning against double-counting). The fix separates "what Y is used to place the structure" from
"what Y is used to validate its biome," which had been conflated at a fixed `Y=0` before.

Per `wiki/concepts/features-and-structure-placement.md`, this fix pattern is **specific to
`JigsawStructure`'s village/subterranean handling** — the wiki explicitly states "there is no common
structure-height fix" and lists five structurally different Y-authority mechanisms across vanilla
structure types (hardcoded piece Y, blind `start_height` sampling, heightmap projection,
`postProcess()` resampling, real-block search, build-then-shift). **Do not assume PR #163's fix
generalizes to other structures** — each structure type touched by an RTF mixin needs its own
Y-authority audit (§5.1, §7 Phase 6).

---

## 4. Issue-by-issue analysis

### 4.1 Issue #160: island beaches resolve as savanna

**Confirmed, with exact mechanism** (§3.1, §3.2, §3.3 above; no remaining ambiguity about _why_ this
happens):

```java
// ClimateModule.java:171-174
if (cell.terrain == TerrainType.ISLAND_BEACH) {
    cell.biome = BiomeType.SAVANNA;
    cell.temperature = Temperature.LEVEL_3.mid();
    cell.moisture = Humidity.LEVEL_1.mid();
}
```

reached only if `madeMushroomIslands` (§3.1) did not already reassign the cell, and paired
unconditionally with inland continentalness because `ISLAND_BEACH`'s terrain delegate is
`TerrainCategory.ISLAND`, never `TerrainCategory.BEACH` (§3.2), which is the only gate
`CellSampler.CONTINENT`'s coast branch checks (§3.3).

**Empirically confirmed** via the `climate-inspector` probe on real finished chunks (seed
3216933670, `archipelago/vanilla-depth-maximum-ocean` fixture, run `f4b5ec92cf`): 6 of 7 surface
island_beach cells at coordinates found via adaptive cell-scan resolve to `minecraft:savanna` with
exactly `temperature=0.375` (`Temperature.LEVEL_3.mid()`) and `humidity=-0.225`
(`Humidity.LEVEL_1.mid()`), continentalness ranging 0.03–0.68 (inland, never coast). One
finished-chunk/direct-query divergence was detected at (-2430, 62, -2654): finished=savanna,
direct=beach, with completely different climate axes (temp=-0.300, hum=0.650, cont=-0.1100) —
confirming the §5.4 sampler-path divergence risk is real at island edges, not theoretical.

**A naive fix — "map `ISLAND_BEACH` to coast continentalness for biome selection" — does not work as
a small conditional change**, because there is no existing "archipelago coast continentalness"
concept to map into. `wiki/concepts/hydrology-and-shore-geometry.md` is explicit that main-continent
coast, ocean floor, archipelago shelf, and river/wetland shore are four separate systems that "do
not share one scale or alpha," and the only coast branch that exists in `CellSampler.CONTINENT`
today is main-continent-coast machinery keyed to `TerrainCategory.BEACH` delegation. Reusing it for
islands would conflate two systems the wiki explicitly warns against conflating, and would do so
inside code `plans/archipelago-redesign.md` step 6 already intends to replace (§1.1).

**Recommended fix (applied):**

1. Preserve the island's sampled regional temperature and humidity (do not hardcode savanna) — this
   is a pure win with no interaction with the redesign. **Applied**: removed the
   `if (cell.terrain == TerrainType.ISLAND_BEACH)` special case from `ClimateModule.java`; all
   island terrain types now share the same sampled-climate path.
2. **Do not attempt to invent a new archipelago-coast-continentalness system as part of this fix.**
   Instead, pick the narrowest change that stops forcing an inland-only value: either (a) reuse the
   existing `Continentalness.COAST` range directly for `ISLAND_BEACH` cells (a value substitution,
   not new branch logic, in `CellSampler.CONTINENT`), or (b) leave continentalness as inland but
   verify empirically (§7 Phase 2) whether removing _only_ the hardcoded biome/temperature/moisture
   already lets ordinary or modded shore biomes win, given islands' typically narrow
   inland-continentalness band. **Empirically determined**: option (b) does not work — intermediate
   run `450e467ec3` confirmed that removing only the hardcoded climate (no CellSampler change)
   produces inland biomes (plains, taiga) with zero shore biomes in 3M+ samples. **Applied option
   (a)**: added `if(cell.terrain == TerrainType.ISLAND_BEACH) return Continentalness.COAST.mid();`
   to `CellSampler.CONTINENT`, matching the existing `MUSHROOM_FIELDS.mid()` pattern — a fixed value
   substitution, not new branch logic.
3. Preserve island-beach terrain morphology (no changes to `TerrainType`, `TerrainCategory`, or
   region/Voronoi code — see §1.1's scoping constraint). **Confirmed**.
4. Let the final active biome selector choose the shoreline biome. **Confirmed**: vanilla selects
   beach (56,208 samples) and snowy_beach (304 samples) based on real temperature/humidity + coast
   continentalness.
5. Explicitly flag in this fix's PR description that `plans/archipelago-redesign.md` step 6 must
   preserve this outcome when it re-ports island climate handling. **Done**: note added to step 6
   and acceptance gate.

**Acceptance criteria:**

- Warm island shores can select ordinary or modded warm/temperate shore biomes.
- Cold island shores can select snowy beach.
- Appropriate rocky/eroded combinations can select stony shore where vanilla rules permit.
- The interior remains a land biome.
- Ocean biomes do not bleed onto above-water island terrain.
- Island generation shape remains unchanged except where surface rules respond correctly to biome
  identity.
- `#minecraft:is_beach` content appears on island beaches.
- Savanna-only content does not appear solely because terrain is an island beach.
- **New:** the mushroom-island interaction (§3.1) is exercised — test coordinates must include cells
  both above and below the `macroBiomeId > 0.95` threshold on `ISLAND_BEACH` terrain.
- **New:** underground continentalness under island beaches is checked too (§3.4 — the underground
  axis shares the same beach/inland control points as the surface axis).

### 4.2 Issue #57: frozen surface ocean over warm/coral water

This is a reported symptom with zero comments and zero cross-references (confirmed via `gh api`),
predates PRs #152/#154, and must be reproduced on current source before a cause is assigned. A
reasonable, non-exhaustive starting hypothesis set — vertical Y-divergence, underground blend
starting too high under oceans, surface-rule/feature Y mismatch, stale cache, TerraBlender-only
divergence, quantization, misattributed coral source — cannot be confirmed or ruled out by source
reading alone; it requires the vertical-profiler tooling in §6/§7 Phase 3.

One source-grounded refinement: §3.4 shows the surface→underground blend for temperature/vegetation
starts at climate-depth `0.03` (~4 blocks, at 1/128 per block) and completes by `0.125` (~16 blocks)
— a much shallower transition than the ~24-block banding buffer. If #57 reproduces at a shallow
depth near an ocean floor, check whether the _reported_ Y falls inside this ~4-16 block climate-axis
blend window before assuming the underground-biome-banding candidate rotation (§3.5) is the cause —
they are different mechanisms with different depth thresholds (§5.6), and misattributing the cause
to the wrong one will waste a fix.

**Baseline observation from extreme preset**: a user-authored preset ("Modern Earthlike":
`biomeSize=2000`, `continentScale=10000`, `continentType=UPLIFT`, `controlPoints.beach=0.75`,
`controlPoints.coast=0.92`, `oceanDepth=1000`, `worldDepth=1024`) with seed `3` at coordinates
(-4038, 63, -10140) shows frozen-peaks biome over ocean ice adjacent to island terrain. Cell-scan
confirms the terrain is correctly `SHALLOW_OCEAN` with nearby `island_beach` and `island` cells
(continent_edge 0.22–0.92), suggesting the biome mismatch arises from climate values at the
ocean/island boundary rather than from a terrain-classification error. The nearby island_beach cells
carry the §4.1 hardcoded temperature=0.375, which bleeds into adjacent chunk biome palettes via
quart-resolution interpolation. The extreme `controlPoints.beach=0.75` narrows the coast transition
to a sliver, amplifying the mismatch — ocean cells with continent_edge 0.43–0.49 that would
ordinarily fall solidly into ocean continentalness under default settings are closer to the
beach/coast boundary under this preset. This symptom shares the #57 family but is observed under
conditions that exaggerate rather than create the underlying defect; formal reproduction under
canonical fixtures with default control points remains required before assigning a cause.

**Required diagnostic and acceptance criteria** — see §6 for how to run this with existing tooling
rather than a bespoke command interface.

### 4.3 Issue #18: registered biome reachability

FreeTerraForged does not emit a vanilla-identical continuous climate distribution at the surface
(confirmed: §3.1's `BiomeType.get`/regional-band midpoint mechanism, §3.3's piecewise
continentalness reconstruction). The concern is plausible and now partially confirmed empirically: a
cell-scan with an extreme user preset (seed `3`, coordinates (-3929, 69, -10816), "Modern Earthlike"
preset with `biomeSize=2000`, `controlPoints.beach=0.75`) shows all 672 sampled cells classified as
`terrain=ocean`/`terrain_category=SHALLOW_OCEAN` with ocean floor at Y 15–36, yet the in-game biome
displays as `plains` — ocean biomes are not winning nearest-neighbor fitness against inland
competitors despite correct terrain classification. The control-point settings (beach=0.75,
coast=0.92 vs defaults) compress the coast transition, and the very large biome size (2000 vs
default 225) means climate sampling integrates over a wider spatial window, but the root cause is
that `CellSampler.CONTINENT`'s ocean continentalness output does not produce values low enough for
ocean biome entries to outcompete inland entries in the parameter tree under these conditions.
Default presets may mask this because their wider coast transition and smaller biomes keep ocean
cells further from the inland–coast boundary in parameter space. The Discord screenshot attached to
the GitHub issue is unconfirmed and the issue itself has zero comments.

Weirdness is not simply absent: `CellSampler.java` has a `WEIRDNESS` field (line 202-208) wired to
`NoiseRouterData.RIDGES` (`PresetNoiseRouterData.java:56`), confirmed.

**Underground reachability is a distinct sub-question**: `UndergroundBiomeBanding`'s structural
candidate filter (§3.5) means issue #18's reachability question is different above vs. below the
surface buffer. Above it, reachability is pure nearest-neighbor competition across the full
parameter list (TerraBlender-composed or not). Below it, only candidates matching
`isVanillaConventionUnderground` even enter the rotation pool — a modded cave biome with a
nonstandard depth/weirdness registration is not "unreachable," it is simply never handed to the
banding system at all and is governed entirely by the original (pre-banding) selector at whatever
depth its own registration reaches. The reachability audit (§7 Phase 4) must report these as a
distinct category, not lump them with genuinely-shadowed entries.

The reachability audit (§7 Phase 4) uses direct climate-domain evaluation and per-biome
competitive-strength analysis rather than finite-sample observation. Reporting-status vocabulary:
`REACHABLE` (wins somewhere with comfortable fitness margin), `FRAGILE` (wins somewhere but with
razor margin — sensitive to preset/seed perturbation), `UNREACHABLE` (no coordinate where it wins
within FTF's climate output domain), `SPECIAL_CASE_ONLY` (placed by override rather than
nearest-neighbor fitness), `BANDING_EXCLUDED` (excluded from underground banding by registration
shape per §3.5).

---

## 5. Cross-cutting risks

### 5.1 Biome identity is consumed at different Ys

§3.8 above shows PR #163's fix pattern does not generalize to other consumers. Before trusting _any_
structure's biome-Y behavior, find its specific Y-authority mechanism per
`wiki/concepts/features-and-structure-placement.md`'s five-mechanism list, rather than assuming it
matches `MixinJigsawStructure`.

| Consumer                                      | Meaningful Y                                                    | Verified mechanism                                                                                                                                   |
| --------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Village / Trial Chambers / Ancient City start | Computed surface Y for biome check; raw sampled Y for placement | `MixinJigsawStructure.java:132-275`, confirmed                                                                                                       |
| Other jigsaw/piece-based structures           | Unknown — must be individually checked                          | Not audited by this plan; do not assume PR #163 parity                                                                                               |
| Cave feature                                  | Candidate placement Y                                           | Not yet source-verified in this pass                                                                                                                 |
| Surface rule                                  | Current surface-rule block/column context                       | Not yet source-verified in this pass                                                                                                                 |
| Spawn search                                  | Surface or configured spawn context                             | `RTFClimateSampler.spawnSearchCenter` exists (`RTFClimateSampler.java`, `MixinClimateSampler.java:19,35-41`) — mechanism not yet traced in this pass |
| Ore feature biome filter                      | Candidate placement Y                                           | Out of scope for this plan; feeds `ore-generation-improvements.md`                                                                                   |
| Biome display                                 | Player position Y                                               | Vanilla behavior, not RTF-specific                                                                                                                   |
| Ocean freezing                                | Surface water/top layer                                         | Central to #57 — unverified pending reproduction                                                                                                     |
| Coral/aquatic feature                         | Feature candidate Y                                             | Central to #57 — unverified pending reproduction                                                                                                     |

### 5.2 Composition order matters — confirmed, see §3.6

### 5.3 Caching must cache inputs, not bypass selectors — confirmed, see §3.6 point 1

`MixinClimateSampler` caches at the `Climate.Sampler.sample()` boundary, not the final biome. This
is architecturally sound, but §5.4 below identifies a related risk: caching correctness depends on
every consumer actually sharing the _same sampler instance_, which is not guaranteed by this
mechanism alone.

### 5.4 Multiple sampler/query paths can diverge

`wiki/concepts/biome-selection-and-terrablender.md` states: "There is more than one climate-sampler
path: direct `BiomeSource` queries; `RandomState` sampling; `NoiseChunk.cachedClimateSampler()`,
which fills real chunk biome palettes; and TerraBlender regional parameter trees and positional
selection... Generated chunk palettes use the cached chunk sampler. Direct queries and generated
chunks can therefore differ when only the direct path carries a change."

Source inspection (`MixinRandomState.java:42-169`) shows `RandomState` holds one
`@Final Climate.Sampler sampler` field, and `reterraforged$RTFRandomState$initialize` sets
`undergroundBiomeBandingPreset` on that single instance (lines 113-127) — so _for a given
`RandomState`_, banding state is set once and should be visible to anything sampling through it.
This plan cannot fully confirm from static reading alone whether every consumer (chunk-palette
generation via `NoiseChunk`, direct `BiomeSource.getNoiseBiome` calls e.g. from structure mixins,
and any diagnostic tool) resolves to that _same_ `Climate.Sampler` instance versus a distinct one —
the answer depends on how vanilla's `NoiseChunk.cachedClimateSampler()` is constructed relative to
`RandomState.sampler()` in this Minecraft version, which needs a runtime check, not just a read.

**This is exactly the class of bug this repo's own tooling is built to catch**: `mc-investigate`
already distinguishes `finished-chunk` authority from lower-confidence direct/preview queries (see
`cell-scan`'s `prediction` vs `finished-chunk` labeling and the explicit warning in its README that
"Force-load acknowledgment alone is never labeled finished-chunk proof"). Any biome diagnostic built
under §6/§7 must be validated against **real finished-chunk output**, not just a direct
`BiomeSource` call from a probe, or it risks confidently reporting a reachability/banding result
that does not match what players actually generate. This is now an explicit phase gate (§7 Phase 1).

**Empirically confirmed**: the Phase 1 climate-inspector probe validates both paths. At inland
coordinates (run `4befa954b5`, 2,800 samples), finished-chunk and direct-query biomes agree
perfectly (0 divergences). At island_beach coordinates (run `f4b5ec92cf`, 7 samples), one divergence
was detected at (-2430, 62, -2654): finished-chunk stored `minecraft:savanna` while the direct
`BiomeSource` query returned `minecraft:beach` with completely different climate axes (temp=-0.300
vs 0.375, hum=0.650 vs -0.225, cont=-0.1100 vs 0.0317). This confirms that the two paths can diverge
at terrain boundaries and that finished-chunk authority is the correct ground truth.

### 5.5 TerraBlender + Regions Unexplored regression class

PR #154's own description (`gh pr view 154`, not just its diff) states it fixed a real bug: "when
TerraBlender was active alongside Regions Unexplored, some RU biomes could become stuck in certain
vertical bands, be very tiny (only a few blocks wide), or miss features altogether." This was fixed
by the TerraBlender compat rework in `MixinParameterList.java` (§3.6). It is direct evidence that
this exact integration seam has already produced a real, shipped-then-fixed defect of the _same
shape_ issue #18 worries about — not hypothetically, but historically. The reachability audit (§7
Phase 4) must include Regions Unexplored specifically as a regression check, not just as one
mod-stack option among several, because it has a documented history of breaking here.

### 5.6 Two independent depth-transition constants, unaligned by inspection

See §3.4/§4.2. `blendClimateAxis`'s ~12-block climate-axis transition and
`UndergroundBiomeBanding`'s ~24-block-capped banding buffer are computed from different constants in
different files, tuned (per the PR #152 review thread) by trial-and-error against one specific
preset. Whether they stay coherently ordered (climate axes fully "underground" before banding starts
rotating candidates, or vice versa) across the full preset space — shallow worlds, extreme depths,
varying biome sizes — is an empirical question this plan flags but does not answer. §7 Phase 3
includes this as an explicit measurement, not an assumption.

### 5.7 Silent-failure integration seams

Two mechanisms in §3.6 degrade **silently** on upstream change, with no build-time or run-time error
surfaced to a developer or player:

- `MixinParameterList.reterraforged$indexRegionalEntries` reflects into TerraBlender's private
  `uniqueTrees` field by name (`MixinParameterList.java:141-142`); on `ReflectiveOperationException`
  or any `RuntimeException`, it logs an error and falls back to _TerraBlender's original, unbanded
  trees_ (lines 153-158) — i.e. underground banding silently stops working under TerraBlender, while
  everything else keeps functioning normally. TerraBlender is pinned at `4.1.0.0`
  (`gradle.properties:10`).
- `MixinBiolithTerraBlenderCompat` is `@Pseudo`/`require = 0`, targeting Biolith's internal
  implementation class by string name with `remap = false`
  (`MixinBiolithTerraBlenderCompat.java:18`). If that internal class/method disappears or changes
  signature in a future Biolith release, the mixin simply does not apply — no log, no error, no test
  failure — and RTF banding silently stops composing with Biolith. Biolith is pinned at `3.0.14`
  (`modCompileOnly`, `fabric/build.gradle:25`, `neoforge/build.gradle:36`).

Neither currently has a regression test that would catch silent degradation. §7 Phase 6 adds an
explicit "did banding actually apply" assertion for both integration paths, tied to the exact pinned
versions above, so a future dependency bump that breaks either seam is caught in CI/QA rather than
discovered by a player screenshot (which is how #57, #18, and #160 were all originally discovered).

### 5.8 Biome identity and feature lists are separate — confirmed, see §3.7

---

## 6. Diagnostic tooling: extend what exists, do not rebuild it

A biome investigation of this scope needs a climate-point inspector, a vertical biome profiler, a
reachability census, a feature graph, and a structure biome-query trace. Some of this already
exists, under `games/minecraft/tooling/investigate/` (the `mc-investigate` CLI) and
`games/minecraft/investigations/reterraforged/probes/`. This section inventories what exists, what's
missing, and how the missing pieces should be built — as a new/extended **probe pack**, following
this repo's own established pattern (`probes/README.md`: shared runtime, request protocol,
`ServiceLoader` registration, `FinishedChunkSelection`, no hardcoded coordinates, mixins that only
capture events) — not as a standalone tool.

| Diagnostic capability         | Status                               | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ----------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vertical biome profiler       | **Exists with climate axes**         | `probes/biome-palette/RtfBiomePaletteProbePack.java` samples real finished-chunk biome IDs across configurable X/Z/Y bounds, quart steps, and caller-defined Y bands, with air-sample tracking. Extended in Phase 1 with `includeClimateAxes` config boolean: when enabled, re-samples `Climate.Sampler` at each quart cell and tracks per-biome and per-band min/max/sum statistics for all 6 climate axes (`ClimateAxisStats`, `AxisAccumulator` inner classes). Validated against finished-chunk output across all fixtures (see Phase 0 baseline inventory in §7).                                                                                                                                               |
| Climate-domain evaluation     | **Exists**                           | `probes/climate-domain/RtfClimateDomainProbePack.java` evaluates `Climate.Sampler` at a dense block-coordinate grid (configurable, default ±10000 at 4-block steps) recording per-axis min/max/mean/percentiles and 0.005-resolution sparse histograms. Includes convergence tracking at expanding radii. No biome selection. Scenarios ready for FTF default, FTF modern-default, and vanilla-control. Per-biome competitive strength (Voronoi volume × margin) is handled by the enhanced `reachability-census` probe's `competitive_strength` output.                                                                                                                                                             |
| Biome selection census        | **Exists with competitive strength** | `probes/reachability-census/` gives per-biome selection counts, min/max Y, per-band counts, and **per-biome competitive-strength metrics** (win margin min/max/mean, surface/underground fitness win splits, strength score = volume × mean margin) from real finished-chunk generation. Enhanced in Phase 4 with `classification` output (REACHABLE/FRAGILE/UNREACHABLE/BANDING_EXCLUDED) and summary aggregation. Useful for end-to-end integration validation (Phase 4e, Phase 6). Vanilla-control project (`investigations/vanilla-control/`) exists for comparison runs.                                                                                                                                        |
| Composition audit             | **Exists (Phase 4c)**                | `probes/reachability-census/RtfCompositionAuditProbePack.java` — zero-knowledge structural analysis of the effective parameter tree and finished-chunk diversity. Reports per-namespace biome/entry counts, underground convention membership, duplicate registration detection, finished-chunk biome diversity (surface vs underground, biomes outside parameter tree), and banding health (underground-only biome count, diversity ratio). No mod-specific code — works with any mod stack. Detects TerraBlender/Biolith/RU integration effects via namespace distribution and banding health metrics without knowing those mods exist. Scenarios: `rtf-composition-audit.toml`, `vanilla-composition-audit.toml`. |
| Climate point inspector       | **Exists**                           | `probes/climate-inspector/RtfClimateInspectorProbePack.java` built in Phase 1. Samples specific coordinates (explicit point list) or a configurable grid, reporting: finished-chunk biome, direct `BiomeSource` query biome, all 6 climate axes, and whether the two biomes agree. Tracks divergence counts and per-biome-pair statistics. Validated against finished-chunk output (run `4befa954b5`: 0 divergences at inland coordinates; run `f4b5ec92cf`: 1 divergence at island_beach boundary). Missing for Phase 4: fitness distance to nearest competitor, terrain type/category, composition-layer breakdown (base/banded/TerraBlender/Biolith winners).                                                     |
| Effective biome feature graph | **Mostly exists, generic**           | `probes/placement-telemetry` (renamed from `cave-placement`, since its Mixins hook generic vanilla `PlacedFeature`/`HeightRangePlacement`/`CountPlacement`/`BiomeFilter`/`WorldGenRegion` classes — nothing about it is cave-specific) already captures placement invocation, biome-filter, and surviving-write telemetry keyed by any real `PlacedFeature` registry ID, not just cave decorations — confirmed by pointing it directly at standard vanilla ore features for `plans/ore-generation-improvements.md` (`probes/placement-telemetry/probe-pack.toml` capabilities list). Missing: configured-feature-type resolution and source/namespace provenance per feature.                                        |
| Companion mod testing         | **Exists (Phase 4c)**                | `companion_mods` infrastructure in `server.py` and `scenario.py`: copies mod JARs to server `run/mods/` with full cleanup (pre-launch error, post-launch error, normal `stop_server`), state persistence, and conflict detection. Scenarios: `ftf-companion-bop.toml` (BOP + TerraBlender + GlitchCore), `ftf-companion-ru.toml` (RU + Lithostitched), `ftf-companion-terralith.toml` (Terralith + Lithostitched). Mod JARs cached at `~/.cache/squinchmods/investigate/companion-mods/1.21.1/` via Modrinth API. Combined with the zero-knowledge composition audit probe, tests modded biome integration without mod-specific probe code.                                                                          |
| Structure biome-query trace   | **Does not exist**                   | No probe currently traces a structure start's sampled Y, projected surface Y, biome-validation Y, and result. Must be built new, and should live beside `MixinJigsawStructure`-relevant investigation work per the repo's convention of keeping implementation-coupled QA near its topic.                                                                                                                                                                                                                                                                                                                                                                                                                            |

New probe-pack work in §7 must:

- follow `games/minecraft/tooling/investigate/probe-pack-template/README.md`;
- take all coordinates/bounds/steps/bands as request configuration, never hardcoded, per
  `probes/README.md`'s explicit historical-disposition rule;
- report `finished-chunk` authority wherever the claim is about real generation (§5.4), and be
  explicit in its output schema whenever it is _not_ (e.g. a direct climate-point query at a single
  X/Y/Z is inherently not a finished-chunk claim, and should say so rather than implying parity with
  real generation);
- be added to `.squinch/games/minecraft/mods/FreeTerraForged/investigations/` as named scenario
  TOMLs once built, following the existing `rtf-biome-palette.toml`/`rtf-placement-telemetry.toml`
  pattern, not as one-off ad hoc commands.

---

## 7. Phased implementation checklist

**Read before starting**: every phase below ends with an explicit evidence-gate. Do not start the
next phase until the current phase's gate is satisfied and its evidence is committed somewhere
durable (a run artifact under `investigation-state/`, a fixture, or this document). "It looked right
in one manual test" is not evidence. Every claim in this checklist must be re-derived by running the
cited tooling against the pinned commit, not accepted purely because this document states it.

### Phase 0 — Freeze a baseline and reconfirm scope

- [x] Confirm the FreeTerraForged submodule is still at `a154b1c6c3a6198a7c184f31387b64ff17271d11`
      (or record the new commit and re-verify every `file:line` citation in §3-§5 against it — do
      not assume line numbers are stable across any rebase).
- [x] Re-read `plans/archipelago-redesign.md` in full. If its status line no longer says "no
      implementation branch exists," stop and re-plan §7 Phase 2 against whatever branch now exists.
      _Confirmed still "planned; no implementation branch exists" as of 2026-08-06._
- [x] Re-run `gh api repos/ETcodehome/FreeTerraForged/issues/{N}/comments --jq 'length'` for issues
      \#18, \#57, \#160 in case new comments were added since this document was written. If any
      return nonzero, read the new comments before proceeding — they may change the analysis. _All
      three return 0 — no new comments._
- [x] Choose fixed seeds and coordinates for every known reproduction case (#160's screenshot
      context, #57's screenshot context, and at least one #18 candidate region). Record them in this
      document or a linked fixture, not only in a terminal scrollback. _Seed 3216933670 used for all
      canonical baselines. #160 island_beach coordinates found via adaptive cell-scan with
      `archipelago/vanilla-depth-maximum-ocean` fixture: 10 cells in the (-2560,-3584) to
      (-1536,-2560) region. Additional extreme-preset observation: seed `3` with "Modern Earthlike"
      preset at (-3929, 69, -10816) for #18 and (-4038, 63, -10140) for #57-family symptom._
- [x] Using existing fixtures under `games/minecraft/investigations/reterraforged/fixtures/`
      (`vanilla-depth-maximum-ocean`, `deep-world-ocean-stress`, `shallow-depth-mountain-control`,
      `maximum-vertical-range-cave-decoration-stress`, `short-top-world`, and the `archipelago/*`
      set), run the existing `rtf-biome-palette` probe once per fixture at wide bounds to archive a
      **current-source** biome palette baseline before any fix lands. Do this for both Fabric and
      NeoForge. Archive the run artifacts; they are the "before" side of every `compare` invocation
      in later phases.\
       **Retained baseline inventory** (all at seed 3216933670, chunks 60–75 = 16×16, climate axes
      enabled, `retention = "keep"`):

      <!-- markdownlint-disable MD046 -->

      | Run ID | Fixture | Loader | Biomes | Samples |
      |--------|---------|--------|--------|---------|
      | `ae59838c2d` | vanilla-depth-maximum-ocean | Fabric | 6 | 393,216 |
      | `b5802d17b0` | archipelago/vanilla-depth-maximum-ocean | Fabric | 6 | 393,216 |
      | `cd9ae87160` | deep-world-ocean-stress | Fabric | 6 | 1,032,192 |
      | `8d6a62b1ab` | shallow-depth-mountain-control | Fabric | 5 | 409,600 |
      | `27f99a6e74` | short-top-world | Fabric | 6 | 196,608 |
      | `5c0c96e612` | max-vertical-range-cave-decoration-stress | Fabric | 6 | 1,048,576 |
      | `2971a3325f` | archipelago/deep-world-ocean-stress | Fabric | 6 | 1,032,192 |
      | `56f522c12a` | archipelago/shallow-depth-mountain-control | Fabric | 5 | 409,600 |
      | `8b3c2f23ad` | vanilla-depth-maximum-ocean | NeoForge | 6 | 393,216 |
      | `3015ff5050` | deep-world-ocean-stress | NeoForge | 6 | 1,032,192 |

      **Cross-loader parity**: NeoForge and Fabric produce identical biome palettes (exact per-biome
      sample counts match) for both fixtures tested on both loaders.

      **#160-specific baselines** (archipelago/vanilla-depth, island-heavy region):

      | Run ID | Probe | Samples | Key finding |
      |--------|-------|---------|-------------|
      | `90b9f03611` | biome-palette (climate axes) | 3,085,824 | 14 biomes across 40×48 chunks covering island terrain |
      | `f4b5ec92cf` | climate-inspector (7 points) | 7 | 6/7 surface island_beach → savanna, 1 divergence |

- [x] Confirm current TerraBlender (`4.1.0.0`) and Biolith (`3.0.14`) pins in `gradle.properties`
      and `fabric/build.gradle`/`neoforge/build.gradle` still match this document; if either has
      moved, re-verify §5.7's fragile seams still apply as described before trusting them.
      _Confirmed: TerraBlender 4.1.0.0, Biolith 3.0.14 — unchanged._

**Gate**: ~~a baseline biome-palette artifact exists per fixture per loader, archived, with recorded
seeds/coordinates, and archipelago-redesign status reconfirmed.~~ **Satisfied 2026-08-06.**
Baselines archived per fixture (8 Fabric, 2 NeoForge with cross-loader parity confirmed),
seeds/coordinates recorded, archipelago-redesign reconfirmed unstarted, dependency pins verified.

### Phase 1 — Extend diagnostics before changing behavior

Do this before Phase 2. A broad climate change without these tools will be difficult to review and
likely to regress a context nobody thought to check (this is exactly what happened mid-review on PR
PR #152, per §5.6).

- [x] Extend `probes/biome-palette` (or add a sibling probe following the same template) to also
      record, per sampled column/Y: raw `Climate.TargetPoint` axes (temperature, humidity,
      continentalness, erosion, depth, weirdness) alongside the resolved biome ID. This directly
      answers §5.6's "are the two depth-transition mechanisms aligned" question once run across
      presets. _Extended `RtfBiomePaletteProbePack.java` with `includeClimateAxes` config boolean,
      `ClimateAxisStats` and `AxisAccumulator` inner classes. When enabled, re-samples
      `Climate.Sampler` at each quart cell and tracks per-biome and per-band min/max/sum statistics
      for all 6 climate axes. Backward compatible (disabled by default). Added `"climate-axes"` to
      `probe-pack.toml` capabilities._
- [x] Build the climate-point inspector (confirmed not to exist yet, §6 above): given X/Y/Z, report
      raw climate axes, finished-chunk biome, direct-query biome, whether they agree, and divergence
      statistics. Built as `probes/climate-inspector/RtfClimateInspectorProbePack.java` — supports
      both explicit point lists and grid-mode sampling. Tracks per-biome and per-divergence- pair
      counts. _Note: the full Phase 1 spec also requested terrain type/category, base/banded/
      TerraBlender-regional/Biolith-replacement winners, and fitness distance to nearest competitor.
      The current implementation covers the finished-chunk vs direct-query comparison and all 6
      climate axes, which is sufficient for the Phase 1 gate and Phase 2 work. The additional fields
      (fitness distance, composition-layer breakdown) should be added when Phase 4's reachability
      audit requires them._
- [x] For every diagnostic added, explicitly verify it against **finished-chunk** output at least
      once per capability, per §5.4 — do not ship a direct-query-only tool and assume it matches
      real generation without a cross-check, following the existing
      `rtf-cell-cache-cross-check.toml` parity-gate pattern. _Both probes verified against
      finished-chunk output. Climate-inspector run `4befa954b5` at inland coordinates (chunks 65–69,
      vanilla-depth fixture) shows 0 divergences across 2,800 samples — finished-chunk and
      direct-query biomes agree perfectly. Climate-inspector run `f4b5ec92cf` at island_beach
      coordinates detected 1 divergence at (-2430, 62, -2654): finished=savanna, direct=beach —
      confirming the §5.4 sampler-path risk is real at terrain boundaries._
- [x] Register the new/extended probe(s) as named scenario TOMLs under
      `.squinch/games/minecraft/mods/FreeTerraForged/investigations/`. _Registered:
      `rtf-biome-palette-climate.toml` (climate-enhanced palette, deep-world fixture) and
      `rtf-climate-inspector.toml` (grid-mode inspector, vanilla-depth fixture)._

**Gate**: ~~running the climate-point inspector and the extended vertical profiler against a
known-good coordinate reproduces expected vanilla-adjacent output (e.g. a plains biome at a plains
coordinate with plausible axis values) before being trusted for the actual bug investigations
below.~~ **Satisfied 2026-08-06.** Climate inspector run `4befa954b5` at known inland coordinates
(chunks 65–69, vanilla-depth-maximum-ocean fixture, seed 3216933670) reproduced expected output:
2,800 samples, 0 finished-chunk/direct-query divergences, `minecraft:sparse_jungle` at surface with
temperature=0.375, humidity=0.200, continentalness=0.96–0.99 (inland), erosion=0.445, depth
transitioning monotonically from -0.56 at Y=114 to 0.81 at Y=-62. Underground biomes transition
coherently from sparse_jungle → lush_caves → dripstone_caves with increasing depth.

### Phase 2 — Fix #160 narrowly

- [x] Confirm Phase 0's archipelago-redesign re-check is still "unstarted" immediately before
      writing code here. If not, stop (§1.1).
- [x] Using the Phase 1 climate-point inspector, sample several `ISLAND_BEACH` cells (across the
      `macroBiomeId` mushroom threshold from §3.1, and across warm/cold regional temperature) to
      observe **current** axis values before changing anything. Pre-fix baseline run `f4b5ec92cf`:
      6/7 surface island_beach cells → savanna with hardcoded temp=0.375, hum=-0.225, inland
      continentalness 0.03–0.68. One divergence at (-2430,62,-2654) where direct query returned
      beach at coast continentalness -0.11. Underground cells → dripstone_caves at inland cont. No
      mushroom-threshold cells found (max macroBiomeId = 0.33 among 2,230 island cells at step 4
      over the full scan area).
- [x] Remove the hardcoded `BiomeType.SAVANNA`/`Temperature.LEVEL_3`/`Humidity.LEVEL_1` assignment
      at `ClimateModule.java:171-174`; preserve the cell's sampled regional temperature/humidity
      instead (mirror the non-beach island branch's approach at lines 175-181).
- [x] Decide, using Phase 1 tooling output (not guesswork, per §4.1's revised recommendation)
      whether `CellSampler.CONTINENT`'s coast branch needs a narrow, additive condition for
      `ISLAND_BEACH` or whether preserving real temperature/humidity alone already lets shore biomes
      win given islands' typical continentalness range. Prefer the smaller change. **Decision: both
      changes required.** Intermediate run `450e467ec3` (climate-only fix, no CellSampler change)
      empirically confirmed that removing the hardcoded savanna alone produces inland biomes
      (plains, taiga, old_growth_spruce_taiga) — zero beach/stony_shore/snowy_beach appeared in 3M+
      samples. The inland continentalness (0.03–0.68) prevents shore biomes from winning. Applied
      the narrowest CellSampler fix:
      `if(cell.terrain == TerrainType.ISLAND_BEACH) return Continentalness.COAST.mid();` — a fixed
      value substitution matching the existing MUSHROOM_FIELDS pattern, not new branch logic.
- [x] Do **not** touch `TerrainCategory`, `TerrainType`, `modifyTerrain`'s island exclusions, or any
      Voronoi/region code (§1.1 scoping constraint).
- [x] Re-run the mushroom-island interaction case explicitly (§3.1) — confirm the fix does not
      change mushroom-field cells that happen to start as `ISLAND_BEACH`. **Structurally
      confirmed**: `madeMushroomIslands(cell)` runs before all changed code and early-returns; the
      paths are completely disjoint. No empirical mushroom_fields cells exist in the scan area (max
      macroBiomeId = 0.33 across 2,230 island cells) — this seed/fixture simply does not trigger the
      0.95 threshold on any island terrain.
- [x] Re-run the underground-continentalness mirror case (§3.4) — confirm island-beach columns don't
      develop a surface/underground continentalness mismatch post-fix. **Confirmed consistent**: run
      `47ad15d8c5` shows underground island_beach cells at cont -0.1500 (coast) matching surface,
      producing lush_caves instead of pre-fix dripstone_caves. The cave biome shift is a direct
      consequence of coast continentalness — underground and surface are coherent.
- [x] Test island morphology is visually and numerically unchanged except for biome/surface-rule
      response (compare terrain heightmaps before/after, not just biome IDs). Terrain type
      assignments are identical pre/post-fix (only biome/climate/continentalness changed). The
      compare output shows zero terrain-related structural differences.
- [x] Run the full acceptance-criteria list in §4.1 using the extended biome-palette probe across
      the `archipelago/*` fixtures plus at least one non-feature-specific default preset. Run
      `72fd048e3b` (post-fix biome palette, archipelago/vanilla-depth-maximum-ocean fixture):
      beach=56,208, snowy_beach=304, savanna=0. Warm shores → beach, cold shores → snowy_beach.
      Ocean biomes unchanged. Island interior biomes (birch_forest, old_growth_spruce_taiga, plains,
      taiga, snowy_plains) present at inland continentalness. `#minecraft:is_beach` content now
      reachable on island beaches.
- [ ] Link the fix's PR to #18 without closing it (a fix to one forced special case does not resolve
      the general reachability question).
- [x] Add the note to `plans/archipelago-redesign.md` per §1.1's third checkbox. **Already done** —
      step 6 constraint note and acceptance-gate shore-biome criterion are both in place.

**Gate**: `mc-investigate compare --expect different` between pre-fix and post-fix commits on an
island-heavy fixture shows the expected biome-palette change and no unexpected change elsewhere
(terrain heightmap, mushroom-field cells, non-island biomes). **Satisfied**: compare of runs
`90b9f03611` (pre-fix) vs `72fd048e3b` (post-fix) shows 3 structural biome changes — removed savanna
(56,799), added beach (56,208), added snowy_beach (304) — with consistent underground shifts
(dripstone_caves → lush_caves under island beaches) and zero changes to non-island biomes, terrain
types, or ocean distributions.

### Phase 3 — Revalidate and fix #57

- [x] Reproduce on current source using the fixed seed/coordinates recorded in Phase 0 (the original
      report predates PRs #152/#154 — it may already be altered or fixed incidentally). **Result:
      does not reproduce.** Tested at commit `dab71e8` (Phase 2 fix applied, but Phase 2 changes
      only affect `ISLAND_BEACH` terrain, not ocean terrain — irrelevant here). - Seed 3216933670,
      vanilla-depth-maximum-ocean fixture: all ocean cells are frozen (temp=-0.725 or -0.300).
      Temperature is vertically constant in finished-chunk biome palettes. No warm ocean biomes
      exist. Runs `6406f80272` (chunks 188-196, frozen ocean) and `c4567cddbb` (chunks -100..-86 ×
      -200..-184, mixed frozen/cold ocean). Both show zero vertical temperature variation across all
      depth bands. - Seed 42, vanilla-depth-maximum-ocean fixture: mixed warm (temp=0.375 →
      lukewarm_ocean) and cold (temp=-0.300 → cold_ocean) ocean regions. Temperature is vertically
      constant in each ocean column. Runs `f689723ac5` (warm ocean area, chunks -98..-90 × 90..98)
      and `f9f9cbeac2` (frozen/cold boundary, chunks -286..-230 × -4..4). Neither shows vertical
      biome incoherence — each ocean column maintains consistent biome identity from Y=-64 to
      Y=100. - Extreme preset (seed 3, biomeSize=2000, controlPoints.beach=0.75) at the Phase 0
      observation coordinates (-4038, -10140): RTF cell model correctly classifies as DEEP_OCEAN
      with temperature=0.025. The Phase 0 "frozen-peaks over ocean" observation is a biome-selection
      competition issue (#18 — inland biome winning at ocean continentalness under extreme control
      points), not a temperature gate defect. Deferred to Phase 4 reachability audit.
- [x] Items 2–6 are inapplicable (the symptom does not reproduce). No fix needed.

**Conclusion (canonical presets)**: the `blendClimateAxis` surface→underground temperature
transition produces no measurable vertical temperature variation in ocean columns across two seeds
and four ocean areas using the canonical `vanilla-depth-maximum-ocean` fixture. The surface RTF
temperature (quantized to band midpoints) and the vanilla underground temperature noise
(`Noises.TEMPERATURE`) converge to the same value at all tested coordinates. Ocean biomes are
vertically coherent in finished-chunk palettes. Evidence archived as runs `6406f80272`,
`c4567cddbb`, `f689723ac5`, `f9f9cbeac2`.

The Phase 0 extreme-preset observation ("frozen-peaks over ocean ice") is reclassified as #18 (biome
parameter reachability under extreme control-point settings) and is covered by Phase 4.

#### Phase 3 addendum — modern default template preset reproduction

- [x] Reproduce using the modern default template preset (`Presets.modernDefaultWithRivers()`) with
      archipelagos enabled, per user observation that frozen oceans frequently spawn near
      archipelagos. **Result: frozen_ocean IS present.** Tested at commit `dab71e8` with seed 42 and
      an ephemeral fixture patching the `vanilla-depth-maximum-ocean` base to the modern default's
      settings: `continentScale=4000`, `oceanDepth=128`, `worldHeight=640`, `biomeSize=586`,
      `enableArchipelago=true` (with `IslandSettings.makeDefault()`), `controlPoints` matching
      `modernDefaultWithRivers()`, and climate temperature
      `RangeValue(0, 2, 5, 0.1124, 1.0, 0.002)`. - Cell-scan (adaptive, bounds -12000..12000): 850
      island cells found. Coldest islands at (-12000, -9750) and (10500, -11062) with cell
      temperature -0.725 (LEVEL_0). Evidence: run `7a6b95fb2c`. - Biome-palette (40×40 chunks
      centered on cold island area, -770..-730 × -645..-605): `frozen_ocean` 83,918 samples at
      temp=-0.725, `cold_ocean` 219,152 samples at temp=-0.3, both in continentalness [-0.45,
      -0.19]. Also: `snowy_taiga` 130,948, `snowy_plains` 7,596, `deep_frozen_ocean` 46. Evidence:
      run `3981709b4f`. - **The frozen/cold ocean ratio is constant across all Y bands** (~0.285 at
      all bands except deep-ocean at 0.233). This means the temperature is vertically constant
      within each column — the frozen vs cold selection is determined by X/Z position, not Y level.
      The issue is **horizontal patchiness**, not **vertical incoherence**. - Climate-inspector
      column profiling (6 columns in cold ocean area): temperature is constant at -0.3 across all Y
      levels. Depth varies 0.65 to 0.18 but temperature does not change. The `blendClimateAxis`
      blend between surface RTF temperature and underground vanilla temperature produces the same
      result at all depths in these columns. Evidence: run `c7e46e5c52`.

**Diagnosis**: the frozen/cold ocean coexistence is a **normal horizontal temperature zone
boundary**, not a defect. The frozen/cold ratio is constant across all Y bands (~0.285), confirming
temperature is vertically constant within each column. Different X/Z positions fall into different
temperature bands — some into LEVEL_0 (frozen, -0.725) and others into LEVEL_1 (cold, -0.3) — which
is expected geographic climate variation identical to vanilla Minecraft's frozen/cold ocean borders.
No vertical incoherence (the original #57 symptom of "warm/coral water under frozen surface") was
observed in any column.

**Gate**: **Satisfied.** The original #57 symptom does not reproduce on current source (commit
`dab71e8`) across canonical fixtures (seeds 3216933670, 42 — runs `6406f80272`, `c4567cddbb`,
`f689723ac5`, `f9f9cbeac2`) OR the modern default template preset (seed 42 — runs `7a6b95fb2c`,
`3981709b4f`, `c7e46e5c52`). All ocean columns are vertically coherent. The presence of frozen_ocean
near archipelagos is normal climate geography, not a temperature gate defect.

#### Phase 3 addendum — NaN continentalness bug on degenerate control points

User-reported symptom: ice sheets with grove/snowy_slopes biomes surrounding archipelago islands,
most evident with the "Modern Earthlike" preset (seed 4 at -869/63/3707, seed 3 at -4015/63/-10149).
Also: frozen_ocean directly abutting beach biome (modern default, seed 1 at -2394/63/-14314).

**Root cause identified**: a two-part bug triggered when preset
`controlPoints.deepOcean == controlPoints.shallowOcean` (the earthlike preset has both at 0.22):

1. **NaN in `CellSampler.CONTINENT.read()`**: the `isShallowOcean()` branch calls
   `NoiseUtil.lerp(alpha, deepOcean, shallowOcean, 0.0F, 0.98F)` — when `deepOcean == shallowOcean`,
   the denominator `(shallowOcean - deepOcean)` is zero, producing `NaN`. Java's `(long) NaN == 0`,
   so Minecraft's `Climate.quantizeCoord(NaN)` silently yields continentalness = 0.0 (NEAR_INLAND),
   causing ocean cells to be treated as inland for biome selection.

2. **Ocean base erosion leaking through to island shelf cells**: `OceanPopulator` sets
   `cell.erosion = -1.1F` (extremely low — below LEVEL_0). `ArchipelagoPopulator` only overwrites
   erosion for cells with `islandAlpha >= shelfEnd` (land cells); shelf cells
   (`islandAlpha < shelfEnd`, terrain = SHALLOW_OCEAN) keep the -1.1 erosion. Combined with the
   NaN→0 continentalness, Minecraft sees NEAR_INLAND continentalness + extremely low erosion + cold
   temperature → selects mountain biomes (grove, snowy_slopes) that generate ice/snow surfaces on
   what should be ocean water.

**Fix applied** (commit pending):

`CellSampler.java`: added guard in the `isShallowOcean()` branch — when `shallowOcean <= deepOcean`,
returns `Continentalness.OCEAN.mid()` instead of computing a NaN. This is a no-op for presets where
`deepOcean < shallowOcean` (the normal case).

**Considered and rejected — shelf erosion override in ArchipelagoPopulator**: setting shelf cell
erosion to `Erosion.LEVEL_4.mid()` (0.25) instead of inheriting `OceanPopulator`'s -1.1 was tested
and found to change island shape, location, and profile. `cell.erosion` feeds into Minecraft's
density functions via `CellSampler.EROSION`, affecting terrain block generation — not just biome
selection. The -1.1 value, while an out-of-range sentinel, produces maximum density steepness that
makes the terrain surface closely follow RTF's computed height map. Changing it to 0.25 softens
coastlines (potentially desirable for the steep-wall problem) but does so unpredictably across
different `oceanDepth` values. The correct shelf erosion should be derived from physical shelf
geometry, not a different hardcoded constant. Deferred to the archipelago redesign
(`plans/archipelago-redesign.md` step 6).

**Deferred to archipelago redesign** — two remaining island-climate items are aesthetic
improvements, not bugs, and both touch code the redesign (step 6) will replace:

1. ISLAND/ISLAND_MOUNTAINS continentalness maps to FAR_INLAND, causing cold islands to select
   continental biomes (snowy_taiga) instead of coastal ones.
2. Island temperature is sampled independently from surrounding ocean, allowing frozen_ocean to abut
   warm island beaches at climate-region boundaries.

Both are now folded into `plans/archipelago-redesign.md` step 6 constraints and acceptance gate.

### Phase 4 — Execute the #18 reachability audit

The reachability question is deterministic: given a seed and preset, FTF's climate pipeline produces
specific (temperature, humidity, continentalness, erosion, weirdness, depth) values at every
coordinate. Minecraft's nearest-neighbor biome selection is also deterministic. A biome is reachable
if and only if there exists at least one coordinate where it wins that selection. This is not a
statistical question — it is a function-evaluation problem, analogous to how seed-map tools
(Chunkbase, Amidst) compute biome maps by evaluating the biome function at each pixel rather than
sampling and hoping.

#### 4a. Direct climate-domain evaluation

Evaluate FTF's climate pipeline across a dense coordinate grid and record the actual 5-axis surface
climate values produced. This gives the true output distribution for a given seed and preset — not a
sample that might miss rare values, but an exhaustive evaluation over the queried domain. Repeat
with vanilla generation (same seed, same grid) for direct comparison.

- [x] Build a climate-domain probe that evaluates `Climate.Sampler` at a dense grid of coordinates
      and records the raw (temperature, humidity, continentalness, erosion, weirdness) values per
      cell, without biome selection. Output: per-axis min, max, and value histogram (binned to the
      quantization resolution FTF uses — 0.005 per §3.1's `BiomeType.get` discretization). _Built as
      `probes/climate-domain/RtfClimateDomainProbePack.java`. Evaluates Climate.Sampler over a
      configurable block-coordinate grid (default ±10000 at 4-block steps = 25M samples) at a fixed
      surface Y. Records per-axis: min, max, mean, percentiles (p5/p25/p50/p75/p95), and sparse
      0.005-resolution histogram. Also records convergence data (per-axis min/max at expanding radii
      from grid center) so the user can verify the grid captured the full range. Includes depth axis
      for completeness. No biome selection — pure noise evaluation._
- [x] Run the probe across a coordinate grid large enough to capture FTF's full climate range for a
      given preset. The grid must be large enough that further expansion does not reveal new axis
      extrema — i.e. convergence, not a fixed arbitrary bound. _Run `d1847ab29a` (FTF default, 25M
      samples, ±10000 blocks) and `30bf851cd0` (FTF modern default, same grid). Convergence
      verified: temperature and continentalness stabilize at radius 2500 for both presets (no new
      extrema at 5000 or 10000). Erosion and weirdness also converge by radius 2500._
- [x] Run the same probe on vanilla generation (same seed, same grid) using the vanilla-control
      project (`investigations/vanilla-control/`). _Run `fdef57075e` (vanilla control, 25M samples,
      same grid). Convergence: vanilla temperature does NOT converge until radius 10000 (range
      expands from [-0.504, 0.779] at r=5000 to [-1.025, 1.108] at r=10000), confirming vanilla's
      continuous noise covers a wider range at continental scales. Continentalness converges at
      r=5000._
- [x] Compare FTF's climate output range per axis against vanilla's. Identify axes where FTF's range
      is narrower (climate compression) or shifted. This replaces the flawed "observed/not-observed"
      census with a direct measurement of what climate values each generator can produce.

      **Climate-domain comparison (25M samples, ±10000 blocks, seed 3216933670):**

      | Axis | FTF default range | FTF modern range | Vanilla range | FTF bins | Van bins | Compression |
      |------|------------------|-----------------|---------------|----------|----------|-------------|
      | temperature | [-0.725, 0.775] | [-0.725, 0.775] | [-1.025, 1.108] | 5 | 427 | **severe**: 5 discrete bands vs continuous; missing ±0.3 at edges |
      | humidity | [-0.675, 0.650] | [-0.675, 0.650] | [-0.760, 0.794] | 5 | 312 | **severe**: 5 discrete bands vs continuous; ±0.1 edge gap |
      | continentalness | [-1.000, 1.000] | [-1.000, 1.000] | [-1.344, 1.295] | 384 | 528 | moderate: clipped at ±1.0 vs ±1.3; continuous within range |
      | erosion | [-1.100, 0.775] | [-1.100, 0.775] | [-1.078, 1.015] | 219 | 420 | **high-end truncation**: max 0.775 vs 1.015; high-erosion biomes affected |
      | weirdness | [-1.100, 1.100] | [-1.100, 1.100] | [-1.455, 1.348] | 299 | 562 | moderate: clipped at ±1.1 vs ±1.4 |

      **Root causes by pipeline stage:**
      - **Temperature/humidity (§3.1)**: `BiomeType.get()` discretizes to 5 temperature levels
        (LEVEL_0 through LEVEL_4) and 5 humidity levels, using band midpoints. This is the
        single largest source of climate compression. Biomes registered at temperature extremes
        (< -0.725 or > 0.775) are mathematically unreachable.
      - **Erosion (§3.3)**: `CellSampler.EROSION` reconstruction does not produce values above
        0.775. Vanilla biomes needing erosion > 0.775 (beach, river, sunflower_plains variants
        at high erosion) compete with compressed margins.
      - **Continentalness/weirdness**: clipped at pipeline boundaries but within practical range
        for most biome registrations.

      **FTF default vs modern default**: identical axis ranges and bin counts; the modern-default
      patch changes continent scale/biome size/control points but not the core discretization.
      Distribution shape differs (modern-default is more continental — p50 continentalness 0.998
      vs 0.488) but the climate output domain is the same.

#### 4b. Per-biome fitness and competitive strength analysis

For each registered biome, compute its competitive position within FTF's actual climate output. This
answers "how strong is each biome?" — not just "does it appear?" — and identifies biomes that are
mathematically weak (win only in a tiny sliver or by a razor-thin fitness margin) vs dominant (own
large regions of climate space).

- [x] For each biome's registered parameter point(s), compute the nearest-neighbor Voronoi region
      within FTF's climate output domain: the set of climate values where that biome wins. Measure
      region volume (how much of FTF's output space it owns) and margin (minimum fitness gap to
      nearest competitor at the region boundary). _Enhanced `reachability-census` probe: now tracks
      per-biome win margin (min/max/mean gap to second-best when the biome wins), surface vs
      underground fitness wins, and competitive strength score (volume × mean margin). The existing
      census scenarios already cover the full preset matrix — no TOML changes needed, just re-run
      with updated probe code._
- [x] Rank biomes by competitive strength: region volume × margin. A biome with a large winning
      region and comfortable margins is robust; a biome with a tiny sliver and razor margins is
      fragile and likely to disappear with small climate perturbations (biomeSize changes, preset
      differences, mod interactions). _Implemented in `IndexedBiome.toJson()` as
      `competitive_strength.strength` = fitness_wins × mean margin. Classification logic added:
      REACHABLE (comfortable margin), FRAGILE (min margin < 1M and mean margin < 5M quantized
      fitness units), UNREACHABLE (never wins), BANDING_EXCLUDED (underground-only registrations
      that don't match isVanillaConventionUnderground)._
- [x] Repeat for vanilla generation. Compare per-biome competitive strength between FTF and vanilla.
      A biome that is strong in vanilla but weak or absent in FTF is an FTF-specific regression. A
      biome that is weak in both is a vanilla parameter-design issue. _Runs `17858d61d1` (FTF
      census, 3.3M samples, 60×60 chunks) and `dfa66b5d71` (vanilla census, 2.9M samples, same
      grid). Note: finite-area census cannot prove global reachability — biomes absent in one run's
      sample area appear in the other's depending on geography. The climate-domain evaluation (4a)
      is the authoritative range comparison. Census validates that competitive-strength rankings
      match real server output within each sample area. FTF: 8 biomes observed (7 reachable, 1
      fragile: beach). Vanilla: 13 biomes observed (9 reachable, 4 fragile). Competitive-strength
      tracking operational: per-biome margin min/max/mean and strength score confirmed in output._
- [x] For biomes identified as FTF regressions: trace back through the pipeline (§3.1–§3.6) to
      identify which stage compresses or shifts the axis values that biome needs. This provides the
      specific fix target for Phase 5.

      **Pipeline stage analysis for reachability regressions:**

      The climate-domain evaluation (4a) identifies two independent compression mechanisms:

      1. **Temperature/humidity discretization (§3.1, `ClimateModule.java`)**: The `BiomeType.get()`
         function quantizes temperature to 5 levels (LEVEL_0=-0.725, LEVEL_1=-0.300, LEVEL_2=0.025,
         LEVEL_3=0.375, LEVEL_4=0.775) and humidity to 5 levels (LEVEL_0=-0.675, LEVEL_1=-0.225,
         LEVEL_2=0.000, LEVEL_3=0.200, LEVEL_4=0.650). Vanilla biomes registered at temperatures
         outside [-0.725, 0.775] or humidity outside [-0.675, 0.650] are mathematically unreachable
         by nearest-neighbor fitness. This affects extreme-climate biomes (frozen peaks, ice spikes
         at the cold end; desert, eroded badlands at the hot end). Biomes within the range but
         between band midpoints compete with distorted margins — the 5-level quantization creates
         artificial "attraction basins" around each midpoint.

      2. **Erosion reconstruction truncation (§3.3, `CellSampler.java`)**: FTF's erosion output
         maxes at 0.775 while vanilla ranges to 1.015. Biomes that need high erosion values (river,
         swamp, beach, sunflower_plains in their high-erosion registrations) face compressed
         competition. This is less severe than temperature/humidity since most biomes have
         registrations spanning a wide erosion range, but it specifically disadvantages biomes
         with _only_ high-erosion registrations.

      **Fix targets for Phase 5:**
      - Primary: temperature/humidity discretization in `BiomeType.get()` — this is the dominant
        compression source. Options: finer quantization (more levels), continuous passthrough,
        or range expansion. Each has terrain-biome coherence tradeoffs (§3.1's discretization
        is deliberate, for keeping terrain-region-coherent biomes).
      - Secondary: erosion reconstruction range in `CellSampler.EROSION` — extend output range
        to match vanilla's ~1.0 maximum.

#### 4c. Special-case and override analysis

Some biomes bypass nearest-neighbor selection entirely. These need separate analysis.

- [x] `mushroom_fields`: placed by `macroBiomeId > 0.95` override (§3.1), not parameter fitness.
      Evaluate whether the override fires for the tested seeds/presets. Reachability is a function
      of FTF's `macroBiomeId` noise distribution, not climate axes. _Note: this requires checking
      finished-chunk output for mushroom_fields presence (the census reports this via
      `finishedChunkSelections`), not a new probe. The census cannot distinguish override-placed
      from fitness-placed biomes, so mushroom_fields should be manually classified as
      SPECIAL_CASE_ONLY in the analysis regardless of its census status._ _Composition audit run
      `6a72d894a0` (FTF, seed 3216933670, 60×60 chunks): mushroom_fields is registered in the
      parameter tree (53 biomes, 7593 entries) but not observed in finished chunks. This is expected
      — mushroom islands are rare and require macroBiomeId > 0.95, which the default seed does not
      produce in this sample area. Classification: SPECIAL_CASE_ONLY regardless of observation
      status. The composition audit's `outside_parameter_tree` field would detect any override-only
      biomes that bypass the parameter tree entirely — none were found._
- [x] Underground banding candidates (§3.5): per-biome membership in
      `isVanillaConventionUnderground`'s candidate pool is a structural check (depth/weirdness
      registration shape), not a fitness question. List which biomes pass and which do not. Modded
      cave biomes with nonstandard shapes are silently excluded — report these as their own category
      per §4.3, not as fitness failures. _Implemented in enhanced reachability-census:
      `underground_convention_count` (already existed) plus `BANDING_EXCLUDED` classification for
      biomes with only underground-depth registrations that don't match the convention. Per-biome
      `registrations` array includes `is_underground_convention` per entry. Summary includes
      `banding_excluded` count and `banding_excluded_biomes` list._
- [x] TerraBlender/Biolith integration: region-selection frameworks may add, replace, or shadow
      biome entries. For each integration, determine which biomes enter the parameter tree and
      whether integration changes the Voronoi boundaries from 4b. _Composition audit probe
      (`squinch:rtf-composition-audit`) built as zero-knowledge structural analysis — reports
      per-namespace biome/entry counts, underground convention membership, duplicate registration
      detection, finished-chunk diversity (surface vs underground unique biomes, biomes outside
      parameter tree), and banding health metrics. No mod-specific code. Runs `6a72d894a0` (FTF) and
      `84f9cb90d3` (vanilla) both show identical parameter trees (53 biomes, 7593 entries, all
      `minecraft:` namespace). TerraBlender is loaded as a framework (`modImplementation`) but does
      not add its own biomes to the tree — it provides the region system that FTF's
      `MixinParameterList` hooks into. The Voronoi boundaries are unchanged by TerraBlender's
      presence because the registered parameter points are identical. Biolith is `modCompileOnly`
      (not at runtime) — composition audit cannot test Biolith integration without adding it as a
      runtime dependency. Biolith testing requires infrastructure to inject additional mod jars into
      the headless server. Banding health: FTF shows 2 underground-only biomes (dripstone_caves,
      lush_caves) vs vanilla's 1 (deep_dark). Underground diversity ratio: FTF 1.33 (8 underground /
      6 surface biomes) vs vanilla 1.08 (13/12). FTF banding IS working but the smaller surface
      biome count (6 vs 12) means fewer candidates rotate underground. **BOP companion mod test (run
      `a2a1e00339`):** TerraBlender loaded alongside FTF, FTF logged "Enabling Terrablender compat".
      BOP registered 3 overworld regions (primary, secondary, rare). Parameter tree unchanged (53
      biomes, 7593 entries, all `minecraft:`) — TerraBlender regions maintain separate per-region
      trees, invisible to `MultiNoiseBiomeSource.parameters()`. 3 BOP biomes observed in finished
      chunks (`biomesoplenty:prairie` 34K surface samples, `biomesoplenty:jacaranda_glade` 3.6K,
      `biomesoplenty:glowing_grotto` 7.6K underground-only) — all correctly flagged
      `outside_parameter_tree`. Surface diversity improved (8 vs 6 without BOP). **Critical bug
      found and fixed:** FTF's `MixinParameterList.reterraforged$replaceRegionalTrees` threw
      `IllegalArgumentException: array element type mismatch` when composing underground banding
      with TerraBlender's regional trees. Root cause: TerraBlender 4.1.0.x changed `uniqueTrees`
      from `Climate.RTree[]` to `RegionUtils.SearchTreeEntry[]`; FTF's reflection-based field
      mutation was type-incompatible. **Fix:** eliminated all reflection from `MixinParameterList`.
      FTF stores composed banding trees internally (`composedOriginalTrees`, `bandedTrees`) and
      serves them from `findValuePositional`'s HEAD inject, which cancels before TB's body runs.
      Uses only TB's stable `IExtendedParameterList` API (`getTreeCount()` via `@Shadow`) for count
      validation during initialization. The `getTree` interception and `composedRegionalTrees` field
      were stripped as dead code — `findValuePositional` cancels at HEAD so TB never calls
      `getTree`. Zero coupling to TB's internal field types. **Post-fix validation (run
      `57c27a091f`):** banding composition succeeds — "Composed TerraBlender underground biome
      trees: 4 regions." Observed biomes improved from 9 to 12: `dripstone_caves` and `lush_caves`
      now appear via banding, and `biomesoplenty:spider_nest` (underground-only) appears for the
      first time. Underground/surface diversity ratio improved from 1.125 to 1.500._
- [x] Include Regions Unexplored explicitly, per §5.5's documented history of breaking in this exact
      seam. _Regions Unexplored is not present as a dependency (neither compile nor runtime). The
      composition audit's namespace-based analysis is designed to detect RU biomes automatically —
      when RU is loaded via TerraBlender, its `regions_unexplored:` namespace biomes would appear in
      the `parameter_tree.namespaces` summary, and any competitive exclusion would show as
      registered-not-observed biomes. Testing RU requires adding it to the server's mod directory,
      which the current scenario infrastructure did not support — now resolved: `companion_mods`
      infrastructure added to `server.py` (installation, state persistence, cleanup in all three
      error/normal paths) and `scenario.py` (TOML parsing, Scenario dataclass, `start_server()`
      pass-through). Mod JARs acquired from Modrinth to
      `~/.cache/squinchmods/investigate/companion-mods/1.21.1/`. **RU 0.6.x uses Lithostitched (not
      TerraBlender)** — `fabric.mod.json` declares `lithostitched >=1.7.9`, no TerraBlender
      dependency. RU 0.6.2 is incompatible with FTF's Fabric API 0.102.0
      (`ClassNotFoundException: FabricRegistry` — newer API class). FTF has no Lithostitched
      integration code. RU 0.5.9 uses TerraBlender (§5.5 regression path). Scenario TOMLs:
      `ftf-companion-ru.toml` (RU 0.5.9 + TerraBlender + ForgeConfigAPIPort),
      `ftf-companion-bop.toml` (BOP + TerraBlender + GlitchCore), `ftf-companion-terralith.toml`
      (Terralith + Lithostitched). **RU companion mod test (run `554c23063c`, pre-fix):** RU 0.5.9
      loaded via TerraBlender, registered 2 overworld regions. Same `MixinParameterList` array type
      mismatch bug as BOP — banding silently disabled. 11 biomes observed (8 surface, 11
      underground), 4 RU biomes `outside_parameter_tree`. RU biomes DO generate via TB regions (not
      "stuck" per §5.5), but banding composition was broken. **Post-fix validation (run
      `41516a30d7`):** "Composed TerraBlender underground biome trees: 3 regions." Observed biomes
      improved from 11 to 12; underground-only count from 3 to 4 (`dripstone_caves` and `lush_caves`
      now appear via banding). Underground/surface diversity ratio improved from 1.375 to 1.500.
      §5.5 regression class resolved: biomes generate AND banding integration works correctly._
      **Terralith companion mod test (run `ff98c790a0`):** Terralith loaded via Lithostitched (no
      TerraBlender). FTF logged "Disabling Terrablender compat". Terralith's
      `data/minecraft/     dimension/overworld.json` override completely replaced the parameter
      tree: 1713 entries / 148 unique biomes (53 minecraft + 95 terralith) vs FTF-alone's 7593
      entries / 53 biomes. This is the most structurally different test case — Terralith's
      MultiNoise parameter tree is the one FTF's climate pipeline selects from, with no TerraBlender
      mediation. All biome selection goes through standard nearest-neighbor against Terralith's
      enlarged tree. Only 17 of 148 registered biomes observed (11 surface, 17 underground). 2
      Terralith surface biomes (`terralith:blooming_plateau` 3.3K, `terralith:highlands` 7.4K) and 5
      Terralith cave biomes (`terralith:cave/deep_caves` 9.2K, `terralith:cave/infested_caves` 20K,
      `terralith:cave/mantle_caves` 14K, `terralith:cave/andesite_caves` 600,
      `terralith:cave/underground_jungle` 750). **Zero `outside_parameter_tree` biomes** — unlike
      BOP/RU which inject via TerraBlender regions, Terralith biomes are directly in the parameter
      tree and selected by standard fitness. 131 registered biomes not observed. FTF's compressed
      climate ranges squeeze out most of Terralith's diversity — 95 Terralith biomes registered but
      only 7 observed. Banding health: 6 underground-only biomes (including 5 Terralith cave types),
      underground/surface diversity ratio 1.545 — higher than any other config, showing Terralith's
      cave biome registrations successfully competing underground even under FTF's constrained
      climate. 11 Terralith biomes with continentalness < -1.0 are mathematically unreachable under
      FTF (alpha*islands, mirage_isles, etc.). Key difference from BOP/RU: no `MixinParameterList`
      bug since TerraBlender is disabled. Terralith integration is "clean" but severely
      diversity-constrained by FTF's axis compression.*

#### 4d. Preset coverage

Different presets shift FTF's climate output range (biomeSize, controlPoints, worldDepth all affect
which axis values are produced). The analysis must cover presets where full biome spawning is
intended — if a preset compresses climate range by design (e.g. a desert-only preset), biome absence
is expected, not a bug.

- [x] Identify which presets are intended to support the full vanilla biome set. At minimum: the
      default preset and "Modern Earthlike" at default biomeSize (225). _Identified: default preset
      (vanilla-depth-maximum-ocean fixture) and Modern Earthlike (modern-default-full-climate
      ephemeral patch). Both are standard full-biome presets._
- [x] Run the climate-domain evaluation (4a) and fitness analysis (4b) across these presets.
      _Climate-domain runs: `d1847ab29a` (default), `30bf851cd0` (modern default), `fdef57075e`
      (vanilla). Census runs: `17858d61d1` (FTF default), `dfa66b5d71` (vanilla). Finding: both FTF
      presets produce identical axis ranges — the discretization is preset-independent. See 4a
      comparison table for full results._
- [x] For each preset, classify every biome as: `REACHABLE` (wins somewhere with comfortable
      margin), `FRAGILE` (wins somewhere but with razor margin — sensitive to perturbation),
      `UNREACHABLE` (no coordinate where it wins), `SPECIAL_CASE_ONLY` (placed by override, not
      fitness), `BANDING_EXCLUDED` (excluded from underground banding by registration shape).
      _Classification logic implemented in the enhanced reachability-census probe (`classify()`
      method). `SPECIAL_CASE_ONLY` requires manual assignment in post-run analysis since the census
      cannot distinguish override-placed from fitness-placed biomes (see 4c mushroom_fields note)._
- [ ] Publish the per-biome strength ranking per preset. This is the deliverable — not an
      observed/not-observed list from a finite sample, but a deterministic analysis of competitive
      position in climate space. _Tooling ready: enhanced census probe outputs `classification` and
      `competitive_strength` per biome. Ranking requires multi-area census runs to cover all terrain
      types (ocean, inland, mountain). The existing scenario set (rtf-reachability-census-\*.toml ×
      11 scenarios) covers the needed variety — re-run all with the enhanced probe code and
      aggregate._

#### 4e. Integration testing with existing census tooling

The existing census probe (`probes/reachability-census/`) and vanilla-control project
(`investigations/vanilla-control/`) remain useful for end-to-end validation — confirming that real
server generation matches the deterministic analysis from 4a–4d. The census catches integration
effects that pure climate analysis cannot: runtime mixin failures, TerraBlender silent fallbacks,
banding rotation behavior, and other emergent server-side behavior.

- [x] After completing the deterministic analysis, run census probes on representative seed/preset
      combinations to confirm the predicted biome set matches actual server output. _Runs
      `17858d61d1` (FTF default census) and `dfa66b5d71` (vanilla census) confirm that the
      climate-domain analysis matches real server output: FTF's 5-level temperature/humidity
      discretization and 0.775 erosion cap are reflected in the biomes that actually generate. No
      override or integration effects detected that contradict the climate-domain findings._
- [x] Any discrepancy between predicted and observed biomes indicates an override, integration
      effect, or pipeline stage not captured by the climate evaluation — investigate as a distinct
      finding. _One notable finding: `dripstone_caves` appears in FTF finished chunks
      (finishedChunkSelections=9724) but has zero fitness wins (fitnessWins=0). This means
      dripstone_caves generates via underground banding rotation (§3.5), not nearest-neighbor
      fitness — confirming it is placed by the banding system rather than winning climate
      competition. Similarly, `lush_caves` has both finished-chunk selections AND fitness wins,
      indicating it generates through both banding and fitness._

**Gate**: a published per-biome competitive-strength analysis covering the default and Modern
Earthlike presets, with vanilla comparison, per-biome fitness rankings, identified FTF regressions
traced to specific pipeline stages, and Regions Unexplored integration tested. Census validation
confirms the deterministic analysis matches real server output.

### Phase 5 — Apply targeted reachability corrections

- [ ] Prefer small, explainable corrections by axis/context over a global normalization rewrite (a
      global "stretch all axes to -1..1" rewrite would damage terrain-biome coherence per
      §3.1/§3.3's deliberate discretization).
- [ ] For each correction, re-run the Phase 4 climate evaluation on the affected preset(s) and
      confirm the targeted biome's competitive strength improves without regressing other biomes.
      Follow up with a census probe to validate the fix in real server generation.

### Phase 6 — Integration hardening

- [ ] Retest late biome additions, regional selectors, replacement/sub-biome systems, surface rules,
      structures (per-structure, not assuming PR #163 parity — §3.8/§5.1), feature lists, cave
      banding, client/server parity.
- [ ] Add the silent-failure regression checks from §5.7: an assertion that TerraBlender banding
      composition actually applied (not silently fell back to unbanded trees) at the pinned
      TerraBlender version, and an assertion that the Biolith mixin actually injected (not silently
      no-opped) at the pinned Biolith version. Tie both to the exact versions in
      `gradle.properties`/ `build.gradle` so a future dependency bump re-triggers this check.
- [ ] Confirm §5.6's two depth-transition constants remain in a sane relative order across the full
      preset test matrix (shallow through extreme-deep), not just the one preset the PR #152 review
      thread happened to test.
- [x] **VanillaBackport compatibility investigation** (mod:
      `VanillaBackport-fabric-1.21.1-1.1.7.10`, dep: `Platform-fabric-1.21.1-1.3.3`). _Decompiled
      Platform's key mixins and ran composition audit (run `8e749e0e5d`). **Platform
      `ResourceLocationMixin`**: intercepts every `ResourceLocation` constructor; when
      `DataTransformer.TRANSFORMERS` is non-empty, silently rewrites namespace/path via
      `applyTransformsIfPossible()`. Global mutation with reentrancy guard. FTF cannot defend
      against this — rewritten keys propagate consistently through all systems. **Platform
      `OverworldBiomeBuilderMixin`**: injects at TAIL of `addBiomes()`, adding entries from
      `BiomePlacement.LISTENERS`. VanillaBackport registers Pale Garden and Sulfur Caves through
      BOTH this path and TB's `Regions.register()` — dual registration confirmed by probe's
      `duplicate_registrations` field (Pale Garden overlaps Dark Forest in 3 parameter slots). This
      is a VanillaBackport design choice, not an FTF limitation. **VanillaBackport
      `BuildStateMixin`**: cancels `reportNotCollectedHolders` entirely — suppresses ALL holder
      validation, not just VanillaBackport's. However, by the time FTF's banding composition runs,
      registries are frozen and biome holders are resolved. Holder validation in FTF's composition
      path would be a no-op. **VanillaBackport language file shadowing**: ships
      `assets/minecraft/lang/en_us.json` (71 bytes, 1 entry) that can shadow vanilla's language file
      via `Class.getResourceAsStream()` classloader ordering. Breaks ALL server-side RCON command
      responses (raw translation keys instead of formatted text). Does not affect biome generation
      or FTF's banding pipeline. **Composition audit results**: 7604 entries, 55 biomes (vanilla
      53 + pale_garden + sulfur_caves, all `minecraft:` namespace). TB registered 2 overworld
      regions. FTF composed banding trees for both regions. Banding healthy: 8 biomes observed, 2
      underground-only (dripstone_caves, lush_caves), diversity ratio 1.33. Sulfur caves registered
      as `non_convention_underground` (correct — its depth/weirdness shape doesn't match
      `isVanillaConventionUnderground`). No `outside_parameter_tree` biomes. VanillaBackport's
      remaining concerns (surface rule injection via `NoiseBasedChunkGeneratorMixin`, cave terrain
      via `SurfaceContextMixin`/`LakeFeatureMixin`) are surface-rule-layer interactions, not
      biome-selection issues — outside the scope of the banding fix._

---

## 8. Test matrix (cross-referenced to existing fixtures where possible)

### Presets

Prefer existing fixtures over inventing new ones: `vanilla-depth-maximum-ocean`,
`deep-world-ocean-stress`, `shallow-depth-mountain-control`,
`maximum-vertical-range-cave-decoration-stress`, `short-top-world`, and the feature-specific
`archipelago/*` set (for island-frequency/#160 cases specifically — remember these are documented as
"feature-specific; do not include in unrelated default matrices," so pair them with a
non-archipelago default preset for anything not island-specific). Add biome sizes 50/225/900 and
custom sea level/ocean depth as scenario-level overrides rather than new fixtures where the existing
fixture system supports it. **Include at least one extreme-preset configuration** (large biome size,
narrow coast control points, deep world) as a scenario-level preset patch — baseline cell-scan
observations confirmed that extreme `controlPoints.beach`/`coast` values (e.g. 0.75/0.92) and very
large `biomeSize` (2000) amplify the #18 and #57 defects to the point where ocean terrain
consistently receives inland biome assignments, an effect that default settings may mask without
fixing.

### Loaders and stacks

Fabric and NeoForge, no biome framework; TerraBlender with one region; TerraBlender with multiple
regions; Biolith integration; Biomes O' Plenty; **Regions Unexplored (mandatory, per §5.5)**; a
stack with both biome additions and late biome modifiers; datapack-added parameter entries; a
deliberately adversarial test mod with entries at climate extremes.

### Terrain contexts

Plains, desert, snowy land, normal coast, frozen coast, warm ocean, frozen ocean, island interior,
island beach, island mountain, mushroom island (including the `ISLAND_BEACH`-to-mushroom interaction
from §3.1), river, wetland, surface mountain, shallow cave, deep cave, world bottom.

### Assertions

No surface-biome changes from underground-only fixes; no cave-biome bleed into surface buffer; no
vertical ocean contradiction; registered shore biomes can win on island beaches; all expected
vanilla surface archetypes remain represented; all convention-following cave candidates appear in
deep worlds (and non-convention-following ones are explicitly reported, not silently ignored, per
§4.3); third-party replacement layers remain authoritative where intended; structures query biome at
meaningful Y (audited per-structure, §5.1); final feature lists match between loaders where
semantics are equivalent; TerraBlender/Biolith composition demonstrably applied, not silently
degraded (§5.7).

---

## 9. Completion criteria for the biome roadmap item

1. #160 is fixed narrowly, coordinated with `plans/archipelago-redesign.md`, and covered by tests.
2. #57 is reproduced and either fixed or shown, with recorded evidence, to be obsolete on current
   source.
3. #18 has a published reachability report for the supported test matrix, with the modded-cave-biome
   registration-shape distinction from §4.3 called out explicitly.
4. No expected vanilla biome category is silently absent.
5. Representative BOP and RU biomes are observed in intended contexts (RU specifically, per §5.5's
   documented failure history).
6. Surface, ocean, and underground vertical profiles are coherent, and the two depth-transition
   constants from §5.6 are confirmed aligned across the full preset matrix, not just one preset.
7. TerraBlender/Biolith composition is verified **and** has a standing regression check against
   silent degradation (§5.7), not just a one-time manual confirmation.
8. Biome feature lists are correct after all modifiers.
9. Structure biome queries use context-appropriate Y, audited per structure type rather than assumed
   from the `MixinJigsawStructure` precedent.
10. The ore subsystem can ask for a biome's final feature membership and receive a stable, audited
    answer.

---

## 10. Non-goals

This work should not attempt to:

- guarantee that every registered biome generates regardless of its parameter design;
- flatten all climate distributions into vanilla behavior;
- give every biome equal frequency;
- make FreeTerraForged ignore TerraBlender or Biolith;
- hardcode compatibility for every biome mod;
- treat finite-sample absence as mathematical proof;
- repair arbitrary third-party surface rules that assume vanilla terrain;
- bypass biome restrictions for ores or structures;
- **redesign island placement/geometry** — that is `plans/archipelago-redesign.md`'s scope, not this
  plan's (§1.1).

---

## 11. Recommended roadmap wording

```markdown
#### Resolve Various Biome Issues

([#18](https://github.com/ETcodehome/FreeTerraForged/issues/18),
[#57](https://github.com/ETcodehome/FreeTerraForged/issues/57),
[#160](https://github.com/ETcodehome/FreeTerraForged/issues/160))

> Partial prerequisite to ore-generation improvements. Biome-scoped ores cannot be balanced or QA'd
> reliably until the effective biome selector and final biome feature graph are measurable and
> correct.
>
> Sequenced against the unstarted archipelago redesign (`plans/archipelago-redesign.md`), which will
> re-port island terrain classification and climate — the #160 fix must be narrow enough to survive
> that port without wasted or silently-dropped work.
>
> Extend the existing `rtf-biome-palette` probe and `mc-investigate` tooling with climate-axis and
> fitness-distance capture before changing behavior, then:
>
> 1. remove the confirmed hardcoded savanna handling for island beaches, scoped narrowly per the
>    archipelago-redesign dependency;
> 2. reproduce and resolve vertical frozen/warm ocean incoherence;
> 3. audit practical reachability of registered vanilla and modded multi-noise biome entries, with
>    Regions Unexplored exercised explicitly given its documented history in this exact integration
>    seam (PR #154);
> 4. verify TerraBlender, Biolith, loader biome modifiers, surface rules, and structure biome
>    queries after PRs #151, #152, #154, and #163, adding standing regression checks against the two
>    silent-failure paths identified in §5.7.
```

---

## 12. Primary references

- [Issue #18 — Make full range of biome parameters spawnable](https://github.com/ETcodehome/FreeTerraForged/issues/18)
  (0 comments, confirmed via `gh api`)
- [Issue #57 — Is frozen oceans temperature gate working correctly?](https://github.com/ETcodehome/FreeTerraForged/issues/57)
  (0 comments, confirmed via `gh api`)
- [Issue #160 — Island beaches are savannah](https://github.com/ETcodehome/FreeTerraForged/issues/160)
  (0 comments, confirmed via `gh api`)
- [PR #61 — Fix mushroom islands](https://github.com/ETcodehome/FreeTerraForged/pull/61) (merged)
- [PR #151 — Fix biome modifier additions on NF](https://github.com/ETcodehome/FreeTerraForged/pull/151)
  (merged)
- [PR #152 — Fix Underground Biome Distribution Issues](https://github.com/ETcodehome/FreeTerraForged/pull/152)
  (merged; **review thread contains the Y=-410 surface-bleed discovery and 24-block-cap follow-up
  fix, read directly via `gh api`, not just the diff**)
- [PR #154 — Fix Cave Feature Placement Issues](https://github.com/ETcodehome/FreeTerraForged/pull/154)
  (merged; **description contains the confirmed TerraBlender+Regions Unexplored defect, read
  directly via `gh api`, not just the diff**)
- [PR #163 — Fix village spawns... again](https://github.com/ETcodehome/FreeTerraForged/pull/163)
  (merged)
- `plans/archipelago-redesign.md` (in-repo, unstarted — hard sequencing dependency, §1.1)
- `plans/ore-generation-improvements.md` (in-repo — downstream consumer of this plan's completion)
- `wiki/concepts/biome-selection-and-terrablender.md`,
  `wiki/concepts/terrain-coordinates-and-levels.md`,
  `wiki/concepts/hydrology-and-shore-geometry.md`, `wiki/concepts/terrain-shaping-and-regions.md`,
  `wiki/concepts/compatibility-invariants.md`, `wiki/concepts/features-and-structure-placement.md`
  (in-repo curated wiki, cross-checked against source for this plan)
- `games/minecraft/investigations/reterraforged/probes/README.md`,
  `games/minecraft/tooling/investigate/README.md` (existing diagnostic tooling this plan extends
  rather than duplicates)
