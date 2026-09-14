# System Search

This is the current-state working record for the No Man's Sky system and planet finder. Replace
conclusions when stronger source or runtime evidence changes them. Raw results remain in retained
run/session artifacts; this file is not a changelog.

## Current product decision

System Search has two deliberately separate UI surfaces:

- An owned, F7-toggleable window composes searches, manages named presets, reports progress, retains
  results, and can publish a selected destination through a disposable Search Probe navigation
  mission. It is injected Python/DearPyGUI and does not replace an NMS layout. A completed form
  search is only a result set until the user explicitly selects a result and presses **Navigate to
  selected result**.
- One additive **Search Probes** category in Catalogue & Guide lists the preset snapshot loaded when
  the resident runtime attaches. Launching a probe runs that exact preset in the background and
  publishes the closest match through NMS's ordinary mission and Galaxy Map navigation path. The
  probe language is an in-universe presentation of the bounded procedural query; it does not claim
  that a persistent physical object travels through the galaxy.

This is preferable to a base/freighter part because it works anywhere, and preferable to a new
top-level NMS tab because a tab would require substantially broader exact-build layout, input, and
lifecycle hooks without improving the search engine. The additive Guide data does not replace shared
Guide layouts and does not overlap the files changed by BG Dark UI and Fonts.

The form and Guide are not the execution thread. They submit immutable commands to a bounded
mailbox. Every procedural generator, candidate evaluator, object-list resolver, and navigation call
runs cooperatively on the gameplay thread. Worker threads perform only owned UI and filesystem work.
The procedural engine is not called concurrently because its caches, constructors, temporary
objects, RNG, and destructors have not proved thread-safe.

The production package is self-starting. NMS imports only `timeBeginPeriod` and `timeEndPeriod` from
WINMM, so a minimal application-local 64-bit `winmm.dll` forwards exactly those exports to the
system DLL and starts the bundled Python 3.13 runtime in-process. The bootstrap waits for the NMS
window, verifies the exact executable hash, initializes pyMHF, and installs the resident bridge. On
Proton the installer configures a native-first per-application WINMM override. An ordinary Steam
launch is sufficient; no host Python process, injector, or repository script remains running.

The form's hotkey listener starts without importing DearPyGUI or creating a graphics window. The
first F7 press creates the viewport; subsequent presses toggle it. This keeps optional form graphics
initialization out of the native bootstrap and Guide lifecycle. Guide status, completed searches,
and navigation handoffs never auto-show it. The UI loop polls Win32 `GetAsyncKeyState(VK_F7)` for a
rising edge; it does not depend on a global Python keyboard hook. Listener readiness and viewport
readiness are separate diagnostic events.

An idle form is activatable so text and controls work normally. Starting a form search briefly hides
it, returns Win32 focus to NMS, applies `WS_EX_NOACTIVATE`, and remaps it without activation. It
continues rendering live progress while procedural work advances through NMS's gameplay callback. If
Wine refuses the foreground transition, the form stays hidden instead of stalling the search. Once
work finishes, the no-activate style is removed. UI-thread failures are emitted to the resident log
rather than becoming silent hotkey failures.

The build produces a Nexus-rooted expanded directory and ZIP, then installs transactionally by
default. The package contains the native forwarder, embedded runtime, owned application code, and
the four loose Guide, localization, Wiki mission, and NPC mission adapter files. It preserves user
preset files on update and fails closed on a foreign WINMM proxy. The old external attach launcher
remains only a development fallback and must not be used alongside the native bootstrap. Native
Windows follows the ordinary application-local DLL loading contract but remains a separate
runtime-validation target; current proof is on Proton.

## Preset and Guide contract

The effective library contains zero through **nine** presets. Nine is the product maximum because
the native topic panel renders nine reachable rows and exposes no scrolling path: a 64-record owned
array was memory-safe, but only rows one through nine could be selected. Preset names are one
through 80 Unicode characters and unique case-insensitively. NMS topic labels have a separate
31-byte fixed-string limit; longer names receive a deterministic, UTF-8-safe slot suffix in Guide
without changing the full stored name.

