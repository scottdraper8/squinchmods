# C2ME density-function compiler compatibility

Status: implementation complete at `9412025` on `fix/c2me-dfc-compatibility`; current-tip
functional, cross-loader, reload, production-client creation, packaging, cleanup, and healthy-host
performance gates pass. The expanded performance, packaged-server, three-dimensional biome/banding,
and 18-cell actual-preview matrices are complete. The focused fix restores the DFC-on runtime to the
DFC-off/C2ME-absent reference without changing the tested three-dimensional biome field. The first
actual applied preview at zoom 50 is invariant across branches, modes, and loaders for the pinned
seed and modern-default preset, but is intrinsically approximate rather than an exact prediction of
runtime surface height or biome at every pixel. Post-interaction regeneration at the reported zoom
80/90 remains open and must not be inferred from that initial-frame corpus.

This plan is subordinate to `worldgen-compatibility.md` and its companion runtime and invariant
documents. Live source, dependencies, host state, and retained artifacts supersede this plan.

## Objective

FreeTerraForged generation must preserve its documented terrain and density behavior when C2ME's
density-function compiler is absent, disabled, explicitly enabled, or enabled by its current
default. Compatibility must restore the public Minecraft density-function lifecycle rather than
dispatching on C2ME identity, suppressing third-party compilation, or maintaining a private second
density graph.

The active implementation branch is `fix/c2me-dfc-compatibility` in
`games/minecraft/investigation-state/worktrees/ftf-c2me-dfc-compatibility`, based on live
`upstream/1.21.1` commit `22a212bbcfe5bb697251417a399cf4ff4acba5b7`.

## Established root cause

Vanilla `NoiseChunk` obtains `RandomState.router()` and invokes `NoiseRouter.mapAll(this::wrap)`
once to create the chunk-owned router. `wrapNew` registers `NoiseInterpolator`, `FlatCache`,
`Cache2D`, `CacheOnce`, and `CacheAllInCell` instances and maps FTF `CellSampler` leaves to
request-owned `CellSampler.CacheChunk` instances. A later, narrower mapping constructs cached final
density; it is not a replacement for the first whole-router pass.

Upstream FTF replaced that first call with a `@Redirect` whose handler initialized FTF state and
returned the unvisited `RandomState.router()`. That suppressed a public vanilla lifecycle boundary,
not merely an optimization. C2ME DFC compiles the `RandomState` router after FTF has installed its
deferred `CellSampler` leaves. When `NoiseChunk` maps a compiled function, C2ME clones the compiled
entry and applies the supplied visitor to captured density-function arguments. Suppressing the call
therefore prevents C2ME from ever receiving `NoiseChunk::wrap`; the compiled graph remains unbound
to the chunk. With DFC disabled, vanilla's later final-density mapping partially masks the defect by
initializing a subset of wrappers. With DFC enabled, C2ME's compiled final-density path does not
recreate the omitted whole-router lifecycle.

This mechanism is independently established by exact source/bytecode and runtime falsification:

- Before the fix, explicit-off run `20260906T015140Z-d0a81c88fe` initialized wrappers in every
  observed constructor, while explicit-on run `20260906T015217Z-56e0ae2917` recorded zero
  interpolators, zero wrapped functions, and zero mapped FTF cell samplers in all 1,351 observed
  constructors.
- The same pre-fix pair differed in 24 of 144 pre-surface noise-stage height hashes, including six
  chunks at least two chunks inside the forced region. All pre-surface biome hashes matched, which
  isolates the demonstrated failure to density/aquifer terrain in that corpus rather than feature
  ordering or preview rendering.
- After replacing the redirect with an injection immediately before the original call, explicit off
  and on produce the same all-region pre-surface terrain hash
  `c3c9fd38d6eb17cde37c60e654cf2cb66da30587df10084b35071c64a4e78ab1` and biome hash
  `e31b6068c7e34e482c884e5c5d8e18cf62a7e62a7f853efb9958acfcf8f07aba` on both loaders.
- Instrumented default runs observe exactly one before-call and one after-call event for every
  constructor: Fabric run `20260906T020652Z-1fb5bb3d5e` has 1,366/1,366/1,366 and NeoForge run
  `20260906T020737Z-1619a398c5` has 1,336/1,336/1,336 constructors/before/after, with zero invalid
  constructors and nonzero interpolator and `CellSampler.CacheChunk` totals.

