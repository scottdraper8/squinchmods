# Minecraft Resource Pack Ideas

## Compatibility Packs

- Compatibility packs for all official Fusion resource packs and Excalibur. See the
  [Fusion mod page](https://modrinth.com/mod/fusion-connected-textures) for more information.
- Compatibility packs for all packs in the Connected series by
  [Jacosvaldo](https://modrinth.com/user/Jacosvaldo)

## Compatibility Goals

The compatibility target is not just "make Fusion load with Excalibur." The goal is to preserve
Excalibur's visual identity while selectively adding Fusion-driven behavior such as:

- connected textures
- transition overlays
- emissive overlays
- item model changes

In practice, this means separating packs into three categories:

1. Overlay packs that can often coexist with Excalibur with minor or no art changes.
2. Override packs that replace the visible texture or model for vanilla assets and therefore
   overwrite Excalibur's appearance unless custom compatibility work is done.
3. Packs that rely on bespoke connected-texture atlases and therefore require Excalibur-specific
   texture sheets, not just JSON or model wiring.

## Official Fusion Packs

### Mostly Compatible with Excalibur

These are the easiest targets because they primarily add overlays or model modifiers instead of
fully replacing a block's base appearance:

- `Fusion Block Transitions`
- `Fusion Emissive Ores`

For these packs, compatibility work is mostly about style matching:

- verify that the overlay colors, brightness, and noise read correctly on top of Excalibur's base
  textures
- adjust overlay textures if Excalibur's palette or contrast makes the stock Fusion overlay feel out
  of place
- check edge blending for grass, podzol, sand, nylium, and similar blocks
- confirm ore overlays align cleanly with Excalibur ore silhouettes

These packs are good candidates for a first compatibility project because they are more likely to
require texture polish than full texture replacement.

### Likely to Overwrite Excalibur Assets

These official packs override `minecraft` block models or blockstates and redirect them to Fusion
pack textures, which means they do not preserve Excalibur's look out of the box:

- `Fusion Connected Glass`
- `Fusion Connected Blocks`

Examples of what this means in practice:

- `Fusion Connected Glass` overrides `minecraft` glass models and pane blockstates, then points them
  at `fusion_connected_glass` textures.
- `Fusion Connected Blocks` overrides selected `minecraft` models and blockstates for blocks like
  bookshelves, sandstone, quartz, copper blocks, and other supported blocks, then points them at
  `fusion_connected_blocks` textures.

This means load order alone is not enough if the goal is to:

- keep Excalibur's texture art
- gain the Fusion connected behavior

To make these packs truly compatible with Excalibur, a compatibility pack would need to:

- preserve or recreate the model and blockstate logic that enables the Fusion behavior
- replace the Fusion pack's visible textures with Excalibur-matched equivalents
- verify that any special cases such as pane edges, bookshelf shelves, or block side and top splits
  still read correctly in Excalibur's style

### Likely to Overwrite Excalibur Item Presentation

These official packs target vanilla items directly through Fusion item model modifiers:

- `Fusion Stacking Items`
- `Fusion 3D Items`

They are not inherently incompatible with Excalibur, but they do change the appearance of targeted
items such as:

- sticks
- candles
- signs
- lanterns
- torches
- campfires
- sea pickles
- chains

Since Excalibur already supplies custom item textures for several of these, these packs should be
treated as override packs if visual consistency matters. Compatibility work here means:

- auditing which targeted items already have custom Excalibur art
- deciding whether Excalibur's 2D item look should be preserved or replaced with a 3D or stacked
  variant
- creating Excalibur-matched item textures or models where the stock Fusion assets clash with the
  Excalibur aesthetic

## Connected Series Packs

The Connected series by Jacosvaldo is a harder compatibility target than the overlay-focused
official Fusion packs.

Relevant packs include:

- `Connected Bricks (Fusion)`
- `Connected Paths (Fusion)`
- `Connected Rocks (Fusion)`

These packs are important because they generally do not just add connection logic on top of the
existing vanilla or Excalibur textures. Instead, they ship their own connected-texture atlases.

For example:

- `Connected Bricks (Fusion)` uses its own connected brick atlas rather than reusing
  `minecraft:block/bricks`.

This creates a different kind of compatibility problem:

- JSON or model compatibility alone is not enough.
- Excalibur-compatible connected atlases must exist for the affected block families.

## What a Real Compatibility Pack Would Require

### For Official Overlay-Oriented Fusion Packs

Usually required:

- resource pack load-order testing
- model and blockstate verification
- overlay texture edits for palette and contrast matching
- targeted bug checking for broken particles, seams, or unexpected lighting

Sometimes required:

- Excalibur-specific overlay redraws
- alternate edge masks if Excalibur's texture shapes differ from vanilla assumptions

### For Official Connected-Appearance Fusion Packs

Usually required:

- custom Excalibur-style visible textures matching the Fusion pack's expected layout
- reuse of Fusion model JSON and blockstate wiring where possible
- testing each targeted block in stairs, slabs, panes, posts, and other shape variants

### For the Connected Series

Usually required:

- extracting the connected atlas from the source pack
- extracting the corresponding Excalibur base texture
- rebuilding the connected atlas in Excalibur's style
- preserving the original Fusion logic while swapping in Excalibur-matched texture sheets

This is texture-editing work, not just configuration work.

## Texture Work Expectations

For the Connected series in particular, compatibility likely requires pixel-art adaptation rather
than brand-new concept art.

Typical workflow:

1. Extract the source connected atlas from the Fusion or Connected pack.
2. Extract the equivalent Excalibur base texture.
3. Use the connected atlas as a layout or template.
4. Rebuild each tile using Excalibur's palette, mortar lines, shading, and material language.
5. Test in-game and clean up seams, corners, and edge transitions.

This means the work is usually:

- not "invent an entirely new texture pack"
- but also not "copy one 16x16 Excalibur texture and call it done"

The more a source pack depends on a custom connected atlas, the more likely it is that hands-on
pixel editing will be required.

## Practical Priorities

If building compatibility packs incrementally, start in this order:

1. `Fusion Emissive Ores`
2. `Fusion Block Transitions`
3. `Fusion Connected Glass`
4. `Fusion Connected Blocks`
5. `Connected Paths (Fusion)`
6. `Connected Rocks (Fusion)`
7. `Connected Bricks (Fusion)`

Rationale:

- overlay packs have the lowest art burden
- connected official packs require more visible asset replacement
- the Connected series is the highest-effort category because it depends on custom connected texture
  atlases

## Compatibility Deliverables

A finished Excalibur compatibility effort should probably ship as multiple small packs rather than a
single giant pack:

- `Excalibur | Fusion Emissive Ores Compat`
- `Excalibur | Fusion Block Transitions Compat`
- `Excalibur | Fusion Connected Glass Compat`
- `Excalibur | Fusion Connected Blocks Compat`
- `Excalibur | Connected Series: Paths Compat`
- `Excalibur | Connected Series: Rocks Compat`
- `Excalibur | Connected Series: Bricks Compat`

That keeps maintenance easier when either Excalibur or the upstream Fusion packs update.
