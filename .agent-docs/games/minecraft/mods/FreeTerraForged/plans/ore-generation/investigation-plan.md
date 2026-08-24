<!-- markdownlint-disable MD013 MD038 MD046 -->

# Dynamic Ore Investigation Plan

The mechanism/design investigation is complete. This file records what evidence is authoritative
and the bounded QA still justified before production handoff. Do not restart completed surveys
without a named evidence gap.

## Fixed scope

- Minecraft `1.21.1`, FTF baseline `908595b`.
- Ordinary final active `Feature.ORE` and `Feature.SCATTERED_ORE` occurrences.
- Contract-based behavior across namespaces on Fabric and NeoForge.
- Dynamic Y distribution and linear local candidate intensity.
- No per-mod compatibility logic.
- Noise-router veins, retrogen, and custom configured features remain separate.

## Complete behavior model

| Dimension | Preserved/derived mechanism | Evidence |
| --- | --- | --- |
| Scope | final dimension, biome, step, and order | final graph census |
| Multiplicity | Count, Rarity, or implicit one plus mapped-intensity scale | census, unit tests, runtime candidate counts |
| X/Z | original InSquare/order; fanout before first spatial sampler | X/Z histograms and deep/max runtime runs |
| Y | uniform/trapezoid PMF, anchors, plateau, mapped cell overlaps | offline mirror, unit tests, runtime histograms |
| Deposit | original ore/scattered algorithm and configured size | per-call deposit histograms |
| Targets | original ordered rule tests and output states | codec census and rejection attribution |
| Exposure | original discard-on-air-exposure | rejection attribution and cave runs |
| Filters | original downstream PlacementFilters | Create runtime call/success evidence |
| Realization | hosts, terrain, caves, fluids, overlap | finished host/output scans |
| Survival | later decoration and final state | surviving/overwritten writes by Y/block |

## Completed evidence packages

### E-001 — Final active contract census: complete

The census records every final occurrence and inactive registry declaration, actual feature/config
type, modifier order/configuration, multiplicity, X/Z, height provider/anchors/plateau, ore targets,
size, exposure, filters, memberships, and reason codes.

The stable control has 30 distinct ordinary-ore contracts across 53 possible biomes: 22 executable
supported contracts and eight final blacklist-only declarations. Fabric and NeoForge agree on the
ordinary mechanism boundary.

### E-002 — Realization/rejection attribution: complete

Instrumentation records configured-feature origins and success, deposit size, rule checks,
target/exposure rejection, accepted replacements, raw/unique writes, and producer identity without
re-evaluating a rule or consuming generation RNG.

### E-003 — Host volume and final survival: complete

Opt-in finished scans report target-rule-eligible hosts plus measured output states, target index,
actual block IDs, air/fluid/solid volume, air adjacency, and surviving/overwritten positions by Y.
This distinguishes candidate success, raw production, and final visibility.

### E-004 — Vertical transform: complete

The Java derivation and independent Python mirror implement discrete half-cell mapping across
bottom/0/8/sea/top. Evidence covers:

- reference identity;
- floor contraction and expansion;
- ceiling contraction and expansion;
- absolute, above-bottom, below-top, and mixed anchors;
- uniform, triangle, and nonzero-plateau trapezoid providers; and
- authored tails outside the reference/live world.

### E-005 — Multiplicity and spatial independence: complete

The initial height-only fanout was rejected because it stacked expanded trials in one X/Z column.
The retained algorithm fans out at Count, Rarity, InSquare, or Height before first spatial sampling.
Unit tests cover all four decisions; runtime runs prove all 16 local X and Z offsets remain active.

Modeled versus observed candidate totals include:

- expanded reference coal/iron families within about `0.6%` over large samples;
- maximum scattered ore `996` observed versus about `994.9` expected;
- Create zinc `1057` observed versus about `1051.7` expected;
- Immersive Ores vibranium `1764` observed versus about `1764.5` expected; and
- short-ceiling coal `1941` observed versus `1942.4`, upper iron `5777` versus `5827.2`.

### E-006 — Realized concentration: complete for policy selection

The 256-chunk reference/shallow comparison uses surviving writes per million reconstructed host
opportunities in mapped support:

