# Search Probes fauna contract

## Public criteria

Fauna Criteria is a top-level peer of System Criteria and Planet Criteria. It has no overall match
mode. General temporarily holds Quantity, Player-attacking fauna, Vile Brood, Titan worms and
Sandworms, with its own All/Any mode. Quantity selects generated CreatureLife abundance, rather than
a species count or animals visible on screen. Current referenced role tables use Dead, Medium and
Full; the public choices omit Low.

Aquatic Fauna, Land Fauna and Airborne Fauna are independent, initially expanded subsections. Each
offers Has <domain> fauna (Any/Require/Exclude), body family, category, activity time, rarity and
discovery height bounds in metres. Land additionally offers Surface and Cave habitat. Choices within
one field are alternatives. In All mode, at least one species must satisfy all active species
criteria: a surface cat plus an unrelated cave rodent cannot satisfy Cats + Cave. In Any mode, a
species meeting any active criterion is sufficient.

Every active subsection must pass, including General, alongside the other active planet and system
sections. Different fauna subsections can match different creatures. General Any cannot bypass
another subsection. Empty subsections impose no requirement or species acquisition. There is no
parent aggregation, parent match-mode preset key or compatibility mapping for the removed mode. A
settled subsection avoids only its own remaining acquisitions.

The presence control is one ordinary criterion inside its subsection. Require establishes that its
domain exists; Exclude establishes that it is absent; Any adds no requirement. In subsection Any
mode, another matching field can satisfy the subsection even when its presence criterion fails. Land
Exclude + Cats accepts a planet with cats in Any mode, and rejects it in All mode. Require in each
of Aquatic, Land and Airborne selects a planet with all three populations. Presence exclusions use
completed observations; unavailable species facts never establish absence.

The four discovery/taming suitability controls have no public model, native query readers, UI,
preset parser or authored mission leaves. Their native mission-placement flags are unsuitable
proxies for actual creature characteristics. There is no compatibility mapping for those keys.

## Owned native observation

On the qualified 7.06 executable, GenerateQueryInfo calls GenerateCreatureRoles before releasing
planet data. The query visitor owns a valid observation window without another generation call.
GcPlanetData stores the array at 0x3180; GcCreatureRoleData has stride 0x5d8, role at 0x57c,
creature ID at 0x5a0, positive finite group density at 0x5c4, tile at 0x5cc and active time at
0x558. Info has gender heights at 0x84/0x88 and discovery rarity at 0x8c. The latter is GcRarity
(Common/Uncommon/Rare), distinct from the catalogue's GcCreatureRarity SuperRare class.

Malformed arrays, unknown IDs, invalid enum values or nonfinite heights fail acquisition; they do
not establish absence. A completed empty array establishes absence. Reads run after cheap query
rejection and before expensive appearance/object work. General boolean criteria retain the short
reader; selected domain criteria copy compact species values into shared owned storage. No native
pointer leaves the visitor. Fact clones share the immutable allocation, and unknown merges cannot
clear acquired species. Species count and total cached species bytes are bounded; byte pressure can
evict records before the system-count limit. Ordinary default searches allocate no species.

Height is the discovery species' generated height for either gender, rounded to centimetres for
comparison. Either gender height within the selected bounds is sufficient. The interval between two
heights is not treated as additional possible heights. These are not measurements of every spawned
individual: actor size/gender can differ, and underwater depth adds another model scale.

## Families, categories and habitat

Current creature data contains 58 ecosystem IDs mapped to 52 grouped body families. Flock and
luminous versions share a family. Catalogue membership establishes potential definitions, not normal
generation reachability of every variant. Presence depends on the generated positive roles.

Body IDs, model descriptors, behaviour types and placement are independent surfaces. RealType and
ForceType are not reliable appearance or habitat classifiers. Airborne families use their current
model/generation routing; an ordinary BIRD role can have TileBase, while PLOUGH can force a flying
engine type without belonging to the flying population. FLOATSPIDER uses ground routing. Underwater
tile takes precedence: crab and hermit-crab families can be aquatic despite Ground MoveArea. Cave
tile identifies underground land species explicitly.

