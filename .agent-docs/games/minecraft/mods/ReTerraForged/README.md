# ReTerraForged Agent Docs

Planning and reference material for the `ReTerraForged` mod submodule
(`games/minecraft/mods/ReTerraForged`), centralized here rather than kept inside the fork itself —
see `../../../README.md` for why.

## Provenance

Everything under `plans/` (except `rtf-1.21.1-branch-split-plan.md`) and everything under `refs/`
was migrated on 2026-07-07 from the RTF fork's `scottdraper8/docs` orphan branch, which used a local
`agent-ref/` convention on the code branches. See `refs/branch-map.md` for the full branch inventory
and provenance detail, and `plans/tall-world-scaling/world-height-cutoff-investigation.md` for a
known content-loss case (one referenced planning doc was never committed anywhere and could not be
recovered).

The source branch/convention is retired as of this migration — new RTF planning work should be added
directly here, not in a per-submodule `agent-ref/` folder or docs branch.

## Layout

```text
plans/
  rtf-1.21.1-branch-split-plan.md   overview of how the topic branches relate to 1.21.1/staging
  ocean-depth/                       configurable ocean depth feature
  strata/                            strata thickness weighting
  mountain-variability/              mountain scaling, summit shaping, variety
  tall-world-scaling/                tall-world height cutoff investigation + recovered findings
  shorelines/                        beach/shore port (beach system, integration, compat)
refs/
  branch-map.md                      RTF branch inventory and agent-ref/docs-branch history
```

`river-carving` and `water-table` topics were considered but have no dedicated planning docs in
RTF's history — related material is scattered inside `shorelines/integration-plan.md`.
