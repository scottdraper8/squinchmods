# Underground Settings

This page controls underground cave shapes and which biomes appear below the surface. Cave shapes
decide where air-filled spaces form. Underground biome settings decide what those spaces look like
and which surface biomes can continue underground.

## Cave shapes

| Screenshot | Value                         | Description                                                                                                            |
| ---------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
|            | **Entrance Cave Chance**      | Changes how often larger cave openings form near the surface.                                                          |
|            | **Cheese Cave Depth Offset**  | Sets the depth boundary where broad, roomy caves can begin to form.                                                    |
|            | **Cheese Cave Chance**        | Changes how much broad, roomy space is carved underground.                                                             |
|            | **Spaghetti Cave Chance**     | Changes how often narrow, winding tunnels form.                                                                        |
|            | **Noodle Cave Chance**        | Changes how often long, thin tunnels form.                                                                             |
|            | **Large Ore Veins**           | Turns Minecraft's larger underground ore deposits on or off.                                                           |
|            | **Ravine Carver Probability** | The editor shows and saves this slider. Current generation ignores its value, so changing it has no effect on ravines. |

Each cave chance slider controls a different cave shape. Underground biome settings control biome
choices. Cave generation also uses the world height and depth chosen on [World Settings](world.md).

## Underground biomes

These settings choose biome regions for underground spaces. The cave-shape settings above control
where caves form.

| Screenshot | Value                                 | Description                                                                                                                                                                    |
| ---------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
|            | **Underground Biome Horizontal Size** | Sets how wide underground biome regions are. Larger values make broader areas. It also affects ordinary surface biomes that continue underground.                              |
|            | **Underground Biome Vertical Size**   | Sets how tall those underground areas can be. The maximum is limited by the world's height and depth.                                                                          |
|            | **Cave Biome Coverage**               | Sets what share of underground space uses cave biomes. At 0%, none uses cave biomes. At 100%, they fill eligible underground areas.                                            |
|            | **Cave Climate Influence**            | Sets how strongly temperature and moisture guide cave biome choice. At 0%, climate has no influence. Higher values favor a closer climate match.                               |
|            | **Vertical Cave Biome Banding**       | Spreads cave biomes across broad bands at different underground heights. Turning it off confines them to their usual depths. Surface biome placement is controlled separately. |

Newly generated chunks use the updated underground biome settings.
