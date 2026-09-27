# Search Probes Rust architecture and release gates

## Authorized outcome

Replace the pre-release Python product completely with a Rust implementation. Ship a self-starting,
version-qualified mod archive, deploy the accepted build to the direct NMS installation and recorded
Amethyst sources, and commit/push the mod repository. Do not publish to Nexus. Preset compatibility
and internal compatibility layers are not requirements. Preserve unrelated repository work.

Runtime searches must each finish or be cancelled within ten minutes. No billion-system or
100,000-system runs. Final coverage must use several representative populations and positive and
negative controls, with enough systems to exercise region traversal and less common criteria.

Runtime save restriction: use only `save.hg`/`save2.hg` (the "Galaxies 1-50" pair). Filename numbers
are not menu rows. Inspect the menu visually and verify the loaded address against the permitted
save before running probes. Fixed startup button sequences are unsafe because the mod-warning/menu
state varies. The launcher now stops before sending any menu input.

Keep code comments to necessary safety contracts and native semantics that names/types cannot
express. Use explicit names and typed records instead of explanatory comments about structure.

## Architecture decisions and open gates

- Product runtime, search engine, UI, persistence, and native bridge are Rust. Python may remain a
  host-side investigation tool while evidence is acquired; no interpreter or Python module ships.
- Reuse NMS generation algorithms through a narrow exact-build native interface. Do not reproduce
  the procedural engine externally or swap the game's global generator pointers.
- Compile selected predicates and acquisition requirements once. Any creates no predicate. Evaluate
  cheap fields before costly fields; acquire each required planet once where native seams permit.
- Use compact owned values, bounded result/cache/command storage, and session continuation across
  disjoint regions. Unknown cached fields cannot be interpreted as negative matches.
- Independent solar and planet contexts require real constructor, resource, and release contracts. A
  private context must pass serial parity before any worker call. Shared dependencies must have a
  proven lifetime and synchronization contract. If the native boundary cannot support workers,
  document the concrete limitation and retain a Rust gameplay-thread execution backend.
- UI selection favors a Rust native GUI without a webview. Preserve F7, criteria/preset editing,
  progress/cancellation, 100 results, Guide integration, and native navigation. Condense related
  controls with explicit OR-within-field and AND-across-field semantics.
- Native hooks, resource release, callbacks, and shutdown are owned by the new runtime. Do not
  retain Python or pyMHF through a compatibility shim.

## Dependency-ordered execution

1. Record baseline identity, source contracts, known bottlenecks, installed ownership, and healthy
   host. Establish reproducible Rust Linux-test and Windows-product build toolchains.
2. Construct focused native probes for generator lifecycle and explicit query orchestration.
   Establish dependency closure, serial parity, single-generation capture, and release ownership.
   Probe one/two workers only if the ownership/synchronization gates support doing so.
3. Implement typed search model, multi-selection, compact capture/filtering, region traversal,
   bounded session facts/frontiers, cancellation, and instrumentation in Rust. Preserve native
   semantics with fixture tests and comparisons against retained/current reference snapshots.
4. Implement native bootstrap/hooks, gameplay lifecycle, Guide/navigation, Rust UI and persistence.
   Remove obsolete product source and dependencies after replacement coverage exists.
5. Produce a complete archive with exact-build guards, licenses, user instructions, install/update/
   uninstall behavior, and no Python runtime. Validate ordinary Steam self-start, cold/warm
   searches, region coverage, every exposed criterion, multi-select, resource conjunctions, cache
   continuation, memory bounds, responsiveness, cancellation, native teardown, and destination
   lifecycle.
6. Deploy transactionally to NMS and Amethyst with NMS stopped. Verify file parity and clean launch.
   Commit and push the accepted mod; report measured capabilities and platform limitations honestly.

## Acceptance and evidence

The preceding investigation is in
[generator concurrency](../../../../games/no-mans-sky/investigations/analysis/search-probes-generator-concurrency.md)
and
[performance audit](../../../../games/no-mans-sky/investigations/analysis/search-probes-performance.md).
It proves scheduling headroom and identifies private-context candidates; it does not prove worker
safety. Existing runtime is the comparison oracle only, not the foundation for a compatibility
layer.

## Current implementation