The sole shipped default is **Earthlike**. It requires a Lush planet satisfying the current
executable's exact Paradise predicate, generated Green grass and Blue sky primary-hue families, and
at least one moon. NMS currently exposes a proved has-moons relationship here, not an exact one-moon
count. Generated hue families are procedural palette inputs rather than guarantees about final
rendered pixels. The default is an ordinary record: users can overwrite or delete it, save up to
eight additional presets, reach zero records, and restore the default without deleting custom
records. Saving never launches a probe. Selecting a preset first resets every form field, then
applies its criteria and limits, so stale values on hidden tabs cannot constrain it.

The whole library is schema-versioned and atomically replaced; the previous valid file is retained
as a backup. Persistence is completed before the in-memory list changes. A failed write leaves the
visible library unchanged. Maximum systems is an editable decimal text field validated from one
through the proved 20,000-system boundary; result limits are one through 16.

The data adapter precompiles nine Wiki probe missions (`SQN_SS9_P00` through `P08`), each with a
request, ready, and target table-3 scan event. Form navigation starts the disposable, non-repeating
Secondary mission `SQN_SS11_NAV` from the additive NPC mission table. It has no auto-started form
listener. The runtime validates the selected galaxy, rejects an active or pending target, patches
its owned single-entry `FromList` destination, and calls NMS's native mission start function with
restart disabled and selection enabled. NMS owns its stage progression and target event. The form
reports navigation success only when both the native mission and its exact route are active.

The native start function and manager ownership are verified against current `GcRewardMission` and
`GcMissionSequenceStartMission` callers. The earlier RPC/request-manager path is not a valid
mission-engine start seam; its retained records do not prove a gameplay-phase timing problem. Exact
addresses, byte prefixes, request layouts, and raw disassembly are linked from the
[lifecycle evidence](../../../../games/no-mans-sky/investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json).
Do not use stale generated SDK layouts as native ownership evidence.

Abandon the current Search Probe Target before selecting another. Each native target mission ends
its event and leaves the Log on abandonment or arrival. Guide searches retain their launching slot's
native context independently. At attach, the runtime finds its one additive category, clones the
source topic into one runtime-owned array, writes current user labels and exact slot missions, and
swaps only that category's topic header. All published arrays stay alive until teardown; teardown
restores the original 16-byte header before releasing callback or array storage. If the library is
empty, the category contains one inert **No search probes saved** row. A true zero-length topic
array reproducibly crashes NMS.

The Guide snapshot is immutable for one resident session. Preset edits are immediately persisted and
usable from the owned form, but the native Guide reflects them on the next NMS/runtime launch. This
is a safety contract, not unfinished UI polish: changing the loaded topic records while the Search
Probes page is open reproducibly strands NMS even when the pointer, allocation, and array length
remain unchanged. The runtime cannot currently prove whether that page is closed, so it does not
guess and does not live-mutate Wiki state.

## Guide icon selection

