# Vanilla redstone and automation update inventory

Checked **2026-10-27**, against Mojang's live version manifest, official Java release notes, and
selected official archive data/bytecode. **Latest stable: 26.3. Latest observed snapshot:
26.4-snapshot-6.** The existing mod documentation stops its matrix at **1.21.10**; its last
repository-maintenance commit is later than that. “Since last looked at” is therefore treated as
**missing from the feature inventory**, not guessed from the last Git commit date.

See [scope and existing backports](scope-and-existing-backports.md) for implementation quality,
competing mods, licensing, and recommended ownership. Raw observations and exact source identities
are in the [research evidence][evidence]. Use the
[active implementation contract](../implementation-contract.md) for scope and acceptance:
standalone, all-in-one, with latest stable behavior by default and independently qualified
coexistence. Inclusion here does **not** establish implementation, target applicability,
source-audit completeness, or runtime qualification.

## 1. Stable changes missing after the matrix's endpoint

| Release                              | Confirmed relevant changes                                                                                                                                                                                                                                                                                                                                                                                                                   | Implementation obligations                                                                                                                                                                                                                                                                                        |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [1.21.11 — Mounts of Mayhem][v12111] | **Jukebox comparator notification fix:** removing a disc after its song finished now updates the comparator (MC-301632). Also disc-ejection placement fix MC-271941, waxed-lightning-rod deoxidation fix MC-302409, and copper golems failing to become statues in cave/void air MC-302184.                                                                                                                                                  | The comparator fix is directly in scope. Other fixes matter if their content/behavior is present on the target; do not apply a newer-version regression fix blindly to 1.20.1. Spears explicitly **do not emit item-interact vibrations**. No new general comparator block is announced here.                     |
| [26.1 — Tiny Takeover][v261]         | **Trumpet note-block instrument on copper blocks**, with a different sound for each oxidation stage. Four sound events: `block.note_block.trumpet`, `_exposed`, `_weathered`, `_oxidized`. Also copper-golem chest-pathfinding fix MC-300380.                                                                                                                                                                                                | A real redstone-adjacent musical feature using existing copper blocks, not a decorative copper-block pack requirement. Implement the instrument, oxidation-dependent selection, and legally sourced sound resources together. Tripwire's alpha-cutout rendering change is visual, not a new circuit rule.         |
| [26.1.1][v2611] / [26.1.2][v2612]    | Hotfixes; inspected notes announce no additional redstone feature.                                                                                                                                                                                                                                                                                                                                                                           | Do not invent a feature row merely because a release exists. The 26.1.2 page does not enumerate the underlying critical issues, so this is not a claim that every internal change is known.                                                                                                                       |
| [26.2 — Chaos Cubed][v262]           | **Dispenser/Sulfur Cube automation:** insert/swap absorbed blocks, shear the held block out, and release a cube from a bucket. TNT absorbed by a cube can be primed by redstone, fire (including dispensed flint and steel), or explosions. **Potent Sulfur geysers** emit sculk-detectable events at eruption start/end. **Bounces emit vibration frequency 2.** New disc **Bounce** gives jukebox comparator output **8**.                 | Implement the complete standalone cube/sulfur system and its acquisition/physics dependencies, not isolated dispenser hooks. Generic bounce-event parity needs its own production-path cases.                                                                                                                     |
| [26.3 — Wilderness Bound][v263]      | **Wool stairs/slabs dampen vibrations.** New Poplar wood family includes ordinary redstone-interacting variants. Fixes include sculk detection of ice/snow melting (MC-210117), paintings/item frames not triggering sculk shriekers when broken (MC-253023), piston/client movement desync (MC-295756), and tripwire depowering disturbing cross-chunk block-tick order (MC-310372). Commands including `/tick` now properly signal errors. | Wool variants and sculk-event fixes are relevant even though the update is not marketed as redstone. Piston/tick-order fixes require exact target-source/runtime investigation before adoption. Include the required content and dependency closure; distinguish stable behavior from unrelated format expansion. |

### Details that are easy to misstate

#### Wool stairs/slabs: dampening is not a full vibration wall

Official **26.3 client data** confirms:

- `dampens_vibrations` includes wool, wool carpets, wool slabs, and wool stairs.
- `occludes_vibration_signals` still includes **only wool**.

Therefore the new shapes suppress applicable vibrations like other dampening surfaces, but they
should **not** be advertised as full wool-block line-of-sight occluders. Exact shape/stepping cases
still deserve runtime tests. The distinction is backed by the extracted tag JSON, not visual
intuition about a half-height wool block.

