# Unfinished agent pickup

FreeTerraForged work is in these plans:

- [Configurable shorelines](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-shorelines.md)
- [Configurable strata](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/configurable-strata.md)
- [Current-target compatibility qualification](.agent-docs/games/minecraft/mods/FreeTerraForged/plans/current-target-compatibility-qualification.md)

Live Git and source are authoritative for branch state.

## No Man's Sky Search Probes

Search Probes is fully implemented in Rust; Python and NMS.py are not product runtime dependencies.
Follow [the Rust release plan](.agent-docs/games/no-mans-sky/working/search-probes-rust-overhaul.md)
and establish current behavior from the Rust source and live runtime. Runtime work is authorized
when needed. Use only `save.hg`/`save2.hg` ("Galaxies 1-50") and visually verify save identity
before probes; never infer it from a menu row or send an automatic fixed menu sequence. Do not move
the character, fly, warp, or otherwise travel through gameplay, and do not mutate saves. Do not run
100,000-system or billion-system searches; each search must stay under ten minutes. Current region
behavior and validation boundaries are in
[region streaming evidence](games/no-mans-sky/investigations/analysis/search-probes-regions.md). Its
current plan is
[system-search-investigation.md](.agent-docs/games/no-mans-sky/working/system-search-investigation.md);
build/install and runtime procedures are in `games/no-mans-sky/tooling/` and scoped acceptance is in
`games/no-mans-sky/investigations/analysis/search-probes-acceptance.md`.

Before runtime work, inspect the installed package, process, and runtime-session state. Menu, form,
mission-launch, and abandonment automation is within the established scope. Never replace installed
files while `NMS.exe` is running. Use compositor captures for Wayland Vulkan windows and verify
bounded capture completion. After a mod fix, update, or change reaches user-testing readiness, make
a full production build and install the same package into both the game files and Amethyst's managed
sources so a stale manager cache cannot overwrite it. Preserve user presets. Do not commit or push
without the user's express permission. Package changes must work through ordinary Steam self-start
without a development injector.
