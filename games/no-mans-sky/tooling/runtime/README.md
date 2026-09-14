# NMS Search Probes runtime

This directory owns the parent-side build, install, host-control, and resident test tooling. Product
code lives in the private [`search-probes`](../../mods/search-probes/) mod repository, under
`src/search_probes/`. The package currently targets the pinned Cosmos 7.01 build and the validated
Proton host. The
[scoped acceptance record](../../investigations/analysis/search-probes-acceptance.md) distinguishes
tested lifecycle behavior from broader platform and travel validation.

## Build and install

Stop NMS before building or installing:

```bash
games/no-mans-sky/tooling/runtime/build_system_search.py \
  games/no-mans-sky/dist/SearchProbes-7.01
```

The command creates an expanded Nexus-ready tree and a same-named ZIP, verifies the manifest,
installs transactionally into the detected NMS directory, and configures Proton's native-first
`winmm` override. Use `--no-install` for build-only output, `--install-only` to verify and install
an existing expanded output, `--rebuild-runtime` to recreate the pinned Python dependency runtime,
or `--game-root` to select an explicit NMS installation.

The build obtains the current Guide adapter through the investigation pipeline and packages four
generated adapter files, including the NPC mission table. Native bootstrap sources and dependency
requirements come from the mod repository. The package contains the resident Python runtime under
`app/`, the mod's `app/search_probes/` package, and the native bootstrap; host control and matrix
programs remain in this parent repository and are not shipped to players.

The installer fails closed if NMS is running, paths are not recognizably owned by Search Probes, or
another product already owns `Binaries/winmm.dll`. It does not guess at DLL chain-loading.

## In-game use

Launch NMS normally from Steam. The application-local `winmm.dll` starts the bundled Python runtime
inside NMS and installs the exact-build hook. The resident form starts hidden; **F7** shows or hides
it using direct Win32 key-state polling. The form is available once resident state is ready, while
search work advances only from NMS's gameplay update callback.

Choose criteria, a candidate limit, and a result limit, then press **Search**. Presets can be saved,
updated, deleted with a second-click confirmation, or restored to built-ins. Presets and resident
state are stored below the installed package's `app/.resident-search/`; valid preset data is backed
up on replacement. Host-side tools must point at that same directory with
`SQN_RESIDENT_SEARCH_ROOT`.

Search results contain the decoded system and first matching planet. **Navigate to selected result**
publishes the exact planet address to the owned Search Probe Target mission. In the Log, select
**Search Probe Target**, then use **Current Mission** in the Galaxy Map. The generated planet index
is converted to NMS's one-based address field, so navigation targets the matched planet rather than
only its system. System-only queries use the first generated planet as their destination.

The navigation mission uses NMS's ordinary `SQN_SS11_NAV` NPC mission path. `NativeMissions.start`
invokes the native start function at `0x1409B13C0` with the mission manager resolved from
application base + `0x837B20`. Before changing a target, the resident requires the mission's
active/pending guard. The acknowledgement waits for both the active mission state and the exact
route-bearing target, preventing a stale or merely system-level route from being reported as ready.

Guide launches use their own native slot request/ready path. A no-match search publishes no target;
abandon that probe in the Log before retrying. Search details remain available in the F7 form. A
saved Guide destination is cleared before a new launch, and Guide data is refreshed on the next NMS
launch rather than mutating an open native page. Search Probe does not use a quick-warp action.

The form keeps target-planet predicates separate from system aggregates. Terrain-family floating
islands and resolved object-backed floating islands are independent controls; required resource
slots are a same-planet conjunction; system “contains” predicates may be satisfied by different
planets. Generated hue families describe generated inputs, not final rendered pixels.

## Development tools

The external attach launcher is a development fallback for a deliberately non-native test install.
Do not run it while the packaged `winmm.dll` runtime is installed in the same NMS process:

```bash
SQN_RESIDENT_SEARCH_NO_OVERLAY=1 \
  games/no-mans-sky/tooling/runtime/launch_resident_search.sh
```

The resident matrix exercises bounded survey, deep spawn copying, repeated snapshots, predicate
parity, exact criteria, and teardown within one resident session. It requires the mod source on
`PYTHONPATH` because the matrix is parent-owned:

```bash
PYTHONPATH=games/no-mans-sky/mods/search-probes/src \
  games/no-mans-sky/tooling/runtime/resident_search_matrix.py smoke
PYTHONPATH=games/no-mans-sky/mods/search-probes/src \
  games/no-mans-sky/tooling/runtime/resident_search_matrix.py full
```

For a cold-client end-to-end run with health gates and ordered teardown:

```bash
games/no-mans-sky/tooling/runtime/run_resident_matrix_e2e.sh full
```

The host controller can inspect state or request an orderly live detach. It must use the installed
state root and the mod source for protocol imports:

```bash
SQN_RESIDENT_SEARCH_ROOT="/path/to/No Man's Sky/Binaries/SearchProbes/app/.resident-search" \
PYTHONPATH=games/no-mans-sky/mods/search-probes/src \
  games/no-mans-sky/tooling/runtime/resident_search_control.py status

SQN_RESIDENT_SEARCH_ROOT="/path/to/No Man's Sky/Binaries/SearchProbes/app/.resident-search" \
PYTHONPATH=games/no-mans-sky/mods/search-probes/src \
  games/no-mans-sky/tooling/runtime/resident_search_control.py stop
```

Live detach is available only while the gameplay callback is advancing. If NMS is at a menu or the
Galaxy Map, exit NMS normally instead. The controller never replaces the hook or releases injected
state directly; the gameplay thread performs shutdown, restores hooks, drains active callbacks, and
only then releases runtime storage.

## Layout and safety boundary

```text
mods/search-probes/                 private mod repository
  src/search_probes/                resident product code
  native-bootstrap/                 application-local winmm forwarder source
  dependencies/                     pinned runtime requirements
tooling/runtime/                    parent build/install/control/matrix tooling
installed .../SearchProbes/app/
  search_probes/                    bundled product package
  .resident-search/                 shared state, commands, progress, and results
```

All engine and navigation calls run on NMS's gameplay thread. Background work performs filesystem
I/O and communicates through atomically published mailbox files. Searches stay within the player's
current galaxy and bounded indexed graph; they do not fly the player or traverse remote systems.
`Any` criteria are omitted from commands, object resolution is deferred until cheaper predicates
pass, and candidate/result limits remain bounded by the protocol.

The runtime is pinned to one executable hash and refuses other builds. Native Windows, graphics or
input overlays, VR, live Guide refresh, and future executable updates require separate evidence and
are not claimed here.
