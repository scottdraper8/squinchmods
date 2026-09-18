# River Settings

This page controls river layouts, channels, widened river sections, wetlands, and effects on water
particles and boats. River layout and terrain controls shape the land. **River Flow Dynamics**
controls particles and boat movement. For how rivers, local water, and wetlands relate, see
[Hydrology and Shore Geometry](../concepts/hydrology-and-shore-geometry.md).

## River layout

| Screenshot | Value           | Description                                                                                      |
| ---------- | --------------- | ------------------------------------------------------------------------------------------------ |
|            | **Seed Offset** | Rolls a different river layout from the same world seed.                                         |
|            | **River Count** | Sets how many main rivers are laid out for each continent. Branch rivers join these main routes. |

## Main rivers and branches

Main rivers are the larger routes across a continent. Branch rivers are smaller channels that join
them. Each group has the same six controls, so you can tune the main channels and their branches
separately.

| Screenshot | Value                                       | Description                                                                                                                                                                                               |
| ---------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Bed Depth**                               | Sets how far the central channel cuts below the water line, measured in blocks.                                                                                                                           |
|            | **Min Bank Height** and **Max Bank Height** | Set the range used for the channel's banks and valley floor. Generation uses the gap between these values to set the vertical span.                                                                       |
|            | **Bed Width**                               | Sets the width of the central river channel.                                                                                                                                                              |
|            | **Bank Width**                              | Sets how far the river's banks and surrounding valley extend beyond the central channel.                                                                                                                  |
|            | **Fade**                                    | Sets how far along a river the channel and banks take to reach their full profile. Lower values reach the full profile sooner. Higher values extend the smaller starting profile farther along the river. |

## Lakes

These controls widen and deepen a river where it crosses flatter terrain. This creates broad pools
along the river's route.

| Screenshot | Value                                             | Description                                                                                                                 |
| ---------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
|            | **Chance**                                        | Sets how often a qualifying flatter section is widened.                                                                     |
|            | **Min Start Distance** and **Max Start Distance** | Set where widening begins and ends along the river. Values from 0 to 1 represent fractions of the route.                    |
|            | **Depth**                                         | Controls how much deeper the widened section can become.                                                                    |
|            | **Size Min** and **Size Max**                     | Set scale factors for how much the widened section expands.                                                                 |
|            | **Min Bank Height** and **Max Bank Height**       | The editor shows and saves both values. Current generation ignores them, so changing either value has no effect on terrain. |

## Wetlands

Wetlands are broad, low, mounded areas alongside rivers.

| Screenshot | Value                         | Description                                                                            |
| ---------- | ----------------------------- | -------------------------------------------------------------------------------------- |
|            | **Chance**                    | Sets how often a wetland is added along a river.                                       |
|            | **Size Min** and **Size Max** | Set wetland length along the river. Generation chooses the wetland's width separately. |

## River flow dynamics

These switches control particles and boat movement where FTF river flow data is available.

| Screenshot | Value                    | Description                                                                                                                                        |
| ---------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Flow Particles**       | Shows moving water particles above flowing river water.                                                                                            |
|            | **Flow Pushes Boats**    | Lets river current push boats while they are in flowing water.                                                                                     |
|            | **Navigable Waterfalls** | Lets a boat rise while submerged in a flowing area, helping it travel up waterfalls. This only takes effect when **Flow Pushes Boats** is also on. |

Newly generated chunks use the updated river and wetland settings.
