# Local Minecraft checks

The `squinch qa` commands plan and run configured checks against Minecraft mod submodules. They
record plans, logs, built artifacts, results, and generated worlds under
`games/minecraft/qa-state/`.

## Setup

The dispatcher uses [uv](https://docs.astral.sh/uv/) to run this package:

```sh
tooling/squinch qa --help
```

For package development, install its dependencies from the tool directory:

```sh
cd games/minecraft/tooling/qa
uv sync
```

## Configuration

Shared check profiles and defaults are in `.squinch/config.yml`. Per-mod targets and check settings
are in `.squinch/games/minecraft/mods/<mod>/config.yml`; source projects remain in
`games/minecraft/mods/<mod>/`.

Each target identifies a Minecraft version, loader, loader version, and Java version. The shared
profiles are:

| Profile    | Checks                                   |
| ---------- | ---------------------------------------- |
| `quick`    | `build`, `server-smoke`                  |
| `default`  | `build`, `server-smoke`, `pregen`        |
| `extended` | Inherits `default`; allows a larger plan |

Mod configuration can add checks to a profile or supply its complete check list. Profile entries can
set check-specific values. Values merge in this order: shared check defaults, mod check settings,
then profile entry settings. Later values replace earlier values with the same key.

The current check IDs are `build`, `server-smoke`, `pregen`, `tick-freeze`, and `crafter-basic`. The
last two send configured commands to a test server and check for expected output. `max_jobs` limits
the number of target/check combinations in a profile. The shared configuration sets limits of 32 for
`default` and 64 for `extended`.

## Plan checks

`plan` prints deterministic JSON with the selected target/check jobs:

```sh
tooling/squinch qa plan redstone-backport --profile default
tooling/squinch qa plan FreeTerraForged --profile extended --target neoforge-1.21.1
tooling/squinch qa plan redstone-backport --profile default > plan.json
```

A plan contains the mod identity, resolved profile, and jobs. Each job includes its target metadata
and the resolved check configuration. Emitted jobs are sorted by target ID and then by profile check
order; `--target` selects one target.

The repository root is discovered by walking up to `.squinch/config.yml`. Set `SQUINCHMODS_ROOT` or
pass `--repo-root` to select it explicitly. A mod can be selected by its config directory name or
its `mod.id`.

## Run checks

```sh
tooling/squinch qa run redstone-backport --profile quick
tooling/squinch qa run redstone-backport --profile extended --target forge-1.20.1
tooling/squinch qa run FreeTerraForged --profile extended --promote
tooling/squinch qa run redstone-backport --plan plan.json --no-clean
```

The runner executes jobs sequentially. A run records a copy of the plan, a run manifest, an overall
result, and per-job manifests, results, logs, and artifacts. Check executors build the mod, launch a
test server, run a configured command check, or generate a world with a configured pregeneration
tool.

Pregeneration uses the configured tool preference (default: `chunksmith`, then `chunky`). Tool JARs
are cached below the Squinchmods cache directory. Set `SQINCHMODS_QA_OFFLINE=1` to use cached tools
only.

`--promote` promotes generated worlds from a passing run into `games/minecraft/qa-state/current/`.
The `promote` command can also select worlds from a completed run:

```sh
tooling/squinch qa promote --run-id <run-id> --dry-run
tooling/squinch qa promote --run-id <run-id> --target forge-1.20.1 --test pregen
```

Promotion validates the run and its artifacts before replacing the matching current world. Replaced
worlds are retained in `trash/`.

## Run records and cleanup

```text
games/minecraft/qa-state/
  runs/<run-id>/                         plans, results, logs, artifacts, generated worlds
  current/<mod>/<target>/<check>/        promoted worlds
  incoming/ and staging/                 promotion state
  trash/                                 replaced promoted worlds
```

`summary` renders a completed run from its saved result files:

```sh
tooling/squinch qa summary <run-id>
```

`clean` prunes old run records and retained replaced worlds. It applies cleanup by default; pass
`--dry-run` to preview it. Select states and retention limits with:

```sh
tooling/squinch qa clean --dry-run
tooling/squinch qa clean --runs --keep-runs 20 --max-run-age-days 30
tooling/squinch qa clean --trash --keep-trash 2
```

Runs also clean retained run and trash state after execution. Use `--no-clean` to keep those records
for inspection.

## Package checks

The Python package has a local test suite and a pre-push hook:

```sh
cd games/minecraft/tooling/qa
uv run --extra dev pytest
```