#### Sulfur systems are not new comparator inputs

The 26.2 notes describe **dispenser, redstone ignition, and sculk-event** interactions. They do not
announce a Sulfur Cube comparator inventory or geyser fill-level comparator. Do not conflate those
mechanics with comparator-readable block entities.

The generic bounce event is explicitly frequency **2**. Geyser events are separately described as
emitted at start/end; do not label all of them “frequency 2.” Vanilla Backport's inspected source
already has potent-sulfur activation/deactivation game-event calls and sulfur-cube implementations;
that is overlap, not proof it has every new vanilla physics/dispenser detail correct.

#### Adjacent content worth noticing, but lower priority

26.3 Shelf Mushrooms can be bonemealed from small to large, and the large mushroom drops two items;
Red Shrubs spread into adjacent spaces with bone meal and are compostable. Classify these
farm/observer-relevant state changes in the complete source inventory and implement their required
content/acquisition closure when in scope, rather than treating another mod as the provider.
Cushions cannot be moved by pistons. Concrete stairs/slabs and ordinary wood variants largely reuse
existing block-family behavior rather than introducing new logic components.

#### Required existing-automation data controls

Current stable exposes existing logic through `sculk_growth_inhibitors` and
`furnace_fuel_bottom_takeable` tags, item-defined cooking/brewing fuel and composting behavior,
data-defined brewing recipes, and typed numeric providers. These are **data/control-surface
contracts**, even where ordinary survival defaults look unchanged. Default-only hard-coded lists do
not implement them. Review their actual introduction and intervening consumer/serialization changes;
listing a current endpoint does not date the entire system to 26.3.

Thread 7 owns existing-block consumer semantics; Thread 2 supplies the shared registry, provider,
component, resource-reload and serialization interfaces. Required content/environment dependencies
must close with their owners rather than becoming companion requirements. Implement the applicable
provider contexts, fallback values, evaluation/RNG order and numeric boundaries. Do not port every
unrelated modern subsystem merely because it is newer, but do not exclude required closure because
an underlying component or recipe system is large.

Qualify genuine override/reload precedence as well as defaults, fuel remainders, sided extraction,
and save/restart behavior. The current furnace consumer divides base cooking time by a positive fuel
speed multiplier: a base-200 recipe at speed 2 takes 100 ticks, not 50. Legacy shorter recipes and
half-burn subclass overrides must not double-apply the new adjustment. Widened saved timers do not
imply full-width menu synchronization; inspect and test actual packet bounds separately.

## 2. Snapshot-only watchlist — not shipped stable behavior

The manifest still labels all **26.4** builds as snapshots at the time checked. Official pages for
snapshots [1][s1], [2][s2], [3][s3], [4][s4], and [5][s5] were inspected. A newer manifest refresh
also observes snapshot 6; its semantics have not been reviewed here and it supplies no
stable-default contract. The important additions in the inspected snapshots are:

- **Snapshot 4: jukebox playlists.** A **single** chest, trapped chest, or copper chest directly
  above a jukebox supplies discs in slot order. Non-discs/empty slots are skipped; the sequence
  loops. At the end of a track the disc is swapped with the next disc in the chest; if the chest has
  no music discs, the current jukebox disc replays. Ejecting the current disc skips to the next
  available disc. This is useful automated music playback and an obvious comparator-automation test
  candidate; the notes do not establish exact comparator-notification timing during swaps.
- **Snapshot 4: Brittle Ice.** Cracks/breaks after a player or mob steps on it. It is Silk-Touch
  obtainable and can form where flowing water borders Blue Ice horizontally. Potential trap,
  observer, and farm interactions. **Frosted Ice** specifically now emits a vibration when changing
  state; do not silently extend that statement to every new ice behavior.
- **Snapshot 5: playlist fixes.** Double-chest conversion detection,
  crash/negative-playlist-position cases, and related implementation fixes show the feature is still
  settling.
- **Snapshot 5: dispenser feedback fixes.** Bottles filling and chest-equipped animals lacked their
  sounds; flint and steel could lose durability/click with nothing to ignite (MC-312654). The
  durability issue has mechanical relevance; the sound fixes are feedback, not new item IO.

No other broad new redstone/comparator component was identified in the first three snapshots.
Snapshot 3's additional underground **redstone ore** features affect resource generation, not wire
semantics; that is separate from an automation parity backport. Snapshot 2's sculk-catalyst XP fix
is another dependency-sensitive bugfix candidate, not a new component.