- coal: `14432.8` reference, `14389.9` shallow (`-0.3%`);
- small iron: `574.3`, `561.3` (`-2.3%`);
- upper iron: `6019.0`, `4587.5` (`-23.8%`, different high-terrain opportunity); and
- diamond: `181.2`, `96.1` (`-47%`, small exposed deposit plus changed host/cave geometry).

The candidate formula matched expectation. The divergent realized cases demonstrate why a generic
host-feedback or per-ore compensation term would violate the content-agnostic contract.

Maximum-height high-volume ores also retained comparable ratios where hosts existed. Empty upper
bands in the deep-ocean fixture are composition evidence, not transform failure.

### E-007 — Standard/custom mechanism boundaries: complete

- `minecraft:scattered_ore` wrote `1252` surviving raw-gold blocks after generic maximum-depth
  scaling.
- Create zinc used the generic standard-ore/custom-filter path and wrote `11946` surviving zinc ore
  blocks; the filter still rejected some transformed candidates.
- Create striated ore remained one custom configured-feature invocation and was not transformed.
- Immersive Ores vibranium used the generic standard path and wrote `5506` surviving blocks.
- Its custom geode path remained outside the transform.

### E-008 — Loader and lifecycle: complete

Fabric and NeoForge compile and run the common implementation. Post-`/reload` maximum-depth runs
used one plan publication and produced exactly identical diamond/tuff Count totals, configured
calls, X/Z histograms, and Y histograms. Small final tuff differences came from later composition,
not candidate sampling.

### E-009 — Maximum-frame timing: complete for first-slice acceptance

Three pre-transform and three dynamic samples used the exact same maximum `-1024..1023` fixture,
seed, 16-chunk window, Fabric loader, finished-chunk authority, selected feature set, and full
host-volume probe. Median generation was `8.165s` pre-transform and `8.862s` dynamic (`+8.5%`).
Median combined generation/probe time was `20.827s` and `21.726s` (`+4.3%`).

All server runs and cleanups completed. One dynamic command process hit the known host Python
teardown fault after persisting its successful summary and complete cleanup; that sample remains
explicitly qualified. This is a bounded implementation gate, not a general hardware benchmark.

## Completed implementation QA

- Full Fabric and NeoForge `build` completed from the isolated worktree.
- All 25 ore-specific unit tests were forced to re-execute and passed.
- The production artifact inspector reported both remapped JARs clean with no probe findings:
  Fabric `49478087eb7a31b36af8ddaff85f1a6a1946c39db4552f9a7ba507eeb618423e` and
  NeoForge `b9f6c7a196c160161eba208b4b1ba5a5584305ba4e0ef5cfd985b3bf3fc32d48`.
- Both JARs contain the complete dynamic-ore class and Mixin set.
- The current reference-frame prototype exactly matched baseline core telemetry; final release
  inputs must repeat this check if the implementation changes.

## Remaining bounded QA

No additional experiment is currently required to choose the classifier, mapping, density, or
provenance policy. Before release, only these implementation QA tasks remain:

1. independent diff review of all production hooks and reason-code paths;
2. side-by-side player QA using the same seed/preset with a baseline jar and prototype jar; and
3. reference-frame behavior-identity confirmation if the release inputs differ from this prototype.

Maximum-frame generation timing is now measured. Runtime memory remains a normal release
observation, not an unresolved transform-policy decision; the immutable plan is chunk-count
independent and bounded by the accepted feature tables.

Player QA should look for more/fewer ordinary deposits across added/removed depth and height—not
larger deposits, different host stones, exposed-ore rescue, or changed large veins. Use spectator or
an ore-visibility test world if desired, but compare the same seed, coordinates, preset, and loader.

## Stop conditions for new experiments

Add a new experiment only if it can answer one of these concrete failures:

- an accepted contract topology not represented in tests;
- modeled/observed candidate mismatch outside stochastic expectation;
- lost X/Z independence;
- a downstream filter or intrinsic ore rule no longer executing;
- stale/wrong plan activation;
- unsupported custom feature being transformed; or
- unacceptable maximum-height performance.

Do not repeat ownership, RU/BOP composition, multiseed, mountain, cave, or broad block-count surveys
without one of those gaps.
