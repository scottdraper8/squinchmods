<!-- markdownlint-disable MD013 MD038 MD046 -->

# FreeTerraForged Ore Generation Implementation Plan

This is a design boundary, not authorization to implement. The current evidence supports a
classifier and diagnostics; the vertical mapping and density policy are still open.

## Supported first slice

The first production slice should handle ordinary Overworld placed features whose configured feature
is proven to use the vanilla `minecraft:ore` or `minecraft:scattered_ore` contract. It should
inspect the final active biome graph and adapt only the supported height semantics.

It should not initially reinterpret noise-router veins, retrogen, arbitrary custom codecs, or custom
placement systems.

## Runtime architecture

### 1. Final graph inventory

At the point where final biome generation settings are available, inspect each active placed feature
by biome, decoration step, order, ID, configured-feature type, and placement modifiers. Report:

- active occurrences and duplicates;
- inactive registry entries;
- same-contract candidate groups;
- namespace and loader differences;
- unknown or custom contracts.

The inventory must not claim a replacement without before/after modifier provenance.

### 2. Contract classifier

Classify from the complete configured/placed feature contract:

- configured-feature codec and target rules;
- vein geometry and size;
- count/rarity and horizontal placement;
- height provider and anchor semantics;
- biome/environment filters;
- custom placement modifiers and configuration gates.

Use explicit results: `SUPPORTED_STANDARD`, `STANDARD_WITH_CUSTOM_FILTER`, `CUSTOM_DIAGNOSTIC`,
`PRESERVE_UNKNOWN`, and `NO_ACTIVE_MEMBERSHIP`.

### 3. Height adapter

Adapt only the height provider forms approved by `decisions.md`. Preserve every non-height modifier,
authored count, target rule, feature geometry, filter, order, and deterministic identity. Do not
mutate global registry definitions or bypass custom filters.

The existing canonical FTF hook may be reused only behind this classification boundary; it must not
be treated as a general ore adapter.

### 4. Diagnostics

Emit a report containing the feature ID, biome/step membership, contract classification, height
semantics, target rules, custom modifiers, adaptation decision, and reason for preservation or skip.
Diagnostics must work without changing generation.

## Validation sequence

1. Add classifier tests for standard ores, custom filters, custom features, disks in
   `UNDERGROUND_ORES`, inactive entries, duplicate memberships, and loader-specific graphs.
2. Add height-provider tests for absolute, bottom-relative, top-relative, triangular, and
   unsupported mixed ranges.
3. Compare candidate and realized writes before/after adaptation on reference, shallow, deep, tall,
   mountain, cave, and non-ocean fixtures.
4. Validate vanilla, Create zinc, Create striated ores, and Immersive Ores.
5. Confirm RU and BOP remain composition diagnostics, not ownership gates.
6. Run Mekanism and Immersive Engineering later as separate custom-system investigations.

## Acceptance criteria

- Final active graph is observable on Fabric and NeoForge.
- Duplicate, inactive, and unknown entries are reported without overclaiming replacements.
- Standard ore classification is contract-based.
- Unsupported/custom features are preserved and reported.
- Height transformations have explicit anchor semantics and deterministic behavior.
- Counts, target rules, geometry, filters, exposure, generation step, and order remain intact.
- No density compensation is introduced without an accepted density decision.
- No unexplained feature loss, duplicate execution, target-rule bypass, or loader divergence occurs.
- The ore implementation branch is created only after the open investigation gates close.
