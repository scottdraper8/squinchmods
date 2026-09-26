# Search Probes: generator isolation and throughput

## Decision supported by current evidence

Independent native generator contexts are a credible direction, but are not yet a proved worker
interface. The current synchronous query has mutable RNG in both its solar and planet generators,
hardcoded application-global accesses, and resource ownership outside those objects. Giving each
worker a copied generator and its own Python capture list is insufficient.

There is a separately demonstrated scheduling bottleneck. In the bounded local sample, allowing up
to 16 candidates and an 8 ms cooperative slice produced identical results and approximately 4.8×
basic-search throughput, 7.0× sky-colour throughput, and 6.6× Lush-plus-sky throughput. Unfiltered
floating-island searches remained dominated by object resolution and barely improved. These are
temporary diagnostic settings, not deployed product changes or general speed guarantees.

Reusing native generators should require less maintenance than reproducing NMS's procedural
algorithms externally. This is an engineering assessment, conditional on finding a narrow ownership
boundary. Native code continues to supply generation algorithms and installed data. We would still
maintain executable identities, function signatures, object layouts, resource leases, capture
ownership, and load/teardown synchronization. A design requiring widespread binary patches or
global-singleton swapping would lose much of that advantage and is not recommended.

## Evidence and scope

Target: NMS 7.04, public build 25442159, executable SHA-256
`b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`.

The
[runtime evidence directory](../../investigation-state/runs/20260924T184843Z-generator-concurrency/)
retains health gates, temporary instrumentation, responses, calculations, save backups and teardown.
Principal artifacts:

- [Timing and result-parity calculations](../../investigation-state/runs/20260924T184843Z-generator-concurrency/profile-analysis.json).
- [Per-search timing records](../../investigation-state/runs/20260924T184843Z-generator-concurrency/profile-fetch-3.json).
- [Native evidence index](../../investigation-state/runs/20260924T184843Z-generator-concurrency/native-evidence-index.json).
- [Restored runtime state](../../investigation-state/runs/20260924T184843Z-generator-concurrency/restored-runtime.txt).

All searches were capped at **64 systems**, with a result limit of 100 to prevent early completion
from changing the evaluated population. Five criteria sets were repeated. No 100,000-system or
billion-system search was run. Production source and deployment files were not edited, built,
committed or pushed. Temporary Python timing wrappers and scheduler settings existed only in the
investigation session and were restored before native detach.

The first control script incorrectly sent configuration/fetch/restore requests as `ping`, which the
mailbox answers without entering the gameplay callback. Consequently its 30 searches all used
default settings. `baseline-profile.json` records their actual empty configuration; filenames that
mention other settings do not demonstrate those settings. They are baseline evidence only. The
corrected script used queued `enumerate` requests intercepted by the diagnostic handler; repetitions
2 and 3 contain the actual comparisons. The first footprint installation also failed before
installation because an executor-local variable was unavailable to the executed module. Its
`footprint-query-*` results are ordinary enumeration, not context evidence. Only `footprint2-*`
results support the context findings below. These failed controls remain retained.

Doctor reported a healthy host before launch, before both profiling phases, after profiling, before
shutdown and after shutdown. NMS was launched normally through Steam; the installed package
self-started. The player was left idle. Native detach restored the hooks and closed the executor.
Alt+F4 did not end the process within the bounded wait; the subsequent window-close request did.
Final doctor found no NMS process and no uninterruptible processes. This is not a shutdown-latency
benchmark.

The launcher requested the newest `save7.hg` menu row. Before/after hashes show game-authored
changes to `save13.hg`, `mf_save13.hg`, `accountdata.hg` and `mf_accountdata.hg`; therefore the
requested row must not be treated as proof of the loaded save. The complete profile backup is
retained. No save file was manually edited or restored, and no movement, warp or navigation mission
was requested. The benchmark claims concern the actual sampled addresses, not a named save fixture.

## Measured scheduling effect

Means of two corrected repetitions, same 64 nearest remote systems per query:

