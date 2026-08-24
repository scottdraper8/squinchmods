<!-- markdownlint-disable MD013 MD038 MD046 -->

# Dynamic Ore Decisions

These are the concrete answers for the first dynamic ordinary-ore implementation at Minecraft
`1.21.1`, FTF baseline `908595b`.

## D-001 — Goal: preserve local candidate intensity

Ore must adapt when the usable FTF vertical domain grows or shrinks. The production policy is
linear local candidate-density preservation, not fixed attempts, fixed total output, sublinear
scaling, or a host-dependent feedback controller.

The authored vertical provider is treated as an intensity field. If a reference Y cell has
probability mass `p(y)` and maps to a live interval of width `w(y)`, then it contributes:

```text
mapped intensity(y) = p(y) × w(y)
attempt scale = sum(mapped intensity)
mapped Y probability = mapped intensity / attempt scale
```

The scale may be below one. Integer output uses `floor(scale) + Bernoulli(frac(scale))`, preserving
expectation without a floor-to-zero bias.

Measured finished writes validate this policy but do not drive it. Exact finished concentration
cannot be terrain-agnostic because host topology, caves, exposure, fluids, overlapping producers,
and later decoration remain authored behavior.

## D-002 — First supported classifier boundary

A final active occurrence is eligible only when all of these are true:

- the configured feature object is exactly `Feature.ORE` or `Feature.SCATTERED_ORE`;
- the configuration is `OreConfiguration`;
- the placed feature has exactly one `HeightRangePlacement`;
- its height provider is uniform or trapezoid/triangle;
- both anchors are recognized as absolute, above-bottom, or below-top;
- every other position producer is `CountPlacement`, `RarityFilter`, or `InSquarePlacement`;
- any other modifier is an actual `PlacementFilter`, not merely a type with “filter” in its name;
- every retained filter occurs at or after the selected safe fanout boundary; and
- the registered placed-feature ID has one non-conflicting contract across active memberships.

Standard ores with downstream custom filters are supported without linking their concrete classes.
Create zinc proves this boundary. A filter before the safe fanout is preserved unchanged because
duplicating a passed filter result would not preserve independent candidate semantics.

Unknown position transformers, constant or unknown height providers, multiple height ranges,
unregistered direct placed features, conflicting contracts, malformed frames, and inspection
failures are unchanged and receive precise reason codes.

## D-003 — Custom feature boundary

Configured feature systems other than `ore`/`scattered_ore` are diagnostic-only and unchanged,
even when they write ore blocks. This includes Create striated ores, Immersive Ores geodes,
Lithostitched custom ore features, Mekanism resizable ores, and Immersive Engineering retrogen.

This is a mechanism boundary, not a mod allowlist. Conventional modded ores enter automatically;
custom systems require separate future designs.

## D-004 — Reference and live geological frames

Use inclusive block-cell bands rather than point landmarks. Reference cell edges are:

```text
[-64.5, -0.5]  below deepslate
[-0.5,   8.5]  deepslate transition
[ 8.5,  62.5]  below sea
[62.5, 319.5]  sea and above
```

Live edges are:

```text
[liveMin - 0.5, -0.5, 8.5, liveSea - 0.5, liveMax + 0.5]
```

Map each interval piecewise-affinely. These fixed boundaries follow FTF's actual geology:
`worldDepth` owns the volume below zero, the deepslate transition remains absolute `0..8`, sea
level is explicit, and `worldHeight` owns the upper volume.

Resolve relative anchors in the reference frame first, then map their discrete probability cells.
Absolute, bottom-relative, top-relative, and mixed anchors therefore share one rule.

Authored support outside `-64..319` is extrapolated using the nearest segment slope rather than
clipped before mapping. This preserves authored clipping semantics. For example, upper iron's
absolute `80..384` tail remains partly above a short live ceiling, and diamond's below-bottom tail
remains partly below a deep live floor.

An exact reference frame delegates to vanilla. If the transformed discrete PMF for one feature is
also exactly unchanged, that feature delegates even when another world band changed.

## D-005 — Multiplicity must fan out before first spatial sampling

Applying expansion only at `HeightRangePlacement` produced multiple Y values in one X/Z column and
did not preserve independent horizontal sampling. The safe boundary is selected in this order:

1. the last Count or Rarity modifier before the first InSquare/Height sampler;
2. otherwise InSquare when it precedes Height;
3. otherwise Height.

At Count/Rarity, FTF duplicates upstream positions before `InSquarePlacement`; at InSquare it emits
independent authored X/Z samples; at Height it emits mapped Y samples for chains with no earlier
spatial sampler. The original modifier objects and placement list are never edited.

