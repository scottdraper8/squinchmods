# ReTerraForged Branch Map

Snapshot as of the 2026-07-07 `agent-ref/` migration. Reflects `origin` branches on
`scottdraper8/ReTerraForged` at that time — reverify before relying on it long-term.

## Active/code branches

| Branch                             | `agent-ref/` in `.gitignore`? | Notes                                                                                       |
| ---------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------- |
| `1.21.1`                           | Yes                           | Currently the commit squinchmods' submodule pointer is pinned to (via a tag on this branch) |
| `staging/1.21.1`                   | Yes                           |                                                                                             |
| `feat/configurable-ocean-depth`    | Yes                           | See `plans/ocean-depth/`                                                                    |
| `feat/configurable-shorelines`     | Yes                           | See `plans/shorelines/`                                                                     |
| `feat/configurable-strata`         | Yes                           | See `plans/strata/`                                                                         |
| `feat/mountain-region-variability` | Yes                           | See `plans/mountain-variability/`                                                           |
| `fix/tall-world-scaling`           | Yes                           | See `plans/tall-world-scaling/`                                                             |
| `fixCarvingNearRivers`             | No                            | Predates the `agent-ref/` convention; no captured planning docs found                       |
| `fixOceanRivers`                   | No                            | Predates the convention; no captured planning docs found                                    |
| `unresolvedexperiments`            | No                            | Predates the convention; no captured planning docs found                                    |
| `vanity`                           | No                            | Predates the convention; no captured planning docs found                                    |
| `waterTableWorks`                  | No                            | Predates the convention; no captured planning docs found                                    |

None of the "Yes" branches carry tracked content under `agent-ref/` at their tip — it's purely a
gitignore rule on all of them. All real committed planning content lived on the `scottdraper8/docs`
orphan branch (see below) plus two now-superseded commits earlier in `1.21.1`'s ancestry (`e133c47`,
`db02d29`).

## Retired: `scottdraper8/docs` orphan branch

An orphan branch (`ba425d8` "Add agent reference docs", `c959a2a` "Document docs branch workflow",
both 2026-06-28) that tracked `agent-ref/` content independent of the code branches, edited via a
separate `git worktree add ../RTF-docs scottdraper8/docs` checkout.

All 11 documents on this branch were migrated into `plans/` and `refs/` in this folder on
2026-07-07. One additional file, `rtf-world-height-cutoff-runtime-findings.md`, was recovered from
earlier history (`db02d29^`) and migrated alongside it even though it never made it onto this
branch. See `plans/tall-world-scaling/world-height-cutoff-investigation.md` for a note about one
referenced-but-unrecoverable file (`rtf-tall-world-scaling-salvage-plan.md`) that was lost before
ever being committed.

This branch can be safely deleted once this migration is verified — nothing in the code branches'
build or CI depends on it. Deletion is a destructive, GitHub-visible action; confirm with the repo
owner before deleting rather than doing it automatically as part of any tooling.

## Known gap

Because `agent-ref/` has been gitignored on every code branch since 2026-06-23, any notes written
directly into a code branch's working tree (rather than through the dedicated `../RTF-docs`
worktree) and never committed are permanently unrecoverable from git. The
`rtf-tall-world-scaling-salvage-plan.md` case above is a confirmed instance of this, not theoretical
— there may be others with no trace in git history at all.
