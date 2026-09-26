# Weather Indicator Short inspection

## Decision

Weather Indicator Short `1.0.1` is a useful weather-key taxonomy, but it did not implement or
reverse-engineer a runtime weather classifier. Its archive contains only `LocTable.mxml`. The file
replaces 305 existing English weather-description strings with one of five author-supplied labels:
No Storms, Occasional Storms, Frequent Storms, Extreme Storms, or Unknown.

The general idea remains structurally relevant to Cosmos 7.01: every one of those 305 localization
IDs still exists in the current English localization data. The individual English replacements are
nevertheless the author's classification assertions, not executable logic and not proof that every
label exactly describes current runtime behavior.

For System Search, current generated planet data provides a stronger contract. The current
`GcPlanetWeatherData` layout directly contains `StormFrequency` (`None`, `Low`, `High`, `Always`),
`WeatherIntensity` (`Default`, `Extreme`), and a 17-value `WeatherType`. Those fields should be
copied from temporary generated planet data and checked directly; the finder should not infer storm
frequency from a localized weather-description ID or import this mod's labels.

## Artifact and mechanism

| Field          | Value                                                                    |
| -------------- | ------------------------------------------------------------------------ |
| Nexus page     | [Weather Indicator](https://www.nexusmods.com/nomanssky/mods/3373)       |
| Nexus file     | Short, file `39729`                                                      |
| Version        | `1.0.1`                                                                  |
| Published      | February 22, 2025                                                        |
| Claimed target | Worlds Part II 5.57                                                      |
| Archive hash   | `d96423fc2e66ea42bdac87cb09cea9478c1438c070c2bc6f346f2bd16d97af4c`       |
| Contents       | One 338,375-byte `LocTable.mxml`; no EXML, MBIN, DLL, Lua, or executable |
| Catalog status | `diagnostic-only`                                                        |

The committed identity and hash are in the
[NMS third-party catalog](../../../../../.squinch/games/no-mans-sky/third-party/artifacts.toml).
Downloaded and extracted bytes remain local and ignored because the author does not grant general
redistribution or modification permission.

The 305 English replacements divide as follows:

| Replacement label | IDs |
| ----------------- | --: |
| No Storms         | 104 |
| Occasional Storms |  83 |
| Frequent Storms   |  83 |
| Extreme Storms    |   4 |
| Unknown           |  31 |

Most `_CLEARn` keys become No Storms, most `EXTREMEn` keys become Frequent Storms, and most base
weather keys become Occasional Storms. Red, Green, Blue, and Waterworld keys are mostly classified
as Unknown; the four GasGiant keys are classified as Extreme Storms. This is a consistent manual
mapping convention, not a calculation performed by the mod.

## Current-engine weather contract

The exact current MBINCompiler source snapshot identifies these fixed fields in
`GcPlanetWeatherData`:

| Field              | Structure offset | Current enum                                                                                                                                         |
| ------------------ | ---------------: | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `StormFrequency`   |          `0x168` | None, Low, High, Always                                                                                                                              |
| `WeatherIntensity` |          `0x170` | Default, Extreme                                                                                                                                     |
| `WeatherType`      |          `0x174` | Clear, Dust, Humid, Snow, Toxic, Scorched, Radioactive, RedWeather, GreenWeather, BlueWeather, Swamp, Lava, Bubble, Weird, Fire, ClearCold, GasGiant |

`GcPlanetData.Weather` begins at `0x1CE0`, making the corresponding temporary-planet offsets
`0x1E48`, `0x1E50`, and `0x1E54`. The retained source evidence is
`games/no-mans-sky/investigation-state/runs/20260912T192340Z-source-snapshot-65488937/`.

Current-runtime validation then copied those fields during the temporary planet destructor without
retaining a pointer. The authoritative complete local graph covered 15,053 remote systems and 71,730
planets. Every copied value was inside the current enum domain. Storm frequency was None on 30,862
planets, Low on 33,494, and High on 7,374; Always did not occur. Both intensities and 14 of 17
weather types occurred. Repeating the same address produced identical per-planet weather triples,
and exact compound searches found both Lush/no-storm and High-frequency/Extreme targets. A
deliberately absent Always-frequency query completed the full window without a false match. The
retained summary is
`games/no-mans-sky/tooling/runtime/.resident-search/sessions/1789283539387536500-f8012cc566284ebeb53c66390b085448/results/matrix-full-1789283540088867715-summary.json`.

The form exposes only positively observed current values. `Always`, `RedWeather`, `GreenWeather`,
and `BlueWeather` remain valid diagnostic enum values but are withheld until a positive current
runtime sample proves their generated use.

The current `GcPlanetInfo` schema also has a 128-byte `Weather` localization-ID field. It does not
provide the missing crosswalk in the offscreen search path: a current runtime probe found that field
empty in the temporary `GcPlanetData` produced by the type-1 solar query and failed closed. The
current `WEATHERLIST.MBIN` maps the 17 weather-type enums to weather-property resources but contains
no localization-ID-to-frequency table. Consequently, this investigation cannot validate the mod's
305 individual label assertions from offscreen generated data. Doing so would require a separate
loaded-planet display-info/frequency correlation probe or exact disassembly of the display string
selector. That work cannot improve System Search because its direct frequency enum is already more
precise.

The supporting current-schema and weather-table evidence is retained at
`games/no-mans-sky/investigation-state/runs/20260912T210420Z-source-snapshot-b55ecc58/` and
`games/no-mans-sky/investigation-state/runs/20260912T210039Z-roundtrip-5d2b2c52/`. The bounded
offscreen negative control is
`games/no-mans-sky/tooling/runtime/.resident-search/sessions/1789248106016833600-510822d54bc54d13b60af66e5522d54a/results/weather-description-audit.json`.

The older mod therefore contributes two useful facts without serving as System Search's algorithm:

1. Hello Games has long grouped player-facing weather names into meaningful storm-frequency
   families, so a frequency filter is a sensible feature.
2. Localization replacement is the wrong seam for an exact search engine when the generated planet
   object exposes the underlying enum directly.

## Reproduction

```bash
tooling/squinch third-party no-mans-sky import \
  --artifact-id nms-nexus-3373-39729-weather-indicator-short \
  --archive '/var/home/scott/Downloads/Weather Indicator Short-3373-1-0-1-1740203995.zip'

tooling/squinch third-party no-mans-sky inspect \
  --artifact-id nms-nexus-3373-39729-weather-indicator-short

tooling/squinch third-party no-mans-sky validate
```

The current source layout is reproduced by the request retained beside the source-snapshot result
above. Current localization-key presence is checked against the English MXML files extracted and
round-tripped in the pinned Cosmos 7.01 investigation runs.
