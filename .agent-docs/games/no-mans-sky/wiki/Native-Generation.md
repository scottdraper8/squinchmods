# Native generation and addresses

## Addresses

A universal address contains signed X/Y/Z region coordinates, a zero-based galaxy index, a system
index and a planet component. Planet zero identifies a system; generated planet index n uses n+1.
The packed layout is X bits 0–11, Z 12–23, Y 24–31, galaxy 32–39, system 40–51 and planet 52–55.
Portal codes omit the galaxy and encode planet/system/Y/Z/X as `PSSSYYZZZXXX`. The same portal code
in another galaxy identifies another destination. Displayed galactic coordinates offset X/Z by 0x7ff
and Y by 0x7f.

Native region generation supplies actual address arrays. System indices are not a guessed contiguous
interval; purple-system addresses occupy an additional range beginning at 1001. The loaded galaxy
graph is a nearby subset, not the entire searchable galaxy. Caller-owned region generation can
enumerate systems outside that graph without adding them to it.

## Generated planet data

`GenerateQueryInfo` produces planet data and calls `GenerateCreatureRoles` before releasing it. Its
completed-data lifetime contains selected object lists, discovery resource hints and creature roles.
Values can be copied while valid; embedded pointers do not remain valid afterward.

The temporary generated planet does not populate the loaded-world address field used by a loaded
planet. The caller's exact query address is the remote identity. A zero loaded-address field does
not mean that the generated planet lacks an identity.

Solar and planet generators contain mutable random state. Native resource managers, caches,
constructors and destruction have separate ownership from those structs. Copying a generator alone
does not make concurrent native calls independent. Callbacks, loading transitions and
resource-manager shutdown define additional lifetime boundaries.

## Native resources

Requested recipe, ready resource and selected component are separate identities. Filename caches can
reuse an existing seed/filter selection. A requested recipe does not prove which recipe produced the
cached model. Attachments and procedural descriptors determine selected components and variants.

Resource requests distinguish pending, ready, missing, failed and cancelled states. Release does not
imply immediate manager cleanup. Handles, owner generations and manager epochs distinguish retired
or replaced resources from their successors.

Procedural model bounds depend on the selected scene graph, descriptors, attachments, transforms and
completed child resources. Modular building bounds also depend on completed parts, snap counts and
variants. A scene filename alone is not a complete geometry input.

## Metadata and UI assets

`METADATA/REALITY/WIKI` defines Guide/Catalogue entries. `WIKIMISSIONTABLE` defines Wiki mission
sequences; existing Guide topics can launch Wiki missions containing scan events. Localization
tables supply strings. Mission destinations require native mission state as well as data-table
entries.

`PAGESELECTBAR` supplies a generic pause-menu layout. Closed frontend page types and native
controllers determine routing; adding a visible slot does not create a routed page.

EXML merge output, full MBIN replacements, native state and rendered UI are distinct layers. A
parseable asset does not establish an active mission or reachable menu page.
