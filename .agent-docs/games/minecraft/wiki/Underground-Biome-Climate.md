# Underground Biome Climate

Minecraft's Overworld assigns a biome to every quart-resolution position. This includes positions
inside air, water, and solid rock. The multi-noise biome source chooses among registrations using
temperature, humidity, continentalness, erosion, depth, weirdness, and offset.

## Biome labels are independent of cave geometry

A physical cave is not automatically filled with a cave biome. Terrain density and carvers decide
where caves exist; the biome source independently decides which biome label owns each position.
Consequently:

- an air-filled cave can retain an ordinary Overworld biome such as plains, forest, or ocean;
- a lush-caves, dripstone-caves, or deep-dark label can occupy solid rock where no cave intersects
  it; and
- the ordinary biome underground is not copied from the surface. It wins a new climate lookup at
  that Y, although the mostly column-like climate fields often make it match or resemble the biome
  above.

Ordinary land-biome targets are registered at depth points `0.0` and `1.0`. They therefore remain
competitors underground instead of yielding all underground positions to the three named cave
biomes.

## Climate fields and nearest-neighbor selection

The biome source consumes climate values produced by terrain and noise systems. It does not inspect
blocks, cave air, cave size, or the surface biome. `MultiNoiseBiomeSource` finds the registration
with the lowest squared distance across all seven climate coordinates.

Registrations are nearest-neighbor targets, not hard inclusion masks. A declared range has zero
distance while the sample lies inside it, but a biome can still win outside that range when its
total distance is smaller than every alternative. This has two important consequences:

- reading a registered span as an absolute generation condition is incorrect; and
- shortening a span does not create a hard boundary or make the biome unreachable beyond it.

Biome reachability is a property of both the registrations and the produced climate field. Widening
a target does not help if the producer never approaches it. Expanding a producer's range without
preserving spatial continuity can replace coherent regions with a fine-grained biome mosaic.

## Vanilla 1.21.1 cave-biome targets

The following are the exact distinguishing targets registered by
`VanillaBiomeParameters.writeCaveBiomes` (named `OverworldBiomeBuilder` in Mojang mappings). “Full”
means the vanilla `[-1.0, 1.0]` range, and all three use offset `0.0`.

| Biome           | Temperature | Humidity       | Continentalness | Erosion            | Depth          | Weirdness |
| --------------- | ----------- | -------------- | --------------- | ------------------ | -------------- | --------- |
| Dripstone caves | Full        | Full           | `0.8` to `1.0`  | Full               | `0.2` to `0.9` | Full      |
| Lush caves      | Full        | `0.7` to `1.0` | Full            | Full               | `0.2` to `0.9` | Full      |
| Deep Dark       | Full        | Full           | Full            | `-1.0` to `-0.375` | point `1.1`    | Full      |

These values describe where each biome has no climate-distance penalty. They are not hard gates. In
direct vanilla samples, each cave biome can win somewhat outside its nominal humidity,
continentalness, erosion, or depth span because the complete seven-dimensional nearest-neighbor
comparison still favors it.

## Depth is terrain-relative, not an absolute Y test

Vanilla climate depth is based on a clamped vertical gradient from `1.5` at Y `-64` to `-1.5` at Y
`320`, combined with the terrain offset spline. Its vertical component changes by approximately
`1/128` per block. A climate-depth displacement of `0.205`, for example, corresponds to about 26
vertical blocks before the terrain contribution is considered.

The terrain term is why a depth target cannot be translated into one universal block Y. The same
depth value can occur at different elevations beneath different landforms.

## How the vanilla cave biomes are gated

### Lush caves

The biome label is favored by high humidity (`0.7` to `1.0`) and cave depth (`0.2` to `0.9`). It has
no special temperature, continentalness, erosion, or weirdness target. Because selection is nearest
neighbor, humidity `0.7` is not an absolute cutoff.

The label itself does not require an existing cave, water, clay, moss, or an azalea tree. Lush
decoration is a later stage and is biome-filtered. Individual features then search for usable cave
geometry: air with a solid ceiling or floor, replaceable blocks, and suitable attachment positions.
The surface azalea is therefore a locator produced by world generation, not a prerequisite checked
before the lush-caves biome can be selected.

### Dripstone caves

