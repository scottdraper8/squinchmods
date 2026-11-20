# Minecraft Investigation Tooling

This package manages local Minecraft server/client sessions and task-local checks. Development probe
overlays target compatible Fabric/NeoForge mod worktrees; `packaged-runtime` instead accepts
externally assembled, exact prebuilt Fabric/Forge/NeoForge/Quilt runtimes without compiling or
injecting instrumentation. Core lifecycle, scenario, probe, benchmark, and exact-comparison features
are project-agnostic. FTF adapters provide preset export and standalone cell scanning.

Use the repository dispatcher from any working directory, select an existing task tranche, and
always name the exact target worktree. Generated runs, Gradle build and project state, worlds,
worktrees, comparisons, and benchmarks live below that tranche's `minecraft/investigate/` root.

```bash
tooling/squinch tranche create example-fix
export SQUINCH_TRANCHE=example-fix
tooling/squinch mc-investigate run \
  --project "$PROJECT" \
  --loader fabric \
  --seed "$SEED" \
  --command list
```

The public commands are `start`, `stop`, `status`, `doctor`, `command`, `run`, `client`, `scenario`,
`packaged-runtime`, `benchmark`, `generate`, `probe`, `compare`, `inspect-artifact`, `cell-scan`,
and `preset-export`. Add `--json` to any command for the committed `schemas/cli-output-v1.json`
envelope. `cell-scan`, `preset-export`, and the `ftf_preset` scenario field are FTF adapters;
lifecycle workflows otherwise target any compatible project. Inputs are supplied for the active
task, not from a persistent FTF catalog. The states `starting`, `running`, and `stopping` are
non-terminal; `ready` means RCON authentication succeeded; `succeeded`, `failed`, `inconclusive`,
and `error` are terminal outcomes; `inactive` means no service is tracked; and `degraded` or
`unknown` requires diagnosis rather than an assumption of success.

Run a scenario supplied for the current investigation. The target project and optional source
project use repository-root-relative `games/minecraft/...` paths. Datapacks, presets, runtime-file
sources, probe packs, probe configurations, candidate files, and packaged subject artifacts use
paths relative to the scenario file, which keeps those inputs inside the selected tranche:

```bash
tooling/squinch mc-investigate scenario "$SCENARIO_FILE" --json
```

Scenario schema version 1 requires an exact seed and ordered steps. It supports command, generation,
and selected-probe steps; multiple datapacks; server properties; startup/step/shutdown timeouts;
retention; required runtime mods; managed `[[runtime_files]]` inputs copied from scenario-relative
sources to targets below the owned server run's `config/` directory; managed `runtime_absent_files`
paths for first-start behavior; and response/region/terminal expectations. Managed inputs are
fingerprinted and the source worktree is never used as the server runtime. A generation step has
`generation` authority unless it names a selected terminal probe and explicitly requests
`finished-chunk` authority. Force-load acknowledgment alone is never labeled finished-chunk proof.
Each `companion_artifacts` entry is a catalog root: its transitive `required_dependencies` closure
is validated, deduplicated, conflict-checked, and staged in dependency-first order. Do not manually
flatten a mod's dependency list into every scenario. Set `launch_task = "prodServer"` to execute
production-mapped Fabric/NeoForge code. For Fabric revision comparisons, the probe overlay supplies
the standard Loom production-server task when an older clean revision does not declare one, while
preserving an existing project-owned task.

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

## Exact packaged runtimes

```bash
tooling/squinch --tranche <id> mc-investigate packaged-runtime "$SPEC" --json
```

`SPEC` is an absolute task-local JSON path, validated against
[`schemas/packaged-runtime-v1.json`](schemas/packaged-runtime-v1.json). All fields are required;
unknown fields, duplicate JSON keys, nonfinite numbers, unsafe names, and mismatched hashes fail.
Its shape is:

