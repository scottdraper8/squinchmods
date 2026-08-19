# FreeTerraForged Biome Correctness Plan

**Repository:** `games/minecraft/mods/FreeTerraForged`

**Primary branch:** `1.21.1` (merged biome-fix baseline); the active preview follow-up is on
`hotfix/biome-previewer-bugs` and is pushed with upstream PR #186 open.

**Related issues:** [#18](https://github.com/ETcodehome/FreeTerraForged/issues/18),
[#57](https://github.com/ETcodehome/FreeTerraForged/issues/57),
[#160](https://github.com/ETcodehome/FreeTerraForged/issues/160),
[#171](https://github.com/ETcodehome/FreeTerraForged/issues/171)

**Sequencing dependency:** `plans/archipelago-redesign.md`

This is a design and validation plan, not a changelog. It records the behavioral model, the problems
that led to it, the fixes that are already part of that model, and the remaining work needed to make
biome preview, TerraBlender, and underground biome integration reliable.

## 1. Goals and invariants

FreeTerraForged should preserve FTF's terrain identity while presenting climate values to
Minecraft's biome selector in the form that vanilla and biome mods expect.

The intended behavior is:

- Surface biome mods register ordinary MultiNoise parameter points. Their temperature, humidity,
  continentalness, erosion, and weirdness values determine where they win; FTF must not replace
  those values with biome-ID-specific rules or a random biome mosaic.
- TerraBlender regional tables are intentional alternatives selected by its weighted positional
  function. FTF must preserve that boundary, retain the default tree as deferred fallback, and
  propagate additions injected after TerraBlender initialization without flattening every base
  datapack preset into every complete regional table.
- Underground cave biomes are candidates in the selected region's overlay. Shallow cave biomes
  occupy the first cave stage. Bottom/deep cave biomes, including siblings of `deep_dark`, become
  eligible only in later/deeper stages; same-point regional alternatives replace their fallback.
- A mod's unusual but valid climate shape must not disable banding for unrelated biomes.
- Any integration failure must fall back to the original vanilla/TerraBlender selection without
  restoring a Y-dependent climate transition or crashing world generation.
- Finished chunk biome palettes are authoritative for runtime validation. Cold biome-source queries
  are useful diagnostics but cannot replace finished-chunk checks.

The central reachability invariant is:

> Every biome intended to generate must own a non-zero, reachable winner region within the climate
> targets FTF produces for the terrain contexts where that biome is intended.

This does not mean every registered biome must generate everywhere, or that all biomes should have
equal frequency.

## 2. The real climate problems

Vanilla's `MultiNoiseBiomeSource` performs a continuous nearest-neighbor search over temperature,
humidity, continentalness, erosion, depth, weirdness, and offset. The five horizontal axes are
column-like 2D fields; depth is the principal vertical discriminator.

The former FTF pipeline violated that contract in several related ways:

1. Continuous temperature and moisture were reduced to a discrete `BiomeType`, then reconstructed
   from per-cell hashes. This widened statistical coverage but destroyed spatial coherence.
2. Region temperature and moisture were sampled at Voronoi cell centers, quantizing climate across
   biome-sized cells and causing abrupt boundaries.
3. Terrain types emitted nearly constant erosion and weirdness values. Large portions of vanilla's
   parameter space therefore had no reachable FTF targets.
4. All horizontal climate axes were blended with vanilla underground noise as Y changed. The blend
   completed before underground banding began, creating a transition gap in which surface climate
   and unbanded underground climate disagreed. This produced vertical biome stacking and a large
   transition layer when banding was unavailable.
5. Expanding ranges with per-cell interpolation improved reachability metrics but amplified a fine
   horizontal mosaic. Random hashes are not a substitute for continuous spatial noise.

The architectural correction is to fix the producer side of the pipeline instead of adding more
special cases to the biome consumer.

## 3. Current climate design

The following behavior is the baseline that the TerraBlender/banding work must preserve.

### 3.1 Continuous horizontal climate

- `ClimateModule` uses its existing continuous temperature and moisture noise directly for climate
  output, with smooth rescaling to Minecraft's coordinate range.
- Climate output is sampled at the query `(x, z)` position. FTF's cell center remains available for
  internal thematic classification, but it is not the sole source of vanilla temperature/moisture.
- `BiomeType` is no longer a runtime classification or surface-rule input. It survives only as a
  legacy preview label/color model plus two investigation fields and should be retired after the
  preview can resolve the actual active biome source safely.
- Temperature, humidity, continentalness, erosion, and weirdness are horizontal 2D fields. Only
  depth should provide ordinary vertical biome layering.
- The surface-to-underground climate blend is removed. Underground variety comes from depth-owned
  banding, not from changing horizontal climate axes with Y.

### 3.2 Erosion policy

The purpose of widening erosion is to make parameter points reachable without allowing generic
terrain to masquerade as wetland terrain. Ranges are derived from the `Erosion` level boundaries,
not from biome IDs.

| Terrain family    |                        Former output |       Current target range | Levels        | Rationale                                                  |
| ----------------- | -----------------------------------: | -------------------------: | ------------- | ---------------------------------------------------------- |
| Steppe            |  `LEVEL_4.mid ± 0.05` (`0.20..0.30`) |              `-0.38..0.45` | 2–4           | Open terrain needs ordinary climate coverage.              |
| Plains            |  `LEVEL_4.mid ± 0.05` (`0.20..0.30`) |              `-0.38..0.45` | 2–4           | Allows multiple vanilla plains/forest families to compete. |
| Plateau           | `LEVEL_3.mid ± 0.05` (`-0.06..0.04`) |              `-0.78..0.45` | 1–4           | Retains plateau identity while opening adjacent bands.     |
| Hills 1/2         |  `LEVEL_4.mid ± 0.05` (`0.20..0.30`) |              `-0.78..0.55` | 1–5           | Preserves slope variation across more biome registrations. |
| Dales             |          threshold around levels 2–4 |              `-0.78..0.55` | 1–5           | Uses the broader landform family range.                    |
| Badlands          |  `LEVEL_4.mid ± 0.05` (`0.20..0.30`) |              `-0.78..0.05` | 1–3           | Avoids generic wetland `LEVEL_6`.                          |
| Torridonian       |  `LEVEL_5.mid ± 0.05` (`0.45..0.55`) |              `-0.78..0.55` | 1–5           | Supports its full landform family.                         |
| Mountains 1/2/3   |               `LEVEL_1/2.mid ± 0.05` |               `-1.0..0.05` | 0–3           | Opens cold and elevated biome families.                    |
| Explicit wetlands |              mixed/terrain-dependent | `LEVEL_6` where identified | 6             | Keeps the wetland signal explicit.                         |
| Oceans            |               special ocean handling |       approximately `-1.1` | below level 0 | Retains ocean behavior.                                    |

`LEVEL_6` is not a generic variation band. FTF terrain is not constrained by the same vanilla
terrain/erosion coupling, so allowing every warm terrain to reach level 6 makes wetland biomes win
in visibly incorrect places. Regional diagnostics should inspect `terrain_erosion` before later
river, lake, or wetland passes overwrite the final erosion field.

#### 3.2.1 Distribution and spatial-scale correction

The nominal envelopes above were not sufficient by themselves. The two-octave Perlin source used for
provider variation is theoretically normalized to `[0, 1]`, but a 1,048,576-sample control put its
5th and 95th percentiles at approximately `0.304` and `0.696`. Mapping theoretical endpoints
directly into Erosion E1–E5 left only 15 samples (`0.00143%`) high enough to enter E5 before terrain
selection and blending. This was the first failing stage behind the missing windswept family.

The production follow-up introduces one shared `ClimateParameterSampler` for terrain-owned erosion
and weirdness. It clamps/maps the stable central `[0.3, 0.7]` distribution to `[0, 1]`, then lets
each terrain family map that source into its intended envelope. One shared spatial source avoids
provider, border, and mountain-variety discontinuities while retaining distinct family ranges.

Normalization increases gradient by `1 / 0.4`, so the source wavelength is expanded by the same
factor. The source scale is derived as:

```text
biomeSize / 0.4 / terrainHorizontalScale
```

For the exact seed-3 Modern Default preset, this is `586 / 0.4 = 1465`. The formula restores the
preset's physical biome scale after normalization rather than introducing a new tuned constant.
Matched screenshot-window scans reduced erosion/weirdness boundary crossings from `44.2592%` after
override removal to `34.1283%`, below the old override's `35.6944%`, while restoring ordinary E5
production.

### 3.3 Weirdness policy

- Generic steppe, plains, hills, and badlands use the bounded ordinary-land range `[-0.4, -0.06]`.
- The macro-biome sign inversion provides the corresponding positive variant slices.
- The generic range deliberately excludes the valley interval `[-0.05, 0.05]`; ordinary terrain must
  not become a River biome merely because it sampled a valley value.
- Dales and torridonian retain negative height-derived weirdness.
- Mountains retain height-based weirdness.
- Plateaus retain weirdness derived from valley structure.
- Rivers, lakes, and wetlands retain their explicit climate assignments.

This is a producer-level policy, not a final clamp. It must not erase an explicitly assigned water
or river climate.

Follow-up finding: the older `Heightmap.applyClimate` river-valley assignment overwrote
producer-selected erosion and weirdness for many non-island cells before final biome lookup. This
was especially destructive for the E5 climate band used by the windswept biome family because the
override value `0.445` falls just inside E4. The generic assignment is removed in the committed
production implementation. Only explicitly classified rivers, submerged lakes, and wetlands retain
producer-independent hydrology climate values; ordinary valley influence preserves the terrain
producer's climate. The generic weirdness source already maps to the intended `[-0.4, -0.06]`
interval; there is no code/design discrepancy on that point.

### 3.4 Narrow correctness fixes

- When `deepOcean == shallowOcean`, shallow-ocean continentalness must use the ocean value rather
  than divide by a zero-width interpolation range.
- Island beaches select by coastal climate/continentalness rather than a hardcoded savanna biome.
- The archipelago redesign remains a separate scope. Its island placement, shape, and climate code
  may replace parts of the current region model later.

## 4. Underground biome model

Underground selection should be a scheduling layer over original climate registrations, not a second
unrelated biome source.

### 4.1 Candidate roles

The implementation must distinguish roles structurally:

- **Surface:** not eligible for cave banding.
- **Shallow cave:** eligible for the first underground stage.
- **Bottom/deep cave:** not eligible for the first cave stage, but eligible after the deep-stage
  boundary. `deep_dark` is the canonical example, not a hardcoded special case.
- **Unknown/nonstandard:** remain on the original climate path until the registration can be
  classified safely.

Depth is the primary semantic signal. Full vanilla weirdness coverage is one supported convention,
not a universal requirement. A biome such as Vanilla Backport's Sulfur Caves uses underground depth
but a narrow weirdness interval (`-1.1..-0.85`); that must not be discarded merely because it does
not use the full vanilla weirdness span. Its original horizontal constraints must remain meaningful.

The classifier must be data-driven and explainable. It may use climate depth shape, registration
provenance, and underground biome tags as corroborating signals, but must not depend on BOP, Vanilla
Backport, or other mod IDs.

### 4.2 Banding behavior

- Preserve the original climate list above a terrain-relative surface buffer.
- Choose the first cave candidate from the original horizontal climate registrations.
- Rotate eligible candidates by depth below the buffer, with a spatially coherent phase field.
- Keep deep-only candidates out of the shallow stage.
- Include shallow and deep candidates in later stages according to their roles.
- Preserve each candidate's temperature, humidity, continentalness, erosion, and weirdness intent;
  do not replace all entries with generic full-range synthetic points.
- If fewer than two valid candidates remain, leave the original list unchanged.
- Build every regional underground overlay from the default cave slots, that region's replacements
  and additions, and all late global additions. Do not flatten mutually exclusive regions together.

The surface buffer and world-depth scaling must remain internally consistent. The current maximum
surface buffer is 24 blocks; changing the depth schedule requires rechecking surface bleed, band
count, horizontal footprint, and short/deep-world behavior together.

## 5. TerraBlender and Biolith integration model

TerraBlender selects a positional region before resolving that region's climate list. This is a
useful optimization and a legitimate mod API, but it is also the source of the current composition
boundary: entries in separate regional trees do not automatically compete with each other.

The integration must therefore distinguish three concerns:

1. **Registration:** collect vanilla entries, every TerraBlender regional entry set, and late global
   additions without losing provenance.
2. **Lookup optimization:** preserve TerraBlender's native weighted positional-region selection and
   resolve the climate point against the selected region's immutable tree. Do not substitute FTF's
   discrete biome-region cell ID or flatten alternative region tables into one global competition.
3. **Underground scheduling:** build one cave layout per region. Start with the default cave slots,
   replace a default slot when that region registers an alternative at the same parameter point, add
   distinct regional cave points, and restore late injected additions in every layout. This keeps
   fallback alternatives mutually exclusive while allowing datapack/global additions everywhere.

Biolith's TerraBlender compatibility hook runs after Biolith computes its fittest result. It should
compose underground banding beneath Biolith replacements and sub-biomes, while leaving surface
results unchanged. It must remain optional and version-tolerant; a missing or changed Biolith hook
must not disable ordinary TerraBlender or vanilla biome selection.

## 6. Historical failures that must not recur

The earlier attempts are useful because they show where fallback and composition boundaries fail.

### 6.1 Y-blended climate plus banding

The underground climate mapping introduced by `a5bee8f`, then used by the early banding work,
blended surface and vanilla underground climate over roughly 12 blocks. Banding began later, leaving
a gap in which horizontal climate was already underground but the banding layer had not started.
This caused vertical biome stacking and a large transition layer whenever banding was absent.

The direct 2D climate correction removes this failure mode. A banding failure must now return the
original biome selection, not re-enable a Y-dependent climate fallback.

### 6.2 Reflection failure in TerraBlender 4.1

The early TerraBlender composition implementation used reflection to read and replace `uniqueTrees`.
TerraBlender 4.1 changed the array element type. `Array.set()` then failed during composition, and
the catch path preserved the original TerraBlender trees, meaning banding did not run for
multi-region chunks.

This is recorded in commit `599c17b`, whose fix replaced reflection with stable tree-count
validation and internally owned banding trees. Vanilla Backport exposed the problem by registering a
second region; it was not necessarily the source of the type incompatibility.

### 6.3 Cave-slot alternatives and nonstandard cave registrations

The first Phase 6 implementation flattened every regional tree into one climate index and one cave
catalog. That treated TerraBlender alternatives as additive registrations. BOP intentionally
registers Spider Nest at the Dripstone Caves parameter point and Glowing Grotto at the Lush Caves
point, so flattening allowed the alternative and fallback to compete simultaneously. It also made
surface alternatives such as Dead Forest tiny exact-point winners inside unrelated vanilla biomes.

The corrected implementation uses regional cave-slot overlays: a same-point regional cave replaces
the default candidate for that region, while a distinct point remains additive. Late global entries
are then added to every regional overlay. No biome ID or namespace-specific rule is required.

The former exact-shape recognizer also excluded valid nonstandard registrations. The Vanilla
Backport audit found Sulfur Caves in the parameter tree but classified it as non-convention because
of its narrow weirdness range. This was a candidate-classification limitation, not a registration
failure.

### 6.4 Surface region mosaicing

Before Phase 6, FTF supplied TerraBlender uniqueness from the discrete `biomeRegionId` cell value.
That value is a per-cell hash mapped to a regional tree index, so a nearby location could abruptly
switch from one complete regional biome table to another. This explained the observed surface
clustering.

The initial Phase 6 global index removed the custom cell boundary but introduced a worse semantic
error: complete TerraBlender alternative tables competed point-by-point, producing surface
micro-biomes and cave-feature overlap. The corrected design keeps one immutable surface tree per
TerraBlender region and restores TerraBlender's native weighted `getUniqueness(x, y, z)` selector.
The canonical snapshot is diagnostics/provenance only. FTF's discrete `biomeRegionId` is no longer
used to select a TerraBlender tree.

## 7. Phase 6 — TerraBlender composition and underground banding redesign

**Status:** implemented and merged into `1.21.1`; follow-up climate-preservation validation is
ongoing. Issue #171 is resolved by the merged biome updates.

### 7.1 Phase goals

- Preserve climate competition within each TerraBlender alternative region while using its native
  weighted positional selector between regions.
- Build region-aware underground overlays in which same-point alternatives replace fallback slots
  and distinct/global registrations remain additive.
- Accept valid narrow or mod-specific climate shapes without IDs or namespace-specific branches.
- Keep deep-only candidates out of the first cave stage.
- Make every failure local, observable, and recoverable.
- Preserve TerraBlender and Biolith performance characteristics as far as practical.

### 7.2 Implementation sequence

1. **Freeze behavior with diagnostics before editing.** Add or extend a composition audit that
   records, for each parameter list: region count, source list sizes, entries by provenance,
   candidate role, selected region, selected original biome, selected banded biome, and fallback
   reason. Run it for vanilla, BOP, Vanilla Backport, Regions Unexplored, and a Biolith-enabled
   stack.

2. **Separate capture from transformation.** Capture the base list, each regional list, and late
   global additions through the stable TerraBlender initialization seam. Do not reflect into or
   mutate TerraBlender's private tree storage. Keep the original regional selector available as a
   fallback.

3. **Create a canonical composition snapshot.** Deduplicate only exact duplicate registrations;
   retain all distinct parameter points and their source region. Maintain enough provenance to
   explain why a biome was or was not eligible. Construct optimized lookup structures once per
   parameter-list snapshot, never per biome query.

4. **Refactor underground classification.** Replace the all-or-nothing full-weirdness test with a
   structural role classifier. Test vanilla cave shapes, deep dark, BOP caves, Vanilla Backport
   Sulfur Caves, narrow weirdness ranges, bottom-only points, tags, malformed points, and ordinary
   surface points. Unknown entries must remain on the original path rather than disabling all
   banding.

5. **Build regional underground overlays.** Begin each layout with the default-region cave groups.
   At an identical parameter point, replace the default group with that region's alternatives;
   retain distinct regional points as additions, then restore late global additions. Apply band
   counts, depth scheduling, and horizontal phase independently to each immutable layout.

6. **Define surface composition explicitly.** Build one immutable climate index for each captured
   regional list, including late global additions. Select it with TerraBlender's native weighted
   positional uniqueness function. Retain the canonical snapshot for provenance and validation;
   never use it as a flattened lookup tree. A deferred regional winner falls back locally to the
   default tree.

7. **Harden fallback paths.** If capture counts mismatch, a regional list is null, classification
   fails, or layout construction throws, preserve the original TB result for the affected path. A
   single invalid entry must not erase valid candidates. Log a structured reason and expose enough
   counts to detect silent banding loss. With the current 2D climate model, fallback must not create
   a transition layer.

8. **Keep Biolith composition at the boundary.** Apply the selected regional FTF underground result
   beneath Biolith's selected ultimate candidate only when the result is actually underground and
   banding has a valid layout. Preserve Biolith distance metadata and replacements. Surface Biolith
   results must remain unchanged.

### 7.3 Required unit and integration tests

Unit tests should cover:

- candidate role classification for vanilla shallow caves and bottom entries;
- narrow-weirdness underground entries such as Sulfur Caves;
- BOP-style regional cave entries and deep-only entries;
- mixed valid/invalid registrations, null regions, missing late additions, and duplicate points;
- one candidate, zero candidates, and layout-construction failure;
- first-band shallow ownership and later deep eligibility;
- original-list fallback when composition is incomplete;
- stable tree/index selection and no per-query layout allocation.

Runtime tests should include these stacks:

- vanilla without TerraBlender;
- TerraBlender with one region;
- BOP with multiple TerraBlender regions;
- Vanilla Backport + Platform + TerraBlender;
- Regions Unexplored with TerraBlender;
- a Biolith-based stack on both Fabric and NeoForge where available;
- TerraBlender absent, present with two regions, and present with three or more regions.

### 7.4 Acceptance behavior

For finished chunk palettes, verify:

- vanilla lush and dripstone caves remain independently locatable and observable;
- BOP Glowing Grotto and Spider Nest replace their intended regional Lush/Dripstone fallback slots
  rather than coexisting with those fallbacks at the same point;
- Vanilla Backport Sulfur Caves are present in the candidate audit and can win where their climate
  values are reachable;
- deep dark and other bottom-only entries do not occupy the first cave stage;
- cave transitions begin only after the surface buffer and do not produce the former large climate
- surface BOP and other modded biomes do not form abrupt per-cell mosaics caused by regional-table
  switching;
- exact biome locate predicates return the requested biome ID, not merely a biome from a related
  tag;
- direct queries and finished chunk palettes agree at sampled points;
- no composition failure disables all banding or crashes generation.

### 7.5 Performance acceptance

TerraBlender's biome lookup is a hot path. The implementation should compare against the current
baseline using identical seeds, presets, region bounds, and mod stacks. Record:

- server startup and first-chunk generation time;
- finished-chunk generation time for a fixed area;
- parameter-list construction time and entry counts;
- allocation or cache behavior if a profiler is available;
- lookup time with no TerraBlender, one region, and multiple regions.

The regional catalogs must be immutable or safely published after construction. No reflection,
per-query list rebuilding, or unbounded synthetic expansion of parameter points is acceptable.

### 7.6 Current validation state

The common test suite and both Fabric and NeoForge builds pass. Finished-chunk composition audits
pass for multi-region BOP, Vanilla Backport, and Regions Unexplored stacks. The corrected BOP audit
created four weighted regional surface trees, replaced nine regional cave slots, inspected 3,721
finished chunks, and reported no composition fallbacks. Direct selections agreed with 3,333,974 of
3,334,016 stored quart-biome samples; the small remainder is the expected query/palette boundary
difference rather than a composition fallback.

A Fabric runtime audit with Biolith 3.0.14, TerraBlender 4.1.0.8, and BOP 21.1.0.14 inspected 1,681
finished chunks, enabled Biolith's TerraBlender compatibility layer, and reported no selection
fallbacks. The equivalent NeoForge Biolith runtime also works. Lithostitched 1.7.13 plus Terralith
2.6.2 passed 3,721 finished chunks; because that stack does not use TerraBlender, the regional
composition layer correctly remained dormant. A combined TerraBlender/BOP/Lithostitched/Terralith
run also inspected 1,681 finished chunks with no fallback. It preserved Terralith as the default
datapack tree and BOP's three complete regional alternatives rather than flattening the two
placement systems. The remaining validation is a repeatable profiler-backed lookup benchmark.

Maintainer client QA additionally confirmed real Terrestria 7.0.3 Japanese Maple Forest placement
and successful YUNG's Cave Biomes 3.1.1 placement. A reduced exact-version Fabric reproduction with
Terrestria, Biolith 3.0.14, TerraBlender 4.1.0.8, and YUNG inspected 1,681 finished chunks with no
selection fallback. Its biome source advertised all 18 Terrestria and both YUNG cave biomes, and
`/locate biome` returned coordinates for Japanese Maple Forest, Canyon, and Frosted Caves. The
maintainer's earlier lookup failure came from BiomeSpy, which did not return the Biolith-managed
biomes; vanilla `/locate biome` was not failing. Treat that result as a BiomeSpy/Biolith
compatibility issue rather than an FTF biome-placement or locate issue unless later evidence
implicates FTF itself.

The seed-3 Modern Default climate-preservation follow-up has now also passed its producer and
finished-world gates. A broad 65,536-point scan found 403 E5 samples in hill-family terrain, 199 of
them outside the old river-override zone. Targeted 81-chunk finished worlds produced independent
parameter-tree wins and stored surface palettes for windswept hills, windswept forest, windswept
gravelly hills, and windswept savanna. Full common tests and both Fabric and NeoForge builds pass.
The climate-preservation implementation and the responsive biome-preview/integration work are
committed on `hotfix/biome-previewer-bugs`; the branch is synchronized with its origin. The
remaining validation is a repeatable profiler-backed lookup benchmark and the optimization work
described below.

### 7.7 Preview performance model and optimization requirements

The preview is a procedural render, not a load of an already-generated map. A prepared generator
context and resolver are reused between requests, but `TileGenerator.generateZoomed` creates a new
tile for every zoom or navigation request. With the current editor factor (`4`), each request
evaluates a 256×256 tile, or 65,536 cells, regardless of the on-screen texture size. The previous
tile is retained only for display until the replacement completes; it is not a source cache for a
different zoom.

For a tile width `S`, `Q = S²` cells, `E` biome parameter entries, `R` selected TerraBlender region
entries, and `C` underground candidates, the current work is approximately:

| Stage                  | Work per request                                                                    | Current behavior                                                                                                                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FTF terrain            | `O(Q · G)`                                                                          | Every cell reruns terrain, river, climate, and required filters; `G` is the per-cell noise/river/filter cost.                                                                                                  |
| Active biome selection | `O(Q · (L(E/R) + C))`                                                               | Each cell samples climate and calls the positional biome-source path. `L` is the parameter-tree lookup cost (nominally logarithmic, but dependent on the R-tree traversal); banding scans candidates linearly. |
| 2D sidecar and pixels  | `O(Q)`                                                                              | Each cell resolves an exact biome ID/color and the render mode writes one pixel.                                                                                                                               |
| 3D texture rebuild     | `O(W·H)` in the normal projected layout, with a high per-cell/native-image constant | The render thread clears the image and paints three clipped faces per cell; `W×H` is the UI texture size.                                                                                                      |
| texture upload         | `O(W·H)` or `O(Q)` for 2D                                                           | The full native image is copied/uploaded after each completed frame.                                                                                                                                           |

The most expensive correctness-driven path is the active biome lookup. The preview now opens a
screen-scoped integration session once per sidecar and carries the exact composed positional result
through the TerraBlender parameter-list and MultiNoise return hooks. The resolver consumes that
result when it is still authoritative; a Biolith/Lithostitched replacement that changes the holder
does not match the hand-off and therefore remains authoritative. The fallback inspection path is
retained for non-composed sources and replacement failures. Integration setup is still once per
tile, not once per cell, so session setup is not the dominant term.

The preview cache is scoped to the owning preset-config screen and keyed by the complete biome
revision plus center, zoom, and tile size. It is bounded and lease-based because pooled `Tile`
instances are mutable resources: 2D and 3D can share completed terrain tiles safely, while a sidecar
future shares exact positional biome IDs/colors even when both views request the same tile
concurrently. Eviction recycles a tile only after its last reader releases its lease; closing a
screen evicts the cache and does not leave a static tile reachable by a later page.

Biome resolver construction is lazy and occurs only for a BIOME render request. Superseded requests
cancel their token through terrain-cell loops, sidecar iteration, and raster stages; stale results
are released rather than uploaded. 2D mode changes rasterize on the worker pool, and 3D geometry,
color shading, and clipped-face rasterization are calculated into an ordinary pixel buffer off the
render thread. The render thread is limited to the required NativeImage copy/upload and UI draw.
Dimension changes or mode changes invalidate only the corresponding raster request; unchanged
terrain and exact sidecars remain reusable.

Zooming still cannot be instant merely by retaining the current tile: changing zoom changes the
world coordinate sampled by almost every cell. The current cache therefore guarantees exact reuse
for repeated views and page transitions without claiming an unsafe approximate interpolation. Future
multi-resolution/incremental cell reuse must use the same revision and positional parity checks; it
must not bypass TerraBlender, Biolith, Lithostitched, or other biome integrations.

## 8. Validation methodology

Use several authorities because each catches a different class of defect:

1. **Unit tests** validate climate-range helpers, role classification, band scheduling, and fallback
   behavior.
2. **Cell-scan and climate-domain probes** measure the actual FTF climate pipeline over dense
   coordinate grids. They are authoritative for axis continuity, range coverage, and spatial
   gradients, but do not prove final biome storage.
3. **Finished-chunk palette probes** force generation, wait for `FULL` chunks, and inspect stored
   quart biome cells. They are authoritative for generated biome identity and vertical bands.
4. **Direct biome-source queries** validate locate-like behavior and sampler paths, but must be
   compared with finished palettes because cold and cached samplers can differ.
5. **Composition audits** report registered, classified, selected, observed, and fallback states.
   Never interpret “registered” as “reachable,” or a finite census as a prevalence measurement.

Every runtime comparison should keep seed, preset, coordinates, world height/depth, loader, and mod
versions identical. Small-area tests are good for deterministic regressions; broad regional scans
are needed for spatial distribution and frequency claims.

## 9. Issue status and later QA

| Issue                                                            | Status                                      | Behavioral conclusion                                                                                                                                                                       |
| ---------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [#160](https://github.com/ETcodehome/FreeTerraForged/issues/160) | Addressed                                   | Island beaches use coastal climate selection rather than hardcoded savanna.                                                                                                                 |
| [#57](https://github.com/ETcodehome/FreeTerraForged/issues/57)   | Does not currently reproduce                | Frozen/cold ocean coexistence is a horizontal climate question; retain the regression fixture.                                                                                              |
| [#18](https://github.com/ETcodehome/FreeTerraForged/issues/18)   | Follow-up implemented, validated, committed | Shared normalized/preset-scaled climate sources restore meaningful E5 occupancy and smooth boundaries; all four vanilla windswept variants won and were stored in targeted finished worlds. |
| [#171](https://github.com/ETcodehome/FreeTerraForged/issues/171) | Addressed                                   | Resolved by the merged biome updates; retain finished-chunk evidence for regression coverage.                                                                                               |

River/flowfield regression coverage should retain the same seed, preset, region, and finished-chunk
distinction between intentional river/wetland terrain and micro River biomes on terrain without a
visible channel.

## 10. Test matrix

### Presets and terrain contexts

Use the existing ocean, deep-world, shallow-world, maximum-height, short-world, modern-default, and
archipelago fixtures. Include biome sizes 50, 225, and 900 plus extreme control-point cases. Sample
plains, desert, snowy land, normal and frozen coasts, warm and frozen oceans, islands, rivers,
wetlands, mountains, shallow caves, deep caves, and the world bottom.

The primary regression anchor is seed `3` with the modern-default preset, especially the region
around `(-1438, 146, 363)`. The exact user-supplied `Modern - Default with 3D Rivers` preset is
available read-only under the Zioncraft profile's `config/reterraforged/presets/` directory.

Use this as read-only test input; do not modify the Zioncraft profile. Compare the surface palette,
climate gradients, selected TerraBlender region, and underground palette around the anchor before
and after any composition change.

### Loaders and mod stacks

Test Fabric and NeoForge; no biome framework; TerraBlender with zero, one, and multiple regions;
BOP; Regions Unexplored; Terralith/Lithostitched where compatible; Vanilla Backport + Platform; and
Biolith integration where a suitable companion stack exists.

### Minimum assertions

- All five horizontal climate axes are smooth and Y-invariant.
- Surface biome identities are spatially coherent at terrain-region scale.
- No vertical surface biome stacking occurs before the banding buffer.
- Expected vanilla surface and underground archetypes remain reachable.
- Modded surface entries compete by climate values within their intended registration scope rather
  than IDs or brittle namespace rules.
- All valid underground candidates are classified and banded appropriately.
- Deep-only candidates never own the first cave stage.
- TerraBlender and Biolith composition is demonstrably active, not silently bypassed.
- Fallback preserves original selection and does not crash or recreate the old transition layer.
- Erosion/weirdness widening does not create visible terrain artifacts.
- Low `riverMask` on ordinary hills, mountains, coast, or ocean cells does not replace the
  producer-selected erosion/weirdness pair.
- Explicit rivers, submerged lakes, and wetlands retain their hydrology-owned climate values.
- Windswept biome targets remain reachable in finished chunks after the E5 climate band is restored.

### `BiomeType` preview retirement

`BiomeType` is not a runtime biome-selection input. Its remaining production consumers are
`Cell.biome`, three `ClimateModule` assignments, the 2D/3D preview biome-type colors, and preview
hover labels. The enum/loader/color resources and two investigation adapters exist only to support
that legacy preview model.

Retirement must replace the preview model before deleting it. The replacement should use the patched
worldgen registries already available to the preset screens, construct or obtain the actual selected
`MultiNoiseBiomeSource` and climate sampler, and call the positional four-argument biome query at
the preview surface height. A direct parameter-list lookup is insufficient because it bypasses
positional TerraBlender and Biolith composition. Resolve the returned holder to its exact namespaced
registry ID and compute/store preview pixels on the existing worker pipeline, never on the render
thread.

Modded biomes do not expose one universal identity color. The preview therefore needs an explicit
color policy: configured overrides where present and a stable registry-ID-derived fallback, while
hover/legend output always displays the actual ID. Cache identity must include seed, preset patch,
datapacks, and biome registrations. Validate preview IDs against finished-chunk palettes with
vanilla, TerraBlender, Biolith, and mixed stacks; then remove `Cell.biome`, the assignments,
`BiomeType`, its loaders/resources, and the diagnostic `biome_type` fields together.

## 11. Non-goals

- Guaranteeing every registered biome generates regardless of its parameter design.
- Giving every biome equal frequency.
- Hardcoding compatibility for individual biome mods.
- Flattening all TerraBlender regional semantics without measuring the performance and behavior
  cost.
- Repairing third-party surface rules that assume vanilla terrain.
- Redesigning island placement, geometry, or macro climate; that belongs to
  `plans/archipelago-redesign.md`.

## 12. References

- [Issue #18 — Make full range of biome parameters spawnable](https://github.com/ETcodehome/FreeTerraForged/issues/18)
- [Issue #57 — Is frozen oceans temperature gate working correctly?](https://github.com/ETcodehome/FreeTerraForged/issues/57)
- [Issue #160 — Island beaches are savannah](https://github.com/ETcodehome/FreeTerraForged/issues/160)
- [Issue #171 — later River/flowfield QA investigation](https://github.com/ETcodehome/FreeTerraForged/issues/171)
- [PR #61 — Fix mushroom islands](https://github.com/ETcodehome/FreeTerraForged/pull/61)
- [PR #151 — Fix biome modifier additions on NeoForge](https://github.com/ETcodehome/FreeTerraForged/pull/151)
- [PR #152 — Fix underground biome distribution](https://github.com/ETcodehome/FreeTerraForged/pull/152)
- [PR #154 — Fix cave feature placement](https://github.com/ETcodehome/FreeTerraForged/pull/154)
- [PR #163 — Fix village spawns](https://github.com/ETcodehome/FreeTerraForged/pull/163)
- `wiki/concepts/biome-selection-and-terrablender.md`
- `wiki/Underground-Biome-Climate.md`
- `plans/archipelago-redesign.md`
- `plans/ore-generation/implementation-plan.md`
- `games/minecraft/investigations/reterraforged/probes/README.md`
- `games/minecraft/tooling/investigate/README.md`
