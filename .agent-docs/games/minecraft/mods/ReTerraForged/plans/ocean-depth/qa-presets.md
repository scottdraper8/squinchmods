# Ocean Depth QA Presets

## Purpose

Reference for the datapacks used during PR #97 ocean-depth QA. Canonical copies live in this repo
under `test-presets/`; prefer them over the Modrinth profile's own `exports/` directory, which has
previously lost a preset (the shallowest export disappeared from it at least once — see "Modrinth
profile exports" below).

| Name                                          | Committed copy                                       | SHA-256                                                            |
| --------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test                          | `test-presets/very-deep.zip`                         | `0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837` |
| Goldilocks (vanilla-depth max ocean)          | `test-presets/goldilocks.zip`                        | `b1487bcf52fdb3e27a2a76ea5e7f505f7e925aa00e63ce7f9b9f4bd44fb7c878` |
| Mountain, `worldDepth=16`                     | `test-presets/mountain-worldDepth16.zip`             | `546aeab25e0d61b59638ff1da81d661f2817c50c5886e54b0297523d31ce1c68` |
| Very deep, archipelago enabled                | `test-presets/very-deep-archipelago.zip`             | `558410784d1aee8813ce9bc2738a123a1092f5a8f32e6b0fb5586e89fbe0d3ac` |
| Goldilocks, archipelago enabled               | `test-presets/goldilocks-archipelago.zip`            | `1729dbb6f2ecda0f2a7cb9d62989928acfd39d1768bac17dae204fbddaf82024` |
| Mountain `worldDepth=16`, archipelago enabled | `test-presets/mountain-worldDepth16-archipelago.zip` | `c464b7de710bdd4ee15e14498ae8a8f4b9fb7fe70d35131591bfcfc94f087c84` |

The `worldDepth=16` mountain preset is the hand-reconstructed extreme-shallow preset described in
`trial-chambers-and-ocean-structures.md`'s "Upward window rescue" section (`min_y=-16`,
`height=400`). It was reconstructed ad hoc each session before being committed here as a canonical
copy.

The three `-archipelago` variants are the same underlying presets with `island.enableArchipelago`
flipped on (`IslandSettings.makeDefault()`, all other fields identical) — built for the island
interaction investigation (`island-interaction-investigation.md`) since none of the base presets had
archipelago turned on. Kept as the starting point for whoever picks up that investigation's
recommended follow-up PR.

Two earlier presets built as one-off screenshot aids for the (now-shipped) Trial Chambers/Ancient
City work — a `deep_dark`-allowed variant and a tall-mountain/dense-Ancient-City variant, both
described in older revisions of this doc — have been removed. They existed only to get matching
before/after screenshots for that fix and reflected deliberately non-default behavior (an added
biome tag merge, and terrain/structure-spacing values well outside any real preset), not something
worth carrying forward as a QA reference.

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

## Modrinth profile exports

The presets above were originally authored in a Modrinth profile before being committed here. Those
original paths are kept as a secondary reference only — prefer the committed copies for any new QA.

| Name                                 | Modrinth export path                                                                                                                                                   | Key values                                                                                         | SHA-256                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test                 | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset.zip`            | `oceanDepth=677`, `worldDepth=624`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER` | `0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837` |
| Shallowest ocean test                | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset-shallowest.zip` | `oceanDepth=10`, `worldDepth=128`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER`  | `5ae7ba936536abc2930ec719b869e19aadb35a783d999f4e81c22358f9aa6383` |
| Goldilocks (vanilla-depth max ocean) | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset-goldilocks.zip` | `oceanDepth=117`, `worldDepth=64`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER`  | `b1487bcf52fdb3e27a2a76ea5e7f505f7e925aa00e63ce7f9b9f4bd44fb7c878` |

The shallowest export has gone missing from the Modrinth profile's `exports/` directory before, with
no trace of why — another reason to treat the committed `test-presets/` copies as the source of
truth rather than this directory.

"Goldilocks" is not an RTF-internal name; it's this investigation's label for the deepest _legal_
ocean at otherwise vanilla world depth (`worldDepth=64`, the codec default): `oceanDepth=117` is the
UI/code maximum for `seaLevel=63` with `worldDepth=64` (`seaLevel + worldDepth - 10`, see
`WorldSettingsPage.java`). It was created specifically to test whether Ancient Cities could protrude
into oceans with a fixed structure `start_height` even without RTF's extreme deep-ocean settings —
that test led to discovering the biome climate-banding issue described in
`biome-climate-banding-investigation.md`. Unlike the very-deep/shallowest exports, the exported
datapack's `preset.json` omits `worldDepth` from `world.properties` (it equals the codec default),
but the loose preset JSON in `presets/ocean-depth-test-preset-goldilocks.json` does list it
explicitly.

All exported zips contain the RTF preset at:

```text
data/reterraforged/reterraforged/worldgen/preset/preset.json
```

For the biome climate-banding scans specifically, the Goldilocks preset was combined ad hoc with a
dense Ancient City `structure_set` override (`spacing=6`, `separation=2`) into
`combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip` — there's no build script for
this, it was assembled by adding a second `data/` path into a copy of the Goldilocks export. Current
copies exist under `fabric/run/world/datapacks/` and
`fabric/run/qa-biome-bands-goldilocks/datapacks/` as run artifacts; rebuild it the same way if
picking that investigation back up.

The very-deep and Goldilocks presets share these relevant terrain controls:

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

| Name                                 | Path                                                                                                                                                                    | SHA-256                                                            |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test                 | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/presets/ocean-depth-test-preset.json`            | `64425cbecf15956c00227c62da4b363deea0a1dd1202466d21a17b5f6332ab46` |
| Shallowest ocean test                | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/presets/ocean-depth-test-preset (1).json`        | `ce90c89125b1ed5c79b6c12ce9a15eeadf2070702eb78a4b67fe212f2b3e27ef` |
| Goldilocks (vanilla-depth max ocean) | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/presets/ocean-depth-test-preset-goldilocks.json` | `8df44a80bcb8ee2f3ed1842c325a494e16d5a0a638788ec256c82147c9124c65` |

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

Several archived worlds under `fabric/run/world.*` also contain copies of these zips. Treat those as
historical run artifacts; prefer the committed `test-presets/` copies when starting new QA.

## What They Were Used For

- Very deep preset: reproducing deep ocean floors, long monument legs, trial chamber exposure, the
  large open-column floor variation seen during monument sampling, and (via its `-archipelago`
  variant) the island interaction investigation.
- Shallowest preset: verifying that the monument fix also handles shallow ocean floors, including
  the accepted outcome where a monument may protrude above the waterline.
- Goldilocks preset: originally built to test whether Ancient Cities' fixed structure `start_height`
  could expose them protruding into oceans without needing RTF's extreme deep-ocean settings. Became
  the primary preset for the `deep_dark`/low-ocean-floor biome climate-banding scans, and (via its
  `-archipelago` variant) part of the island interaction investigation.
- Mountain `worldDepth=16` preset: the extreme-shallow-world case for structure placement QA, and
  (via its `-archipelago` variant) the island interaction investigation.

See `monument-placement-research.md` for the measured monument floor samples,
`trial-chambers-and-ocean-structures.md` for the trial chamber reproduction and Ancient City search
data, `biome-climate-banding-investigation.md` for the Goldilocks/extreme biome-band scans, and
`island-interaction-investigation.md` for the archipelago findings.
