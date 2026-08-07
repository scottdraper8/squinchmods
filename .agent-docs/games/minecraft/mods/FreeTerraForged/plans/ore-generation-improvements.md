<!-- markdownlint-disable MD013 MD038 MD046 -->

# FreeTerraForged Ore Generation Improvement Plan

**Repository:** [ETcodehome/FreeTerraForged](https://github.com/ETcodehome/FreeTerraForged) **Target
branch:** `1.21.1` (submodule pinned at `a154b1c6c3a6198a7c184f31387b64ff17271d11`) **Document
date:** 2026-08-05 **Dependency:** Complete enough of the
[biome correctness plan](./biome-fixing-plan.md) to validate biome-scoped ore profiles.

> This plan deliberately excludes a per-ore GUI and minute user editing. The goal is a conservative,
> compatible world-height adaptation layer for ordinary ores, with diagnostics for everything else.
>
> Every quantitative claim below is either a citation against the pinned commit (`file:line`), a
> citation against mapped vanilla source (`games/minecraft/reference/sources/1.21.1/official/src/`),
> a citation against a real, currently-checked-out third-party mod source tree (paths under
> `games/minecraft/reference/sources/1.21.1/mods/`, gitignored and reusable across sessions — see
> §21), or **real telemetry from an actual running FreeTerraForged dev server**, generated for this
> plan and reproducible with the exact commands given in §15. Nothing here is estimated from an
> illustrative hypothetical world; every dilution ratio in §4 is a measured number from a real
> 256-chunk generation run at seed `3216933670`.

---

## 1. Executive summary

Ore generation is not governed by one "spawn rate." A block of ore appears only after a chain of
independent conditions succeeds:

1. the relevant dimension and chunk generator run;
2. an eligible biome is selected at the candidate position;
3. the final biome generation settings contain the placed feature;
4. the feature executes in the correct decoration step;
5. count, rarity, noise, config, and custom placement modifiers produce a candidate;
6. the height provider produces a valid Y;
7. all filters accept the candidate;
8. the configured feature runs;
9. the existing host block matches a replacement target;
10. the generated geometry survives overlap, caves, air exposure, and bounds;
11. no later feature overwrites the ore.

FreeTerraForged's main ore problem is vertical semantics. Vanilla and modded profiles are usually
authored around a roughly `-64..319` Overworld. FreeTerraForged can create worlds hundreds of blocks
deeper or taller — **and its own default preset already does**, measured below. Depending on the
profile:

- fixed absolute bands remain concentrated around vanilla Y and leave added terrain empty;
- bottom-relative bands move with the new bottom;
- top-relative or mixed ranges stretch while their attempt count remains fixed, diluting density;
- biome-scoped profiles disappear if their biome is unreachable;
- target rules fail if another geology system replaces expected host blocks;
- custom placement modifiers add conditions that FreeTerraForged must preserve.

The recommended scope is:

- recognize standard `minecraft:ore` and `minecraft:scattered_ore` configured features;
- inspect the **final active biome feature graph** after modifiers;
- adapt only clearly understood vertical placement semantics;
- preserve counts, feature sizes, targets, exposure rules, biome scope, generation step, custom
  filters, and modifier order unless a documented density policy explicitly changes counts;
- leave custom ore systems untouched — and there are real ones in the compatibility surface this
  plan targets, not just hypothetical ones (§6.1, §6.3);
- emit a detailed compatibility report;
- treat vanilla noise-router iron/copper veins as a separate system.

A concrete, currently-open gap this plan surfaces (§11) is that **the tooling needed to measure
realized ore block placement does not exist yet** for standard `minecraft:ore` features — verified
by running the existing telemetry probe against real vanilla ore features and finding it reports
zero block writes for all of them, then confirming against both FreeTerraForged's mapped vanilla
source and Lithostitched's reimplementation that standard ore features write blocks through a code
path the existing probe does not hook. Phase 1 of this plan (§15) must close that gap before any
"realized density" claim in this document or a future PR can be trusted.

---

## 2. Why biome work is a prerequisite

A placed feature is commonly attached to one or more biomes. The actual chain is:

```text
climate target point
→ selected biome
→ final biome generation settings
→ generation step
→ placed feature
→ configured ore feature
```

If an ore is exclusive to a biome that never generates, changing its Y range or count will not make
it appear.

Vanilla examples include:

- extra gold in badlands;
- large copper placement in dripstone caves;
- emerald ore in mountain biomes.

Modded ores may be gated by:

- exact biome IDs;
- biome tags;
- TerraBlender regions;
- cave-biome depth;
- dimension tags;
- loader biome modifiers.

The ore implementation can begin before every biome issue is solved, but biome reachability and
final feature membership must be measurable before biome-dependent ore density can be declared
correct.

---

## 3. Complete gate model for ordinary ore spawning

### 3.1 Dimension and generator gate

Possible conditions: exact dimension key; dimension tag; Overworld biome tag; generator type; world
preset; loader-specific event; server config; datapack load predicate; custom code checking world
properties.

Failure mode: the ore is registered but never attached to FreeTerraForged's Overworld.

FreeTerraForged must inspect the active Overworld graph, not every ore-like registry entry globally.

### 3.2 Biome-selection gate

Conditions: owning biome must actually win at candidate X/Y/Z; TerraBlender region must be selected;
Biolith or another replacement layer may change the result; cave banding may change the deep biome;
special terrain overrides may intercept selection.

Failure mode: an ore profile is valid but its owning biome is absent or only selected at unintended
Y.

This gate is exactly what `plans/biome-fixing-plan.md` is scoped to make measurable — see that
document's §6 diagnostic-tooling inventory and §7 phased audit before assuming a biome-scoped ore's
biome is reachable.

### 3.3 Biome feature-membership gate

A `PlacedFeature` must be present in the final `BiomeGenerationSettings` for the relevant generation
step. It may be added by the biome's own builder, added by Fabric biome modification, added by a
NeoForge biome modifier, added or removed by Lithostitched, replaced by a datapack, duplicated by
multiple compatibility systems, or removed by a pack that installs a replacement distribution.

Confirmed real example: PR #151 (merged) changed the NeoForge `AddModifier` to use a mutable
`ArrayList` for feature lists so later mods can append safely
(`neoforge/src/main/java/raccoonman/reterraforged/world/worldgen/biome/modifier/neoforge/AddModifier.java`,
+10/-6 lines per the PR diff). This is precisely a §3.3 failure mode that was real and shipped.

Failure mode: FreeTerraForged sees the definition in the registry but it is inactive, or sees both
original and replacement profiles as active.

### 3.4 Generation-step gate

Most ores run in `UNDERGROUND_ORES`, but the step is not an ore classifier. Confirmed against real
Biomes O' Plenty source (`biomesoplenty/biome/BOPOverworldBiomes.java`, checked out at
`games/minecraft/reference/sources/1.21.1/mods/biomesoplenty`, branch `1.21.1`): the same
`GenerationStep.Decoration.UNDERGROUND_ORES` step carries `MiscOverworldPlacements.DISK_SAND`,
`DISK_CLAY`, `DISK_GRAVEL`, `BOPMiscOverworldPlacements.DISK_MUD`, and `DISK_CALCITE` alongside
actual ore features in the same biomes (lines 352-353, 541-542, 838-840, 789). Classifying every
feature in `UNDERGROUND_ORES` as an ore produces false positives on real, currently-relevant mod
content, not a hypothetical one.

FreeTerraForged must identify the configured feature type and output/target semantics, not only the
step.

### 3.5 Attempt-count gate

Candidate origins can be controlled by `count`, `rarity_filter`, `noise_based_count`,
`noise_threshold_count`, `count_on_every_layer`, multiple count-like modifiers, mod configuration,
custom placement modifiers, or feature-internal random chance. An attempt is not a successful
deposit. Later gates can reject it.

### 3.6 Horizontal-position gate

Modifiers may distribute candidates with `in_square`, offset candidates, scan an environment, use
heightmaps, or use a custom regional or noise distribution. Chunk-border geometry can also make
deposits straddle neighboring chunks.

### 3.7 Vertical-position gate

A `HeightProvider` may be constant, uniform, trapezoid, biased, very biased, a weighted list,
custom, or nested/data-driven. Its anchors may be absolute, above bottom, or below top. A profile
can combine different anchor types at its endpoints — confirmed directly in vanilla's own
`OrePlacements.java` (`ORE_IRON_SMALL` combines `VerticalAnchor.bottom()` with
`VerticalAnchor.absolute(72)`; see §5.4).

### 3.8 Placement-filter gate

Standard filters can include biome filter, block predicate, carving mask, environment scan, surface
relative threshold, surface water depth, heightmap, or custom placement filters. A custom filter may
be decodable but not semantically understood — confirmed real example: Create's
`ConfigPlacementFilter` (§6.1), a genuinely opaque, mod-specific gate this plan must preserve rather
than reinterpret.

