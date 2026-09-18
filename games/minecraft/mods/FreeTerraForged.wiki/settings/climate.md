# Climate Settings

This page shapes the temperature and moisture patterns used to choose surface biomes. It also
controls the size and irregularity of biome regions. The [Terrain](terrain.md) and [World](world.md)
pages control land shape.

## Temperature and moisture

Temperature and moisture are separate maps. Together they help determine which biome fits each
location. The controls use the same terms in both maps.

| Screenshot | Value               | Description                                                                                                                                                                          |
| ---------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|            | **Seed Offset**     | Rolls a different temperature or moisture pattern. Each map has its own button.                                                                                                      |
|            | **Scale**           | Sets the width of the warm/cool bands or wet/dry patches. Higher values make broader patterns. Lower values make them change over shorter distances.                                 |
|            | **Falloff**         | Changes how much of the map sits near moderate values versus the warm/cold or wet/dry extremes. Higher values make the transition sharper and leave the extremes to smaller areas.   |
|            | **Min** and **Max** | Set the lowest and highest allowed values for that map. Moving them closer together narrows the climate range. Moving them farther apart widens it.                                  |
|            | **Bias**            | Shifts the map toward one end of its range. Positive values favor warmer or wetter readings. Negative values favor cooler or drier readings. The Min and Max still limit the result. |

These settings shape map patterns. Temperature Scale controls how broadly warm and cool areas
spread.

## Biome shape

| Screenshot | Value                   | Description                                                                                                                                                                   |
| ---------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Surface Biome Size**  | Sets the typical width of surface biome regions. Higher values make the regions larger. Lower values make them smaller.                                                       |
|            | **Macro Noise Size**    | Changes the size of a broad background pattern. Current world generation uses it for a rare Mushroom Fields biome on islands and one terrain adjustment around strong rivers. |
|            | **Biome Warp Size**     | Sets how broad the bends are when biome regions are warped.                                                                                                                   |
|            | **Biome Warp Strength** | Sets how far those bends can shift biome sampling. Higher values make region outlines more strongly warped.                                                                   |

## Biome edge shape

These settings add irregularity near biome boundaries. Region size is set above. The edge settings
change which climate is sampled near a boundary.

| Screenshot | Value          | Description                                                                                                                                              |
| ---------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Type**       | Chooses the pattern used for the edge detail. The menu includes smooth, cellular, ridged, repeating, and random styles.                                  |
|            | **Scale**      | Sets the size of that pattern. Higher values make broader features. Lower values make finer detail.                                                      |
|            | **Octaves**    | Sets how many layers of detail are combined for pattern types that support layered detail. More layers can make the pattern more detailed.               |
|            | **Gain**       | Sets how much each added detail layer contributes.                                                                                                       |
|            | **Lacunarity** | Sets how much smaller each added detail layer becomes.                                                                                                   |
|            | **Strength**   | Sets the maximum distance, in blocks, that the climate sample can be shifted near a region edge. Higher values can make the edge detail more noticeable. |

The pattern names are technical, so the biome preview is the clearest way to compare their
appearance. Newly generated chunks use the updated climate settings.
