# Weather and planetary resources

## Storms

Frequency controls scheduling independently of weather type/severity. Zero frequency bypasses
scheduling; frequency categories are not fixed intervals. The extreme hazard/intensity selector
differs from the similarly named extreme-weather byte. Temperature, toxicity and radiation can
override default profiles separately. Ambient/storm entries contain normal/extreme values.

| Weather selections                           | Native warning family                |
| -------------------------------------------- | ------------------------------------ |
| Humid, Swamp                                 | Superheated rain                     |
| Snow                                         | Blizzard                             |
| Toxic                                        | Toxic rain                           |
| Radioactive                                  | Radioactive supercell                |
| Dust, Scorched, GasGiant                     | Firestorm                            |
| Lava, Fire                                   | Wall of flame                        |
| RedWeather, GreenWeather, BlueWeather, Weird | Gravitational anomaly                |
| Bubble                                       | Atmospheric bubbles; generic warning |
| Clear, ClearCold                             | Generic incoming-storm warning       |

Lightning, tornadoes and localized anomalies are secondary hazards. A storm-family label alone does
not establish active localized effects or actual hazard severity.

## Discovery hints

| Hint ID           | Occurrence        | Icon    |
| ----------------- | ----------------- | ------- |
| `UI_BONES_HINT`   | Ancient bones     | BONES   |
| `UI_SCRAP_HINT`   | Salvageable scrap | SALVAGE |
| `UI_B_SWARM_HINT` | Swarm debris      | SWARM   |
| `UI_BUGS_HINT`    | Vile Brood        | GRUBS   |

Hint construction follows selected external object lists. `HasScrap` is a broader eligibility input
than the completed hint list. Dissonance plus Scrap does not establish Swarm Debris: additional
biome and probability gates apply. Multiple hints can coexist.

Combat difficulty's Sentinel level describes encounters under that difficulty. World dissonance is
represented separately through its normal-difficulty corrupted-Sentinel entry. Difficulty can
suppress encounters without removing the world property.
