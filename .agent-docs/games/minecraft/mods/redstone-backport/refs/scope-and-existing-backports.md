# Redstone Backport: scope, usefulness, and existing implementations

Research checked **2026-10-27**. This is a source/archive investigation, not a gameplay or
compatibility qualification. No mod implementation or public feature claims were changed by this
initial investigation.

**Decision status:** the user subsequently selected a standalone, all-in-one product. The earlier
narrow-companion recommendations below are research opinions, not approved requirements; the
[active implementation contract](../implementation-contract.md) supersedes them. Keep the source and
licensing observations as evidence rather than treating their scope recommendation as policy.

## Bottom line

**A small, rigorously tested redstone/automation parity backport still has a useful niche. Another
large collection of copper blocks and modern mobs is substantially redundant.**

The strongest remaining case is a dependable 1.20.1 Crafter, vanilla-style tick debugging across
loaders, and selected automation fixes that content backports do not cover. Existing implementation
quality must be addressed before treating parity as the project's differentiator. In a pack that
already has modern-content backports and Carpet, the incremental benefit is considerably smaller.

The [update inventory](vanilla-redstone-update-inventory.md) records the newer vanilla
opportunities. [Active task evidence][evidence] includes official release notes, API responses,
pinned source-file identities, official vanilla data, bytecode observations, and inspected published
artifact identities.

## 1. What this project is trying to accomplish

The mod's `docs/index.md` describes bringing **select redstone-related gameplay and tools from newer
Java releases onto older Minecraft**, with matching behavior where practical. Its eventual version
span reaches back to 1.16.5; that is an aspiration, not the current distribution matrix.

Current source and `.squinch/games/minecraft/mods/redstone-backport/config.yml` establish:

- **Actual target:** Minecraft 1.20.1, Java 17, Fabric / Quilt / Forge. No current NeoForge target.
- **Actual feature surface:** a registered `redstone_backport:crafter`, `/tick` with server/client
  state synchronization, and modifications to witch redstone drops.
- **Not currently implemented:** copper bulbs, shelves, statues, decorated-pot storage, wind
  charges, creaking hearts, or the rest of the public roadmap.
- **No alternative dust engine:** this is not a redstone-performance rewrite, a Bedrock-redstone
  emulator, or a general technology mod. Adding arbitrary machines would change its purpose.

The sensible scope boundary is **automation semantics**, not “anything mentioning redstone.” That
includes comparator inputs, hopper/dropper/dispenser interactions, observer-relevant state changes,
sculk events, note-block instruments, farm-relevant ticking, and debugging tools. It does not
require owning every biome, wood set, or mob that participates in one of those interactions.

### Current implementation does not yet justify full parity claims

The following findings come from the checked-out source, not inferred runtime failures. Paths below
are relative to `games/minecraft/mods/redstone-backport/`; exact file identities and source
permalinks are in `source-review.json` under [evidence][evidence]. Vanilla's official [1.21 release
notes][v121] explicitly specify Crafter comparator, insertion, extraction, and output behavior.

| Finding                                                         | Source evidence                                                                                                                                                            | Consequence                                                                                                                                                                                         |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Crafter comparator support is absent.**                       | `common/.../block/CrafterBlock.java` has neither `hasAnalogOutputSignal` nor `getAnalogOutputSignal`; no companion mixin supplies them.                                    | Documentation says the Crafter has 0–9 comparator behavior, but the block does not implement that contract.                                                                                         |
| **Automated extraction is explicitly disabled.**                | `common/.../blockentity/CrafterBlockEntity.java:canTakeItemThroughFace` always returns false; Forge's `CrafterForgeItemHandler.extractItem` returns `ItemStack.EMPTY`.     | Vanilla 1.21 explicitly permits hoppers and hopper minecarts to extract Crafter ingredients.                                                                                                        |
| **Loader insertion semantics diverge.**                         | Common sided insertion accepts any enabled slot. The round-robin `findNextInsertSlot` helper is used by Forge's item handler, not Fabric/Quilt's ordinary container path.  | There is no single cross-loader implementation of vanilla's first-empty / least-filled distribution rule. Forge round-robin is not that rule either.                                                |
| **Crafting and animation share the same scheduled block tick.** | `CrafterBlock.neighborChanged` schedules after 1 tick. `tick` clears `CRAFTING` and returns when it is set; successful crafting schedules another tick to clear animation. | Timing and repeated-pulse behavior need an exact vanilla comparison. A pulse arriving during animation can take the clear-and-return path instead of a craft path; runtime ordering is unqualified. |
| **Output/remainder behavior differs.**                          | `CrafterBlockEntity.tryCraftAndEject` places crafting remainders back into emptied input slots before outputting leftovers.                                                | Vanilla describes ejecting the recipe's result and remaining items through the front. Bucket recipes and chained Crafters need dedicated tests.                                                     |
| **Witch loot differs by loader and from vanilla.**              | Fabric/Quilt append a guaranteed pool without removing redstone from the original random pool. Forge removes existing redstone stacks and adds `4 + nextInt(5) + looting`. | Fabric/Quilt can retain extra old random redstone drops and the old random-pool distribution. Both implementations use a deterministic Looting bonus rather than vanilla's uniform random increase. |