The biome label is favored by very high continentalness (`0.8` to `1.0`, the far-inland end of the
field) and cave depth (`0.2` to `0.9`). It has no special temperature, humidity, erosion, or
weirdness target. Continentalness `0.8` is not an absolute cutoff.

Dripstone decoration is also later and biome-filtered. Large dripstone and clusters need an actual
air- or water-filled cavity with usable floor and ceiling surfaces, sufficient column height, and
replaceable stone. Pointed dripstone needs a suitable base above or below it. Lava and other local
block conditions can reject an attempt. A dripstone-caves label in solid rock therefore produces no
visible dripstone until cave geometry exposes a valid placement site.

### Deep Dark

Deep Dark is targeted at the deepest vanilla climate point (`1.1`) and the two lowest erosion bands
combined (`-1.0` to `-0.375`). This biases it toward deep positions beneath low-erosion terrain, but
there is no hard rule saying “below Y N.” The terrain-relative depth field can let the label rise
above Y `0` inside sufficiently tall terrain, and the biome label itself does not require cave air.

Vanilla also has a separate `inDeepDarkParameters` check requiring erosion below approximately
`-0.225` and depth above approximately `0.9`. The aquifer uses that predicate to suppress normal
flooding in Deep-Dark-like terrain. It is not the biome-source selection predicate and should not be
presented as the biome's hard gate.

Sculk veins and Deep Dark sculk patches are later biome-filtered placed features with their own
placement conditions. Ancient Cities use a separate, sparse structure-placement pipeline whose
starting biome must be Deep Dark. Deep Dark is therefore required for a vanilla city start but does
not guarantee a city, and the city's footprint can extend beyond Deep Dark-labelled cells.

## Underground proportions

There is no seed-independent or location-independent ratio of ordinary to cave-biome space. Climate
fields are spatially coherent, and the distinguishing humidity, continentalness, erosion, and depth
values cover very different amounts of a particular region. A ratio also needs a measurement domain:
all underground biome cells and only cells centered on cave air answer different questions.

As a broad calibration, a direct vanilla 1.21.1 biome-source sample used seed `3216933670`, a
129-by-129 horizontal grid from `-32768` to `32768` blocks at 512-block spacing, and all 32 biome
quart layers spanning Y `-64` through `63`. Of 532,512 sampled biome cells:

| Label category            |   Cells |  Share |
| ------------------------- | ------: | -----: |
| Ordinary Overworld biomes | 456,943 | 85.81% |
| Dripstone caves           |  37,989 |  7.13% |
| Lush caves                |  21,911 |  4.11% |
| Deep Dark                 |  15,669 |  2.94% |
| All three cave biomes     |  75,569 | 14.19% |

That sample has about `6.05:1` ordinary-biome cells to cave-biome cells. By vertical band,
cave-biome labels occupied 15.22% at Y `-64..-1`, 18.18% at Y `0..31`, and 8.15% at Y `32..63`.

These figures are a scale estimate, not a vanilla constant. In a contiguous 512-by-512-block window
of the same seed whose climate strongly favored cave biomes, 76.78% of underground biome cells had
cave-biome labels. Among sampled quart-cell centers that were actually air, the share was 82.13%.
The contrast demonstrates why a local cave or one regional test must not be extrapolated to the
whole Overworld. The air-center measurement is also only a quart-resolution proxy, not an exact
block-volume census of every cave.

## Integration paths

Biome selection can pass through:

- direct `BiomeSource` queries;
- cached climate samplers used to fill chunk biome palettes;
- TerraBlender per-region parameter trees; and
- parameter points registered after an early regional-tree capture.

These paths can contain different parameter sets or preset context. TerraBlender selects a
positional region before resolving climate, so its regional tree remains part of deep selection.
Late global registrations affect regional selection only when they are composed into the applicable
trees.

Namespaced surface-rule dispatch has equivalent vanilla-only behavior when the namespace set is
exactly the vanilla namespace. Empty, unknown, multiple, and modded sets represent different
dispatch states.

## Stored biomes and decoration

A cold biome-source query describes direct selection for that sampler. `NoiseChunk`'s cached climate
sampler determines the biome palette written during chunk generation. The stored palette is the
authoritative biome state of a completed chunk.

Correct stored biome palettes do not imply visible decoration. Placed-feature candidate generation,
biome filters, and configured-feature block tests form a later pipeline described in
[Placed-feature vertical distributions](Placed-Feature-Vertical-Distributions.md).
