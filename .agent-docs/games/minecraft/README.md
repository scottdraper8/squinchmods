# Minecraft workspace

Minecraft tooling in squinchmods builds mod submodules, runs local checks, manages development
servers for controlled investigations, and acquires catalogued third-party artifacts. Command
references live beside each tool:

- [`qa/README.md`](../../../games/minecraft/tooling/qa/README.md): local check profiles, plans,
  runs, world promotion, summaries, and cleanup.
- [`investigate/README.md`](../../../games/minecraft/tooling/investigate/README.md): managed server
  and client investigations.
- [`third-party/README.md`](../../../games/minecraft/tooling/third-party/README.md): runtime JAR and
  source acquisition.
- [`agentic-development-guide.md`](agentic-development-guide.md): the Minecraft investigation
  workflow and evidence handling.

## Layout

```text
games/minecraft/
  mods/<mod>/             Git submodule for each maintained mod
  tooling/
    env.sh                shared JDK and cache setup
    build-mod             build one mod submodule
    mc-source             extract vanilla source for inspection
    source-worker/        Gradle project used by mc-source
    qa/                   local check planner and runner
    investigate/          managed Minecraft server and client investigations
    third-party/          catalog-backed artifact and source acquisition
  investigations/        probes, fixtures, and controlled projects
  investigation-state/   generated investigation runs and worlds
  reference/             local vanilla and third-party source checkouts
  qa-state/               local check runs and promoted worlds

.squinch/
  config.yml                                      shared Minecraft check profiles
  schema/                                         check configuration schemas
  games/minecraft/mods/<mod>/config.yml           per-mod targets and check settings
  games/minecraft/mods/<mod>/scenarios/           mc-investigate scenarios
  games/minecraft/third-party/artifacts.toml      third-party artifact catalog
```

Use `tooling/squinch <tool>` from the repository root to reach the package CLIs. Local check and
investigation state is kept beneath the corresponding game-owned state directory.

## Local checks

`tooling/squinch qa` resolves a shared profile and a mod's target/check configuration, prints a
plan, and can execute its jobs against the mod submodule. The runner currently supports builds,
server smoke checks, pregeneration, and command-based server checks. Jobs run sequentially. A
successful run can promote generated worlds into `games/minecraft/qa-state/current/`; the CLI also
provides run summaries and cleanup.

Shared profiles are `quick`, `default`, and `extended`. Per-mod settings can select a complete check
list or add checks to an inherited profile, and can override check configuration. The operational
guide has the profile contents and exact command syntax.

## Investigations and artifacts

`mc-investigate` runs repository-defined scenarios against an explicitly selected project worktree.
It owns server or isolated-client startup and cleanup, records run inputs and outputs, and supports
structured probes, generation, comparisons, and artifact inspection. Scenario files are stored under
`.squinch/games/minecraft/mods/<mod>/scenarios/`; reusable probe projects and fixtures are under
`games/minecraft/investigations/`.

`third-party` uses `.squinch/games/minecraft/third-party/artifacts.toml` to acquire and verify
runtime artifacts. Its source command creates shallow, sparse checkouts for source review. The
acquisition guide documents catalog entries, cache paths, and commands.

## Reference material

The general Minecraft world-generation reference is [`wiki/README.md`](wiki/README.md). Mod-specific
engineering notes and active work plans live under `.agent-docs/games/minecraft/mods/<mod>/`.

`games/minecraft/reference/` holds local source material produced by `mc-source` and
`third-party ... source`. These checkouts are available for inspection by investigations and
developer tools.

## Development environment

`tooling/env.sh` sets the repository JDK from `tooling/.sdkmanrc` and redirects shared Gradle, npm,
yarn, pip, and uv caches under `$XDG_CACHE_HOME/squinchmods`. `games/minecraft/.envrc` loads the
same settings for direnv users. Local check targets select the Java version recorded in each mod
target.

Pre-commit formats and checks repository files and validates centralized `.squinch` configuration.
The `squinch-qa-pytest` pre-push hook runs the local Minecraft check-tool test suite.
