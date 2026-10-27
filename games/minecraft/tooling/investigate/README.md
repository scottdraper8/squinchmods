# Minecraft Investigation Tooling

This package manages local Minecraft server and client sessions for controlled development
investigations.

Use the repository dispatcher from any working directory and always name the exact target worktree:

```bash
tooling/squinch mc-investigate run \
  --project games/minecraft/mods/FreeTerraForged \
  --loader fabric \
  --seed 12345 \
  --command list
```

The public commands are `start`, `stop`, `status`, `doctor`, `command`, `run`, `client`, `scenario`,
`benchmark`, `generate`, `probe`, `compare`, `inspect-artifact`, `cell-scan`, `preset-export`, and
`clean`. Add `--json` to any command for the committed `schemas/cli-output-v1.json` envelope.
`cell-scan`, `preset-export`, and the `ftf_preset` scenario field are FTF adapters; lifecycle
workflows otherwise target any compatible project. Inputs are supplied for the active task, not from
a persistent FTF catalog. The states `starting`, `running`, and `stopping` are non-terminal; `ready`
means RCON authentication succeeded; `succeeded`, `failed`, `inconclusive`, and `error` are terminal
outcomes; `inactive` means no service is tracked; and `degraded` or `unknown` requires diagnosis
rather than an assumption of success.

Run a scenario supplied for the current investigation. Scenario files and target projects are
otherwise independent. Every repository-owned project, datapack, preset, patch, and probe path is
repository-root-relative (`games/minecraft/...`) and resolved from the repository root rather than
the caller's directory:

```bash
tooling/squinch mc-investigate scenario "$SCENARIO_FILE" --json
```

Scenario schema version 1 requires an exact seed and ordered steps. It supports command, generation,
and selected-probe steps; multiple datapacks; server properties; startup/step/shutdown timeouts;
retention; required runtime mods; managed `[[runtime_files]]` inputs copied from repository-relative
sources to targets below the loader's `config/` directory; managed `runtime_absent_files` paths for
first-start behavior; and response/region/terminal expectations. Managed files are fingerprinted
where applicable, backed up, installed or removed before launch, and restored on every cleanup path.
A generation step has `generation` authority unless it names a selected terminal probe and
explicitly requests `finished-chunk` authority. Force-load acknowledgment alone is never labeled
finished-chunk proof. Each `companion_artifacts` entry is a catalog root: its transitive
`required_dependencies` closure is validated, deduplicated, conflict-checked, and staged in
dependency-first order. Do not manually flatten a mod's dependency list into every scenario. Set
`launch_task = "prodServer"` to execute production-mapped Fabric/NeoForge code. For Fabric revision
comparisons, the probe overlay supplies the standard Loom production-server task when an older clean
revision does not declare one, while preserving an existing project-owned task.

A command step can own an asynchronous measurement by setting `wait_for_log`, `fail_on_log`, and
`capture_files`. The runner snapshots output files before issuing RCON commands, accepts only files
that changed during that command, waits for stable output plus the command-owned completion marker,
copies the files into task-local run state before shutdown, and rejects configured failure markers.
`[[steps.metrics]]` entries extract typed `int`, `float`, or `string` values from either the new
server-log range or a captured text file. This keeps workload-specific commands and report formats
in task-local scenario data instead of adding them to the generic lifecycle manager.

Packaged-subject scenarios may set `subject_artifact` to a repository-relative production JAR. The
runner hashes it, installs it as an owned runtime companion, records the materialized path, and
removes it during cleanup. When Fabric's production JAR is intermediary-mapped, pair it with a
matching Mojang-named `subject_compile_artifact`; probes compile against that independently hashed
view while the server executes only `subject_artifact`. Runtime companions are never implicit
compile inputs. `probe_compile_artifacts` may explicitly select catalog artifacts with an explicit
loader and `named` or `loader` mapping when a probe needs an optional mechanism API that is not
already on the subject project's compile classpath. These compile inputs are never copied to the
runtime unless they are also listed in `companion_artifacts`. This boundary is intended for
independent packaged-JAR harnesses, not as a substitute for source-worktree provenance.

