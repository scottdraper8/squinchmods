<!-- markdownlint-disable MD013 MD038 MD046 -->

# Ore Generation Decisions

These are the current constraints for the eventual FTF ore implementation. Open items remain
explicit gates.

## Accepted decisions

### D-001 — Fixed target and latest-stable evidence

The target is Minecraft `1.21.1` at FTF baseline `908595b`. Every current run uses the newest stable
compatible release for its loader. Beta/alpha artifacts, stale generated JARs, and mixed API stacks
are not stable evidence. A candidate with no stable build is a separately labeled composition
diagnostic.

### D-002 — Defer the implementation branch

Do not create the ore implementation branch until vertical mapping and density policy are supported
by realized-write evidence and the standard/custom boundary is concrete. The active preview-hotfix
branch remains separate.

### D-003 — First supported feature contracts

The first adapter targets only configured features proven to use the vanilla `minecraft:ore` or
`minecraft:scattered_ore` contract. Classification is contract-based, not namespace- or
generation-step-based.

### D-004 — Preserve authored placement semantics

Unless an explicit later decision changes them, preserve biome scope, feature order, generation
step, count/rarity, horizontal placement, target rules, vein size, exposure rules, custom filters,
and modifier order.

### D-005 — Preserve and report unsupported systems

Unknown codecs, custom features, custom filters, custom placement modifiers, and noise-router veins
must remain unchanged and produce a compatibility diagnostic. Create striated ores and Lithostitched
ore are examples of custom systems.

### D-006 — Separate candidate counts from realized density

Candidate calls, biome passes, successful feature calls, and block writes are separate metrics. No
attempt multiplier or density-compensation policy is allowed based on candidate counts alone.

### D-007 — Keep noise veins separate

`largeOreVeins` is a noise-router system, not an ordinary placed-feature ore. It requires its own
implementation or diagnostic decision.

### D-008 — Treat companion categories differently

Vanilla, Create, and Immersive Ores provide ownership evidence. Regions Unexplored and BOP are
composition cases. Mekanism and Immersive Engineering are later custom-system cases. Biome Ore
Richness is excluded because it adds extra vanilla ore placements and would confound ownership.

### D-009 — Do not assume `oreCompatibleStoneOnly` is active

The setting currently has no effective alternate tag-generation branch. It must be repaired,
redefined, or removed in a separate decision before it is used as an ore policy.

## Open gates

- Map absolute, bottom-relative, top-relative, triangular, and mixed height providers.
- Choose preserve-attempts, preserve-local-density, or bounded/sublinear density behavior.
- Define the exact supported boundary for custom filters and modifiers.
- Decide whether replacement provenance is needed beyond the final graph census.
- Decide whether noise-router veins and `oreCompatibleStoneOnly` are implementation work or separate
  diagnostics.
