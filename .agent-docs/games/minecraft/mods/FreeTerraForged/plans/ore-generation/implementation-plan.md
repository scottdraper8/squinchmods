<!-- markdownlint-disable MD013 MD038 MD046 -->

# Dynamic Ore Implementation Plan

This is the current content-agnostic architecture embodied by the uncommitted isolated-worktree
prototype. It is not authorization to branch, commit, push, or merge.

## Pipeline

```text
final Overworld graph
→ occurrence-local structural inspection
→ immutable contract records
→ reference discrete Y intensity
→ live geological cell map
→ safe pre-spatial fanout plan
→ exact runtime activation
→ original filters and configured ore feature
→ attributed realized-write QA
```

The cave-feature work supplies the architectural pattern: adapt a public mechanism to the live
world. Dynamic ore is not a rescue pass and does not search for ore blocks after generation.

## 1. Discovery and classification

`DynamicOreLifecycle` runs from Architectury's common server/level lifecycle. It supplies the live
server registry access, actual Overworld chunk generator, final possible-biome set, real build
bounds, and generator sea level to `DynamicOrePlanner`.

Activation requires the Overworld `RandomState` to expose a non-null FTF `GeneratorContext`. Merely
having FTF's preset registry installed is not an ownership signal; vanilla/custom non-FTF worlds
publish an empty plan.

The planner asks `OreContractClassifier` for one record per final biome/step/order occurrence and
one inactive diagnostic record per unused registry entry. Classification inspects public base types
and codec values only:

- actual configured `Feature` object and `OreConfiguration`;
- ordered placement modifier types and encoded configurations;
- height provider shape, anchors, and plateau;
- configured target/output/size/exposure data; and
- final membership.

No optional-mod class is referenced, initialized, reflected, or mixed into. Unknown structure is
preserved unchanged.

## 2. Immutable plan

`DynamicOrePlan` separates three axes:

- contract: supported standard, standard with custom filter, custom diagnostic, unknown preserved,
  or inactive;
- inspection: classified, unsupported, or failed; and
- action: dynamic vertical density, exact reference delegation, or unchanged.

The plan stores only immutable value data. A transform is keyed by registered placed-feature ID and
contains:

- contract fingerprint;
- selected fanout stage and exact modifier indices;
- expected output positions per authored upstream position; and
- a cumulative discrete Y-intensity table.

The server mixin owns one `volatile DynamicOrePlan`, initialized empty and atomically replaced at
Overworld load. There is no optional global state and no registry mutation.

## 3. Vertical derivation

`DynamicOreVerticalTransform` resolves authored anchors against reference `-64..319`, calculates the
exact discrete uniform or trapezoid PMF, maps each integer cell interval through the
bottom/0/8/sea/top frame, and distributes overlap into live integer cells.

The output weight sum is the multiplicity scale. The normalized weights are the live Y sampler.
Support outside either world remains outside after nearest-segment extrapolation so authored
clipping behavior is retained.

Safety limits reject malformed landmarks, invalid plateaus, integer overflow, empty support, and
oversized tables. Exact reference or feature-local identity produces no transform and consumes no
new random values.

## 4. Safe fanout

Expansion must occur before the first spatial sampler that would otherwise correlate extra trials.
`DynamicOrePlanner` selects:

```text
last Count/Rarity before first InSquare/Height
else InSquare before Height
else Height
```

Mixin hooks are on Minecraft's public placement base mechanisms:

- `RepeatingPlacement.getPositions` for Count;
- `PlacementFilter.getPositions` for Rarity;
- `InSquarePlacement.getPositions` for implicit pre-height fanout; and
- the existing `HeightRangePlacement.getPositions` hook for Y sampling and height-first chains.

Count/Rarity fanout duplicates the upstream logical position before authored X/Z sampling.
InSquare fanout generates independent X/Z values. Height always replaces the authored Y sample
with the mapped sampler. Contraction returns zero positions probabilistically.

All custom/biome filters accepted by the classifier remain downstream of this boundary. If a filter
would run first, the occurrence is unsupported rather than duplicating one filter result.

## 5. Exact runtime activation

`DynamicOrePlacement` activates only when:

- generation is in the Overworld;
- `PlacementContext.topFeature()` is actual `Feature.ORE` or `Feature.SCATTERED_ORE`;
- the current modifier is the same object at the planned index;
- the top feature has a registered ID;
- the server owns a plan for that ID; and
- the placement context's min/max/sea frame equals the plan frame.

