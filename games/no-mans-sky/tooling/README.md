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

## Investigation runner

[`investigate/`](investigate/) provides pinned HGPAK/MBIN tooling, current-game asset inventory and
extraction, semantic MBIN round trips, EXML/mod analysis, conflict detection, merged-export checks,
executable string probes, declarative scenarios, and transaction-safe staging:

```bash
tooling/squinch nms-investigate --help
```

Runs live below the ignored `games/no-mans-sky/investigation-state/` boundary. See the
[investigation runner README](investigate/README.md) and the
[NMS agentic development guide](../../../.agent-docs/games/no-mans-sky/agentic-development-guide.md).

## Client operator helper

[`client/`](client/) contains current-host UI automation kept deliberately outside the evidence
runner. Its launcher creates a virtual controller before Steam starts NMS, focuses NMS immediately
before each known input, and selects the verified newest/top save route without per-step
screenshots:

```bash
games/no-mans-sky/tooling/client/launch-latest-save.py
```

The helper is fixed to the currently proven 3840x2160 menu layout and fails closed when the client,
profile, save ordering, or window geometry does not match its contract. See the
[client helper README](client/README.md).

## System Search runtime

[`runtime/`](runtime/) contains the current-build-pinned Search Probes build, install, and host
control tooling. The mod runtime sources, native bootstrap, and pinned runtime dependencies are
owned by [`../mods/search-probes/`](../mods/search-probes/). Build the distributable and install it
locally with:

```bash
games/no-mans-sky/tooling/runtime/build_system_search.py \
  games/no-mans-sky/dist/SearchProbes-7.01
```

Run it with NMS stopped. It emits an expanded Nexus-rooted tree plus ZIP, verifies both product and
dependency inputs, installs transactionally, and configures the Proton DLL override. Thereafter an
ordinary Steam launch self-starts Search Probes; the owned form begins hidden and F7 toggles it. The
historical external attach launcher is retained only for controlled development runs. See the
[runtime README](runtime/README.md) for packaging details and the exact compatibility boundary.
