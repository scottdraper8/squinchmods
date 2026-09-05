# Trail Ruins shell-exposure baseline

## Status: 2026-09-05

Baseline empirical measurement of Trail Ruins burial under RTF's plain default preset, on
`upstream/1.21.1`, with a vanilla-terrain control. Not a fix. The scanner establishes finished-world
shell adjacency; it does not by itself distinguish intended Trail Ruins surface visibility from an
RTF-specific protrusion defect.

This shell metric is superseded as the defect oracle by `trail-ruins-terrain-deformation.md`, which
measures each rigid piece's `BURY` ground plane against the terrain surface used by real RTF chunks.
The shell artifacts remain useful evidence of expected surface contact and of why shell visibility
alone cannot diagnose the large terrain shelves.

## Setup

- Worktree: `games/minecraft/investigation-state/worktrees/ftf-trail-ruins`, branch
  `fix/trail-ruins-encapsulation`. The RTF run used `upstream/1.21.1` at `f9c254e`. The worktree was
  subsequently fast-forwarded cleanly to live upstream `95c9b21`; the intervening commits only
  change preset UI/C2ME guarding and do not touch structure or terrain generation.
- Fixture:
  `games/minecraft/investigations/reterraforged/fixtures/modern-default-with-rivers-live-export` —
  RTF's own live default preset (`Presets.modernDefaultWithRivers()`), captured through the real
  `PresetConfigScreen.exportAsDatapack` path (`WorldCreationContext.worldgenLoadContext()` for a
  genuine `RegistryAccess`) via `tooling/squinch mc-investigate client` with the
  `client-world-lifecycle` probe pack, since `tooling/squinch mc-investigate preset-fixture` cannot
  produce a current-schema fixture against any plain-`upstream/1.21.1` worktree (see
  `agentic-development-findings.md`). The `client-world-lifecycle` run itself confirmed the fixture
  loads a real overworld (run `20260904T234748Z-8b0224b2a5`).
- Seed: `3216933670` (same seed used throughout the existing FTF compatibility/QA evidence).
- RTF candidate discovery:
  `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-trail-ruins-locate-discovery.toml`,
  run `20260904T235006Z-7b11f79340` — thirteen `/locate structure minecraft:trail_ruins` queries
  spread across a roughly 15000x15000 block area, yielding 11 unique candidate structures.
- RTF measurement:
  `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-trail-ruins-enclosure-scan.toml`, run
  `20260904T235233Z-3a74d31572` — force-generates a 13x13 chunk (208x208 block) region centered on
  each candidate's chunk-aligned start (Trail Ruins' `max_distance_from_center` is 80 blocks / 5
  chunks, so this covers the full footprint plus shell-scan margin), then runs
  `games/minecraft/investigations/reterraforged/probes/trail-ruins-enclosure`
  (`squinch:rtf-trail-ruins-enclosure`) against the real, finished `StructureStart`/`StructurePiece`
  bounds. The probe scans the one-block shell immediately outside each piece's real bounding box
  (excluding cells inside another piece of the same structure) and classifies each shell cell as
  buried, open (air/fluid), or open-with-sky-access. This is finished-chunk authority: real
  generated blocks, not a prediction. The scenario's own steps all succeeded (`state: "succeeded"`
  in `scenario-summary.json`); only the post-scan world-save over RCON timed out during shutdown
  (`games/minecraft/investigation-state/active/` recovered cleanly via
  `mc-investigate doctor --recover`), which does not affect the retained per-step probe results.
- Vanilla-terrain control discovery:
  `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-trail-ruins-vanilla-locate-control.toml`,
  run `20260905T132955Z-e75fd5b396` — the same seed and query grid, with no RTF preset datapack,
  yielded 13 unique candidates.
- Vanilla-terrain control measurement:
  `.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-trail-ruins-vanilla-enclosure-control.toml`,
  run `20260905T133121Z-e7b267ab9e` — the same version-1 probe and 13x13-chunk coverage at all 13
  candidates. All steps and cleanup succeeded on clean `upstream/1.21.1` `95c9b21`.

## RTF result

11 of 11 located Trail Ruins instances have a non-empty, sky-visible opening in their shell scan.
The query grid was chosen without reference to exposure, but nearest-structure results from a fixed
grid are not a statistically random sample of all Trail Ruins and are not labeled unbiased.

The probe's version-1 field named `exposed_fraction` is `shell_open / shell_examined`, including
both sky-visible and enclosed air/fluid. It is reported here as **open fraction**. Sky fraction is
`shell_sky_exposed / shell_examined` and is calculated directly from the retained integer counts.