The Cargo workspace contains Rust model, native runtime, GUI, WinMM bootstrap and packaging crates.
Host tests and Windows GNU product builds work with Rust 1.98.1 and the Fedora 44 / MinGW 16
toolchain. The standalone Rust candidate is installed transactionally in NMS and both Amethyst
sources. The previous Python installation is retained outside those destinations as a rollback
artifact. Navigation, reload, Guide, scheduler/cache regression and ordinary startup/exit pass
bounded standalone validation. The release archive matches the direct NMS and both Amethyst
installations; the mod source is committed and pushed. Exact release identity is retained in the
focused release-verification artifact. Obsolete Python/C product and host launcher paths have been
removed; their exact contents are retained as investigation artifacts, including previously dirty
related tooling.

The model owns typed multi-select predicates, selective acquisition requirements, compact facts with
explicit unknowns, a clipped constant-storage region iterator, dropdown budgets, settings
validation, nine Guide presets, and 100 results. Any compiles to no predicate. Choices are OR within
one field; fields and requirements are AND. Resource choices have explicit All/Any semantics.

Session state retains at most 16,384 systems with bounded names, below a 64 MiB structural storage
budget including conservative container overhead. It keeps facts acquired for nonmatches, without
claiming unrequested properties. Complete cached evaluations avoid native generation; partial facts
can supplement a later query. Cached matches pause before live work and offer continuation. A cache
result may lack a generated name; its validated address remains a usable identity. Facts and history
are invalidated on the inspected native epoch/configuration changes; live reload verifies clearing.

Continuation stores the most recent 128 compiled-filter/galaxy combinations. A matching filter
resumes its existing region and system cursor even if the player's position changed within that
galaxy. An explicit restart starts at the current location. Eviction is reported. Each frontier
stores one native region list (at most 4,095 addresses), not a visited-system graph. A batch
advances only after a completed system is accepted. Cancellation preserves partial facts and leaves
incomplete work at the frontier.

The native scheduler generates regions on the gameplay callback, dispatches bounded batches to a
persistent Rust pool, and waits before returning control to the game. It adapts batch size toward a
requested time budget, capped at 256 systems. The time budget is a scheduling target, not a hard
bound on an individual native call. Each worker owns solar/query/planet scratch state for that batch
and drops all borrowed contexts before the gameplay callback returns. Search uses one solar query
and at most one generation of each planet per system. Metadata, colours, and object flags are
acquired only when still required. Rust release panic policy is unwind; capture callbacks catch
panics before returning through native code, and worker dispatch joins every borrowed task on
failure.

Space anomaly uses the query classification field directly. It includes visited Atlas locations; the
old mission evaluator's additional visited-station exclusion is not a property of the system and is
not used. The enum remains native one-based, like biome subtype. Current positive runtime controls
cover Atlas and black holes; the other exposed native anomaly values currently have only negative
controls.

## Native ownership contracts

- Query storage has a native constructor/destructor and owns its metadata. A generated bit mask
  rejects repeated generation of one planet within a query. A TLS visitor observes the live planet
  during its destructor and retains only copied values. Recursive callbacks fail before aliasing.
- Private solar contexts construct the inline vectors and acquire/release their two native tables.
  Grown vectors use the game's release function.
- Private planet query contexts borrow the configuration graph while the gameplay callback waits.
  They own RNG state and the description hash cache at `+0xBB0`, including its pool chunks and
  active hash table. Full planet generation and the old object resolver are outside this ownership
  contract.
- Object filtering acquires the selected tables, reads `IsFloatingIsland` from source record
  `+0x15F`, then releases the acquisitions. Quality normalization writes only `+0x00..+0x47`; it is
  unnecessary for this flag. No output-object copies, sorting, or shared table normalization are
  performed.
- The optional query call at `0x14168F71D` retains an acquired table in the shared filename map
  through `0x141697BE0`. A Rust hook bypasses this registration only at that verified return address
  during an active search query, releasing the acquisition. Generator-initialization callers remain
  native.
- Native allocator TLS assigns process-lifetime pool slots with atomic xadd and has no observed slot
  release. Workers are reused, never created per query. The allocator's internal heap locks and
  atomic pool operations were inspected; native module TLS defaults initialize on Rust threads.
