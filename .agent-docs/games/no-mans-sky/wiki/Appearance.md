# Appearance and vegetation

## Colour grading

Biome membership does not determine grading. Red/Green/Blue mega-exotic families share HugePlant,
HugeLush, HugeRing, HugeRock, HugeScorch and HugeToxic variants permitting Default and Weird
filters. Ordinary Lush and Frozen definitions can also select Weird filters. The selected
`GcPlanetData.Weather.ScreenFilter` is the grading authority; weather type is separate.

Weird1–Weird8 have native values 12–19. The filter enum includes selections absent from ordinary
biome weights, including a corrupted-Sentinel override. Rendering blends base, distance, storm and
effect LUTs. An assigned filter does not guarantee constant full-strength grading in every view.

SDR LUTs use 16- or 32-cubed BGRA8 textures. HDR LUTs use 33-cubed R10G10B10A2 data with a separate
log encoding. An SDR estimate is not an HDR simulation.

Cloud, sky, horizon, fog and water have separate colour anchors. Sunset, lighting, reflection,
exposure, weather and viewpoint alter rendered appearance. Grass does not establish flora colour.

## Grass

NEWCROSSGRASS and NEWLUSHGRASS use ground-matching materials. `_F56_MATCH_GROUND` binds terrain
colours, not necessarily Grass palette hue. Render setup binds tile slots 1 and 3 to
`gTerrainColour1Vec4` and `gTerrainColour2Vec4`. The resource creator's Main/Patch ground-colour
selection is separate from these live uniforms.

Grass mixes tints using a two-octave Perlin blend biased toward the main tint. Minor secondary
patches need not represent the dominant appearance. Near-camera brightness includes
`min(2 * max(diffuse.rgb), 1)`; transparent padding contributes no visible grass. Texture darkening
fades between 24 and 56 metres. Selected material variants can have different brightness.

Presence requires active ground-grass spawns with positive coverage/density. Decorations, flowers
and mushrooms do not establish grass cover; clump placement does not guarantee continuous cover.

## Flora materials

Discoverable flora identity comes from attachments. Bark, stems, leaves and flowers can use separate
palettes, alternatives, fixed textures and uniforms. Procedural options can depend across materials
through `SelectToMatchBase`; alternatives are not necessarily independent.

Procedural average colour is packed AARRGGBB in the relevant DDS reserved word. Shader recolouring
preserves shading through HSV operations. Layers compose in reverse descriptor order and retain the
first present layer's alpha. Primary/secondary diffuse textures use their own UVs; secondary alpha
blends linear RGB. Vertex colours, opacity and cutout affect visible contributions.

## Emission and bubbles

Emission requires the shader flag and positive strength; masked emission also needs nonzero blue
mask data. Bright palettes and “glow” filenames do not establish emitted light. Bubble-lush grass
emission varies with night and a time/position wave. Airborne bubbles are a separate effect.

`Weather.HeavyAir.Filename` can select `MODELS/EFFECTS/HEAVYAIR/BUBBLE/BUBBLE.SCENE.MBIN`, with
ordinary/storm emitters. Object tables can separately select bubble effects. Neither is equivalent
to the Bubble subtype or glowing grass.
