# Search Probes biome and colour contract

## Biome membership and colour grading

The Biome menu combines native Red/Green/Blue as `Mega-exotic`. The system composition control is
labelled `Contains a mega-exotic biome`. Those three categories share six variants: HugePlant,
HugeLush, HugeRing, HugeRock, HugeScorch, and HugeToxic. Every variant permits Default and
Weird1–Weird8 screen filters with positive weight. Biome membership therefore does not guarantee
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

`Flora colour` classifies colours present on discoverable surface flora. It follows the selected
positive-density object tables into renderable mesh materials, including stems, bark and fixed
colour tissues. Different parts and species can have different colours. Each highest-detail mesh
uses bounded, deterministic local-surface-area samples with paired UVs and vertex RGBA. A mesh
qualifies a colour when that category accounts for more than half of its visible sample weight;
flora parts are combined rather than assigning one palette to the whole plant. Scene emitters and
attached effects without their own flora discovery identity do not contribute.

Current world object construction creates procedural textures. Its native caller disables the
existing-texture replacement route, so authored replacement choices are not classification inputs.
The creator gathers layer and option names across materials before selection, including
`SelectToMatchBase` dependencies. Classification bounds this unresolved selection with the compiled
local texture alternatives and permitted layer omissions; it does not assume that each material
selects its options independently. Only colours stable across that bound qualify. This conservative
rule can omit a colour that appears only for one actual procedural choice. Palette alternatives zero
through three use their corresponding slots; alternatives four and five use slot three. Match-ground
objects instead supply the selected source's Main/Patch terrain colour to the texture creator. Its
source index and native validity bound determine that colour; an invalid index uses the native blue
default. Native palette mode zero leaves palette alternatives unchanged, including objects with
authored palette-swap flags.

Diffuse textures are read from current game archives. Procedural average metadata uses the DDS
reserved word as packed AARRGGBB; unrelated exporter tags do not determine validity. Shader
recolouring preserves texture shading through its HSV transform, combines layers in reverse
descriptor order, and preserves the first present layer's raw alpha. Primary and secondary diffuse
textures use their corresponding paired UVs; the secondary texture's alpha blends their linear RGB.
Constant-colour materials use their actual uniform and shader gamma conversion. Enabled vertex RGB
and alpha gates modulate the same surface samples, and native material opacity and cutout controls
determine their contribution.

A canonical diffuse mip, bilinear repeated sampling, representative unit diffuse illumination,
current SDR tone mapping and the selected world LUT produce a daylight appearance estimate. This
does not reconstruct shadows, exposure, storms, secondary lighting, perspective or every viewpoint.
Unresolved procedural choices qualify only colours shared by the conservative variant bound.
Modified scenes, materials or placement can change what is visible.

Each model calculation reuses prepared material options and lazily composed texture recipes across
its meshes. Primary and secondary sampler namespaces have separate entries. The memo is local to one
spawn, palette context and world grading; it retains at most 16 MiB of texture entries and 65,536
exact RGB classifications. UV/vertex sampling, alpha weights, recipe order and majority thresholds
are unchanged. Requested-category decisions can finish once the remaining surface weight cannot
change their outcome; unrequested categories stay unknown until acquired.

Grass uses its separately calibrated main-tint and material-brightness contract below. A grass
observation cannot establish the colour of other flora because its materials can bind different
palettes, alternatives or fixed textures.

## Atmospheric and water colour anchors

Cloud, daytime sky, horizon, sky fog and height fog classify their selected clear-day colour
anchors. Night sky uses the selected clear-night anchor. Water uses its own optical colour with a
separate positive water-presence requirement. Linear anchors pass through the representative SDR
tone map and selected world LUT before the shared hue-aware colour classifier. The eight hue
families and Black/Grey/White describe this representative appearance rather than raw native hue
indices.

These controls do not simulate the complete sky-scattering or water-reflection renderers. Looking
toward the sun, sunset, storms, reflections, foam and nearby lights can change the visible colour.
Sunset is a time-dependent presentation and has no separate searchable colour control. Reachability
uses the selected native sky tables and only the grading choices permitted by each biome, including
the corrupted-Sentinel override. Daytime sky, horizon and sky fog have no Black choice; height fog
has no Purple, Grey or Black choice. Cloud, night sky and water expose all eleven categories
supported by those anchor and grading combinations.

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

## Grass appearance and acceptance

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

