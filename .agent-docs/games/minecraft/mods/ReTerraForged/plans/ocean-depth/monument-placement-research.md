# Ocean Monument Placement Research

## Status

Ocean monument placement is fixed in the RTF branch by anchoring the monument building to the
highest sampled ocean floor across its footprint during structure-start creation, then preserving
that adjusted height across vanilla's reload/regeneration path.

This is a targeted RTF fix for PR #97's configurable `oceanDepth` behavior. It is related to the
known vanilla bug tracked as [MC-249144](https://bugs.mojang.com/browse/MC/issues/MC-249144): ocean
monuments use fixed vertical placement and do not adjust to custom terrain/water levels. The Mojira
issue confirms the broader vanilla problem category; it does not determine RTF's anchor policy.

## Vanilla Behavior

`OceanMonumentStructure.findGenerationPoint()` samples `Heightmap.Types.OCEAN_FLOOR_WG` through
`onTopOfChunkCenter(...)`, but the sampled Y is used only for biome validation. It is not passed to
the monument piece constructor.

`OceanMonumentStructure.createTopPiece()` constructs an
`OceanMonumentPieces.MonumentBuilding(worldgenRandom, i, j, direction)`. The building constructor
hardcodes the bounding box at `Y=39..61`:

```java
super(StructurePieceType.OCEAN_MONUMENT_BUILDING, direction, 0, makeBoundingBox(i, 39, j, direction, 58, 23, 58));
```

That fixed Y is the root behavior. Monuments can be far above the floor in very deep RTF oceans, or
buried into/excavating shallow seafloor when the local floor sits above vanilla's assumed range.

Vanilla already extends monument legs dynamically. `MonumentBuilding.postProcess()` calls
`fillColumnDown()` for the footing columns, and `fillColumnDown()` walks down through replaceable
blocks until it hits solid terrain or the world minimum. The long-leg artifact in deep RTF oceans is
therefore not caused by missing leg logic; the legs are doing exactly what vanilla told them to do
from a fixed building anchor.

## Live Verification

All measured cases used seed `3216933670` and the located monument at `[-256, ~, -256]`, with the
vanilla-fixed building bbox `(-285,39,-285)-(-228,61,-228)` before applying the RTF fix.

The very-deep preset (`oceanDepth=677`, `seaLevel=63`, `worldDepth=624`) proved the mismatch
directly:

```text
generation sample: centerOceanFloorWG=-399
constructed bbox: (-285,39,-285)-(-228,61,-228)
placement centerOceanFloorWG=-624, deltaMinYToFloor=663
```

The later footprint scans compared three measurements over the same 5x5 footprint:

- raw `OCEAN_FLOOR_WG`
- top-down first motion-blocking block scan
- sea-level-down first motion-blocking block scan

For both shallowest and very-deep test presets, the raw heightmap and block scans matched exactly at
all 25 sample points. That proves the low samples in these worlds were real open columns at the
sampled points, not sealed caves hidden underneath an intact seabed.

| Preset                                         | Structure-start 5x5                                       | Placement-time 5x5                                        | Sea-level scan                  |
| ---------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------- | ------------------------------- |
| Shallowest (`oceanDepth=10`, `worldDepth=128`) | `min=52, max=53, mean=52, median=52, center=52`           | `min=-128, max=54, mean=-55, median=-128, center=-128`    | matched placement, `rawDiffs=0` |
| Very deep (`oceanDepth=677`, `worldDepth=624`) | `min=-476, max=-369, mean=-407, median=-401, center=-394` | `min=-624, max=-370, mean=-452, median=-411, center=-393` | matched placement, `rawDiffs=0` |

The exact later generation phase that introduces the low open columns was not proven. The measured
fact is narrower: by placement time those columns are really open, and `OCEAN_FLOOR_WG` is
faithfully reporting them.

## Anchor Policy

RTF uses the highest sampled floor across a 5x5 grid over the monument's 58x58 footprint.

The policy reason is to avoid placing the monument base below any sampled seafloor point. That is
the most conservative choice for preventing terrain from cutting into the building envelope in
shallow or highly variable oceans.

Rejected alternatives:

- `min` and `median` are not viable on the measured targets because they can collapse to
  world-bottom or open-column outliers.
- `mean` can reduce leg length in deep basins, but the shallowest-preset measurements show enough
  open columns that mean anchoring could sink a shallow-water monument into the seafloor.
- A flat offset, as used by several deeper-ocean mods, is still a fixed Y policy. It may improve one
  depth range while remaining wrong for RTF's per-column variable terrain.

Highest-floor anchoring can expose monuments above very shallow custom oceans. That is an explicit
tradeoff of the chosen policy, not an accidental side effect.

## Ocean Floor Variability Follow-Up

The shallowest and very-deep measurements both showed extreme variation inside a single monument
footprint. Some sampled columns were near the expected seafloor while other sampled columns dropped
to the world's minimum build height. The sea-level-down scan proved those low samples were real open
columns at the sampled positions, not sealed caves below an intact seabed.

This doc does not yet prove why that variation exists. Open explanations include preset-specific
terrain geometry, interaction with later vanilla generation phases, or an RTF setting combination
that creates abrupt floor transitions. Do not treat any of those as established until tested.

Needed follow-up if this becomes important:

- Compare the same seed/location across multiple ocean-depth presets, including default/unmodified,
  shallowest, and very-deep.
- Record the relevant preset controls besides `oceanDepth` and `worldDepth`, especially ocean
  control-point spacing and any horizontal scale settings that could make the seafloor change
  quickly across a 58x58 footprint.
- Add a focused height-sample dump over the monument footprint before and after terrain generation,
  then compare it to nearby non-monument ocean floor samples to distinguish general preset behavior
  from monument-local terrain effects.
- Only after those measurements, decide whether the variability is expected preset behavior, a
  tuning issue, or a separate generator bug.

## Implemented RTF Fix

Normal generation is adjusted in `OceanMonumentStructure.generatePieces(...)`, after vanilla adds
the top-level `MonumentBuilding` to the `StructurePiecesBuilder` and before the structure start is
saved or used for structure-based spawn checks.

The mixin:

1. Reads the generated monument piece from `StructurePiecesBuilder`.
2. Samples the highest `OCEAN_FLOOR_WG` value across a 5x5 grid over the piece footprint using
   `GenerationContext.chunkGenerator().getFirstOccupiedHeight(...)`.
3. Moves the parent `MonumentBuilding` and all private child pieces by the same `dy`.
4. Marks the building as already adjusted so the placement-time fallback does not move it again.

The early structure-start hook matters for guardian spawning. Regular guardians use structure spawn
overrides through `ChunkGenerator.getMobsAt(...)`, which consults the structure start/piece bounds.
When the fix lived only in `MonumentBuilding.postProcess()`, blocks moved but the old structure
spawn area could remain at the vanilla Y. Moving the pieces during structure-start creation aligns
the generated blocks and the structure bounds used by spawning.

The `MonumentBuilding.postProcess()` hook remains as a defensive fallback for any monument building
that reaches placement without the structure-start adjustment. In normal RTF generation it should be
a no-op because the building is already marked adjusted.

## Reload Behavior

Vanilla has a special reload path: `OceanMonumentStructure.regeneratePiecesAfterLoad(...)`.

That method reconstructs a `MonumentBuilding` from saved X/Z/orientation and therefore recreates the
hardcoded `Y=39` building unless corrected. The RTF mixin compares the original saved piece height
to the regenerated piece height and applies the same vertical offset to the regenerated parent and
children. This keeps adjusted monuments stable across world reloads; it does not require the player
to regenerate chunks that were already generated before the fix.

## Blast Radius

The production change targets only vanilla ocean monument building pieces:

- `MixinOceanMonumentStructure` targets `OceanMonumentStructure`.
- `MixinOceanMonumentBuilding` targets `OceanMonumentPieces.MonumentBuilding`.
- The accessor exposes only `StructurePiecesBuilder.pieces` so the generated monument piece can be
  moved before the structure start is finalized.

No other vanilla structures use these classes. Ocean ruins and shipwrecks already reposition
themselves from real `OCEAN_FLOOR_WG` data during their own placement paths, so this monument fix is
not generalized to them.

Datapacks or mods that replace vanilla monuments with a different structure implementation are
outside this fix. Mods that also mix into vanilla monument placement could conflict in the usual
mixin-order sense, especially if they apply their own fixed vertical offsets.

## Remaining Uncertainty

The fix has been code-compiled and visually confirmed by Scott in a shallow-ocean test where the
monument followed the floor and protruded above the waterline as expected.

The measured extreme floor variability is documented above, but the exact terrain-generation phase
responsible for the low open columns has not been isolated. That uncertainty does not affect the
chosen RTF fix because highest-floor anchoring deliberately avoids treating the low outlier columns
as the desired building base.
