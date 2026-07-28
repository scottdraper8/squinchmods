# ReTerraForged Branch Map

Snapshot as of the 2026-07-07 `agent-ref/` migration, updated 2026-07-27. Reflects `origin` branches
on `scottdraper8/ReTerraForged` — reverify before relying on it long-term.

## Active/code branches

| Branch                             | `agent-ref/` in `.gitignore`? | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ---------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.21.1`                           | Yes                           | Currently the commit squinchmods' submodule pointer is pinned to (via a tag on this branch)                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `feat/configurable-shorelines`     | Yes                           | See `plans/shorelines/`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `feat/configurable-strata`         | Yes                           | See `plans/strata/`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `feat/mountain-region-variability` | Yes                           | See `plans/mountain-variability/`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `qa/biome-climate-mapping`         | Yes                           | Working branch for the underground biome-climate-banding line. Root mapping fix `bbd845c`, production dynamic-banding commit `ad491ab`, retained QA scanner `78fab7e`, and a region-aware fix to the scanner's own comparison baseline `0664f23` (see the plan doc's "Multi-region compatibility — closed"). Both real fixes and QA/testing instrumentation should continue landing here. See `plans/biome-climate-banding/biome-climate-banding-investigation.md` and `plans/biome-climate-banding/dynamic-underground-biome-banding-plan.md`. |
| `fix/biome-climate-mapping`        | Yes                           | Clean PR/ship candidate with no QA scaffolding: root mapping fix `bbd845c`, followed by dynamic-banding commit `7a0491b` (the clean cherry-pick of QA-branch production commit `ad491ab`). As the QA branch gains further work, replicate only production commits here.                                                                                                                                                                                                                                                                         |
| `fixCarvingNearRivers`             | No                            | Predates the `agent-ref/` convention; no captured planning docs found                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `fixOceanRivers`                   | No                            | Predates the convention; no captured planning docs found                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `unresolvedexperiments`            | No                            | Predates the convention; no captured planning docs found                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `vanity`                           | No                            | Predates the convention; no captured planning docs found                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `waterTableWorks`                  | No                            | Predates the convention; no captured planning docs found                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

## Merged upstream (branch deleted)

PRs from `scottdraper8/ReTerraForged` accepted into `ETcodehome/ReTerraForged`. Feature and QA
branches are deleted locally/remotely once merged; planning docs stay under `plans/`.

| Branch                          | PR                                                                                   | Notes                         |
| ------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------- |
| `feat/configurable-ocean-depth` | [ETcodehome/ReTerraForged#97](https://github.com/ETcodehome/ReTerraForged/pull/97)   | See `plans/ocean-depth/`      |
| `feat/world-seed-input`         | [ETcodehome/ReTerraForged#142](https://github.com/ETcodehome/ReTerraForged/pull/142) | No local branch was ever kept |

None of the "Yes" branches carry tracked content under `agent-ref/` at their tip — it's purely a
gitignore rule on all of them. All real committed planning content lived on the now-deleted
`scottdraper8/docs` orphan branch, plus two now-superseded commits earlier in `1.21.1`'s ancestry
(`e133c47`, `db02d29`).

## Known gap

Because `agent-ref/` has been gitignored on every code branch since 2026-06-23, any notes written
directly into a code branch's working tree (rather than through the dedicated `../RTF-docs`
worktree) and never committed are permanently unrecoverable from git. A confirmed instance of this
was the loss of an `rtf-tall-world-scaling-salvage-plan.md`, written for the now-deleted
`fix/tall-world-scaling` branch — there may be others with no trace in git history at all.

## `qa/` vs `fix/` convention (established 2026-07-27)

A prior QA branch for the biome-climate-banding investigation (`qa/biome-climate-distribution`) had
its worktree retired and its QA mixins stripped before the fix was ever committed — the mixin source
itself is gone; only its logged output was recovered into the successor worktree (see the
investigation doc). To avoid repeating that loss, this line of work now uses two branches instead of
one:

- `qa/<topic>` — the actual working branch. Both real fixes and QA/debug instrumentation (mixins,
  debug commands, scan harnesses) get committed here as work happens, instead of being written,
  used, and discarded uncommitted.
- `fix/<topic>` — forked from the qa branch once it contains only clean fix commits, with no QA
  scaffolding present. This is the ship/PR candidate. As the qa branch accumulates further work,
  replicate just the real fix commits onto the fix branch (cherry-pick or manual re-apply), not the
  QA additions.

`fix/` rather than `feat/` because this line of work corrects existing broken behavior rather than
adding new capability — `feat/` stays reserved for genuinely new features, matching its existing use
for `feat/configurable-ocean-depth` and friends.