The search prepares the main-tint appearance once. When its hue is invariant across material
brightness, a nonmatching choice can reject the planet before object-table acquisition. Stored
candidate bounds support negative decisions only: a possible hue remains unknown until actual grass
presence and materials are resolved. Later searches cannot turn these bounds into confirmed grass
colours. Sky, fog and water appearance anchors and enabled terrain layers reject nonmatches before
object acquisition. Object flags and the calibrated grass-material classification reject nonmatches
before flora's mesh and texture classification. Shared object-table reads avoid serializing warm
workers, while native table loading remains exclusive. Component performance and its limits are
recorded in [product validation](../../../../games/no-mans-sky/mods/search-probes/VALIDATION.md).

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
Grass acquisition retains a mask of active ground-grass models. For each selected model, the
candidate decodes its current vanilla diffuse DDS textures (BC1/BC7), applies the material sampler's
sRGB decode, and obtains the opacity-weighted median of the shader's near-camera multiplier
`min(2 * max(diffuse.rgb), 1)`. Transparent atlas padding has no weight. The multiplier precedes
world grading. This estimates representative blade brightness; it does not reconstruct mesh UV
coverage, procedural texture recolouring, lighting, exposure or pixel footprints. NEWLUSHGRASS has
median multiplier 1.0, preserving Antwithe Guro; large barren grass has multiplier 0.558. Cross
grass has nine material variants. The current descriptor roundtrip confirms nine alternatives under
one `_GRASS_` group, each with `Chance=0`; it does not establish the runtime selection algorithm.
The captured query data identifies the selected scene, not its rendered descriptor variant. The
candidate therefore intersects the possible colour sets of all active models and materials. Only
shared colours qualify; widely disagreeing materials do not qualify a minority colour as the main
appearance. This conservative fallback can miss worlds whose selected variant alone would match. The
descriptor audit is retained in
`games/no-mans-sky/investigation-state/runs/20261008T-grass-calibration/descriptor-roundtrip.json`.

Colour identity considers the source main tint, graded main tint and graded texture-brightness
representative. The extracted shader fades texture darkening out from 24 to 56 metres, so the
brighter main tint is also relevant. Oklab relative chroma above 0.08 in both source and graded main
tint preserves its graded hue even when the nearby texture estimate becomes dark and muted. A
strongly coloured graded main tint (above 0.10) also preserves its hue when the source itself is
neutral. Independently, representative relative chroma above 0.08 preserves the representative's
hue. These gates apply to every hue, with lightness below 0.20 treated as too dark to establish
colour. Only samples passing these neutrality gates receive Black/Grey/White by representative
lightness. Grading that removes source chroma can still qualify; the raw tint alone cannot veto
neutral matches. The 0.08/0.10 limits are calibrated heuristics, not perceptual guarantees or
per-hue exceptions. A chromatic source below Oklab lightness 0.45 that grading maps to a neutral
shadow also receives three daylight probes at lightness 0.45, 0.55 and 0.65. Linear-RGB exposure
scaling preserves its chromaticity before grading. All three probes must retain a non-neutral,
consistently named hue before that hue can replace the shadow classification. Neutral source tints,
genuine desaturation and clipped highlights retain their existing handling. These are daylight
identity probes, not a reconstruction of scene illumination or exposure. Olarac Minor supplies the
clipped-shadow counterexample: Vibrant bright grading flattens its dark green input, but the three
daylight probes remain Green. Its selected bubble grass now matches Green and rejects Black, Grey
and White.

