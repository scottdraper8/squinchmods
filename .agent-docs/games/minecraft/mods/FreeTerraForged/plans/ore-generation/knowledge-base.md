<!-- markdownlint-disable MD013 MD038 MD046 -->

# Ore Generation Knowledge Base

This is the current evidence-backed model for ore generation in FreeTerraForged. It is a current
state document, not a run history. Unless stated otherwise, evidence is from Minecraft `1.21.1`, FTF
baseline `908595b`, and the latest-stable stack in [`test-matrix.md`](test-matrix.md).

## How ore generation works

Ordinary placed-feature ore generation is evaluated in this order:

```text
dimension / generator
→ selected biome
→ final biome feature membership
→ decoration step and placed-feature modifiers
→ height provider and filters
→ configured ore feature
→ target-block rules and vein geometry
→ terrain volume, caves, exposure, and later writes
```

The final `BiomeGenerationSettings.features()` list is the input that matters at runtime. A
feature's registry entry is not enough: loader modifiers, biome-composition systems, datapacks, and
replacements can change final membership, order, or duplication.

`UNDERGROUND_ORES` is not an ore classifier. It also contains disks such as sand, clay, gravel, mud,
and calcite. Classification must use the configured-feature type and complete placement contract.

For `minecraft:ore`:

- the configured feature defines target rules and vein size;
- the placed feature defines count or rarity, horizontal distribution, height, and filters;
- the biome feature list defines where the feature can run;
- the feature can run successfully without writing a block;
- target material, terrain volume, cave exposure, and later writes determine realized blocks.

Therefore these are different measurements:

```text
candidate calls → biome passes → successful feature calls → actual block writes
```

The current telemetry records all four where the probe can observe them. Actual section block writes
are the realized-output metric.

## Vertical behavior

Vanilla 1.21.1 uses several different height contracts, including absolute, bottom-relative,
top-relative, uniform, and triangular ranges. Examples include coal above absolute Y 136, iron from
the bottom to absolute Y 72, redstone from the bottom to absolute Y 15, and diamond in a
bottom-relative triangular range.

FTF's existing dynamic height hook only recognizes the canonical uniform range from
`above_bottom(0)` to `absolute(256)`. It creates extension bands for that range. It does not inspect
ore target rules, classify `minecraft:ore`, or adapt the varied ordinary ore ranges. The current
ordinary ore behavior is therefore still vanilla-contract placement; no production ore adapter has
been implemented.

Large ore veins controlled by `CaveSettings.largeOreVeins` are a separate noise-router system. They
are not part of the ordinary placed-feature adapter.

The `oreCompatibleStoneOnly` setting is currently persisted and visible but has no effective
alternate tag branch in the source. It must not be treated as an active ore policy until separately
resolved.

## Current baseline measurements

The following are aggregate actual block writes in the current telemetry windows. The reference,
shallow, and extreme cases use 256 chunks; the standard and control cases use 64 chunks.

| Fixture                    |            Coal upper |             Iron small |                 Diamond |               Redstone |
| -------------------------- | --------------------: | ---------------------: | ----------------------: | ---------------------: |
| Reference                  |                   `0` |    `2,078` (`-63..44`) |     `1,410` (`-63..12`) |    `3,784` (`-63..15`) |
| Shallow                    |                   `0` |    `3,484` (`-15..52`) |     `1,437` (`-15..51`) |    `4,604` (`-16..15`) |
| Extreme                    |                   `0` | `2,840` (`-1023..-85`) | `1,608` (`-1023..-946`) | `3,539` (`-1021..-97`) |
| Standard survey            |                   `0` |     `303` (`-63..-19`) |      `338` (`-63..-15`) |     `607` (`-63..-13`) |
| Seed `12345`, inland       |     `41` (`134..139`) |    `1,052` (`-15..71`) |       `342` (`-15..61`) |    `1,128` (`-15..15`) |
| Seed `987654`, inland      |  `1,433` (`134..183`) |    `1,100` (`-15..72`) |       `360` (`-15..61`) |    `1,123` (`-15..15`) |
| Seed `12345`, mountain     | `10,680` (`133..205`) |    `1,099` (`-15..72`) |       `338` (`-15..62`) |    `1,158` (`-15..14`) |
| Seed `12345`, cave control | `19,568` (`133..654`) |  `1,276` (`-1018..69`) |   `421` (`-1023..-947`) |  `1,392` (`-1021..14`) |

The controls establish the important result: candidate counts remain largely fixed while realized
writes change with biome, host material, terrain height, caves, and available vertical volume. A
density multiplier cannot be chosen from candidate counts alone.

The standard survey also observed non-ore disks and ordinary ore features in the same decoration
step. This is why the implementation must classify feature contracts rather than rewrite an entire
generation step.

