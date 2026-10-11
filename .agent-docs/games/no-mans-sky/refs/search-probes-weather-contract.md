# Search Probes storm filters

## Public behavior

The Weather subsection exposes Storm frequency (Any/None/Low/High), Extreme storms
(Any/Require/Exclude) and a Storm type multi-select. None means no storms; Low and High mean
recurring storms. Selecting Low and High accepts either cadence. A planet needs a recurring storm
schedule to match a storm type or Require extreme storms. Frequency is the generated cadence
category; exact intervals vary with the game's global timers and intensity. The reserved continuous
seasonal schedule is grouped with High rather than offered as an ordinary planet option.

Extreme storms means a selected extreme profile that increases storm heat, cold, toxicity or
radiation beyond both its ordinary storm profile and its extreme ambient conditions. This uses
loaded hazard values, with no biome exclusions, weather-type exceptions or numerical cutoffs. It
recognizes extreme Lush rainstorms while distinguishing mild bubble/gravitational weather. It
describes environmental storm severity, not the player's protection settings or every secondary
weather event. Contains extreme storms uses the same predicate across the system's planets.

Each subsection's All/Any rule applies to its active criteria, including exclusions. Unknown facts
remain unknown until acquired; neither a planet exclusion nor a system exclusion treats missing
hazard observations as a negative result. No-storm and normal-intensity query facts settle severity
absence immediately. Cached hazard capability is owned data and is reused with the ordinary
configuration/session cache lifetime.

## Storm families and labels

The categories follow the current executable's storm-warning routes. Multi-selected types are
alternatives on the target planet, independently of the subsection match mode. Each planet has one
primary storm family; All/Any combines the active filters, not values within this list.

| Public label          | Raw weather selections                       | Warning/effect authority                                   |
| --------------------- | -------------------------------------------- | ---------------------------------------------------------- |
| Superheated rainstorm | Humid, Swamp                                 | WEATHER_WARN_LUSH                                          |
| Blizzard              | Snow                                         | WEATHER_WARN_COLD                                          |
| Toxic rainstorm       | Toxic                                        | WEATHER_WARN_TOXIC                                         |
| Radioactive supercell | Radioactive                                  | WEATHER_WARN_RADIO                                         |
| Firestorm             | Dust, Scorched, GasGiant                     | WEATHER_WARN_HOT                                           |
| Wall of flame         | Lava, Fire                                   | WEATHER_WARN_LAVA                                          |
| Gravitational anomaly | RedWeather, GreenWeather, BlueWeather, Weird | WEATHER_WARN_GRAV / UI_GRAVITY_WARNING_OSD                 |
| Bubble storm          | Bubble                                       | Generic warning; BUBBLE weather atmospheric particle asset |
| Other storms          | Clear, ClearCold                             | Generic incoming-storm warning                             |

Bubble storm is a descriptive Search Probes label. It selects the atmospheric bubble weather route
during recurring storms; it is distinct from choosing the Bubble biome subtype. Other storms
provides a destination for the remaining generic warning routes. Secondary hazards such as
lightning, tornadoes and localized anomalies can accompany several storm families. Their occurrence
is not inferred from a biome label or promoted to a separate storm family here.

## Current native evidence

The exact installed 7.06 executable and current shipped assets were checked before collecting
evidence. Native scheduling at `0x14131A0B0` returns immediately when `GcPlanetWeatherData`
frequency is zero, before selecting interval/fallback timers. The query's ExtremeHazard byte at
`+0x131` is the extreme intensity selector; the distinct ExtremeWeather byte at `+0x130` has
biome/type restrictions and is not the user-facing storm predicate.

The hazard selector at `0x141696270` reads the generated weather type, the generator's bounded
weather-properties pointer list (`+0x504/+0x508`) and default weather table (`+0x4F8`). Temperature,
toxicity and radiation overrides are the properties' `+0xBE0/+0xBE1/+0xBE2` booleans. Their
six-state arrays begin at `+0xAD0/+0xB30/+0xB60`, or the default table's `+0x110/+0x140/+0x170`.
Each state is two floats ordered extreme/normal; Ambient is state 0 and Storm is state 3. Capture
copies only owned floats and validates finite values and the selected weather-table bound. No native
reference is retained and no packaged/linked mod inventory is involved.

Isolated replay of this exact selector against 14 current vanilla weather assets agrees on all 504
float comparisons, including overrides and default fallbacks. The warning table initialization at
`0x141311D61` was also replayed to recover all 17 warning entries, and their English labels were
checked against current localization tables. Exact executable replay establishes the native table
routes; it does not claim measured gameplay hazard drain or live visual acceptance.

Raw evidence is retained under
`games/no-mans-sky/investigation-state/runtime/search-probes-ui-preview/validation/storms/`: the
doctor identity, native disassembly, `warning-table.py/.json` and `hazard-selector.py/.json`.
Current assets and untouched semantic roundtrips remain in the corresponding ignored investigation
run directories referenced by those artifacts and the validation record.

## Qualification and remaining gate

Model/native controls cover absence, positive severity, mild profiles, malformed native inputs,
override/default memory reads, incremental system aggregation, unknown exclusions, All/Any,
serialization, cached-fact reuse and removed public keys. The standalone UI reloads the same Weather
section used by the overlay. Workspace tests and the Windows production build qualify source and
build behavior. Fresh live searches and HUD-warning/visual comparisons for the new controls remain
pending; no game was launched or production files replaced for this weather investigation.
