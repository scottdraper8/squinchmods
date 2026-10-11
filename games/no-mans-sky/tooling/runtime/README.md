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

## Standalone UI preview

From the parent repository root, run:

```sh
games/no-mans-sky/tooling/runtime/preview-ui
```

The host shares the product's Rust UI and keeps separate preview settings. It rebuilds and reopens
on successful UI/model/host source edits while preserving the draft and window state. A failed build
keeps the previous window open. Close the window or press Ctrl+C to stop the watcher. NMS process
detection suspends the preview and prevents window launches during gameplay; the preview resumes
after NMS exits. Searches and navigation require the in-game overlay.

Python 3 and Rust are development dependencies. The launcher, fixture tests and Rust desktop host
belong to this parent repository and do not ship in the Search Probes mod. Use
`preview-ui --no-watch` for a single window or run the host directly with:

```sh
cargo run --locked --manifest-path games/no-mans-sky/tooling/runtime/ui-preview/Cargo.toml
python games/no-mans-sky/tooling/runtime/ui-preview/test_watcher.py
```

## Windows build container

`windows.Containerfile` defines the Fedora/MinGW build environment for the product's Windows DLL. It
is a development dependency, not a distributable mod component. The product packager remains in the
Search Probes Rust workspace and retains dependency/toolchain license notices from its `licenses/`
directory in the release ZIP.
