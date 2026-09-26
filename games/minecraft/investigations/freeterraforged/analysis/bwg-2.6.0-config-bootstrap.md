# BWG 2.6.0 existing-config bootstrap boundary

## Result

Oh The Biomes We've Gone 2.6.0 for Fabric 1.21.1 has a deterministic existing-config failure that is
independent of FreeTerraForged. A first launch with no `config/biomeswevegone/world_generation.json`
starts and generates a new world. Once that file exists, a launch that creates a new world registers
each BWG vanilla biome feature twice and Minecraft aborts chunk feature ordering.

This is a third-party bootstrap/config-lifecycle boundary. An FTF compatibility coordinator must not
deduplicate or suppress the resulting feature graph.

## Inputs

- BWG `2.6.0-Fabric` (`ICd7oSmA`)
- Fabric API `0.116.15+1.21.1`
- TerraBlender `4.1.0.8`
- CorgiLib `5.0.0.9`
- Oh The Trees You'll Grow `5.3.2`
- GeckoLib `4.9.2`
- Minecraft `1.21.1`, Fabric Loader `0.19.3`
- no FTF classes or resources on the launch classpath

The no-FTF launch reused the repository's Loom Minecraft runtime while filtering both FTF platform
outputs and the FTF common development JAR from the classpath. Only the catalog artifacts above were
installed as runtime mods.

## Runtime observations

- First launch, absent config, new world: one `BWGBiomeModifiers.init`, 25 Fabric biome
  modifications, server ready after spawn generation.
- Existing config, existing world: two `BWGBiomeModifiers.init` calls and 50 modifications; the
  already-generated world opens.
- Existing config, new world: two initialization calls and 50 modifications, followed by
  `Feature order cycle found` for `minecraft:windswept_savanna` while generating features.

The focused FTF diagnostic installs `{}` as an existing config. It independently reports 25 distinct
duplicate placements without an observer failure, including adjacent copies of
`biomeswevegone:vanilla/flower_default` in `minecraft:windswept_savanna`, immediately before
Minecraft reports that biome's feature-order cycle. The primary BWG graph and spatial scenarios
instead declare that generated config absent and restore the prior file after the run, so their
default first-start measurements are repeatable.

## Source cause

At BWG tag `2.6.0`, commit `ef8dd6981a6a14f582fbed590a5b7375a8c99b67`:

1. `ConfigLoader.loadConfig` constructs `defaultValue` with `clazz.getConstructor().newInstance()`.
2. When a config exists, it later returns `GSON.fromJson(defaultJson, clazz)`, constructing a second
   `BWGWorldGenConfig`.
3. The instance field `individual_vanilla_additions` invokes `getVanillaPlacedFeatureAdditions()`.
4. That method calls `BWGBiomeModifiers.init()` on every construction.
5. `BIOME_MODIFIERS_FACTORIES` is a `Reference2ObjectOpenHashMap`; each `init()` creates new,
   equal-but-not-identical `ResourceLocation` keys, so the second initialization retains duplicate
   modifier values.
6. `VanillaCompatFabric.registerBiomeModifiers()` registers every retained value with Fabric's biome
   API. Minecraft's feature sorter then sees the same placed-feature identity twice in a biome and
   reports a cycle.

Relevant retained source is under
`games/minecraft/reference/sources/1.21.1/mods/oh-the-biomes-weve-gone/`.
