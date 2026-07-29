# Biome Climate Distribution and Cave-Biome Exposure

## Conclusion

The biome-banding problem is not limited to oceans. In the tested RTF preset, the climate band used
for cave biomes begins about 26 blocks deeper than it does with the corresponding vanilla depth
function. That delay occurs under ordinary land and mountains as well as oceans. Very deep oceans
have an additional problem: if their floor is too close to the world's minimum Y, the column can run
out of vertical space before it ever reaches the cave-biome band.

Removing RTF's `-0.205` climate-depth adjustment corrects the vertical delay, but it is not a valid
fix by itself. RTF also maps the other biome-climate axes differently from vanilla. In particular,
its inland continentalness values cluster at the extreme end of the vanilla range, and its humidity
range does not reach some vanilla and modded biome parameter ranges. With the depth adjustment
removed but those mappings left unchanged, dripstone caves begin almost immediately below most RTF
land.

Current Regions Unexplored cave biomes do generate with RTF, including under mountains. Some are
extremely rare in RTF's source distribution, however, and many selected biome cells do not intersect
an open cave. This can reasonably produce reports that the biomes are absent even though the biome
source technically selected them somewhere.

Strata layering is not a cause of the biome-selection problem. It has a small secondary effect on
later cave carving and on how recognizable some already-selected Regions Unexplored caves are. That
effect should be kept separate from the climate-distribution fix.

A production fix is implemented as `bbd845c` on `qa/biome-climate-mapping` in worktree
`ReTerraForged-biome-climate-qa`, and as message-rewritten equivalent `a5bee8f` on the clean
`fix/biome-climate-mapping` branch. See `refs/branch-map.md` for the branch convention. It corrects
the registered router fields at their Java source instead of patching generated datapack JSON:

- climate depth now uses the same registered, surface-relative RTF depth function as terrain;
- the RTF surface climate remains unchanged, with a depth-based transition from `0.03` to `0.125`;
- underground temperature, humidity, and ridges use vanilla's registered shifted-noise fields;
- underground land continentalness uses a normalized vanilla field but retains RTF's land/ocean
  classification, preventing a second unrelated continent map from selecting ocean biomes on land;
- underground land erosion combines RTF's terrain-selected, pre-river erosion with `0.25` of the
  vanilla erosion field, retaining terrain correlation while restoring continuous variation;
- underground continentalness and erosion transition continuously from coast behavior to inland
  behavior over RTF's configured `beach..inland` continent-edge interval.

The final mapping has no hard land/ocean climate selector. Across 3,958 adjacent pairs that cross
real RTF coasts, underground continentalness had median/q99 deltas of `0.1552/0.4297`, compared with
`0.1553/0.4392` for RTF's surface continentalness at the same pairs. Underground erosion's
median/q99 was `0.0085/0.1032`. The earlier hard-selector control produced q99 coast deltas of
`1.1365` for continentalness and `0.7728` for erosion. The continuous mapping removes that
independent-field discontinuity without suppressing the real coastline transition.

Source-distribution tests show that the fix removes broad dripstone saturation, restores
approximately vanilla cave-biome frequencies at tested depths, preserves surface biome selection,
retains a strong relationship between Deep Dark selection and RTF highland terrain, and works with
both Uplift and Multi continent generators. A dense comparison of `1,050,625` real RTF surface
columns found zero biome changes versus the prior surface tuple, including zero changes in 16,933
samples near `beach` and 14,309 near `inland`.

The initially tested terrain-erosion capture contained a separate implementation-path defect:
standalone lookups used `Heightmap.apply()`, but live chunk generation used `TileGenerator`'s split
`applyTerrain()` / `applyRivers()` / `applyClimate()` sequence. Capturing only in `apply()` left
tile-backed `terrainErosion` at its default zero. The fix now captures at the beginning of
`applyRivers()`, the first shared point after terrain erosion exists and before rivers or climate
overwrite it. A corrected live Regions Unexplored run verified all `312/312` fixed targets against
the biome stored in finished chunks, with zero source/chunk mismatches.

