# Parked and ongoing workstreams

The FreeTerraForged compatibility runtime remains ongoing. Configurable strata, configurable
shorelines, and No Man's Sky Search Probes are parked. Live Git, source, dependency, host, and
runtime state supersede this routing note.

The preset-editor settings documentation is complete in the
[FreeTerraForged wiki](games/minecraft/mods/FreeTerraForged.wiki/README.md). The
[settings index](games/minecraft/mods/FreeTerraForged.wiki/settings/README.md) links to
beginner-friendly guides for the nine settings screens reachable through the current GUI navigation.
Reachability was checked from the preset list through each page's previous/next links; the unlinked
Structure Settings page is excluded. Each included page was checked against its GUI, preset data,
and generation consumers. Visible controls with no effect remain documented as such. For future
documentation, recheck current source rather than assuming a tooltip is correct, and use the
Minecraft investigation guide and `tooling/squinch mc-investigate` when source cannot settle
behavior.

## FreeTerraForged

The nested source at `games/minecraft/mods/FreeTerraForged` has local `1.21.1` tracking
`upstream/1.21.1`; the local baseline has been pushed to `origin/1.21.1`.

The ongoing compatibility implementation is on `feat/worldgen-compatibility-runtime` in
`games/minecraft/investigation-state/worktrees/ftf-worldgen-compatibility`. Review its exact status
before acting. Do not reset, reconstruct, clean, stash, commit, switch, or remove this worktree
without explicit user direction. Its current branch tip predates the newly synced baseline;
reconcile it deliberately before treating branch-owned probes as current evidence.

The retained feature branches `feat/configurable-strata` and `feat/configurable-shorelines` are
parked backlog, not active work. They need deliberate integration with the current baseline and
their listed QA gates:

- [Configurable Strata](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-strata.md)
- [Configurable Shorelines](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-shorelines.md)

Remaining pre-release findings are recorded in
[ftf-pre-release-findings.md](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/ftf-pre-release-findings.md);
none is currently in progress. Keep seed identity and preset/spawn ownership as separate
workstreams.

For compatibility-runtime implementation and evidence, follow the
[worldgen compatibility plan](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/worldgen-compatibility.md),
its
[acceptance record](.agent-docs/games/minecraft/mods/FreeTerraForged/refs/compatibility-runtime-acceptance.md),
and the [agentic development guide](.agent-docs/games/minecraft/agentic-development-guide.md). Use
`tooling/squinch mc-investigate`, repository-relative scenarios, and the catalog acquisition
pipeline for third-party jars and sources. Before JVM-bearing work, verify host health,
investigation ownership, and complete cleanup. Never use a personal Minecraft launcher profile.

## No Man's Sky Search Probes

This workstream is parked. Its current plan is
[system-search-investigation.md](.agent-docs/games/no-mans-sky/working/system-search-investigation.md);
build/install and runtime procedures are in `games/no-mans-sky/tooling/` and scoped acceptance is in
`games/no-mans-sky/investigations/analysis/search-probes-acceptance.md`.

Before future runtime work, inspect the installed package, process, and runtime-session state. Menu,
form, mission-launch, and abandonment automation is within the established scope; do not fly or warp
through gameplay, mutate saves, or replace installed files while `NMS.exe` is running. Use
compositor captures for Wayland Vulkan windows and verify bounded capture completion. Package
changes must pass the scoped gates and work through ordinary Steam self-start without a development
injector.
