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
count. Generated hue families are base vegetation palettes and selected sky/water inputs rather than
guarantees about final rendered pixels. The default is an ordinary record: users can overwrite or
delete it, save up to eight additional presets, reach zero records, and restore the default without
deleting custom records. Saving never launches a probe. Selecting a preset first resets every form
field, then applies its criteria and limits, so stale values on hidden tabs cannot constrain it.

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

The requested candidate count is the native nearest-query output capacity. Search Probes passes it
to NMS's 3D spatial-tree query, maps returned graph IDs through the active index's system-address
array, and skips rank zero (the current system). The count is not a distance radius and increasing
it does not add systems to the index. NMS's own criteria-based nearest-system resolver calls the
same coordinate-to-graph and spatial-nearest functions and reads the same indexed system count and
address array, so this is also NMS's native nearby-candidate path. The exact-build disassemblies are
retained in the
[spatial-query](../../../../games/no-mans-sky/investigation-state/runs/20260917T094220Z-exe-functions-84f637bb/pe-functions/function-00000001403a9160.asm)
and
[native resolver](../../../../games/no-mans-sky/investigation-state/runs/20260917T093027Z-exe-functions-d225c97e/pe-functions/function-00000001412d2190.asm)
runs.

The active index is finite and its count varies by observed location/state. A 20,000-entry request
returned all 14,723 indexed candidates (including the current system) in the live Galaxy 256 probe;
earlier exact-build controls recorded 14,527 in Galaxy 256 at another system and 15,098 in
Galaxy 30. The
[live enumeration](../../../../games/no-mans-sky/investigation-state/runs/20260917T092545Z-spatial-index-enumeration/results/1789637145117661656-e00fc4912e6b447cbabebe62fad7d11a.json),
[earlier Galaxy 256 result](../../../../games/no-mans-sky/investigation-state/runs/20260915T050700Z-colour-redeployment/live-results/islands.json),
and
[Galaxy 30 survey](../../../../games/no-mans-sky/investigation-state/runs/20260917T043233Z-production-7.03.1-exhaustive-field-matrix/analysis.json)
preserve the exact results. This variation is consistent with a position-dependent active subset,
but the native graph population/rebuild policy and the reason for its finite size remain unresolved.
The native nearest functions only query that existing index. Raising the 20,000 protocol cap could
cover a larger index if one is found, but would not grow it. Searching beyond the active index needs
a proved native expansion/rebuild seam or a separate coordinate-space/region enumerator. The
existing index remains the supported source for nearby searches; no complete alternative has been
proved, and whole-galaxy coverage is not claimed.

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
- One Floating islands control through the resolver-selected native `IsFloatingIsland` flag.
  FloatingIslands terrain variants remain raw diagnostics, not alternative island controls.
- Non-gas Giant, rings, one-or-more moons, water, and deep water.
- Up to three survey resource IDs as a same-planet conjunction, not a complete resource inventory.

### Environment and life

- Exact current Paradise-label predicate: Lush biome; subtype other than Structure, Infested, or
  Swamp; Default weather intensity; `StormFrequency=None`; and the difficulty-selected Low sentinel
  level. HighQuality is not required.
- Generated life (Dead/Full), creature abundance (Dead/Low/Mid/Full), observed building-density
  values, and resource abundance (Low/High).
- Weather type and one Storms choice: None (frequency zero), Non-extreme (storms without the
  extreme-weather flag), or Extreme (storms with that flag). Raw frequency and intensity remain
  diagnostic/preset criteria, not separate form controls.
- Hazard, sentinel, corrupt-sentinel, sentinel-presence, prime-generation, infestation,
  ordinary-group, relic, RGB-biome-group, scrap, and creature-suitability flags.
- Base hue families for grass, plants, leaves, water, daytime sky, horizon, fog, and height fog. Sky
  uses selected biome/generic weather-colour records; water uses selected optical coefficients and
  the native-equivalent reflectance calculation. Legacy sky/water palette entries are not those
  selected inputs. Water-colour criteria also require actual water on the same planet. Cloud,
  near-water, sunset, and night controls are omitted. Old saved filters remain visible as additional
  constraints and are never silently discarded when a preset is loaded or saved.

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

The current executable is No Man's Sky 7.03.1, Steam build `25351301`, SHA-256
`6213bed7f859766d4064de704be25f119f84449fa13d78a3e40e162364a552ad`. The runtime is pinned to that
hash and fails closed on any other executable.

The current native planet predicate selects its four sentinel rows through the ground-combat
difficulty field at application offset `0x315A2C`. The retained
[native trace](../../../../games/no-mans-sky/investigation-state/runs/20260917T031654Z-sentinel-difficulty-trace/analysis.json)
records the exact disassembly and live row-2 values. Installed controls then prove both
player-facing cases:

