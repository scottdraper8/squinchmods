# Underground Biome Climate and Banding — Retrospective

The production implementation is complete on `fix/biome-climate-mapping` and proposed upstream in
[PR #152](https://github.com/ETcodehome/ReTerraForged/pull/152). This document describes the
problem, final design, compatibility boundaries, and evidence worth preserving. It is not an
implementation log.

## What was wrong

RTF exposed three related problems when world depth, cave-biome distribution, and Biome Size were
tested together.

### Underground climate did not match the terrain or biome registrations

Minecraft selects an overworld biome from six climate coordinates. RTF supplied its own fields for
those coordinates, but the underground values had several distribution problems:

- Climate depth applied an extra `-0.205` adjustment that terrain density did not use. Since the
  depth gradient changes by `1/128` per block, cave-biome selection started about 26 blocks deeper
  than the actual terrain-relative depth implied.
- RTF inland continentalness clustered at the top of the vanilla range. About 91% of sampled land
  reached Dripstone Caves' `0.8..1.0` continentalness target, so removing the depth delay alone made
  Dripstone Caves nearly universal below land.
- RTF humidity did not reach parts of the vanilla/modded registration range. This reduced Lush Caves
  and conventionally registered dry cave biomes such as Regions Unexplored's Prismachasm and
  Redstone Caves.
- RTF erosion was overwritten by later river and climate passes. Using the final cell value lost the
  terrain relationship needed for Deep Dark to favor highland terrain.

The result was not merely an ocean-floor issue. The delayed cave band appeared below ordinary land
and mountains, while extremely low ocean floors added a separate physical-headroom constraint.

### Vanilla's terminal depth stage does not scale to configurable worlds

Only the `depth` climate coordinate varies with Y. Temperature, humidity, continentalness, erosion,
and weirdness are effectively 2D fields within a column.

Vanilla registers Dripstone and Lush Caves across depth `0.2..0.9`, then Deep Dark at the single
depth target `1.1`. Nothing is registered deeper. In a vanilla-height world the terminal region is
short enough to be unobtrusive. With RTF's configurable `worldDepth`, one Deep Dark selection could
continue for hundreds of blocks to bedrock. In a very shallow world the inverse occurred: terrain
could run out of vertical room before Deep Dark was reachable.

### Biome Size did not scale underground climate

RTF's Biome Size setting scaled surface climate, but underground shifted-noise fields used a fixed
frequency of `0.25`. Large surface biomes could therefore sit above cave biomes that retained
vanilla's much finer horizontal scale.

## Final design

The solution has two layers. The climate mapping first produces trustworthy six-axis inputs; the
banding layer then decides how registered underground candidates occupy the available depth.

### Corrected climate mapping

- Climate depth uses the same registered, surface-relative RTF depth function used by terrain. The
  climate-only `-0.205` adjustment is gone.
- RTF surface fields remain unchanged through climate depth `0.03`; underground mappings fade in
  continuously by depth `0.125`. This avoids relocating surface biomes.
- Underground temperature, humidity, and ridges use vanilla's registered shifted-noise fields.
- Continentalness preserves RTF's land/ocean classification. RTF oceans retain their own field; land
  uses a normalized vanilla-shaped field. The two representations blend across RTF's configured
  `beach..inland` continent-edge interval rather than switching at a hard selector.
- Erosion combines RTF's pre-river terrain erosion with `0.25` of vanilla erosion. This retains the
  terrain relationship needed by Deep Dark while restoring continuous local variation.
- Pre-river erosion is captured at the start of `Heightmap.applyRivers()`, which is shared by direct
  and tile-backed generation and occurs before rivers/climate overwrite the value.

The corrected mapping changes underground selection without creating a second independent continent
map or a coastline climate seam.

### Dynamic underground bands

`UndergroundBiomeBanding` discovers compatible cave-biome entries from each biome parameter list.
The recognized signature is deliberately conservative: a depth span of `0.2..0.9` or point `1.1`,
with weirdness left at `FULL_RANGE`. Registrations that do not follow this convention remain
untouched.

The final layout:

- preserves the original parameter list for every target below climate depth `1.1`;
- spans new bands from depth `1.1` through the usable configured depth
  `(worldDepth + min(worldHeight, 256)) / 128`;
- derives band count from candidate count, usable vertical space, and Biome Size, capped at 32;
- partitions weirdness `[-1, 1]` into one regime per candidate and rotates candidate order across
  bands, so shallow columns can omit a band without making one biome globally unreachable; and
- adds full-climate fallback entries after the transition band so one constrained candidate cannot
  saturate the rest of a deep column.

No new biome content is added. The algorithm redistributes compatible vanilla and modded cave biomes
that are already registered.

### Underground horizontal scale

Underground shifted-noise frequency is:

```text
0.25 * 225 / biomeSize
```

This is identical to the prior value at the default `Biome Size=225`. Smaller settings create finer
horizontal and vertical regions; larger settings create broader regions.

### Biome-source integration

- Plain Fabric builds a banded list beside the original `MultiNoiseBiomeSource` and uses it only
  beyond the `1.1` threshold.
- TerraBlender builds a banded list for each populated region, preserves TerraBlender's positional
  region choice, and then selects from the corresponding regional list.
- Actual chunk biome palettes are filled through `NoiseChunk.cachedClimateSampler()`. The RTF preset
  is propagated to that cached sampler; attaching it only to `RandomState.sampler()` is
  insufficient.

The last point is a required production invariant. A standalone `BiomeSource` query can look correct
while generated chunks remain unchanged if it does not exercise the cached chunk sampler.

## Compatibility boundaries

- Vanilla Dripstone Caves, Lush Caves, and Deep Dark participate.
- Convention-following modded entries participate automatically. Regions Unexplored and YUNG's Cave
  Biomes were exercised directly.
- TerraBlender region ownership is preserved; the default region is not substituted for a modded
  region below ground.
- Custom placement systems that do not use the recognized vanilla depth/weirdness signature are left
  alone. Regions Unexplored's Inferno placement is an example. This is the safe failure mode, not a
  promise to reinterpret arbitrary mod registrations.
- Existing chunks are not retrofitted. Their stored biome palettes and already-placed features
  remain unchanged.

## Evidence

### Surface identity and climate distribution

- A dense old-versus-new comparison covered 1,050,625 RTF surface columns, including 31,242 samples
  near configured coast boundaries, with zero surface-biome changes.
- Corrected cave-biome frequencies were close to vanilla at matched terrain-relative depths:
  Dripstone/Lush measured `3.12%/0.43%` at surface-minus-16, `8.05%/2.49%` at minus-32, and
  `25.51%/14.56%` at minus-64.
- Deep Dark retained a terrain relationship. At surface-minus-144, Uplift selected it in `48.86%` of
  highland samples and `4.12%` of lower land; Multi reproduced the same split at `49.10%/3.48%`.
- Across 3,958 real coast-crossing pairs, corrected underground continentalness had median/q99
  deltas `0.1552/0.4297`, effectively matching RTF's surface continentalness (`0.1553/0.4392`). The
  rejected hard-selector control measured `0.4137/1.1365`.

### Band sizing

All cases used seed `3216933670` and live per-preset biome sources.

| Case                           | Candidates / bands | Durable result                                                                                   |
| ------------------------------ | -----------------: | ------------------------------------------------------------------------------------------------ |
| Very deep, size 225            |              3 / 6 | Candidate averages were about 107-117 blocks; no terminal 576/752-block saturation remained.     |
| Goldilocks                     |              3 / 3 | Deep Dark remained reachable where terrain supplied headroom without appearing in shallow space. |
| `worldDepth=16` mountain       |              3 / 3 | Deep Dark remained reachable below mountains instead of being globally lost.                     |
| Very deep, size 50             |             3 / 13 | All candidate maxima were 112 blocks; horizontal and vertical regions became measurably finer.   |
| Very deep, size 900            |              3 / 3 | Candidate averages grew to 158-257 blocks and horizontal neighbor agreement increased.           |
| Very deep + Regions Unexplored |             5 / 10 | Compatible modded candidates were discovered and distributed with the vanilla candidates.        |

### Finished chunks

The authoritative comparison generated chunks `(80,100)..(95,115)`, then read the biome palettes
stored in each `LevelChunk`:

```text
finished columns compared:               4,096
columns with different vertical profile: 4,096
columns with shared-air divergence:        165
shared open biome cells differing:          240
```

The scanner processed 4,096 columns and about 792,000 stored biome cells in 170-190 ms. Generating
the 256 chunks was the expensive part.

The final scanner is the model for future biome-divergence searches:

1. Generate and forceload the same chunk window for each jar.
2. Run the comparison on the server thread.
3. Read `LevelChunk.getNoiseBiome()` rather than predicting from a cold biome-source query.
4. Compress each vertical column into biome runs.
5. Diff the runs, retain cells that are open in both worlds, and RCON-check only those candidates.

### Mod compatibility

- A corrected Regions Unexplored run generated 312 fixed targets spanning all five cave biomes,
  lower land and mountains, and two depths. All `312/312` source-selected targets matched the biome
  stored in the finished chunk.
- TerraBlender 4.1 completed positional lookups with no region-index fallbacks.
- TerraBlender plus YUNG's Cave Biomes activated two independently populated regions. Both regions'
  underground biomes participated with comparable vertical run lengths, and selection remained
  unchanged below climate depth `1.1`.
- Both Fabric and NeoForge production builds pass.

## Screenshot reproduction

Use the shared QA seed and preset:

```text
seed:   3216933670
preset: qa/presets/very-deep.zip
```

Create both worlds fresh and use spectator mode. The current preset explicitly sets
`lavaLevel=-575`. The original air/block-context measurements used the same preset before that field
was made explicit, when it decoded to `-54`. Lava level does not feed biome climate, so the biome
profiles remain applicable; re-check exact nearby decoration counts in newly generated screenshot
worlds.

| Coordinate       | Unfixed   | Fixed           | What it demonstrates                                                     |
| ---------------- | --------- | --------------- | ------------------------------------------------------------------------ |
| `1454 -50 1650`  | Savanna   | Dripstone Caves | Correct underground climate selection and matching dripstone decoration. |
| `1362 -82 1662`  | Savanna   | Deep Dark       | Stored-biome correction in open cave space; keep F3 visible.             |
| `1522 -376 1654` | Deep Dark | Dripstone Caves | A deep Dripstone band replacing terminal Deep Dark saturation.           |
| `1422 -394 1838` | Deep Dark | Lush Caves      | The clearest complete vertical-banding comparison.                       |

At the last coordinate, the unfixed column is Deep Dark from `Y=-217..-624`. The fixed column is:

```text
savanna          116..153
dripstone caves    8..115
savanna          -68..7
deep dark       -256..-69
dripstone caves -380..-257
lush caves      -504..-381
deep dark       -624..-505
```

## Separate issues

These findings were tested while diagnosing biome distribution but are not part of this fix:

- **Physical headroom:** an ocean floor near minimum Y may have no blocks available beneath it.
  Climate mapping cannot create space outside the dimension.
- **Strata:** removing strata changed open same-biome exposure by only two of 7,815 sampled cells.
  It can affect later carvers and decoration, but it does not select biomes.
- **Legacy carver controls:** `caveCarverProbability`, `deepCaveCarverProbability`,
  `ravineCarverProbability`, `legacyCarverDistribution`, and `LegacyCarverHeight` have no generation
  consumer. Wiring them could alter cave exposure, not climate selection.

## Rejected approaches

- Do not remove only the `-0.205` depth adjustment. That exposes the continentalness saturation and
  produces near-universal Dripstone Caves.
- Do not use a hard land/ocean climate selector. Independent fields disagree at the boundary and
  create a seam; use the configured coast-to-inland blend.
- Do not replace erosion with vanilla erosion alone. Aggregate frequencies look reasonable, but Deep
  Dark loses its relationship to RTF terrain.
- Do not stretch the shared depth density function to create bands. Terrain and biome climate share
  it; changing it would alter terrain density and external datapack behavior.
- Do not trust cold/background biome-source scans for screenshot coordinates. Read finished chunk
  palettes on the server thread.
- Do not treat standalone-source validation as proof that a change reaches chunk generation.

## Current status

The production implementation is complete and the original reported behavior has reproducible
before/after evidence. No climate-mapping or banding implementation task remains.

Further modded finished-chunk matrices, more Biome Size extremes, or a dedicated root-mapping-only
visual pair would add coverage, but they are not blockers and should not be treated as unfinished
parts of the fix.