| Category   | Body families                                                                  |
| ---------- | ------------------------------------------------------------------------------ |
| Ordinary   | The conventional natural families, including luminous conventional variants    |
| Robotic    | Robotic antelopes and walking constructs                                       |
| Skeletal   | Skeletal cats and cattle                                                       |
| Plant-like | Plant cats                                                                     |
| Anomalous  | Roller, flyer, digger, plough, drill and the explicit weird/geometric families |

Each domain exposes only its applicable families/categories. Sentinel robots, reward pets, bosses
and space encounters are not natural ecosystem choices. Complete bioluminescence is not implemented:
STRIDERGLOW, MANTAGLOW and SEAHORSEGLOW are explicit luminous definitions, but PURPLE_WEIRD mixes
luminous and other selected descriptors. Neither a GLOW suffix nor the entire broader ID supplies
complete coverage. Selected descriptor/material qualification is required before exposing that
trait.

Aquatic roles do not provide a reliable shallow-only/deep-only habitat classification. Exact current
executable function 0x14124B61C checks underwater placement and actual spawn depth, applies minimum
water depth, and scales underwater actors between the configured depth/scale endpoints. This is
position-dependent, not a Squid-specific deep-only tag. Other physical placement constraints remain
possible; this finding is not proof that every aquatic animal fits a shallow lake. Planet Water can
require deep water independently of an aquatic family. No fabricated species-depth options ship.

## Aggression and worm encounters

Player-attacking fauna checks generated PlayerPredator roles, distinct from ordinary Predator and
FishPredator. Difficulty, feeding and behaviour mods can suppress an individual's attack; the
criterion identifies species that naturally target players. It does not encompass provoked
retaliation or event monsters.

Vile Brood is the independent native UI_BUGS_HINT planetary marker. Titan worms use the selected,
non-superseded external object tables and positive spawn variants for
MODELS/PLANETS/CREATURES/SANDWORMMINI/GROUNDWORMSPAWNER.SCENE.MBIN. The immutable table summary
retains the owned burrow flag. Sandworms read the generated role table's HasSandWorms at planet
0x3198 and validate its accompanying frequency at 0x3194. Current generation function 0x14169F4F0
writes these fields, including the worm-subtype override.

Brood markers, titan burrows and giant travelling sandworms are distinct occurrences. Their
Require/Exclude controls are independent. Excluding naturally player-attacking species does not
silently exclude brood or worm encounters; users can select their independent exclusions.

## Xeno Arena boundary

Xeno Arena will have its own initially collapsed subsection, independently matched alongside Aquatic
Fauna, Land Fauna and Airborne Fauna. Each active subsection requires its own qualifying species;
they need not identify the same animal. A squid requirement and an S-tier Arena requirement can
therefore match different species. Land criteria likewise do not constrain the Arena animal. The
subsection offers Has tameable fauna (Any/Require/Exclude). Within the Arena subsection, All mode
requires one eligible creature meeting all selected Arena criteria; Any mode accepts one eligible
creature meeting any selected Arena criterion. Arena eligibility remains mandatory in either mode.
Coincidental overlap between subsection matches is allowed, but is never required. Empty subsections
impose no requirement.

Current CreatureData supplies CanBeUsedInPetBattler and PetBattlerForcedAffinity. Robot-antelope
forces mechanical affinity; geometric creatures force anomalous affinity. Game-table globals map
other biome families to Tropical, Toxic, Fire, Radioactive, Frost, Desert or Anomalous affinities.
The wild initializer also adjusts certain planet subtypes before resolving biome affinity. Complete
remote affinity and tameability qualification remains pending; no Arena criterion is exposed yet.
Catalogue battle eligibility alone has not been established as the full taming rule.

