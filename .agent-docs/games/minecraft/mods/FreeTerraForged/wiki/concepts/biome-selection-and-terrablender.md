# Biome Selection and TerraBlender

## Climate model

Minecraft selects multi-noise biomes from temperature, humidity, continentalness, erosion, depth,
weirdness, and offset. Within a vertical column, depth is the primary Y-varying coordinate; the
others are largely horizontal fields.

FTF produces climate and owns the selection pipeline. The pipeline resolves normalized public
Minecraft climate tables and provider-contract tables, then invokes any retained public executable
leaf through its typed plan. Terrain categories can shape the ranges that FTF produces, but they
must not become substitute biome IDs or replace the continuous climate fields used by the selector.

Climate parameter ranges are nearest-neighbor targets, not hard inclusion filters. A terminal depth
registration can continue winning below its declared point when no closer candidate exists. Merely
shortening a range does not create a lower boundary.

RTF climate mappings have these relationships:

- surface fields remain stable near terrain;
- underground depth is surface-relative and aligned with terrain depth;
- ocean and land continentalness blend across configured coast controls rather than switch at a hard
  seam; and
- terrain-owned erosion and weirdness remain available to biome selection until an explicitly
  classified hydrology feature assigns its own values.

Hydrology-specific climate ownership is narrow by design. Rivers, submerged lakes, and wetlands may
assign the values that identify those features, but river proximity or a low river-mask value must
not replace the climate produced for ordinary plains, hills, badlands, or mountains. Generic terrain
needs to retain enough erosion and weirdness variation for the biome registrations that are intended
to compete there.

Altering a density function shared with terrain redistributes both biomes and terrain.

## Underground biome composition

RTF treats underground selection as three separate decisions:

1. **Ownership** decides whether a region may contain a cave-biome label or must use an ordinary
   biome.
2. **Identity** chooses among the cave biomes that are valid for the current depth stage.
3. **Shape** controls the horizontal and vertical size of both cave-biome and ordinary-biome
   regions.

Keeping these decisions separate allows large but uncommon cave-biome regions, small but common
ones, and finite cave regions even when only one cave biome is available.

### Candidate recognition and ordinary background

RTF derives candidates from the active climate registrations rather than biome IDs or namespaces.
The vanilla `0.2..0.9` depth span identifies shallow cave registrations, and the `1.1` depth point
identifies bottom-role registrations. A cave-tagged custom registration with a valid positive-depth
range can participate in the corresponding stage. Malformed and unrecognized conventions remain on
their original path instead of being guessed into cave policy.

The ordinary background is the active registration set with recognized cave entries removed. It is
not a synthetic void biome and is not copied from the surface. Ordinary registered biomes perform a
normal climate lookup at the underground position.

### Ownership, size, and surface protection

Ownership uses deterministic three-dimensional cells. `Cave Biome Coverage` controls the share of
those cells that permit cave selection, while horizontal and vertical size control the dimensions of
the complete underground cell field. The size settings therefore affect ordinary-background regions
as well as cave-biome regions.

The editor limits vertical size to `16..512` blocks or the world's full vertical span when shorter.
Preset data retains a wider compatibility ceiling, and generation clamps the configured value to the
active world's span.

Cave ownership fades in below a terrain-relative protected layer. The surface check covers the whole
quart biome cell plus a four-block lateral border, keeps a four-block hard shell, and then ramps
toward configured coverage over 24 blocks. This protects steep walls and overhang-adjacent cells
rather than comparing only with the surface directly above one X/Z point.

The protection is a local terrain envelope, not a cave-connectivity test. A cave entrance can remain
open elsewhere without allowing a cave-biome label through a nearby mountain wall.

### Identity, climate influence, and banding

With vertical banding enabled, each cave-owned three-dimensional region selects from its depth
stage. Shallow stages contain shallow registrations. Deep stages also admit bottom-role candidates,
so Lush and Dripstone Caves remain possible while Deep Dark participates.

`Cave Climate Influence` controls identity selection only in this banded mode. At zero, candidates
have equal weight. At one, the nearest registered horizontal climate target wins. Intermediate
values smoothly favor better climate matches. Influence is constant with depth. Adjacent regions can
therefore choose the same strict match, making a real region boundary visually invisible.

With vertical banding disabled, cave-owned regions delegate to the original climate registrations
and normal depth behavior. Coverage still controls which three-dimensional regions may retain cave
depth, so vertical size remains observable below 100% coverage. At 100% coverage beyond the surface
transition there are no ownership gaps, and the size field has no visible boundary to express.
Because identity is delegated, the custom climate-influence setting does not participate in this
mode.

### Shared composition boundary

Ownership is applied to the sampled climate target before downstream biome sources consume it. A
background-owned cell receives a surface-depth target while preserving temperature, humidity,
continentalness, erosion, and weirdness. Vanilla selection, TerraBlender regional selection, and
outer wrappers therefore observe the same ownership decision through Minecraft's normal climate
contract.

For the FTF generator, FTF owns positional cells. The TerraBlender capability snapshot supplies
weighted provider tables; one provider is assigned deterministically to each final FTF cell, and
that table remains authoritative for ordinary climate selection inside the cell.

## Runtime integration paths

There is more than one climate-sampler path:

- direct `BiomeSource` queries;
- `RandomState` sampling;
- `NoiseChunk.cachedClimateSampler()`, which fills real chunk biome palettes; and
- provider-contract parameter tables and FTF-owned spatial selection.

Generated chunk palettes use the cached chunk sampler. Direct queries and generated chunks can
therefore differ when only the direct path carries a change.

Preset and terrain context must reach every sampler path that performs this composition. A change
attached only to direct source queries does not establish generated-chunk behavior.

## Preview identity

The preset preview should query the same active biome-selection system that world generation uses,
not render an internal terrain category as a biome substitute.

- Resolve the biome at the generated surface height using the active positional query path.
- Display the exact registry ID so vanilla and modded biomes have the same identity in the preview
  that they have in a generated chunk.
- Keep underground-only candidates out of the surface view without changing runtime selection.
- Treat every supported public selection mechanism as part of the backend request plan, without
  exposing the mechanism to the preview widget.
- Return an immutable biome-ID/color sidecar to the preview. The widget does not inspect provider
  domains, factories, samplers, or selection diagnostics.
- If required selection behavior cannot be made request-owned, fail that preview request and log the
  concrete backend cause. Do not render a vanilla-looking substitute or put technical provider
  diagnostics over a successful image.

## TerraBlender

TerraBlender's public region registry exposes stable IDs, weights, registration order, and climate
tables. FTF snapshots those values into its provider-selection plan. Weighted rendezvous assigns one
provider to each final FTF cell; the selected provider's climate table resolves the biome, and
deferred placeholders query the captured default table.

Each region's public `addBiomes` output is snapshotted independently in registration order. Only
exact duplicate `(parameter point, biome holder)` pairs are removed; distinct values registered at
the same point remain distinct candidates.

Native TerraBlender uniqueness noise does not execute on the FTF path. Provider boundaries are a
subset of FTF cell boundaries and inherit FTF biome size and warp.

## Surface-rule interaction

TerraBlender biome selection and surface rules are separate plan facets. A capability failure in one
does not transfer ownership or failure to the other.

A namespaced surface-rule wrapper has equivalent behavior without dispatch only when its namespace
set is exactly the vanilla namespace. Empty, unknown, multiple, or modded sets retain TerraBlender
dispatch, including when wrappers are nested by Lithostitched.
