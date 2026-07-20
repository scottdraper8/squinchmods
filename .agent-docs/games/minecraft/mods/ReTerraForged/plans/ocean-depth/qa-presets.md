# Ocean Depth QA Presets

## Purpose

Reference for the datapacks used during PR #97 ocean-depth QA.

**Canonical copies now live in this repo** under `test-presets/` (added 2026-07-20, after the
Modrinth profile's `exports/` directory was found to have already lost one preset once — see the
"Note (2026-07-19)" below). Prefer these committed copies for any new QA; the Modrinth profile paths
below are the original source and are kept as a secondary reference only.

| Name                                                                     | Committed copy                                                     | SHA-256                                                            |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Very deep ocean test                                                     | `test-presets/very-deep.zip`                                       | `0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837` |
| Goldilocks (vanilla-depth max ocean)                                     | `test-presets/goldilocks.zip`                                      | `b1487bcf52fdb3e27a2a76ea5e7f505f7e925aa00e63ce7f9b9f4bd44fb7c878` |
| Mountain, `worldDepth=16`                                                | `test-presets/mountain-worldDepth16.zip`                           | `546aeab25e0d61b59638ff1da81d661f2817c50c5886e54b0297523d31ce1c68` |
| Very deep + `deep_dark` allowed for Trial Chambers (screenshot aid only) | `test-presets/very-deep-plus-deepdark-allowed-SCREENSHOT-ONLY.zip` | `b345f060dc5827d230cd35a5f20f0b63e8cee0e57665289d170ad1a19f277651` |
| `worldDepth=16` mountain, tall terrain + dense Ancient City spacing      | `test-presets/mountain-worldDepth16-tall-plus-dense-ac.zip`        | `36c89b6ba30c711dd520eef9c084d079d7a75c2c3e376c03d69fc3675fc68588` |

The `worldDepth=16` mountain preset is the hand-reconstructed extreme-shallow preset described in
`trial-chambers-and-ocean-structures.md`'s "Upward window rescue" section (`min_y=-16`,
`height=400`, dense Trial Chambers `structure_set` override `spacing=8, separation=3`) — committed
here since it was previously reconstructed ad hoc each session with no canonical saved copy.

**The `deep_dark`-allowed preset is not a QA preset, it's a screenshot aid, do not use it for
anything that needs to reflect real behavior.** It's the very-deep preset plus one extra file
(`data/minecraft/tags/worldgen/biome/has_structure/trial_chambers.json`, additive tag merge, adds
`minecraft:deep_dark` to the list of biomes Trial Chambers is allowed to spawn in). The known
floating Trial Chambers at `[-30768,~,-34080]` is normally rejected by the fix's biome pre-check
(its corrected position resolves to `deep_dark`, which Trial Chambers structurally excludes), not by
a lack of room, so under the real, unmodified game this exact location never generates anything for
a "same spot, after" screenshot. This preset removes only that one biome restriction so the same
exact horizontal footprint (confirmed identical bbox X/Z, `(-30843,-34163)-(-30733,-34020)`)
produces a real, buried instance instead, purely so a true same-seed/same-location before-and-after
pair is possible for a screenshot. It does not change anything about the fix itself.

**The tall-mountain/dense-AC variant is also a screenshot aid, not a QA preset**, built to solve a
real practical problem: the plain `worldDepth=16` preset's nearest natural Ancient City was
`[18176, ~, 4432]`, about 17,000 blocks from spawn, because `deep_dark` biome climate is extremely
rare in a preset this shallow (a symptom of the same biome-banding issue tracked in
`biome-climate-banding-investigation.md`). RTF's `DEPTH` density function
(`PresetNoiseRouterData.java`) is the sum of a Y-based gradient term _and_ a term derived from the
local generated terrain height, so making mountains dramatically taller
(`terrain.general.globalVerticalScale` and `terrain.mountains.verticalScale` bumped `1.0 → 4.0`,
`terrain.mountains.weight` `2.5 → 5.0`) plus a denser `ancient_city` `structure_set` override
(`spacing=6, separation=2`, vanilla default `24, 8`, same technique used elsewhere in this
investigation) brought the nearest real, healthy, fix-confirmed instance down to 624 blocks from
spawn (`[1536, ~172, 2000]`, one of 11 real instances found clustered in a single ~200x200
forceload, all `10-24%` solid, all sitting at `Y=145..199`, confirmed with the diagnostic solidity
scanner before being reverted out of the production build). This also empirically confirmed Ancient
City's own upward window-rescue path live, which had previously only been inferred from Trial
Chambers sharing the same code.

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