Run world-creation UI probes through the isolated client lifecycle, never a personal launcher
profile or the project's ordinary run directory. This example uses a probe pack and artifact
supplied for the current investigation; the client lifecycle itself is generic:

```bash
tooling/squinch mc-investigate client \
  --project "$PROJECT" \
  --loader fabric \
  --probe-pack "$PROBE_PACK" \
  --artifact "$ARTIFACT_ID" \
  --runtime-file "$INPUT_FILE=config/example.toml" \
  --probe-env "SQUINCH_CASE=$CASE" \
  --result-env SQUINCH_RESULT=result.json \
  --production \
  --cpu-list 16-31 \
  --json
```

The command owns a run-local client directory, runtime mods, result files, headless Wayland runtime,
and systemd service/cgroup. Each `--compile-artifact ID:LOADER:MAPPING` is compile-only. Each
`--artifact ID` is a runtime root whose transitive catalog `required_dependencies` are validated,
deduplicated, conflict-checked, and staged dependency-first. Probe and result environment names must
start with `SQUINCH_`, and each `--runtime-file SOURCE=config/TARGET` is copied into the isolated
run before launch and hashed in the manifest. Runtime-file targets cannot escape the run's `config`
directory. During execution, crash reports, structured fail results, successful completion of all
required results, and termination of the inner client application are terminal signals independent
of the longer-lived display and build wrappers. Every required result must be a JSON object whose
`status` is `pass`. Cleanup is part of success and a surviving owned process retains recoverable
active state.

`--production` packages the subject and probe and launches them in a production-mapped client, which
is required when an exact third-party artifact targets production names or synthetic loader methods
that are absent from the Gradle development runtime. Fabric and NeoForge use separate owned launch
paths; NeoForge installs the requested project version into the investigation cache and resolves
metadata-pinned Mojang libraries without using launcher accounts or profiles. `--cpu-list`
constrains the entire owned service to an explicit processor set. A result whose probe-level status
is `fail` may still be a completed behavior-bearing falsification artifact; callers must distinguish
an asserted behavioral mismatch from launch failure and still require complete cleanup.

For an isolated generation benchmark, use task-local scenario inputs with disjoint coordinate
windows and release generated chunks between observations. A scenario can record per-observation
timings and an optional `.jfr` profile in run scratch state. Remove benchmark inputs and outputs
when the active work is complete. Lifecycle timing separates startup, world-open, save, shutdown,
and cleanup from generation.

Run repeated or multi-stack measurements through a task-local benchmark matrix rather than a shell
loop. The matrix runner and schema are workload-agnostic:

```bash
tooling/squinch mc-investigate benchmark \
  "$BENCHMARK_FILE" \
  --json
```

A schema-version-1 task-local matrix references one base scenario and declares catalog-root
variants, required runtime mod IDs, optional asserted `startup_failure` outcomes, repetitions,
retention, failure policy, and execution order. Scenario and variant artifact IDs are always
expanded through the catalog's transitive `required_dependencies` closure before staging;
`required_mods` can assert every resulting runtime mod ID rather than only the top-level mods.
`round-robin` preserves declaration order, `shuffled` randomizes each repetition from the recorded
seed, and `bracketed` runs a named control before and after a randomized treatment block.
`paired-bracketed` assigns every variant a `comparison_group` and `pair_id`, brackets every group
with its own control pair, randomizes treatment-pair order, and keeps each pair's group members
adjacent while randomizing their order. A variant may override the base scenario's `loader`, which
allows one matrix to compare equivalent Fabric and NeoForge stacks. Before each scenario, the
generic runner can require a continuously quiet host window using normalized load, available memory,
swap usage, and no swap I/O. Every run remains a normal independently owned scenario with verified
teardown. Each scenario and matrix record also carries bounded log diagnostics: WARN, ERROR, FATAL,
and exception-line counts plus the 20 most frequent messages in each category. The matrix scratch
state contains its immutable plan, matrix and base-scenario hashes, per-run records, host snapshots,
scenario artifact links, extracted metrics, per-variant aggregates, and paired metrics normalized to
the mean of each group's start/end controls in the same repetition. A cleanup failure always stops
the matrix.

