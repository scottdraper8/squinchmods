# Trail Ruins terrain-deformation placement contract

## Status: 2026-09-05

Root cause, runtime oracle, and accepted placement design for Trail Ruins on FreeTerraForged's
default terrain. Evidence targets Minecraft 1.21.1 at live `upstream/1.21.1` commit `95c9b21`, seed
`3216933670`, and the live-exported default RTF preset in
`fixtures/modern-default-with-rivers-live-export`.

## Conclusion

The large flat shelves around some Trail Ruins are `BURY` terrain adaptation around suspended
jigsaw-piece ground planes. Trail Ruins projects the start piece once to `WORLD_SURFACE_WG`, then
positions every child by connector offsets without resampling terrain. On high-relief RTF terrain, a
child piece can retain that common elevation while extending over a much lower slope or valley.
Vanilla's Beardifier then adds density around that piece's ground plane, creating the visible shelf.

The placement contract is therefore:

> For every rigid Trail Ruins piece, its ground plane must not exceed RTF's filtered terrain height
> at any column where that piece has a nonzero `BURY` contribution.

The active `BURY` footprint is the piece box plus points whose horizontal squared distance from the
box is strictly less than 36. The radius-six boundary itself contributes zero and is excluded.

## Evidence authority

The one-block shell scanner is not a valid failure oracle. Vanilla Trail Ruins intentionally reach
the surface, and all 13 vanilla controls also had sky-visible shell cells. See
`trail-ruins-enclosure-baseline.md` for the retained shell evidence.

The RTF filtered tile is the production surface authority. Normal RTF chunk density construction
acquires `generatorContext.cache.provideAtChunk(...).getChunkReader(...)` in `MixinNoiseChunk` and
reads the resulting `Tile.Chunk` cells. A one-column vanilla `ChunkGenerator#getBaseHeight` query
does not take that path because its noise chunk has `cellCountXZ == 1`; it remains useful as a
structure-free counterfactual, but it can differ from the eroded/smoothed surface used by real RTF
chunks. `PointCellCache` is also unsuitable for this decision because it can retain a raw fallback
cell across later tile availability.

Probe `squinch:rtf-structure-terrain-deformation` version 7 reports both authorities separately:

- `ground_plane_minus_bury_support_rtf_cell_max` is the maximum suspension against the filtered RTF
  tile and is the placement acceptance metric.
- `ground_plane_minus_bury_support_max` is the maximum against vanilla's structure-free base-column
  query and remains a diagnostic counterfactual.
- Affected terrain-deformation outputs through probe-pack version 5 wrote the ground-plane
  difference extrema under reversed `min`/`max` names. Their raw values remain valid when
  interpreted by arithmetic; version 6 corrected the names, and version 7 additionally replaced
  lifecycle-sensitive `PointCellCache` reads with direct filtered-tile reads.

## Baseline

Run `20260905T143803Z-d649cf7dc5` measures the 11 located structures before the fix. Nine of 11 have
a positive maximum ground-plane suspension against the filtered RTF surface. The maxima, in scenario
order, are:

```text
7, 5, 28, 3, 1, -11, -12, 12, 3, 18, 9
```

Thus five exceed four blocks, three exceed eight blocks, and two exceed sixteen blocks. The highest
case is 28 blocks. This is the geometry that permits a local BURY contribution to manufacture the
large shelves seen in-world.

The vanilla control `20260905T142334Z-9d27260f92` has one positive result among 13 structures, with
a maximum of nine blocks; its median is −7 and mean is −6.08. Vanilla can rarely form the same
unsafe geometry, but RTF's greater local relief makes it much more frequent. In the built-in 1.21.1
registry, Trail Ruins is the only jigsaw structure combining `BURY` with heightmap projection.
Strongholds also use `BURY`, but they are not jigsaw/heightmap-projected, so this particular
single-projected-start failure is Trail-Ruins-specific among vanilla structures.

## Placement design

`MixinJigsawStructure` handles the built-in Trail Ruins key only when the `RandomState` exposes a
live RTF `GeneratorContext`. Vanilla terrain and other jigsaw structures retain their existing
paths.

For an RTF Trail Ruins start:

1. Generate the ordinary candidate first, preserving vanilla layout when it is safe.
2. Materialize its real pieces and inspect every rigid piece over the exact active `BURY` support.
3. Read filtered cells through the same tile/chunk-reader path used by normal RTF density
   generation.
4. Accept only when the maximum ground-plane suspension is at most zero.
5. Otherwise retry deterministic offsets within 32 blocks, preserving normal jigsaw projection,
   biome validation, pool aliases, and piece metadata. Stop after 16 attempts and omit the start if
   no safe, biome-valid graph exists.

Eight attempts were insufficient at start `(-6144, 5760)`: run `20260905T151616Z-04f9fa37e9` omitted
it, while isolated run `20260905T152533Z-ac13df252b` found a safe graph at attempt 11 with maximum
suspension −2. This is the evidence for the 16-attempt bound.

## Acceptance evidence

- Fabric full acceptance: `20260905T152827Z-52d9ffcfa9`. All 11 steps and cleanup succeeded; all 11
  structures were retained. Filtered-surface maxima are
  `-4, -7, -5, 0, 0, -11, -12, -3, -2, -8, -3`. Generation steps ranged from 7.70 to 10.97 seconds,
  with median 9.67 seconds.
- Fabric exact-final-source focused acceptance: `20260905T155108Z-39c32ab707`. The worst original
  site is retained with filtered-tile maximum −3; the generation step took 9.15 seconds and cleanup
  completed. Diagnostic run `20260905T151405Z-45c9e56f26` additionally logged the identical −3 at
  placement time and probe time.
- Fabric lifecycle-sensitive control: `20260905T152339Z-4dc1559379`. Direct filtered-tile reads at
  placement and probe time both equal zero at the site that exposed `PointCellCache` staleness.
- Vanilla fall-through: `20260905T153605Z-eb45b7c9e8`. All 13 controls were retained and succeeded.
  Canonical start/piece geometry has SHA-256
  `f8f5aa18c14c53ab3440085e0273916c937b5c7cb8285d99fe5d2d9036b1a8e4`, identical to pre-fix run
  `20260905T142334Z-9d27260f92`.
- NeoForge behavior acceptance: `20260905T154610Z-2952a396bc`. The worst original site and the
  attempt-11 site both succeeded and were retained, with maxima −3 and −2. Cleanup completed and
  post-run status/doctor checks reported inactive with no remaining JVM.
- Production packaging: `./gradlew build` completed all 29 tasks. Artifact inspection reported no
  probe contamination in Fabric JAR SHA-256
  `28430d9a17ef0933ce6f45b7019e1bd3d23f6c4fcedf807c553d5650cfbfe14f` or NeoForge JAR SHA-256
  `e08731b501384e2e6149228e0e157dca27737a70640531e364d5f1fb52f1f93a`.

The structure-free-base deformation mass is secondary because that base query does not include RTF's
filtered tile. It nevertheless falls from 58,074 to 28,860 positive solid blocks across the same 11
windows. The direct filtered-surface invariant above is the acceptance gate.

## Scope

This design does not alter the vertical-start correction for Trial Chambers or Ancient Cities, the
village river retry policy, vanilla terrain, strongholds, or arbitrary datapack structures. Support
for a non-vanilla structure should be based on an explicit placement contract rather than inferred
only from `TerrainAdjustment.BURY`.
