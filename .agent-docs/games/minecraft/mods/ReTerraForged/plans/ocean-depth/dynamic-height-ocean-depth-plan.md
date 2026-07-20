# Configurable Ocean Depth Plan

## Status: 2026-06-27

Replaces the earlier ocean-depth plan. The branch has been renamed from
`fix/tall-world-ocean-scaling` to `feat/configurable-ocean-depth`. This is a feature, not a fix —
RTF never had configurable ocean depth.

**Superseded note (2026-07-19):** this plan's slider-clamp formula below (§ Slider bounds, § file 9)
is stale. The shipped clamp is `properties.seaLevel + properties.worldDepth - 10`
(`WorldSettingsPage.java:180`, confirmed) — a 10-block margin was added after this plan was written,
undocumented here or anywhere else until now. That flat margin is exactly the mechanism investigated
in `trial-chambers-and-ocean-structures.md` and `biome-climate-banding-investigation.md`: it's too
small to guarantee underground biomes/structures have room to exist near the floor in many presets
(see the extreme vs. Goldilocks preset comparison), and a formula-derived replacement is proposed
there (Fix Design Options, Option A) but not yet implemented. Treat everything below as the
_original_ design, not current behavior.

## Approach

**Reset to `1.21.1` and rebuild.** The existing commit (`deea518`) is majority throwaway: 7 of 19
changed files must be fully discarded (tall-terrain projection, fixNether reverts, version reverts),
5 must be rewritten (4 sliders → 1 slider, Ocean class → field on Properties), and only 6 are
partially salvageable. Writing the changes fresh is less work and less error-prone.

## Design

One user-facing setting: **Ocean Depth** (`oceanDepth`). A positive integer field on
`WorldSettings.Properties`. Placed directly below World Depth in the Properties section of the GUI,
matching its style — both are positive-integer depth values measured in Y units.

Layout order in Properties:

1. World Height
2. World Depth
3. Ocean Depth ← new
4. Sea Level
5. Lava Level

This groups the two "depth" sliders together (World Depth, Ocean Depth) and keeps the two "Y level"
sliders together (Sea Level, Lava Level).

Default value: **63** (matches vanilla RTF behavior where the deepest floor is at Y=0, which is 63
blocks below default seaLevel of 63).

Tooltip: "Controls the minimum y level of the deep ocean floor."

### Why one slider

- The old code had zero user control. One configurable value solves the problem.
- RTF already has "Deep Ocean" and "Shallow Ocean" sliders under Control Points (geographic zone
  boundaries). Adding more sliders with "ocean" in the name under a different section invites
  confusion.
- Shallow ocean depth, deep ocean min depth, and noise scale are all derivable from the max depth.
  Exposing them gives power users fractionally more control at the cost of making the feature harder
  to understand for everyone.
- Start with one. Split later if users ask.

### Slider bounds

The slider uses a positive integer, range 0–256. This mirrors the World Depth slider which is also a
positive integer depth value.

The callback dynamically clamps to `min(value, properties.seaLevel + properties.worldDepth)` so the
ocean floor can never exceed the world bottom. With default seaLevel=63 and worldDepth=64, the
effective max is 127. If the user increases worldDepth, the effective cap rises with it. The
slider's static range of 256 covers any realistic configuration.

### Derived values

Given `oceanDepth` (user-set, positive integer depth in Y units):

- **shallowOceanFloor**: `max(7, oceanDepth / 9)` blocks below sea level — proportional to
  oceanDepth so the shallow→deep transition stays natural at extreme depths. At default 63 this
  gives 7 (identical to upstream). At 200 this gives 22, preventing a jarring cliff between shallow
  and deep floors.
- **deepOceanMinDepth**: `max(8, oceanDepth / 3)` — the shallowest deep-ocean floor point. At the
  default of 63 this gives 21, producing hills that reach up to about Y=42. The ratio preserves
  approximately the same proportional floor variation as the old noise.
- **deepOceanMaxDepth**: `oceanDepth` directly — the deepest canyon point.
- **noiseScale**: hardcoded at 150 (matching old hardcoded perlin scale).
- **Floor clamp**: `levels.min` (computed from worldDepth). If
  `seaLevel - oceanDepth < -worldDepth`, the floor clamps at the world bottom.

## Files to change

All paths relative to `common/src/main/java/raccoonman/reterraforged/`.

### 1. `data/worldgen/preset/settings/WorldSettings.java`

Add to `Properties`:

- Field: `public int oceanDepth;`
- Codec: `Codec.INT.optionalFieldOf("oceanDepth", 63).forGetter((o) -> o.oceanDepth)`
- Add to constructor parameter list (after `lavaLevel`), constructor body, and `copy()`.

Do NOT add an `Ocean` class. Do NOT add `terrainModelHeight()` or any tall-terrain constants.

### 2. `world/worldgen/cell/heightmap/Levels.java`

Add:

- `public int worldDepth;`
- `public float min;`
- New constructor `Levels(int height, int depth, int seaLevel)` that computes
  `min = scale(-worldDepth)`.
- Old two-arg constructor delegates with `depth = 0`.

### 3. `world/worldgen/cell/terrain/populator/OceanPopulator.java`

Change the record to accept a `float minHeight` parameter:

- `public record OceanPopulator(Terrain terrainType, Noise height, float minHeight)`
- Keep existing two-arg constructor as convenience (minHeight = 0.0F for backward compat with coast
  populator).
- In `apply()`: clamp to `this.minHeight` instead of `0.0F`.

### 4. `world/worldgen/cell/terrain/Populators.java`

