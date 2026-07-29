# ReTerraForged Agent Docs

Planning and reference material for the `ReTerraForged` mod submodule
(`games/minecraft/mods/ReTerraForged`), centralized here rather than kept inside the fork itself —
see `../../../README.md` for why.

## Provenance

These references were centralized from the RTF fork's retired `scottdraper8/docs`/`agent-ref/`
convention. New RTF planning and QA documentation belongs here rather than inside a code worktree.
`refs/branch-map.md` records the branch inventory.

## Layout

```text
plans/
  ocean-depth/                       configurable ocean depth feature
  strata/                            strata thickness weighting
  mountain-variability/              mountain scaling, summit shaping, variety
  tall-world-scaling/                retrospective only; branch retired 2026-07-18, split into
                                      ocean-depth and mountain-variability above
  biome-climate-banding/             root climate correction and dynamic underground banding
  shorelines/                        beach/shore port (beach system, integration, compat)
qa/
  presets.md                         shared preset roles, checksums, and reproduction notes
  presets/                           canonical datapack archives
refs/
  branch-map.md                      RTF branch inventory
```

`river-carving` and `water-table` topics were considered but have no dedicated planning docs in
RTF's history — related material is scattered inside `shorelines/integration-plan.md`.
