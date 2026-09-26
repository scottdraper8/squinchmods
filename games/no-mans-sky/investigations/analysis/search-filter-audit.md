# Search Probes form-filter audit

This records the current advertised form and its evidence boundary. The form renders only criteria
with a supported resident evaluator path; protocol fields not rendered remain valid API and
saved-preset data. `Any` omits a criterion.

## Evaluation model

The native scan event performs cheap system predicates. The resident evaluates copied generated
snapshots and resolves additional data only when a selected criterion needs it. Planet criteria are
conjunctive on one planet; system “contains” criteria may match different planets. The first
matching planet is the navigation target.

## Current form semantics

- `floating_islands` is the one Floating islands control. It reads resolved object-list
  `IsFloatingIsland`, not terrain-family naming. The terrain diagnostic
  `has_floating_island_terrain` is not advertised as an island selector.
- The exact terrain dropdown hides `FloatingIslands`, `FloatingIslandsPrime`, and
  `FloatingIslandsPurple`; other terrain families remain available.
- Biome, subtype, size, water, deep water, rings, moons, life, creatures, buildings, resources,
  sentinels, special planet groups, and system aggregates remain distinct predicates and scopes.
- Resource 1–3 are required survey-resource slots on the same planet, not a complete inventory.
  Empty slots are ignored and duplicates collapse.
- Weather type remains available. `weather_conditions` is the single Storms control: `None` means
  frequency 0, `Non-extreme` means frequency > 0 with no extreme-weather flag, and `Extreme` means
  frequency > 0 with the extreme-weather flag.
- The form exposes Grass, Plant, Leaf, Water, daytime sky, horizon, fog, and height-fog base colour
  controls. Cloud, near-water, sunset, and night legacy controls are not rendered; neither are their
  legacy sunset/night/cloud form criteria.
- Displayed palettes are limited to Grass, Plant, Leaf, Water, Sky, SkyHorizon, SkyFog, and
  SkyHeightFog. Base colours exclude lighting and colour grading; they do not guarantee screen
  pixels. Vegetation may contain multiple colours, and water reflects the sky.
- The native sky input is the biome/generic `GcWeatherColourSettings` selected by the planet's day,
  dusk, and night indices. Water optical reflectance comes from `GcPlanetWaterColourData` selected
  by `ColourIndex` through the native-equivalent function. These are not the retired legacy palette
  controls.
- Legacy protocol and saved-preset fields remain exact additional filters, shown read-only when a
  preset contains them. Loading and clearing a preset replaces or clears those extras rather than
  silently dropping constraints.

## Complete control inventory

The following unaffected controls retain their distinct predicates and scopes:

| Control                                                        | Scope and current predicate                                                                                                                               |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Biome / `target_biome`                                         | Planet biome index; proven values only, excluding `Test`.                                                                                                 |
| Biome subtype / `biome_subtype`                                | Planet subtype index; distinct from biome.                                                                                                                |
| Planet size / `planet_size`                                    | Generated size enum; `Giant` is not synonymous with gas giant.                                                                                            |
| Non-gas giant / `non_gas_giant_planet`                         | Target planet is `Giant` and not `GasGiant`.                                                                                                              |
| Rings / `planet_rings`                                         | Target planet generated ring flag.                                                                                                                        |
| Has moons / `planet_has_moons`                                 | Target planet has one or more moons.                                                                                                                      |
| Water / `water_planet`                                         | Target planet has water.                                                                                                                                  |
| Paradise / `paradise_planet`                                   | Lush, excluding Structure/Infested/Swamp; Default intensity, no storms, and difficulty-selected sentinel level 0. This is not merely Lush or HighQuality. |
| Deep water / `deep_water_planet`                               | Target planet has deep water; independent of Water.                                                                                                       |
| Extreme hazards / `extreme_hazard_planet`                      | Target planet extreme-hazard flag.                                                                                                                        |
| Sentinels / `sentinels`                                        | Target planet sentinel flag.                                                                                                                              |
| Extreme sentinels / `extreme_sentinel_planet`                  | Target planet extreme sentinel flag.                                                                                                                      |
| Corrupt sentinels / `corrupt_sentinel_planet`                  | Target planet corrupt sentinel flag.                                                                                                                      |
| Prime / `prime_planet`                                         | Target planet prime-generation flag.                                                                                                                      |
| Infested / `infested_planet`                                   | Target planet has Infested subtype.                                                                                                                       |
| Ordinary / `normal_planet`                                     | Target planet normal-group predicate; not a universal complement.                                                                                         |
| Relic / `relic_planet`                                         | Target planet Weird biome with Structure subtype.                                                                                                         |
| RGB biome / `rgb_planet`                                       | Target planet biome is Red, Green, or Blue.                                                                                                               |
| Has scrap / `has_scrap`                                        | Target planet generated scrap flag.                                                                                                                       |
| Creature discovery / `suitable_creature_discovery`             | Target planet suitability flag.                                                                                                                           |
| Weird creature discovery / `suitable_weird_creature_discovery` | Target planet distinct weird-creature suitability flag.                                                                                                   |
| Creature taming / `suitable_creature_taming`                   | Target planet taming suitability flag.                                                                                                                    |
| Robot creature discovery / `suitable_robot_creature_discovery` | Target planet robot-creature suitability flag.                                                                                                            |
| Life level / `life_level`                                      | Generated target-planet life enum, captured when selected.                                                                                                |
| Creature abundance / `creature_life_level`                     | Generated target-planet creature enum, distinct from life level.                                                                                          |
| Building density / `building_density`                          | Generated density category, not a biome selector.                                                                                                         |
| Resource abundance / `resource_level`                          | Generated abundance enum, distinct from resource IDs.                                                                                                     |
| Weather type / `weather_type`                                  | Generated target-planet weather type; proven values only.                                                                                                 |
| Star colour / `star_type`                                      | Native system star-type enum.                                                                                                                             |
| Minimum planets / `minimum_planets`                            | Native system planet-count minimum, not candidate count.                                                                                                  |
| Wealth / `wealth_class`                                        | Native system economy enum.                                                                                                                               |
| Trading class / `trading_class`                                | Native system trading enum; pirate semantics remain native.                                                                                               |
| Conflict / `conflict_level`                                    | Native system conflict enum.                                                                                                                              |
| Population / `population_state`                                | Native system population state, presented as Inhabited, Empty, or Abandoned.                                                                              |
| Dominant race / `race`                                         | Native system race; only proven ordinary races are advertised.                                                                                            |
| Space anomaly / `anomaly`                                      | Native-only system criterion, absent from copied snapshots.                                                                                               |
| Pirate system / `pirate_system`                                | Native pirate requirement/exclusion with supplemental passes.                                                                                             |
| Contains any giant / `giant_planet_system`                     | System aggregate over any Giant planet.                                                                                                                   |
| Contains gas giant / `gas_giant_system`                        | System aggregate over any GasGiant biome.                                                                                                                 |
| Contains non-gas giant / `non_gas_giant_system`                | System aggregate over Giant non-GasGiant planets.                                                                                                         |
| Contains waterworld / `waterworld_system`                      | System aggregate over Waterworld biome.                                                                                                                   |
| Contains water planet / `system_water`                         | System aggregate over `has_water`.                                                                                                                        |
| Contains deep water / `deep_water_system`                      | System aggregate over `has_deep_water`.                                                                                                                   |
| Contains weird / `system_weird_planet`                         | System aggregate over Weird biome.                                                                                                                        |
| Contains infested / `system_infested_planet`                   | System aggregate over Infested subtype.                                                                                                                   |
| Contains ordinary / `system_normal_planet`                     | System aggregate using the normal-group predicate.                                                                                                        |
| Contains relic / `system_relic_planet`                         | System aggregate over Weird Structure planets.                                                                                                            |
| Contains RGB / `system_rgb_planet`                             | System aggregate over Red, Green, or Blue biomes.                                                                                                         |
| Contains corrupt sentinels / `system_corrupt_sentinel_planet`  | System aggregate over corrupt sentinel planets.                                                                                                           |
| Contains extreme storms / `system_extreme_storm_planet`        | System aggregate over extreme-weather planets with nonzero storm frequency.                                                                               |

`required_resources` is a same-planet conjunction across three survey slots; it is not a complete
planet inventory. The singular protocol `resource` remains an API compatibility field, not a second
form concept. `Any` disables a predicate rather than matching a sentinel. Legacy protocol fields
such as old palette and weather fields remain exact saved extras and are not silently approximated
by the current controls.

## Reference evidence

Water-colour criteria require water on the same target, not merely an assigned colour on a dry
planet. Vegetation hue classification treats green-dominant olive/yellow-green as Green; it does not
infer the proportion of yellow patches or simulate scene lighting.

Reference planet: Mosworkin, discovered name Cape Oath, address `0x00300A31FBB284D6`, planet index
2; Lush HydroGarden LilyPad with 10 resolved islands. Its observed base values were Green
Grass/GrassAlt, Purple Leaf, actual sky Blue, actual water Cyan/turquoise, and screen filter 42 New
Vibrant.

Evidence is retained under
`games/no-mans-sky/investigation-state/runs/20260915T030000Z-colour-island-reference`. The native
water helper at `0x141692BA0` matched all 19 records with maximum error ≤ 2.74e-7; the sky selector
is at `0x141680AD0`. These observations establish input selection and colour classification
boundaries, not a guarantee of final rendered pixels or final shipped status.
