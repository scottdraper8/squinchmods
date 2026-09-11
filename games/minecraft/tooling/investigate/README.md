# Minecraft Investigation Tooling

This package owns the tight Minecraft development and investigation loop. Release matrices and
promotion remain under `../qa/`.

Use the repository dispatcher from any working directory and always name the exact target worktree:

```bash
tooling/squinch mc-investigate run \
  --project games/minecraft/mods/FreeTerraForged \
  --loader fabric \
  --seed 12345 \
  --command list
```

The public commands are `start`, `stop`, `status`, `doctor`, `command`, `run`, `client`, `scenario`,
`generate`, `probe`, `compare`, `inspect-artifact`, `cell-scan`, `preset-fixture`, and `clean`. Add
`--json` to any command for the committed `schemas/cli-output-v1.json` envelope. The states
`starting`, `running`, and `stopping` are non-terminal; `ready` means RCON authentication succeeded;
`succeeded`, `failed`, `inconclusive`, and `error` are terminal outcomes; `inactive` means no
service is tracked; and `degraded` or `unknown` requires diagnosis rather than an assumption of
success.

Run a canonical or temporary scenario with one command; every repository-owned project, datapack,
fixture, patch, and probe path is repository-root-relative (`games/minecraft/...`) and resolved from
the repository root rather than the caller's directory:

```bash
tooling/squinch mc-investigate scenario \
  .squinch/games/minecraft/mods/FreeTerraForged/scenarios/smoke.toml \
  --json
```

Scenario schema version 1 requires an exact seed and ordered steps. It supports command, generation,
and selected-probe steps; multiple datapacks; server properties; startup/step/shutdown timeouts;
retention; required runtime mods; managed `[[runtime_files]]` inputs copied from repository-relative
sources to targets below the loader's `config/` directory; managed `runtime_absent_files` paths for
first-start behavior; and response/region/terminal expectations. Managed files are fingerprinted
where applicable, backed up, installed or removed before launch, and restored on every cleanup path.
A generation step has `generation` authority unless it names a selected terminal probe and
explicitly requests `finished-chunk` authority. Force-load acknowledgment alone is never labeled
finished-chunk proof.

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
profile or the project's ordinary run directory:

```bash
tooling/squinch mc-investigate client \
  --project games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility \
  --loader fabric \
  --probe-pack games/minecraft/investigations/freeterraforged/probes/pre-server-preview \
  --artifact lithostitched-fabric \
  --runtime-file games/minecraft/investigations/example.toml=config/example.toml \
  --probe-env SQUINCH_PREVIEW_CASE=regeneration \
  --result-env SQUINCH_PREVIEW_RESULT=preview-result.json \
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

For an isolated generation benchmark, set `repeat`, a nonzero `offset = [x, z]`, and
`release_after_observation = true` on a generation step. The parser requires every translated
coordinate window to be disjoint and caps one step at 20 observations. Releasing each exact owned
force-load set after its terminal probe prevents earlier windows from remaining live and poisoning
later heap and timing behavior; release time is recorded but excluded from generation/total timing.
Each observation retains its exact bounds plus generation, probe, release, and total seconds; the
step also reports every timed generation/probe value with median, minimum, maximum, and range. Set
`jfr = true` on any step to record only that step with the owned Minecraft JVM. The resulting
nonempty, hashed `.jfr` is stored under that run's `profiles/` directory and referenced by both the
scenario result and manifest. Lifecycle timing separately records startup, verified world-open,
save, shutdown, and cleanup rather than folding those costs into generation.

The retained FTF benchmark is
`.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-biome-palette.toml`. Use it directly
with `scenario`, or pass it to exact `compare` as shown below. Exact comparisons hold a global lock
and run the two sides sequentially, preventing before/after benchmark overlap by default. Timing and
profile metadata remain evidence but are excluded from behavioral equality.

Run an exact before/after comparison with full 40-character commit SHAs and one scenario:

```bash
tooling/squinch mc-investigate compare \
  --project games/minecraft/mods/FreeTerraForged \
  --before 9099214b0a92e702bd2de9e1d9e61c5d645fb5b0 \
  --after a05560848cf7bec7ad56ba5832d247d08a1c7da0 \
  --scenario .squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-biome-palette.toml \
  --expect different --json