| Candidate (chunk-aligned start) | BBox Y range | Pieces | Shell examined | Shell open | Sky-exposed | Open fraction | Sky fraction |
| ------------------------------- | ------------ | ------ | -------------- | ---------- | ----------- | ------------- | ------------ |
| (-880, 1696)                    | 71..113      | 20     | 2834           | 33         | 20          | 0.0116        | 0.0071       |
| (3648, 256)                     | 51..95       | 17     | 2846           | 130        | 56          | 0.0457        | 0.0197       |
| (-480, -3232)                   | 131..174     | 19     | 3232           | 103        | 103         | 0.0319        | 0.0319       |
| (2800, 2272)                    | 130..174     | 18     | 2719           | 74         | 22          | 0.0272        | 0.0081       |
| (-4544, -2560)                  | 50..94       | 18     | 3122           | 105        | 88          | 0.0336        | 0.0282       |
| (3120, -3216)                   | 28..75       | 18     | 3555           | 109        | 64          | 0.0307        | 0.0180       |
| (-1968, 5008)                   | 37..82       | 23     | 3336           | 35         | 4           | 0.0105        | 0.0012       |
| (6064, 8512)                    | 188..233     | 18     | 2929           | 62         | 38          | 0.0212        | 0.0130       |
| (-6144, 5760)                   | 25..76       | 19     | 3392           | 40         | 30          | 0.0118        | 0.0088       |
| (6576, -3616)                   | 118..163     | 19     | 2697           | 111        | 82          | 0.0412        | 0.0304       |
| (-7552, -6480)                  | 85..128      | 18     | 3046           | 248        | 128         | 0.0814        | 0.0420       |

Open fraction ranges 1.05%-8.14%; sky fraction ranges 0.12%-4.20%. No shell scan hit its
200000-sample cap (`shell_scan_capped: false` throughout), so the aggregate counts cover each
instance's complete deduplicated one-block piece shell.

## Vanilla control and interpretation

The vanilla-terrain control also has nonzero sky-visible shell cells in 13 of 13 instances. Its open
fraction range (0.98%-8.66%) overlaps and slightly exceeds the RTF range. The RTF sample has greater
sky-visible severity, but the distributions still overlap:

| Terrain     | Instances | Sky-positive | Open fraction min / median / mean / max | Sky fraction min / median / mean / max |
| ----------- | --------: | -----------: | --------------------------------------- | -------------------------------------- |
| RTF default |        11 |           11 | 1.05% / 3.07% / 3.15% / 8.14%           | 0.12% / 1.80% / 1.89% / 4.20%          |
| Vanilla     |        13 |           13 | 0.98% / 2.69% / 3.77% / 8.66%           | 0.03% / 0.98% / 0.97% / 1.72%          |

This is descriptive, not a matched or causal comparison: the two biome sources place Trail Ruins at
different coordinates and produce different piece layouts. It invalidates the interpretation that
the 11/11 sky-positive rate itself demonstrates an RTF failure. Vanilla source also makes some
surface contact expected: Trail Ruins starts 15 blocks below `WORLD_SURFACE_WG`; the selected tower
base templates are 13 blocks high and attach a four-block tower-top piece from a Y=12 upward jigsaw.
`BURY` adds density around each rigid piece from its ground-level plane; it is not a full enclosure
contract.

For the RTF candidate with the largest open fraction, (-7552, -6480), the version-1 result retains
only the first 40 examples out of 248 open shell cells. Those examples occupy Y 113..115 and a small
X/Z window, but they do not establish the bounds of all 128 sky-visible cells or identify which
piece owns them. The earlier stronger geometry claim is therefore unsupported by this artifact.

## Questions outside this baseline

- Shell visibility's correlation with biome remains descriptive rather than diagnostic. The
  terrain-deformation investigation establishes the relevant relief relationship directly: 9 of 11
  original RTF graphs have a rigid-piece `BURY` plane above the filtered terrain surface, versus 1
  of 13 vanilla controls against vanilla's structure-free surface.
- Whether the sky-visible shell is adjacent to actual retained structure blocks, rather than empty
  volume inside a piece bounding box. The current probe scans outside real piece bounds but does not
  identify template occupancy or visible structure blocks.
- Whether any instance is buried but has a _non-air_ opening (e.g., water) that the probe's
  `isOpen()` (air or fluid) already covers, or an enclosed-but-unreachable void the shell scan
  cannot distinguish from a true surface breach at this single-block-shell resolution.
- The built-in registry contains no other jigsaw structure combining `BURY` with heightmap
  projection. Strongholds use `BURY` but not the projected-jigsaw pathway. Datapack structures
  remain outside this baseline and require their own placement-contract evidence.
