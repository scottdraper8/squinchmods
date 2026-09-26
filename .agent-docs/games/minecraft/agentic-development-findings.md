# Minecraft Agentic Development Findings

Unresolved tooling defects that need human attention. Mod-specific conclusions belong in that mod's
canonical plan, durable operating rules belong in `agentic-development-guide.md`, and raw evidence
belongs in retained run artifacts. Remove an entry once its resolution gate is satisfied.

## Active

### `preset-fixture` cannot compile against plain `upstream/1.21.1`

Fabric headless datagen provides `HolderLookup.Provider`, but `Datapacks.makePreset` on
`upstream/1.21.1` requires `RegistryAccess`. The widening fix is on
`fix/preset-fixture-provider-widening` (`40acb11`). Fixture presets also needed three missing
`IslandSettings` codec fields to avoid registry-load crashes.

**Needs:** merge the widening branch (or PR to `ETcodehome/FreeTerraForged`) and confirm a
`preset-fixture` run produces a fixture that boots a server.

## Entry rule

Add only a reproducible, repository-wide tooling defect with a concrete cost and a resolution gate.
Do not add reminders, mod behavior, speculative improvements, completed work, or workarounds. Fold
related symptoms into the existing root issue instead of adding another entry.
