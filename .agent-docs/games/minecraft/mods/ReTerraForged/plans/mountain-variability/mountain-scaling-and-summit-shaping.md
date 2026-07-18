# RTF Mountain Scaling And Summit Shaping

## Incorrect Earlier Approaches

Earlier tall-world work made two bad assumptions:

- Mountains needed a tall-world density projection to exceed Y 256.
- Summit shape could be fixed by remapping the final density/height transfer.

Those assumptions were wrong. RTF source terrain can already produce `cell.height > 1.0`, so
mountains can exceed Y 256 while the terrain model scale remains capped at 256 for preset
compatibility. The observed external mod cutoff with Hybrid Aquatic/Lithostitched was not proof of
an RTF mountain height cap.

Do not bring back:

- `TallTerrainProjection`
- `world.tallTerrain`
- built-in tall-world projection presets
- private density/depth bypasses
- automatic tall-world mountain-width multipliers
- ocean-depth config or ocean-populator behavior changes on this branch

## Current Approach

This branch keeps the architectural/correctness fixes and moves mountain art controls into source
terrain:

- use registered density graph functions instead of private bypasses
- keep per-chunk max-height estimation instead of forcing full-world chunk generation height
- keep `terrainModelHeight()` as the capped RTF model height name
- improve the existing `terrain.mountains.horizontalScale` control
- add one mountain source setting, `terrain.mountains.summitSpread`

The intent is that tall worlds use normal preset controls. Height remains controlled by existing
vertical/base/global scale settings. Width remains the existing mountain horizontal scale. Summit
profile is controlled by the new summit spread setting.

## Horizontal Scaling

`terrain.mountains.horizontalScale` is the only user-facing mountain width control. This branch
makes it apply more coherently to feature-scale mountain noise instead of only parts of the mountain
system.

In `Heightmap.make(...)`, the outer mountain-chain mask now uses the mountain horizontal scale:

- worley mask period: `1000 * horizontalScale`
- non-legacy mask period: `1000 * 2.25F * horizontalScale`
- large mask warp period: `333 * horizontalScale`
- large mask warp strength: `250.0F * horizontalScale`

In `Populators`, mountain source generators now scale broad feature components:

- `makeMountains`: ridge period and large warp period/strength
- `makeMountains2`: cell period, large warp period/strength, surface period
- `makeMountains3`: cell period, large warp period/strength, surface period, terrace modulation
  period, terrace mask period
- `makeFancy`: erosion radius scales with mountain horizontal scale

Small local detail is intentionally not all scaled. For example, some blur or fine scaler noise
stays fixed so increasing mountain width does not simply smear all texture. At
`horizontalScale = 1.0`, output should stay as close to previous behavior as the refactor allows.

## Summit Shaping

`terrain.mountains.summitSpread` is an optional mountain terrain setting:

```json
"mountains": {
  "horizontalScale": 1.0,
  "summitSpread": 0.0
}
```

The default is `0.0`, which skips summit shaping and preserves old preset behavior.

The implementation is source-terrain shaping, not a final density projection. Each mountain
generator computes its normalized mountain height, then calls `spreadSummit(...)` before vertical
scaling and before/around fancy erosion.

The shaping only affects the upper part of the mountain height curve:

- values at or below `summitStart = 0.55F` are unchanged
- values above that threshold are normalized to `0..1`
- an exponent derived from `summitSpread` broadens the upper curve
- the shaped upper curve is mapped back into `summitStart..1`

In code terms:

```java
float exponent = 1.0F - summitSpread * 0.55F;
upper = clamp((height - summitStart) / (1.0F - summitStart), 0.0F, 1.0F);
spread = pow(upper, exponent);
height = threshold(height, height, summitStart + spread * (1.0F - summitStart), summitStart);
```

Higher `summitSpread` makes upper mountain forms broader and less needle-like. It is not intended to
be the main way to make mountains taller; use vertical scale/base scale/global scale for height.
