# Surface Settings

These controls adjust how exposed slopes are covered with grass, soil, loose gravel, and rock. They
are part of the surface erosion decorator. For river channels and hills, see
[River Settings](river.md).

## Erosion decorator

| Screenshot | Value                 | Description                                                                                                       |
| ---------- | --------------------- | ----------------------------------------------------------------------------------------------------------------- |
|            | **Erosion Decorator** | Turns the surface material changes on or off. Turning it off disables the other controls on this page.            |
|            | **Rock Steepness**    | Sets how steep a slope must be before it gets exposed rock. Higher values reserve bare rock for steeper slopes.   |
|            | **Scree Steepness**   | Sets the slope threshold for loose gravel. Higher values limit it to steeper slopes.                              |
|            | **Dirt Steepness**    | Sets the slope threshold for dirt and ground-cover changes. Higher values mean fewer slopes reach that threshold. |

The editor keeps these thresholds in order. Rock must be at least as high as Scree. Scree must be at
least as high as Dirt. Together they create a gradual progression from gentler ground to scree and
then exposed rock as a slope gets steeper.

## Height transitions

The height controls are offsets from the generator's baseline. On uplifted continents, that baseline
rises with the landmass, so the settings follow the raised terrain.

| Screenshot | Value             | Description                                                                                                                                                                                    |
| ---------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Rock Min**      | Moves the height where surfaces become fully rocky. A higher setting keeps soil and other cover on higher ground. A lower setting brings rock farther down the landscape.                      |
|            | **Rock Variance** | Widens or narrows the uneven transition into rocky surfaces around Rock Min. Higher values make the change less uniform across the landscape.                                                  |
|            | **Dirt Min**      | Moves the height band where sloped ground changes between dirt and grass cover and more exposed material. A higher value keeps that cover on higher ground. It must stay at or below Rock Min. |
|            | **Dirt Variance** | Widens or narrows the uneven transition around Dirt Min. Higher values make the change less uniform.                                                                                           |

Newly generated chunks use the updated surface settings.
