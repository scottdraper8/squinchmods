# ReTerraForged resumption index

A dynamic cave-feature-placement investigation, production fix, and cross-loader QA suite are now
complete alongside the existing archipelago/island-transition rewrite. The underground biome-climate
and banding fix is complete and has its own retrospective.

## Completed work: dynamic cave feature placement

Issue #133 is not fixed by the underground biome-climate PR. Live NeoForge and Fabric runs with
Biomes O' Plenty confirmed that valid Spider Nest cave cells exist above `Y=256` while the biome's
placed features sample candidate origins only through absolute `Y=256`. Very-deep runs confirmed
that the lower bound follows the configured bottom but fixed attempt counts are diluted across the
enlarged vertical range.

The production branch now contains the generic fix, while the QA branch contains instrumentation
around the exact same shipping classes. The fix recognizes the exact
`uniform(bottom, absolute(256))` placement signature and preserves density by retaining one sample
in `-64..256`, then adding stratified/probabilistic samples at one expected origin per 321 extended
Y levels. It does not use biome, feature, or mod ID allowlists. The implementation produced BOP
Spider Nest decorations above 256 on both loaders and restored deep Deep Dark density.

Read the completed investigation, implementation details, and evidence here:

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/cave-feature-placement/cave-feature-placement-investigation.md
.agent-docs/games/minecraft/mods/ReTerraForged/plans/cave-feature-placement/fixed-y-worldgen-follow-up-audit.md
```

The scaffolded branches/worktrees are:

```text
fix/dynamic-cave-feature-placement
games/minecraft/mods/ReTerraForged-cave-feature-fix

qa/dynamic-cave-feature-placement
games/minecraft/mods/ReTerraForged-cave-feature-qa
```

Production commits:

```text
80d56a9 Scale canonical cave feature placement with world height
e6b0964 Make extended height sampling position-deterministic
```

QA commits:

```text
5b2e7d2 Add dynamic cave placement QA prototype
3a81e57 Scale canonical cave feature placement with world height
f623a06 Make extended height sampling position-deterministic
```

Both production loaders build cleanly. Final 256-chunk live runs cover default, tall, and very-deep
RTF presets; NeoForge and Fabric; BOP 21.1.0.14; high Spider Nest decoration; Deep Dark decoration
down to Y -603; density ratios; and coarse generation cost.

BOP has a separate upstream limitation: 29 configured-feature classes contain literal Y 255 checks,
including four Glowing Grotto glowshroom features. Do not add BOP-specific workarounds to RTF. The
distinct follow-up audit classifies those checks plus fixed carver ranges, ore distributions,
surface thresholds, structure heights, and suspicious RTF-local height arithmetic.

## Active work: cellular archipelago rewrite

Read these two documents fully before changing code:

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/island-interaction-investigation.md
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/archipelago-follow-up-scope.md
```

No implementation branch has been created.

### Problem

Three mechanisms contribute to abrupt island walls:

1. `ArchipelagoPopulator.sizeNoise` contains a high-frequency domain warp whose strength exceeds its
   wavelength enough to fold the sampled field. A tested strength reduction removes the fold, but
   that isolated patch should not ship because the rewrite replaces this path.
2. Island shelf width is expressed in alpha-space while the elevation it must cover grows with
   `oceanDepth`. The same horizontal span therefore becomes much steeper in deep-ocean presets.
3. `continentFade` is multiplied into island alpha independently at every point. Near a continent,
   one island can be clipped or partly erased instead of being accepted or rejected as a stable
   whole.

Only the shelf-height mismatch is caused by configurable ocean depth. The fold and unstable
continent eligibility are older archipelago-design problems.

### Required solution

Replace alpha-derived island placement and blending with a cellular/Worley design that exposes:

- deterministic island-cell identity and center;
- density/skip decision per cell;
- a real-block signed distance to the island shoreline; and
- stable per-island size/shape values.

Use that distance to express shelf, beach, and land bands in blocks. Scale shelf width against the
elevation it must cover, bounded relative to island radius.

Replace pointwise `continentFade` with a stable per-island clearance decision against the rendered
main-continent coastline. A cellular island distance does not solve continent clearance by itself.

Exact island-coordinate compatibility is not a goal; the rewrite will relocate enabled archipelagos.
Do not merge an intermediate relocation that omits the distance-based shelf and stable continent
exclusion that justify the compatibility break.

### First implementation steps

1. Create a dedicated branch/worktree from current `1.21.1`.
2. Port the existing archipelago profiler into committed QA source and record baseline island count,
   footprint, radii, shelf widths, terrain mix, and height profiles.
3. Prototype nearest jittered-cell resolution, stable cell identity, density skip, size variance,
   and real-block shoreline distance independently of terrain shaping.
4. Convert shelf/beach/land transitions to distance bands.
5. Add stable whole-island continent clearance.
6. Port island terrain shaping, then tune and validate the complete system.

### Validation matrix

Use seed `3216933670` and the three canonical archipelago presets in:

```text
.agent-docs/games/minecraft/mods/ReTerraForged/qa/presets/
```

Also include a default-depth/default-island control and the known regression area around
`(230250, 163350)`. Measure continuity, real-block shelf slope, island count/footprint, whole-island
continent clearance, deterministic output, chunk boundaries, and generation cost. The complete
acceptance criteria are in `archipelago-follow-up-scope.md`.

## Completed work: underground biome climate and banding

The production implementation is complete on `fix/biome-climate-mapping` and PR #152 is open. It
corrects underground climate inputs, prevents terminal Deep Dark regions from occupying hundreds of
blocks in deep worlds, scales underground regions with Biome Size and world dimensions, supports
compatible modded cave-biome registrations, and reaches finished chunk biome palettes.

There is no remaining climate/banding implementation task. Read the retrospective for the final
design, compatibility limits, evidence, scanner workflow, and screenshot coordinates:

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/biome-climate-banding/biome-climate-banding-investigation.md
```

The uncommitted PR-body sandbox is `PR-DESCRIPTION-DRAFT.md` at this repository root. It is locally
excluded from Git. The rebuilt Fabric artifact is:

```text
/var/home/scott/Desktop/rtf-biome-banding-fix.jar
SHA-256: 973472d59ce92cfc051bd5efc276ea7ac867c0ffabf443f308ed1dde8d5c5131
```

## Shared references

- Canonical preset descriptions and checksums:
  `.agent-docs/games/minecraft/mods/ReTerraForged/qa/presets.md`
- Headless server workflow: `.agent-docs/games/minecraft/live-worldgen-investigation-howto.md`
- Mapped vanilla 1.21.1 source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Dev-server tooling: `games/minecraft/tooling/dev-server`
- Clean climate-fix worktree: `games/minecraft/mods/ReTerraForged-biome-climate-fix`
- Climate QA/scanner worktree: `games/minecraft/mods/ReTerraForged-biome-climate-qa`
