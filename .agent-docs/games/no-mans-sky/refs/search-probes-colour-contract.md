# Search Probes biome and colour contract

## Biome membership and colour grading

The Biome menu combines native Red/Green/Blue as `Mega-exotic`; the separate planet-level
`Chromatic biome` control is removed. Saved chromatic requirements appear through the Biome control
and become ordinary biome restrictions when edited. Narrower saved Red/Green/Blue selections retain
their exact semantics as unavailable choices. Contradictory saved combinations remain intact until
replaced through that control; loading them does not discard other settings. The system composition
control is labelled `Contains a mega-exotic biome`. Those three categories share six variants:
HugePlant, HugeLush, HugeRing, HugeRock, HugeScorch, and HugeToxic. Every variant permits Default
and Weird1–Weird8 screen filters with positive weight. Biome membership therefore does not guarantee
anomalous colour grading.

The reverse inference also fails: current Lush and Frozen biome definitions permit Weird2 and
Weird4. A colour-effect search must inspect the selected filter rather than infer it from biome.
`GcPlanetData.Weather.ScreenFilter` is available through the native capture code. Weird1–Weird8
occupy native values 12–19. This gives a precise predicate for that filter family, independent of
biome. Other generated colour effects exist; this family does not encompass every non-default LUT.

The eight SDR LUTs have different transformations. Weird4 and Weird7 specify distance fading;
rendering blends base, distance, storm, and effect LUTs. An assigned-filter criterion describes the
planet's grading configuration, not a promise that every object always appears strongly tinted. The
native query's `+0x164` slot is weather type, not screen filter; acquiring the latter requires the
existing live generated-planet capture path.

Current biome definitions select 41 distinct screen filters with positive weight; the general enum
has 85 entries. Native generation can override the biome selection with CorruptSentinels (83) when
the selected difficulty has corrupted Sentinels. The menu includes this override as
`Corrupted Sentinels`. The appearance reader supports all 85 native entries rather than restricting
itself to the biome weight table. `Any` omits a filter predicate and `Default` specifically requires
native Default. Matching uses the selected native filter, independent of biome, weather type and
storm frequency. The UI/native protocol changes with the added criterion. Offline SDR colour probes
identify Weird7 as amber/sepia and Weird6 as dark grey/red; these descriptions are analytical
labels, not localized game names. The retained interactive preview compares all 41 SDR
transformations. SDR LUTs are 16- or 32-cubed BGRA8 textures; HDR LUTs are 33-cubed R10G10B10A2
textures sampled through a separate log encoding in the current HDR shader. An SDR preview is not an
HDR simulation.

## Vegetation colour inputs

Plant and Leaf classify their palette's primary RGB by hue. They do not inspect material bindings,
alternates or brightness. Grass previously used the same classifier; the candidate now resolves
terrain-bound grass colours and distinguishes Black and White before hue. These are appearance
categories, not native game enum values.

HugeLush selects NEWCROSSGRASS with `MatchGroundColour=true`. All nine material variants enable
`_F56_MATCH_GROUND`; the corresponding compiled fragment shader mixes `gTerrainColour1Vec4` and
`gTerrainColour2Vec4`, modulates brightness with the grass texture, and converts to linear colour.
Its output colour is consequently not determined by the Grass palette's hue.

Ixha Delta has native Green/HugeLush, selected filter Default, and green primary Grass RGB
`(0.261, 0.283, 0.163)`. Its selected base tile set uses RockDark, RockLight, and RockSaturated for
the surface colours. The captured terrain colours match those palette bindings exactly and include
blue-grey `(0.099, 0.111, 0.118)` and grey `(0.098, 0.098, 0.098)`. These entries alone do not
establish which values reach the grass shader. The current planet render setup converts all tile RGB
values to HSV, keeps their RGB identity, and binds tile slots 1 and 3 to `gTerrainColour1Vec4` and
`gTerrainColour2Vec4`. Passive reads of the live resource manager confirm these exact uniforms in
UBERSHADER, REFLECTIONPROBE and RENDERIMPOSTER. On Ixha Delta their RGB inputs are brown-grey
`(0.329, 0.318, 0.310)` and `(0.267, 0.228, 0.208)`. The loaded grass material records have no
overriding terrain-colour uniforms. Scene lighting and postprocessing still matter. The
resource-generation Main/Patch ground-colour selector is a separate path from these uniforms. An
appearance-oriented grass filter must resolve the active material bindings; adding a Black choice to
the primary-palette hue classifier cannot fix this case.

A grass observation cannot establish a planet's plant or leaf colour: their materials can bind
different palettes and alternates. Colour grading acts on rendered scene colours generally. Literal
zero-valued palette entries alone do not prove visible biological leaves use those entries.

## Grass appearance candidate and acceptance

