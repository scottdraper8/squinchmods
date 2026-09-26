# No Man's Sky agentic investigation guide

Use this guide for reproducible NMS mod and asset work. The canonical game-format and deployment
facts remain in [README.md](README.md); command details live in the
[investigation tooling README](../../../games/no-mans-sky/tooling/investigate/README.md).

## Start from live identity

Run `tooling/squinch nms-investigate doctor` before collecting evidence. Record the Steam build ID,
public/experimental branch, archive snapshot, exact asset/archive hashes, HGPAKtool version,
MBINCompiler release/hash, and actual .NET backend identity. Reacquire current third-party files
through `tooling/squinch third-party no-mans-sky freshness`, `acquire`/`import`, `inspect`, and
`validate` before they support a compatibility conclusion.

Do not use timing, allocation, RSS, startup, shutdown, or cleanup measurements while doctor reports
a degraded host. Content hashes and deterministic semantic comparisons may still be useful when
their commands complete, but retain the degraded-host label.

## Evidence ladder

Work upward only when a lower layer cannot answer the question:

1. Current source, MBINCompiler templates, executable strings, and bytecode/static structure.
2. Exact HGPAK inventory, extraction, MBIN version/decompile, and untouched semantic round trip.
3. EXML target/template/touched-path analysis and full-replacement comparison to current vanilla.
4. Actual merged `MODS/EXPORTED` metadata, checked against authored intent and vanilla.
5. Controlled client behavior and visual QA with a disposable, backed-up save.

Keep the authority of each result explicit. XML parseability is not merge success; merge success is
not menu routing; a visible control is not a working action; one gameplay observation is not update
or conflict compatibility.

## Organize investigations

Put repeatable, non-secret workflows in `games/no-mans-sky/investigations/scenarios/`. Scenarios
declare exact inputs, expected positive or negative outcomes, and fail-fast behavior. Raw output
belongs to the ignored run tree; durable current-state conclusions belong in focused
`.agent-docs/games/no-mans-sky/refs/` documents. Never commit extracted copyrighted mod files, game
assets, saves, logs, compiler binaries, or runtime staging trees.

Use one coherent question per scenario. Keep extraction, schema/overlay, conflict, executable, and
visual claims separate unless evidence demonstrates a shared contract. Include negative controls:
missing assets must fail, semantically changed XML must differ, stale full replacements must be
distinguishable from current vanilla, overlapping modifications must be detected, modified staged
trees must refuse cleanup, and expected failures must be declared rather than ignored.

## Choose the correct seam

Prefer stable data surfaces: existing registries/tables, narrow EXML writes, localization, and loose
resources. Rebuild a complete MBIN from current vanilla only when the UI or data contract cannot
express the change narrowly. Treat executable routes and runtime hooks as a separate mechanism with
separate version, lifecycle, injection, teardown, and save-safety gates.

For the top pause-menu bar, `PAGESELECTBAR.MBIN` proves only a generic seven-slot layout. Current
executable strings and generated templates show that page routing belongs to closed frontend page
types and executable-owned controllers. A visual eighth slot without a new route is not a tab.
Adding a genuinely new peer page therefore requires a proven runtime hook/executable seam; ordinary
EXML or UI MBIN deployment does not supply one. Reusing or altering content inside an existing
Catalogue/Guide page remains data-driven and is the practical supported surface.

## Runtime safety

Develop outside the live installation. `stage` is dry-run by default and `--apply` owns exactly one
uniquely named child under `GAMEDATA/MODS`; it does not launch, enable, reorder, or clean another
mod. Always inspect `stage-status` before removal. Do not automate Steam/Proton client QA until a
disposable prefix, non-personal save fixture, deterministic input/oracle, log/export collection, and
complete process teardown are all proven on the current host.
