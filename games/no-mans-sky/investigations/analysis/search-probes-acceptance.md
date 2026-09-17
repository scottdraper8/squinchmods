# Search Probes acceptance

The installed package targets No Man's Sky 7.03.1, Steam build `25351301`, on the validated Steam
Proton host. The executable SHA-256 is
`6213bed7f859766d4064de704be25f119f84449fa13d78a3e40e162364a552ad`; the runtime fails closed for any
other executable. An ordinary Steam launch starts the packaged runtime without an external injector
or controller.

Current evidence is retained in:

- [`exhaustive installed field matrix`](../../investigation-state/runs/20260917T043233Z-production-7.03.1-exhaustive-field-matrix/analysis.json)
- [`native sentinel-row trace`](../../investigation-state/runs/20260917T031654Z-sentinel-difficulty-trace/analysis.json)
- [`aggressive-sentinel control`](../../investigation-state/runs/20260917T032553Z-sentinel-positive-control/analysis.json)
- [`corrupt-sentinel control`](../../investigation-state/runs/20260917T033732Z-corrupt-sentinel-positive-control/analysis.json)
- [`mission lifecycle`](../../investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
- [`completed-target reuse`](../../investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json)

## Search and filter acceptance

The installed package completed the full resident matrix in the user's current galaxy without
navigation or save mutation. The generated-field and colour surveys each examined 15,097 remote
systems and 71,673 planets.

The exhaustive gate enumerates the visible form schema: 62 fields and 304 selectable values. It
issues one installed-runtime search for every value and requires each search to return a concrete
match. This includes both Require and Exclude for every visible tri-state, every resource ID, every
choice in the eight visible colour fields, and every other advertised planet, environment, life, and
system value. A separate three-resource same-planet conjunction also returns a concrete match.

The generated surveys provide an independent source corpus: all values in 56 non-palette categories
have positive controls, all proven hues remain present across 11 internal palettes, and six
native/generated predicate pairs agree across the full graph. Three of those internal palettes are
diagnostic inputs and are not visible form fields.

The matrix also executes 65 composition and diagnostic searches. Sixty return positive matches. Five
deliberate negative controls return no match: three anomaly enum values withheld from the form,
`StormFrequency=Always`, and the Waterworld-plus-Giant combination. Repeatable generated names,
snapshots, object resolution, restored procedural RNG, and released native outputs remain mandatory.
The matrix status is `completed` only after every gate passes.

## Sentinel behavior

The 7.03.1 native `cGcScanEventManager::PassesPlanetInfoChecks` reads the active ground-combat
difficulty row from the application singleton at application offset `0x315A2C`. Its sentinel,
extreme-sentinel, and corrupt-sentinel predicates index the four-byte query arrays at `+0x124`,
`+0x128`, and `+0x12C` with that row. Live memory and the native compatibility global both selected
row 2 during the aggressive-sentinel trace.

The installed runtime decodes Folk at sentinel level 2 with sentinel presence and extreme sentinels
true. Requiring both properties selects Folk; excluding sentinel presence selects a different planet
whose flag is false. On Yachi 33/Z7, the visible `Dissonance detected` indicator, the runtime's
current planet index, sentinel level 3, and the corrupt-sentinel flag agree. Requiring corrupt
sentinels selects Yachi itself; excluding them selects a planet whose flag is false.

## Package and deployment

The package was built and installed while NMS was closed. Source, package, direct-game, and Amethyst
copies of the corrected modules have identical hashes. All 1,723 package runtime files match
Amethyst's managed source, and all four owned adapter files match both destinations. The direct game
tree contains additional live session state. Both deployment records point at the verified Amethyst
runtime and adapter sources, so Amethyst will preserve this build.

The final gates are:

- 287 investigation tests passed.
- 10 third-party acquisition tests passed.
- Ruff and both Git whitespace checks passed.
- The installed full matrix completed.
- Aggressive and corrupt sentinel positive and negative controls passed.

## Form, mission, and lifecycle contract

The form uses one disposable native NPC mission per navigation target. Active or pending targets are
rejected before destination mutation. A successful start publishes one exact planet route and
selects the sole matching active instance. The mission identity uses `GcSeed(value=0, valid=true)`;
an invalid all-zero seed is a different identity. Native abandonment owns cleanup.

Retained lifecycle controls cover repeated start, abandonment, restart, duplicate rejection,
completed-target reuse, save/reload, Guide positive and no-match launches, exact route ownership,
and cleanup without disturbing unrelated routes. The user has confirmed mission and Galaxy Map
behavior. The sentinel correction does not change the route or mission lifecycle.

The host acceptance does not claim native Windows, VR, HDR, multiplayer, other display/input
configurations, or automatic flight and warp. Generated colours are searchable generation inputs;
they do not promise final pixels after atmosphere, lighting, weather, reflections, or screen
grading.

Raw run directories are local ignored evidence. Tracked documentation identifies the small set of
current runs needed to reproduce each acceptance claim; superseded or failed runs are not product
source and need not be published.
