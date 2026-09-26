# External probe-pack template

Copy this directory's example files into
`games/minecraft/investigations/<mod-id>/probes/<probe-id>/`, remove the `.example` suffixes, and
replace `example` identifiers. A new pack does not require changes to `probe-runtime`, the Python
investigation engine, the shared tick dispatcher, or the target worktree.

Required structure:

```text
<probe-id>/
├── probe-pack.toml
└── src/main/
    ├── java/.../ExampleProbePack.java
    └── resources/
        ├── META-INF/services/org.squinchmods.investigate.ProbePack
        └── example.mixins.json        # only when a hook is required
```

The manifest declares identity, adapter, source/resource roots, Mixin configurations, configuration
schema, and capabilities. The service file names every `ProbePack` provider. `register()` assigns a
stable probe ID/version and returns an isolated `ProbeExecution` per request.

Use `FinishedChunkSelection` when the measurement needs stored chunks. It owns bounds/unit parsing,
negative-coordinate conversion, limits, bounded readiness polling, missing examples, completeness,
and the final pass/inconclusive result. Use `MinecraftProbeHelpers` for guarded generation reads,
block/biome IDs, forced chunks, bounded examples, and deterministic top-K output. Keep measurement
logic in the pack; these helpers intentionally do not prescribe what to measure.

Only add a Mixin when the information does not exist at probe time. Keep the injection method small:
capture an event into pack-owned state and return. Do not add another `MinecraftServer.tickServer`
or `stopServer` Mixin—the shared runtime already owns dispatch, isolation, error handling, and stop
flush. Put implementation-coupled QA in a topic QA worktree when proximity makes the experiment
safer; extraction is for mechanisms proven useful across investigations, not a requirement to move
every historical prototype.

Configuration belongs in the request whenever changing it does not change the hook: coordinates,
chunk bounds, feature/biome/block IDs, height bands, predicates, sampling steps, limits, and top-K
sizes. A hook should not know a scenario's seed, coordinates, or expected result.

Verification sequence:

1. Select the pack with repeatable `--probe-pack PATH`, or `probe_packs = [PATH]` in a scenario.
2. Compile `:fabric:compileJava` and `:fabric:processResources` through the overlay.
3. Confirm the target's tracked status is byte-identical before/after.
4. Run a positive probe and a meaningful negative or falsification control.
5. Stop and verify inactive state, no listeners/world/protocol directory, and complete cleanup.
6. Run a normal production build and `inspect-artifact` before publishing anything.

The FTF `heightmap-delta` pack is the first genuinely new probe created through this template. It
changed only its new pack directory plus scenario selection and uses the unchanged shared runtime.
