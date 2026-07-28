# Dynamic Underground Biome Banding — Design Plan

## Status: 2026-07-27 — implemented, internally self-consistent, NOT verified against real chunks

Read "Visual verification attempt failed" near the end before trusting the word "validated" anywhere
else in this document. Every number below was checked standalone-against-standalone, never against a
real generated chunk — a later session tried to find real screenshot coordinates, found zero real
divergence anywhere it checked (including 70 candidates from a systematic scan), and traced it to a
genuine standalone-vs-real-generation mismatch. The numbers below may still be correct — but that is
now an assumption this document is flagging, not something it has proven.

This is a follow-on to the root climate-mapping fix in `biome-climate-banding-investigation.md`
(committed at `bbd845c` on `qa/biome-climate-mapping` and `fix/biome-climate-mapping`). That fix is
a **hard prerequisite** for everything below, not parallel or competing work — see "Why the root fix
has to come first" below.

The production implementation is commit `ad491ab` on `qa/biome-climate-mapping`, mirrored as
`7a0491b` on clean branch `fix/biome-climate-mapping`. QA scanner commit `78fab7e` and its
region-aware comparison fix `0664f23` (see "Multi-region compatibility — closed" below) exist only
on the QA branch, per the convention in `refs/branch-map.md`. Both branches pass the full Fabric +
NeoForge build.

## Implementation outcome

`UndergroundBiomeBanding` scans each climate list for the deliberately narrow compatibility
signature established below: depth span `0.2..0.9` or point `1.1`, with weirdness left at
`FULL_RANGE`. It groups those entries by biome in encounter order and leaves nonconforming mod
registrations untouched.

The final layout:

- preserves every original `0.2..0.9` point and routes all climate targets below depth `1.1` through
  the original list, giving exact shallow and surface identity;
- spans dynamic bands from climate depth `1.1` to `(worldDepth + min(worldHeight, 256)) / 128`;
- chooses band count from candidate count, usable vertical space, and `Biome Size`, using
  square-root scaling and a cap of 32 so extreme settings remain useful without exploding the
  R-tree;
- partitions weirdness `[-1, 1]` into one strict regime per candidate, then cyclically rotates the
  candidate assigned to each band across regimes, so a shallow column can omit a band without making
  that biome globally unreachable;
- adds full-climate fallback points after the first transition band to prevent one constrained
  candidate from saturating a deep column; and
- changes underground climate frequency from fixed `0.25` to `0.25 * 225 / biomeSize`, which is
  byte-for-byte equivalent at the default `Biome Size=225`.

Fabric without TerraBlender lazily builds a banded list beside the original `MultiNoiseBiomeSource`.
TerraBlender retains every original regional R-tree, builds a parallel banded list for each
non-empty region, preserves TerraBlender's uniqueness-selected region, and uses the parallel list
only at depth `>=1.1`. This matters: falling back to the default region for shallow targets would
have hidden another TerraBlender mod's surface biomes.

## The problem this addresses

The root fix restores vanilla-like underground biome selection at the depths RTF was tested at. But
RTF's `worldDepth`/`worldHeight` are user-configurable (that's the whole point of the
`configurable-ocean-depth` branch this all sits on), and the underlying selection mechanism has a
structural property that only becomes visible at configuration extremes:

Vanilla's biome climate model has **one** axis that varies with Y (`depth`); the other five
(temperature, humidity, continentalness, erosion, weirdness) are pure `(x, z)` fields, constant for
an entire column below the surface transition. Confirmed directly from vanilla source
(`NoiseRouterData.DEPTH`'s registration is `yClampedGradient(...) + a flatCached 2D offset`; the
`OverworldBiomeBuilder` climate axes for temperature/humidity/continentalness/erosion are all
`DensityFunctions.shiftedNoise2d`, cached per column). Once a column's depth value passes every
registered biome's depth window except the deepest one (`deep_dark`, a single point at `1.1` — the
only vanilla biome with nothing deeper registered above it), nothing in the selection changes for
the rest of that column, all the way to bedrock, because every other axis is already frozen.

