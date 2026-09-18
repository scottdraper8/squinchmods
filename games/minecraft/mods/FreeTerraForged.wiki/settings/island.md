# Island Settings

This page shapes the small island groups, called **archipelagos**, that can appear away from the
main continents. They are blended into ocean and coastal terrain. Turn **Spawn Archipelagos** on to
use the other controls on this page. When it is off, the archipelago layer stays disabled.

## Where islands can appear

| Screenshot | Value                   | Description                                                                                                                               |
| ---------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Spawn Archipelagos**  | Adds or removes the island layer. It is the master switch for the rest of this page.                                                      |
|            | **Island Density**      | Controls how often island shapes pass the local density check. Higher values make islands more likely within areas that are open to them. |
|            | **Landmass Percentage** | Controls how much of the ocean is open to island landmasses. Higher values make the broad eligible areas more common or larger.           |
|            | **Average Island Size** | Sets the broad scale of the island shapes. Higher values make larger islands.                                                             |

Island Density and Landmass Percentage affect different steps. Density controls how readily islands
form inside an eligible area. Landmass Percentage controls how much ocean is eligible.

## Island height and shape

| Screenshot | Value                          | Description                                                                                                                                                   |
| ---------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Island Height**              | Sets how much the island rises above its surroundings. It scales the main island relief.                                                                      |
|            | **Island Base Scale**          | Raises or lowers the broad interior of an island before its taller features are added.                                                                        |
|            | **Vertical Feature Scale**     | Scales the height of island peaks and other vertical features.                                                                                                |
|            | **Smoothness**                 | Sets the horizontal size of several island details. Higher values make those shapes broader and smoother. Lower values allow smaller, tighter details.        |
|            | **Mountain Influence**         | Controls how strongly mountain peaks affect islands.                                                                                                          |
|            | **Mountain Scale**             | Changes the shape of mountain peaks, from rounder forms toward more concentrated, steep peaks. It also changes the amount of small variation near their tops. |
|            | **Mountain Horizontal Scale**  | Sets the horizontal size of mountain features independently of the island's overall scale.                                                                    |
|            | **Volcanism Influence**        | Controls how often volcanic peaks appear across island interiors.                                                                                             |
|            | **Volcanism Scale**            | Controls the height of the sharp volcanic peaks when they appear.                                                                                             |
|            | **Volcanism Horizontal Scale** | Sets the horizontal size of volcanic features independently of the island's overall scale.                                                                    |

## Underwater edge and beaches

| Screenshot | Value              | Description                                                                                                                                   |
| ---------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Offshore Depth** | Sets the depth of the shallow underwater shelf around an island. This is separate from the overall ocean depth on the [World](world.md) page. |
|            | **Shallows Width** | Sets how wide the underwater shelf and shallow transition are around an island.                                                               |
|            | **Beach Coverage** | Controls how much of the island's outer edge is classified as beach. Higher values extend the beach zone farther inland.                      |

These controls shape terrain. Newly generated chunks use the updated island and coastline settings.