## D-006 — Preserve the producer's intrinsic behavior

The dynamic path may change only candidate Y and expected candidate multiplicity. It preserves:

- dimension and final biome membership;
- decoration step and list order;
- X/Z sampler and chunk convention;
- `OreConfiguration` target order, output states, size, and geometry;
- discard-on-air-exposure chance;
- downstream filters and biome checks; and
- separate upper/lower, small/large, buried/exposed, and biome-specific producers.

Deposit geometry does not scale. Larger worlds receive more deposits, not larger deposits.

## D-007 — Final graph and provenance

Discovery uses the final Overworld biome generation settings from the live chunk generator. It
records every occurrence's biome, step, order, placed-feature ID, contract, and status. Inactive
registry entries are retained only as diagnostics and never transformed.

Full before/after modifier provenance is not required for the first implementation. The transform
does not need to decide whether another mod added or replaced an occurrence; it operates on the
final contract. Per-occurrence configured calls, raw writes, final survival, overwrite targets, and
Y histograms are enough to distinguish “never produced” from “produced then replaced” for QA.

## D-008 — Lifecycle and coupling

Build one immutable value-only plan when the final Overworld loads. Store it on the server instance
and publish it through one volatile reference. The plan contains strings, numbers, enums, and value
records only—no holders, registries, modifiers, optional-mod objects, or mutable global override.

World ownership is proven by a non-null FTF `GeneratorContext` on the Overworld `RandomState`, not
by the mere presence of FTF's preset registry. Non-FTF Overworlds publish an empty plan.

Minecraft `/reload` reloads reloadable resources, not the world-generation registry epoch used by
existing chunks. Ore therefore does not hook FTF's loader-specific, mapping-sensitive reload
lambdas. Fabric and NeoForge post-reload runs prove the original plan remains valid and produces
identical candidate sampling.

The static lifecycle flag only prevents duplicate common event registration; all world-specific
state is server-owned.

## D-009 — Failure policy

Codec/capability inspection catches `RuntimeException | LinkageError` only around the occurrence
being inspected and records the phase, type, and first message. That occurrence remains unchanged;
other occurrences continue to classify.

Activation requires the current Overworld, exact registered top feature, exact modifier object and
index, matching live frame, and a published transform for that ID. A missing/mismatched plan
delegates unchanged. Normal configured-feature execution and block-placement failures are not
relabelled as compatibility failures.

## D-010 — Realized concentration measurement

The primary QA ratio is per-occurrence surviving writes divided by reconstructed pre-placement host
opportunities in the corresponding mapped-intensity bands. The denominator is:

```text
finished target-rule-eligible hosts + this configured feature's output states
```

Including output states reconstructs hosts already replaced by the measured producer. Reports also
retain candidate origins, biome passes, successful calls, raw/unique writes, overwrites, target and
exposure rejection, block IDs, and air adjacency.

This denominator explains realization; it is not a production correction term.

## D-011 — Separate systems and configuration

Noise-router `largeOreVeins` remains controlled by its existing cave setting and is not enlarged by
this work. `oreCompatibleStoneOnly` currently has no effective alternate branch and is not reused.

The first supported ordinary-ore behavior is automatic in non-reference FTF Overworlds and exact
identity in a reference frame. No per-mod compatibility toggle or version allowlist is part of the
design.

## D-012 — Evidence-backed limitations

Expanded or contracted candidate intensity does not guarantee equal finished ore/host ratios in
unlike terrain. In the 256-chunk reference/shallow comparison, coal remained within `0.3%` and small
iron within `2.3%`, while exposure-sensitive diamond and high-terrain iron diverged because their
available host/cave geometry differed. The candidate formula itself matched modeled expectation.

Maximum-height common ores retained comparable realized concentration, while some high-altitude
ores had no host opportunities in an ocean/deep fixture. These are expected composition outcomes,
not reasons for ore-specific correction.

Linear scaling increases generation work in very tall worlds. That cost is intrinsic to preserving
local density and must remain visible in performance QA; it must not be silently capped or made
sublinear.

## Decision status

The four original gates are answered:

1. classifier boundary: exact standard feature/config plus safe modifier topology;
2. vertical mapping: discrete piecewise geological cell mapping;
3. density policy: linear local pre-biome candidate-intensity preservation; and
4. provenance: final graph plus per-occurrence write/survival attribution, without full modifier
   history.

Remaining work is implementation review and release QA, not another ownership survey or a formula
decision.
