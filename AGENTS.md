# Repository operating rules

## General

- Establish the truth from current source and reproducible runtime evidence. Correctness and
  completeness outrank speed or convenience.
- Within the authorized scope, continue until the task's acceptance criteria are met or a concrete
  blocker prevents safe progress. Do not treat elapsed time or an intermediate milestone as
  completion.
- Prefer the smallest correct design. Do not keep an unsound implementation merely to reduce the
  diff.
- Keep documentation current-state and forward-facing. Do not maintain a persistent investigation
  archive; put long-lived behavior in CI/CD tests and retain only inputs required by those tests or
  by generic tooling.
- Preserve unrelated dirty work.
- On context restoration, inspect current repository state and continue from completed artifacts
  rather than repeating finished work.

## Documentation and evidence

- For game- or mod-specific work, consult the relevant guide under `.agent-docs/games/<game>/` and
  follow the active plan, workflow, and evidence gates it identifies.
- Treat investigation inputs and outputs as task-local scratch. Remove raw observations, run
  artifacts, and reusable investigation recipes when the active work is complete.
- Keep commit hashes, artifact hashes, investigation run IDs, ephemeral counts, and run inventories
  out of `AGENTS.md` and routine routing notes.

## Task scratch tranches

- Create one scratch tranche for each feature or fix with `tooling/squinch tranche create <id>`.
  Select that tranche for game and QA tools with `tooling/squinch --tranche <id> ...` or
  `SQUINCH_TRANCHE=<id>`.
- Put task-local inputs below the path reported by `tooling/squinch tranche path <id>`. Repository
  tools place generated state in the same workspace. Source, maintained tests, generic tooling,
  shared download caches, shared source checkouts, and Gradle's shared cache stay outside it.
- Preview exact cleanup with `tooling/squinch tranche clean <id>` and apply it with
  `tooling/squinch tranche clean <id> --apply`. Cleanup targets one tranche across every game and
  removes its ownership metadata. Resolve incomplete teardown or modified external staging before
  applying cleanup.
