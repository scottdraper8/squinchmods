# World Settings

This page controls the world map, coastlines, spawn location, and vertical limits.

## Continents

### Continent Type

Chooses the broad continent layout. MULTI_IMPROVED and UPLIFT share the newer continent controls.
UPLIFT also creates raised continents and supports 3D rivers.

| Screenshot                                                                                                           | Value              | Description                                                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![UPLIFT continent example](https://github.com/user-attachments/assets/53bc5d64-d44e-4361-8a4d-e7f0fd8d1b88)         | **UPLIFT**         | Raises each continent toward its center. It shares the organic layout of MULTI_IMPROVED and supports 3D rivers.                                          |
| ![MULTI_IMPROVED continent example](https://github.com/user-attachments/assets/1004b432-f2e2-49df-aaa3-abe5ff3c9b97) | **MULTI_IMPROVED** | Creates organically shaped continents with varied sizes and coastlines.                                                                                  |
| ![SINGLE continent example](https://github.com/user-attachments/assets/194fb8c5-16ad-4312-8b75-fced8ce8c89d)         | **SINGLE**         | Creates one continent surrounded by ocean. This older option supports existing presets, and Continent Shape has a strong effect on its outline.          |
| ![MULTI continent example](https://github.com/user-attachments/assets/41680c48-ddad-45ca-bf05-76fb67cf232b)          | **MULTI**          | Shapes continents around the underlying cell grid. This older option supports existing presets, and Continent Shape has a strong effect on its outlines. |

### Continent Shape

Controls continent edges for MULTI and SINGLE. The editor enables it for those types.

| Screenshot                                                                                                  | Value         | Description                                                                         |
| ----------------------------------------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------- |
| ![MANHATTAN shape example](https://github.com/user-attachments/assets/e1de51e5-cf92-4b87-9e94-45f696020b00) | **MANHATTAN** | Tends to create angular continent edges with wide stretches of ocean between them.  |
| ![NATURAL shape example](https://github.com/user-attachments/assets/54bdc2cb-3f7a-4269-bb0a-eddfe6e346cc)   | **NATURAL**   | Mixes the available distance patterns for organic outlines and moderate ocean gaps. |
| ![EUCLIDEAN shape example](https://github.com/user-attachments/assets/955271a9-3b7a-44a2-8c1e-23284cba8517) | **EUCLIDEAN** | Tends to create rounded continents close to their neighbors, with narrower oceans.  |

### Continent Scale

Sets the typical size of continents. Larger values create broader continents and longer travel
distances.

| Screenshot                                                                                                        | Value     | Description                                                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ![Continent Scale 10000 example](https://github.com/user-attachments/assets/7e302179-6ebb-41f6-af8b-424ca281921d) | **10000** | Creates continents about 40,000 blocks wide. This scale suits large exploration worlds and screenshots. UPLIFT can raise the centers about 400 blocks, so allow extra World Height. |
| ![Continent Scale 4000 example](https://github.com/user-attachments/assets/0291ba25-8bf7-4946-b419-90da43617f4e)  | **4000**  | Creates continents about 20,000 blocks wide. This scale suits general play and survival. UPLIFT can raise the centers about 200 blocks.                                             |
| ![Continent Scale 2000 example](https://github.com/user-attachments/assets/c06a2804-ac78-4e57-8a87-4f795169fb88)  | **2000**  | Creates continents about 10,000 blocks wide. The cell pattern may become visible in the coastlines. UPLIFT can raise the centers about 100 blocks.                                  |
| ![Continent Scale 500 example](https://github.com/user-attachments/assets/2415ccf7-d02a-47e6-9384-15932b009752)   | **500**   | Creates continents about 2,000 blocks wide. Very small scales can distort terrain and make continents run together.                                                                 |

### Continent Jitter

Moves continent centers away from a regular grid. Higher values make placement less regular.

| Screenshot                                                                                                        | Value    | Description                                                             |
| ----------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------- |
| ![Continent Jitter 0.50 example](https://github.com/user-attachments/assets/53465b6a-4043-423d-9225-8ecff9f60ece) | **0.50** | Some of the regular grid pattern remains visible.                       |
| ![Continent Jitter 0.65 example](https://github.com/user-attachments/assets/e2c4287f-2df1-4085-aba7-50875af2a902) | **0.65** | Adds practical offsets that help disguise the regular pattern.          |
| ![Continent Jitter 0.80 example](https://github.com/user-attachments/assets/fb94b298-532f-47ac-bbdb-27c10457d05f) | **0.80** | Creates strong variation in continent placement.                        |
| ![Continent Jitter 1.00 example](https://github.com/user-attachments/assets/b3a184ed-1720-42d9-b61d-21529960cd19) | **1.00** | Continents can bridge together and change where rivers reach the coast. |

### Continent Skipping

Sets the share of continent positions left as ocean. Higher values create wider open-water areas.

| Screenshot                                                                                                          | Value    | Description                                                                                                       |
| ------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| ![Continent Skipping 0.00 example](https://github.com/user-attachments/assets/1bd5c85f-34b0-4081-bcbc-2dab89a55fea) | **0.00** | Generates a continent at every position.                                                                          |
| ![Continent Skipping 0.25 example](https://github.com/user-attachments/assets/0368253c-39e8-4539-b193-ad34cd9309fc) | **0.25** | Skips about one quarter of the continent positions.                                                               |
| ![Continent Skipping 0.50 example](https://github.com/user-attachments/assets/ae784837-0aa8-421d-8c91-76421af83476) | **0.50** | Skips about half of the continent positions.                                                                      |
| ![Continent Skipping 0.75 example](https://github.com/user-attachments/assets/30f7576d-e87d-43d2-be96-81c9a652a4c0) | **0.75** | Skips about three quarters of the continent positions.                                                            |
| ![Continent Skipping 1.00 example](https://github.com/user-attachments/assets/f39f6124-129a-45b8-9461-2af621ce9c61) | **1.00** | Leaves only the continent closest to the world center. This creates a large central landmass surrounded by ocean. |

### Continent Size Variance

Sets how much continent sizes can vary. Higher values allow more positions to produce smaller
continents.

| Screenshot                                                                                                               | Value    | Description                                                             |
| ------------------------------------------------------------------------------------------------------------------------ | -------- | ----------------------------------------------------------------------- |
| ![Continent Size Variance 0.00 example](https://github.com/user-attachments/assets/1cb78985-58cd-4b28-8ab5-7e7f4a4c98c1) | **0.00** | Continents use the full size available at each position.                |
| ![Continent Size Variance 0.25 example](https://github.com/user-attachments/assets/ead4fd42-dbcd-46ad-8a79-1ade8975514a) | **0.25** | About a quarter of continents can be up to a quarter smaller.           |
| ![Continent Size Variance 0.50 example](https://github.com/user-attachments/assets/31f1a8a6-e843-4acb-abf3-6fd89aa7e00d) | **0.50** | About half of continents can be up to half their full size.             |
| ![Continent Size Variance 0.75 example](https://github.com/user-attachments/assets/a26266cb-8126-4c6f-a201-278517abdc97) | **0.75** | About three quarters of continents can be up to three quarters smaller. |

### Continent Noise Octaves

Sets how many layers of coastline detail are combined. More layers add finer detail.

| Screenshot                                                                                                            | Value | Description                                                                                          |
| --------------------------------------------------------------------------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------- |
| ![Continent Noise Octaves 1 example](https://github.com/user-attachments/assets/278ac2e4-9313-42c4-a55f-be08dbc669a8) | **1** | Creates smoother coastlines with broad shapes. Similar details can appear on neighboring continents. |
| ![Continent Noise Octaves 3 example](https://github.com/user-attachments/assets/fef9d2fd-573a-4237-9819-8f5de0126b76) | **3** | Adds more detail to coastal regions. Noise Gain and Noise Lacunarity also affect the result.         |
| ![Continent Noise Octaves 5 example](https://github.com/user-attachments/assets/dea1786b-b587-4034-b10f-e247f4dbebd2) | **5** | Creates fine variation along the coastline.                                                          |

### Continent Noise Gain

Sets how strongly each detail layer changes the coastline. Higher values create more irregular
coastal shapes.

| Screenshot                                                                                                             | Value     | Description                                                           |
| ---------------------------------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------- |
| ![Continent Noise Gain 0.00 example](https://github.com/user-attachments/assets/a07cf322-11f0-4696-b835-a61b4270d534)  | **0.00**  | Leaves continent edges close to the regular cell pattern.             |
| ![Continent Noise Gain 0.125 example](https://github.com/user-attachments/assets/18a80461-716a-4fde-9291-00d0222e5606) | **0.125** | Creates strongly organic continent shapes.                            |
| ![Continent Noise Gain 0.25 example](https://github.com/user-attachments/assets/4dd94005-b795-4390-b60f-0877bf60bd18)  | **0.25**  | Keeps organic outlines and adds more detail.                          |
| ![Continent Noise Gain 0.375 example](https://github.com/user-attachments/assets/fefe63a9-d4c1-4749-b8ad-7403b956fdbd) | **0.375** | Adds strong coastal detail. Similar coast shapes can begin to appear. |
| ![Continent Noise Gain 0.50 example](https://github.com/user-attachments/assets/72225109-cd52-41b8-bf73-a9b7745529fc)  | **0.50**  | Creates rounded outlines with many irregular edge details.            |

### Continent Noise Lacunarity

Sets how much smaller each added detail layer becomes. Higher values add finer details over shorter
distances.

| Screenshot                                                                                                                   | Value     | Description                                    |
| ---------------------------------------------------------------------------------------------------------------------------- | --------- | ---------------------------------------------- |
| ![Continent Noise Lacunarity 1.00 example](https://github.com/user-attachments/assets/f415ba5b-993d-4fa3-8050-9a2f9bcd7d54)  | **1.00**  | Creates very little coastline variation.       |
| ![Continent Noise Lacunarity 2.50 example](https://github.com/user-attachments/assets/c407633c-c22a-4541-b54e-28d32a1a3d81)  | **2.50**  | Adds a small amount of coastline variation.    |
| ![Continent Noise Lacunarity 5.00 example](https://github.com/user-attachments/assets/1c6bb3bd-d55e-49d2-8f66-c2b97c0d7137)  | **5.00**  | Adds a moderate amount of coastline variation. |
| ![Continent Noise Lacunarity 7.50 example](https://github.com/user-attachments/assets/4c7412f4-46af-43cf-b0a9-17b0f4d44c44)  | **7.50**  | Adds heavy coastline variation.                |
| ![Continent Noise Lacunarity 10.00 example](https://github.com/user-attachments/assets/7433d5ee-aaba-4870-9dcc-3bda086b03c5) | **10.00** | Creates very fine, erratic terrain detail.     |

## Ocean, coast, and inland boundaries

These sliders mark positions along the map from ocean to inland. The editor keeps them in order. The
gaps between values set transition widths. Wider gaps create gradual transitions.

| Screenshot | Value             | Description                                                                                                            |
| ---------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
|            | **Island Inland** | Sets where the raised island interior begins. Raising it shrinks the interior and widens the shore.                    |
|            | **Island Coast**  | Sets where the island coast ends. The gap from Island Inland controls island beach width.                              |
|            | **Deep Ocean**    | Sets where deep ocean ends and shallow ocean begins. Raising it extends deep ocean toward land.                        |
|            | **Shallow Ocean** | Sets where shallow ocean ends and the coastal zone begins. Its gap from Deep Ocean controls underwater slope.          |
|            | **Beach**         | Sets where the beach strip ends. Its gap from Shallow Ocean controls beach width.                                      |
|            | **Coast**         | Sets the transition from coastal land to interior land. It also shifts where coastal biomes give way to inland biomes. |
|            | **Inland**        | Sets where the full interior begins. Wider spacing from Coast stretches the coastal transition.                        |

## Spawn and vertical world shape

### Spawn Type

Chooses where the world places you. Safe spawn checks can move the final position to a nearby
suitable location.

| Screenshot | Value                | Description                                                                     |
| ---------- | -------------------- | ------------------------------------------------------------------------------- |
|            | **CONTINENT_CENTER** | Searches near the nearest continent's center for a suitable point.              |
|            | **ISLANDS**          | Starts its search at the origin. The selected point may fall outside an island. |
|            | **WORLD_ORIGIN**     | Places you at coordinates 0, 0.                                                 |
|            | **USER_SELECTED**    | Uses the location you most recently clicked in a world preview.                 |

### World Height

Sets the highest Y level in the world. Taller worlds leave more room for mountains and raised
continents.

| Screenshot                                                                                                                              | Value       | Description                                                                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
|                                                                                                                                         | **320**     | Matches vanilla Minecraft's world height.                                                                                                  |
|                                                                                                                                         | **640**     | Leaves more room for tall terrain.                                                                                                         |
|                                                                                                                                         | **1024**    | The top of the current slider range. Very tall worlds can take more processing and storage.                                                |
| ![Preview highlighting terrain above the world height](https://github.com/user-attachments/assets/9a49deca-8770-42aa-9650-a2108b278d89) | **TOO LOW** | Pink areas in the preview show terrain above the selected height. Raise World Height or lower terrain scales to bring it inside the limit. |

### World Depth

Sets how far the world extends below Y=0. Greater depth leaves more room for deep caves and
underground terrain.

| Screenshot | Value    | Description                                                                  |
| ---------- | -------- | ---------------------------------------------------------------------------- |
|            | **64**   | Matches vanilla Minecraft's world depth.                                     |
|            | **128**  | A deeper setting that leaves more room underground.                          |
|            | **1024** | An extremely deep setting that can require more processing and save storage. |

### Ocean Depth

Sets how far the ocean floor can extend below the waterline. The range adjusts with Sea Level and
World Depth.

| Screenshot | Value           | Description                                       |
| ---------- | --------------- | ------------------------------------------------- |
|            | **Ocean Depth** | Sets the depth of the seabed below the waterline. |

### Sea Level

Sets the Y level of the main waterline. This also affects how the coastline transitions into the
ocean.

| Screenshot                                                                                                     | Value        | Description                                                                                   |
| -------------------------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------- |
| ![Sea Level 0 example](https://github.com/user-attachments/assets/859164b7-50cf-4f41-9b18-674f040de66b)        | **0**        | Creates an ocean-free world. River ends can look unusual at this level.                       |
|                                                                                                                | **63**       | Matches vanilla Minecraft's water level.                                                      |
| ![Sea Level below 63 example](https://github.com/user-attachments/assets/94200011-d638-4f7e-a712-e80141c746e2) | **Below 63** | Lower levels can leave vanilla structures such as ocean monuments and trial chambers exposed. |

### Lava Level

Sets the general height below which underground spaces can fill with lava. Sea Level also limits the
result.

| Screenshot                                                                                                             | Value               | Description                                                        |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------- | ------------------------------------------------------------------ |
| ![Lava Level above sea level example](https://github.com/user-attachments/assets/4d21d24d-2b54-42f8-a7a2-7ae89002f074) | **Above sea level** | Can replace oceans with lava and create heavily distorted terrain. |
| ![Lava Level below zero example](https://github.com/user-attachments/assets/52d059c6-b052-4675-a2f3-b8fd4ee47a0c)      | **Below 0**         | Places lava deeper underground and can create deep lava lakes.     |

These settings affect newly generated chunks.
