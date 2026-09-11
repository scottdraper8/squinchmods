# No Man's Sky Tooling

Executable tooling owned specifically by No Man's Sky lives here. Root `tooling/` contains only
repo-wide dispatchers; it does not implement NMS behavior.

## Third-party artifacts

[`third-party/`](third-party/) implements catalog-backed Nexus Mods metadata retrieval, acquisition,
manual browser-import, safe unpacking, inventory, validation, and bounded removal. Invoke it through
the game-neutral root dispatcher:

```bash
tooling/squinch third-party no-mans-sky --help
```

Its committed catalog is `.squinch/games/no-mans-sky/third-party/artifacts.toml`. Downloaded
archives live in the external squinchmods cache. Unpacked third-party trees mirror Minecraft under
the ignored `games/no-mans-sky/reference/sources/<claimed-version>/mods/<mod>/` namespace; they are
reference source, not maintained workspace mods. See the
[third-party tool README](third-party/README.md) for the exact ownership model and workflow.
