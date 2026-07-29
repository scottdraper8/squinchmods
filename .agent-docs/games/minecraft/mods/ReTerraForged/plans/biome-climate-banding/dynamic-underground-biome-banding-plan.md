# Dynamic Underground Biome Banding — Final Design Reference

The design is implemented. See `biome-climate-banding-investigation.md` for the complete
retrospective, validation evidence, screenshot coordinates, and rejected approaches.

## Invariants

- Surface and shallow biome selection use the original parameter list.
- Dynamic selection begins only at climate depth `1.1`.
- Band count and scale respond to configured world dimensions and Biome Size.
- Compatible modded cave biomes participate without hardcoded biome IDs.
- TerraBlender's positional region choice is preserved.
- Unknown registration schemes retain their original behavior.
- Actual chunk generation and standalone lookups receive the same RTF preset context.

## Candidate discovery

`UndergroundBiomeBanding` scans each climate parameter list for the compatibility signature used by
vanilla underground biomes:

- depth span `0.2..0.9` or point `1.1`; and
- weirdness left at `FULL_RANGE`.

Matching entries are grouped by biome in encounter order. Nonmatching entries remain untouched. This
intentionally supports convention-following mod registrations without guessing how arbitrary custom
placement systems should be redistributed.

## Depth layout

The usable dynamic depth ends at:

```text
(worldDepth + min(worldHeight, 256)) / 128
```

Band count derives from candidate count, usable depth, and Biome Size using square-root scaling,
with a maximum of 32. The layout compresses naturally in shallow terrain and expands in deep worlds.

Each candidate owns one non-overlapping weirdness regime. Candidate order rotates between regimes,
so a column that cannot fit every band does not always omit the same biome. Full-climate fallback
entries after the first transition band prevent one constrained candidate from winning every
remaining depth.

Nearest-neighbor selection across continuous weirdness values supplies the horizontal transition;
the parameter list does not need to be rebuilt per column.

## Horizontal scale

Underground shifted-noise frequency is:

```text
0.25 * 225 / biomeSize
```

The default `Biome Size=225` preserves the original `0.25` frequency exactly. Smaller settings
produce finer regions and more vertical bands; larger settings produce broader regions and fewer,
thicker bands.

## Integration paths

### Plain biome source

`MixinMultiNoiseBiomeSourceCache` lazily builds a banded list beside the original
`MultiNoiseBiomeSource`. `MixinClimateSampler` selects the original list below depth `1.1` and the
banded list at or beyond it.

### TerraBlender

`MixinParameterList` captures each populated TerraBlender region's original entries and builds a
parallel banded list. The existing uniqueness/region lookup runs first; banding selects from the
matching regional list rather than falling back to the default region.

### Chunk generation

Minecraft fills chunk biome palettes through `NoiseChunk.cachedClimateSampler()`. `MixinNoiseChunk`
propagates the active RTF preset to that sampler. `MixinRandomState` covers direct and standalone
sampling, but is not sufficient by itself.

## Safe compatibility boundary

The banding layer only narrows weirdness where a registration explicitly declared `FULL_RANGE`. It
does not reinterpret entries that already use weirdness or a nonstandard depth signature. Such
entries continue through their original biome-source/mod integration.

This means compatibility is automatic for the vanilla convention, not universal for every possible
custom biome-registration mechanism.
