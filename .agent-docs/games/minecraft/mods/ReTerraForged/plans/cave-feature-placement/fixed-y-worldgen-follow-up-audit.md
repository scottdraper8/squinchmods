# Fixed-Y Worldgen Follow-up Audit

## Purpose and scope

This document tracks vertical limits that are separate from the canonical
`uniform(bottom, absolute(256))` placed-feature bug addressed by the dynamic cave-placement fix. It
prevents those unrelated limits from being forgotten or being “fixed” by a global rewrite that would
change intentional distributions.

The source audit covers mapped vanilla 1.21.1, ReTerraForged `1.21.1`, and Biomes O' Plenty
21.1.0.14. It is not an assertion that every other biome or worldgen mod has been audited.

Each category needs its own semantic decision:

- **dynamic world-bound bug:** a legacy build limit is being used where the active dimension bound
  was intended;
- **extended-world compatibility question:** the fixed range was reasonable for vanilla, but may
  leave RTF's added terrain volume empty;
- **intentional distribution:** changing it would alter resource balance or feature identity;
- **upstream mod bug:** RTF cannot solve it generically without rewriting another mod's configured
  feature.

## 1. BOP configured-feature checks at Y 255

Priority: **high; confirmed dynamic-world-bound bugs in BOP**

BOP has 29 configured-feature classes containing checks of the form:

```java
if (pos.getY() >= 255 || !canReplace(...)) {
    continue;
}
```

These checks reject writes at Y 255 and above even though a normal 1.21.1 Overworld builds through
Y 319. They should use the active world's maximum build height, with whatever feature-size margin
the algorithm requires.

Affected Glowing Grotto configured features:

- `SmallGlowshroomFeature`
- `MediumGlowshroomFeature`
- `HugeGlowshroomFeature`
- `GiantGlowshroomFeature`

This matters directly to the cave investigation. The RTF placement adapter can deliver their origins
above 256, but these configured features will still reject their own high writes. Other Glowing
Grotto decorators—mud, moss, glowworm silk, and extra glow lichen—do not all share that internal
limit, so a high grotto may become only partially decorated.

Other affected BOP feature families:

- trees: Bayou, Cypress, Empyreal, Palm, Redwood, Taiga, and Umbran;
- mushrooms/toadstools: Small Brown Mushroom, Small Red Mushroom, Small Toadstool, and Huge
  Toadstool;
- large plants and terrain decoration: Big Pumpkin, Huge Clover, Huge Lily Pad, Large Fumarole,
  Monolith, Rooted Stump, Termite Mound, and Wispjelly;
- logs and other features: Fallen Log, Fallen Birch Log, Fallen Fir Log, Fallen Jacaranda Log, Bone
  Spine, and Anomaly.

Recommended action:

1. prepare a focused BOP upstream report/patch replacing literal 255 with dynamic build-height
   checks;
2. test ordinary tall surface biomes as well as Glowing Grotto;
3. do not add 29 BOP-specific mixins to RTF;
4. document partial high-Grotto behavior until the upstream BOP limit is fixed.

## 2. Other placed-feature ranges with fixed absolute anchors

Priority: **review by semantic family; do not transform globally**

### Vanilla cave-adjacent features

- fossils:
  - upper fossil uses `aboveBottom(0)..absolute(-8)`;
  - lower fossil uses `aboveBottom(0)..absolute(-8)` or another fixed negative ceiling depending on
    registration;
- amethyst geodes use `aboveBottom(6)..absolute(30)`;
- water springs use `bottom..absolute(192)`;
- ordinary vines use `absolute(64)..absolute(100)`.

Deep RTF worlds enlarge the interval below the absolute upper bound for bottom-relative uniform
features, diluting fixed attempt counts just as the cave decorator range was diluted. Whether those
features should maintain density, remain concentrated near vanilla elevations, or acquire separate
deep variants requires explicit design.

### BOP placements

- volcano lava springs use `absolute(96)..absolute(192)`;
- extra water springs use `absolute(72)..absolute(192)`.

These may intentionally describe terrain strata rather than the whole build range. They should be
tested in tall volcano terrain before changing their anchors.

### Ores

Vanilla ores use many deliberate fixed distributions:

- extra gold: uniform `32..256`;
- upper iron: triangle `80..384`;
- emerald: triangle `-16..480`;
- lower coal: triangle `0..192`;
- copper: triangle `-16..112`;
- several gold, lapis, redstone, diamond, granite, diorite, and andesite variants use other fixed
  absolute or bottom-relative bands.

