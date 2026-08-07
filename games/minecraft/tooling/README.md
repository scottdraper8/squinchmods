# Minecraft Tooling

Environment management and build utilities for Minecraft projects.

## Java Configuration

The [`.sdkmanrc`](.sdkmanrc) file specifies the required JDK version (`21.0.11-tem`).

### Automated Setup (SDKMAN)

If SDKMAN `auto-env` is enabled, the shell automatically switches to the specified JDK upon entering
the directory.

### Automated Setup (direnv)

A root-level `.envrc` is provided to automate environment loading for users with `direnv` installed.
This ensures that:

- Direct execution of `./gradlew` or other ecosystem tools respects the monorepo settings for JDK
  and shared caches.
- IDEs and editors correctly resolve the project environment.

To enable this:

```sh
direnv allow
```

## Shared Caches

The `env.sh` script configures a centralized cache root at
`\${XDG_CACHE_HOME:-\$HOME/.cache}/squinchmods`. This ensures that all Minecraft projects share
common artifacts, reducing disk usage and build times:

- **Gradle:** Wrapper distributions, dependencies, and Loom artifacts are stored in
  `GRADLE_USER_HOME`.
- **Package Managers:** npm, Yarn, pip, and uv caches are redirected to the shared root.

## Build Utilities

- **`build-mod [mod-name]`**: Compiles the specified mod located in `games/minecraft/mods/`.
- **`mc-source [version]`**: Downloads and decompiles the specified Minecraft version into
  `games/minecraft/reference/sources/<version>/official/`, alongside a `manifest.json` describing
  the extraction. There is no equivalent command for third-party mod source; clone a mod's own
  public repository directly into a `games/minecraft/reference/sources/<version>/mods/<mod-name>/`
  sibling when an investigation needs to read it — shallow (`--depth 1`) and sparse,
  delete-and-re-clone to update, never `fetch`/`pull` in place (see
  `.agent-docs/games/minecraft/README.md` for why and the exact commands).

**Note:** These tools automatically source `env.sh`. Functionality is maintained even if `direnv` or
manual shell initialization has not been performed.

## Live Investigation

Use the managed investigation package through the root dispatcher:

```sh
tooling/squinch mc-investigate --help
```

It accepts exact project/worktree paths, authenticates readiness through RCON, owns unique run
artifacts and worlds, validates process identities and descendants during teardown, and emits a
versioned JSON contract for agents. See [`investigate/README.md`](investigate/README.md) for
command, state, retention, and cleanup details. This remains distinct from `qa/`, which owns release
matrices and promotion.

## Manual Setup

If neither `direnv` nor automated shell hooks are used, the environment can be initialized manually:

```sh
source games/minecraft/tooling/env.sh
```
