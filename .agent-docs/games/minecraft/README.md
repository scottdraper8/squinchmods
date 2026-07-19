# Minecraft

Architecture reference for how Minecraft modding is organized in squinchmods. For QA CLI usage, see
`games/minecraft/tooling/qa/README.md` (the operational reference); this doc is the conceptual one,
and shouldn't need to change every time a flag or field gets added.

## Layout

```text
games/minecraft/
  mods/<mod>/            git submodule per mod
  tooling/
    env.sh               shared JDK pin + monorepo cache-dir setup; sourced by every script below
    build-mod            `./gradlew build` for one mod, with env.sh bootstrapped
    mc-source             source-extraction script
    source-worker/        its own minimal Gradle wrapper, independent of any mod
    qa/                  the QA planner/runner (squinch-qa)
  reference/             gitignored: decompiled source, curated reference worlds
  qa-state/              gitignored: QA runtime state (generated per run)
```

Dispatched from the repo root via `tooling/squinch <tool>` (e.g. `tooling/squinch qa plan ...`), a
thin game-agnostic dispatcher that `exec`s into the target tool's own project directory. Root
`tooling/` was renamed from `tools/` to match this same `games/<game>/tooling/` convention.

## Root vs. per-game tooling boundary

Root-level tooling and config are meant to stay game-agnostic; anything that only makes sense for
one game belongs under that game's own directory instead (see root `.agent-docs/README.md`).
Minecraft is currently the only game with real tooling, which makes `squinch-qa` the easiest place
to wrongly assume something is already generic just because it's the only example that exists.

Looking at what's actually inside `squinch-qa`, the real seam isn't at the package boundary:

- Genuinely generic (no Minecraft assumptions in the logic itself): profile/`extends` resolution,
  capability `requires`/skip matching, matrix expansion, the plan JSON shape, the
  run/manifest/result artifact layout, the incoming→staging→current→trash promotion pipeline with
  atomic-completion sentinels, retention-based cleanup, remote-dispatch polling via `gh`.
- Genuinely Minecraft-specific: the `Target` schema's required fields (`minecraft`/`loader`/`java`),
  and every executor (`build` via `gradlew`, `server-smoke`, `command-script`, `pregen` via
  chunksmith/chunky, the Forge-production launcher) — all mod-loader/Gradle/server concepts baked
  into the executor layer.

`squinch-qa` stays under `games/minecraft/tooling/` rather than moving to root, deliberately, until
a second game actually needs matrix QA. Splitting it into a generic root engine plus a Minecraft
executor "plugin" now would mean guessing where the real boundary belongs; a second game's actual
requirements should draw that line, not speculation from a single data point. This mirrors the
existing note in root `.agent-docs/README.md` that `.squinch/`'s config _mechanism_ is game-agnostic
but its current _content_ (e.g. the target schema) is not.

## Adding new Minecraft tooling

New tools live as flat siblings under `games/minecraft/tooling/`, matching the existing
`build-mod`/`mc-source`/`qa/` pattern:

- Start as a plain script (sourcing `env.sh` for JDK/cache setup, like `build-mod` and `mc-source`
  do) if the scope is small; only graduate to a real package (`pyproject.toml`, `uv`-managed, like
  `qa/`) once it actually needs dependencies, tests, or a real CLI surface. Don't pre-build the
  package shape before the scope demands it.
- Name for what the tool actually is, not for an aspirational cross-game generality it doesn't have
  — `qa` already drifted this way (a generic-sounding name for a Minecraft-only tool), which is an
  accepted rough edge, not a pattern to repeat. Tooling for live-server/RCON investigation, for
  example, should read as investigation tooling, not as a generic `dev` verb.
- Give it a section in `games/minecraft/tooling/README.md` (the operational doc) once built; this
  file only needs the conceptual "how tools are organized" pattern, not a changelog of each one.

## QA system

`squinch-qa` is a data-driven QA planner and runner: given a mod and a profile, it works out which
(target, test) combinations to run, executes them, and records the result. It's built to run
identically locally or on GitHub Actions.

### Config

- **Parent config** (`.squinch/config.yml`): global defaults, including `profiles` (e.g. `dev`,
  `default`, `pre-pr`, `release`, each optionally `extends`-ing another) and shared test defaults.
