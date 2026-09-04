# FreeTerraForged Documentation

Documentation for the `games/minecraft/mods/FreeTerraForged` submodule lives here so engineering
reference, active planning, and local branch state do not need to be committed to an upstream-facing
code branch.

## Where to read

- [`AGENTS.md`](../../../../../AGENTS.md) — durable repository operating rules and architectural
  constraints. Keep it because agents must receive these rules before choosing an investigation or
  implementation path; do not put branch status or investigation conclusions there.
- [`agent-resume.md`](../../../../../agent-resume.md) — concise routing, accepted state, and current
  integration boundary. It points to authoritative documents and retained evidence rather than
  preserving a session history.
- [`wiki/README.md`](wiki/README.md) — current FTF engineering concepts: mental models, data flow,
  coordinate meanings, ownership boundaries, and compatibility invariants.
- [`Compatibility-runtime acceptance`](plans/compatibility-runtime-completion.md) — the implemented
  runtime, accepted verification surface, and current production-artifact state.
- [`Minecraft reference`](../../wiki/README.md) — general Minecraft world-generation reference for
  reusable engine concepts such as extended height, placed features, structures, and biome climate.
- [`plans/`](plans/) — current product contracts, acceptance records, and genuinely unfinished
  implementation work. Completed investigation narratives do not remain here.
- [`refs/branch-map.md`](refs/branch-map.md) — current local FTF branch/worktree state.

## Documentation boundaries

The FTF wiki explains current FTF-specific engineering behavior. General Minecraft pages explain
reusable engine behavior. Plans contain current product contracts, unresolved decisions, and
acceptance boundaries only.

`AGENTS.md` remains necessary as the compact policy boundary: evidence standards, safety rules,
runtime ownership, and documentation hygiene must apply before any task-specific plan is read.
`agent-resume.md` remains necessary only as a small current-state router. If either begins carrying
run-by-run history or detailed conclusions, move that material to retained artifacts or the active
plan and restore the document to its stated role.

Retrospectives, session timelines, branch archaeology, feature summaries, QA records, and evidence
dumps are outside the wiki's scope. Reusable technical knowledge appears in concept pages;
feature-specific work appears in plans or PR descriptions.
