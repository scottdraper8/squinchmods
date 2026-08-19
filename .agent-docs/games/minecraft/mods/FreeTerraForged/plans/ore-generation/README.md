<!-- markdownlint-disable MD013 MD038 MD046 -->

# FreeTerraForged Ore Generation

This directory documents the current ore-generation behavior and the evidence needed before changing
it. It is intentionally about ore behavior, not a chronology of the biome work.

## Current state

The investigation baseline is Minecraft `1.21.1`, FreeTerraForged `908595b`, with the active
preview-hotfix submodule kept separate. The current latest-stable runtime stack is:

| Component               | Version              |
| ----------------------- | -------------------- |
| Fabric Loader           | `0.19.3`             |
| Fabric API              | `0.116.15+1.21.1`    |
| NeoForge                | `21.1.248`           |
| Create                  | `6.0.10+mc1.21.1`    |
| Immersive Ores Fabric   | `1.21.1-1.1.8`       |
| Immersive Ores NeoForge | `1.21.1-1.1.9`       |
| Regions Unexplored      | `0.6.2-fabric-21.1`  |
| Lithostitched           | `1.7.13-fabric-21.1` |

All current controls, the feature-graph census, Create, Immersive Ores, and Regions Unexplored
scenarios pass on this stack. No production ore code or implementation branch has been created.

Biomes O' Plenty is not a stable `1.21.1` case: its compatible BOP/TerraBlender/GlitchCore chain is
beta-only. It remains a composition diagnostic and cannot be used as stable-matrix evidence. This is
an availability boundary, not an unresolved RU-style startup failure.

## What ore generation actually does

For ordinary ores, generation is this pipeline:

```text
final biome
→ final biome placed-feature list
→ decoration step and placement modifiers
→ height provider / filters
→ configured ore feature
→ target-block rules and vein geometry
→ terrain, caves, and later writes
```

The final biome feature list is authoritative. `UNDERGROUND_ORES` contains disks and other non-ore
features, so the implementation must classify by configured-feature contract rather than by
generation step or namespace.

For `minecraft:ore`, the configured feature owns target rules and vein size. The placed feature owns
count or rarity, horizontal placement, height, and filters. A candidate can pass placement and still
write no block because its target block is absent, terrain is missing, or exposure rules reject it.
Candidate calls, biome passes, successful feature calls, and actual block writes are separate
measurements.

FTF's existing dynamic height hook recognizes one canonical `above_bottom(0)` to `absolute(256)`
range. It does not classify ordinary ore contracts or automatically remap the varied vanilla ore
ranges. The ordinary ore adapter therefore remains unimplemented and must be contract-aware.

Noise-router large ore veins are a separate system from placed features. Custom feature systems,
including Create striated ores and Lithostitched's ore feature, are diagnostic-only until their
contracts are deliberately supported.

## Current findings

- Reference, shallow, extreme, standard, two extra seeds, mountain, and cave controls pass with
  complete block-write telemetry.
- Changing terrain depth changes realized writes and their Y distribution; candidate counts alone do
  not predict ore output.
- The final feature graph has no duplicate memberships in either loader run. Registry entries that
  are inactive and same-contract groups are reported as candidates, not claimed replacements.
- Create zinc is a standard ore feature with a custom filter; Create striated ores are custom.
- Immersive Ores vibranium is an additive conventional placed feature. Its geode feature is active
  in the graph but produced no writes in the current window.
- Regions Unexplored reaches generation on its current stable stack and writes its vanilla
  `minecraft:ore` redstone-large feature. It is composition evidence, not clean FTF ownership
  evidence.
- Mekanism and Immersive Engineering are later custom-system investigations.

## Documents

- [`knowledge-base.md`](knowledge-base.md): current ore mechanics, measurements, graph census, and
  ownership findings.
- [`test-matrix.md`](test-matrix.md): exact current versions, acquisition status, and run records.
- [`investigation-plan.md`](investigation-plan.md): remaining questions and experiments.
- [`decisions.md`](decisions.md): constraints on an eventual implementation.
- [`implementation-plan.md`](implementation-plan.md): production design boundary; no implementation
  is authorized yet.

## Stable-version policy

Every current investigation run must use the newest stable artifact compatible with Minecraft
`1.21.1` and its requested loader. Beta and alpha artifacts are not stable evidence. When no stable
build exists, record the candidate as a composition diagnostic and do not substitute a beta build,
stale generated JAR, or mixed API/runtime stack.

The latest-stack runs use the detached merged-baseline investigation worktree. The active
`hotfix/biome-previewer-bugs` submodule is not modified by this investigation.

## Branch gate

Do not create an ore implementation branch until the remaining design questions have concrete
answers: vertical anchor mapping, density policy, and the supported/unsupported boundary for custom
placement contracts. The current evidence is sufficient to design the classifier and diagnostics,
not yet sufficient to authorize production adaptation.
