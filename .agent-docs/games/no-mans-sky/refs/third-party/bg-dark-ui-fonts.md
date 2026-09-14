# BG Dark UI and Fonts inspection

## Decision

BG Dark UI and Fonts `4.8` is the current main file for Nexus mod 2335 and is retained as a
UI-overlap reference. It is **not approved for No Man's Sky Cosmos 7.01**. Its global fonts and
frontend backgrounds are ordinary whole-resource replacements, but its full
`UI/BOOT/TWOLINEBUTTON.MBIN` was built for 6.45.1 and does not represent the current 7.01 layout.
Current comparison finds 118 semantic differences and non-finite numeric drift where the authoring
Lua describes only two intended layout edits.

No file was installed into the game, no save was opened, and no runtime compatibility is claimed.
The author disallows redistribution and requires permission for asset use or modification. The
downloaded archive and extracted files therefore remain local and ignored.

## Artifact identity and ownership

| Field                      | Pinned value                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| Nexus page                 | [BG Dark UI and Fonts, mod 2335](https://www.nexusmods.com/nomanssky/mods/2335?tab=description) |
| Nexus file                 | BG Dark UI Fonts, file `47383`                                                                  |
| Mod/file version           | `4.8`                                                                                           |
| Published                  | June 23, 2026 at 09:32 UTC                                                                      |
| Archive                    | `BG Dark UI Fonts 2335 4.8 2026-06-23T09-32Z qTSCvocoG.zip`                                     |
| Archive size               | 1,737,048 bytes                                                                                 |
| SHA-256                    | `4a596f5e57d149df39e30728b2ccd87de2f00b83c639d700f0d146297b9ab005`                              |
| Catalog status             | `diagnostic-only`                                                                               |
| Author compatibility claim | NMS 6.45.1                                                                                      |
| Validation target          | Cosmos 7.01, Steam build `25233815`                                                             |

The immutable identity and hash live in the
[NMS third-party catalog](../../../../../.squinch/games/no-mans-sky/third-party/artifacts.toml). The
archive is cached outside Git at
`${SQINCHMODS_CACHE_HOME}/third-party/nexus-mods/nomanssky/2335/47383/`. Its safely extracted,
ignored reference tree is `games/no-mans-sky/reference/sources/6.45.1/mods/bg-dark-ui-fonts/47383/`.
It is an inspection input, not a maintained workspace mod.

## Runtime contents and overlap boundary

The ZIP has 20 members, 13 regular files, and one meaningful deployment root,
`BgDarkerUIFonts.v4.8/`. The game-facing files are:

- one full `UI/BOOT/TWOLINEBUTTON.MBIN` layout replacement;
- `UI/GAMEFONT.TTF` and `UI/GAMEFONT2.TTF`; and
- nine replacements below `TEXTURES/UI/FRONTEND/BACKGROUNDS/`: `BACKGROUND`, `BGCIRCLEELEMENT`,
  `DISCOVERYBG`, `EXPEDITIONBG`, `INVENTORYBG`, `LOADINGBG`, `MAINTENANCEBG`, `OPTIONSBG`, and
  `STARTBG`, all as DDS files.

The remaining file is AMUMSS Lua authoring source; the game does not execute it. There are no EXML
patches, localization tables, custom controllers, or Catalogue/Guide data changes.

This is a broad visual-theme mod but a precise path-level conflict boundary. A search-menu mod that
only appends `METADATA/REALITY/WIKI.EXML`, a mission-table EXML, root localization, and uniquely
named icons has no direct asset-path collision with it. The theme's global fonts and backgrounds
will naturally style the vanilla Guide UI used by such a mod. Direct collision begins only if the
new mod also owns one of the twelve game-facing paths above.

An unrelated UI overhaul can still replace `UI/WIKIPAGE.MBIN` or change controller-expected IDs.
That is a separate compatibility case and must be tested; BG Dark UI does not do so.

## Cosmos 7.01 compatibility evidence

The current 7.01 compiler can deserialize both the packaged and current vanilla
`TWOLINEBUTTON.MBIN`, but that does not make the old full replacement current. Its semantic
comparison has 2,542 nodes on each side and 118 differing values. The first two differences are the
author's documented intent from `_Silent369.BgDarkUI.v4.8.lua`:

- find the child with `ID=ICON` and set `Position X` from about `41.364212` to `50`; and
- change its horizontal alignment from `Left` to `Center`.

The other differences include current scrolling, offsets, colors, font/layout state, and non-finite
numeric values. The analysis therefore reports `nonfinite_full_replacement_drift`. A full UI MBIN is
a serialized snapshot, so a priority change cannot merge the intended two edits onto the current
layout or repair the stale values.

The DDS and TTF resources are whole-file visual replacements. Static inspection identifies their
formats, hashes, and exact destinations, but does not prove visual quality, glyph coverage, or
runtime behavior on 7.01.

## Acceptance boundary

A future package can be considered for 7.01 only after its button change is regenerated from the
current vanilla layout and the exported result differs only at the intended leaves. Runtime checks
must then cover keyboard/controller focus, all screens using the shared two-line button, UI scale,
localization, font glyph coverage, and at least one Guide/Catalogue extension. The background and
font resources should be validated independently from the button MBIN so failure in one domain does
not imply the others are safe or unsafe.

## Reproduction

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-2335-47383-bg-dark-ui-fonts \
  --archive '/var/home/scott/Downloads/BG Dark UI Fonts 2335 4.8 2026-06-23T09-32Z qTSCvocoG.zip'

tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-2335-47383-bg-dark-ui-fonts

tooling/squinch third-party no-mans-sky validate

tooling/squinch nms-investigate analyze-mod \
  --mod-root 'games/no-mans-sky/reference/sources/6.45.1/mods/bg-dark-ui-fonts/47383/BgDarkerUIFonts.v4.8'
```

The retained analysis is
`games/no-mans-sky/investigation-state/runs/20260911T222358Z-analyze-mod-01d4b08f/`.

## Public references

- Hello Games, [Cosmos 7.01](https://www.nomanssky.com/2026/09/cosmos-7-01/).
- Nexus Mods, [BG Dark UI and Fonts files](https://www.nexusmods.com/nomanssky/mods/2335?tab=files)
  and [description and permissions](https://www.nexusmods.com/nomanssky/mods/2335?tab=description).
- MBINCompiler,
  [7.01 release](https://github.com/monkeyman192/MBINCompiler/releases/tag/v7.01.0-pre1).
