# Minecraft

Architecture reference for how Minecraft modding is organized in squinchmods. For QA CLI usage, see
`games/minecraft/tooling/qa/README.md` (the operational reference); this doc is the conceptual one,
and shouldn't need to change every time a flag or field gets added.

## Layout

```text
games/minecraft/
  mods/<mod>/            git submodule per mod
  tooling/
    qa/                  the QA planner/runner (squinch-qa)
    mc-source            source-extraction script
    source-worker/        its own minimal Gradle wrapper, independent of any mod
  reference/             gitignored: decompiled source, curated reference worlds
  qa/                    gitignored: QA runtime state (generated per run)
```

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
promote validate the run's jobs, then atomically replace games/minecraft/qa/current/:
        all-or-nothing across the batch, one real failure blocks promoting any of it
summary render a human-readable report from a completed run's already-written files
```

Promotion never deletes on failure: incoming → staging → current happens through sentinel-gated
atomic swaps, with the previous `current/` entry moved to `trash/` rather than deleted, so a crash
mid-promotion is always recoverable.

### Storage

```text
games/minecraft/qa/
  runs/<run-id>/                     everything from one plan+run: plan, manifests, logs, worlds
  current/<mod-id>/<target>/<test>/  latest promoted output, durable until replaced
  incoming/, staging/                 transient promotion state, cleaned up by crash recovery
  trash/                             evicted current/ entries, pruned by retention policy
```

Keyed by canonical `mod.id`, not directory name, so two mods can't collide on the same target/test
path. `runs/` and `trash/` are pruned by `squinch qa clean`; `current/` is never touched by cleanup,
only by a new promotion.

### Remote QA

`squinch qa remote-run` dispatches a GitHub Actions workflow (`workflow_dispatch`), polls for
completion via the `gh` CLI, downloads the result artifact, and then runs it through the same
plan/manifest/promote path as a local run: there's no separate remote-specific data model. This is a
deliberate choice: dispatch-and-poll over `gh`, not a local daemon receiving uploads.

## Source tooling

`mc-source <minecraft-version>` decompiles and extracts Minecraft's own source for that version into
`games/minecraft/reference/sources/<version>/`, using a dedicated minimal Gradle wrapper
(`tooling/source-worker/`) rather than depending on any particular mod's build. This is for local
source inspection (understanding vanilla behavior to backport or reference against); extracted
sources are gitignored, never committed.

`games/minecraft/reference/` can also hold curated, durable reference worlds, distinct from
`games/minecraft/qa/current/`, which holds the latest QA-promoted output and can be overwritten by
the next passing run at any time.

## Dev environment

Java is managed via SDKMAN (`tooling/.sdkmanrc`); QA execution uses whatever Java version a target
declares, which may differ from the tooling default. Pre-commit covers shell/YAML linting and QA
config schema validation, but deliberately never runs actual QA (builds, server launches, pregen);
that stays a manual or CI concern.

## Where mod-specific docs live

Per-mod investigation/design docs live under `.agent-docs/games/minecraft/mods/<mod>/`, not in this
file and not in the mod's own repo (see the root `.agent-docs/README.md` for why).
