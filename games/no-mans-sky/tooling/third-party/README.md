# No Man's Sky third-party acquisition

This tool acquires exact Nexus Mods files for local investigation without committing or
redistributing author-owned archives. It follows the Minecraft catalog/cache pattern while keeping
Nexus authentication and the post-download unpacking boundary explicit.

## Ownership and paths

| Content                                                                    | Location                                                                               | Git state          |
| -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------ |
| Artifact identity, file ID, compatibility claim, status, and expected hash | `.squinch/games/no-mans-sky/third-party/artifacts.toml`                                | Committed          |
| Downloaded archive and `acquisition.json`                                  | `${SQINCHMODS_CACHE_HOME}/third-party/nexus-mods/nomanssky/<mod-id>/<file-id>/`        | Outside repository |
| Safely unpacked files and `inspection.json`                                | `games/no-mans-sky/reference/sources/<claimed-nms-version>/mods/<mod-slug>/<file-id>/` | Ignored            |
| API and short-lived download credentials                                   | Environment only                                                                       | Never written      |

The catalog may contain `pending-authentication` entries with an empty archive filename and hash.
That state records a known Nexus identity, but it is not an approved artifact. After the first
acquisition, copy the exact returned filename and SHA-256 into the catalog and change its status to
`approved` or `diagnostic-only`. `validate` requires both pins for either active status.

## Nexus authentication

Every Nexus v1 metadata request requires a Nexus account and personal API key. Generate a key on the
[Nexus Mods API Access page](https://www.nexusmods.com/users/myaccount?tab=api%20access), then
expose it only to the command process:

```bash
read -rsp 'Nexus API key: ' NEXUSMODS_API_KEY
export NEXUSMODS_API_KEY
echo
```

Do not put the key in the catalog, a `.env` file, shell history, acquisition output, or an agent
prompt. The tool reads it from `NEXUSMODS_API_KEY`, sends it as the `apikey` header, and never
serializes it.

An API key is necessary but does not necessarily authorize unattended downloads. Nexus normally
limits API-only download links to Premium accounts. A free account can initiate **Mod Manager
Download** in a logged-in browser and pass the short-lived `key` and `expires` values from the
resulting `nxm://` URL through `NEXUSMODS_DOWNLOAD_KEY` and `NEXUSMODS_DOWNLOAD_EXPIRES`. Those
values are also never persisted. The simpler free-account path is manual browser download followed
by `import`.

If this tool becomes a public-facing application, a personal key is no longer the appropriate
authentication model. Nexus's API policy requires application registration and user authorization.

## Catalog-backed workflow

Inspect the exact live metadata named by the catalog:

```bash
tooling/squinch third-party no-mans-sky metadata \
  --artifact-id nms-nexus-3368-47562-lush-finder-full
```

For a Premium account, or after exporting the short-lived free-account download values:

```bash
tooling/squinch third-party no-mans-sky acquire \
  --artifact-id nms-nexus-3368-47562-lush-finder-full
```

For a normal manual browser download:

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-3368-47562-lush-finder-full \
  --archive '/home/scott/Downloads/<exact Nexus archive name>'
```

Both acquisition paths copy the archive into the same catalog-identity cache location, calculate
SHA-256, and write `acquisition.json`. They do not deploy the mod into the game.

Unpack and inventory it for review:

```bash
tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-3368-47562-lush-finder-full
```

Inspection rejects absolute paths, parent traversal, symbolic links, and special files before
materializing the ignored tree. Its report identifies runtime formats, authoring/documentation
files, unknown files, candidate deployment roots, sizes, and per-file SHA-256 hashes. It is an
inventory, not a declaration that the mod is compatible or safe to run.

Validate all active catalog entries against their cached bytes and manifests:

```bash
tooling/squinch third-party no-mans-sky validate
```

Removal is a dry run unless `--apply` is explicit. It targets only the exact catalog cache and
inspection directories and requires their ownership manifests before deletion:

```bash
tooling/squinch third-party no-mans-sky remove \
  --artifact-id nms-nexus-3368-47562-lush-finder-full
```

## Acquired inspection corpus

All three pinned files are `diagnostic-only`; that status authorizes local evidence use, not game
deployment or redistribution.

| Mod and Nexus file                    | Claimed NMS version | SHA-256                                                            | Cosmos 7.01 static result                                          |
| ------------------------------------- | ------------------: | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Lush Finder Full Mission `47562`      |                6.45 | `9775f897f85a20fd59074ddca7aeba2de4c48b3fe0fafff358ff8f2dc521c9d9` | Rejected: packaged scene has a stale binary layout                 |
| Ship Parts Catalogue `44949`          |                6.16 | `5e94eadbefcaf993c603b14b180dab79ec536b85c5c4377c7212c11b77612365` | Likely loadable, but its fixed list omits current Corvette content |
| Expedition Catalogue Improved `47075` |                6.40 | `d6d990e85e8a96ad8a534da6b00b3fcf3c8932b60d6ff7c7958ea3ab5fe01be0` | Rejected: stale GUI layout and omission of released Expedition 23  |

The Nexus permission settings for each file prohibit reuploading and require permission to modify
the author's work. Therefore:

- the archive and unpacked contents remain local and ignored;
- no file should be copied into a committed fixture or redistributed from the cache;
- a future compatible author release must receive its own Nexus file ID and catalog entry; and
- runtime validation, if later authorized, must use a backed-up save and an isolated deployment.

Detailed content and compatibility analyses:

- [Lush Finder inspection](../../../../.agent-docs/games/no-mans-sky/refs/third-party/lush-finder.md)
- [Ship Parts Catalogue inspection](../../../../.agent-docs/games/no-mans-sky/refs/third-party/ship-parts-catalogue.md)
- [Expedition Catalogue Improved inspection](../../../../.agent-docs/games/no-mans-sky/refs/third-party/expedition-catalogue-improved.md)

## References

- [Nexus Mods API Acceptable Use Policy](https://help.nexusmods.com/article/114-api-acceptable-use-policy)
- [Nexus Mods API v3 OpenAPI source](https://github.com/Nexus-Mods/Vortex/blob/master/packages/nexus-api-v3/schema/openapi.yaml)
- [Lush Finder description and permissions](https://www.nexusmods.com/nomanssky/mods/3368?tab=description)
- [Lush Finder file list](https://www.nexusmods.com/nomanssky/mods/3368?tab=files)
- [Ship Parts Catalogue description and permissions](https://www.nexusmods.com/nomanssky/mods/3013?tab=description)
- [Ship Parts Catalogue file list](https://www.nexusmods.com/nomanssky/mods/3013?tab=files)
- [Expedition Catalogue Improved description and permissions](https://www.nexusmods.com/nomanssky/mods/3064?tab=description)
- [Expedition Catalogue Improved file list](https://www.nexusmods.com/nomanssky/mods/3064?tab=files)
