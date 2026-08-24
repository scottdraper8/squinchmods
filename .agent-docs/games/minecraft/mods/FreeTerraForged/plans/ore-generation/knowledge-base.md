<!-- markdownlint-disable MD013 MD038 MD046 -->

# Dynamic Ore Knowledge Base

## Ordinary ore is a pipeline, not a block count

For one final placed-feature occurrence, generation is:

```text
final biome membership and decoration order
→ Count/Rarity/implicit multiplicity
→ X/Z sampling
→ height-provider Y sampling
→ placement filters and biome check
→ configured ore/scattered-ore geometry
→ ordered target-rule tests
→ discard-on-air-exposure test
→ block writes
→ later decoration/overwrites
→ finished visible blocks
```

Every layer matters:

- Count/Rarity controls expected origin trials.
- InSquare controls horizontal origin distribution; chunks remain 16×16 at every world height.
- Height providers control nonuniform Y probability.
- Biome membership and filters decide which candidate origins survive.
- `OreConfiguration.size` and the `ore`/`scattered_ore` algorithm control deposit geometry.
- Ordered target rules choose hosts and output states (for example stone versus deepslate ore).
- `discard_chance_on_air_exposure` rejects otherwise valid target cells.
- Terrain, caves, fluids, overlap, and later features determine realized/final blocks.

`UNDERGROUND_ORES` is not a classifier; that decoration step also contains disks and custom
features. Namespace and output block are not classifiers either. The reliable first boundary is the
actual configured `Feature.ORE` or `Feature.SCATTERED_ORE` mechanism with `OreConfiguration`.

## Environmental role is not a vanilla cave/mountain flag

The high-mountain deepslate observation is caused by the interaction of two independent vanilla
mechanisms. FTF's `ErodeFeature` can place a shallow tuff surface band on steep terrain. Vanilla
ore configuration commonly contains both a normal stone target and a deepslate/tuff target. At
`OreFeature.doPlace`, target rules are tested in order against the current host block; when the
host is tuff, the normal target fails and the deepslate/tuff target succeeds. The ore feature then
writes the configured deepslate ore output directly. There is no later generic transmutation step.

Minecraft does not retain one universal semantic value such as `isCave`, `isMountain`, or
`environmentRole` for ore placement. Existing signals answer narrower questions:

| Signal | What it describes | Policy value |
| --- | --- | --- |
| Current host plus neighboring blocks | The generated local shape at the write position | Primary generic signal |
| `WORLD_SURFACE_WG` and `OCEAN_FLOOR_WG` | Distance below the local world/ocean surface | Primary cheap depth signal |
| `CarvingMask` | Whether a vanilla carver processed a coordinate | Diagnostic/secondary only |
| `EnvironmentScanPlacement`-style bounded scan | Nearby air/solid topology | Possible generic classifier input |
| Biome and biome tags | Intended ecological environment | Secondary context only |
| NoiseRouter or FTF terrain cells | Generator-specific terrain cause or intent | Not a universal runtime signal |

The distinction between cause and shape matters. `NoiseBasedChunkGenerator.applyCarvers` runs
configured carvers that write air and maintain a `CarvingMask`. `CarvingMaskPlacement` can reuse
that mask, but it only covers carver-produced cavities; noise-density caves and arbitrary modded
terrain need not leave the same provenance. The mask is also set before the carver has necessarily
successfully replaced the host block, so it is not a perfect cavity truth table. `CaveSurface` is
only a floor/ceiling scan direction. Vanilla vegetation placement uses that direction together
with local air/solid scanning; it does not receive a universal cave boolean.

The generic distinction we can test is therefore environmental role rather than named terrain:

- `SURFACE_VENEER`: the candidate is shallow below the local world surface, such as FTF's tuff
  band on a mountain;
- `CAVITY_WALL`: the host is solid but has nearby air/fluid or bounded cavity topology;
- `SOLID_INTERIOR`: no nearby cavity topology is visible; and
- `UNKNOWN`: context is insufficient, so vanilla behavior is preserved.

