# Terrain Shaping and Region Selection

## Source terrain ownership

Source populators own distinct parts of terrain character before final density projection:

- vertical/base/global scale own terrain height;
- mountain horizontal scale owns broad mountain width;
- summit shaping owns the upper mountain curve;
- continent settings own landmass footprint and distribution; and
- island settings own archipelago terrain.

Private density-router bypasses create a second terrain path that datapacks and other mods cannot
observe or modify consistently. RTF functions in the registered graph remain visible to all graph
consumers.

## Region pipeline

RTF assigns terrain populators through Voronoi-style regions. `RegionModule` supplies region
identity and `RegionSelector` maps that identity into a weighted populator array.
`RegionLerper`/Blender then smooth transitions between neighboring terrain systems and continuous
mountain overlays.

The weighted array length is part of deterministic layout. Adding more entries—even variants of an
existing terrain type—changes `identity → index` mapping and remaps unrelated cells. A wrapper can
contain internal variants while occupying one weighted entry and leaving the outer mapping intact.

Raw `terrainRegionId` can be correlated with the selector slice that chose the current populator.
Direct reuse can give every region of one terrain type the same subvariant; hashing decorrelates the
subvariant decision from the outer selector slice.

Continuous overlays have no cell identity. A seeded spatial selector supplies spatial ownership. A
coordinate offset derived from region scale shifts the sample away from structural noise zeros at
the origin.

## Seed ownership

Construction order and `Seed.next()` calls are world layout. Adding a new noise draw in the middle
of an established sequence moves all downstream noise.

Optional variants can preserve baseline layout through this construction:

- construct the baseline/center path with the original seed sequence;
- construct extra variants from isolated offset seeds; and
- the option does not advance the main sequence.

The same principle applies when adding beach/material noises or helper fields to `Heightmap`.

## Mountain shaping

Broad mountain horizontal scale affects ridge and cell periods, large warp period and strength,
surface period, terrace modulation and masks, chain masks, and broad erosion radius. Fine detail can
remain fixed, which prevents scale changes from simply blurring all texture.

Summit shaping affects the upper normalized curve and is a no-op at its default. Final density
remapping changes already-composed terrain and tends to create vertical walls.

## Archipelago geometry

The current archipelago representation mixes macro island shape, edge transition, and pointwise
continent fading in alpha fields. A field used as a threshold is not automatically a distance.

Physical slope and clearance are expressible through distance in blocks as a first-class value. A
cellular island model exposes stable cell identity, center, density decision, shoreline distance,
and size/shape values. Per-island continent eligibility produces whole-island decisions, while a
rapidly changing pointwise fade can clip a single island differently at adjacent samples.

Domain warp amplitude relative to wavelength and cell size determines whether a field can fold. Warp
strength by itself does not establish that property.
