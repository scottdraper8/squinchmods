# Minecraft Mod Ideas

## Game Mechanics

### Portalate

A configurable portal-behavior and dimensional-access mod for modpack authors, server operators, and
single-player worlds.

Core idea: define rules for how portals behave instead of being limited to each portal mod's default
logic. The mod should support in-game configuration through an admin UI, plus file/datapack-based
configuration for pack distribution.

Intended capabilities:

- Map vanilla Nether portals and End portals to specific destination dimensions.
- Configure rules per source dimension, destination dimension, portal type, or portal block.
- Disable specific portal types entirely, including vanilla Nether portals, vanilla End portals, End
  gateways, and supported modded portals such as The Aether's portal.
- Allow or deny portal activation, portal entry, and portal return behavior separately.
- Support progression gates such as required advancements, items, game stages, permissions,
  commands, or world state flags.
- Provide clear client-side feedback when a portal is disabled or locked.
- Include an in-game admin UI for viewing, editing, importing, exporting, and testing portal rules.
- Support server-side enforcement so clients cannot bypass restrictions.

Prior-art / reference mods:

- [Dimension Portal Linker](https://github.com/Encrypted-Thoughts/DimensionPortalLinker): Fabric mod
  that configures how Nether and End portals behave in custom dimensions. It is closer to
  Portalate's rule-based model because it maps portal destinations and enable/disable states by
  dimension, rather than adding new player-built portal types.
- [Dimension Link](https://modrinth.com/mod/dimensionlink): Mod for creating linked dimension sets,
  such as giving a custom overworld its own Nether and End equivalents. Useful reference for
  world-set-style behavior, but less directly aligned with Portalate if the goal is arbitrary portal
  rules, per-portal controls, and modded portal disabling.

## Compatibility Mods

### CTS Compats

- [CTS Compats](https://www.curseforge.com/minecraft/mc-mods/cts-compats): seems to be dead, so make
  my own or make a PR. Add compatibility with [KleeSlabs](https://modrinth.com/mod/kleeslabs).

## Optimization Mods

### StructureSpy

- Improve structure & poi search, similar to [BiomeSpy](https://modrinth.com/mod/biomespy). Make it
  non-blocking.
- Determine if similar mod already exists

## Ports of Existing Mods

- [Medieval Glass](https://www.curseforge.com/minecraft/mc-mods/medievalglass): backport
- [Respackopts](https://modrinth.com/mod/respackopts): port to Forge
- [Slabbed](https://modrinth.com/mod/slabbed): backport and port to Forge
