# Search Probes runtime development

The product, UI, bootstrap, native search workers and packager are the Rust workspace in
[Search Probes](../../mods/search-probes/README.md). Its README defines the locked build commands,
installation layout and supported executable. Python and NMS.py are not runtime dependencies.

Use `tooling/squinch nms-investigate` for retained PE disassembly, archive extraction, native schema
roundtrips and host health. These host-side investigation tools do not ship with the mod. Use the
[client controls](../client/README.md) for visually verified menu input. Runtime work is restricted
to `save.hg`/`save2.hg` (Galaxies 1-50). Never infer save identity from a menu row number.

Release gates and evidence are in the
[Rust release plan](../../../../.agent-docs/games/no-mans-sky/working/search-probes-rust-overhaul.md).
Do not replace installed files while NMS is running. Do not perform 100,000-system or billion-system
acceptance runs; keep every search below ten minutes.