- Hooks use iced-x86 relocation and absolute jumps. Only verified straight-line prefixes are
  accepted. Other process threads are suspended during patching, instruction pointers in the
  replacement range cause refusal, and repeated thread snapshots establish a stable set. Modules and
  trampolines are pinned until process exit. MinHook was removed because its near relay allocation
  failed in Proton.

## Focused native evidence

Raw artifacts are under `games/no-mans-sky/investigation-state/runs/`.

| Contract                                      | Evidence                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Permitted save; purple-system native parity   | `20260924T194412Z-rust-purple-parity`: 64 systems, 323 planets, native/Rust comparison, save identity and screenshot                                                                                                                                                                                                                                                                                      |
| Selective capture                             | `20260924T195020Z-rust-capture-parity`: 969 captures and individual-colour comparisons                                                                                                                                                                                                                                                                                                                    |
| Solar lifecycle                               | `20260924T195914Z-rust-private-solar`: live bytes unchanged and table references balanced                                                                                                                                                                                                                                                                                                                 |
| Planet scratch/cache ownership                | `20260924T202655Z-rust-private-context-matrix`: private/native/private comparisons across 64 systems; native cache allocation evidence in `20260924T202321Z-exe-functions-5545bb71` and `20260924T202458Z-pool-link-range`                                                                                                                                                                                |
| TLS and allocator synchronization             | `20260924T203437Z-rust-collected-query`, `20260924T203508Z-allocator-metadata`, `20260924T203525Z-exe-functions-7ea517bb`                                                                                                                                                                                                                                                                                 |
| Rust hook and scoped workers                  | `20260924T213633Z-rust-hook-self-test`, `20260924T213651Z-rust-native-hook-workers`: one/two-worker parity, distinct native threads, reference balance and restoration                                                                                                                                                                                                                                    |
| Direct object flag scan                       | `20260924T215012Z-rust-object-flags-refcounts`: 323 planets, 10 positives, 38,189 objects agree with full resolver; all reference counts balance. Static contract: `20260924T214430Z-exe-functions-33ed3061`                                                                                                                                                                                              |
| Actual region addresses                       | `20260924T215422Z-rust-region-parity`: sixteen regions, two galaxies, distant/boundary/empty regions, noncontiguous purple indices                                                                                                                                                                                                                                                                        |
| Persistent workers and registration isolation | `20260924T220640Z-rust-persistent-workers`: 64 systems / 329 planets across nine regions and two galaxies; repeated one/two-worker parity, live bytes/reference counts/global filename-map header unchanged. Registration static evidence: `20260924T220335Z-exe-functions-53b2c6dc`, `20260924T220414Z-exe-functions-076064ad`                                                                           |
| Actual Rust filtering                         | `20260924T222344Z-rust-filter-matrix`: 349 cases over the 64-system corpus; all ordinary fields, flags, multi-select, resource conjunctions, and colour/weather/object criteria match native reference facts. One system generation and at most one generation per planet. Any requests no metadata, colour, or object scans                                                                              |
| Anomaly filtering                             | `20260924T223346Z-rust-anomaly-values-matrix`: classify 609 actual local systems; positive Atlas/black-hole controls added to 64-system matrix. Nine cases including mixed criteria and multi-select agree with native query fields. Rejected systems generate no planets. Static evaluator/classification evidence: `20260924T222609Z-exe-functions-a13dfa70`, `20260924T223205Z-exe-functions-70a124ae` |

| Scheduler, cache and worker scaling | `20260924T224817Z-rust-session-matrix`: 1,000 systems /
4,769 planets at each of one/two/four/eight workers have identical acquired facts. Every callback
preserves live generator bytes, solar/object references and the shared filename-map header. A new
blue-sky filter returns 100 cached matches with zero native generation. The original rare filter
resumes for 1,000 additional systems, then cancellation/resumption preserves its frontier. | |
Independent wider reference | `20260924T225148Z-rust-session-native-reference`: all known
fields/flags/resources/selected hues from the 1,000-system cache match fresh native queries across
all 4,769 planets. | | UI fixture | `20260924T230431Z-rust-ui-fixture`: compiled Rust egui window
runs under Proton; screenshots verify the powers-of-ten budget dropdown and cached results. This
fixture does not control the game. Live UI integration is covered by subsequent standalone evidence.
|

## Current standalone acceptance

