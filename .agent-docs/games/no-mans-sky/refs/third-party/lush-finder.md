# Lush Finder Full Mission inspection

## Decision

Lush Finder Full Mission `3.3.6.45` is acquired for source-level investigation but is **not approved
for No Man's Sky Cosmos 7.01**. The packaged custom `SYSTEMSCAN.SCENE.MBIN` is a 6.45
`TkSceneNodeData` object. The current 7.01 MBINCompiler identifies its old GUID, expects the new
7.01 GUID, and then fails to deserialize the shorter old layout. That is a demonstrated structural
incompatibility, not an inference from the upload date.

No file was installed into the game, no save was opened, and no runtime compatibility is claimed.
The author disallows redistribution and modification without permission, so the downloaded archive
and extracted tree remain local and ignored. A repaired/recompiled derivative was not produced.

## Artifact identity and ownership

| Field                      | Pinned value                                                                           |
| -------------------------- | -------------------------------------------------------------------------------------- |
| Nexus page                 | [Lush Finder, mod 3368](https://www.nexusmods.com/nomanssky/mods/3368?tab=description) |
| Nexus file                 | Full Mission Mode, file `47562`                                                        |
| Mod version                | `3.3.6.45`                                                                             |
| Published                  | July 23, 2026 at 16:43 UTC                                                             |
| Archive                    | `Lush Finder (Full Mission Mode) 3368 3.3.6.45 2026-07-23T16-43Z 8gT07OStD.zip`        |
| Archive size               | 515,150 bytes                                                                          |
| SHA-256                    | `9775f897f85a20fd59074ddca7aeba2de4c48b3fe0fafff358ff8f2dc521c9d9`                     |
| Catalog status             | `diagnostic-only`                                                                      |
| Author compatibility claim | Works with NMS 6.45                                                                    |
| Validation target          | Cosmos 7.01, Steam build `25233815`                                                    |

The committed identity and hash live in the
[NMS third-party catalog](../../../../../.squinch/games/no-mans-sky/third-party/artifacts.toml). The
archive is cached outside Git at
`${SQINCHMODS_CACHE_HOME}/third-party/nexus-mods/nomanssky/3368/47562/`. Its safely extracted
inventory is ignored at `games/no-mans-sky/reference/sources/6.45/mods/lush-finder/47562/`. This
mirrors Minecraft's third-party reference-source layout and does not make Lush Finder a maintained
workspace mod. Neither tree may be committed, published, or used as a redistribution source.

## Archive contents

The ZIP has 42 members and 20 regular files. Generic XML parsing succeeds for every EXML/MXML
document. All 11 images have valid 256-by-256 DXT5 DDS headers.

| Format | Count | Role                                                                                |
| ------ | ----: | ----------------------------------------------------------------------------------- |
| EXML   |     4 | Partial patches to rewards, NPC missions, emotes, and the player entity             |
| MBIN   |     2 | New custom system-scan entity and scene objects                                     |
| MXML   |     1 | Root `LocTable.MXML`, containing 107 localization entries across 17 language fields |
| DDS    |    11 | Custom quick-menu icons                                                             |
| TXT    |     2 | An empty AMUMSS marker and a localization working/export file; ignored by the game  |

There is no Lua source in this variant. The meaningful runtime root is
`Lush Finder V3.3.6.45 (Full Mission)/`; installing the outer ZIP name as an additional directory
would introduce an invalid extra nesting level.

## How the mod works

The mod builds a mission launcher out of ordinary data-driven game systems:

```mermaid
flowchart LR
    E[Quick-menu emote] --> A[Player animation]
    A --> T[BOOT animation-frame trigger]
    T --> R[Special reward]
    R --> M[Planet-finder mission]
    M --> S[System and planet scan event]
    S --> W[Quick warp / navigation]
    W --> P[Portal marker on matching planet]
```

- `EMOTEMENU.EXML` patches the existing `MEGA_WARP` and `SYSTEM_SCAN` entries and adds 31 finder
  actions. Selecting one starts a corresponding player animation.
- `PLAYERCHARACTER.ENTITY.EXML` adds animation-frame triggers to the existing `BOOT` trigger-action
  state. Each finder animation grants a named special reward. It also supplies `SYSTEM_SCAN`,
  `MEGA_WARP`, and finder animation definitions based on the binocular animation.
- `REWARDTABLE.EXML` adds 31 `GcRewardMission` entries. Each reward starts one named finder mission.
- `NPCMISSIONTABLE.EXML` adds 31 search missions and 31 `R_` helper missions. A helper starts its
  paired search mission, waits, and has `RestartOnCompletion=true`; the search mission starts a scan
  event, waits for locality/navigation conditions, performs `GcMissionSequenceQuickWarp`, marks the
  target portal, ends the scan event, and reports completion.
- The 31 query profiles cover 16 Lush variants, two Swamp variants, one Green variant, four Frozen
  variants, four Barren variants, one Scorched variant, two Waterworld variants, and one Gas Giant
  variant. In this file, every primary and fallback system lookup also requires an undiscovered
  system and `NeedsWaterPlanet=true`, and excludes extreme weather and extreme sentinels.
- The custom scene is the model attached to the `SYSTEM_SCAN` emote. Its locator attaches the custom
  entity, whose `SuperDoopaScanner` interaction plays the signal-scanner sound and fires the simple
  interaction.
- `LocTable.MXML` supplies menu, objective, tooltip, and mission text. Most language fields repeat
  the English values; Simplified and Traditional Chinese contain translated strings.

This is all accepted game data: EXML merge patches, full MBIN objects, localization MXML, and DDS
resources. AMUMSS generated some files, but neither the game nor this analysis executes a Lua
script.

## Merge and conflict surface

The reward and mission patches primarily append entries through `_id`, so their direct collision
surface is their custom IDs. The other two patches are broader:

- `EMOTEMENU.EXML` deliberately rewrites the existing `MEGA_WARP` and `SYSTEM_SCAN` records before
  adding its own records. Another mod changing either emote can conflict by priority.
- `PLAYERCHARACTER.ENTITY.EXML` targets the shared player attachment. It extends the existing `BOOT`
  trigger state and includes a large `TkAnimationComponentData` subtree with hundreds of generated
  `_index` selectors. This is both a high-overlap mod conflict surface and an update-sensitive
  surface.
- The two custom MBINs and 11 custom textures use a `LUSHFINDER` namespace and do not replace
  vanilla files, but anything that reuses those exact custom paths or IDs collides.
- The localization table can override another mod only if that mod reuses the same localization IDs.

Load order cannot repair a stale serialized layout. It can only select which replacement or patch
wins after every participating file is readable.

## Cosmos 7.01 compatibility evidence

The exact installed game is Cosmos 7.01, Steam build `25233815`. The current vanilla reward table,
NPC mission table, emote menu, and player entity were located in the installed HGPAKs, extracted
with HGPAKtool commit `2ea9b0351f93b72e4fa3d199bf4ac54149f748f8`, and successfully decompiled with
MBINCompiler `v7.01.0-pre1` (`abeaf218ad6e0792be7bc1e64b0128c98a53ac3d`). That establishes that the
current compiler/toolchain can read the comparison inputs.

The two packaged custom MBINs report compiler version `6.45.0.1`:

| File                     | 7.01 compiler result                  | Meaning                                                                                                    |
| ------------------------ | ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `SYSTEMSCAN.ENTITY.MBIN` | Successfully decompiled               | Its top-level `cTkAttachmentData` remains readable; this alone does not validate every referenced behavior |
| `SYSTEMSCAN.SCENE.MBIN`  | Rejected, then `EndOfStreamException` | Its 6.45 `cTkSceneNodeData` binary layout is not a valid 7.01 object                                       |

The relevant MBINCompiler source change is explicit. From 6.45 to 7.01, `TkSceneNodeData` changed
GUID from `42A57794F683F216` to `AD96A863591F02D8`, gained an `InstanceTransforms` list, moved
`Children` from serialized index 6 to 7, and shifted the fields after it by 16 bytes. The current
compiler reports exactly those old and expected GUIDs when it rejects the packaged scene. The 6.45
compiler successfully decompiles the same bytes, ruling out archive corruption.

The loose EXML patches also cross changed schemas:

- `GcScanEventData`, central to all 31 searches, gained a story-utility tag and multiple space-POI
  fields, changing its serialized layout and generated indices.
- `TkAnimationComponentData` gained `LimbJointMappings`, and each `TkAnimationData` gained
  `LimbPlants`; the large player patch was generated without either field.
- `NPCMISSIONTABLE.EXML` emits an obsolete `ForcesPageHint` property 62 times. That property exists
  in neither the checked 6.45 nor 7.01 MBINCompiler template.
- Fifteen of the 80 MBIN template classes referenced by the patch set changed between the checked
  6.45 and 7.01 compiler tags. Some changes are GUID-only; others alter fields and offsets.

Missing fields in a partial EXML object may receive defaults, so schema drift alone does not prove
that each EXML operation fails. It does prove that the old generated patch cannot be accepted on
version strings alone: it needs a current-schema regeneration followed by exported merged-metadata
validation. The stale full scene MBIN is independently sufficient to reject the archive as a Cosmos
7.01 deployment candidate.

## Acceptance boundary

A future release can move out of `diagnostic-only` only when all of these are true:

1. It has a new immutable Nexus file identity and SHA-256 catalog pin.
2. Every packaged MBIN is accepted by the compiler matching the exact installed game build.
3. Every EXML target and generated `_index` is compared with current vanilla data.
4. The game's exported merged metadata contains all 31 rewards, emotes, mission pairs, animation
   triggers, and expected scan filters without damaging unrelated current fields.
5. Isolated runtime validation exercises menu launch, system scan, target search, quick warp,
   mission restart/cancel/completion, and save reload with a backed-up disposable save.
6. Conflict checks cover at least another emote-menu patch and another player-entity animation or
   trigger patch in both priority orders.

Author permission would also be required before this repository could distribute a rebuilt version
or changed assets. A private diagnostic result does not grant that permission.

## Reproduction

Acquire, verify, and inventory the exact local bytes through the repo-wide dispatcher:

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-3368-47562-lush-finder-full \
  --archive '/home/scott/Downloads/Lush Finder (Full Mission Mode) 3368 3.3.6.45 2026-07-23T16-43Z 8gT07OStD.zip'

tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-3368-47562-lush-finder-full

tooling/squinch third-party no-mans-sky validate
```

`import` and `inspect` are idempotent when the existing bytes/report match. They fail closed if a
same-identity cache or inspection destination contains different bytes.

For the loader, format, Bazzite paths, and validation model used here, see the
[No Man's Sky modding architecture](../../README.md). For credential and cache behavior, see the
[third-party tool documentation](../../../../../games/no-mans-sky/tooling/third-party/README.md).

## Public references

- Hello Games, [Cosmos 7.01](https://www.nomanssky.com/2026/09/cosmos-7-01/).
- MBINCompiler,
  [7.01 `TkSceneNodeData`](https://github.com/monkeyman192/MBINCompiler/blob/abeaf218ad6e0792be7bc1e64b0128c98a53ac3d/libMBIN/Source/NMS/Toolkit/TkSceneNodeData.cs).
- MBINCompiler,
  [6.45 `TkSceneNodeData`](https://github.com/monkeyman192/MBINCompiler/blob/v6.45.0-pre1/libMBIN/Source/NMS/Toolkit/TkSceneNodeData.cs).
- Nexus Mods, [Lush Finder files](https://www.nexusmods.com/nomanssky/mods/3368?tab=files) and
  [author permissions](https://www.nexusmods.com/nomanssky/mods/3368?tab=description).