The production correction initializes FTF request state in an `@Inject` before the invocation and
leaves vanilla's call, visitor, returned router, and C2ME's stable compiled-entry visitor contract
intact. It contains no C2ME class, mod ID, version, configuration parsing, or private bridge.

The live `upstream/experimentalChunkFixes` tip `8591d2b` does not contain fix commit `9412025`:
`git merge-base --is-ancestor` is false, and the branches share older ancestor `95c9b21`.
Experimental independently replaces the bad redirect with a before-`mapAll` injection, so it does
contain the root lifecycle correction in equivalent form. It also changes `CellSampler` equality and
hashing, changes an out-of-chunk fallback from `sampleClimate = false` to `true`, introduces an
`RTFCellFunction` unwrapping bridge and access wideners, and moves the `wrapNew` interception from
entry to return. Those extra identity, sampling, and wrapping semantics are not required by the
established root cause. The branch also predates and does not contain upstream `22a212b` and its
trail-ruins correction. Merge the focused fix into current `1.21.1`; treat experimental's additions
as separate changes requiring their own correctness and parity evidence.

## Acquisition

- Fabric latest exact-version control: catalog ID `mc1.21.1-fabric-c2me-0.4.0-alpha.0.27+1.21.1`,
  Modrinth version `gRm1ZAvc`, SHA-256
  `f0a488fa26a1d1c7668f644527c470941d41474da2d7d620620da13473509b84`.
- NeoForge latest exact-version primary: catalog ID
  `mc1.21.1-neoforge-c2me-0.4.0-alpha.0.120+1.21.1`, Modrinth version `kvrPcTsz`, SHA-256
  `67fe384ae84f947e999a02ebde5f5e7de3a632803304a625beee9c4268509a76`.
- Reported-version regression control: catalog ID `mc1.21.1-neoforge-c2me-0.4.0-alpha.0.112+1.21.1`,
  Modrinth version `GzlGNw5O`, SHA-256
  `961e80018496036a47421617c9891bb58c71c13ad82211f557a81d0a14579ffd`.
- All JARs were acquired and validated through `tooling/squinch third-party`. The NeoForge source
  checkout is shallow at outer commit `92646290596cd9a39df3fb1f0ed2da0071bf1fdb`; its Java base is a
  gitlink that the acquisition pipeline cannot materialize. Exact shipped JAR bytecode is therefore
  the behavior-bearing authority for C2ME internals.

## Retained acceptance evidence

- Fixed Fabric explicit-off/on/default: `20260906T015326Z-2852a76b03`,
  `20260906T015400Z-bf60e5f75b`, and `20260906T015447Z-ba385260ee`. All 144 pre-surface terrain and
  biome hashes match. Finished-chunk differences are limited to the outer generated boundary and
  recur between identical modes; they are cross-chunk feature timing, not density evidence.
- C2ME-absent Fabric: `20260906T015541Z-666e613e13`. Its pre-surface terrain and biome hashes match
  fixed explicit-off/on/default.
- Fixed production NeoForge latest explicit-off/on/default: `20260906T020332Z-f35beb0777`,
  `20260906T020359Z-952a127d5f`, and `20260906T020235Z-c4e049f524`. All 144 pre-surface hashes match
  each other and Fabric.
- NeoForge `.112` reported-version default regression control: `20260906T020448Z-c63567fb8d`. It
  matches the latest release and both loaders at the pre-surface layer.
- Packaged Fabric latest/default: `20260906T021025Z-8c5f5083d8`. It matches the common hashes and
  proves the remapped artifact plus exact C2ME and cataloged Fabric API on Java 21.
- Fabric client lifecycle with generated/default C2ME config: `20260906T015808Z-265227d792`. The
  config remains `"default"`, generated DFC classes exist, world creation completes, and located,
  queried, stored, and zoomed surface biome observations agree.
- Packaged reload and disjoint post-reload generation: `20260906T021150Z-6481bf0c83` (Fabric) and
  `20260906T021217Z-106fa3b920` (NeoForge). Both loaders share pre-reload terrain hash `2210b921...`
  and post-reload hash `adb5ed0d...`; every cumulative constructor has exactly one completed router
  mapping and nonzero wrappers.
