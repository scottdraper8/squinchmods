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

## Dev Server (Live Investigation)

`dev-server` starts/stops a headless mod dev server with RCON enabled, for ad hoc live investigation
(reproducing worldgen bugs, poking at a running world) — distinct from `qa/`, which is CI/CD matrix
testing. It's a standalone script (stdlib-only, no dependencies) rather than a managed package.

```sh
dev-server start <mod> --loader <fabric|forge|neoforge|quilt> [--seed N] [--datapack path.zip] \
  [--level-name name] [--fresh] [--server-properties key=value ...]
dev-server rcon <mod> --loader <loader> -- <command> [<command> ...]
dev-server stop <mod> --loader <loader>
```

`start` picks free server/RCON ports automatically (or accepts `--server-port`/`--rcon-port`),
writes `eula.txt` and `server.properties`, stages a datapack into `world/datapacks/` if given, waits
for the ready line, and records connection info in a state file (`.dev-server-state.json`) inside
the loader's run directory. `stop` reads that state, sends an RCON `stop`, falls back to killing the
process if needed, and checks whether the RCON/server ports are actually free afterward, warning
explicitly if they aren't.

Refuses to start over an existing world of the same `--level-name` unless `--fresh` is passed, so a
new seed/datapack never silently mixes with stale state. A state file left behind by a process
that's no longer running is detected and cleared automatically on the next `start`.

### Known limitations

- **`stop`'s port-still-bound warning does not mean the process actually got cleaned up — a manual
  kill is currently required.** Confirmed repeatedly (2026-07-19): Architectury's transformer
  wrapper spawns the real game process as a _child_, not the PID `dev-server` tracks, so `stop` can
  warn about a port still being bound while that real, heavy (200%+ CPU observed) process keeps
  running indefinitely. Workaround: `ss -ltnp | grep <port>` (the port `stop` warned about) to find
  the actual PID, then `kill -TERM` it, falling back to `-KILL` if it doesn't exit within a few
  seconds.
- **A `start` that times out waiting for "ready" can leave an entirely untracked process tree
  running, with no warning at all** — since no PID ever gets recorded for `stop` to later attempt
  cleaning up. After any `start` that reports a timeout or failure, check
  `ps aux | grep -i "KnotServer\|runServer"` explicitly before retrying or moving on — don't assume
  a failed attempt cleaned itself up.
- Neither is fixed yet; both require the workarounds above until `dev-server` itself is improved to
  track and kill the actual child process in both cases.

## Manual Setup

If neither `direnv` nor automated shell hooks are used, the environment can be initialized manually:

```sh
source games/minecraft/tooling/env.sh
```