Benchmark campaigns are checkpointed rather than restarted. Every attempt is appended beneath the
campaign's `attempts/` directory. A successful scenario with verified cleanup becomes an accepted
checkpoint in `runs/` with a separate SHA-256 sidecar; accepted checkpoints are immutable and are
never retried. Lifecycle-invalid attempts (`cleanup_failed`, `already_active`, `recovery_required`,
`host_degraded`, `host_not_quiet`, or a changed campaign input) remain in the attempt ledger but are
classified as retryable, excluded from aggregates, and retried after recovery. Other scenario
failures are classified as rejected samples and are retried only when the caller explicitly uses
`--retry-failed`.

Invoking the same matrix without `--resume` automatically resumes the unique matching incomplete
campaign. It refuses ambiguous campaigns, refuses to silently repeat an already completed campaign,
and refuses to mix records after the matrix, base scenario, source worktree, catalog, or external
input fingerprints change. `--new-campaign` is the explicit escape hatch for deliberately starting
over. `--max-new-runs` limits new attempts without changing any accepted checkpoints:

```bash
tooling/squinch mc-investigate benchmark path/to/matrix.toml --max-new-runs 16 --json
# The same command auto-resumes the matching campaign.
tooling/squinch mc-investigate benchmark path/to/matrix.toml --max-new-runs 16 --json
# Retry an unexpected rejected sample after diagnosis.
tooling/squinch mc-investigate benchmark path/to/matrix.toml --retry-failed --json
# An exact ID is available when multiple incomplete task campaigns need disambiguation.
tooling/squinch mc-investigate benchmark path/to/matrix.toml --resume RUN_ID --json
```

Matrix inputs and campaign state are scratch for the active comparison. Remove them when its
analysis is complete; do not keep campaigns as a historical archive.

Normal run cleanup treats scenario runs referenced by accepted benchmark checkpoints as protected,
even if an age or project selector would otherwise match them. Deleting a benchmark that owns
accepted checkpoints requires the explicit `clean --benchmark RUN_ID --discard-checkpoints --apply`
combination. Rejected and superseded attempt runs are not checkpoint-protected and can be removed by
normal owned cleanup after they are no longer active; compact attempt records remain only in the
task's benchmark scratch state.

Matrix runtime state lives below the investigation cache's `benchmarks/` directory. Workload
adapters remain task-local scenarios, so the matrix runner contains no mod-specific command or
report knowledge. Remove the matrix and its scratch results when the active comparison is complete.

Use a task-local scenario with `scenario` or pass it to exact `compare` as shown below. Exact
comparisons hold a global lock and run the two sides sequentially, preventing before/after benchmark
overlap by default. Timing and profile metadata are excluded from behavioral equality.

Run an exact before/after comparison with full commit SHAs and one task-local scenario:

```bash
tooling/squinch mc-investigate compare \
  --project "$PROJECT" \
  --before "$BEFORE_SHA" \
  --after "$AFTER_SHA" \
  --scenario "$SCENARIO_FILE" \
  --expect different --json
```

The command creates two detached worktrees under `investigation-state/worktrees/`, runs them
sequentially, and requires identical scenario-input and injected-probe fingerprints. It removes
request IDs, timestamps, polling/timing fields, and placement CPU time from behavioral equality;
list order and all remaining numbers stay exact. The comparison output includes both normalized
sides, recursive field-level differences, exact commit/tree identities, and code, environment,
input, probe, and timing fingerprints. Clean temporary worktrees are removed in `finally`. A failed
side or an unexpectedly modified worktree is left in task-local scratch state and reported rather
than force-removed. Remove that state after the issue is resolved. Existing result files can still
be compared with `compare --left FILE --right FILE`.