- `./gradlew test build` passes. Remapped Fabric artifact SHA-256 `4ada14db...` and NeoForge
  artifact SHA-256 `4908f9ef...` pass `mc-investigate inspect-artifact` with no development-probe
  findings. Artifact hashes identify this working-tree build and may change after subsequent source
  edits.

The NeoForge development launch is not a valid runtime authority for these catalog JARs: latest run
`20260906T015933Z-afd0b73eca` and `.112` run `20260906T020110Z-a09a370457` both fail before world
creation because C2ME chunk-I/O targets missing synthetic method `IOWorker.lambda$submitTask$13`
without a refmap. The same exact artifacts pass under the production NeoForge launcher. Failed
`cell-scan` run `20260906T015109Z-ca56764098` retains the documented plain-upstream `RegistryAccess`
fixture-tool boundary and has no bearing on runtime results.

Healthy-host packaged-server benchmarks use a 441-chunk warmup followed by seven disjoint 441-chunk
finished-chunk windows in fresh worlds. Three independent Fabric JVMs per side improve from a
21.160554-second median of run medians (20.8407 chunks/second) before the fix to 5.572777 seconds
(79.1347 chunks/second) after it: 3.7971x throughput and 73.6643% less generation time. All 21 fixed
observations are faster than all 21 parent observations. One accepted NeoForge parent and two
accepted fixed JVMs independently measure 4.1909x-4.1971x throughput; further parent replication is
bounded by the demonstrated pre-fix generation hang rather than folded into the performance set.

Six Fabric JFRs attribute 73.49%-74.75% of parent execution samples to repeated `ImprovedNoise` and
`PerlinNoise` evaluation, versus 8.67%-9.15% after the fix. Fixed profiles execute
`CellSampler.CacheChunk` and `PointCellCache`, directly matching the restored router mapping and
request-owned cache lifecycle. Estimated allocation falls 10.30%; comparable or slightly higher
fixed-side GC pause totals exclude favorable GC timing as the speedup explanation. Startup, probe,
save, and shutdown time are excluded. Exact inputs, observations, calculations, profiles, rejected
runs, and interpretation limits are retained under
`games/minecraft/investigation-state/analysis/c2me-dfc-performance-20260906T040000Z/`.

This is an operational comparison between the broken parent output and corrected output, not a
same-output microbenchmark: the two artifacts are already proven to generate different terrain. It
establishes that restoring correctness also restores the intended cache behavior and does not
introduce a performance regression for the measured preset, seed, hardware, and exact C2ME builds.

### Expanded runtime-mode matrix

The requested follow-up matrix distinguishes C2ME with DFC explicitly enabled, C2ME with DFC
explicitly disabled, and C2ME absent across exact parent `22a212b`, fix `9412025`, and the live
`upstream/experimentalChunkFixes` tip `8591d2b`. All cells use the same packaged Fabric harness,
seed, preset, 441-chunk warmup, and seven disjoint 441-chunk finished-chunk windows. JFR is excluded
after the cross-loader HotSpot failures recorded in `agentic-development-findings.md`.

The original runner retained all earlier force-load tickets, so an eight-window benchmark grew from
441 to 3,528 simultaneously forced chunks. At 4 GiB, profiler-free fixed/no-C2ME run
`20260907T010315Z-1c6346bcbf` reached 4.17 GiB G1 usage and crashed in
`RegisterNMethodOopClosure::do_oop`. The accumulated-ticket results are rejected for this matrix.
The corrected runner durably removes only the current observation's four acknowledged regions after
its terminal probe and records release time outside the metric. The final matrix uses 12 GiB on the
same Temurin 21.0.11+10 JVM. All 27 scenarios and 189 measured windows passed, with exact
four-region release, complete cleanup, inactive investigation state, and zero surviving JVMs after
each run.

The independent unit is one JVM. Values below are the median of three JVM medians; the range is
across those three medians. Each JVM median contains seven nested spatial observations.

