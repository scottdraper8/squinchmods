# Minecraft workspace

Minecraft tooling in squinchmods builds mod submodules, runs local checks, manages development
servers for controlled investigations, and acquires catalogued third-party artifacts. Command
references live beside each tool:

- [`qa/README.md`](../../../games/minecraft/tooling/qa/README.md): local check profiles, plans,
  runs, summaries, and tranche-owned outputs.
- [`investigate/README.md`](../../../games/minecraft/tooling/investigate/README.md): managed server
  and client investigations.
- [`third-party/README.md`](../../../games/minecraft/tooling/third-party/README.md): runtime JAR and
  source acquisition.
- [`agentic-development-guide.md`](agentic-development-guide.md): the Minecraft investigation
  workflow and scratch-state policy.

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
    investigate/          managed Minecraft server and client tooling
    third-party/          catalog-backed artifact and source acquisition
  investigations/        source integrations required by investigation tooling
  reference/             local vanilla and third-party source checkouts

.squinch/
  config.yml                                      shared Minecraft check profiles
  schema/                                         check configuration schemas
  games/minecraft/mods/<mod>/config.yml           per-mod targets and check settings
  games/minecraft/third-party/artifacts.toml      third-party artifact catalog
```

Use `tooling/squinch tranche create <id>` for each feature or fix, then
`tooling/squinch --tranche <id> <tool>` to reach game package CLIs. Local check and investigation
inputs and outputs use that tranche's workspace.

## Local checks

`tooling/squinch --tranche <id> qa` resolves a shared profile and a mod's target/check
configuration, prints a plan, and can execute its jobs against the mod submodule. The runner
supports builds, server smoke checks, pregeneration, command-based server checks, and run summaries.
Jobs run sequentially and all generated state stays in the tranche.

Shared profiles are `quick`, `default`, and `extended`. Per-mod settings can select a complete check
list or add checks to an inherited profile, and can override check configuration. The operational
guide has the profile contents and exact command syntax.

## Investigations and artifacts

`mc-investigate` runs task-local inputs against an explicitly selected project worktree. It owns
server or isolated-client startup and cleanup, records run inputs and outputs in scratch state, and
supports structured probes, generation, comparisons, and artifact inspection. FTF presets are
supplied as task-local preset inputs; exporter output is a generated datapack. FTF scenario, preset,
and probe-pack catalogs are not maintained in the repository. Long-lived behavior belongs in tests.

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