**Recommendation:** keep 26.4 in a watchlist and recheck final release behavior before choosing a
contract. Do not describe playlists as available in vanilla 26.3 or silently change an old world's
jukebox behavior based on a moving snapshot target.

## 3. Older omissions and under-described mechanics worth correcting

These predate the matrix's endpoint but materially affect the usefulness/ownership decision.

### Copper Age is more than statues and hotbar swaps

The official [1.21.9 notes][v1219] introduce copper chests/golem sorting, oxidizing lightning rods,
shelves, and statue outputs. The existing matrix's two-item summary leaves important mechanics out.

**Shelf comparator output is an occupancy bitmask, not a normal fill percentage:**

```text
output = (slot0 occupied ? 1 : 0)
       | (slot1 occupied ? 2 : 0)
       | (slot2 occupied ? 4 : 0)
```

That gives **0–7**, so a single occupied slot can give 1, 2, or 4 depending on position. Three
occupied slots give 7 regardless of stack sizes. Official 26.3 `ShelfBlock` bytecode confirms this
and a direction check restricting which side can read it. The bitmask exists in both inspected
Copper Age Backport and Vanilla Backport shelf implementations; exact side/notification parity still
needs testing. Power **enables player interaction** to swap hotbar groups; a pulse does not itself
automatically swap a player's inventory.

**Copper-golem statue output is pose-based 1–4**, not a readout of oxidation level. Official 26.3
bytecode computes pose ordinal plus one. The statue and shelf therefore offer distinct compact
signal-state mechanisms, already covered by content backports.

Copper chests provide the inventory side of golem sorting. Oxidizing lightning rods are also a
content/automation interaction to include in a complete Copper Age evaluation, rather than assuming
the unchanged 1.20.1 rod represents the whole newer feature.

### Chunk loading / random ticking is a major missing axis

- [1.21.2][v1212]: **Ender Pearls load and tick chunks**, including across dimensions; they unload
  with the player and return on login. The matrix discusses that release's wire/minecart experiments
  but misses this **stable** farm/loader mechanic.
- [1.21.5][v1215]: random ticks apply more broadly to eligible loaded/simulation chunks, including
  pearl-loaded chunks. This can grow crops away from the former player-centered ticking area. Mob
  spawning, lightning, and lava fire-spread are explicitly not all expanded by that rule.
- [1.21.9][v1219]: **fixed spawn chunks were removed**, and `spawnChunkRadius` was removed. Active
  dimension/chunk loading and startup preload behavior were revised around players, forced chunks,
  portals, and Ender Pearls. Backporting only the older radius gamerule from 1.20.5 is **not** the
  same contract as “latest vanilla.”

- Dedicated servers also have **empty-server pausing**, present from stable **1.21.2** (absent in
  reviewed 1.21.1 source). Official 26.3 `DedicatedServerProperties` defaults
  `pause-when-empty-seconds` to **60**. In `MinecraftServer.tickServer`, the threshold is seconds ×
  20 server ticks; the empty counter advances with no players unless sprinting, and resets
  otherwise. Reaching the threshold saves once, continues connection ticking, and skips the rest of
  server ticking. Nonpositive thresholds disable this path. Review each intervening source change,
  not just the current endpoint. This interacts with force-loaded farms, pearls, `/tick`, server
  startup, and test harness configuration.

These changes matter a great deal to automation and may break existing farms or change performance.
Implement the approved current-stable default explicitly, with persistence/performance/migration
qualification and separately labeled historical profiles where offered. Existing overlapping Ender
Pearl or server-tick providers require independently qualified ownership; they are not dependencies.

### The neighbor-update engine is an older-target prerequisite

Stable **1.19** introduces the collecting neighbor-update engine and dedicated property
`max-chained-neighbor-updates` (default **1,000,000**), absent in reviewed 1.18.2 source. Required
1.16.5/1.18.2 support therefore cannot consist only of registering new blocks on the old recursive
update engine. Review `Level`, `ServerLevel`, `NeighborUpdater`, `CollectingNeighborUpdater`, and
dedicated property wiring across the intervening releases, including Forge's applicable patches.