This separates the important cases better than a global Y threshold. A high mountain surface is
high in absolute Y but shallow relative to its local surface. A cave beneath that mountain can
also be high in absolute Y while being far below the local surface and adjacent to a cavity. A
cave ore deep inside a thick wall may have no local-air signal; without carver provenance or
generator-specific density evaluation, its origin cannot be recovered generically after terrain
has been generated. That uncertainty must remain an explicit `UNKNOWN` result rather than a guess.

The correct decision boundary for any contextual target policy is `OreFeature.doPlace`, not the
height placement layer. `doPlace` has the position, host state, target list, configured output,
and world context while it loops through ordered target rules and writes the selected state. The
lower-level `canPlaceOre` check can observe the host and air exposure, but it does not by itself
provide the complete target-list context needed for safe output substitution. A generic policy
must not assume that the first target is always a normal ore or that a deepslate output has a
corresponding normal sibling. If no explicitly safe alternate target exists, suppressing a
contextually invalid target or preserving vanilla behavior is safer than inventing an output
mapping.

### Environmental-role probe and performance boundary

The next diagnostic should extend the existing ore placement telemetry at the accepted target or
write boundary. For each accepted candidate, record the feature/target index, Y, host and output
states, local surface depth, neighboring air/fluid state, biome, and optional carver-mask state.
Run matched mountain-surface and cave controls with:

1. baseline telemetry;
2. observation-only environmental reads; and
3. only if the observations separate the cases, a contextual gate prototype.

The observation-only path should use heightmap reads, the current block, six-neighbor checks, and
at most a small bounded local scan. It should not evaluate NoiseRouter or FTF terrain cells for
every ore candidate, scan whole columns/regions, or create missing carving masks in production.
Those operations are either generator-specific, potentially expensive, or unavailable for all
cave types. Compare generation wall time, ore-feature CPU time, candidate totals, accepted host
and output breakdowns, and the environmental-role counts across identical seeds, presets, and
chunk windows.

This is a diagnostic design direction, not a change to the accepted dynamic-Y contract. The
dynamic path continues to preserve the configured target order, output states, exposure rules,
and host-dependent realization until evidence supports a separate contextual target policy.

## Vanilla ore distributions are heterogeneous

The final 1.21.1 census contains:

- fixed and random Count providers;
- rarity-based and implicit-one multiplicity;
- uniform, triangle, and trapezoid height distributions;
- absolute, above-bottom, below-top, and mixed anchors;
- ranges intentionally extending outside the vanilla dimension;
- multiple upper/lower and small/large producers for one material;
- biome-specific producers;
- varied size and air-exposure discard; and
- ordered stone/deepslate target-output rules.

Consequently, “multiply every ore count by world-height ratio” is wrong. A provider may occupy only
one geological segment, cross segments with different scale, have a nonuniform PMF, or retain an
authored out-of-world tail.

Examples:

- diamond is a small trapezoid/triangle-like bottom-relative producer with a `0.5` air-exposure
  discard chance;
- small iron has similar size without diamond's exposure rule;
- upper iron and upper coal use high absolute distributions with authored support above the
  reference top;
- copper and emerald have distinct biome/height families; and
- tuff is a standard ore configured to write a host-like block, demonstrating why output block
  names do not define ownership.

## FTF's live vertical frame

Minecraft's reference Overworld dimension is `-64..319` with sea level `63`. FTF independently
varies:

- `worldDepth`: real volume below zero;
- `worldHeight`: upper volume;
- sea level; and
- terrain/host composition within the frame.

The inherited deepslate transition remains absolute `0..8`. The correct discrete geological bands
are therefore:

| Band | Reference inclusive cells | Live inclusive cells |
| --- | --- | --- |
| deep | `-64..-1` | `liveMin..-1` |
| deepslate transition | `0..8` | `0..8` |
| below sea | `9..62` | `9..liveSea-1` |
| sea and above | `63..319` | `liveSea..liveMax` |

Mapping cell boundaries (`min-0.5`, `max+0.5`) avoids off-by-one density errors. Sea level is the
first cell above global fluid fill, so its boundary is `seaLevel-0.5`.

