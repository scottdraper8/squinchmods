# Source, asset, and distribution boundaries

## Existing project license

Preserve **CC-BY-NC-ND-4.0**, the explicit Redstone Backport choice in `docs/developer/license.md`,
`docs/developer/index.md`, and Fabric metadata. Reconcile other loader metadata with that
declaration; do not invent an MIT/CC0 relicense. This mod-specific declaration is separate from the
parent repository's license. Project licensing does not grant rights over external code, assets,
dependencies, or third-party contributions.

## Official Minecraft material

The [Minecraft EULA](https://www.minecraft.net/en-us/eula) distinguishes original mods from modded
game distributions. Its "Using mods" section permits original mods that do not contain a substantial
part of Minecraft's copyrightable code/content; its distribution section does not grant general
permission to distribute game software or content. The
[usage guidelines](https://www.minecraft.net/en-us/usage-guidelines), especially "Essential
guidelines" and "Extended functionality and modifications", likewise distinguish a mod from a
redistributed game or game files. Public download access and an artifact hash are not a license.

Engineering policy:

- Independently implement behavior from reviewed official contracts. Do not ship decompiled
  Minecraft sources/classes, a modified game, or copied restricted competitor implementation.
- Do not bundle official textures, models, audio/music, structures, or other copied game content
  without an established permission for that distribution. A mod-wide project license must not
  purport to relicense them.
- Keep private development inputs in the legitimate shared source/download cache. Retain compact
  input identities required for reproducible tooling, not a checked-in archive of game content.
- Use original or independently licensed project branding. Do not assume a game texture is permitted
  as the mod's logo merely because it depicts the feature being backported.

This is a conservative implementation/distribution boundary, not a legal opinion or an assertion
that a particular exception or external permission exists.

## Selected resource architecture and unresolved use decision

The controller selects **payload-free publication plus explicit user-supplied local assembly**:
independently authored code and necessary factual identities are distributed, not official or
unproven textures, audio, models, structures or adapted payloads. Future binary **and source**
deliveries must remove/exclude unproven bundled content; renaming, recoloring, or excluding only
from a JAR is insufficient. Optional original branding is assessed separately. Existing public
history, if any, is an owner matter, not authorization for an agent to rewrite it.

This architecture selection is **not permission to execute or publish every local adaptation**. The
specific licensed-input selection/transformation scenario remains subject to an evidence-backed
rights-owner determination. Minecraft's express local Java modding permission must be considered
alongside the incorporated Microsoft Services Agreement's software/Digital Goods terms and the
applicable input/audio rights. Neither a hash nor a user-consent checkbox supplies an external
license. Do not clear an unresolved intended use or the release rights gate on this design alone.
Original-code development and legitimate private semantic review can continue meanwhile.

## Locally supplied game resources

Implement a transparent local acquisition/assembly path rather than omitting content, shipping
placeholders, or copying a competitor's resources. Such a path must:

1. Consume explicitly selected, legitimately acquired local archives and the required asset
   index/objects. Do not silently crawl account/launcher state, request credentials or receipts,
   mirror game archives, bypass access controls/licensing, pre-accept game EULAs, or hide their
   presentation. Automatic official-endpoint acquisition is a separately reviewed optional mode, not
   a requirement of the selected minimum architecture.
2. Pin official version/asset metadata, validate archive/object hashes and sizes, validate safe
   entry paths, and select only the required owned-family resources. Do not mount an entire later
   vanilla resource/data pack over the older game indiscriminately.
3. Document first-use input/storage requirements and provide a verified offline-cache path.
   Missing/corrupted inputs must produce actionable diagnostics before world mutation, not silently
   disable stable features or substitute an unrelated asset. Use atomic publication and owned locks.
4. Keep acquired game resources out of published mod artifacts and release uploads. Provenance
   records describe ownership and acquisition; they are not redistribution grants.
5. Preserve canonical `minecraft:` resource identities and paths. Mount target-adapted resources
   through the family ownership/resource composition system, below user resource/data-pack overrides
   and without enabling another provider's duplicate contributions.
6. Translate only formats that the target actually needs. Validate semantic/data dependencies,
   textures/model layouts, sound references, structure contents, and resource reload behavior.
   Resolve user-pack priority before deriving adapted resources so a higher-priority canonical input
   overrides its cached converted result. Define precedence against target-native equivalent paths.
   Identify code-defined expressive geometry/animation explicitly; embedding copied tables in a Java
   generator is not a payload-free workaround.
7. Qualify the exact production artifact with complete local resources, positive/negative
   acquisition controls, offline reuse, save/reload, client rendering/audio where relevant, and
   distinguishable resource-pack overrides. Dependency acquisition is not runtime feature
   qualification.

No content-companion dependency is introduced by this design: standalone means the mod supplies all
required behavior and can assemble its own legitimate inputs. Do not claim it is fully
self-contained or network-free unless that is actually implemented and tested.

## Third-party boundaries

Do not reuse Vanilla Backport's restricted source/assets. Do not reuse Copper Age Backport material
while the applicable conflicting license declarations remain unresolved. Exact published binaries
may be separate, explicitly acquired coexistence-test inputs; their presence does not authorize
source reuse, redistribution, or a parity claim. Preserve notices and qualify permitted dependencies
and runtime providers independently.