| Criteria                            | Default systems/s | Cap 16, 2 ms systems/s | Cap 16, 8 ms systems/s | Default evaluation time for all 64 |
| ----------------------------------- | ----------------: | ---------------------: | ---------------------: | ---------------------------------: |
| No constraints                      |             110.6 |                  110.3 |                  526.9 |                            55.4 ms |
| Blue sky                            |              41.7 |                   81.1 |                  294.0 |                           105.9 ms |
| Lush and Blue sky                   |              41.7 |                   71.2 |                  276.3 |                           117.9 ms |
| Floating islands required           |              41.8 |                   41.6 |                   42.3 |                           943.6 ms |
| Lush, Blue sky and floating islands |              41.5 |                   71.1 |                  243.4 |                           138.6 ms |

Default wall times were approximately 0.58 s for the basic search and 1.53–1.54 s for the others.
The callback advanced around 42 times/s in this session; no 60 Hz assumption is needed. The current
one-system limit explains the approximately 42 systems/s colour ceiling here. Raising only the
candidate cap helps colour queries; the ordinary basic search already reaches its 2 ms allowance
before its four-system cap matters.

Result addresses, navigation addresses and complete copied summaries were identical across all six
corrected runs of each query. Match counts were respectively 64, 45, 4, 1 and 0. This covers one
small local population, not rare-system coverage, long-run stability, or gameplay usability at 8 ms.

Native calls remain non-preemptible. A default floating-island candidate took up to approximately 36
ms despite the 2 ms scheduling allowance. Increasing the allowance does not solve that spike. The
benchmark used fixed setting order and warmed repeated addresses; active evaluation costs also fell
in several larger-batch runs. Timing wrappers add overhead. Do not interpret the measured ratios as
universal or purely proportional to the slice setting, and do not infer FPS impact from search
throughput alone. Region expansion was not reached by these local 64-system runs.

### Where active time went

The wrappers record nested inclusive times. In particular, `run_solar_query` includes the Python
destructor-hook capture and, when requested, object resolution. Calling its whole duration “native
generation time” would overstate native cost. The following subtraction separates the measured
capture callback from that inclusive time; it is still elapsed time, not thread CPU time.

| Default query             | Query time excluding capture callback | Capture callback | Basic decode | Other snapshot work | Remaining candidate work |
| ------------------------- | ------------------------------------: | ---------------: | -----------: | ------------------: | -----------------------: |
| No constraints            |                               44.0 ms |           1.1 ms |       4.3 ms |              1.5 ms |                   4.1 ms |
| Blue sky                  |                               51.2 ms |          33.1 ms |       4.9 ms |             11.2 ms |                   5.1 ms |
| Lush and Blue sky         |                               77.2 ms |          20.2 ms |       7.8 ms |              8.0 ms |                   3.9 ms |
| Floating islands required |                               77.0 ms |         801.0 ms |       7.6 ms |             52.4 ms |                   5.1 ms |

Constructor/destructor timing contributes the small remainder. The unfiltered island path resolved
all 301 generated planets in these systems; that resolver includes native resolution, Python copying
and output cleanup, so its total is not a pure native benchmark. More precise attribution within
that resolver remains necessary before choosing its optimization.

Native query counts for these 64-system samples were 64 basic, 64 sky, 100 Lush-plus-sky, 128
islands, and 104 combined Lush/sky/islands. The last path resolved only four eligible planets. This
confirms both the cost of repeated generation and the benefit of filtering before expensive object
work. Always capturing every expensive property in one pass is not automatically an improvement.

## Native ownership findings

### Entry points and caller relationships