```json
{
  "schema_version": 1,
  "project": "/absolute/exact/git/build-root/targets/forge",
  "source_roots": [
    "/absolute/exact/git/build-root/common",
    "/absolute/exact/git/build-root/targets"
  ],
  "loader": "forge",
  "minecraft": "1.16.5",
  "side": "server",
  "template": {
    "path": "/selected/tranche/inputs/prepared-template",
    "files": {
      "launch.args": "<sha256>",
      "libraries/server.jar": "<sha256>",
      "server.properties": "<sha256>"
    },
    "mutable_files": ["server.properties"]
  },
  "subject": {
    "path": "/selected/tranche/inputs/production.jar",
    "name": "subject.jar",
    "sha256": "<sha256>"
  },
  "companions": [
    { "path": "/selected/tranche/inputs/tests.jar", "name": "tests.jar", "sha256": "<sha256>" }
  ],
  "java": {
    "path": "/absolute/jdk/bin/java",
    "sha256": "<sha256>",
    "version": "<complete combined java -version output, stripped>"
  },
  "arguments": ["@launch.args"],
  "environment": { "SQUINCH_CASE_GROUP": "mechanisms" },
  "results": [
    { "environment": "SQUINCH_RESULT", "name": "result.json", "cases": ["mechanism:behavior"] }
  ],
  "timeout": 300
}
```

The placeholders above must be replaced with exact paths/hashes/identity. `project` is a Git build
root, not necessarily a modern Gradle multi-loader layout. `source_roots` explicitly enumerates
nonoverlapping production-source directories in that same Git worktree, including shared source
outside a nested target. Supply the complete source boundary: the runner does not discover it by
scanning an unrelated parent repository. The roots must cover the project or its production source
directories, and cannot contain task state. Legitimate selected-tranche source worktrees and
ordinary non-submodule projects inside the parent repository are supported; other-tranche projects
are rejected. The spec, template and artifact inputs must belong to the selected tranche, outside
declared source roots, nested source worktrees and previous run directories. An ignored selected
tranche inside the parent Git repository is legitimate scratch, not production source. Paths must be
canonical and must not traverse symlinks. The manifest enumerates **every** template file, with
exact SHA-256. Files must be regular, without hard links, symlinks or special files. An absent or
empty `mods/` is allowed; implicit mods, source build recipes, reserved output/home/tmp directories,
logs, crash reports and stale named results are not. Subject/companion basenames must be safe and
unique. The subject is also inspected for known development-probe contamination; explicit separate
test companions may contain test instrumentation.

A target's maintained test framework owns installers, real loader/version-compatible Java arguments,
native libraries, assets and all safe resource inputs. Prepare those resources inside the template
and enumerate their hashes. This generic runner installs nothing, downloads nothing, chooses no
build-directory JAR, rebuilds nothing, and assumes no GameTest/Loom/modern-loader API. Launch
references in JVM argv, explicitly referenced argument files and JAR manifest Class-Path must be
relative and offline: no absolute paths, file/HTTP URLs, Windows paths or external source-worktree
builds. Standard JVM classpath/module-path/JAR inputs must name packaged template files/directories
or explicit staged mod JARs (directory wildcards are supported); empty classpath elements are
rejected. Launch-file operands and argument-file names must be canonical relative paths: spell
`libraries/main.jar`, not `./libraries/main.jar` or `libraries/./main.jar`. Lexical `.`/`..`
components are rejected before normalization, so aliases cannot erase an executed-JAR or Java-agent
role. Literal application arguments and configuration prose are unaffected. Manifest dependencies
resolve relative to each archive's **runtime** location, across the combined template and staged
`mods/` namespace, including transitive non-JAR archives and cycles. Internal `./` and `../`
manifest references are allowed only within that namespace; every actual edge must resolve to an
exact packaged file or a nonempty packaged directory (with a trailing `/` in manifests).
Missing/optional edges, escaping references and runtime/output-root references are rejected.
Manifest entry discovery is case-insensitive at these actual archive boundaries, including reached
non-JAR archives. Multiple matching entries (even identical names/content) are rejected as
ambiguous; package exactly one `META-INF/MANIFEST.MF` entry instead. Unreferenced non-JAR data
archives are not scanned as recipes. Launch directories cannot acquire unmanifested files under a
successful final integrity check.

