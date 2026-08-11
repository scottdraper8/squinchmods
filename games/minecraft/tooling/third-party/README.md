# Minecraft third-party acquisition

This tool owns two different artifacts used by investigations:

- Modrinth release JARs for actually running a companion mod.
- Shallow, sparse source checkouts for reviewing the implementation that corresponds to the
  Minecraft version under investigation.

The two are intentionally separate. A source checkout is not assumed to be buildable or to be the
same revision as a published release. A runtime JAR is never silently replaced by a source build.

## Acquire a catalog artifact

The committed catalog at `.squinch/games/minecraft/third-party/artifacts.toml` pins the Modrinth
project, Minecraft version, loader, published version, filename, and SHA-256. Acquire by catalog ID;
the tool resolves that exact release and writes an acquisition manifest beside the cached JAR:

```bash
tooling/squinch third-party acquire \
  --artifact-id mc1.21.1-fabric-immersive-ores-1.1.8

tooling/squinch third-party acquire \
  --artifact-id mc1.21.1-neoforge-mekanism-10.7.19.85
```

Validate the entire active catalog and cache with `tooling/squinch third-party validate`. The cache
is under `${SQINCHMODS_CACHE_HOME}/third-party/modrinth/<minecraft>/<loader>/<project>/<version>/`.
The command prints the exact local JAR path, version ID, version number, and SHA-256.

Required Modrinth dependencies are reported in the command output. Acquisition does not silently
download them into an investigation because the runtime may already provide them, and adding them
can change the experiment. Acquire each required dependency explicitly when it is part of the
intended matrix.

Use the catalog ID in `companion_artifacts = ["<catalog artifact ID>"]` in a scenario. The scenario
runner verifies the catalog record and acquisition manifest before copying the JAR into the isolated
run, then records the ID, hash, and materialized runtime path in the manifest.

## Acquire source

Source acquisition requires an explicit branch or tag and at least one sparse path. The checkout is
one commit deep, blob-filtered, and records the requested ref plus resolved commit in
`source-acquisition.json`:

```bash
tooling/squinch third-party source \
  --repository https://github.com/Creators-of-Create/Create.git \
  --destination games/minecraft/reference/sources/1.21.1/mods/create \
  --ref mc1.21.1/dev \
  --minecraft-version 1.21.1 \
  --sparse src/main/java/com/simibubi/create/infrastructure/worldgen \
  --sparse src/generated/resources/data/create/worldgen
```

An existing checkout is rejected. Updating means intentionally re-running with `--replace` after
confirming the exact destination; this prevents a source review from accidentally changing revisions
in place. The tool does not build source checkouts: source projects can use different loaders,
Gradle wrappers, and dependency requirements, so build them only as a separate, explicit action when
source behavior itself must be inspected.

## Remove acquired artifacts

Removal is explicit and guarded. By default, `remove` only validates the exact acquisition manifest
and prints what it would remove. Add `--apply` to remove the exact cached version and, when
supplied, the exact source checkout:

```bash
tooling/squinch third-party remove \
  --artifact-id mc1.21.1-fabric-immersive-ores-1.1.8 \
  --apply
```

The cache target must contain an acquisition manifest matching the requested project, Minecraft
version, and loader. Source deletion is only accepted below
`games/minecraft/reference/sources/<version>/<mod>`. The command never removes a project cache root
or discovers source checkouts implicitly; this keeps cleanup recoverable at the planning stage and
prevents a broad or mismatched deletion.
