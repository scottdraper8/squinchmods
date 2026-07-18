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
  the extraction.

**Note:** These tools automatically source `env.sh`. Functionality is maintained even if `direnv` or
manual shell initialization has not been performed.

## Manual Setup

If neither `direnv` nor automated shell hooks are used, the environment can be initialized manually:

```sh
source games/minecraft/tooling/env.sh
```