The production Java exporter emitted all 193 files, and a fresh world loaded from that exact output
reproduced the Uplift distribution counts, surface hash, and coast measurements. The controlled
hand-edited pack and exporter graph differ only in eight repeated float-precision leaves derived
from float-backed control points; rounding numeric leaves to six decimals makes their canonical
six-axis graphs identical. The exporter output, not the hand-edited archive, is the authoritative
artifact.

## Source Model

Vanilla chooses an overworld biome from six climate coordinates. The relevant cave-biome parameter
ranges in `OverworldBiomeBuilder.addUndergroundBiomes()` are:

```text
dripstone_caves: depth 0.2..0.9, continentalness 0.8..1.0
lush_caves:      depth 0.2..0.9, humidity 0.7..1.0
deep_dark:       depth point 1.1, erosion -1.0..-0.375
```

The `depth` coordinate is a density-function value, not a direct measurement of blocks below the
local surface. `Climate.Sampler.sample()` computes the registered function at the queried position,
and `MultiNoiseBiomeSource` chooses the nearest registered parameter point.

Mapped vanilla 1.21.1 sources used for this reading are under:

```text
games/minecraft/reference/sources/1.21.1/official/src/net/minecraft/
```

Relevant files are `world/level/biome/Climate.java`, `MultiNoiseBiomeSource.java`,
`OverworldBiomeBuilder.java`, and `world/level/levelgen/NoiseRouterData.java`.

### RTF's climate-only depth adjustment

`PresetNoiseRouterData` registers an RTF depth function built from the vertical gradient and RTF's
terrain-height field. That registered function is used for terrain density at lines 51-53 and 81-82
of the current source. When RTF constructs the `NoiseRouter`, however, the climate `depth` field is
not that function unchanged:

```java
DensityFunctions.add(depth, DensityFunctions.constant(-0.205D))
```

This is at `PresetNoiseRouterData.java:100`. The other terrain-density fields continue to use the
unadjusted registered function. The adjustment therefore moves biome selection without moving the
terrain.

The vertical gradient changes by `1/128` per block. Subtracting `0.205` consequently moves a given
climate-depth value downward by about `0.205 * 128 = 26.24` blocks. That matches the empirical
surface-relative measurements.

The source history also shows that this was not a stable, deliberate part of the current design:

- `7b05c22` introduced `-0.275` while recreating the file in “fixed scaling bugs.”
- `ead93ba` changed it to `-0.205` three days later.
- `b36860d` removed the adjustment two days after that.
- `1033bec`, the later rollback to “improved mountains,” recreated the older `-0.205` version.

History alone does not establish the correct replacement, but it explains why the current shift
needs to be revalidated rather than treated as an intentional compatibility contract.

### The other climate axes do not match vanilla's distributions

RTF does not merely substitute different noises with approximately vanilla distributions:

- `CellSampler.Field.CONTINENT` maps broad inland interiors up to `1.0`. Large areas therefore land
  directly inside vanilla dripstone caves' narrow `0.8..1.0` continentalness target.
- The measured RTF humidity samples ranged from approximately `-0.675` to `0.65`. Vanilla lush caves
  target `0.7..1.0`, while Regions Unexplored's Prismachasm and Redstone Caves explicitly target
  `-1.0..-0.8`.

Nearest-neighbor selection means a biome can still be chosen when an axis does not enter its exact
parameter box, but the distance changes its frequency and which biome wins against neighboring
parameter points.

## Empirical Method

The measurements followed `.agent-docs/games/minecraft/live-worldgen-investigation-howto.md`. They
used the RTF development server, a QA mixin in the investigation worktree, mapped vanilla source,
and fixed-seed scans. No Modrinth instances or unrelated installations were used.

Primary seed:

```text
3216933670
```

The source-distribution scan covered 263,169 columns across a 131,072-block square at 256-block
spacing. It sampled the actual terrain surface and surface-relative offsets of `+16`, `0`, `-16`,
`-32`, `-64`, `-96`, `-128`, and `-192`. Smaller exact-surface controls sampled 66,049 vanilla
columns and 1,089 RTF columns.

