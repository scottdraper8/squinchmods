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
- Completed-target reuse evidence:
  `games/no-mans-sky/investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json`
- Current colour/island reference and installed-update evidence:
  `games/no-mans-sky/investigation-state/runs/20260915T030000Z-colour-island-reference/analysis.json`
  and sibling `installation.json`.
- Managed-source deployment and fresh-runtime validation:
  `games/no-mans-sky/investigation-state/runs/20260915T050700Z-colour-redeployment/analysis.json`
  and sibling `installation.json`.

### Current continuation gate

The colour/island/UI update is built and installed in both the game and Amethyst's owned deployment
sources, with presets preserved. The host recovered after restart. Stale managed-source files had
overwritten the prior direct installation; the installer now synchronizes and remembers those
sources transactionally. Fresh gameplay-callback controls reject the player's Bujav L2 target for
blue sky and blue water independently, match its loaded selected-colour records exactly, and pass
positive colour/island searches with candidate rechecks. Read the current scoped acceptance record
for the actual form and package gates. Generated colour inputs are not an exact rendered-pixel
guarantee. The player confirms mission lifecycle and Galaxy Map behavior work; do not reopen that
investigation or change its native identities.

The current public executable is Steam build `25320008` with SHA-256
`78c1d883a8d47c99308795ee22e8bdf7c03970f0af090effa45107cefb194ba4`. Search Probes has been rebased
to its current native function/global addresses, its executable allowlist and runtime documentation
are updated, and the production package was freshly installed. The current live hook control passes,
F7 visibly opens the form, and the complete production matrix passes in
`games/no-mans-sky/investigation-state/runs/20260915T153000Z-production-7.01-update/`. Keep that run
as the current runtime evidence; the matrix label correction is parent tooling only.

The single island criterion uses resolved object flags, not terrain-family naming. Sky and water use
native-selected weather/optical records. Base grass is Green, leaves Purple, selected sky Blue, and
water Cyan/turquoise on the captured Cape Oath/Mosworkin reference. Cloud/near-water/sunset/night
controls are removed; weather type plus one Storms control remain. Retired form criteria in saved
presets remain visible additional constraints and must round-trip without loss.

### Ownership and lifecycle

`games/no-mans-sky/mods/search-probes` is the standalone Search Probes Git submodule. It owns the
runtime, form, criteria, native bridge, Guide/mission adapter definitions, bootstrap, and pinned
dependencies. The parent owns tooling, build/install orchestration, tests, and retained evidence.
Preserve unrelated dirty Minecraft work.

Form navigation starts one disposable NPC mission through the native mission engine; no persistent
form-listener mission exists. The native start seam is verified from current reward and mission
sequence callers, not the unrelated request path described in older artifacts. Active or pending
targets are rejected before changing their destination. Completion acknowledgment waits for both an
active mission, its exact planet-address route, and verified native selection. Abandonment and
arrival cleanup belong to NMS. Start with `GcSeed(value=0, valid=true)`, not an all-zero invalid
seed: invalid identity matching creates duplicate instances after completion. Native restart also
discards its selection flag, so selection is performed after the route is established.

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
