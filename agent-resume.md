# Resumption prompt: RTF ocean-depth follow-up investigations

Two follow-up investigation tracks live under `games/minecraft/mods/ReTerraForged` (originally from
branch `feat/configurable-ocean-depth`). The island rewrite remains unimplemented; the biome-climate
track is implemented and validated. Read the relevant doc fully before resuming — this file is an
index, not a substitute.

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/               (island interaction)
.agent-docs/games/minecraft/mods/ReTerraForged/plans/biome-climate-banding/     (biome climate distribution)
```

## Island interaction (archipelago) — rewrite scoped, implementation not started

Full findings are in `island-interaction-investigation.md`. Short version: three distinct mechanisms
contribute to the "near vertical walls aren't ideal" symptom, only one of which is actually caused
by `oceanDepth`:

1. A domain-warp fold in the coastline noise (pre-existing, `oceanDepth`-independent, has a tested
   one-line fix not yet shipped anywhere).
2. The island shelf's width is fixed in alpha-space but the elevation it has to cover scales with
   `oceanDepth` — this one is caused by configurable ocean depth.
3. Islands near continents are faded point by point, which can clip or sharply distort part of an
   island rather than placing or excluding the island as a whole. This is pre-existing and
   `oceanDepth`-independent.

Two isolated-patch attempts for #2 failed for structural reasons (see the doc); the real fix looks
like rebuilding archipelago placement on a cellular/Worley basis (mirroring
`UpliftContinentGenerator`) so each island is a distinct shape and actual block distances to its
shoreline and nearby continents are first-class values. That's a bigger, riskier change (relocates
every existing archipelago island) than anything else this session touched.

The implementation scope is recorded in `archipelago-follow-up-scope.md`: build one durable cellular
rewrite. Do not ship Finding 1's isolated warp-strength experiment; it changes a shoreline path the
rewrite will remove and would create an unnecessary intermediate worldgen change. The rewrite must
explicitly replace pointwise `continentFade` with stable per-island continent clearance; cellular
island distance does not solve Finding 3 by itself.

No implementation branch has been created for the rewrite.

The three `-archipelago` test presets built for this investigation
(`test-presets/*-archipelago.zip`) are kept — whoever picks up the rewrite will need real,
screenshot-able islands to work against.

## Biome climate distribution — root and dynamic-banding fixes real-chunk verified

The root fix is commit `bbd845c` on the QA branch and its message-rewritten equivalent `a5bee8f` on
the clean branch. Dynamic underground banding was introduced as production commit `ad491ab` on
`qa/biome-climate-mapping`, mirrored cleanly as `622c56a` on `fix/biome-climate-mapping`. A
real-chunk pass on 2026-07-28 found and fixed a missing live-path connection:
`NoiseChunk.cachedClimateSampler()` did not receive the banding preset, so finished Fabric chunks
silently retained the unbanded biome list even though standalone scans passed. The production
follow-up is `366caae` on the QA branch and `9a1ccdb` on the clean fix branch. QA-only real-chunk
scanner commit `d2b50c3` supersedes the cold scanners for visual-coordinate searches. Both worktrees
pass the full Fabric + NeoForge build.

Read `dynamic-underground-biome-banding-plan.md` for the algorithm and retained evidence. Short
version: convention-following vanilla/modded cave candidates are redistributed from climate depth
`1.1` through the configured usable depth. Band count scales with world dimensions and `Biome Size`;
weirdness partitions rotate the candidate assigned to each band, retaining reachability in shallow
terrain; and underground horizontal climate frequency now scales as `0.25 * 225 / biomeSize`. Every
original target below depth `1.1` is routed through the untouched list, producing zero
surface/shallow mismatches in the live control scan.

Validation covered the canonical very-deep, Goldilocks, and `worldDepth=16` mountain presets; Biome
Size 50/225/900; Regions Unexplored + Lithostitched on Fabric; and the real TerraBlender 4.1
positional path on NeoForge. RU expanded the discovered set from three candidates/six bands to five
candidates/ten bands.

The one gap left after that pass — TerraBlender was only exercised with its own default region
active, never against a second mod genuinely competing for territory — is now closed.
YungsCaveBiomes (confirmed via `javap` to really call `terrablender.api.Region`, not a synthetic
double) was found locally and run alongside TerraBlender 4.1 and the fix on the very-deep preset:
two real populated regions active simultaneously, no crashes, both mods' cave biomes present in the
redistributed bands with comparable run-length stats. That same pass caught a real bug in the QA
scanner itself — its "original" comparison baseline can't do region selection at all (no x/y/z), so
it silently disagreed with the true per-position winner whenever a second region existed,
misreporting hundreds of false mismatches even at shallow depth where the design guarantees no
change. Fixed in QA-only commit `0664f23` (a region-aware lookup mixin, `qa/biome-climate-mapping`
only, never touches the fix branch); re-verified zero mismatches below climate depth `1.1` with the
same two-region setup active.

### Real-chunk visual verification — closed, and it found a missing live-path fix

The failed cold-query attempt remains documented in `dynamic-underground-biome-banding-plan.md`
because its lesson still matters. The replacement scanner (`d2b50c3`) waits for a forceloaded
16x16-chunk region, runs on the server thread, reads `LevelChunk.getNoiseBiome()` from finished
chunks, compresses all vertical biome runs, and records real air samples. It scanned 4,096 columns
and about 792,000 stored biome cells in 170-190 ms; generating the chunks, not scanning them, is the
expensive step.

The first correct comparison was State 1 (`bbd845c`, root fix only) versus the then-current State 2.
It found zero underground differences in all 4,096 columns. That was a real implementation failure,
not another scanner failure: chunk biome filling uses `NoiseChunk.cachedClimateSampler()`, while
`ad491ab` attached the preset only to `RandomState.sampler()`. Commit `366caae` / `9a1ccdb`
propagates the preset to the cached sampler. After that change, all 4,096 column profiles diverged
as intended; 165 columns contained real air at a divergent biome cell (240 open cells total).

The final paired worlds use seed `3216933670`, the pre-lava-adjustment `very-deep.zip` (SHA-256
`0342079254c535428e1c479769c0595e49207a285c06ba7300e802bf60eaf837`), and finished chunks
`(80,100)..(95,115)`. On 2026-07-28 the canonical pack was changed only by explicitly setting
`lavaLevel=-575`; its current SHA-256 is
`58c875c2b2b93b8b7b997b9a666c4aad93afe94e8f55e66f93b0ad49e9a1b5ca`. The biome-profile results remain
applicable because lava level is not a biome-climate input, but the air/block-context checks below
record the earlier default-`-54` run. The "before" jar is genuinely the upstream 1.21.1 state:
detached `c3e2c98`, which is exactly `upstream/1.21.1`. Every coordinate below was independently
confirmed with RCON to be air and to have the stated biome in both freshly generated worlds:

| Coordinate       | Unfixed `c3e2c98` | Fixed `9a1ccdb` equivalent | Visible fixed-world evidence within 12 blocks                     |
| ---------------- | ----------------- | -------------------------- | ----------------------------------------------------------------- |
| `1454 -50 1650`  | Savanna           | Dripstone Caves            | 5 dripstone blocks and 1 pointed dripstone; none before           |
| `1362 -82 1662`  | Savanna           | Deep Dark                  | biome/F3 difference in an open cave                               |
| `1522 -376 1654` | Deep Dark         | Dripstone Caves            | 5 dripstone blocks and 2 pointed dripstone; none before           |
| `1422 -394 1838` | Deep Dark         | Lush Caves                 | 224 clay, 16 moss, moss carpet, grasses, and azaleas; none before |

The last coordinate is also the clearest stacking demonstration. Before, Deep Dark occupies
`Y=-217..-624` without interruption. After, the same column is Deep Dark `-69..-256`, Dripstone
`-257..-380`, Lush `-381..-504`, and Deep Dark again `-505..-624`. Use spectator mode and
`/tp @s 1422 -394 1838`; create both worlds fresh because already-generated chunks retain their old
biome palettes and features.

Retained authoritative logs are `fabric/run/qa-real-chunk-profile-state{0,2}-final.log` in the
unfixed and QA worktrees. SHA-256 values are
`b57f2e936af5e3f8d1e7584143680892ff197d03c2d245ccc252d5bfbd5d4138` (State 0) and
`724dd3bad3cf7bc1cec1c95bcdb4d4136a553de5c45c3fb2a219880bd352626d` (State 2).

What remains is narrower: repeat this finished-chunk matrix with real TerraBlender/Yungs on
NeoForge, and find a dedicated State 0 vs. State 1 visual example for the root mapping alone. In
this vanilla-only 16x16 region, State 0 and State 1 had identical underground biome boundaries even
though the broader root investigation's RU finished-chunk test already proved its selected targets
survive generation.

### Root fix detail (already done — context for the plan above, not a new task)

Full findings are in `biome-climate-banding-investigation.md`. This is not only a deep-ocean issue:
RTF's cave-biome band begins about 26 blocks deeper than vanilla under ordinary land and mountains
as well. Very deep floors near minimum Y have a second problem because the world can end before the
cave band is reached.

The general vertical delay came from a climate-only `-0.205` adjustment in `PresetNoiseRouterData`;
deleting that constant alone was rejected because RTF's other climate axes do not have vanilla
distributions and made dripstone nearly universal below land. The production fix handles the mapping
as a whole in worktree `games/minecraft/mods/ReTerraForged-biome-climate-qa`, branch
`qa/biome-climate-mapping`. It preserves the RTF surface fields, transitions to underground fields
between climate depths `0.03` and `0.125`, uses the actual registered depth instead of the
climate-only offset, and restores vanilla-distributed temperature, humidity, and ridges underground.
Continentalness retains RTF's land/ocean classification while normalizing an independent field
inside RTF land. Erosion combines captured pre-river RTF terrain erosion with `0.25` vanilla erosion
variation, preserving terrain meaning instead of substituting an unrelated erosion map.

The rejected intermediate mapping used a hard land/ocean `range_choice`. The final implementation
instead blends over RTF's configured `beach..inland` continent-edge interval. Across 3,958 real
coast-crossing pairs, underground continentalness median/q99 deltas are `0.1552/0.4297`, compared
with `0.1553/0.4392` for RTF's surface continentalness. The hard control produced `0.4137/1.1365`;
the discontinuity is removed.

A live-path test caught and corrected a second implementation defect. Capturing terrain erosion only
in `Heightmap.apply()` made standalone scans correct but left cached tile cells at zero because
`TileGenerator` calls `applyTerrain()`, `applyRivers()`, and `applyClimate()` separately. The
capture now occurs at the start of `applyRivers()`, the first shared post-terrain/pre-overwrite
point used by both standalone and tile generation. A corrected Regions Unexplored run verified
`312/312` source-selected targets against finished chunks with zero mismatches.

All five RU cave biomes remain reachable below lower land and mountains and none appears at the
surface. Vanilla cave-biome frequencies remain close to vanilla at surface-relative depths `-16`,
`-32`, and `-64`; Uplift and Multi independently reproduce the result. At `-144`, Uplift Deep Dark
selection is `4.12%` in lower land versus `48.86%` in highlands. The rejected vanilla-only erosion
mapping selected approximately `21%` in both, proving why aggregate distribution was insufficient.

The Java `Datapacks.makePreset()` exporter emitted all 193 files. Its graph differs from the
hand-controlled pack only at eight repeated float-precision leaves derived from preset control
points; a fresh world from the exact exported archive reproduced the distribution counts, surface
hash, and continuous coast results. A dense old-versus-new surface comparison covered 1,050,625
columns, including 31,242 boundary-near samples, with zero biome changes. The full multi-loader
production build passes. The root-fix QA instrumentation had been removed at that point; the later
dynamic-banding scanner is retained separately in commit `78fab7e`.

Strata was isolated with two paired 307-location controls. Making clay carveable or removing strata
changed open same-biome exposure by only two of 7,815 sampled cells. Removing strata did alter the
amount of RU decoration in some open caves, especially Prismachasm, so strata is a small secondary
compatibility/appearance issue rather than the cause of biome banding.

The legacy carver probabilities and distribution toggle are genuinely unwired: repository-wide
searches find no generation consumers, and `LegacyCarverHeight` is registered but never constructed.
That can affect physical cave exposure if fixed later, but carvers cannot alter climate selection
and it is not part of this root fix.

No climate-mapping validation gate remains. Separate follow-ups are broader coverage with another
exact 1.21.1 TerraBlender injector when available, policy for ocean floors with no physical
below-floor headroom, and the unused carver settings. Ancient City generation is already verified
with two real `StructureStart` instances; do not mask minimum-Y headroom with an ocean-biome
workaround.

## Practical notes carried forward

- Use `games/minecraft/tooling/dev-server`, not manual Gradle/RCON — see
  `live-worldgen-investigation-howto.md` for the full workflow.
- A full decompiled/mapped vanilla 1.21.1 source tree exists locally at
  `games/minecraft/reference/sources/1.21.1/official/src/` — read it directly for anything
  vanilla-behavior-related rather than reconstructing from memory.
- Reference presets are committed at
  `.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/test-presets/` — see
  `qa-presets.md` for the current list and checksums. Prefer these canonical copies over
  re-exporting or hand-reconstructing.
- The `qa/biome-climate-distribution` branch remains, but its old worktree was retired. Its
  source-distribution, counterfactual-depth, Regions Unexplored, finished-chunk exposure,
  clay-carver, and no-strata logs were recovered into the active worktree's `fabric/run`. The
  filenames are listed in `biome-climate-banding-investigation.md`.
- `qa/biome-climate-mapping` is checked out at `games/minecraft/mods/ReTerraForged-biome-climate-qa`
  at `d2b50c3`. Production commits are `bbd845c`, `ad491ab`, and live-path follow-up `366caae`;
  retained QA-only commits include `78fab7e` (dynamic scanner) and `0664f23` (region-aware
  original-value lookup, fixing a false positive the scanner reported once a second TerraBlender
  region was genuinely populated), plus `d2b50c3` (finished-chunk profile/visual scanner). The clean
  branch is checked out at `games/minecraft/mods/ReTerraForged-biome-climate-fix` at merge commit
  `9099214`, which retains production tip `9a1ccdb`, contains no scanner, and incorporates
  `upstream/1.21.1` through `9e445dd`. Its rebuilt Fabric artifact is
  `/var/home/scott/Desktop/rtf-biome-banding-fix.jar`, SHA-256
  `973472d59ce92cfc051bd5efc276ea7ac867c0ffabf443f308ed1dde8d5c5131`. The detached root-only
  comparison worktree is `games/minecraft/mods/ReTerraForged-root-fix-only` at `bbd845c`.
  Dynamic-banding logs and checksums are listed in its plan document; older root-fix logs and the
  authoritative `qa-coast-edge-blend-production-exported-v2.zip` remain listed in the root
  investigation.
- The Regions Unexplored source used by that worktree is at
  `games/minecraft/mods/RegionsUnexplored-investigation` on branch `21.1`, commit `f5dfe4ee`.
- Seed `3216933670` is the standard seed for all of this investigation's reproduction cases.
