# squinch-qa — Local QA Planner and Runner

`squinch-qa` reads the parent `.squinch/config.yml` and a mod's config under
`.squinch/games/minecraft/mods/<mod>/config.yml` (mod config lives centrally in squinchmods, not
inside the mod's own repo — see "Mod Config Location" below), applies CLI overrides, expands the
selected profile and targets, filters tests by target capabilities, enforces matrix limits, and
emits deterministic execution-plan JSON.

The runner reads that same plan shape and drives the actual Gradle/server/test invocations.

---

## Install / Setup

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
# From the qa tooling directory:
cd games/minecraft/tooling/qa
uv sync
```

This installs `squinch-qa` and its dependencies (PyYAML ≥ 6, jsonschema ≥ 4) into a local `.venv`.
The `tooling/squinch` dispatcher calls `uv run --project games/minecraft/tooling/qa` automatically,
so you do not need to activate the venv manually.

---

## Mod Config Location

Each Minecraft mod's QA config (targets, profiles, tests, expected failures) lives at:

```text
.squinch/games/minecraft/mods/<mod-dir-name>/config.yml
```

— inside squinchmods itself, **not** inside the mod's own submodule checkout. This is deliberate:
`redstone-backport` and `ReTerraForged` are both mod submodules, and `ReTerraForged` specifically is
a fork used for upstream contribution work, so it (and any future upstream-facing fork) should never
need squinchmods-specific files on a branch that might get PR'd upstream. Mods are discovered
dynamically by scanning `.squinch/games/minecraft/mods/*/config.yml` — adding a new mod means adding
a new config file here, not touching any tooling code.

The mod's actual source checkout (used for builds, server launches, git commit lookups) is at
`games/minecraft/mods/<mod-dir-name>/` — `load_mod_config` returns both the parsed config and that
source directory, and raises a clear error if the config exists but the source checkout doesn't
(e.g. an uninitialized submodule).

---

## CLI Usage

All commands are dispatched through `tooling/squinch`:

```sh
squinch qa plan <mod-slug> --profile <profile-name> [--target <target-id>] [--repo-root <path>]
```

`<mod-slug>` accepts **either** the filesystem directory name **or** the canonical `mod.id` from the
mod's config — both resolve to the same mod.

### Examples

```sh
# Plan all default-profile targets for redstone-backport:
squinch qa plan redstone-backport --profile default

# Plan ReTerraForged pre-pr profile, filtered to one target:
squinch qa plan ReTerraForged --profile pre-pr --target neoforge-1.21.1

# Using the mod.id form (case-insensitive):
squinch qa plan reterraforged --profile dev

# Explicit repo root (useful from any working directory):
squinch qa plan redstone-backport --profile default --repo-root /path/to/squinchmods
```

### `--repo-root` and `$SQUINCHMODS_ROOT`

If `--repo-root` is not supplied, the planner checks `$SQUINCHMODS_ROOT`. If that variable is also
unset, it walks up from the current working directory looking for `.squinch/config.yml` to locate
the repo root automatically.

---

## Exit Codes

| Code | Meaning                                                                                    |
| ---- | ------------------------------------------------------------------------------------------ |
| `0`  | Plan emitted successfully (stdout is the JSON)                                             |
| `1`  | CLI / lookup error: unknown mod, unknown profile, unknown target                           |
| `2`  | Config error: schema validation failure, missing extends target, cycle in extends chain    |
| `3`  | Matrix limit exceeded: `len(jobs) > max_jobs`; message includes both the count and the cap |

Skipped jobs (unsupported capability combinations) are **not** an error — they appear in the
`skipped` / `skipped_targets` arrays and the planner exits `0`.

---

## Plan JSON Shape (Phase 7 Input Contract)

The planner writes to stdout. Pipe or redirect as needed:

```sh
squinch qa plan redstone-backport --profile default > plan.json
```

Top-level shape (schema version 1):

```json
{
  "schema": 1,
  "mod": {
    "id": "redstone-backport",
    "display_name": "Redstone Backport"
  },
  "profile": {
    "name": "default",
    "resolved_from": ["default"],
    "max_parallel": 4,
    "max_jobs": 32
  },
  "jobs": [
    {
      "target": {
        "id": "forge-1.20.1",
        "minecraft": "1.20.1",
        "loader": "forge",
        "loader_version": "47.4.0",
        "java": 17,
        "capabilities": ["command-script", "gametest", "server", "worldgen"]
      },
      "test": {
        "id": "build",
        "required": true,
        "config": {},
        "expectations": {}
      },
      "adapter": null,
      "expected_failure": null
    }
  ],
  "skipped": [
    {
      "target_id": "fabric-1.20.1",
      "test_id": "tick-freeze-gametest",
      "reason": "test 'tick-freeze-gametest' requires capabilities ['gametest'] not provided by target 'fabric-1.20.1'"
    }
  ],
  "skipped_targets": []
}
```

### Field notes

- **`schema`**: always `1` for this phase. Phase 7 must reject unrecognised schema versions.
- **`jobs`**: sorted by `(target.id, test origin_index)` — profile order within a target is
  preserved, not re-sorted alphabetically.
- **`skipped` / `skipped_targets`**: sorted alphabetically by `(target_id, test_id)` — informational
  only, not executed.
- **`capabilities`** inside each target: sorted alphabetically.
- **`adapter`**: the test's `adapters.<target.loader>` entry from mod config, or `null` if the test
  declares no adapters (loader-agnostic) or (rarely) the mod hasn't declared one for this target's
  loader — the latter case is skipped during planning instead, so a job only ever carries a real
  adapter or `null`.
- **`test.expectations`**: `adapters.<test>.expectations.default` merged with
  `.by_target.<target.id>` (target-specific keys win). `{}` if the test declares no expectations.
  Carried through to each job's `manifest.json` after the run so target-specific overrides are
  visible in the report, not just in config.
- **Profile test-entry `config` overrides**: a mod profile can use explicit entries such as
  `{id: pregen, config: {preset: l}}` to override one profile's test config without changing the
  parent or mod-wide default. Merge order is parent test config, then mod test config, then profile
  test-entry config.
- **`expected_failure`**: `{reason, expires, expired}` from the mod's `expected_failures` list for
  this `(target, test)` pair, or `null`. An unexpired expected failure promotes a `fail` result to
  `expected_failure` in the manifest (see "Exit Codes" below) — expired ones do not, so a fixed bug
  can't hide behind a stale expectation.
- **No timestamps, run IDs, or absolute paths** in the plan — this keeps output byte-identical
  across machines and across repeated invocations (determinism requirement).
- The runner (Phase 7) adds `run_id`, artifact paths, and per-job results after execution.

### `max_parallel` and `max_jobs` defaults

If `max_parallel` is not set anywhere in the profile extends chain, it defaults to **1**
(sequential). If `max_jobs` is not set anywhere in the chain, it defaults to **256** as a sanity
cap. The `dev` profile (which declares neither) relies on these defaults.

---

## Running

### Runner CLI Usage

```sh
squinch qa run <mod-slug> --profile <profile-name> [--target <target-id>] [--repo-root <path>]
```

`<mod-slug>` resolves the same way as `squinch qa plan` — filesystem directory name or `mod.id`.

#### Runner Examples

```sh
# Run the dev profile (build + server-smoke) for redstone-backport:
squinch qa run redstone-backport --profile dev

# Run one target only:
squinch qa run redstone-backport --profile default --target forge-1.20.1

# Preview without executing (writes plan.json, exits before any executor runs):
squinch qa run redstone-backport --profile dev --dry-run
```

### QA Runtime Layout

Each invocation creates a timestamped directory under `games/minecraft/qa-state/runs/`:

```text
games/minecraft/qa-state/
└── runs/
    └── 1705320000000-a1b2c3d4/            ← run_id: unix-ms timestamp + random hex suffix
        ├── plan.json                      ← copy of the execution plan
        ├── qa-manifest.json               ← aggregate: repo commit, plan SHA, per-job refs
        ├── result.json                    ← roll-up: counts, duration, exit code
        └── jobs/
            └── forge-1.20.1/
                └── build/                 ← one directory per job (<target_id>/<test_id>)
                    ├── manifest.json      ← schema 1 — identity + outcome
                    ├── result.json        ← timings, logs, failure detail
                    ├── logs/
                    │   ├── gradle.stdout.log
                    │   └── gradle.stderr.log
                    └── artifacts/
                        └── mymod-1.0.0.jar
```

Promoted worlds live under `games/minecraft/qa-state/current/<mod-id>/<target-id>/<test-id>/`:

```text
games/minecraft/qa-state/current/
├── redstone-backport/
│   └── forge-1.20.1/
│       └── pregen/
│           ├── .ready
│           └── world/
└── reterraforged/
    └── neoforge-1.21.1/
        └── pregen/
            ├── .ready
            └── world/
```

The old root layout is legacy-only and should not be used by the active workflow:

```text
.qa-runs/
└── 1705320000000-a1b2c3d4/              ← run_id: unix-ms timestamp + random hex suffix
    ├── plan.json                          ← copy of the execution plan
    ├── qa-manifest.json                   ← aggregate: repo commit, plan SHA, per-job refs
    ├── result.json                        ← roll-up: counts, duration, exit code
    └── jobs/
        └── forge-1.20.1/
            └── build/                     ← one directory per job (<target_id>/<test_id>)
                ├── manifest.json          ← schema 1 — identity + outcome
                ├── result.json            ← timings, logs, failure detail
                ├── logs/
                │   ├── gradle.stdout.log
                │   └── gradle.stderr.log
                └── artifacts/
                    └── mymod-1.0.0.jar
```

Both `games/minecraft/qa-state/` and the legacy root `.qa-*` directories are gitignored at the repo
root so old local artifacts are not accidentally committed during migration cleanup.

`qa-state/` avoids colliding with `games/minecraft/tooling/qa/` (the planner/runner's own source) —
one is the tool, the other is everything the tool generates.

### Cleanup

QA cleanup is command-driven, with conservative automatic cleanup at the end of local and remote QA
runs. It only prunes generated `runs/` and `trash/` state:

```sh
python -m squinch_qa clean --dry-run
python -m squinch_qa clean --runs --keep-runs 20 --max-run-age-days 30
python -m squinch_qa clean --trash --keep-trash 2
```

Use `--no-clean` on `run` or `remote-run` to skip automatic post-run cleanup while investigating
retention behavior. Cleanup does not delete `current/`, `incoming/`, `staging/`, or
`games/minecraft/reference/`.

### Exit Codes (runner)

| Code | Meaning                                                  |
| ---- | -------------------------------------------------------- |
| `0`  | All required jobs passed or had active expected failures |
| `4`  | One or more required jobs failed or errored              |

Advisory jobs (`required: false`) never affect the exit code — their failures appear in the manifest
but do not trigger exit code 4.

### Summary

Every other command emits raw JSON (manifest/result files, or streamed JSON-lines events on stdout)
— nothing renders a human-readable view of a completed run. `summary` reads a run's already-written
`result.json`/`qa-manifest.json`/per-job files and prints one:

```sh
python -m squinch_qa summary <run-id>
```

```text
Run 1705320000000-a1b2c3d4 — redstone-backport (default)
Status: FAIL (exit 4)   Duration: 20.0s
error: 0  expected_failure: 1  fail: 1  pass: 2

  forge-1.20.1/build                       pass                   5.0s
  forge-1.20.1/server-smoke                pass                   5.0s
  forge-1.20.1/pregen                      fail                   5.0s  tool-timeout: chunksmith did not finish within 900s
  quilt-1.20.1/crafter-basic               expected_failure       5.0s  Quilt menu sync not implemented yet (expires 2026-08-01)
```

It is purely a read-only report over files a run already wrote — it does not execute or re-check
anything. Exit `0` on success, `6` if the run id resolves outside `qa_runs_dir` (path traversal),
`10` if the run's files are missing or malformed.

### Tool-Preference Behavior (pregen)

The `pregen` test reads `tool_preference` from `config` (parent default: `[chunksmith, chunky]`):

- **Chunksmith** is tried first. If acquisition from Modrinth fails (`AcquisitionError`), the next
  tool in the list is tried as a fallback.
- **If a tool jar is successfully placed but the tool errors during generation**, that is a test
  failure (`exit 4`) — no fallback is triggered.
- Tool jars are cached under `$XDG_CACHE_HOME/squinchmods/qa/pregen-tools/` or
  `$SQINCHMODS_CACHE_HOME/qa/pregen-tools/`.
- The cache is loader-scoped (`<tool>/<loader>/<version>/...`) and downloaded jars are inspected for
  real loader metadata before use. This prevents a Forge jar and a Fabric jar with the same upstream
  version/filename from colliding in cache.
- Quilt acquisition first asks Modrinth for a Quilt jar, then accepts a Fabric-compatible jar when
  no Quilt-specific release exists and the jar declares Fabric/Quilt metadata.

#### Offline mode

Set `SQINCHMODS_QA_OFFLINE=1` to prevent any network access. If a tool jar is not in the local
loader-scoped cache, the pregen test fails rather than attempting a download.

### Command-Script Behavior Tests

`tick-freeze` and `crafter-basic` use the generic command-script executor. The executor boots the
selected server target, sends `commands` from the resolved test config over stdin, and fails unless
each configured `expect_output` pattern appears in the server log in order.

Example config shape:

```yaml
tests:
  tick-freeze:
    requires: [server, command-script]
    adapters:
      forge:
        type: command-script
      fabric:
        type: command-script
    config:
      commands:
        - gamerule sendCommandFeedback true
        - tick freeze
        - tick query
      expect_output:
        - The game is frozen
      timeout_s: 300
```

Loader-specific adapter entries can override or add command-script config keys, so command
differences stay in central mod config instead of executor code. Tests that need new in-mod GameTest
classes, debug commands, or fixtures still require changes in the relevant mod submodule.

For Forge targets, command-script tests default to the production Forge server runtime. Gradle
userdev `runServer` is still available with `server_runtime: gradle-dev`, but it is not the default
for Forge command scripts because stdin does not reliably reach the Minecraft server console there.

---

## Running Tests

```sh
cd games/minecraft/tooling/qa
uv run --extra dev pytest
```

Run without slow (subprocess-heavy) tests:

```sh
uv run --extra dev pytest -m "not slow"
```

Or via the pre-push hook (see `.pre-commit-config.yaml`):

```sh
pre-commit run --hook-stage pre-push squinch-qa-pytest
```