The initial Regions Unexplored exposure test generated finished chunks for 307 fixed target
locations. For each selected cave biome it checked that the biome survived the complete chunk
pipeline and measured the center quart cell plus the surrounding `3x3x3` quart-cell neighborhood for
air, fluid, strata material, carver-replaceable material, and Regions Unexplored blocks.

The final candidate used a new fixed cohort of 312 targets: up to 16 targets for every combination
of five RU cave biomes, lower land or mountain terrain, and surface-relative depths `-64` or `-96`
(the rare mountain Inferno `-64` cohort supplied eight). This test compared the source-selected
biome with `LevelChunk.getNoiseBiome()` after full chunk generation, then measured the real center
quart cell and its in-chunk `3x3x3` neighborhood. All target coordinates were placed eight blocks
inside their chunks, so the neighborhood did not wrap across chunk-local biome storage.

Separate final scans measured 263,169 surface columns and 525,312 adjacent spatial pairs for coast
continuity, repeated the broad Uplift and Multi distribution matrices, and compared the prior and
new surface tuples at 1,050,625 columns on an eight-block grid. The last three scans were repeated
in a fresh world created from the Java export, not the hand-edited control.

The Regions Unexplored source used for the compatibility run was branch `21.1`, commit `f5dfe4ee`
(RU 0.6 for Minecraft 1.21.1), built locally with the same development server.

## Results

### The vertical delay is widespread

All 53 vanilla biome candidates were reachable somewhere in the tested RTF biome source. The
non-archipelago preset missed only Mushroom Fields; the archipelago control selected it. The issue
is therefore distribution and placement, not a blanket failure to register vanilla biomes.

The exact-surface depth controls show the delayed cave band:

| Sample               | Average climate depth |
| -------------------- | --------------------: |
| Vanilla surface      |               `0.003` |
| Vanilla surface - 16 |               `0.128` |
| Vanilla surface - 32 |               `0.253` |
| RTF surface          |              `-0.191` |
| RTF surface - 32     |               `0.051` |
| RTF surface - 64     |               `0.192` |

Vanilla cave biomes began appearing around 16-32 blocks below ordinary terrain. In RTF they first
appeared around 64 blocks below ordinary land and mountains. This agrees with the approximately
26-block shift derived from the code; the exact first appearance also depends on the other climate
coordinates and nearest-neighbor competition.

### Bottom headroom is a separate ocean problem

The tested Goldilocks preset used:

```text
worldHeight=384
worldDepth=64
seaLevel=63
oceanDepth=117
```

Its deepest ocean floors approach the minimum build height. Those columns did not recover into the
cave-depth band before the sampled Y coordinate reached the world bottom. A much deeper control
world, with substantial space below comparable low floors, recovered cave-depth values by roughly
`floor - 64`.

This does not explain the ordinary-land delay: that is visible far from the world bottom and follows
the climate-only `-0.205` adjustment. It does mean a complete fix must also define sensible behavior
when configurable terrain consumes nearly all available below-floor space.

### Removing only `-0.205` is not a correct fix

At the same 1,089 exact-surface RTF columns, removing the adjustment changed average surface depth
from `-0.191` to `0.014`, close to vanilla's `0.003`. It therefore fixes the vertical offset it was
expected to fix.

It also exposed the larger axis mismatch. Just 16 blocks below the surface, the counterfactual
selected 345 dripstone and 123 lush-cave columns in the 1,089-column set, approximately half of
which was ocean. In the broad scan, 21,665 of 23,209 highland columns and 56,998 of 57,648 lower
ordinary-land columns selected dripstone caves at that depth.

The result is not a useful vanilla-like distribution. The depth adjustment currently delays and
partly hides the consequences of RTF's saturated inland continentalness; deleting it without
reworking the other climate mappings replaces one problem with another.

### Regions Unexplored

The current RU code adds five relevant underground biomes by three mechanisms:

- Ancient Delta partly replaces Dripstone Caves when humidity is below `-0.4`.
- Bioshroom Caves partly replaces Lush Caves when erosion is above `0.3`.
- Prismachasm and Redstone Caves register direct climate points with depth `0.2..0.9` and humidity
  `-1.0..-0.8`.
- Inferno is force-placed when depth is at least `0.2` and its own density condition passes.

All five were selected in the broad RTF scan, including under mountains, but none appeared at the
surface, `surface - 16`, or `surface - 32`. They first appeared at `surface - 64`, consistent with
the general RTF depth delay. Their frequencies were also skewed by the non-depth axes. For example,
the direct dry-cave points ask for humidity values below the measured RTF minimum.

All 307 generated target chunks retained the source-selected RU biome. The following values are the
share of same-biome quart cells whose sampled `4x4x4` volume contained air:

| RU cave biome   | Land at -64 | Mountain at -64 | Land at -96 | Mountain at -96 |
| --------------- | ----------: | --------------: | ----------: | --------------: |
| Ancient Delta   |       12.8% |           16.4% |       23.9% |           10.2% |
| Bioshroom Caves |        7.1% |            1.5% |       18.9% |            9.7% |
| Inferno         |       13.2% |            6.3% |       27.4% |           30.8% |
| Prismachasm     |       16.4% |           18.1% |       10.3% |           18.4% |
| Redstone Caves  |       37.1% |            4.2% |       22.2% |            8.2% |

The mountain result is biome-specific rather than a universal “RTF mountains reject cave biomes”
rule. Bioshroom and Redstone Caves are particularly unlikely to intersect air in the sampled
mountain bands, while Prismachasm is not. The source rarity and physical exposure problems must
therefore be measured separately.

## Strata Layering

Strata is applied after biome selection and terrain noise, but before the later carver and feature
stages. Vanilla's chunk pipeline is `BIOMES -> NOISE -> SURFACE -> CARVERS -> FEATURES`
(`ChunkPyramid.java:15-38`). RTF adds strata as a surface rule. `SurfaceSystem` only applies a
surface rule when the current block is the default solid block and skips existing air
(`SurfaceSystem.java:123-153`). Consequently:

- strata cannot alter the climate coordinates or which biome the source selects;
- caves already opened by the terrain-noise stage are not filled with strata;
- strata can affect the later carver pass and substrate-sensitive features.

RTF strata can contain dirt, coarse dirt, sand, gravel, clay, stone, granite, andesite, and diorite.
Vanilla carvers only remove blocks in their configured replaceable tag (`WorldCarver.java:206-208`).
The ordinary strata materials are replaceable, but clay is not in vanilla's overworld
carver-replaceable tag. A clay seam can therefore stop part of a later carver.

Regions Unexplored prepends its exposed cave floor/wall surface rules ahead of the underlying RTF
surface rule. Strata does not simply paint over an already-exposed RU cave. Later carvers can expose
new strata surfaces, however, and later RU features can respond differently to the resulting
substrate.

Two paired controls used the same 307 locations as the normal-strata run:

| Run                              | Open same-biome cells | Neighborhood air blocks | RU blocks |
| -------------------------------- | --------------------: | ----------------------: | --------: |
| Normal strata                    |         1,261 / 7,815 |                  38,860 |     5,909 |
| Same strata, clay made carveable |         1,263 / 7,815 |                  38,858 |     5,844 |
| Strata rule removed              |         1,263 / 7,815 |                  38,772 |     6,056 |

Removing strata changed open-cell exposure from 16.136% to 16.161%. Four individual targets changed
their open-cell count, and the net change was two cells. This is too small and too selective to
explain the widespread vertical banding or the large mountain/non-mountain differences.

The block-decoration effect was more visible but still specific. With strata removed, sampled RU
block counts changed as follows:

| RU cave biome   | Normal strata | No strata | Change |
| --------------- | ------------: | --------: | -----: |
| Ancient Delta   |         2,807 |     2,811 |  +0.1% |
| Bioshroom Caves |           363 |       363 |     0% |
| Inferno         |             8 |         8 |     0% |
| Prismachasm     |           393 |       470 | +19.6% |
| Redstone Caves  |         2,338 |     2,404 |  +2.8% |