```

The command creates two detached worktrees under `investigation-state/worktrees/`, runs them
sequentially, and requires identical scenario-input and injected-probe fingerprints. It removes
request IDs, timestamps, polling/timing fields, and placement CPU time from behavioral equality;
list order and all remaining numbers stay exact. The comparison artifact retains both normalized
sides, recursive field-level differences, exact commit/tree identities, and code, environment,
input, probe, and timing fingerprints. Clean temporary worktrees are removed in `finally`. A failed
side or an unexpectedly modified worktree is preserved and reported rather than force-removed.
Existing result files can still be compared with `compare --left FILE --right FILE`.

An FTF scenario names one compact preset fixture with `ftf_fixture = ".../fixture.toml"`. Before
server startup, the runner invokes the selected worktree's real preset exporter, validates the
complete generated registry tree, writes a deterministic ZIP, and copies it into the scenario run.
The generator run ID, semantic metadata, input preset hash, generated-tree hash, and archive hash
are retained together. Additional independent datapacks remain a repeatable `datapacks = [...]`
array.

Generate a complete source tree through the selected FTF worktree from either an existing fixture or
a complete resolved preset JSON:

```bash
tooling/squinch mc-investigate preset-fixture \
  --project games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility \
  --preset games/minecraft/investigations/freeterraforged/fixtures/vanilla-depth-maximum-ocean/fixture.toml \
  --json
```

The command decodes the resolved preset in a standalone FTF data-generation process, invokes the
real complete preset exporter, and verifies the generated preset, dimension type, noise settings,
density functions, source-tree fingerprint, worktree immutability, and process cleanup. Generated
trees remain run artifacts; only complete preset JSON and its compact semantic metadata belong in
the tracked fixture catalog.

## Standalone FTF cell discovery

`cell-scan` executes the selected FTF worktree's real compiled `Preset`, noise bootstrap,
`GeneratorContext`, and `TileGenerator` classes in a small standalone JVM. It does not start a
dedicated server, create a world, or generate Minecraft chunks, and it fails instead of falling back
to a live probe if the standalone registry boundary cannot be established.

Use preview mode for inexpensive discovery. This calls FTF's exact
`generateZoomed(centerX, centerZ, zoom, false)` path and labels the result `prediction`:

```bash
tooling/squinch mc-investigate cell-scan \
  --project games/minecraft/mods/FreeTerraForged \
  --preset games/minecraft/investigations/freeterraforged/fixtures/vanilla-depth-maximum-ocean/fixture.toml \
  --seed 12345 --mode adaptive --bounds -4096 -4096 4096 4096 \
  --sample-step 16 --predicate 'height:>=:0.15' \
  --field height,height_blocks,terrain,continent_edge \
  --refine-count 2 --refine-step 8 --exact-tile --json