## Dynamic intensity derivation

For each supported height provider:

1. resolve anchors in the reference frame;
2. calculate exact discrete probability mass for every authored integer Y;
3. map the lower and upper boundary of each Y cell through the piecewise geological transform;
4. distribute probability times overlap width into live Y cells;
5. use total mapped weight as expected trial scale; and
6. sample Y from the normalized cumulative table.

The trapezoid PMF is derived from Minecraft's two-uniform-sum construction, including nonzero
plateau. A triangle is a zero-plateau trapezoid.

Out-of-world authored cells are not discarded during derivation. Vanilla itself samples them and
lets world bounds prevent writes. Mapping/extrapolating them preserves that clipping fraction. This
explains two otherwise surprising observations:

- deep/maximum diamond origins can lie below the live floor; and
- short-top upper-iron origins can lie above the live ceiling.

In both cases in-world calls and writes match the mapped authored intensity.

## Why fanout location matters

Height-only expansion generates multiple Y samples for one already-chosen X/Z column. It preserves
vertical counts but not the spatial process. The retained implementation fans out before first
spatial sampling whenever possible:

```text
Count/Rarity fanout → independent InSquare samples → mapped Height samples
```

For implicit-one chains, InSquare itself can fan out. If Height is first, Height fans out because the
authored contract has no earlier X/Z randomization to preserve.

All 16 local X and Z offsets appeared in deep, maximum, scattered, Create, and Immersive Ores runs.

## Candidate intensity versus realized concentration

Candidate expectation is mechanically predictable. Finished ore is conditional.

The 256-chunk reference/shallow same-seed comparison showed modeled/observed candidate ratios near
one for representative high-volume ores. Surviving writes per million reconstructed host
opportunities were:

| Feature | Reference | Shallow | Difference |
| --- | ---: | ---: | ---: |
| upper coal | `14432.8` | `14389.9` | `-0.3%` |
| small iron | `574.3` | `561.3` | `-2.3%` |
| upper iron | `6019.0` | `4587.5` | `-23.8%` |
| diamond | `181.2` | `96.1` | `-47%` |

Coal/small iron show the expected stable local concentration in comparable hosts. Upper iron's high
terrain opportunities and diamond's small, exposure-sensitive deposit interact differently with
the shallow fixture's terrain/caves. Diamond had `1792` configured checks and `845` surviving writes
in the reference window versus `515` and `174` in shallow terrain. The transform's candidate count
was correct; the realization context changed.

This proves both that realized writes are necessary evidence and that a generic production
algorithm must not “fix” each finished ratio with ore-specific feedback.

## Maximum-height and contraction evidence

In the maximum-height 16-chunk control, common/high-volume surviving-write concentration per million
host opportunities remained close to the reference controls where matching hosts existed:

- coal about `14544.7`;
- small iron about `575.3`;
- upper iron about `6345.9`; and
- tuff about `79113.2`.

The deep-ocean fixture has little or no eligible upper terrain for some ores. Zero writes there mean
zero realization opportunities, not zero transformed candidates.

The 256-chunk short-ceiling run used a real `-64..127` dimension. Upper coal produced `1941`
candidates versus `1942.4` modeled and `40936` surviving writes. Upper iron produced `5777` versus
`5827.2` modeled and `34358` surviving writes. Its authored absolute `80..384` range mapped to a
support beginning near `67` and extending through `144`, retaining a small above-ceiling tail.

## Standard modded mechanism evidence

### Create

`create:zinc_ore` is standard `minecraft:ore` with uniform absolute `-63..70`, eight attempts, and a
downstream `create:config_filter`. In a maximum-height NeoForge control:

- expected transformed calls were about `1051.7`; observed were `1057`;
- `1051` calls succeeded after the custom filter;
- all local X/Z offsets remained represented; and
- `11946` zinc writes survived.

Create striated ores remained a custom configured feature: one observed call, no standard transform.

### Immersive Ores

`immersiveores:vibranium_ore_placed` is standard `minecraft:ore`, uniform absolute `-60..0`, seven
attempts. In a maximum-height Fabric control:

