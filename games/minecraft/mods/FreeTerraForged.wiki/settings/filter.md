# Filter Settings

These controls shape terrain during world generation. **Hydraulic Erosion** simulates small drops of
water moving downhill. They carry material away from higher ground and leave some in lower places.
**Smoothing** then softens nearby height differences.

## Hydraulic erosion

| Screenshot | Value                  | Description                                                                                                                                            |
| ---------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
|            | **Droplets Per Chunk** | Sets how many simulated water paths start in each chunk. More paths give erosion more opportunities to reshape the ground and require more processing. |
|            | **Droplet Lifetime**   | Sets how many steps each drop can travel before it stops. Longer paths can affect a larger area.                                                       |
|            | **Droplet Volume**     | Sets how much water each drop starts with. This affects how much loose material it can carry.                                                          |
|            | **Droplet Velocity**   | Sets how quickly each drop starts moving. This affects the path it follows and how much material it can carry.                                         |
|            | **Erosion Rate**       | Sets how strongly moving drops cut material from the ground.                                                                                           |
|            | **Deposit Rate**       | Sets how strongly drops leave carried material behind when they can no longer carry as much. The current English UI spells this label “Deposite Rate.” |

The number of drops and their lifetime control how much simulation runs. The other four settings
shape each drop's behavior. Erosion and deposit rates control how much simulated material movement
is applied.

## Smoothing

| Screenshot | Value                    | Description                                                                                                                                 |
| ---------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
|            | **Smoothing Iterations** | Sets how many times the smoothing pass repeats. Zero skips the pass. More passes strengthen its effect.                                     |
|            | **Smoothing Radius**     | Sets how far around a point the pass looks when comparing nearby heights. A wider radius spreads the comparison over a larger neighborhood. |
|            | **Smoothing Rate**       | Sets how strongly each pass moves heights toward the neighborhood's average. Lower values keep more of the original bumps and dips.         |

These filters shape new terrain generated from the preset.
