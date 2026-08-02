# Minecraft World-Generation Reference

This wiki collects durable engineering knowledge about Minecraft Java Edition world generation. Its
pages are organized by mechanism rather than by investigation, branch, or mod.

## Topics

- [Extended-height worlds](Extended-Height-Worlds.md) — coordinate spaces, build bounds, normalized
  terrain models, and system-specific scaling.
- [Placed-feature vertical distributions](Placed-Feature-Vertical-Distributions.md) — candidate
  origins, density, fixed anchors, configured-feature bounds, and random-stream behavior.
- [Structure vertical placement](Structure-Vertical-Placement.md) — the placement authorities used
  by monuments, jigsaw structures, shipwrecks, ruins, and other vanilla structures.
- [Underground biome climate](Underground-Biome-Climate.md) — multi-noise depth behavior, vertical
  extension, surface-relative climate, and integration paths.

## Authority layers

Minecraft world generation contains several coordinate and authority layers:

1. dimension build bounds;
2. density or terrain-model coordinates;
3. biome climate coordinates;
4. placed-feature candidate coordinates;
5. configured-feature internal checks;
6. structure start, piece bounds, and post-processing coordinates; and
7. blocks and stored biomes in a finished chunk.

A value can be valid in one layer and invalid in another. Source-level lookup results describe the
lookup layer, while finished chunks describe stored world state. A feature origin inside the build
range says nothing about a configured feature's later acceptance checks.
