# Archipelago biome/surface follow-up

Status: open; cause not yet classified.

The older archipelago redesign plan is superseded by the upstream implementation. This note records
a current visual regression candidate that still needs lower-layer evidence.

## Observation

On Fabric 1.21.1 using the `Modern Earthlike` preset, the client overlay reports `Flower Forest` at
`(-158455, 86, -157952)`, but the visible island surface is broadly barren sand with only sparse
vegetation. The screenshot is client visual evidence; it does not establish whether the selected
biome, final surface-rule result, or placed-feature execution is responsible.

Seed: `-7172312720116314664`

A second screenshot from the same seed and complete preset reports `Ocean` at
`(-158397, 72, -157793)`, despite the player standing on an extended grassy landmass. This is a
separate landmass/biome classification symptom from the first screenshot and should be reproduced as
its own probe point.

A third screenshot from the same reproduction reports `Ocean` at `(-159291, 83, -157607)` while
showing a grassy landmass with an ocean-associated dungeon/structure and stray spawns. This adds a
structure and mob-spawn symptom: the biome classification is not merely a HUD discrepancy if the
structure's placement or spawn rules consumed the same incorrect ocean classification. The exact
structure type and stored biome must be confirmed from the generated chunk rather than inferred from
the screenshot.

A fourth screenshot reports `Ocean` at `(-159387, 76, -157562)` and shows a shipwreck suspended
above the same type of grassy landmass. This is an additional structure-placement symptom to check
against the finished terrain height and the structure's ocean placement rules.

A fifth screenshot broadens the scope beyond apparent islands: at `(-162041, 100, -162983)` with
seed `3216931499`, the overlay reports `Desert` while the player is above a broad elevated landmass
and water. The scene is consistent with a continental/coastal location rather than establishing an
archipelago island. This is therefore a separate non-island biome-classification control point until
the exact preset, focused mod set, loaded FTF artifact, and finished chunk are confirmed. It means
the compatibility layer must be investigated as a possible contributor to biome/continentalness
mismatches generally, not only to island terrain.

The complete preset snapshot is retained at
[`modern-earthlike-archipelago-reproduction.json`](../inputs/modern-earthlike-archipelago-reproduction.json)
so the reproduction does not depend on a local launcher/profile installation. Its SHA-256 is
`90df3fa9a6ec283f6187fec726d2839a4141e23852a1e51f3cdce34577f83bb4`.

The relevant island settings captured from that complete preset are:

```text
enableArchipelago = true
islandDensity = 0.6002436
islandSize = 500.0
islandHeight = 0.1
islandBaseScale = 0.1
islandVerticalScale = 1.9998939
islandHorizontalScale = 7.001667
mountainChance = 0.6001463
mountainScale = 0.4997785
volcanoChance = 1.0
volcanismScale = 0.85
volcanismHorizontalScale = 1.9995923
mountainHorizontalScale = 3.0
offshoreDepth = 0.1
beachWidth = 0.5
beachCoverage = 1.0
macroDensityPercentage = 1.0
```

The relevant high-coverage control is `beachCoverage = 1.0`; `beachWidth = 0.5` and the low
`islandHeight = 0.1` are also part of this reproduction.

## Environment snapshot

Use the 22-file
[`neoforge-1.21.1-worldgen-mods-20260904.tsv`](../inputs/neoforge-1.21.1-worldgen-mods-20260904.tsv)
snapshot. It retains worldgen/content mods, biome and structure modifiers, FTF compatibility inputs,
their required libraries, and C2ME because generation execution/concurrency can affect evidence.
Client/UI/rendering, map, pregeneration, and memory-only performance mods were removed from this
focused list. Dependencies embedded inside parent JARs are recorded in the focused manifest rather
than invented as separate profile entries. Its SHA-256 is
`2c4e573c3114ac7e2477efd7523b0610a7c13b731f364b98a4dc4c010b9cd930`.

The retained libraries are dependency-driven: GlitchCore and TerraBlender support Biomes O' Plenty;
CorgiLib, Oh The Trees You'll Grow, TerraBlender, and GeckoLib support Oh The Biomes We've Gone;
YUNG's API, TerraBlender, and GeckoLib support YUNG's Cave Biomes; Biolith supports No Man's Land;
Lithostitched supports Regions Unexplored; Platform supports VanillaBackport; and Architectury
supports Terrain Slabs. Improved Village Placement is retained for structure generation, while
`vb-compat` is retained with VanillaBackport's worldgen compatibility data. C2ME is retained as an
execution/concurrency variable even though it is not a content mod. Other full-profile entries such
as Distant Horizons, Sodium/Iris, Xaero maps, Jade, UI helpers, Smooth Steps, Chunky, FerriteCore,
and generic client/rendering or memory/performance utilities are intentionally outside this focused
worldgen list. A complete personal launcher-profile inventory is intentionally neither required nor
retained; the focused, repository-owned manifest is the reproducible input boundary.

The snapshot's active `ftf-neoforge.jar` is 2,023,787 bytes with SHA-256
`df236bb7673b6fdf603bdf86239cbebac18da1cb0731fc5a05b9c4e02328002d`. The updated compat build used
for the recent local build is 2,043,758 bytes with SHA-256
`69143d51edb321c09e743c3acee7090a67d4e0b3d74d2e7db1ab650c7d58b762`. If the later screenshots came
from this NeoForge profile, they must not be treated as evidence against the updated compat build
until the loaded FTF artifact is confirmed or replaced. The focused active set includes Biomes O'
Plenty, Oh The Biomes We've Gone, Regions Unexplored, Nature's Spirit, No Man's Land, TerraBlender,
Biolith, Lithostitched, C2ME, VanillaBackport, Terrain Slabs, Improved Village Placement, and their
required worldgen/runtime libraries. The focused manifest is the authoritative mod list for this
reproduction analysis.

## Triage boundary

Keep these hypotheses separate until finished-chunk evidence is available:

- the upstream `ArchipelagoPopulator` may be producing a sand-dominated island geometry or terrain
  classification at high beach coverage;
- the compatibility runtime may be reporting a biome from its FTF-owned selection plan that does not
  match the biome palette stored in the finished chunk, potentially on both islands and ordinary
  continental terrain; or
- the biome may be correct while surface rules or placed features fail to produce the expected
  Flower Forest vegetation on the generated surface.

## Required follow-up

Reproduce all exact control points, then inspect the finished `LevelChunk` rather than relying on a
cold biome query or the client label. Record the stored biome palette at each reported position,
surface block/material distribution, heightmap, and flower/tree placement result. Compare the island
inputs with a lower `beachCoverage` control, and reproduce the continental control independently
with its exact preset/mod/artifact inputs. Retain the same loader and seed within each comparison.
This will separate archipelago geometry from FTF biome selection and downstream decoration without
assuming the cause from the screenshots.
