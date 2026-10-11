# Search Probes vegetation emission

## User contract

Glowing grass and Glowing flora are independent Any / Require / Exclude planet controls in Biome &
Environment. They detect emitted light, rather than a bright palette, daytime colour, or a filename
containing “glow”. Grass means primary ground-cover grass; flora means other surface plants
registered by the game as discoverable Flora. Cave and underwater vegetation, resource plants,
mineral props, building decorations and atmospheric effects are outside this scope. The controls do
not select an emission colour. Emission can pulse and may be visible mainly at night.

## Current implementation

The exact supported game build is recorded in the product README. Native planet generation supplies
the selected object tables. Only spawnable surface records qualify: a quality variant needs positive
coverage and a positive native maximum density. The existing ground-cover scene identities separate
grass from other plants. Scene references and entity attachments establish the latter’s Flora
identity; an absent entity provides no discovery identity. Required scenes, materials and emission
textures must load and pass bounded format checks. Visual filters interpret the standard game
assets; mods that change scenes, materials or textures can change the rendered appearance without
changing the search classification.

The material needs the shader’s emission bit and positive emission strength. Materials using a mask
also need nonzero blue-channel emission data. The captured bubble-lush grass shader scales emission
by night and a time/world-position wave. Its meshes directly reference BubbleGrassGlowMAT; the
material is unrelated to airborne bubbles. This is asset-based emission detection, not a simulation
of every scene’s lighting, visual coverage, or procedural choice of individual flora instances.

Object summaries retain explicit acquisition bits. A cached table acquired for another criterion
cannot imply that vegetation does not glow. Requesting a new glow property upgrades the summary;
known positives short-circuit further asset reads for that property. Any requests no glow scan,
colour capture or emission texture decoding. Ordinary metadata predicates still run first.

## Evidence and qualification

Read-only loaded-world captures and the production asset parser agree with operator observations:
Dorent Mito and Exleywoo Major select glowing grass and glowing mushrooms, while Tapons selects
glowing grass and ordinary non-glowing flora. Ordinary cross-grass and non-emissive trees provide
negative controls. Current spawnable surface-table scans resolve both properties without errors. The
production workspace checks independent predicates, unknown cache values, incremental table
acquisition and malformed asset rejection. A fresh native search with Black grass, Require glowing
grass and Exclude glowing flora completes and returns Olarac Minor using 16 workers and cold table
loads. The operator confirms that the game remains responsive. This qualifies the reported crash
combination, not every glow combination or every rendered appearance.

Raw captures, current-asset semantic round trips, shader extraction, parser outputs and the
repeatable surface-table check are retained under the ignored
`games/no-mans-sky/investigation-state/runs/20261008T-bioluminescence/` directory. Windows
asset-path comparisons and fresh native acceptance are retained in the sibling
`20261009T-glow-search-crash/` directory.

## Floating bubbles

Tapons independently selects `MODELS/EFFECTS/HEAVYAIR/BUBBLE/BUBBLE.SCENE.MBIN` in
`GcPlanetData.Weather.HeavyAir.Filename`. That scene references normal and storm heavy-air emitters.
Current untouched metadata round trips confirm particle budgets of 2,000 and 4,000 respectively,
with larger storm particles. These budgets support the operator’s denser-storm observation; they are
not a measured count of visible bubbles. Object tables also contain a distinct airborne-bubble
particle scene. A future Floating bubbles control should check the atmospheric and object sources
separately from grass, flora and the Bubble biome subtype. No bubble filter is implemented here.