Known JVM class/library-path properties, patch-module, bootclasspath and agent paths are also typed
immutable launch inputs. Forge/NeoForge `-DlegacyClassPath` supports explicit colon-separated
packaged files/directories, without empty elements or wildcards; `-DlibraryDirectory` supports one
nonempty packaged directory, not a list or wildcard. This typing does not qualify either loader.
`-XX:VMOptionsFile` and HotSpot `-XX:Flags` are explicitly **unsupported**: put equivalent JVM
options directly in `arguments` or a manifested immutable `@argument-file` instead. Legacy JDK8
`-Djava.ext.dirs` and `-Djava.endorsed.dirs` are also unsupported, as are overrides of the selected
installation's internal `sun.boot.class.path` and `sun.boot.library.path` properties. Use explicit
packaged class/library/boot paths instead; the selected Java installation supplies its standard
platform paths. This is not a claim that those legacy facilities exist on every Java version.
Explicit HotSpot `-XX:SharedArchiveFile`, `-XX:SharedClassListFile`, `-XX:ExtraSharedClassListFile`
and `-XX:SharedArchiveConfigFile` selectors are unsupported; retain the selected installation's
default shared archive and use explicit packaged class paths. This leaves its normal platform CDS
archive trusted; it does not demand hashing every installed JDK library. Explicit
`-XX:CompileCommandFile` and `-XX:CompilerDirectivesFile` are also unsupported optional VM
configuration inputs; supply supported compiler options explicitly in arguments or an immutable
launcher argfile instead. Alternate-VM selectors `-XXaltjvm` and `-J-XXaltjvm` are unsupported: the
selected Java installation must supply its VM. Named native agents (`-agentlib` and legacy `-Xrun`)
are unsupported, including the standard `instrument` aliases that accept another Java-agent JAR; use
the explicit typed `-javaagent` or packaged `-agentpath` interfaces instead. These boundaries are
based on the selected HotSpot JDK8/JDK17 startup recipes, not universal Java-vendor support.

An actually invoked `-javaagent` archive with a nonempty main-manifest `Boot-Class-Path` is
unsupported; remove that attribute and package its dependencies through ordinary `Class-Path` or
explicit immutable launch paths instead. An actual `-jar` operand with a main-manifest
`Launcher-Agent-Class` attribute is unsupported (including an empty value); remove the attribute and
use an explicit packaged `-javaagent` without `Boot-Class-Path` instead. This executable-JAR role is
collected before archive traversal, like explicit agent roles. Merely reaching an archive through
Class-Path does not invoke its launcher agent. Ordinary/uninvoked and named-entry agent attributes
remain data. Ordinary `Class-Path` closure still applies to agent archives. Options of explicit
native `-agentpath` libraries remain supplied native program data, not recursively parsed JVM
options; this is not a sandbox for arbitrary library/application behavior.

Argument-file expansion follows the launcher state, including option operands and boundaries inside
an argument file. After the main class, JAR or module operand, `@missing` and `@data` are literal
application arguments, not files to open or classify immutable. Referenced launcher argument files
themselves are immutable. They support space/tab/newline separation, single/double quotes and
whole-line `#` comments, but not inline `#`, backslash escapes, unterminated or multiline quoted
arguments, other control characters or nested launcher argument files; `--disable-@files` is
unsupported. Unsupported optional grammar is rejected rather than interpreted as shell syntax.

Template resources, attribution, ordinary configuration, unrelated `-D` values, application
arguments after the main class/JAR/module and `SQUINCH_*` control **data** are not launch recipes:
they may contain URLs, escaped text and ordinary data paths. The runner does not impose a network
sandbox on supplied Java/mod code or interpret arbitrary controls as classpaths. Parent traversal in
argv paths and backslash escaping in launch references are unsupported. Source-language Java launch
recipes and Gradle/Maven recipes are not runtime inputs. The runner supplies owned Java home/tmp
_data directories_ (`user.home`, `java.io.tmpdir`), not a replacement Java installation; arguments
cannot override those directories or `user.dir`/`java.home`. Identity probes and managed Java
launches also receive `-XX:-UsePerfData`: HotSpot's optional Linux performance-data facility uses
system `/tmp`, independently of `TMPDIR` and `java.io.tmpdir`. The selected JVM must support this
HotSpot option (qualified controls use Temurin JDK8/JDK17); a failed identity probe reports that
requirement rather than silently dropping the flag. Attempts to set/re-enable `UsePerfData` in
actual launcher argv or argument-file context are rejected before run allocation; an explicit
`-XX:-UsePerfData` is allowed. Option-looking application arguments, property descriptions, and
configuration/control prose remain literal data. This suppresses that specific optional VM output,
not arbitrary application/native-code filesystem writes or every JVM vendor's transient state; it
does not establish historical filesystem containment.

