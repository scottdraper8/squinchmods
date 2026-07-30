# Dynamic Cave Feature Placement

## Status

Source audit, production implementation, and live validation completed on 2026-07-29. The generic
density-preserving fix is implemented and validated on NeoForge and Fabric with Biomes O' Plenty
present.

Issue [ETcodehome/ReTerraForged#133](https://github.com/ETcodehome/ReTerraForged/issues/133) shows
`biomesoplenty:spider_nest` selected around block `-6700 505 14243`, but without its characteristic
decoration. PR #152 does not fix this: biome selection and placed-feature positioning are separate
generation stages.

| Purpose                   | Branch                               | Worktree                                              |
| ------------------------- | ------------------------------------ | ----------------------------------------------------- |
| Production                | `fix/dynamic-cave-feature-placement` | `games/minecraft/mods/ReTerraForged-cave-feature-fix` |
| Instrumentation/prototype | `qa/dynamic-cave-feature-placement`  | `games/minecraft/mods/ReTerraForged-cave-feature-qa`  |

Both branches started from upstream `1.21.1` commit `9e445dd5ad5c27cda5f0aa55729b06d29d2eefc8`.
Production commits are:

- `80d56a9 Scale canonical cave feature placement with world height`
- `e6b0964 Make extended height sampling position-deterministic`

The QA branch applies the same shipping implementation in commits `3a81e57` and `f623a06`. Its
separate commit `5b2e7d2` contains intentionally non-production counters, block-write tracking, and
the finished force-loaded-chunk scanner.

## Conclusion

This is a vanilla placement assumption exposed by RTF's extended world dimensions, not an RTF
biome-selection failure.

Minecraft does not find every volume belonging to a cave biome and decorate that volume. A placed
feature creates a fixed number of candidate origins, placement modifiers choose their positions,
surface/environment filters reject unsuitable positions, and `BiomeFilter` finally checks whether
the biome at a surviving origin owns the feature.

Vanilla's shared `PlacementUtils.RANGE_BOTTOM_TO_MAX_TERRAIN_HEIGHT` is:

```java
HeightRangePlacement.uniform(VerticalAnchor.bottom(), VerticalAnchor.absolute(256))
```

The bottom is relative to the active dimension. The top is the literal coordinate 256. Thus:

- extending `worldHeight` can create valid cave-biome cells that can never receive an origin above
  256;
- extending `worldDepth` does make low caves reachable, but spreads the same attempt count over a
  much larger range and dilutes decoration density;
- the cap constrains candidate origins, not every block a configured feature writes, so offsets and
  multi-block features can spill a short distance beyond 256;
- changing only `absolute(256)` to `top()` fixes reach but worsens density dilution.

The recommended solution is to recognize the exact shared placement semantics generically and
preserve the vanilla density of one origin per 321 Y levels. Keep one sample in the reference
`-64..256` band, then add stratified samples to low and high extensions. A partial extension emits
one sample with probability `extensionLength / 321`; each full 321-level extension emits one.

This neither knows nor cares whether a registered feature came from vanilla, BOP, or another mod.

## Exact scope: caves, ores, and other decoration

The cap is applied to placed features that include that height modifier. It is not a global worldgen
cap and it is not tied to a Java “cave feature” category.

Vanilla 1.21.1 has fourteen cave placed features using it:

- dripstone cluster, large dripstone, and pointed dripstone;
- underwater magma and glow lichen;
- rooted azalea, cave vines, lush vegetation, lush clay, lush ceiling vegetation, spore blossom, and
  classic vines;
- Deep Dark sculk patch and sculk vein.

The only vanilla non-cave consumer is `minecraft:ore_clay`. Ordinary mineral ores do not use this
shared range. Their bounds are independent: for example, upper iron reaches absolute 384, emerald
reaches 480, coal has a top-relative distribution, and the diamond distributions are mostly
bottom-relative. Seeing ores in high mountains is therefore expected and does not contradict this
bug.

BOP 21.1.0.14 uses the shared range for all thirteen Glowing Grotto and Spider Nest placed features
in `BOPCavePlacements.java:57-69`. Five of those are the Spider Nest features measured live: corner
cobwebs, hanging cobwebs, spider eggs, stringy cobweb, and webbing.

A semantic transformation of this exact shared range will also scale `ore_clay` and any modded
feature that deliberately chose the same semantics. Excluding `ore_clay` while retaining a BOP
feature such as `webbing` cannot be inferred from modifier shape alone: both can reduce to count,
horizontal spread, the shared range, and a biome filter. A hardcoded exception would violate the
compatibility goal. If exclusion is desired as policy, use an optional opt-out placed-feature tag;
do not turn ordinary compatibility into an allowlist.

## Live QA method

All runs used seed `3216933670`, RTF's headless dev-server tooling, `max-tick-time=-1`, and BOP
21.1.0.14 with matching GlitchCore 2.1.0.0 and TerraBlender 4.1.0.0.

The generic QA instrumentation:

1. recognizes a placed feature whose modifier list contains `UniformHeight(bottom, absolute(256))`,
   without checking its registry namespace or ID;
2. records emitted height origins;
3. records `BiomeFilter` passes with the runtime biome;
4. attributes successful `WorldGenRegion.setBlock` writes to the active feature;
5. scans only fully promoted `LevelChunk`s selected with `/forceload`;
6. reports air and enclosed-air samples by runtime biome in deep (`Y < -64`), reference
   (`-64..256`), and high (`Y > 256`) bands.

The scanner discovered test locations rather than relying on issue #133's unavailable seed.

## Baseline evidence

### Default control

- Loader: NeoForge
- World: no exported RTF preset; build range `-64..319`
- Forced region: blocks `-128 -96` through `127 159` (256 chunks)
- Spider Nest: 6,367 enclosed-air quart samples in the reference band
- Every BOP origin range: exactly `-64..256`
- Highest BOP write in this region: 167

This establishes normal BOP decoration and confirms that the QA probe does not manufacture the cap.

### Tall RTF world: direct reproduction

- Loader: NeoForge
- Preset: `goldilocks.zip`; build range `-64..383`
- Forced region: blocks `-54656 65152` through `-54401 65407` (256 chunks)
- Discovered Spider Nest enclosed air above 256: 65 samples
- Example positions: `-54534 270 65234`, `-54534 270 65238`, `-54530 266 65238`

Despite real Spider Nest cave space above 256:

| BOP feature     | Candidate origins | Origin range | Highest write |
| --------------- | ----------------: | ------------ | ------------: |
| Corner cobwebs  |            45,300 | `-64..256`   |           238 |
| Hanging cobwebs |           181,200 | `-64..256`   |           236 |
| Spider eggs     |            31,710 | `-64..256`   |           212 |
| Stringy cobweb  |           226,500 | `-64..256`   |           225 |
| Webbing         |            18,120 | `-64..256`   |           261 |

No origin or biome-filter pass occurred above 256. Webbing's 20 writes above 256 ended at 261 and
were spillover from an origin at or below 256. They did not decorate the cave at 266–270. Vanilla
glow lichen and the measured dripstone features had the same capped origin range.

### Very-deep RTF world

- Loader: NeoForge
- Preset: `very-deep.zip`; build range `-624..383`
- Forced region: blocks `1328 1312` through `1583 1567` (256 chunks)
- Deep Dark: 6,368 enclosed-air samples below -64

The lower anchor behaved dynamically:

- canonical origins covered `-624..256`;
- Deep Dark sculk-patch biome passes covered `-624..-184`, with writes down to -603;
- sculk-vein passes covered `-624..-186`, with writes down to -597;
- glow lichen wrote down to -575;
- underwater magma wrote down to -438.

The fixed counts were diluted across 881 Y levels. For example, BOP hanging cobwebs generated 82,000
origins: 52,063 below -64 and 29,937 in `-64..256`. Spider Nest did not occupy the deep band in this
particular region, so those deep attempts could not pass its biome filter. This is why merely making
the lower anchor dynamic is insufficient.

## Implemented design and results

The production implementation is gated to an RTF Overworld and transforms only the exact canonical
`bottom..absolute(256)` uniform range. It does not mutate frozen registries or inspect biome,
feature, or mod IDs.

For an RTF world spanning `minY..maxY`, it emits:

1. one uniform origin in `-64..256`;
2. one origin for every complete 321-level band below -64 or above 256;
3. a probabilistic origin for each partial extension, with probability `partialBandLength / 321`.

Expected origin density is therefore constant at `1/321` per Y level. Sampling is stratified so the
existing band is not starved by a large deep or high extension.

### Tall-world result

In the same high Spider Nest, the NeoForge prototype produced:

| BOP feature     | Highest high biome pass | Highest high write |
| --------------- | ----------------------: | -----------------: |
| Corner cobwebs  |                     290 |                291 |
| Hanging cobwebs |                     284 |                284 |
| Spider eggs     |                     267 |                267 |
| Stringy cobweb  |                     269 |                273 |
| Webbing         |                     303 |                304 |

Thus all five independently reached and decorated runtime BOP cave-biome cells above 256. Vanilla
glow lichen also evaluated above 256.

The Fabric run against the same seed, preset, region, BOP version, and common-code implementation
found the same high Spider Nest and produced high writes for all five features (up to 292 in that
sample). This validates the discovery and interception mechanism on both loaders.

### Deep-density result

In the same very-deep NeoForge region:

| Feature             | Reference origins | Deep origins | High origins |
| ------------------- | ----------------: | -----------: | -----------: |
| BOP hanging cobwebs |            81,600 |      142,280 |       32,276 |
| BOP stringy cobweb  |           102,000 |      177,976 |       40,378 |
| BOP webbing         |             8,160 |       14,244 |        3,221 |

For the 560-level deep extension, the expected multiplier is `560/321 = 1.7445`; hanging cobwebs
measured `142280/81600 = 1.7436`. For the 127-level high extension, the expectation is
`127/321 = 0.3956`; it measured `32276/81600 = 0.3955`.

Deep Dark sculk-patch passes rose from 49,407 to 135,443 and writes from 563,260 to 1,427,265 while
retaining a minimum write near -603. This is increased total work proportional to the additional
world volume, not increased density within a fixed-height band.

## Production implementation

The shipping implementation has the following scope and compatibility guards:

- Keep the exact structural match:
  `HeightRangePlacement -> UniformHeight(above_bottom:0, absolute:256)`.
- Require a registered top-level placed feature and an RTF-generated Overworld context.
- Leave every other height provider and modifier pipeline unchanged.
- Preserve the vanilla reference-band candidate on Minecraft's existing random stream.
- Derive extension-band decisions and positions from world seed, registered feature ID, and
  candidate position. The complete result list is created before downstream configured-feature
  execution, so a mod feature's internal random consumption cannot affect later extension decisions
  and the added candidates do not perturb Minecraft's shared random stream.
- Treat worlds whose entire generation range is within the reference band as an exact no-op.
- Leave unusual dimensions that clip any part of the reference band unchanged rather than guessing
  at new semantics.
- Do not mutate registered `PlacedFeature` instances. Adapt positions at evaluation time.
- Document that existing extended-height/depth chunks are not bit-for-bit generation compatible:
  newly reachable features necessarily change decoration.

The semantic unit should be “the canonical bottom-to-max-terrain range,” not “known cave feature.”
That is what provides mod compatibility without introspecting every BOP or future biome-mod
registration.

## Final production validation

Both production loaders build successfully:

```text
./gradlew :fabric:build :neoforge:build
```

The QA branch tests the actual production classes rather than a duplicate prototype.

### Tall NeoForge

The final code generated the same 256-chunk Goldilocks region in about 17 seconds. All five Spider
Nest feature families passed their biome filter above 256 and wrote decoration above 256:

| BOP feature     | Highest high pass | Highest high write |
| --------------- | ----------------: | -----------------: |
| Corner cobwebs  |               285 |                285 |
| Hanging cobwebs |               288 |                288 |
| Spider eggs     |               268 |                268 |
| Stringy cobweb  |               298 |                273 |
| Webbing         |               302 |                296 |

The 127-level high extension received the expected `127/321` additional candidate density. A fresh
repeat generated the same reference-band candidate counts and statistically identical extension
counts. Exact aggregate write counts are not a valid cross-run equality oracle because neighboring
chunks are generated concurrently; the implementation's extension decision itself is pure for a
given world seed, feature ID, and candidate position and is isolated from configured feature random
consumption.

### Very-deep NeoForge

The final code generated the same 256-chunk `-624..383` region in 29.36 seconds. Representative
counts were:

| Feature             | Deep origins | Reference origins | High origins |
| ------------------- | -----------: | ----------------: | -----------: |
| BOP hanging cobwebs |      141,431 |            81,200 |       31,964 |
| BOP stringy cobweb  |      177,070 |           101,500 |       40,126 |
| BOP webbing         |       14,161 |             8,120 |        3,218 |

For hanging cobwebs, `141431/81200 = 1.7418`, close to the expected deep multiplier
`560/321 = 1.7445`. Deep Dark sculk patch produced 134,753 deep biome-filter passes and 1,433,023
deep block writes, reaching Y -603. Sculk vein produced 119,706 deep passes and wrote through Y
-575. The reference band retained its original per-invocation candidate count.

### Tall Fabric

The final Fabric code generated the 256-chunk Goldilocks region in 17.04 seconds. Every tracked BOP
and vanilla canonical-range feature received high-band candidates. Four Spider Nest families wrote
above 256 in this sample, with webbing reaching Y 295; the final NeoForge run independently
confirmed high spider-egg writes. This is sufficient loader parity because the implementation is
common code and both loader mixin paths executed.

### Controls and performance

- A default RTF control retained exactly `-64..256` candidate origins and emitted no high-band
  candidates.
- The final production classes loaded and ran with BOP 21.1.0.14, GlitchCore 2.1.0.0, and
  TerraBlender 4.1.0.0 on both loaders.
- The 256-chunk command timings showed no measurable regression: tall runs were about 17 seconds
  versus roughly 19 seconds in the baseline run; the very-deep final run was 29.36 seconds versus
  roughly 31 seconds in the baseline. These are coarse end-to-end checks, not a controlled
  microbenchmark.
- Work necessarily grows in proportion to added vertical volume for affected features. Density
  within each 321-level band remains constant rather than becoming either diluted or amplified.

## Screenshot reproduction

Use two fresh Goldilocks worlds with the same mod set, changing only the RTF build:

```text
seed:   3216933670
preset: qa/presets/goldilocks.zip
mods:   Biomes O' Plenty 21.1.0.14, GlitchCore 2.1.0.0, TerraBlender 4.1.0.0
before: upstream 1.21.1
after:  fix/dynamic-cave-feature-placement
```

Generate the same tested chunk window in each world:

```mcfunction
/forceload add -54656 65152 -54401 65407
```

Then enter spectator mode and use this camera position:

```mcfunction
/gamemode spectator
/tp @s -54534 270 65234 180 10
```

Keep F3 visible. This is a confirmed `biomesoplenty:spider_nest` cell above the old absolute-256
origin cap. The before world has the cave biome but no locally originated Spider Nest decoration;
the fixed world places several feature families nearby:

| Feature         | Example fixed-world write |
| --------------- | ------------------------- |
| Corner cobwebs  | `-54529 272 65228`        |
| Spider eggs     | `-54532 266 65219`        |
| Stringy cobweb  | `-54530 266 65208`        |
| Hanging cobwebs | `-54539 271..275 65194`   |

The camera faces north toward the decorated pocket. Move a few blocks north in spectator mode if a
wall obscures the eggs or hanging strands. A second dense cobweb pocket is around
`-54567 285 65282`; a high webbing cluster is around `-54634 269 65310`.

## Stress-preset density and performance follow-up

On 2026-07-30, a `worldDepth=1024`, `worldHeight=1024` stress preset exposed an enormous connected
Spider Nest cavern around `19893 591 -126`. A matched screenshot showed an otherwise bare wall with
only one hanging cobweb. This does not mean the original vertical dilution remained.

### Average density

The QA scanner counts final unique `minecraft:cobweb` and `biomesoplenty:spider_egg` blocks in
quart-biome cells, in addition to placement attempts and writes.

Equal 64-chunk samples produced:

| Case                       | Build range   | Spider Nest enclosed-air samples | Surviving cobweb/egg blocks | Blocks per enclosed sample |
| -------------------------- | ------------- | -------------------------------: | --------------------------: | -------------------------: |
| Vanilla-height RTF control | `-64..319`    |                              775 |                         154 |                      0.199 |
| Cave stress, production 1× | `-1024..1023` |                              304 |                          66 |                      0.217 |

The stress average was about 9% higher, not lower. The broader 256-chunk telemetry reached the same
conclusion from runtime placement events:

- successful Spider Nest origins per sampled cave-air cell: control `0.741`, stress `0.761`;
- configured-feature writes per enclosed-air sample: control `13.08`, stress `13.83`.

The screenshot therefore exposes spatial variance and clumping across giant connected cave surfaces.
Preserving vanilla candidate density per vertical block does not guarantee that every large visible
wall receives decoration.

### Controlled density multipliers

QA-only multipliers sampled each extension band 2× and 4× while leaving the reference band
unchanged. Seed, preset, loader, mod set, and 64-chunk window were identical. A one-chunk pre-run
was subtracted from feature counters and CPU time.

| Extension density | Wall time | Wall delta | Affected-feature CPU | Spider Nest CPU | Spider high passes | Spider high writes |
| ----------------: | --------: | ---------: | -------------------: | --------------: | -----------------: | -----------------: |
|                1× |   38.37 s |          — |           5.16 CPU-s |      0.31 CPU-s |              2,318 |             11,519 |
|                2× |   40.44 s |      +5.4% |           8.28 CPU-s |      0.60 CPU-s |              4,551 |             23,658 |
|                4× |   48.53 s |     +26.5% |          14.65 CPU-s |      1.11 CPU-s |              8,445 |             43,026 |

These wall deltas isolate density: the stress preset and terrain cost were held constant. Summed
feature CPU can overlap across worldgen workers and is therefore not expected to equal wall time.

The generic cost is dominated by `minecraft:sculk_patch_deep_dark`, not BOP. Its scoped CPU rose
from `4.46` to `7.03` to `12.39` CPU-seconds. Multiplying every canonical consumer therefore makes
4× unattractive even in exchange for denser Spider Nests.

A final-state 16-chunk scan around the screenshot found 30 surviving Spider Nest blocks at 1×, 29 at
2×, and 43 at 4×. Extra attempts scaled nearly linearly, but local visible blocks did not because
attempts missed usable surfaces or overlapped. A global multiplier is consequently an inefficient
answer to the screenshot.

### Design consequence

Do not ship the QA multiplier as the production fix. The existing implementation correctly repairs
reach and average vertical density. A further enhancement should target spatial coverage or exposed
cave surface area without multiplying already-dense features such as Deep Dark sculk. Doing that
generically requires a new semantic mechanism; it cannot be inferred safely from the shared
`uniform(bottom, absolute(256))` modifier alone.

### Known separate limitation

All eight BOP Glowing Grotto placed-feature registrations received high candidates. Four of their
configured features—small, medium, huge, and giant glowshrooms—then apply their own literal
`Y >= 255` rejection. RTF cannot repair that generically at placement time. That and the other
hardcoded vertical limits are tracked in `fixed-y-worldgen-follow-up-audit.md`.

PR #152 remains logically independent: it determines which cave biome occupies a cell. This fix
determines whether registered decoration origins can reach that cell at a stable vertical density.