| Revision               | Runtime mode   | JVM medians (seconds / 441 chunks) | Aggregate |       JVM range | Chunks/second |
| ---------------------- | -------------- | ---------------------------------- | --------: | --------------: | ------------: |
| parent `22a212b`       | C2ME + DFC on  | 9.5144, 10.1051, 9.9893            |    9.9893 |  9.5144-10.1051 |       44.1472 |
| fix `9412025`          | C2ME + DFC on  | 2.8107, 2.8626, 2.8955             |    2.8626 |   2.8107-2.8955 |      154.0536 |
| experimental `8591d2b` | C2ME + DFC on  | 2.7975, 2.7346, 2.8150             |    2.7975 |   2.7346-2.8150 |      157.6388 |
| parent `22a212b`       | C2ME + DFC off | 3.3105, 3.1939, 3.4098             |    3.3105 |   3.1939-3.4098 |      133.2121 |
| fix `9412025`          | C2ME + DFC off | 3.1481, 3.0980, 3.0991             |    3.0991 |   3.0980-3.1481 |      142.2998 |
| experimental `8591d2b` | C2ME + DFC off | 3.2661, 3.1309, 3.1738             |    3.1738 |   3.1309-3.2661 |      138.9517 |
| parent `22a212b`       | C2ME absent    | 12.7085, 14.2757, 13.8262          |   13.8262 | 12.7085-14.2757 |       31.8960 |
| fix `9412025`          | C2ME absent    | 13.4192, 14.0978, 13.2276          |   13.4192 | 13.2276-14.0978 |       32.8635 |
| experimental `8591d2b` | C2ME absent    | 13.6768, 14.0180, 13.5313          |   13.6768 | 13.5313-14.0180 |       32.2445 |

The fix improves DFC-on throughput by 3.4895x over the exact parent and reduces generation time by
71.34%. Its smaller DFC-off and absent-mode changes are 6.39% and 2.94% by time; the absent-mode JVM
ranges overlap substantially. Within the fix, DFC on is 7.63% faster than DFC off. The parent
instead becomes 3.0175x slower with DFC on, matching the independently demonstrated failure to
install request-owned wrappers and caches into the compiled graph.

Experimental differs from the fix by -2.33% time with DFC on, +2.41% with DFC off, and +1.92% with
C2ME absent. These small changes reverse direction by mode and have only three independent JVMs;
they do not establish a general performance difference between the branches. Exact run IDs,
per-window observations, method, calculations, and rejected-run boundary are retained in
`games/minecraft/investigations/reterraforged/analysis/c2me-dfc-matrix-20260907/analysis.md`.

The corrected parent/no-C2ME and experimental/no-C2ME cells each pass three times. This falsifies
the earlier branch-specific attribution: runs `20260907T012004Z-caa696b70e` and
`20260906T233513Z-99905130ee` exercised the accumulated-ticket stress workload. They remain valid
failure artifacts for that old workload but are not evidence that either branch hangs under the
corrected benchmark.

### Biome and underground-banding invariance

A separate position-sensitive comparison covers all three revisions, all three runtime modes, and
both loaders. All 18 accepted packaged-server runs use seed `3216933670` and the same modern-default
FTF preset. Each queries 532,512 exact three-dimensional biome positions over X/Z -32,768 through
32,768 and Y -64 through 60, then hashes the ordered `(x, y, z, biome id)` sequence.

All 18 runs produce digest `4174568743a25b34a69b70aeefbb9e2a10b600d5cc3062d9f786df6f6da7e5b9`,
59,061 cave-biome cells, and identical vertical-band counts: 32,151 lower, 14,466 middle, and 12,444
upper. Their generated chunk palettes also match direct biome-source queries at all 9,216 combined
quart cells, with zero mismatches. The parent DFC-on surface biome differs because its wrong density
changes the surface Y, not because the underlying three-dimensional biome field changed.

The focused lifecycle fix therefore changes neither biome layout nor underground biome banding in
this tested corpus. Experimental's additional behavior also leaves this corpus unchanged, but that
does not establish equivalence for third-party biome providers, custom density functions, every
preset, or every seed. The exact method, run IDs, calculations, interruption boundary, and source
interpretation are retained in
`games/minecraft/investigations/reterraforged/analysis/c2me-dfc-biome-invariance-20260907/analysis.md`.
The merge recommendation remains the focused fix because experimental's additional identity,
sampling, and wrapping changes are unnecessary and lack equivalent cross-mechanism acceptance.

### Actual preview-to-world-surface parity