The runner revalidates inputs at both the CLI and implementation boundaries, and again during
transactional preparation and after execution. It creates `runs/<run-id>/runtime`, copies the
verified template, and stages **only** the exact requested subject and companions in `mods/`. Staged
JARs and immutable template files must retain their hashes after execution. The required
`template.mutable_files` array (empty unless needed) may name only exact manifest files:
`server.properties`, `options.txt`, `optionsof.txt`, or configuration under `config/` with suffix
`.json`, `.toml`, `.properties`, `.cfg`, `.conf`, `.txt`, `.yaml` or `.yml`. Archives, libraries,
argument files and classpath/module-path/JAR launch inputs cannot be mutable, even if disguised as
configuration. Each mutable copy must remain a regular, nonlinked file; its final SHA-256 is
recorded in `mutable_files_after` after teardown. Original input templates always retain their exact
manifest hashes. No directory/wildcard/all-files mutability is supported.

Source snapshots use a consistent Git-root-relative path basis for HEAD, scoped tracked porcelain
status, and content hashes of **all** regular source files in the declared roots, including already
dirty, untracked and Git-ignored source. Denied/cache state is excluded before traversal (including
`.git`, `.gradle`, editor/virtualenv/Python/tool caches, `node_modules`, `dist`, and
repository-specific denied reference/QA/investigation/site/private state); these cannot themselves
be declared source roots. Generated class/JAR/log and build/run exclusions for the former parent
investigation tree remain scoped to that tree. Elsewhere, a directory name or binary suffix does not
prove that an input is generated: tracked wrapper JARs, maintained `tools/build/` scripts, binary
fixtures, and unexpected binary output in a declared root are audited. Present build outputs inside
a declared root are read-only during the operation too; this interface offers no concurrent
build-output-write exception. Put runtime/test output outside the declared source boundary.

Ordinary allowed source directories named `private`, `tmp` or `reference` are not silently excluded.
No whole-parent status/untracked discovery, diff drivers or submodule recursion is used. Undeclared
source and excluded caches are not audited. Supplied runtime/test code must itself respect source
isolation; this is provenance checking, not an adversarial-code sandbox. All ordinary game-generated
state belongs in the owned runtime.

The outer finite service retains the project cwd/provenance; `application_exit --cwd` runs the exact
Java argv in the isolated runtime without a shell. The manifest records the full spec/hash, command,
environment, Java executable checksum and observed `-version`, template hashes and source snapshots.
`env -i` discards inherited JVM options, classpaths, launcher/display settings and SQUINCH controls,
including the user-systemd manager environment. The inner Python helper also receives
`PYTHONDONTWRITEBYTECODE=1` and a fresh unused runtime-local `PYTHONPYCACHEPREFIX`, preventing reads
of adjacent existing caches without creating a bytecode cache directory. Spec controls are
restricted to `SQUINCH_*`; result variables and `SQUINCH_TRANCHE`, `SQUINCH_TRANCHE_WORKSPACE`,
`SQUINCH_INVESTIGATE_RUN_ID` are reserved. The run ID is supplied automatically. Result variables
receive absolute owned output paths. A client uses the existing headless cage settings and a private
directory under the user's XDG runtime root; its live sockets never enter the tranche and its
directory is removed on teardown. Personal profiles, accounts and persistent display state are not
used. Server operations cannot own a display.

