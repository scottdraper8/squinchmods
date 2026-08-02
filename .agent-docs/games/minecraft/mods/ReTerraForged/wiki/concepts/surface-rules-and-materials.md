# Surface Rules and Materials

## Surface-rule ownership

Preset-derived RTF surface rules affect generated blocks through the actual Overworld noise settings
and TerraBlender surface integration. A codec or GUI field disconnected from generated surface-rule
data has no world-generation effect.

With TerraBlender active, the preset-derived Overworld rule and other initialization features share
one resolved preset context. Modded namespace dispatch remains semantically relevant for every
namespace set except the exactly vanilla-only case.

## Strata concepts

The strata model contains four independent dimensions:

- horizontal strata region/noise scale;
- vertical layer count and depth;
- material selection/weighting; and
- deepslate transition.

Tags provide membership, not weights. Weighted rock selection is represented by explicit weighted
entries or a codec type carrying weight. Layer count controls band thickness; horizontal region size
does not.

Vanilla deepslate rules use a fixed vertical band. Extending `worldDepth` does not automatically
move that band. A depth-derived transition and a preset-owned transition are distinct models with
different old-preset behavior.

## Shore material pipeline

Shore geometry and material painting form separate pipeline stages:

1. terrain/hydrology writes shore state;
2. evaluator resolves shore type, alpha, and material;
3. neighborhood pass resolves continuity; and
4. a raw-generation surface feature paints surface/filler depth.

Shore geometry can cross biome boundaries, so resolved shore state is a more direct painting input
than biome lists. Cache-miss fallback and cached tiles agree when they share the lookup/evaluator
pipeline.

## Material extensibility

Fixed material enums represent a closed block set. A data-driven representation can key materials by
resource location, carry surface and filler states, associate missing optional entries with
fallbacks, and encode weights explicitly.

Biome, climate, and altitude predicates can select above a weighted fallback palette. Per-mod block
choices embedded in the base evaluator couple the evaluator to those mods.

## Registry stability

Terrain and material types in serialized or cached state derive meaning from stable IDs. Appending a
type preserves earlier IDs; insertion changes them unless a migration translates stored values.
