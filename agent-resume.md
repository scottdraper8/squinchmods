# ReTerraForged resumption index

## Active work: biome-fixing-plan Phase 4 — reachability audit

Read the plan and initial findings before continuing:

```text
.agent-docs/games/minecraft/mods/FreeTerraForged/plans/biome-fixing-plan.md  (Phase 4 section)
```

**Status (2026-08-06):** 5 censuses completed and classified (ocean, cold inland, warm inland,
mountain, warm humid). 29/53 biomes `REACHABLE`, 24 classified as `SHADOWED_IN_SAMPLED_DOMAIN` or
`SPECIAL_CASE_ONLY` across 6 mechanism groups (offset penalty, humidity discretization,
continentalness×erosion range, temperature×humidity range, ocean temperature range, mushroom
override). Aggregate in `investigation-state/census-aggregate-phase4-initial.json`.

**Next steps:** Expand coverage per remaining test matrix (deep-world/max-vertical fixtures, biome
sizes 50/900, TerraBlender integration, Regions Unexplored). TerraBlender/RU testing requires
additional mod JARs — the scenario system does not support this natively; needs build change or
manual mod placement.

Key files:

- Probe: `games/minecraft/investigations/reterraforged/probes/reachability-census/`
- Scenarios:
  `.squinch/games/minecraft/mods/FreeTerraForged/investigations/rtf-reachability-census*.toml`
- FTF submodule: `games/minecraft/mods/FreeTerraForged/` branch `fix/various-biome-issues` at
  `c435960`

---

The cellular archipelago/island-transition rewrite remains a scoped investigation and has not yet
entered implementation.

## Separate work: cellular archipelago rewrite

Read the active plan fully before changing code:

```text
.agent-docs/games/minecraft/mods/FreeTerraForged/plans/archipelago-redesign.md
```

No implementation branch has been created.

For the reusable terrain-region and shoreline-distance models, see
`.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/terrain-shaping-and-regions.md` and
`.agent-docs/games/minecraft/mods/FreeTerraForged/wiki/concepts/hydrology-and-shore-geometry.md`.

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

Use seed `3216933670` and the three canonical archipelago fixtures in:

```text
games/minecraft/investigations/reterraforged/fixtures/archipelago/
```

Also include a default-depth/default-island control and the known regression area around
`(230250, 163350)`. Measure continuity, real-block shelf slope, island count/footprint, whole-island
continent clearance, deterministic output, chunk boundaries, and generation cost. The complete
acceptance criteria are in `plans/archipelago-redesign.md`.

## Shared references

- Canonical FTF fixtures (source-form, semantic names, resolved-preset/archive hashes recorded per
  run): `games/minecraft/investigations/reterraforged/fixtures/`.
- Headless server workflow: `.agent-docs/games/minecraft/agentic-development-guide.md`
- Mapped vanilla 1.21.1 source: `games/minecraft/reference/sources/1.21.1/official/src/`
- Third-party mod source (fetched on demand, not committed):
  `games/minecraft/reference/sources/<version>/mods/<mod-name>/`
- Investigation tooling: `tooling/squinch mc-investigate --help`
  (`games/minecraft/tooling/investigate/`)
