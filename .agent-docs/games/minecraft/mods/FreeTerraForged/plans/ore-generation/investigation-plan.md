<!-- markdownlint-disable MD013 MD038 MD046 -->

# Ore Generation Investigation Plan

This plan answers one question: how can FTF extend ordinary ore generation into its actual world
height and terrain without changing authored ore behavior or breaking companion mods?

## Fixed scope

- Minecraft `1.21.1`, FTF baseline `908595b`.
- Newest stable compatible loader/API/mod releases, recorded in `test-matrix.md`.
- Ordinary placed-feature ores first: `minecraft:ore` and `minecraft:scattered_ore`.
- Fabric and NeoForge semantic parity.
- Vanilla, Create, and Immersive Ores as ownership evidence.
- Regions Unexplored and Biomes O' Plenty as composition cases.
- Mekanism and Immersive Engineering as later custom-system investigations.

Noise-router veins, retrogen, arbitrary custom feature codecs, and broad biome-overhaul ownership
are outside the first implementation boundary.

## Questions the evidence must answer

1. What is the final active feature graph after all biome and loader composition?
2. Which active features are truly standard ore contracts?
3. Which height ranges are absolute, bottom-relative, top-relative, uniform, triangular, or mixed?
4. How do target rules, caves, terrain volume, and FTF strata affect realized writes?
5. What vertical mapping preserves the intended distribution in shallow, normal, deep, and tall FTF
   worlds?
6. Should the first policy preserve authored attempts, local vertical density, or a bounded blend?
7. Which custom modifiers can be classified safely, and which must be preserved unchanged with a
   diagnostic?

## Completed evidence

- Reference, shallow, extreme, and standard surveys pass with direct section-write telemetry.
- Two additional seeds and non-ocean mountain/cave controls pass with complete surface samples.
- Fabric and NeoForge final graph census pass and record duplicate, inactive, and same-contract
  candidates.
- Create and Immersive Ores ownership matrix passes with exact current artifacts.
- Regions Unexplored reaches generation on its current stable stack and is recorded as composition
  evidence.
- BOP's stable availability boundary is recorded: no stable 1.21.1 dependency chain exists.

See `test-matrix.md` for current run identifiers and `knowledge-base.md` for measurements and
interpretation.

## Measurement contract

Every placement experiment must record:

- seed and fixture dimensions;
- final biome/feature membership;
- candidate calls and selected heights;
- biome passes and successful feature calls;
- actual block writes, written block states, and Y histogram;
- inspected/skipped chunk completeness;
- loader, API, mod versions, exact artifact hashes, and FTF baseline.

Actual block writes are the primary realized-output metric. Candidate counts must not be used as a
proxy for density.

## Remaining work before implementation

### 1. Finish contract classification

Build the classifier around configured-feature type, target rules, geometry, placement modifiers,
height provider, and custom filters. The classifier must produce one of:

- `SUPPORTED_STANDARD`;
- `STANDARD_WITH_CUSTOM_FILTER`;
- `CUSTOM_DIAGNOSTIC`;
- `PRESERVE_UNKNOWN`;
- `NO_ACTIVE_MEMBERSHIP`.

It must report active biome/step membership and preserve ordering. It must not infer replacement
from registry presence or absence.

### 2. Resolve vertical mapping from realized output

Use the existing controls to compare candidate and realized distributions across actual FTF bounds.
Then select and document the mapping for:

- absolute ranges;
- bottom-relative ranges;
- top-relative ranges;
- triangular ranges;
- mixed or unsupported providers.

No mapping is approved yet.

### 3. Resolve density policy

Compare preserve-authored-attempts, preserve-local-density, and bounded/sublinear policies against
realized writes. Include shallow, reference, deep, tall, mountain, cave, and non-ocean controls. Do
not compensate for missing host material or cave exposure by blindly multiplying attempts.

### 4. Add provenance when replacement claims matter

The final graph currently reports inactive registry entries and same-contract groups but cannot
prove whether a modifier removed or replaced an entry. Add before/after modifier provenance only if
the implementation needs replacement-specific behavior.

### 5. Schedule later custom systems

After the standard classifier and mapping are concrete, run Mekanism and Immersive Engineering as
separate custom-system cases. Keep BOP/RU composition results out of clean ownership claims.

## Investigation gates

- Latest stable stack is explicit and reproducible.
- All current controls have complete telemetry.
- Final feature graph is observed on both loaders.
- Actual block-write measurement works.
- Standard/custom ownership boundary is explicit.
- Vertical mapping and density policy are supported by realized-write comparisons.
- Unsupported features have a preserve-and-report behavior.

The last two gates are open. Do not create an implementation branch until they close.