At vanilla's fixed world depth (64 blocks below sea level) this is invisible — the "everything is
deep_dark below this point" zone is at most ~100 blocks. Under RTF's configurable depth, it isn't
bounded: a very deep preset (RTF's own `very-deep` test preset goes to `worldDepth=624`) would have
that same zone stretch for hundreds of blocks, starting close to the surface, because deep_dark's
registered depth target (`1.1`) is a fixed constant with no relationship to how deep the configured
world actually is. The inverse also holds: a sufficiently shallow world can fail to ever reach
`depth=1.1` before hitting the configured floor, meaning deep_dark becomes unreachable, not just
rare.

## Goals (agreed 2026-07-27)

1. Introduce more than the current 2 depth stages ("banding") when there's room for it — not
   necessarily by authoring new biome content in this pass (see scope note below), but by
   redistributing whatever biomes are already registered (vanilla's, and any installed mod's) across
   more depth slots.
2. Vertical size of each band should scale with **both** `worldDepth`/`worldHeight` and RTF's
   `Biome Size` setting (`ClimateSettings.BiomeShape.biomeSize`), not be a fixed absolute block
   count.
3. Horizontal scale of underground biome selection should also scale with `Biome Size` — currently a
   confirmed bug: the underground climate noise added by the root fix uses a hardcoded vanilla scale
   (`0.25`, see `PresetNoiseRouterData`'s `shiftedNoise2d` calls), completely decoupled from
   `ClimateModule.biomeFreq` (`1.0F / biomeSize`), which only drives RTF's own _surface_ climate
   noise. Cranking Biome Size up today visibly enlarges surface biomes while cave biomes underneath
   keep vanilla's native (much finer) grain.
4. Stay compatible with biome-adding mods (Regions Unexplored, Terralith, anything else using the
   same registration conventions) — their biomes should participate in the new banding, not be left
   behind in the old 2-stage model, and shouldn't be broken by this change.
5. Where the configured world is too shallow to fit every band comfortably, gracefully compress or
   drop bands rather than either crashing the stack together or leaving a biome permanently
   unreachable — and vary _which_ band gets dropped across the map (not always the same one), so
   every biome (vanilla and modded) still shows up somewhere, and terrain-driven headroom
   differences (more room under a mountain than a valley, even within one "shallow" preset) are
   respected rather than papered over.

Explicitly **out of scope for this pass**: authoring genuinely new biome content (new block
palettes, features, mob spawn tables) to give N distinct-_feeling_ bands. This pass only
redistributes biomes that already exist in the world's registered biome catalog — vanilla's three,
plus whatever a mod contributes. New distinct biome layers are a real, larger future option,
deliberately deferred.

## Why the root fix has to come first

The root fix touches the **six climate input values** computed at a position. This plan touches
**which biome wins given those values** — a different, downstream layer. Banding logic can only ever
be as good as the values it's slicing. Concretely: before the root fix, RTF's own continentalness
was saturated near `1.0` across ~91% of land samples — `dripstone_caves`' target window is
continentalness `0.8..1.0`. Slicing the depth axis into more bands on top of that saturation would
just produce more layers of near-universal dripstone, not more variety, because the other axis
feeding the nearest-neighbor distance calculation would still be broken regardless of how the depth
axis is partitioned. Same story for the pre-fix erosion field (flatlined at a near-constant value
after river/climate overwrites) and the pre-fix depth offset (a 26-block miscalibration that would
throw off every band boundary computed against it, not just the one boundary that existed before).
The root fix is the reason the other five axes are trustworthy inputs; this plan assumes that and
builds on top of it.

## How biome placement actually works (verified against real source, not recalled from memory)

There is no separate "cave placement" system. Every biome — surface or underground, vanilla or
modded — is a `(Climate.ParameterPoint, Biome)` pair in a list, built once into a static R-tree
(`Climate.ParameterList`/`Climate.RTree`, see `net.minecraft.world.level.biome.Climate`) at world
load, searched at runtime by nearest-neighbor over 6 quantized values (temperature, humidity,
continentalness, erosion, depth, weirdness) plus a fixed per-entry `offset` tiebreak. Confirmed the
actual registered underground entries in `OverworldBiomeBuilder.addUndergroundBiomes()`:

```text
dripstone_caves: depth span 0.2..0.9, continentalness 0.8..1.0
lush_caves:      depth span 0.2..0.9, humidity 0.7..1.0
deep_dark:       depth POINT 1.1 (registered via a distinct addBottomBiome helper), erosion -1.0..-0.375
```

Everything Regions Unexplored adds registers inside that _same_ `0.2..0.9` window, competing by
humidity/erosion — not new depth territory. So today's real depth-axis richness is exactly 2 stages
regardless of how many biome mods are installed; getting a 3rd/4th/Nth stage today requires either
new content (out of scope, see above) or redistributing the existing 3 across more depth slots.

RTF's `PresetNoiseRouterData` never touches this list — it only supplies the 6 input values into
whatever list vanilla (or a mod) already built. This plan is the first RTF work that would actually
touch the registry/placement layer itself.

### The mechanism that generalizes to mods, and the one that doesn't

Decompiled the real TerraBlender API (`terrablender.api.Region`/`Regions`/`RegionType`,
`terrablender.worldgen.IExtendedParameterList`, `DefaultOverworldRegion`) via `javap` against
`TerraBlender-neoforge-1.21.1-4.1.0.0.jar` rather than assuming behavior from the mixin names RTF
already has. Key finding: **TerraBlender regions are mutually exclusive per-position competitors,
not merged contributions.** `Regions.register(Region)` adds one weighted entrant into a per-position
lottery (`Regions.getCount`/`getIndex`, driven by a "uniqueness" density function — the same one
RTF's existing `mixin/terrablender/MixinClimateSampler.java`/`MixinParameterList.java` already touch
for an unrelated purpose). Exactly one region's _entire_ list wins at a given position.

This rules out the "obvious" implementation: RTF registering its own TerraBlender region containing
the new N-band entries. That would make RTF's banding and a mod's own cave biomes competitors for
map territory — wherever RTF's region wins, players get more bands but only vanilla biomes in them
(since the mod never registered anything into RTF's region); wherever the mod's region wins instead,
players get that mod's biomes exactly as they work today, untouched by this plan. The map would
fragment into patches that never combine both improvements. This is a real, verified failure mode,
not a hypothetical one — found only by reading the actual bytecode, not by reasoning from the API
surface RTF already touches.

The mechanism that does generalize: hook `Climate.ParameterList`'s _construction_ itself — the one
shared chokepoint every path funnels through (vanilla's plain list, `DefaultOverworldRegion`'s
wrapper, any mod's own TerraBlender region, all end up building a `Climate.ParameterList` before
becoming searchable). RTF already has working precedent for mixin-patching exactly this class
(`mixin/terrablender/MixinParameterList.java`). A similar mixin can scan whatever entries are about
to be built into a given list, find every entry whose depth parameter matches the known underground
signature (span `0.2..0.9`, or point `1.1` — the convention TerraBlender's own API steers mods
toward via `Region.addBiomeSimilar`/`RegionUtils.getVanillaParameterPoints`, which clone vanilla's
exact parameter points rather than inventing new ones), and redistribute those specific entries
across N depth bands computed from world settings. This applies uniformly to whichever list/region
ends up being used, without per-mod compatibility code, and without creating a competing territory.

**Caveat to carry forward**: this only recognizes entries following the vanilla depth-axis
convention. A mod that registers underground biomes some other way wouldn't be picked up — a safe
failure mode (that mod just keeps behaving as it does today, doesn't break), but not a guarantee of
universal compatibility with every conceivable mod.

## Sizing the bands: don't touch the shared depth function

`PresetNoiseRouterData` registers RTF's own `NoiseRouterData.DEPTH`:

```java
ctx.register(NoiseRouterData.DEPTH, DensityFunctions.add(
    DensityFunctions.yClampedGradient(-worldDepth, worldHeight, yGradientRange(-worldDepth), yGradientRange(worldHeight)),
    offset
));
private static float yGradientRange(float range) { return 1.0F + (-range / SCALER); }  // SCALER = 128, fixed
```

Despite taking `worldDepth`/`worldHeight` as parameters, the actual rate works out to a constant
`1/128` depth-units per block regardless of configured world size — the parameters only reposition
where the gradient sits, not how fast it moves. That's the precise mechanical reason bands are a
fixed absolute block count today.

Critically, this exact `depth` value is **shared** with real terrain shaping —
`initialDensity = NoiseRouterData.noiseGradientDensity(cache2d(factor), depth)` is literally the
terrain-height formula. Rescaling `SCALER` to fix banding would also reshape actual generated
terrain for every preset, a much bigger and riskier change than intended, requiring the same
validation rigor as a terrain change, not a biome-selection change.

The resolution: don't rescale the shared depth function at all. Choose N band thresholds as explicit
`Climate.Parameter` values at the registry layer (the `ParameterList` hook above), computed at
preset bootstrap time — which already has full access to `worldSettings`/`biomeSize` — positioned
wherever they need to sit within whatever range the existing, unmodified depth function already
produces for that preset. The terminal band's threshold must be included in this same treatment
(positioned near the depth value corresponding to the configured world floor) rather than left as an
implicit leftover — otherwise the disproportionate-stretch problem just resurfaces one level down,
as N-1 well-sized bands plus one huge catch-all at the bottom.

## The two mechanisms that still needed real design (not just "reuse existing patterns")

Two problems were initially waved off as "handled by patterns that already exist" and then found not
to actually be — worth recording precisely since the resolution ended up being the same insight for
both:

**Problem**: how do you smoothly blend a _discrete_ decision (which band/biome effectively isn't
competing in this region) the way the existing coast-to-inland blend smoothly blends a _continuous_
value? And separately: how does a `ParameterList`/R-tree, built once globally at world load with no
per-region view, behave as if some entries are regionally unavailable, without literally rebuilding
the list per region (not how the data structure works)?

**Resolution (same for both)**: nearest-neighbor selection over a _continuous_ axis is already
inherently smooth — that's why ordinary vanilla biome-to-biome boundaries never need explicit lerp
logic; the coast blend only needed one because it was switching between two different
_representations_ of the same axis, a genuine discontinuity, not a "which entry wins" choice. So:
don't try to make the list spatially aware or explicitly blend a discrete choice. Instead, route the
choice through the one climate axis every underground registration leaves unclaimed — **weirdness**,
registered as `FULL_RANGE` by vanilla's dripstone/lush/deep_dark entries (and, per the same
convention, presumably by well-behaved mods). Register several alternate "regimes" (e.g., one
omitting dripstone, one omitting lush), each tagged with a distinct, exhaustive, non-overlapping
weirdness sub-range. This is not a novel mechanism — `OverworldBiomeBuilder` already does exactly
this for surface-biome regional variety (`MIDDLE_BIOMES_VARIANT`, `PLATEAU_BIOMES_VARIANT`,
jagged_peaks-vs-frozen_peaks), gated by a weirdness-derived value, and it's already proven to blend
without seams because that's what nearest-neighbor over a continuous input does everywhere in this
system.

**What must drive the weirdness value**: a continuous, low-frequency signal — explicitly **not**
RTF's existing `cell.biomeRegionId` (a discrete Voronoi/cellular ID; feeding it directly would just
relocate the hard edge to align with cell boundaries instead of removing it). Most likely a
dedicated low-frequency 2D noise, optionally with frequency tied to `biomeSize` so regime-scale
tracks biome-scale, or possibly a reuse of the existing `ridges` output if its native frequency
proves coarse enough on inspection — an empirical question, not an architectural one.

**Mod compatibility of this specific mechanism**: safe by construction, for the same reason as the
list-hook above — narrowing an axis a mod explicitly left at `FULL_RANGE` can't violate an
assumption that mod made, since `FULL_RANGE` is the mod stating it doesn't care what that axis is.

**Performance of this specific mechanism**: negligible. No new per-block density-function cost if an
existing cached signal is reused; at most one cheap new 2D noise sample if not, cacheable per column
the same way every other climate field here already is. The R-tree/list only grows by a few dozen
entries at world-load time — irrelevant against vanilla's own full parameter list, which already has
hundreds.

## Live-path validation results

All runs used seed `3216933670`, the real headless dev server, and 4,225 columns at 128-block
horizontal spacing. The scanner followed each column from its RTF density surface to minimum Y in
16-block steps (137,930 samples for the very-deep preset), recording climate values, selected
biomes, horizontal neighbor agreement, and vertical run lengths.

| Case                         | Candidates / bands | Result                                                                                                                                                                                                                         |
| ---------------------------- | -----------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Very deep, size 225          |              3 / 6 | Deep Dark, Dripstone, and Lush average runs were `115.43`, `117.22`, and `107.49` blocks; maxima were `256`, `192`, and `256`, replacing the rejected prototype's `576`/`752`-block saturation.                                |
| Goldilocks                   |              3 / 3 | Deep Dark remained reachable in 148 terrain-headroom runs (`31.78` average, `96` max) without appearing in ordinary shallow samples.                                                                                           |
| `worldDepth=16` mountain     |              3 / 3 | Deep Dark remained reachable where mountains supplied headroom (42 runs, `28.57` average, `64` max), rather than being globally lost.                                                                                          |
| Very deep, size 50           |             3 / 13 | Candidate run maxima were all `112` blocks; fine Biome Size produced measurably finer vertical and horizontal selection.                                                                                                       |
| Very deep, size 900          |              3 / 3 | Candidate averages rose to `158..257` blocks and 128-block neighbor agreement at surface-minus-64 rose to `0.8897`, versus `0.8156` at size 225 and `0.6982` at size 50.                                                       |
| Very deep + RU/Lithostitched |             5 / 10 | Vanilla plus RU's convention-following Prismachasm/Redstone candidates were discovered generically. Deep Dark, Dripstone, Lush, Bioshroom, Prismachasm, and Redstone maxima were `160`, `128`, `128`, `112`, `144`, and `144`. |
| Very deep + TerraBlender 4.1 |              3 / 6 | The real NeoForge TerraBlender initialization and positional lookup path completed with the same distribution and no band-index fallback errors.                                                                               |

The in-process control lookup compares the selected biome with the untouched original
`ParameterList` at the exact same `Climate.TargetPoint`. The final very-deep run recorded zero
mismatches at every sampled level below climate depth `1.1`: `0/4,225` at the physical surface,
`0/4,184` at surface-minus-64, and `0/3,819` at surface-minus-128. Divergence begins at
surface-minus-144 where measured climate depth first exceeds `1.1`, exactly as designed.

Authoritative retained logs (paths relative to the QA worktree):

| Artifact                                                       | SHA-256                                                            |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| `fabric/run/qa-dynamic-banding-verydeep-v5.log`                | `5ef668027ff324031ce28d7c737d19059488954ff2ecac2d7e8d36fe9237eaf5` |
| `fabric/run/qa-dynamic-banding-goldilocks-v3.log`              | `73833cb86dcc9bccca47693766834b38d21aac49b3af1644b43e75972fdcfe0c` |
| `fabric/run/qa-dynamic-banding-worlddepth16-v3.log`            | `450dc9d58c75989c13a4a3bc59802014115e10121aca3ccfddbd5efb564c2bc1` |
| `fabric/run/qa-dynamic-banding-verydeep-biomesize50-v3.log`    | `c97ba74637c3b44fb5dba3d7b015ae30cc898e8ab6f9d52c5ef1b15866448387` |
| `fabric/run/qa-dynamic-banding-verydeep-biomesize900-v4.log`   | `55beb402a60a26d3b44f0723da04f4755242e0e63673fac6748a9cd51b5a042a` |
| `fabric/run/qa-dynamic-banding-verydeep-ru-v1.log`             | `489a233f903f6007bce06f2d0fbad7fc4427fdf45737cbcfb2fd4bec0f9db423` |
| `neoforge/run/qa-dynamic-banding-verydeep-terrablender-v3.log` | `0aad321bef58358365176d4af78439dc5a409abe62b26d3340cecfbfdf14e912` |

Biome Size test packs are retained at
`fabric/run/qa-dynamic-banding-packs/verydeep-biomesize-{50,900}.zip`, with SHA-256
`7ea1f5f3bb309ee258f7c66816baf3bc8dc89c0fda3117d7628ce6abf60cfaf0` and
`3999babb69e7dc400a4f568bcfe4aee5bc5a523bba60b775b00888479797582f`.

Compatibility-run setup is intentionally not committed to either code branch. RU and Lithostitched
jars remain in `fabric/run/qa-staged-mods/`; their current builds require test-only Gradle overrides
`ORG_GRADLE_PROJECT_fabric_loader_version=0.19.2` and
`ORG_GRADLE_PROJECT_fabric_api_version=0.116.8+1.21.1`. TerraBlender 4.1 was copied from the Gradle
cache into `neoforge/run/mods/` for the run, then removed. The QA and clean worktrees are left with
no compatibility jars staged in their active `mods/` directories.

## Multi-region compatibility — closed

The gap noted in the original validation pass ("TerraBlender was only tested with its own default
region active, not against a second mod that genuinely registers a competing region") is closed.
YungsCaveBiomes
(`com/yungnickyoung/minecraft/yungscavebiomes/world/CaveBiomeRegion extends terrablender.api.Region`,
confirmed via `javap` against the real jar — a genuine, independently shipped mod, not a synthetic
test double) was run alongside TerraBlender 4.1 and the fix, on the `very-deep` preset. Log
confirmed two real, independently populated regions active simultaneously (`minecraft:overworld` at
index 0, `yungscavebiomes:overworld` at index 1). Result: no crashes, no band-index fallback errors,
both mods' underground biomes appeared in the redistributed deep bands together with comparable
vertical run-length statistics across all five candidates from two independent mods (`deep_dark` avg
97.5 blocks, `dripstone_caves` avg 96.9, `lush_caves` avg 89.3, `yungscavebiomes:frosted_caves` avg
79.9, `yungscavebiomes:lost_caves` avg 83.9 — none disproportionate).

That first pass also surfaced a real bug in the QA scanner itself, since fixed
(`common/src/main/java/raccoonman/reterraforged/mixin/qa/MixinParameterListOriginalLookup.java`,
QA-branch-only): the scanner's "original" comparison baseline,
`MultiNoiseBiomeSource.getNoiseBiome(Climate.TargetPoint)`, has no x/y/z and therefore cannot
perform TerraBlender region selection at all, so it silently disagreed with the real per-position
winner whenever more than one populated region existed — hundreds of false "mismatches" per depth
level, even at climate depths far below the `1.1` banding threshold where the design guarantees zero
behavior change. Every prior validation run only ever had one effective region active, so this never
showed up before. Fixed with a region-aware lookup that independently captures each region's
original entry list at the same call site the production mixin observes, and replicates the
production mixin's exact `TBTargetPoint`-preferring uniqueness derivation (a direct external call to
`IExtendedParameterList.getUniqueness(x,y,z)` bypasses that redirect and can point at the wrong
region). Re-verified with the same YungsCaveBiomes + TerraBlender setup: zero mismatches at every
sampled depth from the surface through climate depth `1.0256`, divergence starting exactly at
`1.1271` as designed.

That fix (`0664f23`) initially applied unconditionally and crashed a plain RTF-only server outright
at boot — every test of it so far had TerraBlender loaded (the whole point was testing multi-region
compatibility), so a server with no TerraBlender at all, the ordinary case for most players, was
never actually exercised. It `@Shadow`s members (`maxIndex`, `uniqueTrees`,
`initializeForTerraBlender`) that only exist once TerraBlender's own mixin has applied, and
`@Shadow` has no graceful-skip equivalent to an injector's `require=0`. Fixed in `ea784db` by adding
it to `TBCompat.TERRABLENDER_COMPAT_MIXINS`, the same gating the production `terrablender.*` mixins
already use. Verified both ways afterward: clean boot and scan with TerraBlender + YungsCaveBiomes
both loaded, and clean boot and scan with neither loaded.

## Visual verification attempt — failed; read this before trusting "validated" above

A later session tried to find real screenshot coordinates proving the fix works, to answer a direct
question: "will I actually see a difference between the fixed and unfixed mod at these coordinates."
It did not find one anywhere it checked, and along the way found that this entire document's
validation methodology has a real gap. This section is the detailed account; a shorter version lives
in `agent-resume.md`.

### What was tried, in order, and how each attempt failed

1. **Manual `/locate` + spot-check**, 3 individually-picked coordinates
   (dripstone/lush/`deep_dark`), fixed vs. unfixed worlds, same seed, `very-deep` preset. Result:
   **zero divergence** at any of them — identical biome in both worlds every time, including at the
   exact boundary where `dripstone_caves` starts (bisected to the block; both worlds crossed at the
   same Y). `/locate` finds the **most obvious** example of a biome, which tends to be a column
   where other climate axes (continentalness especially) already decide the outcome regardless of
   the depth fix — RTF's raw continentalness saturates near `1.0` on ordinary land in **both**
   states, so `dripstone_caves` specifically may be a poor choice of biome to test this with. The
   "~26 blocks deeper" finding from the root investigation is a statistical average across thousands
   of columns, not a guaranteed per-column shift.
2. **A systematic regional scanner** (`DivergenceCandidateScanner`, QA-branch-only), classifying
   columns by terrain category and logging biome-per-depth across a `radius=2048, step=64` grid in
   both worlds, diffing the two logs to generate real candidates instead of guessing. This surfaced
   a striking aggregate gap — 32% highland cave-biome presence at depth-144 in the fixed world vs.
   0% in unfixed — and 70 specific candidate coordinates where the two logs disagreed.
3. **Verified those 70 candidates against real generated chunks** (forceload the region, then
   `/execute if biome`, not a cold query). **0 of 70 survived.** Spot-checked what was actually
   there instead at several: identical biomes in both worlds every time (e.g. both `taiga`, both
   `snowy_plains`), matching what the **unfixed** side had predicted, not the fixed side.
4. **Root cause**: `DivergenceCandidateScanner` calls `biomeSource.getNoiseBiome()` as a cold
   standalone query from a bare background thread on the server's first tick — not through real
   chunk generation. This is the same **class** of bug the root-fix investigation already found and
   fixed once, for a different field: `Heightmap.applyRivers()`'s terrain-erosion capture only being
   correct through the real `TileGenerator` chunk-generation path, not a standalone scan (see
   "Erosion" in `biome-climate-banding-investigation.md`). It recurred here, for the fixed-side
   router specifically, in a form nobody re-checked for when dynamic banding was added. The class is
   now marked `KNOWN BROKEN` in its own Javadoc.

**Confirmed, real-chunk-verified ground truth from this entire attempt: 4 positions, all identical
between fixed and unfixed.** Zero real divergences found this session, across two different search
methods.

### The bigger problem: this document's own validation has the same gap

Every aggregate number in "Live-path validation results" above — 3/6 and 5/10 candidate/band counts,
the run-length averages, "0 mismatches below climate depth `1.1`" — was computed by comparing one
standalone `biomeSource.getNoiseBiome()` query against **another** standalone query (the pre-banding
list), never against `LevelChunk.getNoiseBiome()` on an actually-generated chunk. The only things in
this whole investigation ever checked against genuinely real chunks are the root fix's RU 312/312
finished-chunk test and the Ancient City structure check — both from **before** dynamic banding
existed. A standalone query has now been directly shown to diverge from real generation in this
exact codebase. That does not mean the numbers above are wrong — both sides of each standalone
comparison could share the same bias and cancel out in the **relative** comparison — but it does
mean this was never actually checked, and "implemented and validated" overstates what was done. Read
it as "implemented and internally self-consistent."

### Three code states exist; this session only ever compared two of them

- **State 0** — `c3e2c98`, fully unfixed. Built as worktree `ReTerraForged-unfixed-baseline`, kept
  for reuse (fabric jar already built).
- **State 1** — `bbd845c`, root fix only, **no dynamic banding**. This is the exact state the
  original "deep_dark stretches to bedrock" diagnosis in this document's "The problem this
  addresses" section was made against. **No worktree for this state exists yet.**
- **State 2** — `ad491ab` / current `qa/biome-climate-mapping` head, root fix + dynamic banding.

This session only ever compared **State 0 vs. State 2** — every spot-check, every scanner candidate.
That is the wrong pair for demonstrating "`deep_dark` no longer stretches forever," which is
specifically a banding-on-vs-off claim, i.e. **State 1 vs. State 2** — never built, never tested.
State 0 vs. State 2 (or State 0 vs. State 1) is the right pair for the **original** root-fix claim
about cave biomes starting shallower — but that comparison, checked four separate times now via two
different methods, found nothing. That result deserves real follow-up, not a shrug.

### Instructions for whoever picks this up next

1. Never trust a standalone biome-source query as ground truth in this codebase without a real-chunk
   cross-check, and build that check in from the start of any new instrumentation. The pattern is
   already documented in `live-worldgen-investigation-howto.md` and was already used correctly once
   by the RU 312/312 test: forceload the target region, poll until the chunk is actually present,
   then read `LevelChunk.getNoiseBiome()` — not `Climate.Sampler.sample()` cold.
2. Build State 1 as its own worktree (`git worktree add --detach <path> bbd845c`, from inside the
   RTF repo) — it does not exist yet.
3. To test "deep_dark doesn't stretch forever": compare State 1 vs. State 2 (not State 0),
   real-chunk method, at a real highland column past climate depth `1.1` in a very-deep preset. Dig
   straight down for real, tally consecutive `deep_dark` blocks in both states. State 1 should run
   unbounded to bedrock once triggered; State 2 should cap around 80-160 blocks, finally actually
   verifying (not just repeating) the run-length stats claimed above.
4. To test "cave biomes start shallower": compare State 0 vs. State 1 (or State 2), same real-chunk
   method, at **many** real columns, individually verified — not a cold scan. Try humidity-sensitive
   biomes (`lush_caves`, or an RU dry-cave biome) rather than `dripstone_caves` — see point 1 above
   on why dripstone specifically may be a poor test case.
5. To find a "more bands" screenshot: plain RTF only has 3 vanilla candidates, not enough to look
   dramatically banded. Use Regions Unexplored or YungsCaveBiomes (both already staged at
   `fabric/run/qa-staged-mods/` in the QA worktree) for real variety, and verify any candidate
   against a real generated chunk before treating it as a screenshot spot.
6. Don't scan thousands of columns for real-chunk ground truth — forceload is capped at 256 chunks
   per call and generation for the very-deep preset is slow. Use a standalone scan only to produce a
   shortlist, then real-chunk-verify a small sample (10-20) before trusting it. A near-zero hit
   rate, like this session's, is a signal the standalone method is broken — fix that before
   generating more candidates through it.

## Remaining validation, not a blocker to the implementation candidate

- A visual client pass is still the right way to judge whether weirdness-regime boundaries read as
  natural in exposed caves; the headless measurements establish coherence and scale, not aesthetics
  — though per the section above, a real client pass would also be the first genuine real-chunk
  check this feature has ever received.
- The dynamic scanner validates the live source selected by world generation, including RU's
  `InjectorBiomeSource`, but did not repeat the root investigation's 312-point finished-chunk parity
  matrix. Surface identity is exact by direct original-list comparison, and the default-size
  underground noise graph is unchanged, so the prior coast-continuity measurements remain
  mechanically applicable — with the same standalone-vs-real caveat as everything else on this page.
- RU's `inferno` does not use the recognized vanilla depth signature and therefore keeps its
  original behavior (including long vertical runs). This is the intended safe failure described
  above, not a claim of compatibility with arbitrary custom registration schemes.
