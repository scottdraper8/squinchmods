# Configurable Ocean Depth — Design

Shipped on `feat/configurable-ocean-depth` (PR #97). RTF never had configurable ocean depth before
this; this doc describes what was actually built and why, as a reference for anyone touching this
code later — not an implementation plan or a log of how the work proceeded.

## What it is

One user-facing setting: **Ocean Depth** (`oceanDepth`), a positive integer field on
`WorldSettings.Properties`. It sits in the GUI directly below World Depth, grouping the two "depth"
sliders together (World Depth, Ocean Depth) while Sea Level and Lava Level stay grouped as the two
"Y level" sliders below them.

Default value is **63**, matching vanilla RTF's un-configurable behavior (deepest floor at Y=0, 63
blocks below the default sea level of 63). Loading an old preset with no `oceanDepth` field decodes
to this default via `optionalFieldOf("oceanDepth", 63)` and reproduces the original floor range
exactly.

Only one slider is exposed, deliberately. RTF already has "Deep Ocean" and "Shallow Ocean" sliders
under Control Points (geographic zone boundaries) — a second set of sliders with "ocean" in the name
under a different section would invite confusion. Shallow ocean depth, deep ocean minimum depth, and
noise scale are all derived from `oceanDepth` rather than exposed separately; splitting them out is
easy to add later if it turns out to be needed, and premature to expose up front.

## Derived values

Given `oceanDepth`:

- **shallowOceanFloor**: `max(7, oceanDepth / 9)` blocks below sea level, so the shallow-to-deep
  transition stays proportionally reasonable at extreme depths instead of producing a jarring cliff.
  At the default this is 7, identical to pre-feature upstream behavior.
- **deepOceanMinDepth**: `max(8, oceanDepth / 3)`, the shallowest deep-ocean floor point.
- **deepOceanMaxDepth**: `oceanDepth` directly, the deepest canyon point.
- **Floor clamp**: bounded by `Levels.min` (computed from `worldDepth`) so the floor can never
  exceed the world bottom.

`Populators.makeDeepOcean` builds the actual floor noise from these values (hills and canyons via
Perlin noise, blended, warped, then clamped to the derived range). The noise's horizontal wavelength
and warp strength are scaled by `oceanDepth / DEFAULT_OCEAN_DEPTH` (see the comment next to
`DEFAULT_OCEAN_DEPTH` in `WorldSettings.java`) — this was a fix added later in the same PR after
very deep presets were found to produce noise steep enough to be unclimbable, not part of the
original design above.

## Slider bounds

The slider is a positive integer, range 0-256 (mirroring the World Depth slider). The GUI clamps the
effective value to `seaLevel + worldDepth - 10` (`WorldSettingsPage.java`) so the floor can never
exceed the world bottom, with a 10-block safety margin. That margin turned out to be too small to
reliably guarantee room for underground biomes and structures near the floor in some presets — see
`trial-chambers-and-ocean-structures.md` and `biome-climate-banding-investigation.md` for the
investigation that followed from it and the fixes/open issues that came out of it.

## Backward compatibility

- Default `oceanDepth=63` reproduces the pre-feature floor range and land/mountain layout exactly
  for any preset that doesn't set it.
- No density router changes, so land/mountain generation away from oceans is unaffected.
- The coast populator is unchanged; it always clamps at sea level regardless of `oceanDepth`.

## Files touched

`WorldSettings.java` (field, codec, `DEFAULT_OCEAN_DEPTH` constant), `Levels.java` (world-bottom
awareness), `OceanPopulator.java` (configurable floor clamp), `Populators.java` (`makeDeepOcean`/
`makeShallowOcean` derivation and noise scaling), `Heightmap.java` and `GeneratorContext.java`
(wiring), `Preview2D.java`/`Preview3D.java` (preview rendering), `WorldSettingsPage.java` (slider),
`RTFTranslationKeys.java`/`RTFLanguageProvider.java`/`en_us.json` (GUI text).

Deliberately left untouched: `PresetNoiseRouterData.java`, `MixinRandomState.java`,
`DecorateSnowFeature.java`, `ErodeFeature.java` — none of these needed to change for this feature,
and touching them would have pulled in unrelated tall-world/fixNether history.

## Out of scope

Tall-world mountain projection, configurable strata/deepslate, configurable shorelines/beaches,
noise scale or shallow depth as separate user-facing settings, and a dedicated `WorldSettings.Ocean`
class were all considered and deliberately left out — a single derived slider covers the real need
without adding surface area that would need its own QA and documentation.