## Final feature graph census

The current census walks every registered biome's final placed-feature list on both loaders.

| Metric                         | Fabric | NeoForge |
| ------------------------------ | -----: | -------: |
| Biomes inspected               |     64 |       64 |
| Registered placed features     |    285 |      285 |
| Active unique feature IDs      |    199 |      199 |
| Active feature occurrences     |  2,755 |    2,755 |
| Duplicate final memberships    |      0 |        0 |
| Inactive registry entries      |     86 |       86 |
| Same-contract candidate groups |     34 |       34 |

The active namespace counts are 2,520 Minecraft occurrences and 235 FTF occurrences. The census
therefore sees FTF's generated features in the final graph, not only vanilla registry entries.

The current graph proves no duplicate final memberships. The 86 inactive registry entries are
removal candidates, but a final-only census cannot identify whether a missing entry was removed,
replaced, or never selected by a given biome. The 34 same-contract groups are also candidates, not
replacement proof. A definitive replacement census requires before/after modifier provenance.

## Ownership matrix

The clean ownership question is whether a companion's ore feature is standard and additive or a
custom system that must remain outside the first FTF adapter.

| Producer                 | Current observation                                                                               | Classification                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Vanilla                  | Standard `minecraft:ore` and `minecraft:scattered_ore` features with ordinary placement contracts | First supported contract                                                    |
| Create zinc              | `create:zinc_ore`; 5,249 writes; standard ore feature with `create:config_filter`                 | Standard ore plus custom filter; requires filter-aware classification       |
| Create striated ores     | `create:striated_ores_overworld`; 35,049 writes; custom layered feature                           | Custom system; preserve and report                                          |
| Immersive Ores vibranium | `immersiveores:vibranium_ore_placed`; 1,322 writes on both loaders                                | Additive conventional producer                                              |
| Immersive Ores geode     | Active feature; 0 writes in the current window                                                    | Active custom/conditional path; absence of writes is not absence from graph |
| Regions Unexplored       | Vanilla `minecraft:ore` redstone-large; 607 deepslate-redstone writes                             | Composition case; not clean ownership evidence                              |
| Biomes O' Plenty         | No stable 1.21.1 BOP/TerraBlender/GlitchCore chain; beta composition run passes                   | Composition case; exclude from stable ownership evidence                    |
| Mekanism                 | Not yet run in the current matrix                                                                 | Later custom-system case                                                    |
| Immersive Engineering    | Not yet run in the current matrix                                                                 | Later custom-system case                                                    |

Fabric and NeoForge Immersive Ores runs agree for the observed conventional vibranium path. Create
is intentionally NeoForge-only in the current matrix because that is the selected release/runtime
case.

## Composition boundaries

Regions Unexplored `0.6.2` with Lithostitched `1.7.13` now starts and reaches placement on Fabric
with Fabric API `0.116.15+1.21.1`. Its `minecraft:ore` feature writes 607 deepslate redstone blocks
in the current diagnostic window. This proves the current dependency stack is compatible; it does
not make RU an ownership-isolation control because RU changes biome composition.

Biomes O' Plenty is different: the compatible `1.21.1` BOP, TerraBlender, and GlitchCore artifacts
are beta-only. The exact Fabric beta stack now passes the composition diagnostic on 81/81 chunks,
exposes 114 possible BOP biomes, and observes BOP's `glowing_grotto` underground case. The exact
NeoForge beta stack passes 81/81 preview-parity chunks with zero mismatches. This resolves the
acquisition and startup issue, but there is still no all-stable BOP runtime to add to the stable
matrix. Do not label these composition results stable ore evidence.

## Telemetry boundary

The probe observes direct `LevelChunkSection` writes used by vanilla `OreFeature`, in addition to
placement and feature-call telemetry. It does not yet split target-block rejection, air-exposure
rejection, or later-overwrite identity into separate counters. Custom features that write through a
different path may need additional instrumentation.

## Source evidence

- Vanilla feature contracts: mapped `OrePlacements.java` and `OreFeature` source.
- FTF height behavior: `DynamicHeightRangePlacement.java` and `MixinHeightRangePlacement.java`.
- FTF stone setting: `MiscellaneousSettings.java` and `RTFBlockTagsProvider.java`.
- Create ownership: `create:zinc_ore`, `create:striated_ores_overworld`, and the Create
  feature/filter sources in the acquired `mc1.21.1/dev` checkout.
- Immersive Ores ownership: the exact Fabric and NeoForge release artifacts and current run
  summaries.
- Full graph and placement evidence: run manifests and summaries under
  `games/minecraft/investigation-state/runs/`, with current run IDs in `test-matrix.md`.