- **Mod config** (`.squinch/games/minecraft/mods/<mod>/config.yml`, in squinchmods itself rather
  than inside the mod's own repo, so upstream-facing fork submodules never need squinchmods-specific
  files on a branch that might get PR'd upstream): the mod's `targets` (Minecraft version × loader ×
  Java, each with declared `capabilities`), plus optional profile overrides and test definitions.
  Mods are discovered dynamically by scanning this directory; adding a mod means adding a config
  file here, not touching tooling code.

A test declares which `capabilities` it needs (e.g. `server`, `command-script`); the planner skips
any (target, test) pair where the target doesn't have them, rather than erroring. A mod's profile
override can `add` tests to what the parent profile already lists, replace the list entirely, or
`extend` a different profile's resolved list, and that override automatically flows into any profile
that in turn extends it (a mod's `pre-pr` addition also applies when running `release`, since
`release` extends `pre-pr`).

Tests that differ by loader (e.g. a GameTest on Forge vs. a command-script on Fabric) declare
per-loader `adapters`; the resolved adapter for a job's actual loader is threaded through to
whichever executor runs that test, which can branch on it. Tests can also declare `expectations`
(default values, optionally overridden `by_target`) and mods can register `expected_failures` (with
a required reason and optional expiry); both are resolved per job and recorded in that job's report,
not just present in config.

### Flow

```text
plan    read parent + mod config, expand profile × targets, filter by capability → plan.json
run     execute each planned job (build / server-smoke / pregen / command-script executor)
        → per-job manifest.json + result.json, plus a run-level qa-manifest.json + result.json
promote validate the run's jobs, then atomically replace games/minecraft/qa-state/current/:
        all-or-nothing across the batch, one real failure blocks promoting any of it
summary render a human-readable report from a completed run's already-written files
```

Promotion never deletes on failure: incoming → staging → current happens through sentinel-gated
atomic swaps, with the previous `current/` entry moved to `trash/` rather than deleted, so a crash
mid-promotion is always recoverable.

### Storage

```text
games/minecraft/qa-state/
  runs/<run-id>/                     everything from one plan+run: plan, manifests, logs, worlds
  current/<mod-id>/<target>/<test>/  latest promoted output, durable until replaced
  incoming/, staging/                 transient promotion state, cleaned up by crash recovery
  trash/                             evicted current/ entries, pruned by retention policy
```

`qa-state/` avoids colliding with `tooling/qa/` (the planner/runner's own source, two directories up
in the layout above) — one is the tool, the other is everything it generates.

Keyed by canonical `mod.id`, not directory name, so two mods can't collide on the same target/test
path. `runs/` and `trash/` are pruned by `squinch qa clean`; `current/` is never touched by cleanup,
only by a new promotion.

### Remote QA

`squinch qa remote-run` dispatches a GitHub Actions workflow (`workflow_dispatch`), polls for
completion via the `gh` CLI, downloads the result artifact, and then runs it through the same
plan/manifest/promote path as a local run: there's no separate remote-specific data model. This is a
deliberate choice: dispatch-and-poll over `gh`, not a local daemon receiving uploads.

## Reference material

`games/minecraft/reference/` is gitignored, local-only, and split by content type:

```text
reference/
  sources/<version>/<mappings-type>/   decompiled vanilla source, e.g. sources/1.21.1/official/
    manifest.json                      schema, mappings type/version, tool, source jar sha256, generated_at
    src/                               extracted source tree (com/, net/, META-INF/)
  worlds/<name>/                       curated, durable reference worlds (not yet populated)
```

`mc-source <minecraft-version>` decompiles and extracts Minecraft's own source into
`sources/<version>/official/` (`official` names the mappings set — official Mojang mappings today;
the segment exists so a different mapping set could sit alongside it later without collision), using
a dedicated minimal Gradle wrapper (`tooling/source-worker/`) rather than depending on any
particular mod's build, and always writes a checksummed `manifest.json` alongside the extracted
`src/`. This is for local source inspection (understanding vanilla behavior to backport or reference
against); extracted sources are never committed.

`worlds/<name>/` is for curated, durable reference worlds kept around deliberately (e.g. a
hand-verified world worth comparing future runs against) — distinct from
`games/minecraft/qa-state/`'s `current/`, which holds the latest QA-promoted output and can be
overwritten by the next passing run at any time. Nothing populates `worlds/` yet; the layout above
is the intended shape once something does, so it doesn't need inventing from scratch later.

`reference/sources/1.20.1/official/` and `reference/sources/1.20.4/official/` don't have a
`manifest.json` yet; regenerate them via `mc-source` if that provenance is needed.

## Dev environment

`tooling/env.sh` centralizes JDK pinning (via SDKMAN, `tooling/.sdkmanrc`) and monorepo-shared cache
directories (Gradle/npm/yarn/pip/uv, all redirected under `$XDG_CACHE_HOME/squinchmods`). Every
script under `tooling/` (`build-mod`, `mc-source`) sources it explicitly, so they work regardless of
shell setup; `games/minecraft/.envrc` also sources it for direnv users, so plain `./gradlew` and IDE
tooling pick up the same JDK/caches without needing one of the wrapper scripts. QA execution itself
uses whatever Java version a target declares, which may differ from the tooling default.

Pre-commit covers shell/YAML linting and QA config schema validation, but deliberately never runs
actual QA (builds, server launches, pregen); that stays a manual or CI concern.

## Where mod-specific docs live

Per-mod investigation/design docs live under `.agent-docs/games/minecraft/mods/<mod>/`, not in this
file and not in the mod's own repo (see the root `.agent-docs/README.md` for why).
