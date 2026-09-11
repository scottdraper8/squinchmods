# FreeTerraForged handoff

Establish current Git, dependency, host, and runtime state before acting; live evidence supersedes
this routing note.

## Read first

- Branch roles: `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/branch-map.md`
- Compatibility plan:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md`
- Acceptance gates:
  `.agent-docs/games/minecraft/mods/FreeTerraForged/refs/compatibility-runtime-acceptance.md`
- Investigation guide: `.agent-docs/games/minecraft/agentic-development-guide.md`

## Live ownership boundaries

The nested source at `games/minecraft/mods/FreeTerraForged` uses the `rename` branch tracking
`upstream/rename`. Its canonical Java package is `etcodehome.freeterraforged`; its mod ID and
resource namespace are `freeterraforged`.

The active compatibility worktree is
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility` on
`feat/worldgen-compatibility-runtime`. It contains user work. Do not reset, reconstruct, clean,
stash, commit, switch, or remove it without fresh authorization and an exact status review.

The compatibility and configurable-worldgen feature branches predate the namespace rename. Their
production source must be deliberately integrated with `rename` before their branch-owned probes can
provide post-rename evidence. Do not add package aliases, compatibility shims, legacy tooling paths,
or fallback source trees to bridge that boundary.

Fixture definitions are compact source presets. Full datapack trees are generated on demand into
ignored `games/minecraft/investigation-state/` storage through the selected worktree's real
exporter. Never restore the removed tracked generated-fixture cache or an old-namespace preset
archive.

Before JVM-bearing work, verify host health, investigation ownership/state, and complete cleanup.
Never use a personal launcher profile.