### 3.9 Configured-feature gate

The placed feature invokes a configured feature. Relevant standard types include `minecraft:ore` and
`minecraft:scattered_ore`. Other ore-like deposits use disk, geode, no-op/selector/composite
features, custom seam features, custom strata features, structure placement, surface rules, or
noise-router terrain material rules.

Two **confirmed, currently-real** custom configured feature types this plan must not misclassify as
standard ore:

- **Create's `create:layered_ore`** (`LayeredOreFeature`/`LayeredOreConfiguration`,
  `common/src/main/java/com/simibubi/create/infrastructure/worldgen/`): used by
  `striated_ores_overworld`/`striated_ores_nether` to place weighted, layered decorative stone/ore
  seams (scoria, limestone, crimsite, asurine, veridium, ochrum, plus vanilla stone variants) — a
  genuinely custom placement algorithm, not `minecraft:ore` with different parameters
  (`src/generated/resources/data/create/worldgen/configured_feature/striated_ores_overworld.json`,
  read in full at `games/minecraft/reference/sources/1.21.1/mods/create`).
- **Lithostitched's `dev.worldgen.lithostitched.worldgen.feature.OreFeature`/`OreConfig`**
  (`common/src/main/java/dev/worldgen/lithostitched/worldgen/feature/OreFeature.java`, checked out
  at `games/minecraft/reference/sources/1.21.1/mods/lithostitched`, branch `1.21`): a
  library-provided alternative ore feature implementation available to any Lithostitched-dependent
  mod. A scan of Regions Unexplored's own generated configured features
  (`src/shared/21.1/main/generated/data/regions_unexplored/worldgen/configured_feature/`) found only
  standard `"type": "minecraft:ore"` entries — **this plan found no confirmed real usage of
  Lithostitched's custom type by Regions Unexplored specifically**, so treat it as a capability to
  detect and classify correctly if encountered, not a confirmed RU behavior to special-case.

Only standard ore types should receive automatic initial support.

### 3.10 Target-rule gate

Standard `OreConfiguration` contains target rules mapping host predicates to output block states.
Typical targets include `#minecraft:stone_ore_replaceables`,
`#minecraft:deepslate_ore_replaceables`, Nether base stone, exact blocks, modded rock tags, or
custom rule tests.

Failure mode: the candidate lies at the correct Y, but the current block is not a valid host.
FreeTerraForged should report target mismatch; it should not silently broaden another mod's geology
rules.

### 3.11 Deposit-geometry gate

For standard ore features, nominal `size` is not a guaranteed block count. Real output depends on
geometric overlap, repeated candidate cells, host availability, cave intersections, world bounds,
chunk bounds, target-rule failures, and air-exposure rejection. Frequency and size must remain
separate concepts.

### 3.12 Air-exposure gate

`OreConfiguration.discard_chance_on_air_exposure` is a per-profile probability that exposed
candidate blocks are discarded, confirmed against vanilla's real `OreFeature.canPlaceOre`
(`net/minecraft/world/level/levelgen/feature/OreFeature.java`, mapped source): `0.0` skips the
air-adjacency check entirely (`shouldSkipAirCheck` returns `true`); a value in `(0, 1)` randomly
skips the check per-block; `1.0` never skips it, so every exposed candidate is rejected via
`isAdjacentToAir`. This is a negative filter — standard ores do not require air exposure; some
profiles merely permit it.

An optional FreeTerraForged "hide exterior mountain exposure" rule would be a separate feature and
should not overwrite source cave-exposure semantics.

### 3.13 Terrain-volume gate

A height provider can select Y=500, but ore will not appear there unless solid, target-compatible
terrain exists at that position. Realized density differs among plains, thick mountains, thin
ridges, islands, overhangs, deep oceans, cave-heavy terrain, and aquifer-heavy terrain.

### 3.14 Ordering and overwrite gate

Earlier features can remove host material. Later features can overwrite ore. Potential interactions:
caves and carvers, geodes, strata, disks, stone replacement, structures, surface rules, fluid
placement, another ore replacement system.

### 3.15 Existing-chunk gate

Changing ore generation affects newly generated chunks only unless explicit retrogen is implemented.
Retrogen is a separate project with duplicate prevention, saved-data/version tracking, performance
concerns, player-build safety, and deterministic compatibility. It should remain out of scope for
the first ore improvement.

---

## 4. Measured vertical dilution in real FreeTerraForged worlds

This section replaces a hypothetical illustration with real telemetry. Methodology, reproduction
commands, and full raw output are in §15 (Phase 0). Summary of method: a real Fabric dev server was
started against the current FreeTerraForged submodule (`a154b1c6c3a6198a7c184f31387b64ff17271d11`),
seed `3216933670`, and the existing `placement-telemetry` probe pack — which despite its name mixes
directly into vanilla `PlacedFeature`, `HeightRangePlacement`, `CountPlacement`, and `BiomeFilter`
generically, keyed by any `PlacedFeature` registry ID via request configuration
(`games/minecraft/investigations/reterraforged/probes/placement-telemetry/src/main/java/org/squinchmods/investigate/rtf/placement/RtfPlacementTelemetryProbePack.java:32,39`)
— was pointed directly at four real vanilla ore placed features: `minecraft:ore_coal_upper`,
`minecraft:ore_iron_small`, `minecraft:ore_redstone`, and `minecraft:ore_diamond`. A 16×16-chunk
(256-chunk) region at the world origin was force-generated to `finished-chunk` authority and every
candidate/biome-check/height event was aggregated.

Vanilla Y-ranges and counts below are confirmed directly from mapped vanilla source
(`net/minecraft/data/worldgen/placement/OrePlacements.java`), not memory or documentation:

| Feature          | Anchor type                             | Vanilla range (levels) | Vanilla count |
| ---------------- | --------------------------------------- | ---------------------- | ------------- |
| `ore_coal_upper` | `absolute(136)` .. `top()`              | 184                    | 30            |
| `ore_iron_small` | `bottom()` .. `absolute(72)`            | 137                    | 10            |
| `ore_redstone`   | `bottom()` .. `absolute(15)`            | 80                     | 4             |
| `ore_diamond`    | `aboveBottom(-80)` .. `aboveBottom(80)` | 160                    | 7             |

`VerticalAnchor.top()` is confirmed to equal `belowTop(0)` directly
(`net/minecraft/world/level/levelgen/VerticalAnchor.java:12,30`).

### 4.1 Real measured results across three real fixtures, same seed, same 256-chunk window

| Feature                         | vanilla-depth-maximum-ocean (RTF **default**, worldDepth=64\*, worldHeight=384) | shallow-depth-mountain-control (worldDepth=16, worldHeight=384) | maximum-vertical-range-cave-decoration-stress (worldDepth=1024, worldHeight=1024) |
| ------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `ore_coal_upper` range          | 248 (**1.35× vanilla**)                                                         | 248 (**1.35× vanilla**)                                         | 888 (**4.83× vanilla**)                                                           |
| `ore_iron_small` range          | 137 (**1.00× vanilla**, identical)                                              | 89 (**0.65× vanilla — denser**)                                 | 1097 (**8.01× vanilla**)                                                          |
| `ore_redstone` range            | 80 (**1.00× vanilla**, identical)                                               | 32 (**0.40× vanilla — denser**)                                 | 1039 (**13.0× vanilla**)                                                          |
| `ore_diamond` range             | 160 (**1.00× vanilla**, identical)                                              | 160 (**1.00× vanilla**, identical)                              | 160 (**1.00× vanilla**, identical)                                                |
| Candidate counts (all features) | exactly `count × 256` in every case (7680/2560/1024/1792)                       | same                                                            | same                                                                              |
| Biome-pass rate (all features)  | 100%                                                                            | 100%                                                            | 100%                                                                              |
| Block writes observed           | 0 (§6.1 gap, not a success-rate signal)                                         | 0                                                               | 0                                                                                 |

\* `vanilla-depth-maximum-ocean`'s own fixture metadata states `worldDepth` is _omitted_, relying on
FreeTerraForged's own 64-block default
(`games/minecraft/investigations/reterraforged/fixtures/vanilla-depth-maximum-ocean/fixture.toml`).
`worldHeight` likewise is not overridden and comes from the base preset's own declared default of
`384`
(`games/minecraft/investigations/reterraforged/fixtures/_base/data/reterraforged/reterraforged/worldgen/preset/preset.json`).

### 4.2 What this measured data proves, precisely

