# ReTerraForged Documentation

Documentation for the `games/minecraft/mods/ReTerraForged` submodule lives here so engineering
reference, active planning, and local branch state do not need to be committed to an upstream-facing
code branch.

## Where to read

- [`wiki/README.md`](wiki/README.md) — current RTF engineering concepts: mental models, data flow,
  coordinate meanings, ownership boundaries, and compatibility invariants.
- [`Minecraft reference`](../../wiki/README.md) — general Minecraft world-generation reference for
  reusable engine concepts such as extended height, placed features, structures, and biome climate.
- [`plans/`](plans/) — only genuinely unfinished implementation work. Completed investigations and
  merged feature narratives do not remain here.
- [`refs/branch-map.md`](refs/branch-map.md) — current local RTF branch/worktree state.

## Documentation boundaries

The RTF wiki explains current RTF-specific engineering behavior. General Minecraft pages explain
reusable engine behavior. Active plans contain remaining decisions, implementation steps, and
acceptance gates only.

Retrospectives, session timelines, branch archaeology, feature summaries, QA records, and evidence
dumps are outside the wiki's scope. Reusable technical knowledge appears in concept pages;
feature-specific work appears in plans or PR descriptions.