- The
  [aggressive-sentinel control](../../../../games/no-mans-sky/investigation-state/runs/20260917T032553Z-sentinel-positive-control/analysis.json)
  decodes Folk at sentinel level 2 and selects it with required sentinel and extreme-sentinel
  properties.
- The
  [corrupt-sentinel control](../../../../games/no-mans-sky/investigation-state/runs/20260917T033732Z-corrupt-sentinel-positive-control/analysis.json)
  maps the current planet index to Yachi 33/Z7, agrees with its visible `Dissonance detected`
  indicator, and selects it when corrupt sentinels are required.
- Each case includes an exclude control that selects a planet whose corresponding sentinel flag is
  false.

The installed
[exhaustive 7.03.1 field matrix](../../../../games/no-mans-sky/investigation-state/runs/20260917T043233Z-production-7.03.1-exhaustive-field-matrix/analysis.json)
completed over 15,097 remote systems and 71,673 planets. It enumerates all 62 visible fields and
issues one real installed-runtime search for each of their 304 selectable values. Every search
returned a concrete match. This covers both Require and Exclude for every visible tri-state, every
resource, every choice in the eight visible colour fields, and a separate three-resource same-planet
conjunction.

The independent surveys retain a positive generated control for every value in 56 non-palette
categories and every proven hue across 11 internal palettes. Three internal palettes are diagnostic
and are not visible controls. Six full-graph native/generated predicate parity controls also pass.

The matrix retains 65 separate composition and diagnostic searches, repeatable query snapshots and
generated names, object resolution, restored procedural RNG, and released caller-owned native
outputs. Sixty of those 65 searches returned positive matches. Five deliberately absent or
impossible controls returned no match as required: AtlasStationFinal, MiniStation,
BackgroundSwarmHive, `StormFrequency=Always`, and Waterworld plus Giant. Those absent anomaly and
storm values are not advertised form choices. The matrix status is `completed` only after every
assertion passes.

The package and Amethyst managed runtime contain identical corrected modules. All package-owned
runtime and adapter files match their managed sources. The
[scoped acceptance record](../../../../games/no-mans-sky/investigations/analysis/search-probes-acceptance.md)
records the package, tests, current matrix, sentinel controls, and lifecycle boundary.

Mission navigation retains one exact native route, rejects active or pending target replacement,
uses `GcSeed(value=0, valid=true)`, selects the sole matching active mission, and leaves abandonment
cleanup to NMS. Current lifecycle evidence remains in the retained
[mission run](../../../../games/no-mans-sky/investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
and
[completed-target reuse run](../../../../games/no-mans-sky/investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json).
The user confirms the mission and Galaxy Map flow. Automated acceptance does not drive flight or
warp.

Raw run trees are ignored local evidence. Tracked documents point to the small set of runs that
support the current contract; superseded exploratory and failure runs are not product source.

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
  direct generated model: observed weather type and storm conditions, with raw frequency/intensity
  retained for diagnostics and existing presets. See
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
records control-by-control semantics. Terrain diagnostics and resolved floating-island objects are
distinct, required resources are conjunctive, and target-planet predicates cannot silently match
different planets. Generated planet names are copied for basic searches as well as advanced ones.

## Colour/island reference and current validation boundary

The
[reference capture](../../../../games/no-mans-sky/investigation-state/runs/20260915T030000Z-colour-island-reference/analysis.json)
compares the player's Cape Oath (generated Mosworkin) against loaded and temporary planet data. It
is Lush/HydroGarden with LilyPad terrain and ten resolved island objects. Base grass is olive Green,
base leaves Purple, selected daytime sky Blue, and water reflectance Cyan/turquoise before sky
reflections and grading. Pleasant/Abundant/Frequent labels and all three survey resource IDs agree
with the player's planet panel. Yellow grass patches are not proof of a Yellow primary hue. All 19
loaded water records match the native helper within 2.74e-7; selected colour reads were validated
read-only across all six loaded planets. Combined reference criteria and seven negative controls
pass against captured data.

The
[installed-runtime controls](../../../../games/no-mans-sky/investigation-state/runs/20260915T050700Z-colour-redeployment/analysis.json)
cover a healthy fresh Steam process after host recovery. Amethyst's mirrored deployment source had
retained eight stale modules and overwritten the direct installation. Installation now updates both
owned game and managed-source trees transactionally, remembers source roots for subsequent updates,
and excludes transient runtime state from managed payloads. User presets are preserved.

The player's Bujav L2 negative control has selected yellow-green daytime sky and purple base water
reflectance before its screen filter; neither is Blue. Its fresh temporary snapshot exactly matches
the loaded colour selection captured before restart. Blue-sky and blue-water predicates reject it
independently; non-colour and selected-colour controls accept it. Bounded blue sky/water and island
require/exclude searches each return an independently rechecked match. These prove generated-input
selection, not exact rendered pixels under time, atmosphere, reflections, and grading. Mission
lifecycle is confirmed working by the player and is unchanged.

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
