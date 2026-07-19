# ReTerraForged Branch Map

Snapshot as of the 2026-07-07 `agent-ref/` migration, updated 2026-07-18. Reflects `origin` branches
on `scottdraper8/ReTerraForged` — reverify before relying on it long-term.

## Active/code branches

| Branch                             | `agent-ref/` in `.gitignore`? | Notes                                                                                       |
| ---------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------- |
| `1.21.1`                           | Yes                           | Currently the commit squinchmods' submodule pointer is pinned to (via a tag on this branch) |
| `staging/1.21.1`                   | Yes                           |                                                                                             |
| `feat/configurable-ocean-depth`    | Yes                           | See `plans/ocean-depth/`                                                                    |
| `feat/configurable-shorelines`     | Yes                           | See `plans/shorelines/`                                                                     |
| `feat/configurable-strata`         | Yes                           | See `plans/strata/`                                                                         |
| `feat/mountain-region-variability` | Yes                           | See `plans/mountain-variability/`                                                           |
| `fixCarvingNearRivers`             | No                            | Predates the `agent-ref/` convention; no captured planning docs found                       |
| `fixOceanRivers`                   | No                            | Predates the convention; no captured planning docs found                                    |
| `unresolvedexperiments`            | No                            | Predates the convention; no captured planning docs found                                    |
| `vanity`                           | No                            | Predates the convention; no captured planning docs found                                    |
| `waterTableWorks`                  | No                            | Predates the convention; no captured planning docs found                                    |

## Retired: `fix/tall-world-scaling`

Deleted locally and on `origin` (`scottdraper8/ReTerraForged`) on 2026-07-18. Its closed PR (#90)
and both halves of its work (ocean floor depth, mountain height/shape) were already fully split into
`feat/configurable-ocean-depth` and `feat/mountain-region-variability` — neither branch was built by
merging the deleted branch's commits; both were rewritten from scratch after the tall-world approach
was judged not worth carrying forward. See `plans/tall-world-scaling/retrospective.md` for what
survived and what was deliberately discarded.

None of the "Yes" branches carry tracked content under `agent-ref/` at their tip — it's purely a
gitignore rule on all of them. All real committed planning content lived on the now-deleted
`scottdraper8/docs` orphan branch, plus two now-superseded commits earlier in `1.21.1`'s ancestry
(`e133c47`, `db02d29`).

## Known gap

Because `agent-ref/` has been gitignored on every code branch since 2026-06-23, any notes written
directly into a code branch's working tree (rather than through the dedicated `../RTF-docs`
worktree) and never committed are permanently unrecoverable from git. The
`rtf-tall-world-scaling-salvage-plan.md` case above is a confirmed instance of this, not theoretical
— there may be others with no trace in git history at all.
