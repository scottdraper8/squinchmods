# C2ME DFC preview-to-world parity

## Result

The 18-cell production-client matrix is complete: parent, focused fix, and `experimentalChunkFixes`,
each with C2ME DFC enabled, C2ME DFC disabled, and C2ME absent, on both Fabric and NeoForge. Every
accepted execution used seed `3216933670`, the same modern-default preset, an isolated production
client, packaged FTF, and the exact catalog C2ME artifact. No valid cell crashed or leaked an owned
JVM; all 18 manifests report complete cleanup.

The matrix establishes two distinct facts:

1. The focused fix restores runtime terrain. Its DFC-on runtime biome and height digests are exactly
   the same as DFC-off, C2ME-absent, and the correct parent references on both loaders. The broken
   parent DFC-on cell has different runtime biome and height digests on both loaders while the
   displayed preview digest remains unchanged.
2. FTF's displayed preview is not an exact finished-world oracle, independently of C2ME or this fix.
   In every correct compact cell, 3,356 of 65,536 preview biome pixels differ from direct runtime
   sampling at the generator's real `WORLD_SURFACE_WG` height; 60,768 of 65,536 preview heights
   differ. The same preview, runtime, and mismatch digests recur on both loaders and all correct
   compact-schema cells. The strict probe therefore records `status = "fail"`, but that status is an
   intentional parity assertion, not a client crash or incomplete execution.

Scope warning: these runs captured the first accepted frame at zoom 50 and immediately applied the
preset. They do not test post-interaction regeneration after moving the UI zoom control to 80/90.
Later manual screenshots report apparent on/off differences in that untested state. Until a fresh
controlled reproduction retains seed, exported preset, center, exact artifacts, C2ME startup log,
and every frame ordinal through quiescence, the zoom-50 equality must not be generalized to that
report.

## Final evidence matrix

Performance is the median of three fresh packaged-Fabric JVM medians. Each JVM contains a 441-chunk
warmup and seven disjoint timed 441-chunk windows, for 27 JVMs and 189 timed windows. Server-side
terrain, biome, banding, and storage results are fixed-coordinate exact hashes from packaged Fabric
and NeoForge. Client results use the actual frame accepted by `Preview2D.applyGeneratedFrame`, not a
replacement preview calculation.

| Revision               | Mode          | Performance             | Terrain/density                                                                                    | 3D biome layout               | Underground bands      | Stored biome                 | Preview -> runtime                                                                                                | Preview -> finished world                                                    |
| ---------------------- | ------------- | ----------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------- | ---------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| parent `22a212b`       | C2ME, DFC on  | 9.9893 s / 44.1472 cps  | **Failing control:** wrong terrain on both loaders; digest `aa3ae9ec...` rather than `180ca0a8...` | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Failing control:** preview stays `c57d8272...`, runtime changes to biome `0897e92e...` and height `f8a2bdfe...` | Central 49/49 agree, but this does not rescue the wrong full runtime digests |
| parent `22a212b`       | C2ME, DFC off | 3.3105 s / 133.2121 cps | **Pass:** reference `180ca0a8...`                                                                  | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** 3,356/65,536 biome and 60,768/65,536 height differences                                          | Central 49/49 agree on both loaders; broad exact parity is not established   |
| parent `22a212b`       | C2ME absent   | 13.8262 s / 31.8960 cps | **Pass:** exact reference                                                                          | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | Central 49/49 agree on both loaders; broad exact parity is not established   |
| fix `9412025`          | C2ME, DFC on  | 2.8626 s / 154.0536 cps | **Pass:** exact reference                                                                          | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | NeoForge center 49/49; broad Fabric control has 16/337 composite differences |
| fix `9412025`          | C2ME, DFC off | 3.0991 s / 142.2998 cps | **Pass:** exact reference                                                                          | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | NeoForge center 49/49; broad Fabric control has 25/337 composite differences |
| fix `9412025`          | C2ME absent   | 13.4192 s / 32.8635 cps | **Pass:** exact reference                                                                          | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | Central 49/49 agree on both loaders; broad exact parity is not established   |
| experimental `8591d2b` | C2ME, DFC on  | 2.7975 s / 157.6388 cps | **Pass:** exact reference in the packaged-server corpus                                            | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | Central 49/49 agree on both loaders; broad exact parity is not established   |
| experimental `8591d2b` | C2ME, DFC off | 3.1738 s / 138.9517 cps | **Pass:** exact reference in the packaged-server corpus                                            | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | Central 49/49 agree on both loaders; broad exact parity is not established   |
| experimental `8591d2b` | C2ME absent   | 13.6768 s / 32.2445 cps | **Pass:** exact reference in the packaged-server corpus                                            | **Pass:** exact `41745687...` | **Pass:** exact counts | **Pass:** 512/512 per loader | **Approximate:** same correct hashes and difference counts                                                        | Central 49/49 agree on both loaders; broad exact parity is not established   |

## Exact cross-cell digests

All 18 client cells applied the same preview biome grid and raster:

- biome grid: `c57d8272793aebf78bf3dcc79865d57bd8d53f6f580c618aeed7db73e7d06392`
- uploaded raster: `14cf83b2c6c16c3fc9bfd3b619fe5c44a38c86e98327c7107cbe8b6bda048821`

All 16 compact-schema cells that retain a preview-height digest share
`ea1ea6a194d0dd06949b361e02f6e5515125a1aa692b06b94848508bae06c464`.

The 16 correct cells, including every focused-fix and experimental cell, share:

- runtime surface biome: `600bd1af057ddf384b5f13bbccc0fd866e3bcc7aa9119f33717134d04c07c54c`
- runtime surface height: `4b544562f5666ffd8ecd990d8013b42a1ade6beee505273553854efad0806146`
- preview/runtime biome differences: 3,356 of 65,536
- preview/runtime height differences: 60,768 of 65,536 in every compact-schema cell

The two parent DFC-on controls, one per loader, share the same different runtime digests:

- runtime surface biome: `0897e92e86f356848b64e45d75c423f4dbe948b5e1c427ce9dcf188158cd92fe`
- runtime surface height: `f8a2bdfe009809aea99d3913c609051bedf44257a257d27465d1951ce1db8ee5`
- preview/runtime height differences: 61,674 of 65,536

The biome difference count happens also to be 3,356 in the broken controls. The ordered digest—not
the scalar count—is what detects that C2ME DFC changed the actual surface layout.

The packaged-server matrix provides a separate lower-layer authority. Sixteen correct cells share
terrain digest `180ca0a8de7c38976b7dac5d34648f2066bda2ffacd0bd69e617562c7d224514`; the two-loader
parent DFC-on controls share `aa3ae9ec0dc82b96968c10c27773883bfc657a919f1c0f015fa326ff6f897d97`. All
18 cells share 3D biome digest `4174568743a25b34a69b70aeefbb9e2a10b600d5cc3062d9f786df6f6da7e5b9`,
59,061 cave cells (32,151 lower, 14,466 middle, 12,444 upper), and 512/512 stored/direct biome
matches per loader cell.

## Production-client run inventory

| Revision     | Loader   | Mode           | Run ID                        | Cleanup  |
| ------------ | -------- | -------------- | ----------------------------- | -------- |
| parent       | Fabric   | DFC on         | `20260907T123215Z-ca5be68d5a` | complete |
| parent       | Fabric   | DFC off        | `20260907T123645Z-3e66d1f461` | complete |
| parent       | Fabric   | C2ME absent    | `20260907T124342Z-b855adaa9d` | complete |
| fix          | Fabric   | DFC on, broad  | `20260907T113001Z-9ff7d1284a` | complete |
| fix          | Fabric   | DFC off, broad | `20260907T110800Z-dd71c52461` | complete |
| fix          | Fabric   | C2ME absent    | `20260907T120652Z-918236d815` | complete |
| experimental | Fabric   | DFC on         | `20260907T125139Z-3efc8ba7a1` | complete |
| experimental | Fabric   | DFC off        | `20260907T125643Z-f1fd92819d` | complete |
| experimental | Fabric   | C2ME absent    | `20260907T130334Z-2f5e65e683` | complete |
| parent       | NeoForge | DFC on         | `20260907T133911Z-66dd300348` | complete |
| parent       | NeoForge | DFC off        | `20260907T134424Z-261d4fa2d8` | complete |
| parent       | NeoForge | C2ME absent    | `20260907T135149Z-a824b7ed70` | complete |
| fix          | NeoForge | DFC on         | `20260907T132650Z-6a86c0896a` | complete |
| fix          | NeoForge | DFC off        | `20260907T133221Z-3c370a5fd6` | complete |
| fix          | NeoForge | C2ME absent    | `20260907T131943Z-dd9b1efff8` | complete |
| experimental | NeoForge | DFC on         | `20260907T135922Z-8c8b2e310f` | complete |
| experimental | NeoForge | DFC off        | `20260907T140432Z-24147c18cd` | complete |
| experimental | NeoForge | C2ME absent    | `20260907T141114Z-460e2f7c8a` | complete |

## Interpretation limits

The compact finished-world check deliberately materializes a contiguous 7 x 7 center rather than
widely separated chunks. It proves the client can create, finish, store, query, save, and clean up a
real world, and that direct, stored, and repeated direct samples agree at those 49 positions. It is
not a proof that every preview pixel exactly predicts every finished block biome.

The earlier 337-point Fabric controls generated sparse chunks across a 12,800-block viewport. They
found ordinary edge differences among preview, direct quart sampling, stored noise biomes, and
Minecraft's fuzzy `getBiome` zoom. More importantly, each sparse run generated 8,289 FTF chunks and
left 154,953 Minecraft chunk holders waiting to unload. It was unsuitable as an 18-cell client
acceptance workload. Its differences must not be relabeled as C2ME regressions.

The experimental branch matches this default-preset corpus, but that does not validate its extra
identity, out-of-chunk climate, compiled-function unwrapping, or wrapping-timing changes. The
focused fix remains the smallest change directly supported by the established lifecycle cause.

## Tooling validation and rejected setup attempts

The production client now packages FTF and the probe for both loaders, stages the exact catalog C2ME
JAR, uses an isolated run directory and owned display, and never touches a personal launcher.
NeoForge `21.1.219` is installed under the investigation cache; launcher libraries are resolved from
the official version metadata and verified by SHA-1. The full investigation-tool test suite passes:
135 tests in 52.52 seconds.

Three NeoForge setup runs are rejected as non-behavior evidence and all cleaned up:

- `20260907T131657Z-d519889514`: the first production task lacked installer configuration.
- `20260907T131743Z-2741131736`: the isolated install lacked ordinary Mojang libraries.
- `20260907T131843Z-fe96992178`: the launch included both vanilla and NeoForge's patched Minecraft
  module.

These were launcher-construction failures before a valid FTF/C2ME experiment, not mod crashes.