The current white reference is Antwithe Guro in Euclid, portal `614CFE98E047`. Its screenshot glyphs
match the passive loaded coordinates exactly. Native biome is Lush/HighQuality and grading Default.
NEWLUSHGRASS uses the same ground-matching shader as NEWCROSSGRASS. Its actual shader terrain RGBs
are `(0.678, 0.573, 0.518)` and `(0.353, 0.400, 0.475)`, matching tile slots 1 and 3. The primary
Grass palette would incorrectly classify this world as Orange. The former Eissentam reference
`401298055510` is rejected: the user visited and found its appearance changed after Worlds.

Current asset coverage includes every external object table referenced by the biome registry and
round-tripped scenes/materials for all six grass-named models in GRASS placement records. Lush,
cross, bubble lush and large barren grass use ground matching. Desert scrub and toxic mushrooms use
other material paths. Candidate grass searches require a positive spawn density for one of the four
ground-grass models in the native selected biome tables. Generic building-decoration tables, flowers
and mushrooms do not establish grass cover. Native resource acquisition/release and the bounded
owned object-table cache are reused; no borrowed game pointers enter stored facts.

Grass colour uses the main shader tint, terrain colour 1 / tile slot 1, with the selected SDR LUT.
Secondary patches do not qualify. The former evenly sampled gradient accepted minority patch colours
and did not represent their actual prevalence. Ladonnea Delta supplies the counterexample: the user
observes predominantly pink grass with occasional white patches. Its main RGB is
`(0.493, 0.258, 0.332)` and its secondary RGB is `(0.427, 0.427, 0.427)`. The former rule accepted
Magenta, Black and White; the primary-tint rule accepts Magenta only.

The loaded shader's blend scales are `(0.001, 0.01, 0.6, 0.19)`. Its two-octave Perlin blend and
positive bias favor the main tint. An independent volume sample using the extracted current noise
texture confirms that bias; it is not a measurement of grass-covered area on a particular planet.
The product classifies the primary tint directly rather than inventing a surface-coverage fraction.
Oklab relative chroma at most 0.10 is treated as neutral; lightness 0.50 separates Black/White.
Lightness below 0.20 is Black regardless of hue. These thresholds are calibrated to the current
observations. No separate Grey category is exposed. Legacy Neutral selections become Black plus
White. An owned marked colour set distinguishes grassless facts from unknowns. Current searches
assign one primary grass colour.

The runtime reads current game LUTs from the exact-build HGPAK archive rather than shipping game
assets. Its bounded compressed/raw chunk reader and DDS decoder reproduce all texel values of all 85
native SDR filter mappings against independently extracted LUTs. Detected mod overrides of a
selected LUT fail explicitly; there is no inferred mod load order. Archive reads and decoded LUTs
are bounded and cached.

Production capture/classification/predicate functions over the retained reference snapshots return
Black only for Ixha Delta, White only for Antwithe Guro, and Magenta only for Ladonnea Delta. Host
controls cover saturated green, minority-patch rejection, grading changes, missing grass, inactive
spawns, and archive/texture validation. They do not establish general visual accuracy. The candidate
assumes neutral daylight and full selected SDR grading; it does not reproduce scene lighting,
exposure/tonemapping, texture brightness modulation, distance blending, storms or the HDR pipeline.
Those effects can change borderline classifications. Modified blend rules or grass placement can
also alter which tint dominates visually. Additional independent visual controls remain necessary
before broader appearance claims.

The primary-tint correction and complete native LUT mapping are installed and hash-verified in
Amethyst and the linked game files. Fresh native black-grass searches with unrestricted world
filtering return the same 100 results with two and sixteen workers. A Lush/corrupted-Sentinel
control acquires grass appearance across 1,000 systems, returns 28 matches, and reproduces those
matches from cache without generation. The formerly omitted filter is therefore exercised through
the actual LUT acquisition path. Generator bytes, the filename map and table resource/reference
inventories remain unchanged. User settings and presets are restored exactly; saves are not
replaced. These checks establish successful acquisition and filtering, not broader visual accuracy.
The loaded system is intentionally excluded from displayed search results, so its classification is
verified through acquired facts rather than expecting it in the result list. Earlier native
acquisition/cache/cancellation evidence remains in the raw run.

The supplied
[Husalvangewi black-grass report](https://www.reddit.com/r/NMSCoordinateExchange/comments/pd5uty/black_grass_planet_husalvangewi_galaxy/)
identifies Behealio, portal `5045FDFF9FFD`, in galaxy 70. Its 2021/version-3.5 image establishes a
historical reported appearance, not unchanged generation in the current game.

## Evidence

Current 7.06 executable identity, read-only process captures, archive and asset hashes, untouched
semantic round trips, material flags, decoded SPIR-V, and LUT analysis are retained in
`games/no-mans-sky/investigation-state/runs/20261008T004700Z-grass-colour-investigation/`. The
survey covers all 99 biome definitions referenced by BIOMEFILENAMES; binary filter decoding was
checked against nine round-tripped biome XMLs. Loaded Folk supplies a Weird2 positive control;
loaded Ixha Delta supplies a Default negative control within the same native biome family. The
current doctor also reports an uninterruptible graphics worker. Evidence supports content and
passive-memory comparisons, with no performance claims or automated gameplay inputs.
