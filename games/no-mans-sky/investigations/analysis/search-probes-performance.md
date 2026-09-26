# Search Probes: concurrency, filtering, reuse, and multi-select

## Scope and evidence

Report-only investigation of Search Probes commit `2eeb5864d295de7edc33163ede79e7bdfe41b436`. No mod
source, installed runtime, preset, or save changes; no build, deployment, push, or live search.
Recommendations below describe possible future work, not implemented features.

Source inspection was supplemented by six existing Any/sparse-filter tests and a host-only probe
using the real matcher and engine orchestration with synthetic snapshots in place of native calls.
The probe checked all 66 snapshot fields that accept Any, field access for an unconstrained match,
and the generation stages selected by representative queries. Three previously retained native
snapshots provided deterministic serialization-size examples. They are not a galaxy-wide sample. The
doctor sample contained a graphics worker in D state; no host timing, throughput, RSS, or
allocation-performance conclusion is drawn from it.

Raw evidence:
[tests](../../investigation-state/runs/20260924T182749Z-search-performance-report/any-tests.log),
[probe source](../../investigation-state/runs/20260924T182749Z-search-performance-report/probe.py),
[probe results](../../investigation-state/runs/20260924T182749Z-search-performance-report/probe.json),
[storage calculations](../../investigation-state/runs/20260924T182749Z-search-performance-report/storage.json).

## 1. Concurrency and parallelization

The [generator isolation and throughput investigation](search-probes-generator-concurrency.md) adds
bounded live timing comparisons, context-mutation probes and current-executable lifecycle evidence.
Independent native worker contexts remain unproved; the product still uses the scheduler described
below.

| Boundary                               | Current behavior                                                                                                                       |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Owned form                             | One active search; another submission is refused until it completes/cancels.                                                           |
| Scheduler                              | Up to eight active searches, interleaved rather than running native generation in parallel. Surveys have a separate eight-state limit. |
| Mailbox                                | Command queue capacity 64; one queued command is advanced per gameplay callback.                                                       |
| Ordinary search slice                  | At most four systems, stopping before another is started once the slice has consumed 2 ms.                                             |
| Colour or floating-island search slice | At most one system per callback.                                                                                                       |
| Region generation                      | One region occupies its own callback, without candidate evaluation in the same slice.                                                  |
| Native call                            | Cannot be interrupted at the 2 ms boundary; a single call can exceed it.                                                               |
| Paused gameplay                        | Search work pauses, including in the Galaxy Map.                                                                                       |
| Background threads                     | Owned form and mailbox/file work already run separately.                                                                               |

The generation number is another concurrency restriction: a newer ordinary command makes older
non-Guide requests stale. Guide requests are exempt from that stale check. The scheduler's eight
slots therefore do not mean users can launch eight independent form searches or obtain eight times
the generation throughput. Commands deliberately sharing a generation can be interleaved.

Native generation is currently serialized for concrete reasons:

- `SearchEngine` has one shared capture-enabled flag, capture settings, captured-planet list, error
  slot, and set of requested object-list planet indices. The global planet-destructor hook writes to
  this state. Concurrent calls would mix captures even before considering NMS internals.
- Object-list resolution uses the live procedural generator, inspects its caches, advances its RNG,
  and restores that RNG afterward. Interleaving another caller between save/restore is unsound.
- Native resources, global game state, hook callbacks, destruction, and lifecycle are validated on
  the gameplay thread. Caller-owned output arrays alone do not establish thread safety.
- A lock around our workers would not synchronize with NMS's other callers of its own generator.

The isolated region constructor is a narrower candidate for future thread-safety investigation, but
the current evidence proves isolated ownership on the gameplay thread, not worker-thread safety.
Moving it or solar generation to a pool is not presently justified. This is a proof boundary, not
proof that every conceivable implementation must be single-threaded.