`makeDeepOcean(int seed, Levels levels, int oceanDepth)`:

- Derive minDepth from oceanDepth (oceanDepth / 3, minimum 8).
- Compute `lower = max(levels.water(-oceanDepth), levels.min)`.
- Compute `upper = max(levels.water(-minDepth), lower)`.
- Build hills noise mapped to `[lower, upper]`.
- Build canyon noise mapped to `[lower, canyonUpper]` where canyonUpper is between lower and upper.
- Keep perlin scale at 150, warp at 50, blend thresholds at 0.6/0.65.
- Return `OceanPopulator(DEEP_OCEAN, height, levels.min)`.

`makeShallowOcean(Levels levels, int oceanDepth)`:

- Shallow depth derived as `max(7, oceanDepth / 9)`.
- Use `levels.water(-shallowDepth)`.
- Pass `levels.min` as minHeight to OceanPopulator.

`makeCoast(Levels levels)`:

- Unchanged (uses `levels.water`, clamps at 0.0F via existing two-arg constructor — coast is at sea
  level, never negative).

### 5. `world/worldgen/cell/heightmap/Heightmap.java`

Change `Heightmap.make()`:

- `makeDeepOcean(ctx.seed.next(), ctx.levels, world.properties.oceanDepth)`
- `makeShallowOcean(ctx.levels, world.properties.oceanDepth)`

### 6. `world/worldgen/GeneratorContext.java`

Change Levels construction:

- `new Levels(properties.terrainScaler(), properties.worldDepth, properties.seaLevel)`
- This passes worldDepth so Levels can compute `min`.

### 7. `client/gui/screen/presetconfig/Preview2D.java`

Change Levels construction:

- `new Levels(properties.terrainScaler(), properties.worldDepth, properties.seaLevel)`

### 8. `client/gui/screen/presetconfig/Preview3D.java`

Same as Preview2D.

### 9. `client/gui/screen/presetconfig/WorldSettingsPage.java`

Add one slider in the Properties section after worldDepth (before seaLevel):

- `this.oceanDepth = PresetWidgets.createIntSlider(properties.oceanDepth, 0, 256,`
  `RTFTranslationKeys.GUI_SLIDER_OCEAN_DEPTH, ...)`
- Callback clamps: `Math.min(depth, properties.seaLevel + properties.worldDepth)` so the floor can
  never exceed the world bottom.
- Widget order: worldHeight, worldDepth, oceanDepth, seaLevel, lavaLevel.

No "Ocean" section label. No other ocean sliders.

### 10. `client/data/RTFTranslationKeys.java`

Add one key:

- `GUI_SLIDER_OCEAN_DEPTH = resolve("gui.slider.oceanDepth")`

### 11. `client/data/RTFLanguageProvider.java`

Add:

- `this.add(RTFTranslationKeys.GUI_SLIDER_OCEAN_DEPTH, "Ocean Depth");`
- Tooltip: `"Controls the minimum y level of the deep ocean floor."`

### 12. `resources/assets/reterraforged/lang/en_us.json`

Add the Ocean Depth entry and tooltip. This file is alphabetically sorted — place under `o`.

## Files NOT changed

These files must match upstream `1.21.1` exactly:

- `data/worldgen/preset/PresetNoiseRouterData.java` — no tall-terrain code
- `mixin/MixinRandomState.java` — upstream fixNether version
- `world/worldgen/feature/DecorateSnowFeature.java` — upstream fixNether version
- `world/worldgen/feature/ErodeFeature.java` — upstream fixNether version
- `gradle.properties` — upstream version `0.0.6004R1`
- `neoforge/src/main/resources/META-INF/neoforge.mods.toml` — upstream version

## Backward compatibility

- Old presets without `oceanDepth` load via `optionalFieldOf("oceanDepth", 63)`. Default 63
  reproduces the old floor range (Y=0 to ~Y=55 at standard settings).
- Shallow ocean floor remains 7 blocks below sea level at default.
- No density router changes means identical land/mountain behavior.
- Coast populator is unchanged.
- The `OceanPopulator` two-arg constructor preserves the 0.0F clamp for any external callers
  (coast).

## Execution steps

1. From `feat/configurable-ocean-depth`, hard-reset to `1.21.1`: `git reset --hard 1.21.1`

2. Apply changes to the 12 files listed above.

3. Hygiene:
   - `git diff --check 1.21.1` — no whitespace errors
   - `git diff --name-only 1.21.1` — only the 12 expected files
   - No `PresetNoiseRouterData.java` in the diff
   - No `MixinRandomState.java` in the diff
   - No tall-terrain constants anywhere

4. Build: `./gradlew clean build`

5. Commit with a focused message.

6. Do NOT push until user QA and approval.

## QA

1. Load an old preset with no `oceanDepth` field — should decode with default 63 and produce floors
   in the same range as upstream.
2. Increase `oceanDepth` to 128 with `worldDepth=128` — deep ocean floors should reach below Y=0.
3. Set `oceanDepth` to 0 — deep ocean should be nearly at sea level (effectively no depth).
4. Set `oceanDepth` higher than `seaLevel + worldDepth` — floor should clamp at world bottom, not
   crash.
5. Same seed with default `oceanDepth=63` should produce identical land/mountain layout compared to
   upstream.
6. Preview2D and Preview3D should render ocean depth changes.

## Out of scope

- Tall-world mountain projection
- Configurable strata / deepslate
- Configurable shorelines / beaches
- Noise scale or shallow depth as user-facing settings
- Separate `WorldSettings.Ocean` class