- **FreeTerraForged's own default preset is already taller than vanilla.** `worldHeight` in RTF's
  `WorldSettings.Properties` means "build space above Y 0"
  (`wiki/concepts/terrain-coordinates-and-levels.md`), and the default value of `384` is _not_ the
  same as vanilla's actual space above Y 0 (vanilla's real ceiling `Y=319` gives 320 blocks above
  zero, not 384). The measured `ore_coal_upper` candidate ceiling of `Y=383` in the _default_
  fixture confirms this directly: `-64` (bottom) `+ 64 + 384 - 1 = 383`. This means **every
  top-relative standard ore is diluted by ~1.35× on FreeTerraForged's out-of-the-box default
  preset**, before any deliberately "tall" or "deep" world setting is touched. This changes what
  "vanilla-like" means for the §14.1 test matrix: the baseline case is not dilution-free.
- **Bottom-relative-to-absolute ores (iron, redstone) are exactly vanilla-identical on the default
  preset**, because `worldDepth` defaults to `64`, matching vanilla exactly, and these ores anchor
  their lower bound to `bottom()`. Dilution for this anchor shape is entirely a function of
  `worldDepth`, not `worldHeight`.
- **The same anchor shape can get _denser_, not just sparser.** On `shallow-depth-mountain-control`
  (`worldDepth=16`), `ore_redstone`'s range shrinks to `32` levels — **2.5× denser than vanilla**,
  with the same fixed count of `4` attempts per chunk. This is real, measured evidence for a risk
  this plan's §9 density-policy section discusses in the abstract ("expanded ranges become sparser")
  but had not measured in the opposite direction: a "preserve total attempts" policy can _also_
  overproduce a resource on shallow-depth presets, not only underproduce on deep ones.
  `ore_iron_small` shows the identical effect (`0.65×`, denser).
- **Bottom-relative-to-bottom-relative anchors (`aboveBottom`/`aboveBottom`) are perfectly preserved
  with zero measured dilution across all three fixtures** — `ore_diamond`'s range is exactly `160`
  in every single run, including the most extreme (`worldDepth=1024`). This is real proof that this
  anchor shape requires **no adaptation code at all**; it already tracks FreeTerraForged's actual
  world bottom correctly by construction, confirming §8.1's "Bottom-relative–bottom-relative:
  preserve relative relationship to bottom" recommendation with hard data rather than assuming
  vanilla's `HeightRangePlacement` anchor resolution behaves this way.
- **Candidate counts matched the documented vanilla count exactly, multiplied by chunk count, in
  every single run** (e.g. `30 × 256 = 7680` for `ore_coal_upper`), confirming FreeTerraForged does
  not currently alter standard ore attempt counts anywhere in the pipeline before this plan's work
  begins — a clean, confirmed "preserve total attempts" starting point.
