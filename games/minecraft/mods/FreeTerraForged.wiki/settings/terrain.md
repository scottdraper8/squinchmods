# Terrain Settings

This page shapes where different landforms appear and how tall, broad, or varied they are.
[Climate Settings](climate.md) controls the temperature and moisture patterns used to choose biomes.

## General terrain

| Screenshot | Value                       | Description                                                                                                                                                                |
| ---------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Seed Offset**             | Rolls a different terrain pattern from the same world seed.                                                                                                                |
|            | **Terrain Region Size**     | Sets how large the areas of each terrain style are. Larger values make broader regions.                                                                                    |
|            | **Global Vertical Scale**   | Makes landforms across the world taller or flatter. Uplift uses its own raised land height.                                                                                |
|            | **Global Horizontal Scale** | Makes landforms across the world broader or more tightly spaced.                                                                                                           |
|            | **Fancy Mountains**         | Adds an extra shaping pass to mountains for more detailed forms. Turning it off can save some processing.                                                                  |
|            | **Legacy Mountain Scaling** | Uses an older formula for mountain width and height. This changes how the Mountain sliders are interpreted.                                                                |
|            | **Mountain Variety**        | Adds differences between mountain regions. At zero, ranges use the same settings. Higher values allow more variation in height, width, starting elevation, and ruggedness. |

## Terrain styles

| Screenshot | Value                | Description                                                                                                        |
| ---------- | -------------------- | ------------------------------------------------------------------------------------------------------------------ |
|            | **Weight**           | Adjusts this style's chance of selection relative to the others. A value of zero removes the style from selection. |
|            | **Base Scale**       | Raises or lowers the style's underlying height.                                                                    |
|            | **Vertical Scale**   | Makes the style's hills and peaks taller or flatter.                                                               |
|            | **Horizontal Scale** | Makes its landforms broader or more closely packed.                                                                |

The style groups are listed below.

| Screenshot | Value           | Description                                                                                                                                                                                             |
| ---------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Steppe**      | Broad, mostly flat open ground with gentle height changes.                                                                                                                                              |
|            | **Plains**      | Open, gently rolling lowlands.                                                                                                                                                                          |
|            | **Hills**       | Rounded, rolling rises and dips.                                                                                                                                                                        |
|            | **Dales**       | Softer rolling hills and valleys.                                                                                                                                                                       |
|            | **Plateau**     | Raised areas with broad tops and stepped slopes.                                                                                                                                                        |
|            | **Badlands**    | More broken, ridged, and terraced ground.                                                                                                                                                               |
|            | **Torridonian** | A mix of flatter ground and rough, terraced hills.                                                                                                                                                      |
|            | **Mountains**   | Tall, rugged mountain ranges.                                                                                                                                                                           |
|            | **Volcano**     | Forms volcanic cones and their surrounding slopes. **Weight** affects how often they appear. The visible **Base Scale**, **Vertical Scale**, and **Horizontal Scale** sliders currently have no effect. |

When **Uplift** is selected on the [World Settings](world.md) page, the editor locks some height
controls to keep land above its raised continental floor.

Newly generated chunks use the updated terrain settings.