| Gate                                   | Evidence and scope                                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ordinary Steam startup, no interpreter | `20260925T022820Z-rust-standalone`: Rust proxy self-start, loaded permitted address, no Python module in process maps. Initial asset-disabled timings are not enabled-mod performance evidence.                                                                                                                                                                                                                                           |
| Guide slots and native objectives      | `20260925T025308Z-rust-guide-destination`: actual empty slot opens editor, changed populated slot returns 100 cached purple matches with zero generation and forced UI opening. Native Log objective is visible.                                                                                                                                                                                                                          |
| Exact destination and reload           | `20260925T032639Z-rust-exact-navigation`: current planet 4 completes normally, local planet 2 and remote planet 3 retain exact addresses, duplicate selection is rejected, native Log abandonment removes mission/route. Reloading current permitted autosave retains remote planet-3 seed/route while clearing all search facts/results. Player position remains unchanged.                                                              |
| Enabled-mod search/cache/cancel        | Same exact-navigation run: 1,000 systems / 4,769 planets, cached 100 results with zero generation, Any has zero optional acquisition, cancellation and continuation pass.                                                                                                                                                                                                                                                                 |
| Expensive worker parity                | Same run, `worker-matrix/summary.json`: seven 1,000-system passes at 1/2/4/8/16/4/1 workers agree on all nine blue-sky/floating-island matches, 4,769 planet generations and 989 object scans. This exposed underfilled batches; it does not validate the revised scheduler's performance.                                                                                                                                                |
| Cache eviction and continuation        | Same run, `cache-eviction/summary.json`: 34 separate 1,000-system searches continue beyond the former graph ceiling, with exactly one solar generation per searched system. Cache reaches 16,384 and stays bounded through a further capacity of replacements. Each search takes at most 3.017 seconds. Whole-game RSS is about 3.78 GB, stabilizing across later eviction batches; this is not an isolated cache allocation measurement. |
| Isolated cache allocation              | `20260925T025308Z-rust-guide-destination/cache-allocation.txt`: full eight-planet/max-name cache retains about 41.2 MiB requested heap across four eviction cycles, excluding allocator bookkeeping.                                                                                                                                                                                                                                      |
| Normal shutdown                        | Candidate 05 normal native Quit to Desktop; candidate 06 exits both NMS and Rust UI; candidate 07 exits NMS through the native menu in the retained bounded observation. No signals used in these accepted exits.                                                                                                                                                                                                                         |
| Asset schema                           | `20260925T033934Z-verify-assets-8651ed4a`: all four authored EXML/MXML files compile/decompile with every authored leaf preserved. The generic host tool is independent of Search Probes product code.                                                                                                                                                                                                                                    |
| Packaging and licenses                 | `20260925T003652Z-rust-package-preparation`: crate/font/Rust/MinGW notices with source identities. Subsequent candidates verify all manifest hashes, ZIP entries and product-only contents.                                                                                                                                                                                                                                               |

## Current destination contract

The native SQN_SP_NAV mission seed carries the complete validated planet address. A hook on the
verified scan dispatcher reconstructs the owned FromList address from that seed. The native local
building resolver and its planet predicate are scoped to the exact owned event and mission context;
only the chosen planet qualifies. A fallback on a different planet is rejected before publication.
All other native missions retain their ordinary selection logic. The native mission owns
save/reload, route, completion and abandonment. No external target file or Python mission
implementation remains.

Guide launch intercepts the exact nine owned IDs at the native mission starter and queues a bounded
slot/epoch request for gameplay. Guide definitions have no scan requests or stages. The current
saved preset is read at launch; results/error/cache completion uses a distinct forced-show UI
counter.

## Accepted scheduler and table cache

Candidate 08 is installed transactionally in `20260925T034103Z-rust-scheduler-pages`. Its worker
matrix preserves all nine matches at every worker count. Minimum one system per requested worker
reduces elapsed time from roughly 17 seconds to 8–11 seconds for this expensive case, but active
native work remains roughly 7–8 seconds and the 16-worker maximum batch reaches 244 ms. This is not
useful linear generation scaling. Both before/after worker host-health checks pass. A subsequent
static-disassembly health snapshot records a transient i915 kernel worker; no measurements are taken
from that static command.

The full cached result-page control passes actual UI input: 100 replacement results have zero
overlap with the prior page. Partial preview continuation retains its earlier acceptance.

