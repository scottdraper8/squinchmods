# Search Probes special planetary resources

## User-facing contract

Unique resources is a multi-select for Ancient bones, Salvageable scrap and Swarm debris. Unique
resource match selects All selected (default) or Any selected, independently of the ordinary
resource match mode. All selected requires every chosen resource on the same planet; Any selected
accepts one or more. The field is AND with other filters. The source is the generated
discovery-resource hint list, rather than a guess based on biome, sentinel difficulty or the ground
resource list. Vile Brood is a separate Any / Require / Exclude creature feature, corresponding to
the discovery label Vile Brood Detected. Ordinary infested biome subtypes do not establish this
encounter. The planet Sentinel control classifies the current combat difficulty's level. System
Profile Dissonance classifies the world property through the normal-difficulty corrupted-Sentinel
entry, independently of difficulty settings that suppress Sentinel encounters.

## Native source

For the currently supported executable, GcPlanetData ExtraResourceHints is a dynamic array at
+0x33F0. Its count is at +0x33F8 and records have stride 0x20, comprising two 16-byte strings.
Resource identifiers are UI_BONES_HINT, UI_SCRAP_HINT and UI_B_SWARM_HINT; Vile Brood uses
UI_BUGS_HINT. Icons are BONES, SALVAGE, SWARM and GRUBS respectively. Other hints, such as biome
plants, remain independent of these choices.

The original standalone Scrap criterion used HasScrap at +0x3ACE. That native flag participates in
optional external object-list eligibility; it is broader than the final selected resource hints.
GenerateQueryInfo calls the external-list selection, then the hint builder at 0x141697090 before the
live planet destructor visitor. The builder maps selected list names to configured resource
hint/icon pairs. The reader at 0x1416750A0 places those extra hints alongside the ordinary resource
entries. Reading these completed records adds no asset acquisition or native generation call.

Swarm Debris's configured external list requires Scrap, corrupted Sentinels, a permitted biome and
an additional probability check. Its default probability is 0.4 in the captured live configuration,
with subtype probabilities also consulted. Scrap + Dissonance is therefore a candidate prefilter,
not a sufficient positive classification. The native condition reads the normal combat-difficulty
sentinel entry at +0x34FC; Search Probes uses the explicit resulting hint instead of reproducing
that eligibility calculation. Hello Games describes the relevant worlds in the
[Swarm update](https://www.nomanssky.com/swarm-update/).

## Evidence and qualification

Raw identity, bounded read-only captures, generated list configuration, disassembly, replay and
build/deployment artifacts are retained in
[the unique-resource run](../../../../games/no-mans-sky/investigation-state/runs/20261010T-unique-resources/).

- Exleywoo Major, renamed Apam Woods in discoveries: UI_BONES_HINT, no scrap flag.
- Hersfiel XVI: UI_BUGS_HINT; the operator confirms Vile Brood Detected. Biome subtype 2 is not the
  infested subtype 24. Neighbour Uffa Major independently carries the same hint.
- Sebash Prime: UI_SCRAP_HINT and HasScrap; not dissonant.
- Atsy III: corrupted Sentinels but no Scrap or Swarm Debris hint.
- Wafford Prime: UI_B_SWARM_HINT, UI_SCRAP_HINT and UI_BUGS_HINT coexist. The operator screenshot
  confirms Swarm Debris, Salvageable Scrap and Vile Brood Detected alongside Dissonance detected.
- Sisenil Minor: corrupted Sentinels and Scrap, with UI_SCRAP_HINT but no UI_B_SWARM_HINT in both
  the loaded system and landed captures. The operator screenshot agrees with the Scrap label.

The first Ancient Bones capture read all six capacity slots; its sixth record is stale from the
previous system and is excluded from evidence. Subsequent captures use the live planet count.
Production decoding and compiled predicates pass replay of the counted loaded planets and malformed
array controls. The installed explicit Swarm Debris query returns ten matches within its
1,000-system budget, with Wafford Prime independently verified against loaded data and the operator
tooltip. The production reader and all seven nonempty selections in both match modes pass replay
across 22 counted loaded planets, including cached fact merges. Match modes persist in criteria and
form part of compiled continuation keys. Neither mode adds native acquisition. Installed Bones and
Brood Require/Exclude searches have not been separately exercised.