| Name                                 | Exported datapack                                                                                                                                                      | Key values                                                                                         | SHA-256                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Very deep ocean test                 | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset.zip`            | `oceanDepth=677`, `worldDepth=624`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER` | `0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837` |
| Shallowest ocean test                | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset-shallowest.zip` | `oceanDepth=10`, `worldDepth=128`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER`  | `5ae7ba936536abc2930ec719b869e19aadb35a783d999f4e81c22358f9aa6383` |
| Goldilocks (vanilla-depth max ocean) | `/home/scott/.var/app/com.modrinth.ModrinthApp/data/ModrinthApp/profiles/[TEST] RTF Fabric 1.21.1/config/reterraforged/exports/ocean-depth-test-preset-goldilocks.zip` | `oceanDepth=117`, `worldDepth=64`, `worldHeight=384`, `seaLevel=63`, `spawnType=CONTINENT_CENTER`  | `b1487bcf52fdb3e27a2a76ea5e7f505f7e925aa00e63ce7f9b9f4bd44fb7c878` |

**Note (2026-07-19):** `ocean-depth-test-preset-shallowest.zip` is referenced above and in
`monument-placement-research.md`, but is no longer present in the Modrinth profile's `exports/`
directory as of this investigation — only the very-deep and Goldilocks exports currently exist
there. Re-export it before relying on the shallowest preset again.

"Goldilocks" is not an RTF-internal name; it's this investigation's label for the deepest _legal_
ocean at otherwise vanilla world depth (`worldDepth=64`, the codec default): `oceanDepth=117` is the
UI/code maximum for `seaLevel=63` with `worldDepth=64` (`seaLevel + worldDepth - 10`, see
`WorldSettingsPage` in Source-code correction below). It was created specifically to test whether
Ancient Cities could protrude into oceans with a fixed structure `start_height` even without RTF's
extreme deep-ocean settings — that test led to discovering the biome climate-banding issue described
in `biome-climate-banding-investigation.md`. Unlike the very-deep/shallowest exports, the exported
datapack's `preset.json` omits `worldDepth` from `world.properties` (it equals the codec default),
but the loose preset JSON in `presets/ocean-depth-test-preset-goldilocks.json` does list it
explicitly.

For direct-scanner runs, the Goldilocks RTF preset was combined with a dense Ancient City
`structure_set` override (`spacing=6`, `separation=2`, see Practical notes in the resume doc) into a
single datapack zip, `combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip`. There
is no build script for this combination in the repo; it was assembled ad hoc by adding a second
`data/` path into a copy of the Goldilocks export. Current on-disk copies (run artifacts, not
canonical sources):

```text
games/minecraft/mods/ReTerraForged/fabric/run/world/datapacks/combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip
games/minecraft/mods/ReTerraForged/fabric/run/qa-biome-bands-goldilocks/datapacks/combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip
games/minecraft/mods/ReTerraForged/fabric/run/qa-goldilocks-climate-axis/datapacks/combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip
/tmp/rtf-goldilocks-vanilla-depth-dense-20260719/combined-ocean-depth-goldilocks-vanilla-depth-dense-ancient-city.zip
```

All exported zips contain the RTF preset at:

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
- Goldilocks preset: originally built to test whether Ancient Cities' fixed structure `start_height`
  could expose them protruding into oceans without needing RTF's extreme deep-ocean settings.
  Combined with a dense Ancient City `structure_set` override, it became the primary preset for the
  `deep_dark`/low-ocean-floor biome climate-banding scans.

See `monument-placement-research.md` for the measured monument floor samples,
`trial-chambers-and-ocean-structures.md` for the trial chamber reproduction and Ancient City search
data, and `biome-climate-banding-investigation.md` for the Goldilocks/extreme biome-band scans.
