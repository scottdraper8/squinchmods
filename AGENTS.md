# Repository operating rules

## General

- Establish the truth from current source and reproducible runtime evidence. Correctness and
  completeness outrank speed or convenience.
- Within the authorized scope, continue until the task's acceptance criteria are met or a concrete
  blocker prevents safe progress. Do not treat elapsed time or an intermediate milestone as
  completion.
- Prefer the smallest correct design. Do not keep an unsound implementation merely to reduce the
  diff.
- Keep documentation current-state and forward-facing. Retain raw observations as evidence and put
  durable conclusions in focused references or plans.
- Preserve unrelated dirty work.
- On context restoration, inspect current repository state and continue from completed artifacts
  rather than repeating finished work.

## Documentation and evidence

- For game- or mod-specific work, consult the relevant guide under `.agent-docs/games/<game>/` and
  follow the active plan, workflow, and evidence gates it identifies.
- Keep investigation conclusions in focused references or plans, and retain raw observations as
  artifacts.
- Keep commit hashes, artifact hashes, investigation run IDs, ephemeral counts, and run inventories
  out of `AGENTS.md` and routine routing notes unless an exact identifier is needed to disambiguate
  the live target. Link to the focused evidence record instead.