| Native location                | Current evidence                                                                                                                                                                                   |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0x14164D490`                  | Solar-query wrapper; resolves the live procedural root through the application singleton.                                                                                                          |
| `0x14163D6F0`                  | Solar query-info generation, with explicit generator pointer; seeds and mutates generator RNG at `+0x510`.                                                                                         |
| `0x141680070`                  | Planet query-info generation, with explicit generator pointer; seeds/mutates RNG at `+0xBA4`; creates and destroys temporary planet data.                                                          |
| `0x1413AE660`                  | Planet-generator constructor called on the procedural root's `+0x520570` member. Initializes vectors, RNG and self-relative container pointers.                                                    |
| `0x14167CBA0`                  | Planet-generator initialization called by the root initialization path. Acquires resources, builds collections, and interacts with shared registries/caches.                                       |
| `0x14167F340`                  | Later preparation/reset path, including resource-cache activity; distinct from the constructor.                                                                                                    |
| `0x141683260`                  | Generator resource-release/reset path called from the root lifecycle. Decrements shared resource references and clears per-generator collections. Not yet a complete isolated destructor contract. |
| Root constructor `0x1413ADC70` | Embeds the planet generator and constructs the solar generator at `+0x521180`, including inline-container self pointers.                                                                           |
| `0x14163D4C0`                  | Solar initialization; initializes RNG and acquires two resource references through a shared cache.                                                                                                 |

The
[wrapper and direct-call evidence](../../investigation-state/runs/20260924T184553Z-exe-functions-ace0e5b4/pe-functions/report.json)
and
[query bodies](../../investigation-state/runs/20260924T184632Z-exe-functions-dc68db84/pe-functions/report.json)
show that allocating a fresh solar-query _output_ does not allocate either generator. The wrapper
selects the live solar generator and live planet generator independently.

The
[constructor and initialization evidence](../../investigation-state/runs/20260924T184823Z-exe-functions-9a4f76b5/pe-functions/report.json)
and
[root construction](../../investigation-state/runs/20260924T184748Z-exe-functions-c16ada87/pe-functions/function-00000001413adc70.asm)
support native construction as a candidate approach. They also demonstrate why byte-copying is
unsound: container pointers can point back inside the original object. Copying pointer bytes does
not acquire a resource reference or create an independent container.

The
[release path](../../investigation-state/runs/20260924T185733Z-exe-functions-9de87b12/pe-functions/function-0000000141683260.asm)
modifies shared cache maps and reference counts. PE imports identify its lock/unlock calls at
`0x1434076E0` / `0x1434076E8` as MSVCP140 `_Mtx_lock` / `_Mtx_unlock`; `0x1434076F0` is
`_Mtx_init_in_situ`. This is affirmative evidence that some resource operations synchronize
internally. It does not establish coverage for all caches, initialization, query stages or unload.

### Measured mutable object footprint

Twelve additional single-system probes compared object bytes immediately before and after the
existing synchronous query: four addresses each for basic capture, colour capture, and object
resolution restricted to planet index zero.

- Within the planet object's `0xC10` bytes, changed offsets were only `0xBA4…0xBAB`.
- Within the solar object's `0x6E0` bytes, changed offsets were only `0x510…0x517`.
- The two inspected resource-cache headers remained unchanged in those warmed samples.

These are the independently identified RNG fields. This makes private RNG/context ownership
plausible. It is **not** proof of purity: writes through pointers, transient writes restored before
comparison, shared singleton/cache mutations, cold misses and unsampled branches are outside this
comparison. Only the initialized live objects were queried; no independent context was constructed
or run on a worker in this investigation.

### Dependencies beyond the generator object

The planet query explicitly re-enters the application singleton for name generation, a conditional
live procedural setting, biome/palette lookup and water-colour lookup. Several lower stages do so
again. The
[solar stage audit](../../investigation-state/runs/20260924T185056Z-exe-functions-ccf928d1/pe-functions/report.json)
and
[planet stage audit](../../investigation-state/runs/20260924T185820Z-exe-functions-e65a1711/pe-functions/report.json)
show that supplying a private `this` pointer does not redirect every dependency.

Some accesses are plausible stable-table candidates: biome collections and the water-colour table.
Others read application flags, current-address-related state, difficulty-related fields, time-linked
conditions and dynamically addressed collections. In particular, `0x141692ED0` calls predicates on
application `+0x4BF7F0` and traverses collections rooted at `+0x580BC0`; the latter's count helper
`0x140213210` dereferences a live array of pointers. These cannot simply be declared immutable
because sampled generator bytes stayed stable. The leaf predicate evidence is retained beside the
runtime artifacts; full closure over all indirect callees remains outstanding.

No supported background query submission interface was established. The planet query-info entry has
one direct caller, the synchronous solar-query wrapper. A second planet-generation entry has four
direct callers but also reads the singleton. Two callback registrations found in the loaded system
coordinator resolve live entity/component handles; they do not establish a detached system-search
job API. No exact code/data pointer references to the two query-info functions were found by the
address-reference scan. Direct-call/reference coverage is not proof that no alternative native
worker interface exists anywhere in NMS.

## Recommended isolation boundary and acceptance sequence

The preferred experiment remains **native generation with private contexts**, initially limited to
the smallest set of query fields whose dependency closure can be established. Keep the external
procedural-engine proposal out of the implementation plan.

1. Define ownership for both generator contexts, their inline containers, borrowed tables, acquired
   resources, mutable caches and temporary query/planet outputs. Prove matching release paths.
   Construct and acquire resources on the gameplay thread first. Do not call a whole-world cleanup
   function on a small independently allocated object.
2. Replace only the query orchestration in an isolated probe so it passes explicit context pointers
   to native solar and planet routines. Do not swap the game's application/procedural singleton.
   Catalogue and resolve every remaining global dependency: pin immutable resources with real native
   ownership, use a proved synchronization seam for mutable data, or retain dependent stages on the
   gameplay thread. Snapshotting data in Python alone cannot redirect a native global read.
3. Associate captures with the owning query/thread. The existing global capture flag/list and
   resolver's live-generator lookup must not service independent workers. Reject unrelated native
   planet destructors and copy all required values before destruction.
4. Establish serial parity with private contexts on the gameplay thread, including cold/warm
   resources, repeated A/B/A inputs, colour and resolver outputs, allocation guards and cleanup.
5. Establish one-worker parity and required native thread initialization; then two-worker overlap
   with disjoint contexts. Check live generator state, native output ownership, result
   repeatability, exceptions/cancellation and bounded queues. A lock solely around mod workers is
   insufficient.
6. Gate workers against save/galaxy changes, resource unload and shutdown: stop new work, drain or
   cancel safely, release resources in order, then allow the game lifecycle to continue. Epoch-based
   result rejection alone does not prevent use-after-free during an in-flight query.
7. Measure scaling with small bounded workloads and real gameplay contention before selecting a
   worker count. Native cache locks, memory bandwidth, Python capture and residual gameplay-thread
   stages may limit scaling. No CPU-core count should be advertised as an equivalent speedup.

These are outstanding proof gates, not an implemented worker design. Current evidence reaches a
concrete prototype boundary; it does not justify running existing native queries concurrently.

## Performance priorities and maintenance

The measured scheduling headroom supports an independently useful configurable search intensity,
subject to frame-time validation. Capture requirements should be narrowed, cheap predicates
compiled, and duplicate native generation investigated while preserving early rejection. Names and
display data need not be generated eagerly if an exact native seam permits deferral. Floating-island
resolution deserves its own profile before choosing caching, reduced copying or native changes.

| Design                               | Update responsibility                                                                                                                                                                  |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Existing synchronous native queries  | Executable bindings, decoded fields, hook and lifecycle validation.                                                                                                                    |
| Private native contexts              | Existing responsibilities plus constructor/resource ownership, context layout, capture routing and concurrency/load guarantees. Algorithms and game-data interpretation remain native. |
| External procedural reimplementation | Procedural algorithms, RNG/seed behavior, data interpretation, special cases and parity across game/mod updates, as well as the external runtime.                                      |

The private-context approach is expected to be less maintenance than an external engine, and more
maintenance than the present synchronous query. Its maintenance advantage depends on keeping the
native integration narrow; it is not update-proof and cannot bypass executable-version validation.

A billion systems still requires approximately 11,574 systems/s for 24 hours or 34,722 systems/s for
8 hours. Even the temporary 294 systems/s sky result would extrapolate to about 39 days. That is
arithmetic from a small sample, not a billion-system measurement. Reaching hours requires a much
larger combined gain from avoided work, efficient capture and actual parallel generation. The
current billion-system limit is a traversal/budget capability, not a demonstrated practical scan
duration.
