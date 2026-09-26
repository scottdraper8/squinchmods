# System Search

This is the current-state working record for the No Man's Sky system and planet finder. Replace
conclusions when stronger source or runtime evidence changes them. Raw results remain in retained
run/session artifacts; this file is not a changelog.

## Current product decision

The authorized active work is a complete Rust replacement, governed by
[the Rust overhaul plan](search-probes-rust-overhaul.md). The following sections describe the
installed Python baseline and its evidence until the replacement passes acceptance. Parent NMS
tooling may be redesigned as required. The earlier investigation-only scope is superseded.

System Search has two deliberately separate UI surfaces:

- An owned, F7-toggleable window composes searches, manages named presets, reports progress, retains
  results, and can publish a selected destination through a disposable Search Probe navigation
  mission. It is injected Python/DearPyGUI and does not replace an NMS layout. A completed form
  search is only a result set until the user explicitly selects a result and presses **Navigate to
  selected result**.
- One additive **Search Probes** category in Catalogue & Guide lists the preset snapshot loaded when
  the resident runtime attaches. Launching a probe runs that exact preset in the background and
  publishes the first match through NMS's ordinary mission and Galaxy Map navigation path. The probe
  language is an in-universe presentation of the bounded procedural query; it does not claim that a
  persistent physical object travels through the galaxy.

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
visible library unchanged. Maximum systems is a dropdown of powers of ten from 1,000 through
1,000,000,000. Preset budgets round to the numerically nearest choice (ties upward) on load and
save; a migration atomically persists the adjusted library and retains the original as its backup.
New searches and freshly created built-ins default to 10,000 systems. Result limits are one
through 100.

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
   visits nearby candidates in native distance order, then streams additional regions in outward
   cube shells with no duplicate systems;
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

The requested candidate count is an exact budget of distinct remote systems evaluated, excluding the
current system by address identity. The initial nearest query is capped at 20,000 entries and may
return fewer because the active graph is finite. It does not grow the graph. Its count varies by
location: the current 7.04 control has 9,298 entries, while earlier controls had roughly
14,500–15,100. The user's observed ceiling around 16,300 is consistent with this graph-bound
behavior.

After the nearby batch, `CandidateStream` enumerates unique clipped cube shells around the starting
region, within native X/Z bounds −2047…2047 and Y bounds −127…127. Each region uses NMS's isolated
voxel constructor (`0x1404C3090`), Populate (`0x14135D7B0`), and destructor (`0x1404C2E90`). Native
portal validation and system-distance consumers demonstrate this lifecycle without a graph/cache
instance. Both the owned voxel and root vector are explicitly 16-byte aligned. Actual generated
address arrays are copied before destruction, preserving discontiguous purple-system indices;
synthetic index ranges would miss these systems or include nonexistent ones.

The initial nearby address set excludes overlap with generated regions. Unique region traversal
avoids a growing visited-system set. Each search retains at most the nearby batch/set, one generated
region, and up to 100 results. Native storage is released before returning to gameplay. Region
construction occupies its own update; evaluation resumes on subsequent updates. Results beyond the
initial batch follow region traversal order, without a global nearest-distance guarantee. Traversal
is bounded by valid coordinates, but exhaustive whole-galaxy runtime coverage is not claimed.

The search protocol accepts 1…1,000,000,000 systems; presets use the dropdown values. A request
stops at its exact budget, its requested match count, cancellation, or exhausted coordinate space.
Cancellation preserves completed matches; changing galaxies fails the request. There is no
elapsed-time cutoff or persistence across NMS exit. The bounded `enumerate` and survey diagnostics
continue to use the nearby graph.

The
[region expansion evidence](../../../../games/no-mans-sky/investigations/analysis/search-probes-regions.md)
records exact native discovery, runtime controls, package validation, and the long-search boundary.

`Any` is omitted from form queries and imposes no constraint. It does not eliminate all associated
work: some unselected predicate helpers still execute, basic decoding is unconditional, and optional
capture uses groups rather than individual fields. The
[performance audit](../../../../games/no-mans-sky/investigations/analysis/search-probes-performance.md)
records these distinctions and the actual preliminary/full-query ordering. Colour and object-list
searches process at most one candidate system per update. Ordinary generated/weather searches
process at most four and stop scheduling after a 2 ms cooperative slice; one native call cannot be
preempted.

