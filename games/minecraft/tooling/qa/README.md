# Local Minecraft checks

The `squinch qa` package plans and runs configured checks against Minecraft mod worktrees. Its
profiles, planners, executors, artifact validation, and tests are maintained tooling. Every plan
execution, log, generated world, build directory, Gradle project cache, and server runtime is
task-local scratch inside the selected repository tranche.

## Setup and ownership

Use the root dispatcher and select one existing tranche:

```sh
tooling/squinch tranche create example-fix
tooling/squinch --tranche example-fix qa --help
```

The shared Gradle user home and downloaded pregeneration tools remain in the external Squinchmods
cache. They are shared dependencies and tranche cleanup does not remove them. QA source projects and
repository configuration also remain outside scratch ownership.

## Configuration

Shared check profiles and defaults are in `.squinch/config.yml`. Per-mod targets and check settings
are in `.squinch/games/minecraft/mods/<mod>/config.yml`; source projects remain in
`games/minecraft/mods/<mod>/`.

Each target identifies a Minecraft version, loader, loader version, and Java version. The current
check IDs are `build`, `server-smoke`, `pregen`, `tick-freeze`, and `crafter-basic`. Profile values
merge from shared check defaults, mod check settings, and then the profile entry. `max_jobs` bounds
the resulting target/check matrix.

## Plan and run checks

`plan` prints deterministic JSON:

```sh
tooling/squinch --tranche example-fix qa plan FreeTerraForged --profile extended
```

To edit or retain that JSON as a task input, write it below the tranche path:

```sh
workspace="$(tooling/squinch tranche path example-fix)"
mkdir -p "${workspace}/inputs"
tooling/squinch --tranche example-fix qa plan FreeTerraForged --profile extended \
  > "${workspace}/inputs/plan.json"
tooling/squinch --tranche example-fix qa run FreeTerraForged \
  --plan "${workspace}/inputs/plan.json"
```

The runner executes jobs sequentially. A run records its plan, manifest, result, logs, artifacts,
and generated worlds below `minecraft/qa/runs/<run-id>/` in the tranche. `summary` renders one run:

```sh
tooling/squinch --tranche example-fix qa summary <run-id>
```

Clean all QA and investigation scratch for the completed feature or fix through the repository
tranche command:

```sh
tooling/squinch tranche clean example-fix
tooling/squinch tranche clean example-fix --apply
```

## Package checks

```sh
uv run --project games/minecraft/tooling/qa --extra dev \
  pytest games/minecraft/tooling/qa/tests
```