The `client-world-lifecycle` probe opens the real preset editor, captures the actual
`Preview2D.applyGeneratedFrame` result, creates the same-seed integrated world, and compares the
full 256 x 256 displayed frame with live generator sampling. An owned isolated production-client
path now supplies packaged FTF, the exact catalog C2ME JAR, and the probe on both Fabric and
NeoForge without touching a personal launcher.

All 18 revision/mode/loader cells completed and cleaned up. Every cell applied the identical preview
biome digest `c57d8272...`, preview-height digest `ea1ea6a...`, and uploaded-raster digest
`14cf83b2...`. The 16 correct cells all produced runtime surface-biome digest `600bd1af...` and
runtime height digest `4b544562...`; the two parent DFC-on controls instead produced `0897e92e...`
and `f8a2bdfe...` on both loaders. The unchanged preview combined with different ordered runtime
digests directly detects the reported DFC-on failure and proves the focused fix restores the
reference layout.

The originally proposed zero-mismatch gate was falsified as a premise. Correct cells have 3,356 of
65,536 preview biome differences and 60,768 of 65,536 preview-height differences because the FTF
preview is approximate. The scalar biome-difference count also happens to be 3,356 in the broken
parent; only the ordered runtime digest exposes that those are different positions and identities.
Central 7 x 7 finished-world controls agree at 49/49 positions, while earlier sparse 337-point
Fabric controls expose ordinary preview, quart-storage, and fuzzy-biome-zoom edge differences. Each
broad control generated 8,289 FTF chunks and left 154,953 Minecraft chunk holders waiting to unload,
so the compact matrix is the sound lifecycle and storage check rather than a claim of viewport-wide
exactness.

Exact per-cell run IDs, hashes, mismatch counts, rejected setup attempts, and limitations are
retained in
`games/minecraft/investigations/reterraforged/analysis/c2me-dfc-preview-parity-20260907/analysis.md`.
The full investigation-tool suite passes 135 tests in 52.52 seconds after host recovery.

This corpus captures the first accepted 2D frame and advances immediately to world creation. Its
recorded zoom is 50. It does not exercise a human moving the zoom control to 80 or 90 and waiting
for one or more asynchronous regenerations. Manual screenshots supplied after the matrix show
apparent DFC-on/off differences in that untested UI state, but do not retain the world seed,
exported preset, center, exact artifact hashes, C2ME startup decision, frame ordinal, or a
stable-frame marker. Treat the report as a new falsification case: pin those inputs, capture every
applied-frame ordinal through quiescence, and compare repeated fresh-client runs before assigning
the difference to DFC, stale static texture, asynchronous regeneration, or changed inputs.

## Acceptance gates

- [x] The exact current C2ME releases and FTF base are pinned and reproducible.
- [x] The constructor's public vanilla mapping lifecycle executes exactly once for every applicable
      owner; FTF setup neither replaces nor replays it.
- [x] Every required density wrapper is initialized before consumption, and every FTF custom density
      leaf has one defined mapped or delegated execution path.
- [x] Absent, false, true, and default configurations have bounded, typed outcomes with no crash,
      blocky interpolation, missing biome/density output, or silent vanilla-looking fallback.
- [x] DFC true/default and false produce equivalent density-derived terrain for identical inputs.
- [x] The actual applied preview frame is characterized against live runtime and finished-world
      sampling for all revisions and modes on both loaders. It is approximate in every correct mode;
      ordered runtime digests independently detect the broken parent DFC-on divergence and prove the
      focused fix restores the correct cross-mode result.
- [ ] Post-interaction preview regeneration at the reported zoom 80/90 is repeatable across fresh
      clients with seed, preset, center, artifacts, C2ME startup decision, and every applied-frame
      ordinal retained. The existing first-frame zoom-50 corpus does not close this gate.
- [x] Common behavior passes on Fabric and NeoForge with current exact-version artifacts.
- [x] Parallel generation, reload/reconstruction, and independent owners do not share mutable
      sampler, cache, compiler, or tile state.
- [x] No C2ME class name, mod ID, private field, configuration parser, or version string selects the
      production density behavior.
- [x] Production JARs contain no probe code, obsolete compiler shield, development sentinel, or
      bundled optional dependency and stop without an owned process, cgroup member, listener, active
      state, or display runtime.
