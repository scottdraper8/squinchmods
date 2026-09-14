# Expedition Catalogue Improved inspection

## Decision

Expedition Catalogue Improved `6.40` is retained as a historical UI failure-boundary control and is
**not approved for No Man's Sky Cosmos 7.01**. Nexus now lists a newer 7.00 main file (`48187`),
which has not been acquired into this corpus; the pinned 6.40 file must not stand in for it. The
pinned file's small `JOURNEY.EXML` patch still targets the current Season History category
correctly. The package as a whole is unsafe, however, because it also replaces two full UI MBINs
serialized for the 6.40 GUI schema. The 7.01 schema inserts and shifts nested text-style fields;
decoding the old bytes with the current schema produces `NaN` values and an impossible font index.
It also removes `PATCH23`, which is no longer an empty future slot: Cosmos introduced the currently
released Expedition 23. A successful file walk by MBINCompiler does not make those shifted values or
stale page contents valid.

No file was installed into the game, no save was opened, and no runtime compatibility is claimed.
The author disallows redistribution and modification without permission, so neither a rebuilt
variant nor a committed copy of the archive was produced.

## Artifact identity and ownership

| Field                      | Pinned value                                                                                             |
| -------------------------- | -------------------------------------------------------------------------------------------------------- |
| Nexus page                 | [Expedition Catalogue Improved, mod 3064](https://www.nexusmods.com/nomanssky/mods/3064?tab=description) |
| Nexus file                 | Expedition Catalogue Improved - ZIP, file `47075`                                                        |
| Mod/file version           | `6.40`                                                                                                   |
| Published                  | May 31, 2026 at 16:48:16 UTC                                                                             |
| Archive                    | `Expedition Catalogue Improved - ZIP-3064-6-40-1780246096.zip`                                           |
| Archive size               | 9,932 bytes                                                                                              |
| SHA-256                    | `d6d990e85e8a96ad8a534da6b00b3fcf3c8932b60d6ff7c7958ea3ab5fe01be0`                                       |
| Catalog status             | `diagnostic-only`                                                                                        |
| Author compatibility claim | NMS 6.40 / Swarm                                                                                         |
| Validation target          | Cosmos 7.01, Steam build `25233815`                                                                      |

The immutable identity and hash live in the
[NMS third-party catalog](../../../../../.squinch/games/no-mans-sky/third-party/artifacts.toml). The
archive is cached outside Git at
`${SQINCHMODS_CACHE_HOME}/third-party/nexus-mods/nomanssky/3064/47075/`. The safely extracted,
ignored tree is
`games/no-mans-sky/reference/sources/6.40/mods/expedition-catalogue-improved/47075/`. It is a
third-party reference input, not a maintained workspace mod.

## Archive contents

The ZIP has ten members and five regular files below `FF_ExpeditionCatalogueImproved_640/`:

| File                                     |   Bytes | Role                                                                 |
| ---------------------------------------- | ------: | -------------------------------------------------------------------- |
| `METADATA/REALITY/JOURNEY.EXML`          |     703 | Narrow runtime patch changing the Season History icons               |
| `UI/COMPONENTS/JOURNEYSEASONPATCH.MBIN`  |   3,158 | Full 6.40 replacement for one expedition patch tile                  |
| `UI/JOURNEYMILESTONEPAGE.MBIN`           | 109,237 | Full 6.40 replacement for the Previous Expeditions page              |
| `FF_ExpeditionCatalogueImproved_640.lua` |   6,469 | AMUMSS authoring recipe; not executed by the game or this inspection |
| `AMUMSS_v5.6.2.0w.txt`                   |       0 | Empty authoring marker; ignored by the game                          |

The EXML is well-formed XML. Both MBINs report that they were compiled with MBINCompiler
`v6.40.0.1`. Their exact hashes are retained in `inspection.json` beside the ignored extraction.

## How the UI change was authored

The included Lua was read only as provenance for the already-compiled files. It was not executed or
treated as a runtime mod:

1. On `JOURNEYMILESTONEPAGE`, remove the hard-coded empty sections `PATCH23` through `PATCH50` and
   scale `PATCH01` through `PATCH22` to 75 percent width and height.
2. On `JOURNEYSEASONPATCH`, scale the containers and the `ICON_NOTSTARTED`, `ICON_UNFINISHED`, and
   `ICON_COMPLETED` elements to 75 percent.
3. On Journey category index 2, replace the ordinary Journey on/off icons with the seasonal mission
   icons.

The result changes **Catalogue & Guide → Journey → Previous Expeditions** to display four patches
per row, removes empty future slots, and gives the page an expedition-specific tab icon. The Nexus
description explicitly identifies the two UI files as full MBIN replacements, with conflicts against
any mod replacing the same paths.

The current 7.01 page still contains `PATCH01` through `PATCH50`; the packaged replacement contains
only `PATCH01` through `PATCH22`, matching the recipe's stated removal. The replacement strategy is
nevertheless version-sensitive: Hello Games' Cosmos notes identify Our Journey Continues as
Expedition 23, so the package now removes one released expedition along with the unused future
slots. It also carries the entire 6.40 UI trees, not only those removals and dimension changes.

## Merge and conflict surface

- The two UI MBINs are complete replacements. Only one replacement can win at each exact path, and
  the winner supplies every unrelated field and child in that UI object.
- Load priority may choose between competing replacements, but cannot translate a 6.40 binary layout
  into 7.01.
- The `JOURNEY.EXML` patch is much narrower. Current category index 2 remains `SeasonHistory` with
  `UI_JM_TITLE_SEASON`, so its two icon writes still address the intended category.
- A different mod that inserts/reorders Journey categories or overwrites category 2 can invalidate
  that generated index or win the same icon fields.

The archive bundles no custom resources or localization IDs.

## Cosmos 7.01 incompatibility evidence

HGPAKtool commit `2ea9b0351f93b72e4fa3d199bf4ac54149f748f8` extracted the installed Cosmos 7.01
versions of all three target files. MBINCompiler `v7.01.0-pre1` commit
`abeaf218ad6e0792be7bc1e64b0128c98a53ac3d` successfully decompiled the current vanilla files,
establishing a readable comparison baseline.

The current compiler can also walk the two old replacement files, but their decoded values expose a
shifted nested layout:

| Evidence under the 7.01 compiler  | Packaged 6.40 replacement | Current 7.01 vanilla |
| --------------------------------- | ------------------------: | -------------------: |
| `JOURNEYMILESTONEPAGE.MBIN` bytes |                   109,237 |              126,501 |
| Decompilation properties          |                    44,670 |               51,026 |
| Decoded `NaN` property values     |                        61 |                    0 |
| `JOURNEYSEASONPATCH.MBIN` bytes   |                     3,158 |                3,174 |
| Decompilation properties          |                     1,270 |                1,270 |
| Decoded `NaN` property values     |                         3 |                    0 |

As a control, the matching official `v6.40.0-pre1` Linux compiler (SHA-256
`00a2fb331e1519b5dff94c84d5691ea0e10b5638ac905941095d25b6388c7ffe`) decompiled the same two packaged
files without error. It produced zero `NaN` values, normal font indices (`0` or `1`), 44,235 page
properties, and 1,255 patch-tile properties. This rules out archive damage: the nonsensical values
appear specifically when the same bytes are interpreted through the 7.01 definitions.

The patch-tile dimensions decode to the intended 75-percent scale—`286.65 × 257.85` versus current
`382.199982 × 343.8`—but nearby text-style values do not. One `Font Index` becomes `1065353216`, the
integer bit pattern for a floating-point `1.0`, while outline/font spacing fields become `NaN`. This
is deterministic field displacement, not a visual preference difference.

The MBINCompiler source history explains the displacement. Between `v6.40.0-pre1` commit
`6731d4e9f889234d5c993c373e831e8314b25df3` and 7.01:

- `TkNGuiTextStyleData` gained `Button Image Override Colour` at offset `0x18`, moving its three
  existing colours, alignment, and boolean flags by four bytes;
- `TkNGuiTextStyle` moved its `Default` and `Highlight` subobjects;
- `GcNGuiTextData` moved fields after its nested style by 12 bytes;
- `GcNGuiPreset` moved its graphic/layer arrays, layout, and font; and
- all four affected template GUIDs changed.

The old complete binaries therefore do not represent valid current GUI objects. The separately
packaged Journey EXML cannot repair their nested layouts or restore the omitted `PATCH23`. A fresh
author release generated from current vanilla inputs and the current compiler could potentially
express the same visual intent, but that is a different artifact and would require the author's
permission and its own validation.

## Acceptance boundary

A future file can leave `diagnostic-only` only after its immutable Nexus identity and hash are
pinned, every replacement is compiled for the exact installed public build, untouched current MBINs
round-trip through the same compiler, and an isolated runtime check covers page navigation,
four-column layout, all released expedition patches, hover/scroll/focus behavior, controller and
mouse input, different resolutions/UI scaling, reload, and conflict priority. A new author file ID
must receive a new catalog entry rather than replacing this evidence.

## Reproduction

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-3064-47075-expedition-catalogue-improved \
  --archive '/var/home/scott/Downloads/Expedition Catalogue Improved - ZIP-3064-6-40-1780246096.zip'

tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-3064-47075-expedition-catalogue-improved

tooling/squinch third-party no-mans-sky validate
```

`import` and `inspect` are idempotent when existing bytes and reports match. They do not deploy the
mod. See the [No Man's Sky modding architecture](../../README.md) for loader semantics and the
[third-party tool documentation](../../../../../games/no-mans-sky/tooling/third-party/README.md) for
authentication and cache behavior.

## Public references

- Hello Games, [Cosmos 7.01](https://www.nomanssky.com/2026/09/cosmos-7-01/) and the
  [Cosmos update notes](https://www.nomanssky.com/cosmos-update/), which identify Expedition 23.
- MBINCompiler,
  [7.01 `TkNGuiTextStyleData`](https://github.com/monkeyman192/MBINCompiler/blob/abeaf218ad6e0792be7bc1e64b0128c98a53ac3d/libMBIN/Source/NMS/Toolkit/TkNGuiTextStyleData.cs)
  and
  [6.40 `TkNGuiTextStyleData`](https://github.com/monkeyman192/MBINCompiler/blob/v6.40.0-pre1/libMBIN/Source/NMS/Toolkit/TkNGuiTextStyleData.cs).
- Nexus Mods,
  [Expedition Catalogue Improved files](https://www.nexusmods.com/nomanssky/mods/3064?tab=files) and
  [description and permissions](https://www.nexusmods.com/nomanssky/mods/3064?tab=description).
