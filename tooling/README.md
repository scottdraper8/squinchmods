# Monorepo Tooling

This repo keeps developer environment selection at the monorepo root so nested
projects do not each need their own shell setup.

## Java

The checked-in [`.sdkmanrc`](../.sdkmanrc) pins the default repo JVM to
`21.0.11-tem`.

With SDKMAN auto-env enabled, entering the repo will switch to that JDK
automatically.

```sh
sdk config
# set sdkman_auto_env=true
```

Without auto-env, run:

```sh
source tooling/activate.sh
```

## Shared Caches

[`activate.sh`](activate.sh) exports:

```sh
SQINCHMODS_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}/squinchmods"
GRADLE_USER_HOME="$SQINCHMODS_CACHE_HOME/gradle"
npm_config_cache="$SQINCHMODS_CACHE_HOME/npm"
YARN_CACHE_FOLDER="$SQINCHMODS_CACHE_HOME/yarn"
PIP_CACHE_DIR="$SQINCHMODS_CACHE_HOME/pip"
UV_CACHE_DIR="$SQINCHMODS_CACHE_HOME/uv"
```

That gives all nested projects in this monorepo one shared cache root for:

- Gradle wrapper distributions
- downloaded dependencies
- Loom and Minecraft artifacts
- Gradle toolchain downloads
- npm package tarballs and metadata
- Yarn cache data
- pip wheel/download cache
- uv package cache

This avoids repeated downloads across multiple mods in the repo while keeping
the cache outside the working tree.

### Why Gradle Is Enough For Minecraft

Minecraft jars, mappings, Loom artifacts, wrapper downloads, and Gradle-managed
toolchains all live under `GRADLE_USER_HOME`.

That means separate Minecraft mods inside this monorepo can reuse the same
downloaded inputs as long as they inherit the same repo environment.

### Deliberate Non-Goals

This setup does not override full toolchain homes such as `CARGO_HOME`,
`RUSTUP_HOME`, or `PNPM_HOME`.

Those locations often contain installed binaries and user-level state, not just
caches. If you want to centralize those too, do it intentionally per ecosystem
rather than by surprise from a generic repo activation script.

## Optional direnv

If `direnv` is installed later, the checked-in [`.envrc`](../.envrc) will load
the same environment automatically after:

```sh
direnv allow
```

## Daily Use

Without `direnv`, use:

```sh
source tooling/activate.sh
```

You can add that to a repo-specific shell alias or wrapper if you want zero
manual steps.