The Prismachasm percentage is large relative to its low starting block count, but it represents 77
blocks across 64 sampled target neighborhoods. It supports a secondary compatibility/appearance
issue, not a claim that strata prevents the biome from existing.

Ancient Delta also adds vanilla `ore_clay` during the feature stage. Final clay counts in that biome
cannot be attributed to RTF strata without a paired control, so raw clay presence was not used as
evidence of strata interference.

## Legacy Carver Settings

The reported legacy-carver configuration issue is real but separate. A repository-wide search found
`caveCarverProbability`, `deepCaveCarverProbability`, and `ravineCarverProbability` only in
`CaveSettings` and `CaveSettingsPage`: they are serialized, copied, and edited by sliders, but no
configured-carver bootstrap or generation path reads them. `legacyCarverDistribution` additionally
has its translation keys, but no generation consumer. `LegacyCarverHeight` exists and its type is
registered, but no source constructs or uses an instance. `MixinWorldCarver` only prevents replacing
water and does not wire any probability or height setting.

By contrast, `entranceCaveProbability`, `cheeseCaveProbability`, `spaghettiCaveProbability`, and
`noodleCaveProbability` are read directly by `PresetNoiseRouterData` when registering or composing
the noise-cave density functions. Vanilla's biome-specific configured carvers therefore continue to
run with their registered vanilla configurations, while the legacy sliders currently do nothing.

Carvers operate after biome selection. Wiring those settings could change whether a selected cave
biome is physically exposed, but it cannot change the climate tuple or cause the vertical biome
band. No carver workaround belongs in this climate fix; the unused settings should be handled as a
separate configuration/API defect.

## Candidate Mapping

### Why a depth transition is used

Using the registered RTF depth directly fixes the false 26-block delay. Replacing all climate fields
at every Y would unnecessarily relocate surface biomes, so the candidate keeps each RTF surface
field through climate depth `0.03` and linearly transitions to its underground mapping by `0.125`.
An earlier sparse scan across the full 131,072-block test square found one differing surface sample
at floating-point boundary precision. The final dense 8,192-block square found zero differences in
1,050,625 samples, while cave-biome selection changed in the intended underground band.

This is a density-function transition evaluated by the biome source. It is not a biome replacement,
an ocean-only exception, or a generated-datapack override.

### Continentalness

Keeping RTF continentalness underground failed because ordinary RTF land is concentrated at the top
of the vanilla range:

```text
ordinary RTF land samples: 112,058
mean continentalness:      0.867
exactly 1.0:               78.88%
at least 0.8:              91,849
```

That is why deleting `-0.205` alone made dripstone nearly universal. Replacing it with raw vanilla
continentalness also failed: RTF and vanilla use independent continent maps, so vanilla ocean
coordinates selected ocean biomes below RTF land.

The candidate therefore retains the RTF land/ocean classification. On RTF land it normalizes vanilla
continentalness with vanilla's `squeeze` density function, squares the normalized value, and maps it
to `-0.11..1.0`. In RTF oceans it preserves RTF continentalness. The resulting land distribution no
longer has the pathological top-end plateau; only 515 of 111,328 measured samples were exactly
`1.0`.

The rejected intermediate implementation switched between those functions with a hard `range_choice`
at climate continentalness `-0.11`. A spatial scan proved that boundary was discontinuous because
the independent branch fields need not agree: coast-pair continentalness had median/q99 deltas
`0.4137/1.1365`.

The final implementation instead reads RTF's underlying `continentEdge` field and linearly blends
from the coast function at the configured `beach` control point to the inland function at the
configured `inland` point. Those are RTF's actual terrain-topology boundaries, not vanilla climate
labels. Its coast-pair median/q99 deltas are `0.1552/0.4297`, essentially the same as RTF surface
continentalness at those pairs (`0.1553/0.4392`).

### Erosion

