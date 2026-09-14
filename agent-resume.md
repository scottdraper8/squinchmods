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

## No Man's Sky Search Probes handoff

Establish live Git, host, installed-package, process, and runtime-session state before acting.
Current source and reproducible runtime evidence supersede prose. Menu, form, mission launch, and
abandonment automation are authorized; do not fly, warp, or navigate through actual gameplay. Never
replace installed runtime files while `NMS.exe` is running.

### NMS references

- Canonical plan: `.agent-docs/games/no-mans-sky/working/system-search-investigation.md`
- Build/install/control: `games/no-mans-sky/tooling/runtime/README.md`
- Investigation tooling: `games/no-mans-sky/tooling/investigate/README.md`
- Filter semantics: `games/no-mans-sky/investigations/analysis/search-filter-audit.md`
- Scoped acceptance: `games/no-mans-sky/investigations/analysis/search-probes-acceptance.md`
- Lifecycle evidence:
  `games/no-mans-sky/investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json`

### Ownership and lifecycle

`games/no-mans-sky/mods/search-probes` is the standalone Search Probes Git submodule. It owns the
runtime, form, criteria, native bridge, Guide/mission adapter definitions, bootstrap, and pinned
dependencies. The parent owns tooling, build/install orchestration, tests, and retained evidence.
Preserve unrelated dirty Minecraft work.

Form navigation starts one disposable NPC mission through the native mission engine; no persistent
form-listener mission exists. The native start seam is verified from current reward and mission
sequence callers, not the unrelated request path described in older artifacts. Active or pending
targets are rejected before changing their destination. Completion acknowledgment waits for both an
active mission and its exact planet-address route. Abandonment and arrival cleanup belong to NMS.

The scoped acceptance record covers repeated form-target start/abandon/restart, exact route
ownership, duplicate rejection, save/reload, actual form interaction, first F7, positive/no-match
Guide launches, native abandonment, and installed package parity. A no-match Guide probe needs
explicit Log abandonment; its detailed status appears in the form. Arrival/travel behavior remains
distinct from menu-only validation: the full native arrival sequence matches the retained
player-tested control, but this task does not authorize new flight/warp testing.

Use compositor captures for Wayland Vulkan windows. Bound every capture and confirm completion;
stale X11 frames or a stranded capture grab are not evidence of ignored input or a runtime failure.

Build/install only after scoped tests pass. Verify the exact installed footprint and ordinary Steam
self-start; do not leave a development injector or controller required for normal use.
