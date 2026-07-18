# Configurable Ocean Depth (`oceanDepth` Setting)

> [!IMPORTANT] **Main idea:** This feature adds a single slider that controls how deep the ocean
> floor generates below sea level. The feature preserves default behavior out of the box and only
> changes ocean depth when the user opts in.
>
> The motivation behind this feature is to allow ocean floors to extend into the below-zero Y range
> when using increased world depth, which RTF does not currently support.

## 1. What is this?

A new `oceanDepth` slider in the World Settings properties section, shown below.

<!-- markdownlint-disable MD033 MD045 -->
<p align="center"><kbd><img width="90%" src="SCREENSHOT_SLIDER" alt="oceanDepth slider in World Settings"></kbd></p>
<!-- markdownlint-enable MD033 MD045 -->

The slider controls how many blocks below sea level the deep ocean floor can reach. It sits between
the World Depth and Sea Level sliders because it behaves like a depth value (blocks of distance),
not an absolute Y level.

- Default value is `63`, which matches vanilla RTF behavior (deepest ocean floor at Y=0 with a sea
  level of 63).
- The slider range is `10` to `seaLevel + worldDepth - 10`, giving a 10-block buffer on each end for
  bedrock and shallow water.
- The range updates dynamically if you change Sea Level or World Depth.

For example, with the defaults of `seaLevel: 63` and `worldDepth: 128`:

- `oceanDepth: 63` puts the deepest ocean floor at Y=0 (default, same as current RTF)
- `oceanDepth: 10` raises the ocean floor to a minimum of Y=53 (very shallow)
- `oceanDepth: 181` pushes the ocean floor down to Y=-118 (near the bottom of the world)

## 2. Why add it?

RTF currently hard-clamps ocean floor height at Y=0. This means even if you increase World Depth to
open up the below-zero Y range, oceans never take advantage of that space. The ocean floor is always
stuck at Y=0 at its deepest.

This was caused by a `Math.max(height, 0.0F)` clamp in the ocean populator that prevented any ocean
terrain from generating below the zero line.

With this setting, users who want deeper oceans (especially in tall worlds with increased world
depth) can push ocean floors into negative Y, and users who want shallower oceans can raise the
floor closer to sea level. The default value of 63 means nothing changes unless you want it to.

## 3. How does it work?

The `oceanDepth` value drives all ocean floor calculations:

- **Deep ocean** floor range is computed from `oceanDepth`. The deepest canyons can reach the full
  depth, while the shallowest parts of the deep ocean sit at roughly `oceanDepth / 3`.
- **Shallow ocean** floor depth is derived as `oceanDepth / 9`, keeping it proportionally shallower.
- Both are clamped so they never exceed the world's minimum Y level.

The existing deep ocean noise (perlin hills, canyons, warp, blend) is preserved. Only the vertical
range it maps onto changes. Shallow ocean remains a flat constant height. The horizontal placement
of ocean zones (controlled by the existing Deep Ocean and Shallow Ocean continent sliders) is
completely unaffected.

## 4. How to QA this?

### Default behavior (should be identical to current RTF)

1. Create a world with default settings (`oceanDepth: 63`, `seaLevel: 63`, `worldDepth: 0`)
2. Find a deep ocean biome and dive to the floor
3. The deepest point should be around Y=0, same as it always has been

[SCREENSHOT: Normal ocean floor at default settings]

### Shallow ocean floor

1. Create a world and set `oceanDepth` to `10` (or close to the minimum)
2. Find a deep ocean biome and dive
3. The ocean floor should be noticeably raised, sitting around Y=53

[SCREENSHOT: Raised ocean floor near sea level]

### Deep ocean floor (tall world)

1. Create a world with `worldDepth: 128` and push `oceanDepth` toward the maximum
2. Find a deep ocean biome and dive
3. The ocean floor should extend well into negative Y values

[SCREENSHOT: Ocean floor deep in negative Y range]

### Slider behavior

- Confirm the slider range updates when you change World Depth or Sea Level
- Confirm the slider cannot go below 10 or above `seaLevel + worldDepth - 10`
