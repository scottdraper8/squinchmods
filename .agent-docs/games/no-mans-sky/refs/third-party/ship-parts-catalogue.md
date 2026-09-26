# Ship Parts Catalogue inspection

## Decision

Ship Parts Catalogue `6.16` is acquired as a third-party UI reference. Its single append-style EXML
patch is **structurally credible but content-incomplete on No Man's Sky Cosmos 7.01**. The current
`cGcWiki` target still has the expected category shape, all 418 item identifiers resolve, and all
ten category localization identifiers still exist. However, the literal Corvette list omits at least
the current `B_TUR_F` structural Corvette module; Cosmos also added a new Corvette utility after
this file was published. Unlike a full MBIN replacement, the package does not carry a serialized
6.16 object layout forward.

No file was installed into the game, no save was opened, and no visual or runtime compatibility is
claimed. The author disallows redistribution and modification without permission, so the archive and
extracted tree remain local and ignored.

## Artifact identity and ownership

| Field                      | Pinned value                                                                                    |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| Nexus page                 | [Ship Parts Catalogue, mod 3013](https://www.nexusmods.com/nomanssky/mods/3013?tab=description) |
| Nexus file                 | Ship Parts Catalogue - ZIP, file `44949`                                                        |
| Mod/file version           | `6.16`                                                                                          |
| Published                  | November 15, 2025 at 15:54:32 UTC                                                               |
| Archive                    | `Ship Parts Catalogue - ZIP-3013-6-16-1763222072.zip`                                           |
| Archive size               | 3,077 bytes                                                                                     |
| SHA-256                    | `5e94eadbefcaf993c603b14b180dab79ec536b85c5c4377c7212c11b77612365`                              |
| Catalog status             | `diagnostic-only`                                                                               |
| Author compatibility claim | Release `6.16`; changelog includes Breach Corvette parts                                        |
| Validation target          | Cosmos 7.01, Steam build `25233815`                                                             |

The immutable identity and hash live in the
[NMS third-party catalog](../../../../../.squinch/games/no-mans-sky/third-party/artifacts.toml). The
archive is cached outside Git at
`${SQINCHMODS_CACHE_HOME}/third-party/nexus-mods/nomanssky/3013/44949/`. The safely extracted,
ignored reference tree is
`games/no-mans-sky/reference/sources/6.16/mods/ship-parts-catalogue/44949/`. It is an inspection
input, not a mod maintained by this repository.

## Archive contents and behavior

The ZIP has four members but only one regular file:

| Runtime path below `FF_ShipPartsCatalogue_616/` |  Bytes | SHA-256                                                            |
| ----------------------------------------------- | -----: | ------------------------------------------------------------------ |
| `METADATA/REALITY/CATALOGUERECIPES.EXML`        | 27,311 | `913c0efe6dda3a976f4e9f5e8d8a1e40db9aecc615bafc63a79cbbceb4a65555` |

The EXML is well-formed XML and targets `cGcWiki.Categories`. It adds five `GcWikiCategory` objects
to **Catalogue & Guide → Recipes**, each using `CustomItemList` and existing mission ship icons:

| Added category label | Item references | Data source in 7.01            |
| -------------------- | --------------: | ------------------------------ |
| Fighter              |              65 | Modular-customisation products |
| Explorer             |              41 | Modular-customisation products |
| Hauler               |             135 | Modular-customisation products |
| Solar                |              39 | Modular-customisation products |
| Corvette             |             138 | Base-building objects          |
| **Total**            |         **418** | **418 unique identifiers**     |

The entries have neither `_id` nor `_index`; under the current EXML list rules they append rather
than replace the four vanilla recipe categories. There are no bundled icons, localization tables,
Lua scripts, or full MBIN replacements. The page describes the logical target as
`CATALOGUERECIPES.MBIN`; the deployable file is the corresponding modern loose EXML patch.

## Merge and conflict surface

This is a narrow data patch, but it still shares one high-traffic asset path:

- Another append patch to `cGcWiki.Categories` can coexist when it uses distinct content. An exact
  duplicate can create duplicate categories because these additions have no selector.
- A full `CATALOGUERECIPES.MBIN` replacement selected at higher priority becomes the base to which
  EXML patches are applied. A stale or incomplete replacement can still erase current categories or
  make the patch unreadable.
- A patch that overwrites the entire `Categories` list can erase these five entries depending on
  priority.
- The mod references only vanilla identifiers and resources, so it introduces no custom path or
  localization-ID collision of its own.

Load order can select a different merge base or resolve competing writes; it cannot make a missing
item ID or incompatible template valid.

## Cosmos 7.01 compatibility evidence

The comparison used the installed Cosmos 7.01, Steam build `25233815`. HGPAKtool commit
`2ea9b0351f93b72e4fa3d199bf4ac54149f748f8` extracted these current vanilla inputs, and MBINCompiler
`v7.01.0-pre1` commit `abeaf218ad6e0792be7bc1e64b0128c98a53ac3d` decompiled them:

- `METADATA/REALITY/CATALOGUERECIPES.MBIN`
- `METADATA/REALITY/TABLES/NMS_MODULARCUSTOMISATIONPRODUCTS.MBIN`
- `METADATA/REALITY/TABLES/BASEBUILDINGOBJECTSTABLE.MBIN`
- all eight current English localization tables

The current wiki contains four vanilla recipe categories with the same `GcWikiCategory` structure.
The patch's five `CategoryID` and five `CategoryIDUpper` localization keys all occur in current
English tables. Exact identifier comparison found:

- 280 of the patch's item IDs in `NMS_MODULARCUSTOMISATIONPRODUCTS`;
- the remaining 138 Corvette IDs in `BASEBUILDINGOBJECTSTABLE`;
- zero missing IDs and zero IDs ambiguously present in both sources.

That proves referential integrity, not catalogue completeness. The Fighter, Explorer, Hauler, and
Solar lists exactly match all current IDs with their respective prefixes in
`NMS_MODULARCUSTOMISATIONPRODUCTS`. The fixed Corvette list does not contain `B_TUR_F`, which the
current base-building table identifies as a placeable structural ship module in the `BIGGS_GUNS`
group. Hello Games' Cosmos notes independently announce a new Corvette utility part, the Tractor
Beam. The source evidence strongly indicates that `B_TUR_F` is that new module; regardless of the
display-name mapping, it is a current Corvette structural object omitted from the catalogue.

The `GcWiki`, `GcWikiCategory`, and `GcWikiTopicType` compiler templates are unchanged between the
nearest available post-6.16 compiler tag (`v6.17.0-pre1`) and `v7.01.0-pre1`. More importantly, the
current 7.01 vanilla target directly confirms every field used by this textual patch. Static
evidence therefore finds no stale selector, schema, resource, label, or listed item reference, but
does find stale coverage.

That is not a runtime proof. The entry stays `diagnostic-only` until an isolated run confirms that
the loader appends exactly five pages, every page renders and scrolls correctly, every item tile
resolves, and the change survives a save/reload without log errors. Testing should also include a
second Catalogue patch and a full Catalogue replacement in both priority orders.

## Reproduction

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-3013-44949-ship-parts-catalogue \
  --archive '/var/home/scott/Downloads/Ship Parts Catalogue - ZIP-3013-6-16-1763222072.zip'

tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-3013-44949-ship-parts-catalogue

tooling/squinch third-party no-mans-sky validate
```

`import` and `inspect` are idempotent when existing bytes and reports match. They do not deploy the
mod. See the [No Man's Sky modding architecture](../../README.md) for loader semantics and the
[third-party tool documentation](../../../../../games/no-mans-sky/tooling/third-party/README.md) for
authentication and cache behavior.

## Public references

- Hello Games, [Cosmos 7.01](https://www.nomanssky.com/2026/09/cosmos-7-01/) and the
  [Cosmos update notes](https://www.nomanssky.com/cosmos-update/).
- MBINCompiler,
  [7.01 `GcWikiCategory`](https://github.com/monkeyman192/MBINCompiler/blob/abeaf218ad6e0792be7bc1e64b0128c98a53ac3d/libMBIN/Source/NMS/GameComponents/GcWikiCategory.cs).
- Nexus Mods, [Ship Parts Catalogue files](https://www.nexusmods.com/nomanssky/mods/3013?tab=files)
  and
  [description, changelog, and permissions](https://www.nexusmods.com/nomanssky/mods/3013?tab=description).