Hue naming probes an equal-lightness neutral grey through the same LUT. If that reference has
lightness at least 0.20 and relative chroma at most 0.08, its mild cast is accounted for with linear
Bradford adaptation to an sRGB D65 grey of equal luminance. Strongly coloured neutral references
retain the original graded hue, as do truly neutral references and adaptation results with no hue.
This changes chromatic hue names only; it cannot introduce Black/Grey/White matches. The standard
cone-response scaling uses the Bradford matrix combined with linear-sRGB/XYZ transforms, with
negative channels clipped and over-range linear RGB scaled uniformly before sRGB encoding.
[CSS Color 4 conversion algorithms](https://www.w3.org/TR/css-color-4/#color-conversion-code) and
[ICC's chromatic adaptation specification](https://www.color.org/specification/ICC1v43_2010-12.pdf)
provide the method. The product's D50-to-D65 numerical controls use the independent published CSS
matrix. Applying this method to the LUT's neutral-grey axis is an appearance-estimation choice, not
a claim that game grading is a physical illuminant or that every viewer adapts fully.

Neutral categories overlap narrowly around the calibrated lightness boundaries 0.40 and 0.65: Black
qualifies at or below 0.425, Grey from 0.375 through 0.675, and White at or above 0.625. A
borderline world can match two adjacent choices; Black and White never overlap. These are appearance
heuristics, not native game values or measured perceptual error bounds. Grey replaces the
pre-release Neutral slot; no compatibility conversion remains. An owned marked colour set
distinguishes acquired nonmatches from unknowns.

Iomi 84/C9 has graded unmodulated main-tint lightness 0.603 and relative chroma 0.091. Its selected
barren table contains large ground-matching grass. Applying texture brightness before the LUT
rejects the reported White false positive; its representative now falls in the Black/Grey overlap.
The darker Apaeumasan remains Black. All twelve texture medians match an independent Pillow DDS
decoder. Original captures and texture provenance are retained in
`games/no-mans-sky/investigation-state/runs/20261008T-grass-iomi/`.

Sybarryil is the dark-green visual control. Its selected rocky object table uses cross grass, with
main tint `(0.261, 0.283, 0.163)` and Vibrant grading (42). Texture-only replay classified all nine
material representatives as Black: estimated Oklab lightness 0.203–0.325 and relative chroma
0.014–0.092. The graded main tint instead has lightness 0.414 and relative chroma 0.117, retaining
the green appearance observed by the user. The revised production classifier and compiled predicates
return Green for every material and reject Grey, Black and White. Passive capture is retained in
`games/no-mans-sky/investigation-state/runs/20261008T-grass-sybarryil/`; before/after replay,
six-reference predicate outcomes and workspace checks are retained in
`games/no-mans-sky/investigation-state/runs/20261008T-grass-calibration/`.

Ohnniat XVII is the muted olive false-positive control. The user's search selected Black, Grey and
White with floating islands, and its matching result address equals the live player address. Passive
shader-uniform reads confirm the captured main tint `(0.267, 0.282, 0.192)`; both grass tints are
equal. Its selected Swamp islands table contains active NEWCROSSGRASS. Source relative chroma is
0.095; BarrenDefault grading gives 0.094, while texture representatives fall to 0.053–0.087. The
prior 0.10 rule called every material Black. The source/graded colour-preservation gate now rejects
all three neutral predicates for every material, including source-brightness variations from 0.8 to
1.2. Its graded tint has hue about 52 degrees, falling in the former Yellow bin. The same LUT maps
an equal-lightness grey to `(0.359, 0.322, 0.299)`. Accounting for this mild warm cast yields
`(0.330, 0.353, 0.263)`, hue about 75 degrees. The revised classifier returns Green across all nine
materials and source-brightness variations from 0.8 to 1.2. Seven-world replay preserves the other
six reference outcomes. Hue adaptation replay and warm/cool/strong-effect controls are retained in
`games/no-mans-sky/investigation-state/runs/20261008T-grass-hue-adaptation/`. Capture, exact table
roundtrip, loaded shader/material reads, before/after predicates and broader synthetic controls are
retained in `games/no-mans-sky/investigation-state/runs/20261008T-grass-green-neutral-regression/`.

The runtime reads current game LUTs from the exact-build HGPAK archive rather than shipping game
assets. Its bounded compressed/raw chunk reader and DDS decoder reproduce all texel values of all 85
native SDR filter mappings against independently extracted LUTs. Archive reads and decoded LUTs are
bounded and cached. Colour classification assumes standard game scenes, materials and textures;
visual changes made by mods can change the apparent colour.

Production capture/classification/predicate functions over the retained reference snapshots return
Green only for Sybarryil, Ohnniat XVII and Olarac Minor, Black only for Ixha Delta and Apaeumasan
Gaha, White only for Antwithe Guro, Magenta only for Ladonnea Delta, and Black/Grey for Iomi 84/C9.
Host controls cover the hue circle over several lightness/texture-brightness levels, minority- patch
rejection, grading changes, missing grass, inactive spawns, and archive/texture validation. They do
not establish general visual accuracy. The candidate assumes neutral daylight and full selected SDR
grading; it does not reproduce scene lighting, exposure/tonemapping, per-pixel texture brightness,
procedural texture recolouring, distance blending, storms or the HDR pipeline. Eight-world replay,
nine Olarac source-brightness variations, all 85 LUT acquisitions and actual monochrome negative
controls are retained in `games/no-mans-sky/investigation-state/runs/20261009T-grass-olarac/`. Those
effects can change borderline classifications. Modified blend rules or grass placement can also
alter which tint dominates visually. Additional independent visual controls remain necessary before
broader appearance claims.

Apaeumasan Gaha supplies a dark barren-grass control. Its main terrain RGB is
`(0.384, 0.333, 0.267)`; unmodulated BarrenDefault grading produces `(0.485, 0.398, 0.299)`. The
current material correction classifies it as Black and preserves the captured Ixha, Antwithe and
Ladonnea classifications. Its selected large barren grass uses clump placements, so a grass-colour
match does not guarantee continuous grass cover. Native query generation fills terrain colours
through the tile selector's tail jump to the colour writer and a subsequent palette lookup; these
fields are not uninitialized. Passive resource reads reproduce all twelve loaded tile bindings,
including both grass shader tints. These comparisons are retained in
`games/no-mans-sky/investigation-state/runs/20261008T134000Z-grass-presence/`.

The material-brightness correction, Grey category and complete native LUT mapping are installed and
hash-verified in Amethyst and the linked game files. The material correction has production-function
replay coverage; a fresh native search with this build remains pending. The following live searches
qualified the preceding primary-tint/native-LUT build. Fresh native black-grass searches with
unrestricted world filtering return the same 100 results with two and sixteen workers. A
Lush/corrupted-Sentinel control acquires grass appearance across 1,000 systems, returns 28 matches,
and reproduces those matches from cache without generation. The formerly omitted filter is therefore
exercised through the actual LUT acquisition path. Generator bytes, the filename map and table
resource/reference inventories remain unchanged. User settings and presets are restored exactly;
saves are not replaced. These checks establish successful acquisition and filtering, not broader
visual accuracy. The loaded system is intentionally excluded from displayed search results, so its
classification is verified through acquired facts rather than expecting it in the result list.
Earlier native acquisition/cache/cancellation evidence remains in the raw run.

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