The current-build icon catalogue is retained under
`games/no-mans-sky/investigation-state/runs/20260914T024121Z-extract-5e929fa3/wiki-guide-icon-catalog/`.
It contains all 113 nonempty DDS paths referenced by current vanilla `WIKI.MBIN` icon-bearing
fields, the original DDS files with archive provenance, PNG previews, an HTML index, a JSON
manifest, and separate category, topic/page, and notification contact sheets. This is the
conservative proven choice set: every included icon is already used by vanilla in a Wiki field. The
Search Probes category tab uses the frontend `MISSION.BLACKHOLE.ON/OFF` pair. Preset topics and
their article pages deliberately use HUD `EXPLORATION4` (catalogue #085), while notification
contexts use HUD `EXPLORATION2` (catalogue #083). Vanilla uses #085 as a notification icon rather
than a topic/page icon, so its selection is structurally supported but its topic/page presentation
must be checked in game for acceptable sizing.

## Search pipeline

For each request the runtime:

1. resolves the live current galactic coordinate and RealityIndex and asks that galaxy's active NMS
   spatial graph for nearby systems;
2. rejects the current system, requires every candidate address to carry that same RealityIndex, and
   visits the remaining candidates in native rank/distance order;
3. applies cheap system predicates and native scan-event predicates first;
4. invokes the type-1 solar query only when generated planet/system data is required;
5. copies fixed values from temporary solar and planet objects before their destructors run;
6. applies all target-planet predicates to the same planet and system aggregates across planets;
7. resolves object-list records only after every cheaper predicate has left an eligible planet;
8. retains only copied values, the matched generated planet index, and stable galactic addresses;
   and
9. converts zero-based generated planet index `n` to NMS's one-based universe-address planet value
   `n + 1`, writes the resulting 16-digit address into an owned `FromList` event only if its
   RealityIndex still matches the player's current galaxy, and releases the waiting mission so NMS's
   native `StartScanEvent` resolves and publishes the target. Address value zero means system-only
   and is never used for a matched planet. A system-only match selects the first generated planet as
   its concrete arrival destination.

Native `cGcScanEventManager` publication carries a 24-byte mission ID/seed context in addition to
the event and address. Direct low-level publication was rejected by runtime evidence: it could add
an apparently correct remote record yet lose locality at system or planet arrival. The accepted
Guide-slot SS9 contract uses low-level publication only for the local internal **ready** signal. The
resident runtime patches the single owned 16-character `UAsList` buffer in the target definition,
publishes the ready signal with the captured launcher context, and stops. A native mission
`GcMissionSequenceStartScanEvent` stage then resolves `SolarSystemLocation=FromList` and owns the
target publication, mission association, Galaxy Map route, system transition, planet marker, and
teardown. This is the same ownership boundary demonstrated by Lush Finder rather than a simulated
version of it.

Guide slot missions use that native target sequence directly. Form navigation has a separate,
disposable `SQN_SS11_NAV` Secondary mission from the additive NPC table: it has no hidden reusable
Wiki listener and no SS9 ready handoff. Its owned `FromList` target is patched before the native
mission start; the form reports success only after the mission and its exact route are active.
Native mission stages own locality, completion, and Log teardown. Abandoning the target is required
before another form navigation request, and an abandoned Guide mission cannot publish a route.

Candidate enumeration is frozen to the galaxy active when a search initializes. Changing galaxies
mid-search aborts that search with an actionable retry error, because mixing already-evaluated
candidates from one graph with another graph would be unsound. Explicit navigation to an older
result from another galaxy is rejected for the same reason.

The requested candidate count is an upper bound. NMS's active spatial graph may contain fewer
indexed systems than requested; the engine returns at most that graph count and Search Probes then
removes the current system. For example, a 10,000-system request against a 7,195-entry active graph
correctly evaluates 7,194 remote systems. Current evidence does not establish whether graph size is
caused by galactic-edge position, graph partitioning, or another native loading policy. Searching
beyond the active graph would require a separately proved coordinate-space/region enumerator.

`Any` is omitted from the sparse query and therefore incurs no check for that field. Weather,
palette, and fixed planet metadata are captured only when requested. Object-list resolution is last
and processes at most one candidate system per update. Ordinary generated/weather searches process
at most four candidates per update and stop scheduling after a 2 ms cooperative slice; one native
call cannot be preempted.

Up to eight independent search commands may be active, but they are interleaved on the gameplay
thread rather than executing NMS generation concurrently. This keeps UI/gameplay responsive and
avoids asserting nonexistent generator thread safety. Because advancement is driven by that gameplay
update path, NMS states that suspend simulation—observed with the Galaxy Map—also suspend probe
progress. The request and its completed work remain intact and resume when gameplay updates resume;
this is not an overlay-refresh failure or a cancelled search.

## Criteria exposed in the form

Every advertised choice has a current-runtime generated field and positive control. `Any` gates the
field out entirely.

### Target planet

- Biome: the 15 values observed in the current full graph, including Lush, Waterworld, and GasGiant.
  The schema-only Test value is withheld.
- Observed biome subtypes and 30 observed terrain archetypes.
- Planet size: Large, Medium, Small, Moon, and Giant.
- Exact FloatingIslands/FloatingIslandsPrime/FloatingIslandsPurple terrain family.
- Object-backed floating islands through the resolver-selected native `IsFloatingIsland` flag,
  independently of the terrain family.
- Non-gas Giant, rings, one-or-more moons, water, and deep water.
- Up to three generated resource IDs as a same-planet conjunction.

### Environment and life

- Exact current Paradise-label predicate: Lush biome; subtype other than Structure, Infested, or
  Swamp; Default weather intensity; `StormFrequency=None`; and the difficulty-selected Low sentinel
  level. HighQuality is not required.
- Generated life (Dead/Full), creature abundance (Dead/Low/Mid/Full), observed building-density
  values, and resource abundance (Low/High).
- Storm frequency None/Low/High, weather intensity, and the 14 generated weather types observed in
  the current graph.
- Extreme-weather, hazard, sentinel, corrupt-sentinel, sentinel-presence, prime-generation,
  infestation, ordinary-group, relic, RGB-biome-group, scrap, and creature-suitability flags.
- Positively observed generated primary hue families for grass, plants, leaves, water, near-water,
  clouds, sky, horizon, sky fog, height fog, sunset, and night sky. Each palette uses its own
  observed-value choices.

`StormFrequency=None` is the exact absence of normal generated storms. Excluding the extreme flag is
weaker. Scripted missions, expeditions, seasons, or runtime overrides are not an off-screen
procedural property and cannot be guaranteed. Generated hues are searchable generation inputs, not
promises about final rendered pixels after atmosphere, weather, lighting, time, biome filters,
graphics settings, HDR, and post-processing.

### Star system

- Star colour and minimum planet count one through five.
- Wealth/economy, trading class, conflict level, and pirate status.
- Generated population state: inhabited/settled, empty/uncharted, or abandoned.
- The positively observed ordinary races: Traders, Warriors, and Explorers.
- Atlas Station or Black Hole.
- Contains Giant, GasGiant, non-gas Giant, Waterworld, water, deep water, weird, infested,
  ordinary-group, relic, RGB-biome-group, corrupt-sentinel, or extreme-storm planet.

Target-planet criteria must all match one planet. `Contains ...` predicates are explicit system
aggregates and may be satisfied by different planets.

## Current runtime evidence

The
[scoped installed-release acceptance](../../../../games/no-mans-sky/investigations/analysis/search-probes-acceptance.md)
records current form/Guide lifecycle, save/reload, package parity, and cleanup gates. No-match Guide
probes publish no destination and require explicit abandonment in the Log; the F7 form retains their
detailed status. Broader platform validation is separate from this host's acceptance.

The full retained survey is under
`games/no-mans-sky/tooling/runtime/.resident-search/sessions/1789310863789245500-ebf88c4a581a45a4b1f2db7e3b79e6e/`;
its matrix summary is `results/matrix-full-1789310864882395743-summary.json`. It examined 15,053
remote graph entries and 71,730 planets in one session, then restored hooks and closed cleanly.

Important observations include:

- 1,158 exact Paradise planets; storm frequency None/Low/High on 30,862/33,494/7,374 planets; both
  Default and Extreme intensity; 14 weather types.
- Floating-island terrain on 7,145 planets. HydroGarden resolved 143 selected object records,
  including ten exact floating-island flags; all other Lush subtype controls resolved zero such
  flags.
- 278 systems with a Giant: 186 GasGiant and 92 non-gas Giant. 301 Waterworld systems, 13,296 with
  water, and 643 with deep water.
- Rings on 13,298 planets and at least one moon on 6,954. Every advertised life, creature, building,
  and resource-abundance choice returned an exact result.
- Population state on 12,343 inhabited, 1,866 empty, and 844 abandoned systems. Atlas Station and
  Black Hole had positive controls at ranks 400 and 42.
- Every temporary generated planet name and explicit generated system name was nonempty. These are
  base procedural names, not discovery-service/player-renamed display names.

The exhaustive diagnostic averaged 6.91 ms of engine work per system with a 24.62 ms maximum slice;
it deliberately copied every optional field. Ordinary generated searches averaged roughly 0.55–1.1
ms/system, while anomaly scans averaged about 0.19 ms/system. Wall time is intentionally longer
because work is cooperatively bounded per gameplay update. Performance claims from sessions run
alongside unrelated heavy workloads are not treated as benchmarks.

Guide/runtime proof is retained in the resident session artifacts:

- The shipped Earthlike intersection completed over 5,000 candidates in session
  `1789354244668911900-193edb6196ba463ba4667204b78d3b42`: exact Lush/Paradise, Green generated grass
  hue, Blue generated sky hue, and has-moons filters returned three systems. Those three controls
  happened to report one moon each, but the implemented predicate remains one-or-more.
- That session's live Wiki snapshot contained exactly one runtime-owned topic, **Earthlike**, bound
  to `SQN_SS_P00`. A subsequent fresh-process normal attach automatically opened the owned form with
  `1 / 9 saved presets`.
- Exact slot-zero Guide activation searched Paradise Planet, checked 102 candidates over 43 slices,
  retained five matches, and passed `0x000087FF278028A5` to the native publisher. That older run
  proved event creation but not a route-bearing mission context and is not navigation acceptance
  evidence.
- A 64-topic capacity probe installed safely, but visual/controller/mouse testing could reach only
  the first nine rows and found no scrolling path.
- Empty startup produced one inert topic and no crash; a true zero array had previously crashed.
- A ninth user preset saved through the form appeared on the next launch as topic **My system
  search** with the previous-generation slot mission `SQN_SS_P08` in session
  `1789351835798811800-afd7b92452f74069ab3c625dab443311`, result
  `1789351884110079466-db6d0513be524f69a4337c5907638d96`.
- That final session ended with `hook_restored=true` and `executor_closed=true` while NMS survived.
- A packaged ordinary-launch session in galaxy #256 decoded live `RealityIndex=255`; all eight
  independently enumerated candidate addresses also decoded to 255. A subsequent visible-form
  Earthlike search excluded the current system, advanced from 448/499 to completion while the form
  remained mapped, and recorded galaxy #256 in its enumeration metadata. The same build started
  hidden, opened through direct F7 state polling, and accepted `500` through the keyboard-editable
  Maximum systems field.

The earlier SS9 arrival control produced a selectable target, a Current Mission Galaxy Map route,
stable destination-system locality, and an exact planet marker; approach cleared its HUD/map route
and removed the target from the Log. Its reusable hidden launcher failed abandonment/reuse and is
not the current form architecture. The retained arrival control is
`games/no-mans-sky/investigation-state/runs/20260914T114740Z-ss9-player-acceptance/analysis.json`.
Current start/abandon/reuse and exact-route evidence is retained in
`games/no-mans-sky/investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json`. This
task's automation covers menus and missions, not flight or warp; it does not claim a fresh
travel/arrival test. Live comparison also proves that `GcPlanetData.PlanetIndex` is zero-based while
`cGcUniverseAddressData.PlanetIndex` is one-based: generated index 3 was loaded planet address value
4, while published value zero produced only a system destination.

The same fresh-process Guide snapshot contains two runtime-owned topics, **Earthlike** bound to slot
`P00` and the newly saved **Frozen Giant** bound to slot `P01`. This proves that preset saves are
persistent and appear after the documented next-launch refresh boundary.

## Reference-mod conclusions

- **BG Dark UI and Fonts** changes presentation assets. The current adapter adds data records and
  localization while the form owns its window, so there is no direct path overlap. General
  compatibility with every UI or injection overlay still requires testing.
- **Lush Finder** mostly maps friendly foliage labels to `GcBiomeSubType` values: for example Huge
  Tree→HugeLush, Jungle→Worlds, Floating Flower→HugePlant, and Floating Islands→HydroGarden. It does
  not prove that a rendered foliage model spawned. System Search exposes exact subtype and native
  object flags; subjective foliage labels require a reviewed asset taxonomy.
- **Weather Indicator Short** is localization only: 305 English phrase substitutions grouped by its
  author, not 305 weather types or executable classifications. System Search keeps the smaller
  direct generated model: storm frequency, intensity, and observed weather type. See
  [the focused reference](../refs/third-party/weather-indicator.md).

The synchronous object-list resolver is narrower than the loaded-planet streaming coordinator. It
selects exact detail/object/landmark/distant records, permits pointer-free copies of source and
resource identities and fixed flags, restores procedural RNG, and releases caller-owned results
through NMS's destructor/allocator path. It stops before asynchronous resource instantiation, so it
can answer asset identity and fixed spawn flags off-screen without pretending to render a planet.

## Deliberately withheld capabilities

| Capability                                          | Proven boundary                                                                                                             | Evidence needed before exposure                                                                                                                                |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Final visible sky/grass/water/foliage colour        | Generated palette hues are deterministic; visible pixels are contextual.                                                    | Loaded-planet calibration can support a qualified predictor, never an unconditional exact-colour claim.                                                        |
| Friendly foliage type/model                         | Exact selected asset/resource records and native flags can be copied. No stable player-facing taxonomy follows from a path. | Define/review an asset catalogue; validate against loaded vanilla planets and mod-added object lists.                                                          |
| Discovery/player-renamed names                      | Generated planet/system names are stable and shown.                                                                         | Compare untouched, discovered, uploaded, and renamed cases, including encoding and cache lifecycle.                                                            |
| Undiscovered system                                 | A native save/cache discovery-state bit is decoded and differs from generated Empty.                                        | Prove offline/network/account/cache invalidation and newly-discovered transitions.                                                                             |
| AtlasStationFinal, MiniStation, BackgroundSwarmHive | Enum values exist but were absent from the complete local graph.                                                            | Obtain current positive controls and validate search plus navigation.                                                                                          |
| Raw system class                                    | Default/Initial/Anomaly are generation-control states, not useful star classes.                                             | Keep diagnostic unless a concrete player-facing meaning is established.                                                                                        |
| Additional race values                              | `None` and schema values exist; only three ordinary races have established UI meaning.                                      | Trace consumers/localization and obtain positive controls.                                                                                                     |
| Exact scripted/seasonal absence of storms           | Not a stable generated-planet property.                                                                                     | No honest universal off-screen predicate is currently expected.                                                                                                |
| Live Guide refresh                                  | Any loaded-record mutation can strand an open Guide page; no reliable open/closed signal is proved.                         | Prove a stable Guide lifecycle signal or supported rebuild API, safe refresh, controller behavior, and exact teardown. Until then, update only at next launch. |
| Custom chat slash command                           | Stock chat has built-ins but no data-driven registration seam.                                                              | Exact-build parser/input/IME/controller/multiplayer hooks; F7 remains safer and lower impact.                                                                  |

## Repository ownership

`games/no-mans-sky/mods/search-probes` is the mod-only Git submodule, backed by
`scottdraper8/search-probes`. Its focused modules separate criteria and query decoding, temporary
planet-data capture, native call bindings, search scheduling, Guide catalog ownership, mission
navigation, form presentation, and embedded startup. Native operations stay on the gameplay thread.
Host acquisition, executable probes, adapter materialization, packaging, installation, test suites,
menu controls, and raw evidence remain in squinchmods.

The [filter audit](../../../../games/no-mans-sky/investigations/analysis/search-filter-audit.md)
records control-by-control semantics. Terrain families and resolved floating-island objects remain
distinct, required resources are conjunctive, and target-planet predicates cannot silently match
different planets. Generated planet names are copied for basic searches as well as advanced ones.

## Remaining work

The requested search algorithm, proven filters, preset authoring, native Guide dispatch, and safe
session lifecycle are implemented. Remaining work is bounded to semantic extensions and release QA:

1. Discovery-service/display names and the save-aware undiscovered flag need untouched, discovered,
   uploaded, renamed, offline, online, account, and cache-transition controls.
2. A friendly foliage catalogue needs an explicitly reviewed mapping from resolved assets to user
   concepts, plus loaded-planet and mod-added-list validation.
3. Optional rendered-colour calibration can quantify how predictive each generated hue is under
   controlled atmosphere, weather, time, HDR, graphics, and post-processing settings.
4. Rare anomaly values and additional race values need current positive controls.
5. Broad release needs controller QA, common resolutions/DPI, fullscreen/HDR transitions,
   graphics/input overlays, VR, clean install/update/uninstall, and recovery from malformed preset
   files. Every NMS executable update requires new hash, byte-prefix, layout, lifecycle, and runtime
   evidence.
6. Live Guide refresh is a separate future workstream only if a reliable Wiki-page lifecycle seam is
   found; the current next-launch snapshot is the supported contract.

## Safety invariants

- Never retain an NMS pointer across a callback, destructor, or load; retain copied values only.
- Run every generator, evaluator, resolver, and navigation call on the gameplay thread.
- Never call procedural generation concurrently merely for throughput.
- Never mutate loaded Guide records after the initial attach snapshot.
- Fail closed on an unknown executable, byte prefix, enum, allocation shape, or lifecycle.
- Bound mailbox, candidates, results, active searches, per-update work, and dynamic-array copies.
- Restore entry hooks while callbacks/trampolines still exist, drain active callbacks, then release
  owned storage.
- Do not infer truth from localization wording, screenshots, or third-party preset names when direct
  generated fields exist.