Battle ranks belong to separate pet-battler initialization. GcGameTablePetData holds PetBattlerSeed,
appearance seeds, scale, stat-class overrides and affinity. The current roll table supplies seeded
classes for health, speed and combat potential. The generated species-role array does not contain
these ranks. The wild initializer and seed helper have now been traced. The seed combines creature
ID, generated role/resource seed, application context seed, engine creature type and adult size
class. The role seed alone is insufficient. The size class is not the role description's size choice
or the discovery page's displayed height.

Passive actor/resource captures supply those inputs for the pictured species. Running the exact
native core-class function in an isolated offline process reproduces D. Rookastium's A combat, B
agility and C health, and B. Articipoe's B combat, C agility and A health. The visor presents the
native output in health/agility/combat order; the hashing tag names do not establish its display
order. This comparison does not call or modify the live game. Remote application-context seed and
adult-size acquisition, the overall Trait Potential grade, and taming eligibility remain
unqualified. No rank-search predicate ships until those inputs and rules are established. It is not
yet established that the player must physically visit a planet.

Hello Games describes wild battle traits in Survey Mode, affinities, size effects, training and
morphogenetic upgrades in the [Xeno Arena update](https://www.nomanssky.com/xeno-arena-update/). The
[recipe site's species catalogue](https://nomansskyrecipes.com/creatures/species/) lists body and
encounter definitions, including reward-only entries, rather than the total procedural species
population. Current game data likewise has 85 definitions, of which 58 are ecosystem entries.

## Evidence and remaining gates

Current identity, round-tripped creature/global/archetype/role assets, supplied Creature Finder and
Worms archive clues, exact executable fragments and passive captures remain in the ignored trees:

- `games/no-mans-sky/investigation-state/runtime/search-probes-ui-preview/validation/fauna-categories/`
- `games/no-mans-sky/investigation-state/runtime/search-probes-ui-preview/validation/fauna-revamp/`
- `games/no-mans-sky/investigation-state/runs/20261010T-player-attacking-fauna/`

The supplied mods were inspected without executing or installing them. Current untouched Experience,
Rare/Infestation object and GameTableGlobals assets also pass semantic round trips. Authored mission
assets compile/decompile with remaining authored leaves preserved and removed suitability leaves
restored only as compiler schema defaults. This does not prove runtime merge or mission behaviour.

Arbyis XIX and its neighbours qualify player-predator positive/negative decoding. Wafford Prime
supplies land and flying examples. Passive Eggyon IV capture contains 14 positive species roles:
land, airborne, aquatic and cave populations; the operator independently confirms the discovery
count. Photographs identify aquatic prawn/shark, flying lizard and bipedal land bodies. Their
displayed discovery heights agree with generated gender heights at the game's one-decimal precision.
A visor photo of a different bipedal gender illustrates an actor-height difference. Photographs also
retain Tropical affinity and two distinct A/B/C stat combinations with B overall ranks.
Rarity/activity labels and all body variants do not yet have a complete independent visual oracle.

Production decoder replay uses owned captured roles and planet headers with only the role-array
pointer patched. Family predicates cover present and absent families in each domain. Model controls
cover joint species matching, domain conjunction, heights, unavailable choices, unknown/empty facts,
shared cache ownership and preset identity. Source tests, authored-asset checks, Windows compilation
and preview suspension pass. Retained measurements collected during degraded host health do not
qualify performance or allocation behaviour; structural bounds are deterministic source checks.

The existing Player-attacking fauna control has operator acceptance. The domain and worm candidate
is installed in NMS and Amethyst but has no fresh in-game acceptance. Candidate searches with
positive/negative species and worm controls, cache parity and visible labels remain required. The
standalone preview stays closed while NMS runs, following the development guide.

The installed checkpoint precedes the independent Fauna Criteria layout. That layout and the move of
development tooling to the parent repository are source changes displayed in the standalone preview
for operator review; they have not been installed. Their focused qualification and retained checks
are in
`games/no-mans-sky/investigation-state/runtime/search-probes-ui-preview/validation/fauna-criteria-layout/`.