Up to eight independent search commands may be active, but they are interleaved on the gameplay
thread rather than executing NMS generation concurrently. This keeps UI/gameplay responsive and
avoids asserting nonexistent generator thread safety. Because advancement is driven by that gameplay
update path, NMS states that suspend simulation—observed with the Galaxy Map—also suspend probe
progress. The request and its completed work remain intact and resume when gameplay updates resume;
this is not an overlay-refresh failure or a cancelled search.

## Criteria exposed in the form

Every advertised choice has a current-runtime generated field and positive control. `Any` removes
the field's filtering constraint; it does not guarantee zero acquisition or decoding work.

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

The production runtime targets No Man's Sky 7.04, public Steam build `25442159`, executable SHA-256
`b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`, and fails closed on other
executable bytes. The established native function/hook signatures matched uniquely at their
configured addresses in the retained
[7.04 signature run](../../../../games/no-mans-sky/investigation-state/runs/20260923T152428Z-exe-patterns-140e2069/result.json).
The
[function disassembly run](../../../../games/no-mans-sky/investigation-state/runs/20260923T151045Z-exe-functions-7f8ecf00/pe-functions/function-00000001412d5560.asm)
retains the resolver's current graph, position, and candidate-evaluator call chain.

The 7.04 source adapter was rebuilt from live game assets. The direct Lush predicate in
`SE_PHOTO_BIOME_LUSH` remains `NeedsBiome=true` / `Lush`, with `PlanetSearch`/`Any` search fields.
Its source `BuildingClass` is `TerrainResource` in 7.04, but that field is not imported into the
generated probe; the probe independently sets its no-building, bounded `Near` search policy. The
[native probe run](../../../../games/no-mans-sky/investigation-state/runs/20260923T152348Z-native-search-probe-24788780/result.json)
compiled and decompiled the four generated adapter files. The
[current asset scenario](../../../../games/no-mans-sky/investigation-state/runs/20260923T152416Z-scenario-081b99b6/result.json)
passed semantic round trips for the Wiki and mission tables and all five relevant Guide/UI layouts.

The cold-client 7.04
[full resident matrix](../../../../games/no-mans-sky/investigation-state/runs/20260923T171746Z-resident-matrix-full-retest-save2/session/results/matrix-full-1790183046419051873-summary.json)
completed through ordinary Steam self-start. It checked 9,297 remote systems and 44,430 planets in
both generated-field and colour surveys. All 62 visible fields and 304 selectable values returned
concrete matches, as did the three-resource same-planet conjunction. The 65 composition/diagnostic
searches had 60 positive results and the five expected no-match results: AtlasStationFinal,
MiniStation, BackgroundSwarmHive, `StormFrequency=Always`, and Waterworld plus Giant. Snapshot and
name repeatability, resolver-backed objects, predicate parity, RNG restoration, and native output
release gates also passed. The harness passed its prelaunch, runtime, post-matrix, and post-shutdown
health gates; NMS closed cleanly, with no travel, warp, or save mutation.

The `SearchProbes-7.04-expanded` manifest matches the running expansion package. All 1,724 packaged
runtime files, the WINMM proxy, and four adapter files match the direct game and the recorded
Amethyst `Root_Folder`/`overwrite` sources. Deployment records continue to point at those managed
sources, and the installer preserves user presets. The
[scoped acceptance record](../../../../games/no-mans-sky/investigations/analysis/search-probes-acceptance.md)
contains the current package and test boundary.

Region generation, long-budget search, and its package controls are recorded separately in the
[region evidence](../../../../games/no-mans-sky/investigations/analysis/search-probes-regions.md).
The earlier full criterion matrix remains filter regression evidence; it did not exercise expansion.

The 7.04 native mission start and select functions matched their exact configured signatures and
were resolved during runtime initialization. Mission acceptance, Guide dispatch, abandonment, and
Galaxy Map route behavior were not re-triggered on 7.04 because doing so would mutate the active
save. The retained
[7.03.1 lifecycle controls](../../../../games/no-mans-sky/investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
and
[completed-target reuse controls](../../../../games/no-mans-sky/investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json)
remain historical regression evidence, not a 7.04 lifecycle run. The 7.04 matrix validates the
search path without claiming Guide mission lifecycle or automatic travel.

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

The current performance work is investigation only. The
[generator isolation and throughput report](../../../../games/no-mans-sky/investigations/analysis/search-probes-generator-concurrency.md)
records measured scheduling headroom, native constructor/resource ownership findings, and the
remaining proof gates for independent worker contexts. Temporary probe changes were restored;
production generation remains on the gameplay thread. No large-budget runtime test is authorized by
that investigation.

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