- **Biome-pass rate was 100% for every feature in every fixture in this sample.** These four ores
  attach broadly enough (via vanilla's default Overworld biome membership) that biome-selection gate
  failures were not observed here. This does not generalize to biome-scoped modded ores (Create's
  zinc, BOP's extra emeralds) — those require the biome-fixing-plan's reachability audit, not this
  measurement.

### 4.3 A confirmed, currently-unmeasurable gap: realized block-level success

Every run above reported **zero block writes for every feature**, despite thousands of
biome-passing, in-range candidates. This is not evidence of a 0% success rate. It is a confirmed
instrumentation gap:

- The existing probe's write-tracking hook targets `WorldGenRegion.setBlock`
  (`games/minecraft/investigations/reterraforged/probes/placement-telemetry/src/main/java/org/squinchmods/investigate/rtf/placement/mixin/MixinWorldGenRegion.java:15-16`).
- Vanilla's real `OreFeature.doPlace` does **not** call
  `WorldGenLevel.setBlock`/`WorldGenRegion.setBlock` at all. It writes directly via
  `BulkSectionAccess`/`LevelChunkSection.setBlockState(...)`
  (`net/minecraft/world/level/levelgen/feature/OreFeature.java`, mapped source, confirmed at the
  exact line that performs the write:
  `levelChunkSection.setBlockState(al, am, an, targetBlockState.state, false)`).
- Lithostitched's independent `OreFeature` reimplementation does the identical thing
  (`dev/worldgen/lithostitched/worldgen/feature/OreFeature.java`,
  `section.setBlockState(sectionX, sectionY, sectionZ, ..., false)`), confirming this is not a
  vanilla quirk but the standard pattern any conforming ore feature implementation uses.

**No existing tool in this repository can currently measure realized ore block placement.** This
must be built (a new mixin targeting `LevelChunkSection.setBlockState` scoped to ore-feature-owned
writes, or targeting `OreFeature.canPlaceOre`/`doPlace` directly) before §11's "blocks replaced"
metric or any of this plan's §14.4 statistical claims about realized density can be produced. This
is Phase 1's first concrete deliverable (§15).

### 4.4 Added terrain with no profile

Absolute gold, copper, and lapis bands can remain unchanged while hundreds of added blocks above or
below receive no corresponding distribution. This is not always wrong. It becomes a design problem
when the added terrain is intended to provide ordinary mining progression rather than intentionally
barren geology. §4.1's measured data shows the concrete scale of this for real FreeTerraForged
presets already in this repository's own QA fixture set — the effect is not hypothetical.

### 4.5 Larger caves reduce success

Even with unchanged candidate density, larger cave volume can reduce successful block replacement
because more candidates land in air or fluid, more vein geometry crosses exposed surfaces,
air-exposure discard removes blocks, and thin shells provide less host volume. This must be measured
separately from placement attempts — and per §4.3, cannot yet be measured at all until the
block-write instrumentation gap is closed.

---

## 5. Representative mod behavior

### 5.1 Create zinc — fully verified against real, current source

Create's 1.21.1 zinc is an ideal compatibility example. Verified by cloning
`Creators-of-Create/Create` at branch `mc1.21.1/dev` (real HEAD, not a pinned historical commit)
into `games/minecraft/reference/sources/1.21.1/mods/create` and reading the files directly — **the
originally-linked GitHub blob URLs under a `dev/` path prefix do not exist in the current repository
layout** (there is no top-level `dev/` directory; the real path is
`src/generated/resources/data/...` at the repository root). The generated JSON itself is confirmed
identical in substance:

Placed feature (`src/generated/resources/data/create/worldgen/placed_feature/zinc_ore.json`):

```json
{
  "feature": "create:zinc_ore",
  "placement": [
    { "type": "minecraft:count", "count": 8 },
    { "type": "minecraft:in_square" },
    {
      "type": "minecraft:height_range",
      "height": {
        "type": "minecraft:uniform",
        "min_inclusive": { "absolute": -63 },
        "max_inclusive": { "absolute": 70 }
      }
    },
    { "type": "create:config_filter" }
  ]
}
```

Configured feature
(`src/generated/resources/data/create/worldgen/configured_feature/zinc_ore.json`): standard
`minecraft:ore`, `size: 12`, `discard_chance_on_air_exposure: 0.0`, targets
`create:zinc_ore`/`create:deepslate_zinc_ore` against `#minecraft:stone_ore_replaceables`/
`#minecraft:deepslate_ore_replaceables`.

Biome modifier — confirmed directly in Java, not JSON (the linked
`neoforge/biome_modifier/zinc_ore.json` path also does not exist in the current layout; the modifier
is registered programmatically): `AllBiomeModifiers.java` registers
`new AddFeaturesBiomeModifier(isOverworld, HolderSet.direct(zincOre), Decoration.UNDERGROUND_ORES)`
(`src/main/java/com/simibubi/create/infrastructure/worldgen/AllBiomeModifiers.java:39,44-46`) — zinc
attaches to `BiomeTags.IS_OVERWORLD` at `UNDERGROUND_ORES`, confirmed exactly as previously claimed.

Custom filter — confirmed directly: `ConfigPlacementFilter.shouldPlace` returns
`!AllConfigs.common().worldGen.disable.get()`
(`src/main/java/com/simibubi/create/infrastructure/worldgen/ConfigPlacementFilter.java:18-20`). The
filter disables placement when Create's worldgen config is disabled — confirmed exactly.

FreeTerraForged can understand nearly everything about this profile. It does **not** need to
reinterpret the custom filter; it must preserve it.

Recommended support classification (unchanged, now fully source-verified rather than
documentation-derived):

```text
configured feature: fully recognized
height provider: recognized
count: recognized
targets: recognized
custom filter: preserved, opaque
automatic vertical adaptation: eligible
```

A second, real Create example this plan's original draft did not examine: `striated_ores_overworld`/
`striated_ores_nether` use `create:layered_ore` (§3.9) — a genuinely custom feature type Create
ships alongside zinc's standard one, in the same `AllBiomeModifiers`/`AllConfiguredFeatures`
registration files. This is real evidence that "recognize standard ore types, preserve everything
else" must coexist within a _single mod's own worldgen registration_, not just across different
mods.

### 5.2 Biomes O' Plenty — fully verified against real, current source

Verified by cloning `Glitchfiend/BiomesOPlenty` at branch `1.21.1` into
`games/minecraft/reference/sources/1.21.1/mods/biomesoplenty`.
`BiomeDefaultFeatures.addDefaultOres(biomeBuilder)` is called **54 times** across
`BOPOverworldBiomes.java`, confirming BOP biomes commonly inherit the vanilla ore suite at that
scale, not merely "commonly." `BiomeDefaultFeatures.addExtraEmeralds`/ `addInfestedStone` are also
called repeatedly (lines 289-290, 561-562, 634-635, 814-815, and others), and multiple biomes add
`MiscOverworldPlacements.DISK_SAND`/`DISK_CLAY`/`DISK_GRAVEL` and
`BOPMiscOverworldPlacements.DISK_MUD`/`DISK_CALCITE` at the same `UNDERGROUND_ORES` step (§3.4) —
directly confirming that step is not an ore classifier on real, current mod content.

PR #154's own text (fetched via `gh api repos/ETcodehome/FreeTerraForged/pulls/154`, not just its
diff) documents a real, specific example of a later-feature-internal height check that placement
adaptation cannot override: "several BOP glowshroom features have a hardcoded y-max inside their
placement logic, and refuse to generate at or above `Y=255`... that limitation has to be fixed by
the mod that owns the feature." The same PR body records the exact compatibility versions actually
tested: **Biomes O' Plenty 21.1.0.14, GlitchCore 2.1.0.0, and TerraBlender 4.1.0.0** — useful, real
version pins for any future compatibility test matrix.

Implications, confirmed rather than assumed:

- BOP biome reachability matters (feeds directly into `plans/biome-fixing-plan.md`'s reachability
  audit);
- final biome generation settings must be used;
- `UNDERGROUND_ORES` is not sufficient for classification — confirmed with real, multiple non-ore
  examples above;
- standard inherited vanilla ores can be adapted by their placed-feature identity;
- BOP-specific custom features should remain untouched unless independently recognized;
- adapting a placement modifier cannot override a later feature-internal height check — confirmed
  with a real, specific, currently-documented BOP example, not a hypothetical one.

### 5.3 Regions Unexplored and Lithostitched — verified, and corrected

Verified by cloning `Apollounknowndev/RegionsUnexplored` (branch `21.1`, confirmed to target
Minecraft `1.21.1` via `build.gradle.kts`) and `Apollounknowndev/lithostitched` (branch `1.21`,
confirmed `minecraft_version=1.21.1`) into `games/minecraft/reference/sources/1.21.1/mods/`.

**Correction to the prior framing**: Regions Unexplored does not merely "commonly use" Lithostitched
in 1.21.1 stacks — its own Fabric build declares a hard runtime dependency,
`modImplementation("maven.modrinth:lithostitched:$lithostitchedVersion-fabric-21.1")`
(`build.gradle.kts:99`, with the NeoForge side using `modCompileOnlyApi`/`modImplementation`
equivalents at lines 56, 186). Any FreeTerraForged worldgen stack that includes Regions Unexplored
includes Lithostitched.

Lithostitched genuinely can add, remove, or replace features and modify broader worldgen data — it
ships multiple worldgen-facing systems confirmed directly in its own source tree:
`worldgen/densityfunction/{MergedDensityFunction,OriginalMarkerDensityFunction,WrappedMarkerDensityFunction}.java`,
`worldgen/feature/{CompositeFeature,DungeonFeature,LargeDripstoneFeature,OreFeature}.java`, and
mixins into `JigsawStructure`, `StructureTemplatePool`, `NoiseGeneratorSettings`, and
`ChunkGeneratorAccessor` (`mixin/common/*.java`). This is a substantially larger worldgen surface
than "regional biome composition" alone.

Implications, confirmed:

- inspect the final graph after Lithostitched;
- do not resurrect a removed original ore;
- do not apply a second automatic stretch to an externally authored expanded-height distribution by
  default;
- preserve region and biome scope;
- flag weighted/custom height providers as externally authored unless there is an adapter;
- Lithostitched's own `OreFeature`/`OreConfig` type (§3.9) is a real, available custom ore mechanism
  — detect it explicitly by configured-feature type rather than assuming every ore-shaped feature in
  a Lithostitched-dependent mod stack is standard `minecraft:ore`.

### 5.4 Vanilla large iron and copper veins

Vanilla large ore veins are not ordinary biome placed features. They use noise-router fields and
`OreVeinifier`. Confirmed directly against mapped vanilla source
(`net/minecraft/world/level/levelgen/OreVeinifier.java:60-61`):

```java
COPPER(..., /* minY */ 0, /* maxY */ 50);
IRON(..., /* minY */ -60, /* maxY */ -8);
```

These are literal, hardcoded absolute Y constants — they cannot move with a preset's `worldDepth`/
`worldHeight` by construction. FreeTerraForged already constructs `oreVeininess`, `oreVeinA`,
`oreVeinB`, and `oreGap` density functions in `PresetNoiseRouterData`, confirmed reusing these exact
vanilla constants unmodified:

```java
// PresetNoiseRouterData.java:138-139
int minY = Stream.of(OreVeinifier.VeinType.values()).mapToInt(veinType -> veinType.minY).min()...
int maxY = Stream.of(OreVeinifier.VeinType.values()).mapToInt(veinType -> veinType.maxY).max()...
```

These need a separate audit:

- current min/max Y comes from vanilla `OreVeinifier.VeinType`, confirmed unmodified in current
  source;
- expanded FreeTerraForged depth does not automatically expand those roles — confirmed, since the
  constants are literal and the min/max Y stream above has no dependency on
  `WorldSettings.Properties`;
- vein density and type are coupled to noise fields, not count/height placement modifiers.

Do not fold this system into the first standard-ore implementation.

---

## 6. Effective graph and compatibility precedence

The input to FreeTerraForged must be the effective worldgen graph after mods and datapacks compose
it.

```text
mod/datapack registers configured and placed features
→ biome builders and biome modifiers attach features
→ Lithostitched/other systems add, remove, or replace features
→ FreeTerraForged observes active final profiles
→ optional FreeTerraForged vertical overlay applies at runtime
→ original custom filters and configured feature execute
```

### Precedence policy

| Policy                 | Behavior                                                                        |
| ---------------------- | ------------------------------------------------------------------------------- |
| Inherit                | Run the final externally composed profile unchanged.                            |
| Adaptive standard ores | Adapt only recognized height semantics; preserve everything else.               |
| Disabled globally      | Optional global FreeTerraForged ore adaptation off; source worldgen still runs. |
| Unsupported/custom     | Preserve original behavior and report.                                          |

There should be no per-ore authority contest between FreeTerraForged and Lithostitched.
FreeTerraForged should consume Lithostitched's final result.

If an external pack has already installed a weighted distribution spanning the exact FreeTerraForged
bounds, default to inherit to avoid double transformation.

---

## 7. Recognition and support levels

### 7.1 Full standard support

Requirements: configured feature is `minecraft:ore` or `minecraft:scattered_ore`; active top-level
placed feature is identifiable; at least one recognized height-range modifier exists; standard or
safely preservable count/frequency chain; targets and output states are decodable; custom filters
can remain in place.

Capabilities: read height; read count/rarity where standard; read targets; read size; read exposure;
adapt recognized vertical distribution; measure attempts and replacements (pending §4.3's
instrumentation gap being closed).

### 7.2 Vertical-only support

The height modifier is recognized, but another modifier or feature detail is custom. Behavior: adapt
only the height modifier; preserve all other objects and order; do not estimate exact density; mark
the profile as partially supported.

Create zinc initially fits comfortably here if FreeTerraForged chooses to treat all custom filters
conservatively.

### 7.3 Externally authored distribution

Examples: Lithostitched weighted-list provider; datapack with many hand-authored absolute bins;
profile already matching current world bounds.

Behavior: inherit by default; diagnose out-of-bounds coverage; permit future explicit adapters, not
generic rewriting.

### 7.4 Custom configured feature

The configured feature is not standard ore/scattered ore. Two real, confirmed examples now exist to
validate this classification against: Create's `create:layered_ore` (§3.9, §5.1) and Lithostitched's
`OreFeature` (§3.9, §5.3).

Behavior: preserve; report feature type; do not draw an authoritative distribution or
expected-density estimate; allow an adapter API later.

### 7.5 Non-placed ore system

Examples: noise-router ore veins (§5.4, confirmed real and currently unmodified); surface rules;
structures/meteorites; retrogen; direct chunk-generator hooks.

Behavior: separate subsystem or adapter; never claim standard support.

---

## 8. Vertical semantics and adaptation strategy

A universal stretch is unsafe because an author's absolute Y can mean different things: literal
geological altitude; depth below sea level; distance above bedrock; vanilla-normalized progression
band; intentionally immutable restriction.

FreeTerraForged must use conservative, explicit rules.

### 8.1 Provider classification

#### Absolute–absolute

Example: `-16..112`. Default recommendation: preserve unless the profile is known to be
vanilla-scale standard ore and the chosen adaptive policy explicitly maps it. Risk: scaling can move
a deliberately shallow or deep resource.

#### Bottom-relative–bottom-relative

Default: preserve relative relationship to bottom. **Confirmed by real measurement (§4.2) to already
happen correctly with zero adaptation code**: `ore_diamond`'s `aboveBottom(-80)..aboveBottom(80)`
range measured exactly `160` levels across worldDepth `64`, `16`, and `1024` fixtures. Risk: it may
move far from sea-level progression — this remains a design question independent of the mechanism
working correctly.

#### Top-relative–top-relative

Default: inspect for dilution. A fixed count over a much larger range may require count compensation
rather than range rewriting. **Confirmed real dilution, measured**: `ore_coal_upper` at `1.35×` on
FreeTerraForged's own default preset and `4.83×` on the most extreme currently-retained stress
fixture (§4.1).

#### Bottom-relative–absolute

Default: classify as a bottom-anchored role with an absolute transition. Adapt only under a
documented standard profile rule. **Confirmed real behavior, measured**: this shape
(`ore_iron_small`, `ore_redstone`) is exactly vanilla-identical when `worldDepth` matches vanilla
(RTF's own default), sparser (`8.0×`/`13.0×`) on the extreme stress fixture, and _denser_
(`0.65×`/`0.40×`) on the shallow fixture — this shape's dilution is a direct, roughly linear
function of `worldDepth` alone.

#### Absolute–top-relative

Default: classify as an altitude/upward distribution. Avoid simply repeating it in 321-block bands.

#### Weighted/custom provider

Default: externally authored/inherit.

#### Heightmap/surface-relative

Default: preserve. It already responds to terrain.

### 8.2 Do not reuse cave-decoration banding for ores

PR #154's 321-block repeated opportunities are appropriate for generic cave decorations that should
maintain opportunity density throughout added cave volume. Ores have progression and scarcity
semantics. Repeating diamond, lapis, redstone, or coal roles every 321 blocks would create periodic
resource strata that the source profile never intended.

This caution is reinforced by a real, very recent precedent: the dynamic cave-feature-placement
height-adaptation logic this exact caution refers to **crashed in production** on worlds shorter
than vanilla height (fixed in commit `20f3049`, "Fix surface rescue crash on worlds shorter than
vanilla height," merged as PR #168, days before this plan was written). Both the crash-triggering
fixture (`short-top-world`) and the no-regression fixture
(`maximum-vertical-range-cave-decoration-stress`) were re-run live against current source for this
plan and both currently pass (§15, Phase 0). This is concrete, current evidence that
height-adaptation logic in this codebase has already shipped a real crash on an edge-case world
height once, and any new ore vertical-adaptation code must be tested against the same short/shallow
edge, not only tall/deep ones — the failure mode that actually occurred was on the _short_ end,
which this plan's own illustrative framing had under-weighted relative to "tall and deep."

### 8.3 A confirmed preset-vs-real-dimension divergence risk

The `short-top-world` fixture's own documented `known_limitations` states: "overrides only the
`dimension_type` height/logical_height; the RTF preset's own `worldHeight` field is left at its base
value, so anything that reads the preset directly (rather than the real dimension bounds) will not
see this change"
(`games/minecraft/investigations/reterraforged/fixtures/short-top-world/fixture.toml`). This is a
directly relevant risk for this plan's own proposed architecture (§11): any ore vertical-adaptation
logic that reads `WorldSettings.Properties.worldHeight`/`worldDepth` to determine "the world's real
bounds" can be wrong in exactly the same way the surface-rescue cave-feature-placement crash was
wrong, if a consumer (mod, datapack, or dimension override) changes the real dimension bounds
without changing the declared preset fields. §11's "build a final active ore index" step must read
real dimension bounds (`ChunkGenerator`/`LevelHeightAccessor`), not assume the preset's declared
fields are authoritative.

### 8.4 Recommended semantic model

Represent a recognized distribution in a normalized descriptor:

```text
anchor roles:
  WORLD_BOTTOM
  DEEPSLATE_TRANSITION
  SEA_LEVEL
  SURFACE_TERRAIN
  WORLD_TOP
  ABSOLUTE

shape:
  UNIFORM
  TRIANGULAR/TRAPEZOIDAL
  CONSTANT
  WEIGHTED
  CUSTOM

density policy:
  preserve total attempts
  compensate for range expansion
  custom/unknown
```

The initial implementation can support a smaller subset and fail closed.

---

## 9. Density policy

There are three defensible global policies.

### 9.1 Preserve total attempts

Keep count unchanged. Advantages: conservative; preserves total candidate budget; lower risk of
overproducing rare ores. Disadvantages: expanded ranges become sparser; total successful blocks may
decrease because of more caves/air. **Confirmed real cost of this policy, measured**: on the extreme
fixture, `ore_redstone` becomes `13×` sparser per level with this policy; on the shallow fixture, it
becomes `2.5×` _denser_ — "preserve total attempts" does not mean "preserve resource availability"
in either direction.

### 9.2 Preserve attempts per vertical volume

Scale expected attempts by effective support-height ratio. Advantages: added terrain receives
similar candidate density. Disadvantages: enormous worlds can produce enormous total resources;
progression and economy change substantially; valid solid volume does not scale linearly with world
height.

### 9.3 Balanced/sublinear scaling

Scale attempts sublinearly with support expansion, for example by square root or a capped function.
Advantages: reduces extreme dilution; avoids full linear resource multiplication. Disadvantages:
introduces FreeTerraForged balance policy; requires calibration and documentation.

### Recommendation

For the first PR: adapt standard vertical support; preserve total source attempts by default;
instrument realized density (blocked on §4.3's gap being closed first); do not add count
compensation until measurements show it is needed.

A later PR can introduce one global documented compensation policy, not per-ore editing.

---

## 10. Recommended implementation architecture

### 10.1 Build a final active ore index

At world/datapack initialization: traverse final biome generation settings; collect active top-level
placed features; record biome and generation-step membership; resolve configured feature type;
classify standard ores; group profiles by output block/target family for reporting only; detect
inactive registry entries, replacements, and duplicates; record a stable configuration fingerprint.

Do not use the registry alone. **Read real dimension bounds, not declared preset fields alone** —
see §8.3's confirmed divergence risk.

### 10.2 Lazy/runtime descriptor validation

Because external frameworks may modify worldgen late, generation-time code should verify that the
executing top-level placed feature is the indexed feature; its current modifier/config fingerprint
matches; the dimension is the FreeTerraForged Overworld; the policy is adaptive; the specific height
modifier belongs to that feature.

On mismatch, preserve original behavior and log once.

### 10.3 Narrow hook

A narrow `HeightRangePlacement` interception is preferable to replacing or canceling every placed
feature. The hook should act only for recognized active standard ores; transform only the recognized
height result; preserve modifier order; preserve custom filters; preserve configured feature; avoid
broad `PlacedFeature.placeWithContext` conflicts.

### 10.4 Source descriptor versus effective descriptor

Store both:

```text
source descriptor:
  exact final mod/datapack definition

effective descriptor:
  FreeTerraForged runtime vertical mapping
```

Diagnostics must show both.

### 10.5 Adapter API

Future adapters can expose capabilities:

```text
CAN_IDENTIFY_RESOURCE
CAN_READ_HEIGHT
CAN_READ_FREQUENCY
CAN_READ_TARGETS
CAN_READ_EXPOSURE
CAN_TRANSFORM_HEIGHT
CAN_ESTIMATE_DENSITY
CAN_TRANSFORM_MORPHOLOGY
```

No adapter should imply all capabilities automatically.

---

## 11. Diagnostics and observability: what exists, what must be built

A startup report is more important than a GUI. Unlike the ore-adaptation code itself, meaningful
parts of the _measurement_ infrastructure already exist and were exercised for real in §4 — this
section is corrected against that real usage rather than proposed from scratch.

### 11.1 What the existing `placement-telemetry` probe already gives, for free, today

Confirmed by direct use in §4: pointing
`games/minecraft/investigations/reterraforged/probes/placement-telemetry` at any real
`PlacedFeature` registry ID (via the `feature_ids` request-config array,
`RtfPlacementTelemetryProbePack.java:32,39`) already yields, from real finished-chunk generation:

- exact candidate counts (`count_candidates`);
- exact per-Y candidate histograms (`height_histogram`);
- exact biome-check pass/fail counts and per-Y pass histograms (`biome_checks`/`biome_passes`/
  `biome_pass_height_histogram`);
- per-feature CPU time (`feature_cpu_nanos`);
- caller-defined band aggregation (`bands` config, e.g. "vanilla_range").

This is not a proposal — §4's entire measured dataset was produced using this exact, currently
existing, unmodified probe, pointed at standard vanilla ore feature IDs instead of cave decorations.

### 11.2 What is confirmed missing and must be built before realized-density claims are trustworthy

Per §4.3: **block-write visibility for standard ore features does not exist**, because the existing
`MixinWorldGenRegion.setBlock` hook does not cover the `LevelChunkSection.setBlockState` write path
standard `OreFeature` implementations actually use (confirmed against both vanilla and Lithostitched
source). Building this requires either:

- a new mixin into `Feature<OreConfiguration>` (or the shared `OreFeature`/Lithostitched
  `OreFeature` base logic) at `canPlaceOre`/`doPlace`, keyed the same way the existing probe keys by
  feature ID; or
- a narrower mixin directly into `LevelChunkSection.setBlockState`, filtered to writes occurring
  during an active ore-feature placement context (mirroring how `CavePlacementTelemetry`'s
  thread-local `ACTIVE` stack already tracks "am I inside a feature invocation" for CPU-time
  accounting — the same mechanism can gate a chunk-section write hook).

This is the first concrete deliverable of Phase 1 (§15) — not a future nice-to-have.

### 11.3 Example report format (unchanged target shape)

```text
[FTF Ore Audit] create:zinc_ore
  active biomes: 68 (#minecraft:is_overworld)
  step: underground_ores
  configured feature: minecraft:ore
  count: 8
  source height: uniform absolute -63..70
  custom modifiers: create:config_filter (preserved)
  targets: stone_ore_replaceables, deepslate_ore_replaceables
  policy: adaptive vertical
  support: VERTICAL_ONLY
```

Warnings:

```text
profile entirely outside dimension
profile partially outside dimension
fixed count diluted across expanded top-relative range
owning biome never observed
host target never observed in sampled terrain
original and replacement profiles both active
custom provider not understood
runtime fingerprint changed
declared preset worldHeight/worldDepth diverges from real dimension bounds  (new — see §8.3)
```

### 11.4 Development metrics

Measure separately: candidate attempts; candidate Y histogram (already available, §11.1);
configured-feature invocations; successful invocations; blocks replaced (blocked on §11.2); failures
by reason (out of bounds; air/fluid origin; target mismatch; exposure discard; biome filter; custom
filter); generation time.

A rendered ore chart based only on requested candidate Y is insufficient. Include realized
replaced-block histograms once §11.2 is built.

---

## 12. Surface and mountain exposure

The source ore's `discard_chance_on_air_exposure` must be preserved (confirmed semantics, §3.12).

A global "hide ores on exterior terrain" option is conceptually possible but should be deferred from
the core vertical-fix PR because it introduces a separate gameplay policy.

If implemented later: distinguish cave air from exterior terrain; use `OCEAN_FLOOR_WG` or terrain
surface height as one signal; check each generated block, not only the origin; account for
neighboring lower columns on cliffs; preserve cave-wall visibility by default; allow biome/profile
exceptions only through data/API, not a large UI; measure density lost to rejected blocks.

A heightmap cannot perfectly prove 3D outside-air connectivity, so the option would be an
approximation.

---

## 13. Vanilla noise-router ore veins

Confirmed real, current, unmodified state (§5.4):

1. current iron/copper vein Y limits: `COPPER` `0..50`, `IRON` `-60..-8`, both hardcoded in vanilla
   `OreVeinifier.VeinType` and reused unmodified by `PresetNoiseRouterData.java:138-139`;
2. measure vein occurrence in FreeTerraForged depths — not yet done; requires the same
   probe-extension work as standard ores, targeting the vein noise functions rather than a
   `PlacedFeature`;
3. decide whether the roles should remain vanilla-bottom-oriented or expand;
4. preserve noise topology and gap behavior;
5. avoid conflating noise veins with standard placed blobs — confirmed structurally distinct
   systems, not just conceptually distinct;
6. add separate diagnostics.

Potential configuration:

```text
adaptiveStandardOres = true
adaptiveNoiseOreVeins = false   # until separately implemented
```

---

## 14. Testing plan

### 14.1 Presets — use real, currently-retained fixtures, not invented ones

| Fixture                                         | worldDepth                                    | worldHeight      | Real measured role in this plan                                                                                                   |
| ----------------------------------------------- | --------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `vanilla-depth-maximum-ocean`                   | 64 (default)                                  | 384 (default)    | §4's "reference" run — **already 1.35× diluted for top-relative ores** despite being the closest thing to "vanilla-like"          |
| `shallow-depth-mountain-control`                | 16                                            | 384              | §4's "shallow" run — bottom-relative ores measured _denser_ than vanilla                                                          |
| `deep-world-ocean-stress`                       | 624                                           | 384              | not yet run against ore features; recommended next real-run target                                                                |
| `maximum-vertical-range-cave-decoration-stress` | 1024                                          | 1024             | §4's "extreme" run — up to 13× measured dilution                                                                                  |
| `short-top-world`                               | base (overrides only `dimension_type` height) | —                | §8.3's preset-vs-real-dimension divergence risk; already used for a real, currently-passing crash-regression check (§15, Phase 0) |
| the `archipelago/*` set                         | feature-specific                              | feature-specific | out of scope for ore work per their own fixture metadata ("do not include in unrelated default matrices")                         |

Add biome sizes 50/225/900 and custom sea level/ocean depth as scenario-level overrides where the
existing fixture system supports it, rather than inventing new fixtures.

### 14.2 Mod stacks — real source now available locally for verification

`games/minecraft/reference/sources/1.21.1/mods/` (gitignored, persistent across sessions) now holds
real, checked-out source for `create` (`mc1.21.1/dev`), `biomesoplenty` (`1.21.1`),
`regionsunexplored` (`21.1`), and `lithostitched` (`1.21`). Real, currently-published mod jars for
an actual live integration run (not just source reading) still need to be fetched into
`games/minecraft/investigation-state/mod-cache/jars/` (created but currently empty) — this plan
scopes that as a Phase 3 action (§15) rather than doing it as part of this rewrite, per the same
reasoning as `plans/biome-fixing-plan.md`'s phased empirical gates: source-level verification was
completed now; live multi-mod integration runs are a distinct, larger action appropriately scoped to
its own phase.

- vanilla only — real telemetry obtained (§4);
- Create — source fully verified (§5.1); live integration run pending real jar fetch;
- Biomes O' Plenty + TerraBlender — source fully verified (§5.2); live integration run pending;
- Regions Unexplored + Lithostitched — source fully verified and the dependency relationship
  corrected (§5.3); live integration run pending;
- Create + BOP + RU — pending;
- a hand-authored weighted ore datapack — pending;
- a custom-feature ore test mod — pending;
- a geology mod replacing stone hosts — pending;
- a modifier that removes vanilla ores and adds replacements — pending.

### 14.3 Assertions

Inactive features are not adapted; removed features are not resurrected; replacement features are
not double-run; custom filters still execute; Create's disable-worldgen config still prevents zinc
(mechanism confirmed real, §5.1 — not yet exercised live); biome-scoped profiles remain
biome-scoped; source target rules remain unchanged; source exposure values remain unchanged;
vanilla-height presets remain unchanged or statistically equivalent (redefine "vanilla-height" per
§4.2's finding that RTF's own default is not literally vanilla-height); expanded presets show
expected vertical coverage; unknown features are preserved; Fabric and NeoForge final feature graphs
agree where expected; generation remains deterministic across restarts and thread schedules.

### 14.4 Statistical method

Use fixed seeds and large sample regions — §4 used one seed (`3216933670`) and one 256-chunk window;
this is sufficient to confirm the _mechanism_ (anchor type determines dilution direction and
magnitude, precisely) but is not yet a statistically representative claim about typical realized
density across terrain types, which requires multiple seeds and multiple regions per §3.13's
terrain-volume gate, and requires §11.2's block-write instrumentation to exist at all.

For each profile, compare: attempts per chunk; successful deposits per chunk (blocked on §11.2); ore
blocks per chunk (blocked on §11.2); ore blocks per solid host volume (blocked on §11.2); Y
histogram (available now, §11.1); biome histogram (available now, §11.1); exposed-block fraction
(blocked on §11.2).

Report confidence intervals or at minimum sample sizes and variance. Do not rely on one screenshot —
or, per this plan's own updated standard, do not rely on one 256-chunk sample either; §4's numbers
are real and reproducible but explicitly single-seed.

---

## 15. Phased implementation checklist

**Read before starting**: this mirrors `plans/biome-fixing-plan.md`'s phase-gate structure. Do not
advance to the next phase until the current phase's gate is satisfied with real, reproducible
evidence — not a re-read of this document.

### Phase 0 — Reconfirm baseline (already substantially executed for this revision)

- [x] Confirm the FreeTerraForged submodule commit and re-verify `file:line` citations —
      `a154b1c6c3a6198a7c184f31387b64ff17271d11`, verified throughout §3-§13 above.
- [x] Re-run the two existing surface-rescue crash-regression scenarios live, confirming the recent
      height-adaptation crash fix (commit `20f3049`) still holds on current source:
      `bash     tooling/squinch mc-investigate scenario \       .squinch/.../rtf-cave-rescue-short-top-crash.toml --json     tooling/squinch mc-investigate scenario \       .squinch/.../rtf-cave-rescue-tall-deep-no-regression.toml --json     `

      Both returned `"terminal_state": "pass"` for both steps, on both fixtures, at the time of this
      revision.

- [x] Clone real third-party mod source into a persistent, gitignored, reusable cache rather than
      re-fetching per session:
      `bash     games/minecraft/reference/sources/1.21.1/mods/\       {create,biomesoplenty,regionsunexplored,lithostitched}     `

      This sits alongside the existing vanilla mapped source at
      `reference/sources/1.21.1/official/`, under the same already-gitignored
      `games/minecraft/reference/` tree (no new `.gitignore` entry needed) — `official/` names the
      vanilla mappings set for a given Minecraft version, and `mods/` is the equivalent sibling
      namespace for third-party mod source at that same version. Each mod clone is
      `--depth 1 --filter=blob:none` with sparse-checkout limited to worldgen-relevant paths —
      shallow specifically so `.git` stays a few hundred KB to a couple MB regardless of the mod's
      real commit history (a non-shallow `blob:none` clone of Create's repository, for example,
      pulled 5469 commits and 28MB into `.git` despite fetching almost no blob content). **To pick
      up a newer release from the mod, delete the directory and re-clone from scratch with the same
      recipe — do not `git fetch`/`git pull` an existing shallow clone**, which would either fail
      against a shallow history or start accumulating commits back into it; re-cloning is equally
      cheap and is the only way to guarantee no old commit is retained alongside the new one. See
      `.agent-docs/games/minecraft/README.md` for the exact command sequence.

- [ ] Fetch real, published release jars for Create, Biomes O' Plenty, Regions Unexplored, and
      Lithostitched (Fabric and NeoForge, matching versions actually tested by the FreeTerraForged
      maintainer per §5.2's PR #154 citation where available) into
      `games/minecraft/investigation-state/mod-cache/jars/` for live multi-mod integration runs. Not
      done as part of this revision — scoped to Phase 3 below, since it is a materially larger and
      slower action than source cloning and this revision's priority was closing the
      measurement-tool gap (§4.3) and verifying the vanilla+FreeTerraForged core claims first.
- [x] Run real telemetry against real vanilla ore features on three real fixtures spanning
      shallow/default/extreme world depth (§4). Reproduction:
      `bash     tooling/squinch mc-investigate scenario \       .squinch/.../ore-plan-verification-reference.toml --json     tooling/squinch mc-investigate scenario \       .squinch/.../ore-plan-verification-shallow.toml --json     tooling/squinch mc-investigate scenario \       .squinch/.../ore-plan-verification-extreme.toml --json     `

      These three scenario files were authored for this revision and are currently present under
      `.squinch/games/minecraft/mods/FreeTerraForged/investigations/`; promote them to the permanent
      naming convention (`rtf-ore-*.toml`) if kept long-term, mirroring `rtf-biome-palette.toml`'s
      pattern.

**Gate**: satisfied for this revision — real crash-regression confirmation, real mod source
available locally, real ore dilution telemetry obtained. Not yet satisfied: real jars, multi-mod
live runs, block-write instrumentation.

### Phase 1 — Close the block-write measurement gap (blocking; do this before any adaptation code)

- [ ] Add block-write telemetry for standard ore features, per §11.2: either a mixin into the shared
      `OreFeature`/`Feature<OreConfiguration>` placement path (covers vanilla and any mod reusing
      vanilla's `OreFeature`, but not Lithostitched's independent reimplementation) or a mixin into
      `LevelChunkSection.setBlockState` gated by an active-ore-feature thread-local marker (covers
      both, and any future conforming custom ore feature that writes through the same primitive).
      Prefer the broader `LevelChunkSection.setBlockState` hook given Lithostitched ships its own
      independent `OreFeature` (§3.9, §5.3) that a narrower vanilla-only hook would miss.
- [ ] Re-run all three §4 scenarios with the new instrumentation and confirm nonzero block writes
      are now observed for at least `ore_coal_upper` on all three fixtures (a true zero here, after
      the fix, would itself be a real and important finding requiring investigation, not an expected
      outcome).
- [ ] Extend the reachability-census-style reporting this plan's §11.3 warnings list already
      anticipates ("declared preset worldHeight/worldDepth diverges from real dimension bounds")
      with an actual runtime check comparing `WorldSettings.Properties` against the real
      `ChunkGenerator`/`LevelHeightAccessor` bounds, exercising it against the `short-top-world`
      fixture specifically (§8.3) to confirm the check fires there.

**Gate**: block writes are measurable for standard ore features on at least one real fixture, and
the preset-vs-real-dimension divergence check fires correctly on `short-top-world`.

### Phase 2 — Standard ore discovery (no generation changes)

- [ ] Index final active `minecraft:ore` and `minecraft:scattered_ore` profiles per §10.1, reading
      real dimension bounds rather than declared preset fields (§8.3).
- [ ] Explicitly detect and report Create's `create:layered_ore` and Lithostitched's `OreFeature` as
      recognized-but-custom (§7.4), using the real type identifiers confirmed in §3.9/§5.1/§5.3.
- [ ] Report support status per §7; make no generation changes.

### Phase 3 — Live multi-mod integration verification

- [ ] Fetch real release jars into `games/minecraft/investigation-state/mod-cache/jars/` for Create,
      Biomes O' Plenty, Regions Unexplored (with its hard Lithostitched dependency, §5.3), and
      TerraBlender/Biolith (already dev dependencies of FreeTerraForged itself).
- [ ] Run a real Fabric and NeoForge dev server with each mod individually, then in combination, and
      re-run the §4-style telemetry against each mod's real ore placed features (Create's
      `create:zinc_ore`, BOP's inherited vanilla ores, any Regions Unexplored ore content), using
      the now-closed block-write instrumentation (Phase 1) to get real success-rate numbers, not
      just candidate-range numbers.
- [ ] Confirm Create's `ConfigPlacementFilter` genuinely prevents zinc placement when Create's
      worldgen config is disabled, live, not just by reading the source (§5.1).
- [ ] Confirm BOP's glowshroom `Y=255` hardcoded ceiling (§5.2) is reproducible live and is not
      affected by any FreeTerraForged height adaptation applied to unrelated ore features in the
      same run.

### Phase 4 — Conservative vertical adaptation

- [ ] Support a small set of recognized height-provider/anchor patterns per §8.1, informed directly
      by §4's measured behavior per anchor shape (bottom-relative-to-bottom-relative needs no
      adaptation at all; bottom-relative-to-absolute and top-relative both need it, in opposite
      directions depending on preset).
- [ ] Preserve total attempts by default (§9); instrument realized density using Phase 1's
      now-working block-write telemetry.
- [ ] Preserve all other semantics; default unknown/external profiles to inherit.
- [ ] Re-run §4's three fixtures with adaptation enabled and confirm the measured dilution ratios
      converge toward parity with vanilla (or a documented, deliberate density-policy target), using
      `mc-investigate compare --expect different` between pre- and post-adaptation commits.

### Phase 5 — Mod validation (repeat Phase 3's real runs with adaptation enabled)

- [ ] Create; BOP; RU/Lithostitched; replacement datapacks; loader parity.
- [ ] Confirm none of Phase 3's real, mod-specific findings (config-disabled filter, glowshroom
      hardcoded ceiling) regress once adaptation is enabled.

### Phase 6 — Density calibration

- [ ] Analyze attempt versus realized-block loss using Phase 1's instrumentation across multiple
      seeds and terrain types (§14.4), not the single-seed sample in §4.
- [ ] Decide whether one capped global compensation policy is justified, using real multi-seed data
      rather than the single-seed illustration in §4.

### Phase 7 — Vanilla noise veins

- [ ] Separate design and implementation, per §13; build the equivalent of §11.1's probe extension
      targeting the vein noise functions directly rather than a `PlacedFeature`, since veins are not
      placed features at all.

### Phase 8 — Optional exterior exposure policy

- [ ] Separate feature and review, per §12.

---

## 16. Suggested configuration

Keep configuration narrow and preset-scoped.

```json
{
  "oreGeneration": {
    "adaptiveStandardOres": true,
    "densityPolicy": "PRESERVE_TOTAL_ATTEMPTS",
    "adaptiveNoiseOreVeins": false,
    "diagnosticLogging": false
  }
}
```

Possible density values for future use:

```text
PRESERVE_TOTAL_ATTEMPTS
BALANCED
PRESERVE_VERTICAL_DENSITY
```

Do not expose dozens of ore-specific fields in the FreeTerraForged preset.

---

## 17. Completion criteria

The standard-ore work is complete when:

1. final active standard ores are indexed after composition, using real dimension bounds (§8.3,
   §10.1);
2. standard and custom profiles are classified accurately, including the two confirmed real custom
   types (`create:layered_ore`, Lithostitched `OreFeature`);
3. supported vertical transformations are documented;
4. vanilla-height behavior remains stable — **and "vanilla-height" is defined against measured
   reality (§4.2), not assumed to be FreeTerraForged's own default preset**;
5. expanded worlds no longer have accidental profile dilution or unreachable added volume for
   supported cases, measured against §4's real baseline numbers, not re-estimated;
6. biome restrictions, target rules, exposure, size, step, and custom filters remain intact;
7. Create zinc is validated end to end, live, not only by source reading (Phase 3);
8. BOP biome-scoped vanilla ore behavior is validated live (Phase 3);
9. RU/Lithostitched replacements are not double-transformed, live (Phase 3);
10. unsupported systems are preserved and clearly reported;
11. vanilla large noise veins are explicitly reported as separate (confirmed structurally separate,
    §5.4);
12. deterministic and performance tests pass on Fabric and NeoForge;
13. **block-write realized-density instrumentation exists and is exercised** (§4.3, §11.2, §15
    Phase 1) — this is a new completion criterion this revision adds, because without it, criteria 5
    and 7-9 cannot actually be verified, only assumed.

---

## 18. Non-goals

The first ore project should not include: a per-ore GUI; arbitrary user-authored distribution
curves; automatic conversion to long geological seams; automatic biome reassignment; automatic
target-tag expansion; automatic support for every custom feature; retrogen; equal resource density
in every terrain type; replacement of Lithostitched; global cancellation of placed features;
automatic "fixes" for profiles whose authorial intent is unknowable.

---

## 19. Recommended roadmap wording

```markdown
#### Improve Ore Generation in Expanded Worlds

> Depends on biome reachability and final biome feature-graph diagnostics for reliable QA of
> biome-scoped ores (see biome-fixing-plan.md).
>
> Real telemetry against FreeTerraForged's own default preset already shows measurable vertical
> dilution for standard ores before any deliberately "tall" or "deep" setting is touched — up to 13x
> on the most extreme currently-retained stress fixture — and shows that a naive "preserve total
> attempts" policy can also over-concentrate resources on shallow-depth presets, not only dilute
> them on deep ones.
>
> Before writing adaptation code, close a confirmed measurement gap: no existing tool can currently
> see realized ore block placement, because standard ore features write blocks through a code path
> (`LevelChunkSection.setBlockState`) the existing placement-telemetry probe does not hook.
>
> Add a conservative adaptive layer for active standard `minecraft:ore`/`minecraft:scattered_ore`
> profiles:
>
> - inspect the final post-modifier biome feature graph, reading real dimension bounds rather than
>   declared preset fields (a preset/real-dimension divergence has already caused one real crash in
>   adjacent height-adaptation logic, PR #168);
> - recognize standard vertical placement semantics, informed by measured per-anchor-type dilution
>   behavior rather than an illustrative estimate;
> - adapt only supported height distributions to FreeTerraForged world bounds;
> - preserve biome scope, generation step, counts, configured-feature size, target rules,
>   air-exposure behavior, custom placement filters, and modifier order;
> - inherit externally authored or custom profiles unchanged, including two confirmed real custom
>   ore feature types (Create's `create:layered_ore`, Lithostitched's `OreFeature`);
> - emit diagnostics for unsupported, out-of-bounds, diluted, duplicated, or biome-unreachable
>   profiles;
> - audit vanilla noise-router iron/copper veins separately (confirmed hardcoded, structurally
>   separate from placed-feature ores).
>
> A per-ore configuration GUI, retrogen, and universal custom-feature support are out of scope.
```

---

## 20. Environment and reproduction notes

- **Persistent mod source cache**: `games/minecraft/reference/sources/1.21.1/mods/` holds real,
  working-tree checkouts of `create` (`mc1.21.1/dev`), `biomesoplenty` (`1.21.1`),
  `regionsunexplored` (`21.1`), and `lithostitched` (`1.21`), each a `--depth 1 --filter=blob:none`
  clone with sparse-checkout limited to the paths this document actually cites. This sits alongside
  the existing vanilla mapped source at `reference/sources/1.21.1/official/`, under the same
  already-gitignored `games/minecraft/reference/` tree — no new ignore rule was needed. The
  `--depth 1` matters: an earlier non-shallow attempt at this same set of clones pulled
  5469/717/186/51 commits and 28M/31M/6.2M/944K into `.git` respectively despite `blob:none`; redone
  shallow, the same four clones total 6.4M with a single commit each. To pick up a path not
  currently checked out, or a newer commit from the mod, **delete the directory and re-clone from
  scratch** with the same recipe — do not `git fetch`/`git pull` a shallow clone in place;
  re-cloning is equally cheap here and is the only way to avoid accumulating history back into it.
- **Persistent jar cache**: `games/minecraft/investigation-state/mod-cache/jars/` exists but is
  currently empty; Phase 3 (§15) populates it with real release artifacts for live integration
  testing.
- **Verification scenario TOMLs** authored for this revision:
  `.squinch/games/minecraft/mods/FreeTerraForged/investigations/ore-plan-verification-{reference,shallow,extreme}.toml`,
  each pointing the existing `placement-telemetry` probe pack at real vanilla ore feature IDs over a
  256-chunk window at seed `3216933670`. These reused the existing probe pack unmodified; no new
  mixin or probe code was written for this revision, since the ore-write instrumentation gap (§4.3,
  §11.2) is scoped as Phase 1 future work, not retrofitted into this rewrite.
- Raw JSON output from all real scenario runs referenced in §4/§15 Phase 0 was captured during this
  revision; regenerate with the commands in §15 Phase 0 rather than treating any cached copy as
  durable evidence, since `retention = "discard"` on these scenarios means the underlying world
  directories are not retained between runs.

---

## 21. Primary references

### FreeTerraForged

- [PR #151 — NeoForge biome modifier mutability](https://github.com/ETcodehome/FreeTerraForged/pull/151)
- [PR #152 — Underground biome climate and banding](https://github.com/ETcodehome/FreeTerraForged/pull/152)
- [PR #154 — Dynamic cave feature placement and selector composition](https://github.com/ETcodehome/FreeTerraForged/pull/154)
  (body fetched via `gh api`, confirms the real BOP glowshroom `Y=255` example and the real
  BOP/GlitchCore/TerraBlender test versions cited in §5.2)
- [PR #168 — Fix surface rescue crash on worlds shorter than vanilla height](https://github.com/ETcodehome/FreeTerraForged/pull/168)
  — real, current precedent cited in §8.2, re-verified live in §15 Phase 0
- `PresetNoiseRouterData.java`, `UndergroundBiomeBanding.java` — see `plans/biome-fixing-plan.md`
  for full citations
- `net/minecraft/data/worldgen/placement/OrePlacements.java`,
  `net/minecraft/world/level/levelgen/OreVeinifier.java`,
  `net/minecraft/world/level/levelgen/feature/OreFeature.java`,
  `net/minecraft/world/level/levelgen/VerticalAnchor.java` — mapped vanilla source,
  `games/minecraft/reference/sources/1.21.1/official/src/`
- `games/minecraft/investigations/reterraforged/probes/placement-telemetry/` — existing,
  reused-unmodified telemetry probe (§4, §11.1)
- `games/minecraft/investigations/reterraforged/fixtures/{vanilla-depth-maximum-ocean,shallow-depth-mountain-control,deep-world-ocean-stress,maximum-vertical-range-cave-decoration-stress,short-top-world}/`

### Create

- `games/minecraft/reference/sources/1.21.1/mods/create` (branch `mc1.21.1/dev`, real current HEAD)
- `src/generated/resources/data/create/worldgen/{placed_feature,configured_feature}/{zinc_ore,striated_ores_overworld,striated_ores_nether}.json`
- `src/main/java/com/simibubi/create/infrastructure/worldgen/{AllBiomeModifiers,ConfigPlacementFilter,LayeredOreFeature,LayeredOreConfiguration}.java`

### Biomes O' Plenty

- `games/minecraft/reference/sources/1.21.1/mods/biomesoplenty` (branch `1.21.1`)
- `common/src/main/java/biomesoplenty/biome/BOPOverworldBiomes.java`

### Regions Unexplored / Lithostitched

- `games/minecraft/reference/sources/1.21.1/mods/regionsunexplored` (branch `21.1`, confirms
  Minecraft `1.21.1` and a hard `modImplementation` dependency on Lithostitched)
- `games/minecraft/reference/sources/1.21.1/mods/lithostitched` (branch `1.21`, confirms Minecraft
  `1.21.1`)
- `dev/worldgen/lithostitched/worldgen/feature/OreFeature.java`, `OreConfig.java`