For exact worktrees that use the standard Gradle wrapper, `compare` preflights its bootstrap inputs
before launching either side and reports a sparse checkout that omits `gradlew` or required wrapper
properties. If a worktree has wrapper properties but omits its ignored `gradle-wrapper.jar`, the
runner stages the regular JAR from the selected project into that worktree, fingerprints it in the
comparison summary, and removes it on clean teardown. When both revisions use the wrapper, their JAR
hashes must match. If no valid source exists, the comparison fails before running Minecraft with a
specific bootstrap error.

## FTF adapters and terminology

FTF preset input is supplied for the active task. The `preset-export` command passes it to FTF's
real exporter and produces a generated datapack in run scratch state. The scenario field
`ftf_preset` also names a task-local preset input. No preset catalog is maintained.

`cell-scan` runs the selected worktree's compiled FTF model without starting a server or generating
Minecraft chunks. Preview output has prediction authority; tile mode checks the horizontal tile
model. Neither result establishes final block placement. Use command help for the current scan
options and remove its input and output when the active work is complete.

The probe runtime is injected into development runs by an external Gradle init overlay. It adds no
tracked target source or resources. Requests appear atomically under
`<loader>/run/.squinch-investigate/requests/`; the runtime claims them on the Minecraft server
thread and atomically publishes JSONL transcripts under `results/`. Every transcript record carries
the run, request, probe, and probe-version identity, and exactly one final record has terminal state
`pass`, `fail`, `inconclusive`, or `error`. A terminal also records its observation phase and
inspected/skipped/completeness counts. Logs remain diagnostics; the structured terminal is the
authority used by the CLI and scenario runner.

Before publishing a normal production build, inspect its exact JAR path. The command hashes and
opens every JAR, then rejects the development sentinel, injected probe classes, the probe Mixin
configuration, or generated loader-metadata references to that configuration:

```bash
tooling/squinch mc-investigate inspect-artifact \
  "$ARTIFACT_JAR" \
  --json
```

The built-in runtime (`probe-runtime/src/main/java/org/squinchmods/investigate/BuiltinProbes.java`)
registers a handful of probes by ID/version, callable directly through
`probe --probe-id <id> --probe-version <version> [--config path.json]` or from a scenario's
`[[probe]]` table:

- `squinch:finished-chunks` (config: `bounds`, `unit`, `max_wait_ticks`) — waits for every requested
  chunk to reach real `LevelChunk` status; the finished-chunk generation authority used by
  scenarios.
- `squinch:finished-chunk-palette` (config: `bounds`, `unit`, `sample_heightmap`, `sample_step`,
  `max_wait_ticks`, `top_k`, `example_limit`, and `predicates`) — the generic finished-chunk surface
  scanner. It reports deterministic block, biome, and height histograms plus height extrema and
  predicate matches/examples. Predicates may select `block_ids`, `biome_ids`, `min_height`, and
  `max_height`; omitted fields are unconstrained. `pass` only if every chunk became a real
  `LevelChunk` in time; otherwise it is `inconclusive` with bounded `not_ready_examples` and honest
  completeness. The legacy `top_block_ids` and `top_biome_ids` result aliases remain for consumers
  of the original example probe.
- `squinch:runtime-smoke`, `squinch:partial-control`, `squinch:exception-control`,
  `squinch:isolation-control`, and `squinch:stop-flush-control` are protocol negative/positive
  controls, not investigation probes; see `BuiltinProbes.java` for their exact behavior.

Each scenario manifest fingerprints the scenario, Git HEAD and dirty patch, untracked inputs,
datapacks, Java, Gradle wrapper/build inputs, loader, JVM environment arguments, launch command, and
the runtime mod list parsed from the real loader log. Startup verifies the actual seed and owned
world before steps run. A crash, fatal server condition, timeout, assertion failure, missing or
non-passing probe terminal result, incomplete scan, or cleanup failure makes the command nonzero.