- expected transformed calls were about `1764.5`; observed were `1764`;
- origins covered `-960..0` and all local X/Z offsets; and
- `5506` vibranium writes survived.

The mod's custom/conditional geode path remained outside the transform.

### Scattered ore

A repository-owned raw-gold `minecraft:scattered_ore` control wrote successfully in a maximum-height
world:

- expected calls about `994.9`; observed `996`;
- mapped origin Y `-512..0`;
- all local X/Z offsets; and
- `1252` unique surviving raw-gold writes.

This confirms that the generic configured-feature boundary covers both first-slice algorithms.

## Loader and reload evidence

Fabric run `20260820T035254Z-abba0a9687` and NeoForge run
`20260820T035453Z-3e044efc9b` used the same maximum frame, seed, window, `/reload`, and post-reload
probe. Both produced exactly:

| Feature | Authored Count candidates | Configured calls |
| --- | ---: | ---: |
| diamond | `28` | `437` |
| tuff | `8` | `126` |

Their complete configured-origin X, Z, and Y histograms were identical. Diamond raw/unique/final
counts were also identical (`211`/`204`/`108`). A nine-block tuff final-survival difference arose
from later loader composition/overwrites. This is direct evidence that common candidate RNG and plan
activation are loader-identical while realized final state can differ downstream.

Only one dynamic plan inventory was logged before each reload. The reload callbacks were removed
from ore; the immutable worldgen plan remained valid.

## Provenance and telemetry limits

The first implementation does not reconstruct a historical before/after feature graph. It knows
the final active occurrence and what that occurrence did. That is enough for a final-contract
transform.

Per-occurrence survival can identify produced-then-overwritten positions and their final blocks.
It cannot always attribute a shared final output block to another producer after the fact; combined
material summaries therefore remain secondary to producer-scoped generation hooks.

The host scan deterministically samples stochastic RuleTests without consuming generation RNG and
labels that denominator accordingly. It reconstructs opportunities, not a literal replay of every
random rule decision.

## Performance

Linear density means linear work in expanded bands. Maximum-height tuff can write hundreds of
thousands of blocks across 16 chunks. Three matched maximum-frame samples per side used the same
`-1024..1023` fixture, seed, 16-chunk window, loader, finished-chunk authority, feature set, and
full host-volume probe:

| Measurement | Pre-transform median | Dynamic median | Difference |
| --- | ---: | ---: | ---: |
| generation | `8.165s` | `8.862s` | `+8.5%` |
| full post-generation probe | `12.276s` | `12.864s` | `+4.8%` |
| combined step | `20.827s` | `21.726s` | `+4.3%` |

All six server runs passed and recorded complete cleanup. One dynamic invocation suffered the known
host Python teardown fault only after its successful summary and cleanup were durable; its timing is
retained with that qualification. This small controlled window is not a broad hardware benchmark,
but it closes the first-slice maximum-preset timing gate and discloses a measurable cost. Runtime
memory still receives ordinary release observation; the immutable plan itself is bounded to the
supported feature tables and does not grow with generated chunks.

Silently capping or applying square-root scaling would be a different density policy.

## Separate systems

- Noise-router `largeOreVeins` is a density/noise system, not placed-feature ore.
- Retrogen runs outside initial chunk decoration.
- Custom configured features own their own algorithms and may need separate adapters.
- `oreCompatibleStoneOnly` currently has no effective alternative code path.
- RU and BOP are composition cases, not ownership controls; BOP's compatible artifacts are beta.

## Authorities

- Vanilla/FTF source at the pinned 1.21.1 baseline.
- Final contract census and placement telemetry probe packs under
  `games/minecraft/investigations/reterraforged/probes/`.
- Independent formula mirror at
  `games/minecraft/investigations/reterraforged/analysis/dynamic-ore-realization.py`.
- Exact scenarios under `games/minecraft/investigations/reterraforged/analysis/`.
- Run IDs and stable artifact versions in [`test-matrix.md`](test-matrix.md).
- Immutable prototype classes in the isolated ore worktree only.