These are resource-balance curves, not instances of the shared cave-decoration semantic. The dynamic
cave fix intentionally leaves them unchanged. A future “ores in extended RTF worlds” project should
define desired ore density and rarity curves first, then adapt each distribution family explicitly.

`minecraft:ore_clay` is the exception: it uses the exact shared `uniform(bottom, absolute(256))`
modifier and therefore participates in the current semantic fix. If that is undesirable, use an
explicit opt-out tag rather than identifying it by a hardcoded registry ID.

## 3. Cave carver origin ranges

Priority: **high for very tall/deep terrain; needs live measurement**

Vanilla configured carvers include fixed origin ranges such as:

- cave: `aboveBottom(8)..absolute(180)`;
- extra-underground cave: `aboveBottom(8)..absolute(47)`;
- canyon: `absolute(10)..absolute(67)`;
- Nether cave: `absolute(0)..belowTop(1)`.

BOP's Origin Cave carver uses a biased range of `absolute(0)..absolute(127)`.

These bounds control carver origins, not every block a carver can remove, so carved shapes can
extend beyond them. RTF also uses noise caves, meaning a high cave can exist even when a particular
carver does not originate there. Still, fixed carver origins may change cave-type frequency in
extended terrain and should be measured separately from decoration.

Do not route carvers through the placed-feature adapter. They have different probability, shape, and
vertical-bias semantics.

## 4. Surface-rule thresholds

Priority: **medium; biome-specific visual review**

Vanilla's Overworld surface rules contain an absolute Y 256 condition used by Badlands surface
composition. Above it, the rule selects orange terracotta before the ordinary banded Badlands rules.
This may be intentional peak treatment, but in much taller RTF Badlands it can produce a large
uniform upper region.

Other fixed surface thresholds around sea level—60, 62, 63, 74, and 97—are generally tied to the
Overworld sea level and biome identity. RTF already exports coherent surface/noise data for its
preset. They should only be changed through a sea-level-aware surface-rule design, not height
scaling.

BOP likewise contains fixed surface thresholds around 30–66 for Origin Valley, beaches, and Nether
surfaces. Treat these as biome/sea-level rules unless live evidence shows an extended-world bug.

## 5. Structures and fixed vertical targets

Priority: **low unless a structure-specific bug is reported**

Some structures intentionally use fixed absolute height providers—for example, Nether fossils and
Nether fortress-related placements at negative or Nether-specific elevations. Structures also have
terrain-adjustment and clearance logic distinct from placed features.

The dynamic cave adapter must not transform structure height providers. Each structure needs its own
bounding-box, terrain-adaptation, and spawn-rule audit.

## 6. RTF-local height arithmetic to review

Priority: **medium; source-level correctness audit**

`raccoonman.reterraforged.world.worldgen.feature.DiskFeature` compares an absolute block Y against
`ChunkGenerator.getGenDepth()`:

```java
y + 1 < generator.getGenDepth()
```

Generation depth is a size, not the dimension's absolute maximum Y. In a dimension whose minimum Y
is not zero, the correct upper-bound calculation ordinarily involves `minY + genDepth`. This is not
the cave-decoration cap, but it is suspicious extended-world arithmetic and deserves an isolated
test before modification.

Other inspected RTF feature-template comparisons use template-relative coordinates or zero as a
local origin; those should not be mistaken for world-Y hard caps without tracing their coordinate
space.

## 7. Direct and nested placed-feature invocation

Priority: **compatibility watch**

The production adapter requires the normal registered top-level `PlacedFeature` context used by
biome decoration. A feature invoked directly with no registered top feature cannot safely be
classified as biome decoration. Nested configured or placed features may also have their own height
logic.

If live evidence finds a convention-following biome decorator bypassing registered top-level
placement, add a data-driven semantic extension point. Do not infer that every direct feature call
should multiply with world height.

## Follow-up order

1. Ship and validate the exact canonical placed-feature fix.
2. Report or patch BOP's literal Y 255 configured-feature checks, beginning with Glowing Grotto.
3. Measure carver-type frequency above 256 and below -64.
4. Audit RTF `DiskFeature` against nonzero/negative dimension minima.
5. Review springs, fossils, geodes, and vines in extended worlds.
6. Treat ore scaling, surface thresholds, and structures as separate design projects.
