# Terrain Coordinates and Levels

RTF passes terrain through several coordinate spaces. Most vertical bugs come from treating a
normalized value, block coordinate, dimension size, or local water offset as interchangeable.

## Dimension bounds

`worldHeight` is the build space above Y 0. `worldDepth` is the distance below Y 0, so the intended
minimum is `-worldDepth`. Minecraft dimension height/minimum constraints still apply, including
codec requirements such as 16-block alignment.

`ChunkGenerator.getGenDepth()` is a size, not an absolute maximum Y. The corresponding absolute
upper coordinate is `minY + genDepth`.

## Terrain model scale

`WorldSettings.Properties.terrainModelHeight()` intentionally uses `min(worldHeight, 256)`. It is
the compatibility scale for normalized terrain cells, continent and ocean layout, biome-adjacent
values, and previews. It is not a terrain ceiling.

`Cell.height` can exceed `1.0`; final terrain can therefore rise above Y 256 while the model scale
remains 256. Replacing the model scale with full `worldHeight` changes every consumer of the
normalized model and moves horizontal layout as well as height.

## Height headroom

A source control that increases terrain height (added variance, a taller variant, amplified relief)
can push generated height past a preset's actual configured ceiling (`worldHeight`), independent of
the terrain model's compatibility scale — the raw model can predict a peak higher than the dimension
allows even though the model itself was never clamped. A hard clamp at that ceiling produces a
visible flat cut across every affected column. A continuous, headroom-aware compression — starting
some margin below the ceiling and asymptoting toward it rather than stopping dead — preserves relief
and avoids introducing a new discontinuity at the point compression begins. Deriving the
compression's limits from the preset's real `worldHeight` keeps taller presets from being normalized
toward a shorter default.

## `Levels`

`Levels` is the conversion boundary between preset/dimension properties and normalized terrain.
Values crossing it fall into these categories:

- absolute block Y;
- block distance/depth;
- normalized absolute height;
- normalized height difference; or
- an offset from sea/local water level.

`Levels.scale(...)` maps normalized differences to block units. The active minimum and water fields
provide dimension-specific values in place of vanilla constants such as `-64`, `0`, `63`, `256`, or
`320`.

## Water values

Global sea level and local river/wetland water surface are distinct. `cell.riverWaterLevel` is an
absolute normalized local water surface in current river/shore integration. Adding global
`levels.water` converts it into a double-offset value.

`cell.waterTable` is hydrology input, not necessarily a block Y or final water surface. The relevant
`ContinentalHydrology` function combines it with continent scale modifiers to produce a resolved
surface.

## Ocean depth

`oceanDepth` is a block distance below sea level, not an absolute Y. Its derived floor depths are:

```text
shallow = max(7, oceanDepth / 9)
deep minimum = max(8, oceanDepth / 3)
deep maximum = oceanDepth
```

The compatibility default is `63`, decoded through an optional preset field. At that value the
derived floor range matches the original fixed ocean model.

The resulting absolute floor is bounded by the active world minimum. With a fixed horizontal ocean
noise scale, a larger vertical delta produces a steeper floor; proportional horizontal scale keeps
the slope relationship constant.

Ocean floor, coastline, archipelago shelf, and local river water are separate fields. A change in
one does not inherently define a scale change in the others.

## Climate depth

Minecraft biome climate depth changes at roughly `1/128` per block. An offset in climate depth is
therefore a physical vertical shift, not an arbitrary dimensionless tweak. Shared registered
surface-relative depth gives terrain and biome climate the same vertical meaning; separate functions
can give them different meanings.
