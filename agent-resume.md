# Unfinished agent pickup

FreeTerraForged work is in these plans:

- [Configurable shorelines](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-shorelines.md)
- [Configurable strata](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-strata.md)
- [Current-target compatibility qualification](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/current-target-compatibility-qualification.md)

Live Git and source are authoritative for branch state. No Man's Sky Search Probes has a deployed
Rust release under user QA.

## No Man's Sky Search Probes

The all-Rust overhaul is built, validated, deployed and pushed. User QA is active; do not send game
inputs, change presets or replace installed files during that session. Follow
[the Rust release plan](.agent-docs/games/no-mans-sky/working/search-probes-rust-overhaul.md). The
release plan also records the standalone runtime acceptance and candidate-package state. Use only
`save.hg`/`save2.hg` ("Galaxies 1-50") and verify runtime identity before probes. The old launcher
confused menu position with save number; automatic menu input is disabled. Do not run 100,000-system
or billion-system searches; each search must stay under ten minutes. Current region behavior and
validation boundaries are in
[region streaming evidence](games/no-mans-sky/investigations/analysis/search-probes-regions.md). Its
current plan is
[system-search-investigation.md](.agent-docs/games/no-mans-sky/working/system-search-investigation.md);
build/install and runtime procedures are in `games/no-mans-sky/tooling/` and scoped acceptance is in
`games/no-mans-sky/investigations/analysis/search-probes-acceptance.md`.

Before future runtime work, inspect the installed package, process, and runtime-session state. Menu,
form, mission-launch, and abandonment automation is within the established scope; do not fly or warp
through gameplay, mutate saves, or replace installed files while `NMS.exe` is running. Use
compositor captures for Wayland Vulkan windows and verify bounded capture completion. Package
changes must pass the scoped gates and work through ordinary Steam self-start without a development
injector.