Raw RTF erosion cannot be used as the underground climate field because river and climate processing
overwrite it: approximately half the broad samples were exactly `0.445`. Capturing erosion
immediately after terrain selection and before those overrides recovers a terrain-semantic signal.
In the fixed-seed sample, values at or below `-0.11` occurred in `9.90%` of ordinary lower land and
`57.16%` of highland terrain.

The capture must occur in `Heightmap.applyRivers()`, not only in the convenience `Heightmap.apply()`
method. `TileGenerator.generate()` and `generateZoomed()` bypass `apply()` and invoke the three
stages separately. Vanilla `NoiseBasedChunkGenerator.doCreateBiomes()` fills chunks through
`NoiseChunk.cachedClimateSampler()`, while RTF's `MixinNoiseChunk.wrapNew()` replaces cell samplers
there with tile-backed `CacheChunk` functions. The original capture location therefore made
standalone source scans correct while live chunk cells retained the default zero. Moving the
assignment to the start of `applyRivers()` covers both call paths and still precedes
`Rivermap.apply()` and the climate overrides. `Cell.copyFrom()` also copies the captured field, so
pooled and cached cells preserve it.

That source still contains terrain-category plateaus, so the candidate adds `0.25` times vanilla
erosion as continuous local variation. The coefficient was tested rather than selected visually:

| Mapping                       | Erosion <= -0.375 | Erosion >= 0.3 |
| ----------------------------- | ----------------: | -------------: |
| Vanilla                       |            11.18% |         17.63% |
| Candidate, coefficient `0.25` |             9.16% |         19.36% |
| Control, coefficient `0.50`   |             9.55% |         26.31% |

Vanilla erosion alone was rejected even though its aggregate tails were usable. At depth `-144`, it
selected Deep Dark in `20.92%` of lower land and `21.44%` of highlands, demonstrating that the field
was unrelated to RTF terrain. The final Uplift candidate selected it in `4.12%` of lower land and
`48.86%` of highlands. A height-only replacement was also rejected because the measured lower-land
and highland height distributions overlap too much to encode the terrain relationship reliably.

### Measured selection

The principal comparison below uses ordinary RTF land. Vanilla has a different land footprint, so
the percentages are the meaningful cross-generator comparison rather than raw counts.

| Mapping / depth         | Dripstone |   Lush |
| ----------------------- | --------: | -----: |
| Vanilla, surface - 16   |     4.11% |  0.29% |
| Candidate, surface - 16 |     3.12% |  0.43% |
| Vanilla, surface - 32   |    10.30% |  2.07% |
| Candidate, surface - 32 |     8.05% |  2.49% |
| Vanilla, surface - 64   |    30.32% | 14.58% |
| Candidate, surface - 64 |    25.51% | 14.56% |

The independent Multi continent-generator run produced `8.29%` dripstone and `2.52%` lush at
`surface - 32`, then `25.59%` and `14.67%` at `surface - 64`. At `surface - 144`, Deep Dark selected
`49.10%` of valid highland samples and `3.48%` of lower land. Uplift selected `48.86%` and `4.12%`
respectively. This rules out a mapping accidentally fitted only to Uplift's cell geometry.

No tested ocean-floor sample selected dripstone at `floor - 32` or `floor - 64`. For the deepest
ocean-floor cohort, 129,105 of 151,111 `floor - 64` positions and every `floor - 128` position were
below minimum Y. That is a physical lack of world height, not a remaining climate-axis error, and
must not be hidden with a biome-source workaround.

A live follow-up conversation (2026-07-27) found that the ocean-floor headroom problem is one
instance of a more general structural issue: only the `depth` climate axis varies with Y, so once a
column passes every registered biome's depth window except the deepest (`deep_dark`), nothing
changes for the rest of that column to bedrock — invisible at vanilla's fixed world depth, but able
to produce either an unreachable deep_dark (shallow configured worlds) or a disproportionately tall
single-biome zone (very deep configured worlds) under RTF's configurable `worldDepth`. A full design
for addressing this — more depth bands, sizing them by world depth and the `Biome Size` setting,
staying compatible with biome-adding mods, and gracefully varying which band gets dropped where the
configured world is too shallow to fit everything — is written up in
`dynamic-underground-biome-banding-plan.md`. That follow-up is now implemented and live-path
validated; its document contains the final algorithm, commits, retained logs, and remaining visual
checks.

