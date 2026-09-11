# Minecraft Agentic Development Findings

Unresolved tooling defects that need human attention. Mod-specific conclusions belong in that mod's
canonical plan, durable operating rules belong in `agentic-development-guide.md`, and raw evidence
belongs in retained run artifacts. Remove an entry once its resolution gate is satisfied.

## Active

### Packaged generation can crash or become unkillable on Temurin 21.0.11 independently of JFR

Three retained JVMs crashed in the identical HotSpot frame, `RegisterNMethodOopClosure::do_oop`, on
Temurin 21.0.11+10. The Fabric run `20260907T010315Z-1c6346bcbf` had no JFR recording or JFR startup
flag. Its 4 GiB G1 heap reached 4.17 GiB used, repeatedly failed humongous allocations, and crashed
while rebuilding compiled-code roots during a full collection. Earlier Fabric and NeoForge crashes
have the same `libjvm.so` offset, but did use step-scoped JFR. JFR is therefore not a necessary
cause, and the post-JFR host-health check does not prevent or fully detect this failure class.

The repeated-generation runner also retained every earlier observation's force-load tickets until
server shutdown. An eight-window benchmark therefore grew from 441 to 3,528 simultaneously forced
chunks instead of holding one active window. This is the demonstrated cause of the 4 GiB exhaustion
and a confounder in the profiler-free hangs. The local runner now has exact owned-region release
after each terminal probe. Its corrected three-revision/three-mode matrix completed 27 of 27 fresh
JVMs and 189 of 189 measured windows on Temurin 21.0.11+10, including three passes each for the
previously failing parent/no-C2ME and experimental/no-C2ME cells. Every observation released its
four acknowledged regions and every run passed cleanup, inactive-state, and zero-JVM gates. Exact
evidence is retained in
`games/minecraft/investigations/reterraforged/analysis/c2me-dfc-matrix-20260907/analysis.md`.

Separate profiler-free generation runs `20260906T233513Z-99905130ee` and
`20260907T012004Z-caa696b70e` stopped making probe progress while their JVMs were still present.
Termination of the latter initially left 77 of 125 server threads, and then all 125 threads, in
uninterruptible `D` state at `exit_mm`; TERM, KILL, RCON, user-systemd, and JVM attach could not
retire the process. Do not assume that this hang and the full-GC crash share one root cause merely
because both poison teardown. The corrected matrix falsifies a branch-specific no-C2ME hang, but
does not identify the lower-level mechanism that turned the old accumulated-ticket workload into an
`exit_mm` survivor.

Client run `20260907T043438Z-3ef12fc82e` demonstrates the same operational hazard outside the
generation benchmark. A 180-second total timeout expired while the Fabric development client was
still at the Architectury launch boundary. That same budget was exhausted before user-systemd
cleanup, leaving exact owned PID `92671` in uninterruptible `D` state even after the unit became
failed. This run contains no Minecraft behavior evidence. The active-state validator initially also
rejected recovery because it expected an obsolete artifact-local display path rather than the
current recorded `/run/user/<uid>/squinch-<run suffix>` path. The validator now derives that path
from the recorded runtime root and run ID, and its focused unit test passes; recovery then correctly
reported the surviving process instead of rejecting valid owned state.

The preview-to-finished probe supplied a second client-side workload amplification mechanism. Its
337 sparse viewport points requested chunks across 12,800 blocks. Each broad run generated 8,289 FTF
chunks and left 154,953 Minecraft chunk holders waiting to unload. That is not a bounded 337-chunk
workload and must not be used as a repeated client-matrix acceptance test. After recovery, a
contiguous 7 x 7 center probe completed all 18 production-client revision/mode/loader cells with 24
GiB heap, eight advertised processors, E-core affinity, clean shutdown, and no surviving JVM. Retain
the sparse runs only as preview-edge behavior controls; use compact contiguous chunk corpora for
lifecycle and storage matrices unless distributed generation is itself the behavior under test.

**Needs:** qualify another Java 21 distribution and repeat a JFR-bearing stress case with
per-observation force-load release and a heap large enough for the active window. The profiler-free
Temurin release path is live-qualified. Add a progress watchdog that captures a bounded thread dump
before termination while JVM attach still responds, and extend the general post-run gate to reject
surviving or `D`-state owned JVMs whether or not JFR ran. Until then, disable JFR, release repeated
force-load windows, verify complete cleanup after every JVM, and reboot after any `exit_mm` survivor
before collecting more timing evidence. Give launch work and cleanup independent bounded budgets; do
not let a short operation timeout consume all time available to retire an owned process. The
post-reboot 18-cell production-client matrix exercised the corrected display-path validator and
clean shutdown path; that portion is resolved even though the lower-level `exit_mm` cause remains
open.

### Scenario cleanup failure is emitted as successful process execution

Run `20260907T010315Z-1c6346bcbf` completed all generation steps and then crashed during cleanup.
The scenario CLI preserved the step data, but emitted `state = "succeeded"` with a `cleanup_failed`
error and exited zero. This lets automation accept timing from a poisoned host unless it
independently inspects both the error and `data.cleanup.complete`.

The local CLI now preserves completed step data while emitting an error terminal state and nonzero
exit code. Focused output-schema and handler/main exit tests pass.

**Needs:** exercise a controlled end-to-end cleanup failure that proves the persisted summary,
process exit, surviving-process gate, and inactive-state requirement together before removing this
entry.

### `preset-fixture` cannot compile against plain `upstream/1.21.1`

Fabric headless datagen provides `HolderLookup.Provider`, but `Datapacks.makePreset` on
`upstream/1.21.1` requires `RegistryAccess`. The widening fix is on
`fix/preset-fixture-provider-widening` (`40acb11`). Fixture presets also needed three missing
`IslandSettings` codec fields to avoid registry-load crashes.

**Needs:** merge the widening branch (or PR to `ETcodehome/FreeTerraForged`) and confirm a
`preset-fixture` run produces a fixture that boots a server.

## Entry rule

Add only a reproducible, repository-wide tooling defect with a concrete cost and a resolution gate.
Do not add reminders, mod behavior, speculative improvements, completed work, or workarounds. Fold
related symptoms into the existing root issue instead of adding another entry.