Pure processing of immutable copied data, cache indexing, compression and disk I/O can be separated
from native acquisition. A bounded producer/consumer queue would be required. CPU-bound Python
threads still face the standard CPython GIL; processes or a native implementation can parallelize
that pure work, with serialization overhead. The native `WINFUNCTYPE` calls release the GIL, so
claiming the GIL alone prevents parallel NMS calls would be incorrect. Releasing it does not make
the game functions safe. See
[Python threading](https://docs.python.org/3.13/library/threading.html#gil-and-performance-considerations)
and [ctypes](https://docs.python.org/3.13/library/ctypes.html#ctypes.WINFUNCTYPE).

Sources: `resident_search_overlay.py:777`, `resident_search_probe.py:386`,
`resident_search_probe.py:642`, `search_scheduler.py:24`, `native_layout.py:101`,
`search_engine.py:31`, `search_engine.py:365`.

## 2. What Any actually skips

**Any means no filtering constraint. It does not mean zero work associated with that property.**

Verified behavior:

- The form omits Any fields from submitted criteria. Preset normalization also strips Any values.
- Optional colour, weather, metadata and floating-island acquisition gates remain false when their
  whole group is Any. Native scan-event fields are reset to neutral values before selected fields
  are enabled, so the template's original Lush restriction does not leak into an Any search.
- All 66 snapshot criteria accepting Any were neutral in the bounded fixture probe.
- Ordinary selected enum comparisons short-circuit when absent/Any.

Remaining work despite Any:

- The matcher still visits many unselected tri-state clauses. Their actual arguments are evaluated
  before `_tristate_matches` returns true for an absent constraint. An empty query made **35** such
  calls for the first accepted fixture planet, reading values including size, rings, water and
  sentinel flags. It also visits the colour/weather clause loops, although absent selectors skip
  their value comparisons.
- Basic query decoding builds planet fields and system aggregates whether selected or not. Planet
  names are captured for every generated planet. This is distinct from applying a filter.
- Capture granularity is grouped: selecting sky Blue enables collection/decoding of the supported
  colour palettes and selected atmosphere/water colours, not only the sky field. Grass Any therefore
  does not guarantee no grass-colour work while Sky Blue is selected.
- Optional capture guards do not prove that NMS's own type-1 generator avoids computing those
  properties internally.
- Direct diagnostic protocol input can retain explicit Any values. `anomaly=Any`, for example,
  enters the native-predicate path; the equivalent empty form query does not. No anomaly restriction
  is enabled, but extra work can occur. Sparse canonicalization should apply at every entry point.
- The native evaluator defaults exclude some system categories. Unconstrained requests can need
  supplemental pirate/empty/abandoned passes to implement correct Any semantics.

A compiled list of active predicates would eliminate unselected matcher clauses. Separate capture
requirements should specify exactly which facts those predicates and result presentation require.
This is an optimization opportunity; no such change was made in this investigation.

Sources: `overlay_form.py:136`, `resident_search_protocol.py:314`,
`resident_search_protocol.py:694`, `system_query_snapshot.py:316`, `planet_data.py:355`.

## 3. How a search produces and retains data

The budget counts **systems**, each of which can contain several planets. It does not count planets.
The decoder supports up to eight planet records per system. Results currently contain the first
matching planet in each accepted system, not every matching planet in that system.

Typical generated-data path:

1. Obtain a candidate system address from the nearby index or a generated region.
2. Construct an owned native solar query and run NMS's type-1 planet-info generation.
3. Copy basic query data and selected planet details while temporary planet objects are alive.
4. Destroy native query/output objects, then decode Python-owned values.
5. Apply system predicates and same-planet predicates; return either rejection or a matched planet.
6. Keep a result summary for an accepted system; discard the unsuccessful snapshot from the search.

The native-only path initially receives a Boolean native predicate result. If accepted, it also
obtains generated data to produce a concrete planet destination and summary. Thus the system is not
merely a database of yes/no answers: generated data are obtained, then mostly discarded.

For the blue-sky example, the other nine non-matching planets are **not retained as searchable
history**. Their colours may have been captured temporarily, together with additional palette data,
but no cache receives them. Other planets in an accepted system are also absent from the retained
single-planet result summary. One last query's capture scratch list can remain until the next query;
that is neither indexed history nor a reusable cache.

| Data               | Retention today                                                                                                  |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Rejected snapshots | No historical collection, disk record, or query cache.                                                           |
| Current traversal  | Initial nearby address set (at most roughly 20,000), one generated region, iterator/counters.                    |
| Accepted systems   | Up to 100 result summaries per search, with addresses and one matched planet's copied properties.                |
| Form history       | Completed/cancelled result sets in UI memory; no search of that history for new criteria.                        |
| Mailbox files      | Commands, overwritten progress files, and final result JSON under `.resident-search/sessions/<session>/results`. |
| Logs               | Progress/results and diagnostics; not a rejected-planet catalogue.                                               |

The last two structures are not equivalent to a reusable catalogue. History has no session-wide
result-count eviction policy, and the current pyMHF file logger does not rotate its file. Progress
is emitted every 64 evaluated systems or one second. At huge scale, logs and command history
therefore also need retention limits even though active traversal storage is bounded.

The exact call ordering differs from the older plan's statement that native predicates run first.
Most ordinary form fields use the snapshot path. With both snapshot and native-only fields, the
native predicate runs after snapshot acceptance. Basic 'preliminary' filtering already uses a full
type-1 query. The host orchestration probe demonstrated:

| Criteria                           | Solar snapshot calls for a candidate reaching the final stage      |
| ---------------------------------- | ------------------------------------------------------------------ |
| Sky Blue                           | 1 with colours                                                     |
| Lush + Sky Blue                    | 1 basic, then 1 with colours                                       |
| Lush + Sky Blue + floating islands | 1 basic, 1 with colours, then 1 with colours and object resolution |

These are code-path counts using synthetic data, not timings or native benchmarks. Eliminating
repeated generation while preserving early rejection and native-object lifetime is a useful
performance investigation before attempting native parallelism.

Sources: `search_engine.py:158`, `search_engine.py:418`, `search_scheduler.py:115`,
`system_query_snapshot.py:610`, `resident_search_overlay.py:411`, `resident_search_probe.py:1003`;
bundled `pymhf/injected.py` uses `logging.FileHandler`.

## 4. One billion systems: storage feasibility

The current design does not retain one billion snapshots. Its core active-search storage is bounded,
though the history/log caveats above still apply. Retaining a complete property catalogue would be
an entirely different storage commitment.

Illustrative decimal sizes, before indexes/container overhead:

| Representation for one billion systems                       | Payload                               |
| ------------------------------------------------------------ | ------------------------------------- |
| Only one 64-bit address per system                           | 8 GB                                  |
| Two outcome bits per dense system position                   | 250 MB, plus the mapping to addresses |
| 32 bytes per system + five 32-byte planet records per system | 192 GB                                |
| 1 KB per system                                              | 1 TB                                  |

A Python dictionary per system/planet adds substantial overhead to packed representations. Three
retained five/six-planet samples serialized to approximately 4.1–4.8 KB with basic fields and
32.7–39.6 KB with colour captures. Applying those particular sizes to a billion systems would mean
about 4–5 TB or 33–40 TB of JSON respectively. These are sample illustrations, not a population
estimate, and a minimal cache should avoid retaining full palette JSON.

A dense bitmap is not free address lookup: native system indices are discontinuous, and arbitrary
queries need coverage/index metadata too. Approximate membership must never be allowed to hide an
unsearched system because of a false positive.

Session-only retention is feasible with a **bounded** cache. Keeping complete arbitrary property
records for every system in a billion-system search in ordinary RAM is not a reasonable default. A
persistent or temporary disk database would need explicit byte limits, compact records, indexes,
background writes and eviction. A separate compact traversal record avoids needing a property record
merely to remember that a same-query search already covered a region.

## 5. Recommended separation: progress, facts, and query results

This is a proposed design, not functionality present today.

### Query progress

Keep a canonical query identity and its origin/traversal policy separately from search/result
limits. Normalize away Any, aliases, and ordering differences in unordered selections. A repeat with
the same predicates but a larger requested result count should share progress.

For an anchored sequential scan, retain the iterator/frontier, partial-region position, initial
nearby exclusions, successfully evaluated coverage, and matched-address state. Completing or
cancelling a request would preserve this state in the session rather than dropping its stream.
Coverage must be advanced only after successful evaluation; errors, merely enumerated systems,
current-system exclusions and cancellation must not become false 'searched' records.

A single traversal can describe an enormous completed prefix compactly. Multiple independently
anchored, overlapping searches need explicit region coverage and partial-region records; a lone
cursor does not represent arbitrary unions. Previously checked locations must remain distinguishable
from cached facts that were later evicted.

### Generated facts

Use a separate bounded catalogue keyed by galaxy/system/planet address and a generation-context
identity. Store copied primitive fields and **availability masks**. Missing sky colour means
unknown, not 'not blue'. Acquire only missing required groups when a later query cannot be decided.

A safe key/invalidation boundary includes executable/data/mod generation, schema/algorithm version,
loaded-save/session epoch, galaxy and relevant difficulty/settings. Some values are stable generated
facts, while discovery/native predicates and difficulty-derived values need separate freshness
rules. A same-session cache is not automatically valid across save loads or difficulty changes.

Retain concise facts such as biome/size enum, hue classification or RGB, selected flags and resource
IDs; full object-list structures, native pointers and full palette arrays are unnecessary for most
query reuse. Names and display summaries can be produced only for selected results. Whether to add
facts for every inspected planet or only selected groups is an explicit storage/capture tradeoff.

### Query results

An exact-query result/coverage cache can reuse a rejection for that same canonical query and
context. A rejection for X cannot be assumed to reject Y. A positive X result can satisfy Y only if
the facts needed for Y were captured and Y is explicitly evaluated. Changing thresholds or adding
criteria can require more acquisition even when the system was previously visited.

Bound cached positive results, cached facts and per-query histories separately. If matching facts
are evicted, a progress record still permits continuing elsewhere, but cannot reconstruct all old
matches instantly. Exact exhaustive recall requires retaining a larger catalogue on disk; it cannot
be promised by a bounded RAM cache.

## 6. Location and continuing elsewhere

Current searches remain tied to the **starting location and current galaxy**:

- Every new request starts with the current nearby index.
- Its region shells are centered on the starting system's region.
- That origin stays frozen during the active search. Changing galaxies aborts it.
- A repeated search creates a fresh stream. At the same location it traverses the same systems.
  Moving changes the starting point but does not provide cross-search deduplication.

The graph no longer bounds reach, but it still seeds the initial ordering. A useful future UI would
separate **Continue this search**, **Search near current location**, and **Restart**. Continue would
retain the previous anchor and frontier even if the player moved within the galaxy. Explicit remote
anchors could also use the new region traversal, although initialization currently requires the
player's active graph and would need to be separated for that mode.

## 7. Set X followed by Set Y

The proposed flow is feasible:

1. Evaluate Y against the bounded session fact catalogue off the native generation path.
2. Show: **N matches found in previously searched systems**, with those results immediately usable.
3. Explain that cached coverage can be partial. Systems with missing required facts remain unknown.
4. Offer **Continue live search**, fetching missing data and searching fresh addresses; merge and
   deduplicate results already shown. Apply the same result cap and count cached/new work
   separately.
5. Revalidate dynamic predicates and current-galaxy navigation eligibility before presenting a stale
   record as a confirmed current match.

The current historical match summaries alone can offer a limited first step for Y, but they omit
rejected planets, non-selected planets in accepted systems, and uncaptured fields. They cannot
provide the full catalogue behavior described above.

## 8. Multi-select

Multi-select is feasible in the copied-snapshot filter, but the current protocol accepts one enum
value and rejects `planet_size=[...]`. The UI, normalized criteria schema, preset/Guide loading,
cache identities and evaluator would all need to agree on the new representation.

For the user's example, sizes **Large, Medium, Small, Giant** mean 'any of these sizes', excluding
Moon. Values within one field use OR; different fields still use AND on the same planet. Evaluate
membership against one generated snapshot; do not run a separate native search for each combination.
Treat All as Any, define empty selection explicitly, and convert older scalar presets to singleton
selections without losing their meaning.

| Candidate consolidation                                           | Assessment                                                                                                                            |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Size, biome, star type, race, economy, weather type, hue families | Natural multi-select enum controls.                                                                                                   |
| Three resource selectors                                          | One resource picker can replace them while keeping explicit **all selected resources required**; an OR mode must be separately named. |
| Planet flags such as rings, moons, water and islands              | Group visually with Require/Exclude/Any; they are independent facts, not mutually exclusive enum values.                              |
| System 'contains' flags                                           | Group, but preserve whether all or any selected conditions are required and whether different planets may satisfy them.               |
| Giant/non-gas giant                                               | Related to size and GasGiant biome, but consolidation must preserve `size=Giant AND biome!=GasGiant`; size alone is insufficient.     |
| Floating-island terrain versus resolved floating-island objects   | Keep distinct semantics; they are not interchangeable.                                                                                |
| Water, deep water and Waterworld biome                            | Related but not interchangeable, and planet-level versus system-level scope must remain explicit.                                     |
| Minimum planet count                                              | A threshold, not an OR enum selector.                                                                                                 |

Native scan-event fields typically encode a single selection. Multi-value criteria should be
post-filtered from copied snapshots where supported, rather than placing a list in a scalar native
field or issuing a Cartesian product of native queries.

## Suggested implementation order

1. Compile/canonicalize active predicates, instrument stage costs, and investigate duplicate native
   generation plus capture of unrequested colour groups. Keep measurements bounded.
2. Preserve per-query continuation and bounded exact-query results in the session.
3. Add a bounded fact cache with availability/freshness metadata and the cached-results/live-search
   UI.
4. Add multi-select using the same normalized predicate representation.
5. Evaluate background pure-data processing or a narrowly proved native concurrency seam only if
   measurements justify the ownership/lifecycle work. Add log/history retention limits for long
   runs.
