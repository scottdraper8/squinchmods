# Fauna and Arena

## Species metadata

Generated roles contain ecosystem ID, resource seed, engine type, tile, density, activity, rarity,
hemisphere and discovery gender heights. A completed empty role array establishes absence;
unavailable data does not. Positive roles establish populations, not catalogue membership alone.
`CreatureLife` is abundance, not the number of species or visible animals.

Body family, engine type, model appearance and placement are independent. Underwater tiles can place
crabs in the aquatic population despite ground movement definitions. Cave tiles mark underground
placement. `FLOATSPIDER` uses ground routing. `ForceType`/`RealType` alone do not reliably classify
habitat or appearance.

`GcCreatureHemiSphere` contains unrestricted, northern and southern values, without east/west
restrictions. Discovery rarity is Common/Uncommon/Rare; catalogue `SuperRare` is a separate enum.

Discovery height is metadata, separate from spawned size. The writer adds `0.4 * random - 0.2` to
the capped catalogue scale for the first height, then `0.2 * random` for the second. It does not
clamp to zero. Small schooling-fish definitions can have negative heights. Finite, representable
signed heights are legitimate native values.

Player-targeting `PlayerPredator` roles differ from ordinary predators and fish predators.
Difficulty, feeding and behaviour changes can suppress attacks without changing the role.

## Taming and battle eligibility

`GcCreatureData.CanBeUsedInPetBattler` supplies natural ecosystem battle eligibility.
`PetBattlerForcedAffinity` supplies an affinity override. Canonical ecosystem attachments associate
battle-enabled definitions with Pet/Creature interactions. Companion-slot availability and
placement-specific interaction restrictions are separate from species eligibility.

Aquatic habitat does not imply untameability: CRAB and HERMITCRAB can be battle eligible and
adoptable underwater. Fish and jellyfish references lack battle eligibility. The pure calculator can
nevertheless produce hypothetical ranks for ineligible creatures. Calculable ranks and biome-derived
affinity are not eligibility checks.

The visor panel uses Pet/Creature interaction routing. A missing panel does not prove the absence of
hypothetical rank inputs. Feeding, adoption, riding and panel display are distinct decisions; riding
can be blocked by placement.

## Wild Arena initialization

The seed combines selected creature component ID, role/resource seed, exact planet address, engine
creature type and adult size class. The role array does not store finished combat/agility/health
ranks.

The family ID need not equal the selected component ID. CRAB and HERMITCRAB select SPIDER. Luminous
manta and seahorse definitions use MANTA and SEAHORSE components. Selected attachments establish the
initializer's component identity.

The native roll produces C/B/A/S health, agility and combat classes. With C=0, B=1, A=2, S=3,
overall rank is C for sum zero, B for 1–3, A for 4–6 and S for 7–9. Overall is a combined grade, not
another independently generated stat.

Biome tables supply Tropical, Frost, Fire, Toxic, Desert, Radioactive, Anomalous and Mechanical
affinities. Robot-antelope and geometric definitions have overrides. Wild initialization remaps
relevant biome subtypes before biome lookup. Generated Arena opponents use a separate route.

## Size

Seeded role intervals and catalogue limits determine base scale. Actors measure transformed model
bases, not discovery height. Infant Arena classification divides measured size by the infant
multiplier.

The captured ordinary profile uses cutoffs 1.2, 2.5 and 4.5, actor multiplier 1 and infant
multiplier 0.5. Exact cutoffs belong to the higher class. There is no native 64-epsilon tolerance
rule. Floating-point reconstruction and parent conversion can move cutoff values into adjacent
classes.

Underwater placement with a query handle applies a depth multiplier. The captured linear profile
clamps depth to 200–800 and interpolates scale from 1 to 6.5. Generated base scale need not equal
the actor's measured scale.

## Worms and infestations

`UI_BUGS_HINT` identifies Vile Brood. Titan-worm burrows use selected spawnable
`SANDWORMMINI/GROUNDWORMSPAWNER` scenes. Large travelling sandworms use role-table `HasSandWorms`
and frequency fields. These are distinct occurrences; an infested subtype alone does not establish
all three.