### Regions Unexplored compatibility

The candidate was tested against the exact Regions Unexplored source at commit `f5dfe4ee`. Its five
underground biomes were all reachable below ordinary land and highlands, and none was selected at
the surface. At `surface - 64`, the broad land scan selected:

| Biome           | All land | Highlands |
| --------------- | -------: | --------: |
| Ancient Delta   |      481 |       113 |
| Bioshroom Caves |    2,928 |       196 |
| Prismachasm     |    5,121 |       523 |
| Redstone Caves  |    2,299 |     1,013 |
| Inferno         |       63 |        10 |

The locally built RU source confirmed the mechanisms behind those results: Ancient Delta and
Bioshroom replace vanilla cave-biome targets conditionally; Prismachasm and Redstone register direct
dry underground points; Inferno applies its own density condition after requiring underground depth.
The direct dry points being reachable demonstrates that replacing the restricted RTF humidity
distribution underground corrected a real compatibility defect.

The corrected finished-chunk run then generated 312 fixed targets across all five biomes, both lower
land and mountains, and both `surface - 64` and `surface - 96`. All `312/312` source-selected biomes
matched `LevelChunk.getNoiseBiome()` after generation. Every one of the 20 cohorts contained open
same-biome cells in its sampled neighborhoods. Open shares ranged from `2.0%` for lower-land
Prismachasm at `-96` to `30.8%` for mountain Inferno at `-96`; this variation confirms that physical
cave exposure remains a biome/terrain-specific visibility factor, not a climate registration
failure.

### Exporter verification

The change lives in `PresetNoiseRouterData`, `CellSampler.Field`, and the shared cell-generation
path, so newly exported presets carry the fix without hand-editing a datapack. The hand-edited pack
was useful as a controlled A/B input, but it is not the deliverable.

A QA-only server trigger invoked the same `Datapacks.makePreset()` path as the preset UI. Starting
from the canonical Goldilocks preset, it emitted all 193 expected files. Canonical comparison of the
six router climate axes found the same graph structure and exactly eight differing scalar leaves:
four repeated occurrences each of the `beach` offset and reciprocal `beach..inland` width. The
hand-edited control used decimal values `-0.327` and `5.714285714285714`; the Java producer
correctly serialized the underlying floats as `-0.3269999921321869` and `5.714286298168008`.
Rounding numeric leaves to six decimals gives both graphs the same SHA-256,
`46a8d635853d1fa12f0e677b095e31f12830d48b8af03a3d2cdda8a5fe6dd1d8`.

The retained authoritative export is:

```text
fabric/run/qa-coast-edge-blend-production-exported-v2.zip
sha256 936d32025e0fcaf1434e25ec2a11fa20d74d5ad22378090a220844e8e5f2ae37
```

A fresh world created from that archive reproduced the distribution counts and Uplift surface hash
`49529e8c2e730ba1`. The coast-crossing median/q99 values were identical to the controlled run; a few
within-land erosion quantiles moved by at most `0.0017`, the measurable effect of using the exact
float-backed control points rather than hand-rounded JSON.

### Surface identity

The final exporter-produced world compared the new target tuple with the exact prior surface tuple
at 1,050,625 columns over an `8192 x 8192` area at eight-block spacing. The prior tuple used the
same fully populated RTF cell fields and the historical climate-only `depth - 0.205`; the candidate
tuple came from the live router sampler. All candidate surface depths were at or below the `0.03`
transition start, and all `1,050,625` biome selections matched. The boundary cohorts also had zero
mismatches: 16,933 samples within `0.01` of `beach` and 14,309 within `0.01` of `inland`.

### Generated Ancient City control

A fresh candidate world at seed `3216933670` located the nearest Ancient City at `[1392, ~, 1712]`.
After force-generating the surrounding 256 chunks, temporary QA instrumentation observed two valid
Ancient City `StructureStart` instances after `ChunkGenerator.applyBiomeDecoration()`. The located
one had bounding box `(1268,-64,1589)` through `(1510,-10,1833)`; the second had bounding box
`(1415,-64,1879)` through `(1657,-10,2110)`.