The reviewed 26.3 endpoint bounds a complete update chain, defers nested work through a stack and
per-layer pending list, and clears pending work/count in `finally`. A negative configured limit
disables that bound; zero skips the first update. Ordinary neighbor order remains west, east, down,
up, north, south, with the requested excluded direction omitted. Experimental orientation behavior
is feature-gated and must not become the stable default. Shape-update recursion limits are a
separate input: the 1.19 implementation hardcodes 512 in its queued shape action, while the reviewed
current implementation preserves the supplied limit. Do not copy the old rule as current parity.

These are source observations, not an executed queue/parity qualification. Require production-path
cases for nested ordering, state lookup versus captured state, excluded sides,
zero/positive/negative chain bounds, independent shape limits, exception cleanup, client/server
boundaries, and native-target deltas. Assign shared platform hooks/configuration once; do not stack
competing queue owners.

### Music discs count as comparator content

- [1.21][v121]: **Creator (Music Box) = 11**, **Creator = 12**, **Precipice = 13**.
- [1.21.6][v1216]: **Tears = 10**.
- [1.21.7][v1217]: **Lava Chicken = 9**, another disc missing entirely from the old matrix. The
  release page does not give the number; it was verified in the official 26.3 `jukebox_song` data.
- [26.2][v262]: **Bounce = 8**.

Several reuse already possible signal strengths; new disc content is not necessarily a new analog
capability. Standalone completeness still requires the items, acquisition, legally supplied
resources, notification behavior, and insertion/ejection parity. Follow
[asset provenance](../asset-provenance.md) instead of assuming permission to redistribute recordings
or requiring a companion.

The matrix's **1.19.4 “comparator strength 15 while playing” wording is wrong**: the official
[1.19.4 notes][v1194] specify a **redstone signal of 15** while playing. Do not confuse the
jukebox's powered/playing output with a comparator's disc-dependent signal. The later MC-301632 fix
is specifically a comparator-update issue.

### Debugging and experiments need separate categories

[1.21.5][v1215] also added test/test-instance blocks and `/test` facilities: test blocks have
redstone start/log/fail/accept modes. Those are technical testing tools, not a new normal survival
component; including them would be a separate tooling decision rather than an automatic Crafter
dependency.

[1.21.2's redstone and minecart experiments][v1212] were behind optional world toggles; the release
notes expressly did not promise a future default release for the wire experiment. Never present that
experimental update order as the ordinary stable survival contract merely because its host version
shipped.

[1.21.10][v12110] genuinely contains piston/cobweb/powder-snow, wind-charge collision, teleport
chunk loading, and command-block teleport fixes. That old row is not an invented update; it just
does not cover the subsequent releases above.

## 4. Implementation and qualification priorities

1. **Source inventory and compatible platform foundations:** establish every stable transition and
   exact target obligation before dependent feature planning. Resource rights, collision ownership,
   and executable server/client qualification paths are foundations, not final paperwork.
2. **Existing feature correctness:** replace the identified Crafter/witch deviations and unsound
   tick mechanisms. New breadth cannot compensate for unreliable core semantics.
3. **Standalone dependency closure:** implement the shelves, statues, copper sorting, creaking-heart
   sensors, pot storage, sulfur systems, music, and survival/world-generation prerequisites required
   by the accepted inventory. Independently test overlap; do not require a content companion.
4. **Stable simulation behavior:** qualify pearl loading, random ticking, spawn-chunk removal,
   empty-server pausing, and `/tick` together, including saves, restarts, player presence, timing,
   and performance. Separate experiments from the stable default.
5. **Snapshot watchlist:** keep 26.4 playlists and ice mechanics unshipped until a stable contract
   is established and reviewed. Refresh official release metadata before final qualification.

This is a relevance inventory, not a proof that a cited vanilla bug affects 1.20.1, that every mod
has been surveyed, or that the listed mechanisms work when combined in a real modpack.

[evidence]:
  ../../../../../../.squinch/scratch/tranches/redstone-backport-release/inputs/research/research/2026-10-27/README.md
[v1194]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-19-4
[v121]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21
[v1212]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-2
[v1215]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-5
[v1216]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-6
[v1217]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-7
[v1219]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-9
[v12110]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-10
[v12111]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-11
[v261]: https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1
[v2611]: https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-1
[v2612]: https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-2
[v262]: https://www.minecraft.net/en-us/article/minecraft-java-edition-26-2
[v263]: https://www.minecraft.net/en-us/article/minecraft-java-edition-26-3
[s1]: https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-1
[s2]: https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-2
[s3]: https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-3
[s4]: https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-4
[s5]: https://www.minecraft.net/en-us/article/minecraft-26-4-snapshot-5
