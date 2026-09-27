# FreeTerraForged

FTF-specific engineering references and active feature work live here. The upstream-facing source
remains in `games/minecraft/mods/FreeTerraForged`.

## Active work

- [Configurable shorelines](plans/configurable-shorelines.md)
- [Configurable strata](plans/configurable-strata.md)

## Compatibility qualification

- [Current-target qualification](plans/current-target-compatibility-qualification.md) defines the
  evidence needed to qualify the compatibility runtime against current upstream.

## Engineering references

- [FTF wiki](../../../../../games/minecraft/mods/FreeTerraForged.wiki/Home.md) — preset settings and
  reusable FTF world-generation concepts.
- [Minecraft reference](../../wiki/README.md) — reusable Minecraft world-generation behavior.
- [World-generation compatibility contract](refs/worldgen-compatibility-contract.md) — architecture
  constraints for future compatibility changes.
- [Minecraft investigation guide](../../agentic-development-guide.md) — scenario, probe, and
  evidence workflow.

## Source and evidence workflow

- Post-v1.0 feature and compatibility changes target `upstream/1.21.1_unstable`; `upstream/1.21.1`
  is the released stable line.
- Refresh upstream refs and use a clean worktree from the current target branch for new
  implementation or evidence. The retained compatibility worktree is an older scenario baseline and
  does not establish current-target qualification. Scenario files are manual inputs that must be
  invoked explicitly.
- Use `tooling/squinch mc-investigate` for controlled runtime evidence and the Minecraft
  investigation guide for authority boundaries and cleanup.
- Acquire runtime artifacts through `tooling/squinch third-party minecraft` and the catalog at
  `.squinch/games/minecraft/third-party/artifacts.toml`.

## Documentation boundaries

Feature plans contain current contracts, unresolved decisions, and acceptance criteria. Reusable
engineering behavior belongs in the wiki or the compatibility contract. Drop completed status notes
and one-off conclusions when no current decision relies on them; keep raw runtime observations with
their run artifacts while they remain useful.
