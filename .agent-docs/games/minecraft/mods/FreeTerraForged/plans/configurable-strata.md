# Configurable Strata

Status: `feat/configurable-strata` requires deliberate integration with the current
`upstream/1.21.1` baseline. Product QA and the deepslate policy remain open.

The reusable material-layer and surface-rule model is described in
[`surface-rules-and-materials.md`](../wiki/concepts/surface-rules-and-materials.md). This plan keeps
the feature-specific open decisions and acceptance work.

## Remaining decisions

1. Decide whether deepslate transition depth is derived from `worldDepth` or explicitly configured
   by the preset.
2. Decide whether the WIP defaults intentionally improve existing behavior or preserve the old
   layer-count distribution unless the nested object is present.
3. Confirm whether all four material weights remain in the public editor or only stone weight is
   exposed initially.

## QA gate

- Compare the same seed across at least two layer-count configurations and measure band thickness.
- Compare material weights and measure generated stone/granite/andesite/diorite frequencies.
- Inspect exported `overworld.json` and verify the actual `freeterraforged:strata` rule contains the
  configured counts, depths, and weights.
- Verify old presets without the nested strata object load with the chosen compatibility default.
- Inspect shallow, default, and deep worlds for deepslate transition behavior.
- Exercise Fabric and NeoForge generated chunks, not only compilation and server startup.

Do not use `strataRegionSize` as a vertical thickness control and do not edit only the rock tag to
simulate weights.
