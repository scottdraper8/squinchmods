# Shared RTF QA Presets

Canonical datapack presets used across ocean depth, structure placement, biome climate, and
archipelago investigations live in `presets/` beside this document. Prefer these copies over
Modrinth exports or archived test worlds.

Common QA seed:

```text
3216933670
```

## Canonical archives

| Name                                          | Archive                                         | SHA-256                                                            |
| --------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test                          | `presets/very-deep.zip`                         | `58c875c2b2b93b8b7b997b9a666c4aad93afe94e8f55e66f93b0ad49e9a1b5ca` |
| Goldilocks (vanilla-depth max ocean)          | `presets/goldilocks.zip`                        | `b1487bcf52fdb3e27a2a76ea5e7f505f7e925aa00e63ce7f9b9f4bd44fb7c878` |
| Mountain, `worldDepth=16`                     | `presets/mountain-worldDepth16.zip`             | `546aeab25e0d61b59638ff1da81d661f2817c50c5886e54b0297523d31ce1c68` |
| Very deep, archipelago enabled                | `presets/very-deep-archipelago.zip`             | `558410784d1aee8813ce9bc2738a123a1092f5a8f32e6b0fb5586e89fbe0d3ac` |
| Goldilocks, archipelago enabled               | `presets/goldilocks-archipelago.zip`            | `1729dbb6f2ecda0f2a7cb9d62989928acfd39d1768bac17dae204fbddaf82024` |
| Mountain `worldDepth=16`, archipelago enabled | `presets/mountain-worldDepth16-archipelago.zip` | `c464b7de710bdd4ee15e14498ae8a8f4b9fb7fe70d35131591bfcfc94f087c84` |
| Cave feature distribution stress              | `presets/cave-feature-distribution-stress.zip`  | `9d0b3782c0ac623bdd0927ba696eb848b313aba9a9b6821e51d0204efa3d530c` |

Every archive contains the RTF preset at:

```text
data/reterraforged/reterraforged/worldgen/preset/preset.json
```

## Preset roles

### Very deep

Relevant values:

```text
oceanDepth=677
worldDepth=624
worldHeight=384
seaLevel=63
lavaLevel=-575
spawnType=CONTINENT_CENTER
```

Use it for deep ocean floors, vertical cave-biome bands, long structure-placement ranges, and the
deepest archipelago shelf case.

The published biome-banding screenshot measurements used an earlier copy of the same archive before
`lavaLevel` was explicit. It decoded to `-54` and had SHA-256
`0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837`. Lava level does not feed biome
climate, so the recorded biome profiles remain valid; exact open-air and nearby decoration counts
should be rechecked in new worlds created with the current archive.

### Goldilocks

Relevant values:

```text
oceanDepth=117
worldDepth=64
worldHeight=384
seaLevel=63
spawnType=CONTINENT_CENTER
```

`117` is the deepest legal ocean at the otherwise default `worldDepth=64`:
`seaLevel + worldDepth - 10`. Use it for vanilla-depth maximum-ocean controls, low-floor structure
placement, and compressed underground-band behavior.

### Mountain `worldDepth=16`

This is the extreme shallow-world control (`min_y=-16`, dimension height `400`). Use it to verify
that structure and biome systems respond to terrain-provided headroom below mountains rather than
assuming a globally deep dimension.

### Cave feature distribution stress

This is the canonical preset for cave placement, decoration-density, and extended-height performance
work:

```text
oceanDepth=900
worldDepth=1024
worldHeight=1024
seaLevel=63
lavaLevel=-975
build range=-1024..1023
```

It retains the ordinary cave generators and uses amplified but legal terrain shaping:

```text
globalHorizontalScale=1.5
globalVerticalScale=1.25
mountains.baseScale=1.5
mountains.horizontalScale=2.0
mountains.verticalScale=3.0
mountains.weight=5.0
```

With seed `3216933670`, the 256-chunk window from blocks `19872 -128` through `20127 127` contains a
high Biomes O' Plenty Spider Nest. Verified decoration reaches Y 848, with feature biome-filter
passes through Y 914. The screenshot cavern is around `19893 591 -126`.

Use this preset by default for future cave-feature investigations. Retain Goldilocks and the exact
`-64..319` control when a vanilla-height density baseline is required.

### Archipelago variants

The three `-archipelago` archives match their base presets except that
`island.enableArchipelago=true` with default `IslandSettings`. They are the required starting matrix
for the unfinished cellular archipelago rewrite:

- very deep tests shelf scaling across the largest elevation change;
- Goldilocks provides the vanilla-depth maximum-ocean control; and
- `worldDepth=16` tests shallow-world behavior.

Use the known seed area around `(230250, 163350)` as one regression window, but do not expect exact
island coordinates to survive the planned cellular placement rewrite.

## Headless QA

Use `games/minecraft/tooling/dev-server` and the workflow in
`../../../live-worldgen-investigation-howto.md`. Start with a fresh world whenever the generator or
preset changes, and copy the selected archive into the world's `datapacks/` directory.

For monument-placement controls, both the shallowest historical export and very-deep preset located
the reference monument at:

```text
[-256, ~, -256]
```

Archived datapacks under `fabric/run/world.*` are run artifacts, not canonical inputs.

## Related references

- Ocean depth design: `../plans/ocean-depth/ocean-depth-design.md`
- Structure placement: `../plans/ocean-depth/trial-chambers-and-ocean-structures.md`
- Monument measurements: `../plans/ocean-depth/monument-placement-research.md`
- Underground biome retrospective:
  `../plans/biome-climate-banding/biome-climate-banding-investigation.md`
- Archipelago findings: `../plans/ocean-depth/island-interaction-investigation.md`
- Archipelago rewrite contract: `../plans/ocean-depth/archipelago-follow-up-scope.md`