Generated state lives beneath `games/minecraft/investigation-state/` and is ignored by Git. Every
run owns a unique ID, artifact directory, log, manifest, command stream, summary, and level name.
This is task-local scratch, not a persistent archive; remove completed run state after the active
work is done. Target `eula.txt` and `server.properties` files are backed up and restored. The
launcher invokes a non-executable wrapper as `bash ./gradlew`, uses `env.sh`, disables reusable
Gradle daemons for the launch command, and never changes the wrapper's tracked mode.

Every launch runs as a dedicated transient user-systemd service with control-group kill semantics.
The exact unit intent is published as recoverable `launching` state before `systemd-run` is spawned,
wrapper identity enriches that owner immediately after spawn, and main-process discovery then
advances it in place. While the service is active, the runner retains identity snapshots for its
cgroup thread IDs as well as process identities. Teardown and `status`/`doctor` verify those exact
thread identities, so a surviving D-state thread is not mistaken for a clean exit merely because its
leader or service cgroup disappeared. `status` also degrades when the tracked main-process identity
or service-cgroup membership is missing, even if listeners remain bound. Incomplete thread capture
or a still-blocked owned thread keeps recovery active; the tool never signals thread IDs. `stop`
also enumerates that service's complete cgroup, validates retained Linux process identities before
fallback signaling, removes only force-load regions recorded by the run, and treats any remaining
process/listener/file/world cleanup problem as failure. `doctor --recover` is the explicit recovery
path for retained incomplete state. Launch preparation is transactional, and every blocking stop
phase consumes the same monotonic timeout budget; the timeout is not restarted for each phase.
Choose a timeout that includes launch/transformation, the probe, normal shutdown, and fallback
cleanup; a short diagnostic timeout can expire before cleanup has any remaining budget.

`clean` is a dry run unless `--apply` is supplied. It accepts exact `--run` IDs or an explicit
`--older-than-days` selection and rejects active runs, symlinks, foreign manifests, or paths outside
the owned state root. The repository's `protected_runs` list in
`.squinch/games/minecraft/investigation-retention.toml` is empty. Cleanup deletes directly after
validation; there is no speculative trash layer.

## Verification and test policy

Use source checks and focused tests first. During active development, managed Minecraft runs can
verify loader startup, datapack and registry loading, generation hooks, finished chunks, and client
behavior at the real game boundary. Those checks use task-local inputs and scratch outputs; remove
scenarios, probe packs, presets, logs, profiles, screenshots, and measurements when the work is
done.

Put stable, repeatable behavior in CI/CD tests. Keep investigation recipes and raw results out of
the repository unless a source or test input is required by CI or the generic tooling.

### Useful automated test boundaries

- CLI JSON schema and command state transitions.
- Scenario parsing, path confinement, managed-file restoration, and input validation.
- Coordinate tiling, atomic writes, process identity, teardown, and RCON framing.
- Manifest hashing, preset export output, worktree lifecycle, and production artifact exclusion.

Tests should assert behavior at the lowest real boundary needed to catch the defect. Avoid duplicate
implementations, mock-only assertions, timing thresholds on shared machines, and simulated Minecraft
integration that could pass while the real loader or world generation fails.

### Verification ladder

Use the cheapest layer that can genuinely falsify the claim, then cross the real boundary needed for
completion:

1. Source inspection and deterministic tests.
2. Filesystem, socket, subprocess, Git worktree, and artifact checks.
3. A mod-specific prediction or standalone model, when available.
4. A managed Minecraft run for loader, registry, chunk, block, structure, or feature behavior.
5. Client visual review for player-facing claims.

A lower layer does not establish a higher one. In particular, an FTF cell scan does not establish
final block placement, and a mocked server does not establish real process teardown or loader
behavior.