The witch comparison is backed by **data extracted from Mojang's official 1.21 client archive**, not
just a wiki: redstone was removed from the old random-choice pool and put in a separate guaranteed
4–8 pool; its Looting increase uses a uniform 0–1 number provider, not a constant 1. The retained
`official-data-1.21-witch.json` is the exact extracted table.

`/tick` is more substantial than a cosmetic command: it has managers, world/entity/chunk tick gates,
sprint scheduling, and loader-native networking. It is nevertheless **not runtime-qualified by this
survey**. Broad `@Redirect`s in `ServerLevelMixin` and the server-loop `@ModifyConstant` deserve
particular compatibility attention with Carpet and tick/performance mods.

The repository's current `crafter-basic` check places a block and reads its block-entity ID; it does
not prove crafting, comparators, IO, or parity. `tick-freeze` checks command responses rather than
observing all frozen systems. Do not equate those checks with the stronger claims above.

## 2. Copper Age Backport: which project and where is the source?

There are **two different Modrinth projects with this title**.

### The relevant maintained project: Smallinger

- [Modrinth: `backport-copper-age`](https://modrinth.com/mod/backport-copper-age).
- [Public source](https://github.com/Smallinger/Copper-Age-Backport).
- [**1.20.1 branch**](https://github.com/Smallinger/Copper-Age-Backport/tree/1.20.1). The default
  `main` branch targets **1.21.1**, so comparing only the default branch would miss 1.20.1-specific
  features.
- Published **1.20.1 Fabric and Forge** artifacts were confirmed in Modrinth's version API. The
  inspected Fabric build is `1.20.1-0.1.5.1-pre` (a beta).

Source inspection of its **1.20.1 branch** confirms:

- `CopperBulbBlock`: rising-edge T-flip-flop, lit comparator output 15 / unlit 0, and non-conducting
  block behavior.
- `CopperGolemStatueBlock`: pose-based comparator output **1–4**.
- `block/shelf/ShelfBlock`: powered connected-shelf hotbar swaps and comparator occupancy bitmask
  **0–7**. `ShelfBlockEntity` implements sided container IO.
- Copper chests and copper-golem sorting, oxidation/waxing, and the 1.21 copper
  doors/trapdoors/bulbs.

These are not merely project-page promises: a hash-verified **published 1.20.1 Fabric JAR** contains
those bulb, statue, and shelf implementation classes. Class presence establishes shipping scope, not
behavioral correctness or compatibility with this mod.

**Important qualifications:** it also includes non-vanilla **copper buttons** and button-pressing
behavior, so it is not a pure stable-vanilla parity package. Its source-root `LICENSE` is **CC0**,
whereas Modrinth and `gradle.properties` label it **MIT**. Resolve that discrepancy before copying
code; public visibility is not a substitute for checking the applicable license and asset rights.

### The similarly named discontinued project

[Modrinth: `copper-age-backport`](https://modrinth.com/mod/copper-age-backport) targets Fabric/Quilt
1.21/1.21.1, has no source URL in its project metadata, is marked all-rights-reserved, and
explicitly recommends migrating to Smallinger's mod. It is not the relevant 1.20.1 implementation to
build upon.

## 3. Other backports and overlaps

Loader claims below use **actual version records for 1.20.1**, not the project-wide union of loaders
and Minecraft versions. A project supporting NeoForge somewhere does not establish NeoForge 1.20.1
support, and an older Quilt-tagged version does not establish current Quilt support.

| Project                      | Relevant 1.20.1 availability          | What is actually relevant                                                                                                                                                                            | Limitations / source                                                                                                                                                                                                                                                                                   |
| ---------------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Vanilla Backport**         | Current 1.2.2 Fabric / Forge releases | Copper bulbs, shelves, statue outputs, copper golems/chests, creaking-heart comparator, decorated-pot storage/comparator, Ender Pearl chunk-ticket/persistence work, sulfur cubes and potent sulfur. | [Source, 1.20.1](https://github.com/ItsBlackGear/VanillaBackport/tree/1.20.1). Large content mod, not only automation. Source and released archive inspected.                                                                                                                                          |
| **Tricky Trials Backport**   | Fabric / Forge                        | Has a Crafter implementation and wind charges, plus Trial Chamber content.                                                                                                                           | [Source](https://github.com/DRD2k8/TrickyTrialsBackport), **archived**. Requires Copper Age Backport, Trimmed, Sherds API; broad dependency/content footprint. Its Crafter `use()` calls `tryCraft()` on opening, so do not assume perfect pulse-only parity merely because it has comparator methods. |
| **Copper and Tuff Backport** | Fabric                                | Has a source-visible bulb implementation; alternatives for the copper/tuff block family.                                                                                                             | [Source](https://github.com/AlternateEarth/copperandtuffbackport), MIT. Focus differs from a technical parity layer; extra behavior includes copper beacon bases.                                                                                                                                      |
| **Pale Garden Backport**     | Fabric / Forge                        | Creaking-heart distance comparator and Pale Oak set.                                                                                                                                                 | [Source](https://github.com/danbrown/palegardenbackport). Heart comparator inspected; brings biome/entities and dependencies, not just a sensor.                                                                                                                                                       |
| **Carpet**                   | Fabric, release 1.4.112               | `/tick rate`, freeze, step, warp, plus mature technical-testing tools.                                                                                                                               | [Source](https://github.com/gnembon/fabric-carpet/tree/1.4.112), MIT. Strong overlap with tick-debugging intent, but **not identical vanilla command syntax** (`warp` vs `sprint`, etc.) and not the same loader matrix.                                                                               |
| **Autocrafter Early**        | Fabric                                | Narrow Crafter alternative.                                                                                                                                                                          | [Project](https://modrinth.com/mod/autocrafter-early). API has no source URL; description explicitly excludes a tick-cooldown change. Not verified as stable-1.21 parity.                                                                                                                              |
| **Tick Changer**             | Forge, alpha                          | Standalone `/tick` recreation.                                                                                                                                                                       | [Project](https://modrinth.com/mod/tick-changer). No source URL in metadata; author explicitly says its logic is not an exact copy.                                                                                                                                                                    |
| **Backported Minecarts**     | Fabric                                | Selected 1.21.2 experimental cart behavior.                                                                                                                                                          | [Project](https://modrinth.com/mod/backported-minecarts). Project-wide Forge/NeoForge labels do not apply to the inspected 1.20.1 release; author warns about that distinction. No source URL; not proof of the whole experiment.                                                                      |

### Vanilla Backport is a particularly important overlap

The **current** 1.20.1 source is substantially more capable than its older “Bundle o' Life”
changelog file suggests. The Modrinth project now describes an “Age of Mayhem” code rework. Its
hash-verified 1.2.2 Fabric archive contains shelves, bulbs, creaking hearts, decorated-pot mixins,
sulfur cubes, potent sulfur, and Ender Pearl persistence mixins. Therefore an older recollection of
its scope is not a safe basis for claiming Redstone Backport is needed.

Source inspection found **no Crafter or vanilla `/tick` implementation** in its current
common/Fabric/Forge source tree or those named classes in the inspected archive. That leaves a
credible focused gap. This is not a claim that every other mod lacks these features, nor that all
other automation gaps have been exhaustively audited.

Its **October 2026 Vanilla Backport License** permits use as an official soft/hard dependency and
unmodified official releases in modpacks, but prohibits publicly publishing copied/modified versions
and unofficial redistribution. **Do not transplant its source into a public Redstone Backport
release without separate permission.** Interoperate with its official release instead.

## 4. Is Redstone Backport actually useful?

### Yes, if it becomes a focused technical layer

A useful product promise would be:

> Bring selected stable-vanilla automation semantics and debugging tools to 1.20.1, with known
> per-feature behavior, minimal content baggage, and tested companion compatibility.

Its advantages could be:

1. A small installation for players wanting a **proper vanilla Crafter** without Trial Chambers,
   mobs, world generation, or several content-mod dependencies.
2. Vanilla-style `/tick` on **Forge as well as Fabric/Quilt**, with actual freeze/step/sprint
   evidence, rather than declaring either Carpet or a command lookalike identical.
3. Selected **existing-block fixes**: comparator notification, dispenser actions, vibration
   emission, and hopper behavior can matter even where no new content is needed.
4. Deliberate interoperability: allow a content backport to own shelves/pots/copper while this mod
   owns only the missing technical behavior.

### No compelling case for the undifferentiated roadmap

Reimplementing every copper block, shelf, statue, creaking heart, and sulfur mob independently would
multiply registration, asset, save-format, loader, and compatibility work already undertaken by
other mods. “It contains modern redstone things” is no longer a strong differentiator. For players
already using Vanilla Backport plus Carpet or another Crafter mod, much of that benefit disappears.

**Do not retire the project solely because Copper Age Backport exists.** It does not replace the
current Crafter or `/tick` surface. Equally, do not keep expanding it solely because the public
matrix has unchecked rows. First establish that a missing behavior is useful, absent from the chosen
companion set, and feasible to maintain correctly.

## 5. Recommended direction, not an approved implementation plan

1. **Repair/qualify the existing surface before adding blocks.** Crafter comparator 0–9, insertion
   balance, hopper/dropper/minecart IO including extraction, pulse scheduling, remainders, block
   removal/reload, and all claimed loaders. Match witch pool replacement and Looting distribution.
2. **Separate feature ownership.** Choose standalone vs companion-aware behavior per feature before
   registration. Do not register two competing `minecraft:shelf` implementations or add an
   indistinguishable second shelf under another namespace by accident.
3. **Prefer content companions for content.** In particular, do not duplicate Vanilla Backport's
   pots/hearts/copper/sulfur or Smallinger's copper family unless a concrete requirement rules them
   out. Config entries that prevent obtaining a block are not automatically proof it is
   unregistered.
4. **Target small real gaps.** Audit the 26.1 trumpet instrument, eligible vanilla comparator/sculk
   fixes, and dispenser actions against the actual chosen pack. Their apparent absence is a
   candidate for verification, not an ecosystem-wide uniqueness claim.
5. **Keep invasive mechanics separate and opt-in.** Random-tick reach, Ender Pearl loading, spawn
   chunk changes, and experimental wire/minecarts can alter or break existing farms. They should not
   arrive as silent “more parity” changes to every world.
6. **Keep snapshots on a watchlist.** 26.4 jukebox playlists are interesting but not yet a stable
   default target. Recheck final release behavior before implementing a backport contract.

For each accepted feature, record a vanilla reference version, loader coverage, owner when a
companion exists, intentional deviations, and deterministic acceptance cases. For `/tick`, include
real scheduled ticks, random ticks, entities, block entities, players/passengers, joins, and
integrated client behavior—not only translated command messages.

## Evidence boundaries

- Official version manifest and release notes establish release status and documented vanilla
  behavior. Bytecode/data from official, SHA-verified archives resolve selected precise questions.
- Public source inspection establishes implementation decisions; published-JAR class inspection
  establishes selected shipped scope. Neither establishes real runtime parity.
- This survey did **not** build the mod, start Minecraft, test a modpack, or prove save migration.
- Source branches can advance independently of published releases. Exact inspected commits and
  artifact hashes are retained in the focused evidence, not inferred from version names.
- The public mod docs and website remain unchanged; their stronger current parity claims should be
  corrected or backed by runtime evidence in a separately authorized implementation task.

[evidence]:
  ../../../../../../.squinch/scratch/tranches/redstone-backport-release/inputs/research/research/2026-10-27/README.md
[v121]: https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21
