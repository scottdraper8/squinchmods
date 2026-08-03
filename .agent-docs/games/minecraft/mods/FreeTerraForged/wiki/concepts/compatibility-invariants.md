# Compatibility Invariants

## Preset codecs

An explicit codec default allows old presets to load when a setting is absent. A nested setting
participates in behavior only when `copy()` and every preset-construction path carry it. A
compatibility default reproduces old output; a behavior-changing default opts old presets into new
output.

Unknown fields from another fork do not imply behavioral compatibility. Two forks sharing a mod ID
and ancestry can still have incompatible preset schemas and cell models.

## Seed stability

Seed draw order is world layout. A new `Seed.next()` call before an existing draw relocates every
downstream seeded field. Isolated offset seeds leave the baseline construction sequence unchanged.

## Registry IDs and enum ordering

Appending new terrain registrations preserves existing IDs; inserting them can reinterpret stored
values. Separately, enum/category ordinal comparisons may encode dominance. Serialized ID and
logical ordering are independent compatibility dimensions.

## Mutable cell state

A `Cell` field participates consistently only when initialization, copying, reset, writer units,
reader units, and pipeline order agree. Fields copied from another fork without a current writer or
consumer are inert scaffolding that obscures compatibility.

## Loader and Minecraft version boundary

Loader-neutral worldgen logic lives in `common`; Fabric and NeoForge differences sit behind the
registration and biome-modifier abstractions. Minecraft-version API differences and internal RTF
fork divergence are separate porting dimensions, and internal divergence is often the larger one.

## External worldgen wrappers

Registered density and surface functions expose one graph to RTF, datapacks, and integration mods.
Private bypasses create a second graph, which can hide wrapper defects and omit valid external
modifications.

Fast-path equivalence depends on exact preconditions such as region count, namespace set, and
registry ownership. Absence of observed modded content does not establish those preconditions.

A terrain cutoff can originate outside RTF's terrain model. In particular, worldgen modifiers loaded
through Lithostitched can wrap `minecraft:overworld/offset` with vanilla-height assumptions; Hybrid
Aquatic has produced this failure mode. The registered density graph and active wrappers therefore
explain some vanilla-derived cutoffs even when `terrainModelHeight()` and source terrain remain
valid.

## Generated-world compatibility

Changing terrain, biome scheduling, feature reach, or structure position changes new chunks.
Existing chunks retain stored data. Exact coordinate stability is a separate compatibility property
from successful old-world loading.