```

Preview and adaptive modes support bounds or center/zoom, sample steps, repeatable field and
`FIELD:OP:VALUE` predicate selections, ascending/descending ranking, top-K candidates, bounded
predicate examples, histograms, quantiles, extrema, optional JSON/CSV grids, and a PNG heatmap.
Available data spans height, terrain/type, continent, river, temperature/moisture, erosion,
weirdness, water table, and terrain/biome region fields. Aggregates are the default; grids are only
retained when explicitly requested.

Use `--mode tile --tile-size 3` for FTF's filtered horizontal cell model. Tile mode invokes
`TileGenerator.generate(tileX, tileZ)`, uses FTF's runtime filter-border calculation, closes every
tile, caps one request at 64 tiles, and labels its authority `ftf-horizontal-cell-model` rather than
final block truth. Every scan artifact records the exact seed, resolved preset, target HEAD/dirty
status, harness hashes, standalone bootstrap boundary, Minecraft/FTF/Java versions, fully
fingerprinted classpath, cold/warm/Gradle wall timings, and a deterministic result hash.

The canonical live parity gate is
`.squinch/games/minecraft/mods/FreeTerraForged/scenarios/ftf-cell-cache-cross-check.toml`. It
selects the external `probes/cell-cache` pack, loads the same seed and preset, and compares
standalone factor-3 samples with FTF's live runtime tile cache at exact block coordinates. Direct
development starts can select reusable packs with repeatable `--probe-pack PATH`; scenarios use a
top-level `probe_packs = [PATH, ...]` array. Pack manifests, source/resource roots, capabilities,
mixins, and hashes are recorded in the run manifest.

Reusable FTF packs live under `games/minecraft/investigations/freeterraforged/probes/`. The
`biome-palette` and `placement-telemetry` packs use the same runtime, scenario trigger, result
model, and finished-chunk selector while retaining their distinct measurements. `heightmap-delta` is
the first new probe authored through the external pack template; `placement-telemetry` is the only
one of these three that needs Mixins. See that directory's README and
`probe-pack-template/README.md` for configuration, historical disposition, and authoring rules.

To turn discovery into finished-world evidence, point a scenario generation step at the scanner's
retained `cell-scan-result.json` instead of writing fixed bounds:

```toml
[[steps]]
id = "generate-shortlist"
type = "generate"
unit = "block"
candidate_file = "/exact/run/artifact/cell-scan-result.json"
candidate_limit = 2
authority = "finished-chunk"
terminal_probe = "squinch:finished-chunks"
```

The runner reads `scan.top_candidates`, floors negative coordinates correctly, deduplicates them by
chunk, fingerprints the shortlist artifact, force-generates each selected chunk, and runs the chosen
terminal probe for every chunk. The evidence funnel is therefore: preview prediction → optional
exact FTF tile → bounded real generation → finished-chunk probe. Only the final stage may be
described as finished-world truth.

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
  games/minecraft/mods/FreeTerraForged/fabric/build/libs/freeterraforged-fabric-*.jar \
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
Target `eula.txt` and `server.properties` files are backed up and restored. The launcher invokes a
non-executable wrapper as `bash ./gradlew`, uses `env.sh`, disables reusable Gradle daemons for the
launch command, and never changes the wrapper's tracked mode.

Every launch runs as a dedicated transient user-systemd service with control-group kill semantics.
The exact unit intent is published as recoverable `launching` state before `systemd-run` is spawned,
wrapper identity enriches that owner immediately after spawn, and main-process discovery then
advances it in place. `stop` enumerates that service's complete cgroup, validates retained Linux
process identities before fallback signaling, removes only force-load regions recorded by the run,
and treats any remaining process/listener/file/world cleanup problem as failure. `doctor --recover`
is the explicit recovery path for retained incomplete state. Launch preparation is transactional,
and every blocking stop phase consumes the same monotonic timeout budget; the timeout is not
restarted for each phase. Choose a timeout that includes launch/transformation, the probe, normal
shutdown, and fallback cleanup; a short diagnostic timeout can expire before cleanup has any
remaining budget.

`clean` is a dry run unless `--apply` is supplied. It accepts exact `--run` IDs or an explicit
`--older-than-days` selection and rejects active runs, symlinks, foreign manifests, or paths outside
the owned state root. Age cleanup preserves evidence named in
`.squinch/games/minecraft/investigation-retention.toml`. Exact deletion of one of those runs
requires the deliberately narrow `--include-protected` override. It deletes directly after
validation; there is no speculative trash layer.

## Testing policy: tests must earn their keep

Automated testing is useful only where it is more discriminating and repeatable than a targeted live
experiment. Test count, coverage percentage, and the presence of a `tests/` directory are not goals.

Automated tests also do not replace QA Mixins, live scanners, experimental branches, or
purpose-built investigation logic. Tests protect stable tooling invariants and cheap deterministic
behavior. The handcrafted probes answer new questions about the real game. This package exists to
make those probes easier to create and trust, not to make them unnecessary.

### Rules for retaining an automated test

A retained test must satisfy all of the following:

1. **Named failure:** Its description states a realistic defect it would catch.
2. **Meaningful assertion:** It asserts an observable invariant or outcome, not merely that code
   ran, returned a non-null value, or called a mock.
3. **Independent expectation:** Expected values are not generated by the same logic being tested.
4. **Relevant boundary:** It exercises the lowest real boundary needed to expose the defect.
5. **Negative control:** The test is shown to fail against a deliberately broken implementation, a
   prior known-bad implementation, or a controlled fault.
6. **Stable value:** The likely regression cost exceeds the maintenance and false-confidence cost.

If you cannot explain what plausible code change makes a test fail, don't add it. If an existing
test continues to pass after the behavior it claims to protect is deliberately broken, fix or delete
the test.

### Prohibited low-value patterns

- Testing a mock's configured return value.
- Mocking the code path that contains the behavior under test.
- Reimplementing production logic in the test and comparing the implementation with its duplicate.
- Computing expected output by calling another method that uses the same underlying implementation.
- Assertions such as "result exists," "exit code is an integer," or "a callback was called" when the
  real invariant is stronger.
- Snapshotting incidental log formatting as a substitute for structured behavior.
- Simulating Minecraft registries, chunks, Mixins, or loaders and treating that as evidence that the
  integration works in Minecraft.
- Huge fake frameworks that behave more like the desired system than the real external dependency.
- Timing assertions with narrow wall-clock thresholds on a shared development machine.
- Adding a permanent regression test for every one-off investigation regardless of recurrence or
  stability.

### Where automated tests are legitimately valuable

| Area                    | Useful verification                                                                                                              | Why it earns permanence                                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| CLI JSON contract       | Emit real success, failure, and in-progress responses for each structured command and validate them against the committed schema | Agents need stable state/error semantics; undocumented drift can cause false conclusions or unsafe cleanup |
| Scenario parsing        | Real TOML files with known resolved paths/configuration and invalid cases                                                        | Deterministic logic with many dangerous edge cases                                                         |
| Coordinate tiling       | Boundary tables and property tests covering negative coordinates and 16x16 limits                                                | Off-by-one errors silently generate the wrong world area                                                   |
| Atomic state/results    | Real temporary filesystem operations and interrupted-write cases                                                                 | Corrupt state can cause unsafe cleanup or false completion                                                 |
| Process identity        | Real subprocesses, process groups, `/proc` identity, and socket listeners                                                        | The historical failure is an OS-process problem, not a Python-object problem                               |
| Teardown                | A helper process that forks a child listener and ignores TERM                                                                    | Reproduces the actual class of orphan failure without pretending to be Minecraft                           |
| RCON framing            | A small real socket server with valid and malformed packets                                                                      | Exercises protocol bytes and timeouts directly                                                             |
| Result state machine    | Tables covering pass/fail/inconclusive/error and missing terminal events                                                         | Prevents false success, the most dangerous agent-facing failure                                            |
| Manifest hashing        | Known files/diffs/datapacks and changed-input controls                                                                           | Provenance must detect real input changes                                                                  |
| Fixture materialization | Build a real datapack archive, inspect its required data path and decoded resolved preset, and compare deterministic hashes      | Scenarios depend on the packaged bytes Minecraft actually loads                                            |
| Worktree lifecycle      | A temporary real Git repository with actual detached worktrees                                                                   | Git behavior is cheap to exercise directly and unsafe to merely mock                                       |
| Artifact exclusion      | Inspect a real built jar/zip                                                                                                     | The invariant concerns packaged bytes, not Gradle task configuration                                       |

### Where live scenarios are more honest

Use real, targeted Minecraft runs rather than elaborate automated simulations for: loader startup
and Mixin application; datapack and registry bootstrap; FTF `GeneratorContext` acquisition;
`WorldGenRegion` availability rules; finished `LevelChunk` promotion; stored biome palettes;
structures, Beardifier, aquifers, surface rules, and placed features; Fabric/NeoForge differences;
interactions with TerraBlender, Biomes O' Plenty, Regions Unexplored, or other mods; and whether a
visual worldgen defect is meaningful to a player. These scenarios can still be automated by
`mc-investigate`; the distinction is that they run the real game and assert a narrow condition
rather than replacing the game with mocks.

### Targeted experiments are first-class verification

Not every useful check belongs in a permanent test suite. For a feature under active development, it
is often better to create a small scenario/probe that states the competing hypotheses, uses an exact
seed, preset, coordinates, loader, and code commit, measures the one observation that distinguishes
them, records a structured result and run manifest, and is retained as a permanent regression only
if the invariant is stable and recurrence risk justifies it. The scenario and its artifacts are
evidence even when the probe is later removed — that's preferable to keeping a generic-looking test
that never exercised the actual failure.

Topic QA worktrees remain legitimate when an investigation needs implementation changes and
instrumentation to evolve together; this package should reduce their manual build, registration,
parameter, comparison, and cleanup burden, not treat their existence as a failure or force all
experimental work through a generic permanent test suite.

### Verification ladder

Use the cheapest layer that can genuinely falsify the claim, then cross the real boundary before
declaring integration complete:

1. **Pure deterministic test:** parsing, tiling, aggregation, state transitions.
2. **Real local boundary test:** filesystem, socket, subprocess, Git worktree, jar.
3. **Fast mod-model probe:** FTF preview/cell/tile prediction.
4. **Real Minecraft scenario:** loader, registries, chunks, blocks, structures, features.
5. **Human/client confirmation:** visual and player-facing behavior.

Passing a lower layer never proves a higher one. In particular, an FTF cell scan cannot prove final
blocks, and a mocked server cannot prove process teardown or loader behavior.