Any miss delegates to the original placement behavior. Standard ores are explicitly excluded from
FTF's unrelated canonical surface-feature height expansion, whether transformed or preserved.

The configured feature call is untouched, so ordered target rules, deposit geometry, output states,
air exposure, and all later filters remain authoritative.

## 6. Lifecycle and reload behavior

The plan belongs to the world-generation registry epoch, not reloadable recipes/functions. Ordinary
`/reload` does not replace the active world's placed-feature registry graph. The ore system
therefore uses public common lifecycle events and does not hook the loader-specific reload lambdas
already used by FTF's template manager.

Runtime reload checks on both Fabric and NeoForge show:

- one plan publication at Overworld load;
- successful resource reload with no second ore publication;
- successful post-reload maximum-depth decoration; and
- identical diamond/tuff candidate counts and complete X/Z/Y histograms across loaders.

A future Minecraft/loader version that introduces a true worldgen-registry epoch replacement must
publish a newly derived value plan from that public epoch lifecycle; it must not retain old holders.

## 7. Failure and observability model

Occurrence inspection catches `RuntimeException | LinkageError` only around the inspected codec or
contract operation. The record includes phase, exception type, first message, action, and reason.
Other occurrences continue normally.

The published summary reports schema and graph fingerprints, occurrence counts by contract/status,
dynamic transform count, and live frame. Debug logging can emit normalized occurrences. Runtime
configured-feature or block-placement exceptions remain real generation failures and are not hidden
as optional compatibility failures.

Investigation probes separately report:

- authored Count calls/candidates;
- configured calls, success, and origin X/Z/Y;
- biome pass/failure;
- target and exposure rejection;
- per-call deposit sizes;
- raw and unique writes;
- surviving/overwritten positions by Y and replacement block; and
- opt-in reconstructed host opportunities by Y.

## 8. Files in the prototype

Common production code:

- `world/worldgen/feature/ore/DynamicOreLifecycle.java`
- `world/worldgen/feature/ore/DynamicOrePlan.java`
- `world/worldgen/feature/ore/DynamicOrePlanner.java`
- `world/worldgen/feature/ore/DynamicOreVerticalTransform.java`
- `world/worldgen/feature/ore/DynamicOrePlacement.java`
- `world/worldgen/feature/ore/OreContractClassifier.java`
- `world/worldgen/feature/ore/OreHeightInspector.java`

Runtime hooks/storage:

- `mixin/MixinRepeatingPlacement.java`
- `mixin/MixinPlacementFilter.java`
- `mixin/MixinInSquarePlacement.java`
- existing `mixin/MixinHeightRangePlacement.java`
- `server/RTFMinecraftServer.java`
- Fabric and NeoForge `MixinMinecraftServer.java` server-owned plan fields
- `reterraforged-common.mixins.json`
- `RTFCommon.java`

Tests cover classifier topology/failures, graph normalization/immutability, fanout selection,
reference identity, expansion/contraction stochastic expectation, and out-of-world clipping tails.

## Acceptance criteria

- Reference frame and feature-local identity delegate without RNG changes.
- Expansion and contraction candidate counts match the discrete intensity model within stochastic
  expectation.
- Extra attempts receive independent authored X/Z samples.
- Uniform, triangle/trapezoid, absolute, bottom-relative, top-relative, mixed, and clipped support
  behave according to the same mapping.
- `ore` and `scattered_ore` produce realized writes through the generic path.
- Create zinc and Immersive Ores vibranium activate without optional linkage; their custom sibling
  systems remain unchanged.
- Custom filters remain ordered and observable; upstream-before-fanout filters are preserved.
- Final membership, order, geometry, targets, outputs, exposure, and deposit size remain authored.
- Fabric and NeoForge compile, start, reload, and produce loader-identical candidate sampling.
- No registry mutation, live-holder cache, per-mod adapter, version allowlist, or private optional
  state is introduced.
- Linear-scaling generation cost is measured and disclosed: the matched 16-chunk maximum-frame
  control measured `8.165s` baseline versus `8.862s` dynamic median generation (`+8.5%`).
- Production artifacts contain no investigation probes.

## Smallest safe next implementation phase

Review the isolated diff as one generic ordinary-ore slice, run full loader builds and artifact
contamination inspection, then perform player-facing side-by-side QA with identical seeds and
presets. Do not add custom-system adapters or a large-vein change to that slice.
