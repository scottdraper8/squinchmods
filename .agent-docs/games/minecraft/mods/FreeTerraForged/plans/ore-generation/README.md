<!-- markdownlint-disable MD013 MD038 MD046 -->

# FreeTerraForged Dynamic Ore Generation

This directory defines the current design for making ordinary ore generation follow an FTF Overworld
that can be vertically larger or smaller than Minecraft's reference frame. The target is dynamic
concentration, not a fixed number of attempts or blocks per chunk.

## Current answer

The design gates are closed and the implementation is committed and pushed on
`feat/ore-contract-classifier` at `0a0b05e`. Its isolated worktree is:

`games/minecraft/investigation-state/worktrees/ftf-ore-contract-classifier`

For every active final occurrence whose configured feature is `minecraft:ore` or
`minecraft:scattered_ore`, FTF:

1. classifies the complete public placement contract;
2. derives the authored Y probability mass in Minecraft's reference Overworld;
3. maps that intensity into the live FTF geological frame;
4. scales expected attempts by the mapped cell widths; and
5. runs the original X/Z sampler, filters, biome check, ore geometry, target rules, outputs, and
   exposure behavior.

The implementation is namespace-agnostic. Create zinc and Immersive Ores vibranium follow this path
because they use the standard mechanism. Create striated ores, geodes, Mekanism, Immersive
Engineering retrogen, and other custom configured features remain unchanged. Noise-router
`largeOreVeins` is separate.

## What changes in a world

- A deeper supported geological band receives more independent ore origins across its added Y
  volume.
- A shorter band receives fewer origins through unbiased stochastic thinning.
- High- and low-altitude producer shapes retain their authored uniform, triangular, or trapezoid
  profile after mapping.
- Deposit size and shape do not grow. More or fewer deposits are attempted.
- X/Z coordinates are never stretched; additional attempts receive independent authored X/Z samples.
- A reference frame of `-64..319` with sea level `63` delegates exactly to vanilla and consumes no
  additional random values.
- A feature whose own mapped distribution is unchanged also delegates exactly, even if another part
  of the world is taller or deeper.

This is automatic for supported ordinary ores in an FTF Overworld. It is not the
`oreCompatibleStoneOnly` setting, and it does not enable or enlarge noise-router large ore veins.

## Preserved contracts

The dynamic path changes only candidate Y and the expected number of candidate trials. It preserves:

- final dimension, biome, decoration step, and occurrence order;
- authored X/Z sampling;
- configured `OreConfiguration` size and geometry;
- ordered target rules and output block states;
- discard-on-air-exposure probability;
- downstream vanilla and custom placement filters; and
- distinct producer variants for the same material.

Unsupported height providers, unknown position transformers, unregistered direct features,
conflicting contracts for one ID, and filters that run before any safe expansion boundary fail
closed to unchanged generation with a reason code.

## Evidence status

The evidence program now covers:

- complete final-graph ordinary-ore census on Fabric and NeoForge;
- absolute, above-bottom, below-top, mixed, uniform, triangular, and trapezoid providers;
- reference identity, shallow-floor contraction, deep/maximum expansion, and short-ceiling
  contraction;
- random/count, rarity, implicit multiplicity, and all safe pre-spatial fanout locations;
- per-call deposits, target/exposure rejection, X/Z/Y origins, raw writes, final survival,
  overwrites, and finished host opportunities;
- standard `ore` and `scattered_ore` runtime writes;
- Create zinc with its custom filter and unchanged striated custom feature;
- Immersive Ores vibranium with its unchanged custom geode path;
- loader-identical candidate sampling after `/reload`;
- exact reference-frame baseline identity; and
- matched maximum-frame timing: `8.165s` baseline versus `8.862s` dynamic median generation
  (`+8.5%`) across 16 finished chunks.

The formula preserves local pre-biome candidate intensity. It cannot promise identical finished ore
ratios across terrains: host material, caves, fluids, exposure rejection, overlapping producers, and
later decoration remain authored inputs. Realized-write telemetry is retained to prove that the
formula produces actual ore and to explain those differences; it is not used as a feedback
controller.

## Documents

- [`decisions.md`](decisions.md): concrete policy and boundary decisions.
- [`implementation-plan.md`](implementation-plan.md): runtime architecture and acceptance criteria.
- [`investigation-plan.md`](investigation-plan.md): completed evidence packages and remaining QA.
- [`knowledge-base.md`](knowledge-base.md): mechanism model and measured results.
- [`test-matrix.md`](test-matrix.md): exact stacks and run identifiers.

## Repository state

The branch is source-clean. Implementation review, same-seed player A/B QA, and final
reference-frame identity/release verification remain. Do not copy it into or alter the shared FTF
submodule worktree.