This proves that candidate Deep Dark placement can pass the real structure-placement and generation
pipeline; it is not inferred from source-biome frequency or `/locate` alone. The temporary mixin was
removed after the run. Retained log:

```text
fabric/run/qa-production-climate-ancient-city-results.log
sha256 0a786a0707dac5b10b24e70ecc6fcb81ebfa7a9600ca01447c0bba3970022f32
```

## Remaining Work

No climate-mapping validation gate from this investigation remains open. The continuous mapping,
both continent generators, terrain-correlated Deep Dark selection, dense surface identity, Regions
Unexplored finished chunks, Java export, fresh-world reload, and production build are all recorded.

The following are separate follow-ups, not missing pieces of the root fix:

1. Exercise another Minecraft 1.21.1 TerraBlender biome injector when an exact compatible source and
   build are available locally. RU already exercises replacement, direct parameter-point, and forced
   underground injection mechanisms, so this is broader compatibility coverage rather than evidence
   of an unresolved RTF mapping defect.
2. Decide how presets whose ocean floor approaches minimum Y should expose underground biomes. The
   measured failure there is absent vertical headroom; changing the climate mapping cannot create
   blocks below the dimension boundary.
3. Either wire or remove the unused legacy carver settings in a separate change. That work can
   affect cave exposure, but it must not be presented as a biome-distribution fix.
4. Keep strata/carver and feature-substrate compatibility separate unless a paired generated-chunk
   control demonstrates a candidate-specific regression.

## Raw Measurement Artifacts

The original logs were recovered from the retired first QA worktree and copied into the active
candidate worktree's `fabric/run` directory:

```text
qa-biome-baseline-results.log
qa-biome-archipelago-results.log
qa-biome-verydeep-results.log
qa-biome-vanilla-results.log
qa-biome-rtf-exact-final-results.log
qa-biome-depth-offset-counterfactual-results.log
qa-biome-regions-unexplored-results.log
qa-biome-ru-exposure-strata-results.log
qa-biome-ru-exposure-clay-carvable-results.log
qa-biome-ru-exposure-no-strata-results.log
```

Candidate logs are in `ReTerraForged-biome-climate-qa/fabric/run`:

```text
qa-terrain-source-erosion-results.log
qa-terrain-height-cohorts-results.log
qa-climate-erosion-k025-results.log
qa-climate-erosion-k050-results.log
qa-vanilla-erosion-tails-results.log
qa-climate-erosion-k025-multi-results.log
qa-production-export-source-results.log
qa-production-climate-roundtrip-results.log
qa-production-climate-regions-unexplored-results.log
qa-production-climate-ancient-city-results.log
qa-coast-continuity-hard-results.log
qa-coast-continuity-edge-blend-results.log
qa-hard-selector-distribution-control-results.log
qa-coast-edge-blend-distribution-results.log
qa-coast-edge-blend-multi-v2-results.log
qa-coast-edge-blend-ru-source-results.log
qa-coast-edge-blend-ru-live-exposure-results.log
qa-coast-edge-blend-exporter-results.log
qa-coast-edge-blend-production-roundtrip-v2-results.log
```

Final artifact checksums:

```text
qa-coast-edge-blend-ru-live-exposure-results.log
  b9c394cccc417f9276f26abf2c7999cd34fac22e1d8b925299676891ba5ec89f
qa-coast-edge-blend-production-exported-v2.zip
  936d32025e0fcaf1434e25ec2a11fa20d74d5ad22378090a220844e8e5f2ae37
qa-coast-edge-blend-exporter-results.log
  3a539938cf044764e8c1918b19b1c09b303a3d76f573417af53b6fbb7915adc0
qa-coast-edge-blend-production-roundtrip-v2-results.log
  9d7d42901ec58b4e1453c6d72558f5b449fd94e8b0b20a63962ef5444fc42052
```
