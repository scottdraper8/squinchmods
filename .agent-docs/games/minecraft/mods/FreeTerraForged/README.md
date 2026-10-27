# FreeTerraForged

FTF-specific engineering references and active feature work live here. The upstream-facing source
remains in `games/minecraft/mods/FreeTerraForged`.

## Current work

- [Configurable shorelines](plans/configurable-shorelines.md)
- [Configurable strata](plans/configurable-strata.md)

## Engineering references

- [FTF wiki](../../../../../games/minecraft/mods/FreeTerraForged.wiki/Home.md) — preset settings and
  reusable FTF world-generation concepts.
- [Minecraft reference](../../wiki/README.md) — reusable Minecraft world-generation behavior.
- [World-generation compatibility contract](refs/worldgen-compatibility-contract.md) — architecture
  constraints for future compatibility changes.
- [Minecraft investigation guide](../../agentic-development-guide.md) — generic tooling and
  task-local scratch-state policy.

## Source and validation workflow

- Post-v1.0 feature and compatibility changes target `upstream/1.21.1_unstable`; `upstream/1.21.1`
  is the released stable line.
- Refresh upstream refs and use a clean worktree from the current target branch for implementation
  and validation.
- Use `tooling/squinch mc-investigate` for task-local runtime checks. Remove run outputs and one-off
  inputs when the active work is complete; encode long-lived behavior in CI/CD tests.
- Acquire runtime artifacts through `tooling/squinch third-party minecraft` and the catalog at
  `.squinch/games/minecraft/third-party/artifacts.toml`.

## Documentation boundaries

Feature plans contain current contracts, unresolved decisions, and acceptance criteria. Reusable
engineering behavior belongs in the wiki, compatibility contract, and CI/CD tests. Do not keep raw
observations, one-off inputs, or run reports as a persistent investigation archive.
