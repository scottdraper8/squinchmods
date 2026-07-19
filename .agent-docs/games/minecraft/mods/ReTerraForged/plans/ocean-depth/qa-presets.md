# Ocean Depth QA Presets

## Purpose

Reference for the exported datapacks used during PR #97 ocean-depth QA. These live outside the repo
in the Modrinth test profile, so record the exact paths and key values here before the context gets
lost.

Use the exported `.zip` files as the source of truth for server/client QA. The loose JSON files in
`config/reterraforged/presets/` are useful for reading values, but Minecraft loads the exported
datapack zip from a world's `datapacks/` folder.

Common QA seed used for the measurements below:

```text
3216933670
```

Known `/locate structure minecraft:monument` result for both shallowest and very-deep monument QA:

```text
[-256, ~, -256]
```

## Available Datapacks

| Name                  | Exported datapack                                                                                                                                                      | Key values                                                                                         | SHA-256                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test  | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset.zip`            | `oceanDepth=677`, `worldDepth=624`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER` | `0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837` |
| Shallowest ocean test | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset-shallowest.zip` | `oceanDepth=10`, `worldDepth=128`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER`  | `5ae7ba936536abc2930ec719b869e19aadb35a783d999f4e81c22358f9aa6383` |

Both exported zips contain the RTF preset at:

```text
data/reterraforged/reterraforged/worldgen/preset/preset.json
```

Both presets share these relevant terrain controls:

```text
controlPoints.deepOcean=0.1
controlPoints.shallowOcean=0.25
controlPoints.beach=0.327
controlPoints.coast=0.448
controlPoints.inland=0.502
terrain.general.globalHorizontalScale=1.0
terrain.general.globalVerticalScale=1.0
terrain.general.terrainRegionSize=1200
```

## Loose Preset JSONs

Readable copies from the Modrinth profile:

| Name                  | Path                                                                                                                                                             | SHA-256                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test  | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/presets/ocean-depth-test-preset.json`     | `64425cbecf15956c00227c62da4b363deea0a1dd1202466d21a17b5f6332ab46` |
| Shallowest ocean test | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/presets/ocean-depth-test-preset (1).json` | `ce90c89125b1ed5c79b6c12ce9a15eeadf2070702eb78a4b67fe212f2b3e27ef` |

## Headless Server Use

For a fresh headless QA world, delete the old world and copy the desired exported zip before launch:

```bash
cd /var/home/scott/Repos/squinchmods/games/minecraft/mods/ReTerraForged
rm -rf fabric/run/world
mkdir -p fabric/run/world/datapacks
cp "<exported-datapack.zip>" fabric/run/world/datapacks/
```

Then make sure `fabric/run/server.properties` includes:

```properties
level-seed=3216933670
level-name=world
enable-rcon=true
```

The current dev-server world datapack path observed during this investigation was:

```text
/var/home/scott/Repos/squinchmods/games/minecraft/mods/ReTerraForged/fabric/run/world/datapacks/ocean-depth-test-preset.zip
```

Several archived worlds under `fabric/run/world.*` also contain copies of these zips. Treat those as
historical run artifacts; prefer the Modrinth `exports/` paths above when starting new QA.

## What They Were Used For

- Very deep preset: reproducing deep ocean floors, long monument legs, trial chamber exposure, and
  the large open-column floor variation seen during monument sampling.
- Shallowest preset: verifying that the monument fix also handles shallow ocean floors, including
  the accepted outcome where a monument may protrude above the waterline.

See `monument-placement-research.md` for the measured monument floor samples and
`trial-chambers-and-ocean-structures.md` for the trial chamber reproduction.