Candidate 10 is installed transactionally in `20260925T040022Z-rust-table-cache-guide`; candidate 09
was never installed. It adds a session-owned, bounded 1,024-entry cache of immutable source
object-table counts and floating-island flags, with filenames bounded to the native 256-byte path
representation. No native pointer or reference is retained. Its cache clears with the same
configuration/resource epoch as system facts, and explicit clear history also clears it.
Normalization writes only the earlier object fields; the selected source flag is immutable under the
established resource lifetime contract. Current native acquisition
(`20260925T034655Z-exe-functions-008acf1b`) holds a shared mutex across lookup and synchronous table
loading, explaining a plausible serialization boundary. The live worker matrix preserves all nine
reference matches at 1/2/4/8/16/4/1 workers. Each 1,000-system pass generates 4,769 planets and
scans 989 selections. Native table acquisitions fall from 20,234 to 169 with 20,065 summary hits. At
four workers the elapsed time is 1.41–1.54 s and active batch time 0.50–0.54 s; eight workers take
1.29 s elapsed and sixteen 1.30 s. These are ordered warmed samples, not sustained billion-system
evidence. Both host-health checks pass. New-region and all-skies searches reuse summaries; explicit
Clear History resets both caches.

Live Guide completion opens the existing hidden UI with Earthlike selected, the correct criteria and
three matches after 1,000 systems. Actual permitted-save reload advances the generation, clears all
system and object-table facts/results, preserves player identity, and then reproduces all nine
object-filter matches with 169 fresh table acquisitions. Raw results and screenshots are in the
table-cache-guide run's controls directory. Ordinary Earthlike budget was restored to 10,000 before
user QA; subsequent user-created presets and settings are user-owned and must be preserved.

Current source passes 70 Rust tests, including version-preserving archive naming. Windows product
builds, all archive hashes and product-only contents pass. The remaining host investigation suite
passes 61 tests after removal of obsolete Python product tests. Useful PE, HGPAK and MBIN tools
remain; no NMS.py or old product import is required. Related deleted dirty files are preserved under
the exact-navigation run's obsolete-source-snapshot.

## Release state

The current 0.1.0 package includes the responsive Rust UI and no Hide button. It was installed with
NMS stopped. The direct game runtime and asset links still resolve to Amethyst's `Root_Folder` and
`overwrite` sources, and all installed files match the release manifest. The unmanifested Python
runtime files were moved out of the live game directory into the rollback record. Exact package and
deployment evidence is in the
[UI release verification](../../../../games/no-mans-sky/investigation-state/runs/20260927T213746Z-search-probes-ui-release/release-verification.json).
The install was hash-verified; the game was not launched afterward. No Nexus upload was performed.

A user-initiated million-system search is separate from the bounded agent acceptance corpus. Do not
claim that no large search has ever run; no such search was initiated by the agent. Earlier
billion-system throughput limitations remain. System-location changes alone do not redirect the
stored frontier, but a warp or teleport may trigger native resource/lifecycle invalidation. An
actual warp during an active search has not been validated and uninterrupted continuation must not
be promised. Configuration invalidation is supported by inspected native fields and actual reload,
not a live language/difficulty-change experiment.

## Measurement boundaries and retained failures

The native pool still joins within the gameplay callback because it borrows game-owned configuration
and resources. It is not an unrestricted background generator. No billion-system or 100,000-system
live search was initiated by the agent. Warm ordered microbenchmarks and small completed samples do
not establish hours for a billion systems. Report active batch time separately from elapsed gameplay
time. Cold individual native work has exceeded 100 ms despite a 4 ms scheduling target.

The earlier host stall cleared after reboot; its timings remain invalid. The exact failure and
reboot records are retained under the package/resource-label runs. Candidate 04's navigation failure
was an incorrect pointer-field dereference and missing enabled assets; candidate 05/06 local planet
mismatch was a native path bypassing the remote publisher. Their failed artifacts are controls, not
accepted navigation evidence. Focused disassembly and bounded debugger proof are retained in the
Guide run and `20260925T030220Z` through `20260925T031648Z` function runs. No debugger remains
attached.

The unintended-save run `20260924T193005Z-rust-query-parity`, the zero-capture harness failure
`20260924T214919Z-rust-object-flags-balanced`, the MinHook relay failure, and degraded-host asset
extraction attempts remain rejected evidence. Purple coverage uses the permitted save only.