Every required result must satisfy
[`schemas/packaged-runtime-result-v1.json`](schemas/packaged-runtime-result-v1.json), for example:

```json
{
  "schema_version": 1,
  "run_id": "<SQUINCH_INVESTIGATE_RUN_ID>",
  "status": "pass",
  "subject_sha256": "<exact requested production JAR SHA-256>",
  "runtime": { "loader": "forge", "minecraft": "1.16.5", "side": "server" },
  "cases": [{ "id": "mechanism:behavior", "status": "pass", "observations": {} }]
}
```

Require exactly the declared unique case IDs, all passing, and exact run/subject/runtime identity.
Bare `{ "status": "pass" }` is invalid. Results do **not** terminate the application: success also
requires the actual inner Java application to exit with code zero. An early passing result followed
by a nonzero exit, missing/malformed/nonpassing result, timeout, fatal/crash diagnostic, changed
input or staged file, source Git pollution, or incomplete cleanup fails. Final integrity checks run
after service teardown, including on failed runs and late writes. Rejected assertions, diagnostics
or integrity checks are **run failures**, not incomplete teardown: when actual
process/thread/display cleanup is verified, the failed manifest remains but the active marker is
removed. Only genuine resource cleanup failure retains active recovery state.
`status --project PATH --loader LOADER` and `doctor --recover --project PATH --loader LOADER` use
the same unit/process/thread validation and project locks as existing operations, with additional
run-derived paths and side-specific display confinement. Recovery finalizes a **failed** run; it
does not repair modified inputs or certify its assertions. Startup rollback also removes private
display state, and retains a recoverable launching intent if that removal fails. A preexisting
display path is never removed as rollback.

**Authority limit:** `external-structured-assertions-and-owned-lifecycle` means the runner validates
external assertions and lifecycle, not their semantic truth. The separately maintained test mod must
observe the actual loaded subject identity, loader, Minecraft version, side and production behavior.
A dummy executable, fabricated result, subprocess fixture or real owned-service smoke is only
lifecycle evidence, never Minecraft qualification or parity evidence. No instrumentation is shipped
or injected into the production subject by this command.

## Instrumented client investigations

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

Matrix runtime state lives below the tranche's `benchmarks/` directory. Workload adapters remain
task-local scenarios, so the matrix runner contains no mod-specific command or report knowledge.
Remove the matrix and its scratch results when the active comparison is complete.

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

The command creates two detached worktrees under the tranche's `worktrees/` directory, runs them
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
tracked target source or resources. Requests appear atomically under the run's
`server-run/.squinch-investigate/requests/`; the runtime claims them on the Minecraft server thread
and atomically publishes JSONL transcripts under `results/`. Every transcript record carries the
run, request, probe, and probe-version identity, and exactly one final record has terminal state
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
  completeness.
- `squinch:runtime-smoke`, `squinch:partial-control`, `squinch:exception-control`,
  `squinch:isolation-control`, and `squinch:stop-flush-control` are protocol negative/positive
  controls, not investigation probes; see `BuiltinProbes.java` for their exact behavior.

Each scenario manifest fingerprints the scenario, Git HEAD and dirty patch, untracked inputs,
datapacks, Java, Gradle wrapper/build inputs, loader, JVM environment arguments, launch command, and
the runtime mod list parsed from the real loader log. Startup verifies the actual seed and owned
world before steps run. A crash, fatal server condition, timeout, assertion failure, missing or
non-passing probe terminal result, incomplete scan, or cleanup failure makes the command nonzero.

Every run owns a unique ID, artifact directory, isolated server directory, log, manifest, command
stream, summary, and level name inside the tranche. The launcher invokes a non-executable wrapper as
`bash ./gradlew`, uses `env.sh`, disables reusable Gradle daemons for the launch command, and never
changes the wrapper's tracked mode. Gradle's shared user cache stays outside tranche ownership.

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

Preview and apply task cleanup with `tooling/squinch tranche clean <id>` and
`tooling/squinch tranche clean <id> --apply`. The repository command removes the complete selected
tranche across games after verifying that no owned process or incomplete teardown remains.

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
