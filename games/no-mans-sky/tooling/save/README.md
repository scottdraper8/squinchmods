# No Man's Sky Save Tool (through 7.14)

This SquinchMods CLI inventories, inspects, and transactionally edits Steam/Proton save formats up
to No Man's Sky 7.14. Raw inspection and edits preserve the game's obfuscated keys. Semantic
workflows use pinned 7.14 mapping data; the tool does not invoke MBINCompiler or another save
editor.

Invoke every command through the repository dispatcher with a task tranche:

```bash
tooling/squinch tranche create example-save-edit
tooling/squinch --tranche example-save-edit nms-save --help
```

All command results use the repository's versioned JSON envelope. Errors are JSON on stderr and
return nonzero.

## Validated compatibility ceiling

The compatibility statement is deliberately “up to 7.14.” Current-game profiles retain snapshots
written with older on-disk revisions. Inspection, staging, and application accept the observed PC
families through this ceiling:

- a positive decoded root `F2P` save-format identity;
- encrypted metadata formats `2003` and `2004`;
- metadata base versions `4135` through `4234`; and
- `save.hg` through `save20.hg`, paired with the corresponding `mf_save*.hg`.

A metadata base version above `4234` fails closed until the next game version is investigated,
tested, and the ceiling is explicitly raised. Semantic commands always require mapping data whose
`libMBIN_version` is exactly `7.14.0.1`.

The data file is compact Latin-1 JSON plus one NUL terminator, encoded as independent 512 KiB raw
LZ4 blocks with 16-byte NMS headers. The companion is decrypted and re-encrypted with the storage
slot derived from its filename. Staging preserves the existing metadata length, format, base
version, slot key, and historical size-field convention; it changes only required size fields and
the timestamp. That keeps game-build identity and unknown fields intact.

## Read-only workflow

List every Auto/Manual pair in the single detected Proton profile:

```bash
tooling/squinch --tranche example-save-edit nms-save list
```

Pass `--directory <profile>` when auto-detection is ambiguous. `list` reports future, unsupported,
or malformed files without hiding entries inside the validated range.

Validate one pair, query an RFC 6901 pointer, search keys/scalar values, or compare trees:

```bash
tooling/squinch --tranche example-save-edit nms-save inspect /path/to/save.hg
tooling/squinch --tranche example-save-edit nms-save get /path/to/save.hg '/pointer/to/value'
tooling/squinch --tranche example-save-edit nms-save find /path/to/save.hg --key 'pattern'
tooling/squinch --tranche example-save-edit nms-save find /path/to/save.hg --value 'pattern'
tooling/squinch --tranche example-save-edit nms-save diff /path/to/save.hg /path/to/save2.hg
```

`find` and `diff` are bounded by `--limit`. JSON Pointer escaping follows RFC 6901: `~1` means `/`
and `~0` means `~`.

Export writes the exact decoded JSON bytes without changing numeric spellings:

```bash
tooling/squinch --tranche example-save-edit nms-save export /path/to/save.hg \
  --output .squinch/scratch/tranches/example-save-edit/inputs/save.json
```

It refuses to overwrite an existing export.

## Semantic cross-save inventory

Acquire the exact pinned mapping inside the tranche, or verify an existing copy:

```bash
tooling/squinch --tranche example-save-edit nms-save mapping-acquire \
  --output .squinch/scratch/tranches/example-save-edit/inputs/mapping-7.14.json
tooling/squinch --tranche example-save-edit nms-save mapping-verify \
  .squinch/scratch/tranches/example-save-edit/inputs/mapping-7.14.json
```

Inventory Auto/Manual snapshots:

```bash
tooling/squinch --tranche example-save-edit nms-save inventory \
  --directory /path/to/st_profile \
  --mapping /path/inside/tranche/mapping.json \
  --output-directory /path/inside/tranche/outputs/inventory
```

`saves.json` records payload and metadata names, logical slots, contexts, source hashes, and
galaxy-range status. `bases.json`, `starships.json`, and `multitools.json` combine complete semantic
records with every source occurrence and select the newest revision. `report.json` summarizes
deduplication, range violations, inconsistent Auto/Manual pairs, special single-galaxy saves, and
non-galaxy-centric saves. `slot-diffs.json` compares identities and changed revisions per
Auto/Manual pair. `identity-audit.json` exposes lower-confidence identities and fixed-base location
collisions. `--cached include` adds a separate `cached-bases.json`; cached records are never mixed
with owned bases.

Use `--snapshots all|auto|manual|newest`, `--archives include|exclude|only`, and
`--cached summary|include` to select the evidence set. Query focused evidence without loading the
large entity artifacts into a caller:

```bash
tooling/squinch --tranche example-save-edit nms-save slot-diff \
  --inventory-directory /path/to/inventory --slot 6
tooling/squinch --tranche example-save-edit nms-save identity-audit \
  --inventory-directory /path/to/inventory
```

Base identity primarily uses the player owner ID, base creation timestamp, and base type. This
survives renames and object updates while keeping multiple bases on one planet distinct. A
location-and-position hash is the explicit lower-confidence fallback. Fixed player bases are checked
against ranges expressed by names such as `Galaxies 1-50`; freighter and ship bases are portable and
exempt. Cached external/friend/civilian/generated bases are counted by type but never mixed into the
owned-base collection. Active and nonempty archived starships and multitools are both included. The
command is read-only, pins source and mapping hashes, writes only inside the selected tranche, and
refuses to overwrite an existing output directory.

### Persistent entity library

Publish combined inventory artifacts to persistent local storage when they need to outlive a task
tranche:

```bash
tooling/squinch --tranche example-save-edit nms-save library-publish \
  --inventory-directory /path/inside/tranche/outputs/inventory \
  --output-directory games/no-mans-sky/local/save-library --replace
```

The destination must be below `games/no-mans-sky/local/`, which is ignored by Git and is not removed
by tranche cleanup. The published directory contains `bases.json`, `starships.json`,
`multitools.json`, and a manifest pinning their source hashes and counts. If an authoritative
`systems.json` has already been published, `--replace` preserves it. `--replace` atomically archives
the prior publication before installing the new one.

### Configurable save-name policy

Pass `--policy <json>` to inventory, projection, or finalization to replace the built-in galaxy-name
rules. A policy declares owned/portable base types and non-overlapping regular-expression rules. A
rule can use a fixed range (`"galaxies": [1, 50]`) or capture a dynamic range
(`"galaxy_groups": [1, 2]`). The schema identity is `squinch-nms-save-policy-v1`. Ambiguous rules,
invalid ranges, duplicate types, and portable types outside the owned set fail closed.

## Reviewed semantic projection

Projection turns a semantic inventory into ordinary raw RFC 6902 patches without changing a save.
`prune` proposes only out-of-policy removals. `reconcile` also proposes canonical revision updates
and imports every combined fixed base belonging to the target range while preserving cached and
portable records.

```bash
tooling/squinch --tranche example-save-edit nms-save projection-plan \
  --inventory-directory /path/to/inventory \
  --mapping /path/to/mapping-7.14.json \
  --strategy reconcile --snapshots all \
  --output /path/inside/tranche/reconcile-plan.json
```

The plan lists every removal, update, and import by stable identity, name, galaxy, and revision
hash. It pins the source pair, inventory artifacts, mapping, policy, context, and selection. It is
created with `"approved": false`. Review or remove individual actions, then create a separately
hashed approved copy through an explicit transition:

```bash
tooling/squinch --tranche example-save-edit nms-save projection-approve \
  --plan /path/inside/tranche/reconcile-plan.json \
  --output /path/inside/tranche/reconcile-plan-approved.json --approve
```

Emit patches only from that approved copy:

```bash
tooling/squinch --tranche example-save-edit nms-save projection-emit \
  --plan /path/inside/tranche/reconcile-plan-approved.json \
  --output-directory /path/inside/tranche/projected-patches
```

Emission refuses an unapproved plan or any changed source, metadata, inventory, mapping, policy,
entity revision, or target array. Each generated patch begins with a full-array `test`, is applied
in memory for self-verification, and remains inert until passed separately to `stage`.

## Galaxy-save finalization

`finalize-layout` emits one inert patch per galaxy-classified snapshot for the common final cleanup:

```bash
tooling/squinch --tranche example-save-edit nms-save finalize-layout \
  --directory /path/to/st_profile \
  --mapping /path/inside/tranche/mapping-7.14.json \
  --target-slot 5 --target-slot 6 \
  --output-directory /path/inside/tranche/outputs/finalization
```

It finds the player's canonical settlements across the profile and routes each one only to save
ranges containing its galaxy. Settlements are prefixed with their numeric galaxy and reserve the
first number in that galaxy. Fixed owned bases are then named and ordered by actual numeric galaxy,
with additional bases using `.1`, `.2`, and so on. Freighter and ship bases remain portable;
external, friend, civilian, and generated cache records are preserved after owned records. The
command also replaces `TeleportEndpoints` with an empty array. It does not remove ordinary galaxy
waypoints. Omit `--target-slot` to finalize every galaxy-classified save pair.

Every changed array is guarded by an exact RFC 6902 `test`. The output manifest pins all source,
metadata, mapping, policy, and patch hashes and lists each rename, settlement route, and removed
endpoint count. The command changes no live file: stage and verify every emitted patch, then install
the stages together with `apply-batch`.

## Selective synchronization and composition

`sync-plan` copies selected state from one slot to any number of existing slots. For example, copy
everything from slot 1 except bases, starships, and multitools into slots 2 through 4:

```bash
tooling/squinch --tranche example-save-edit nms-save sync-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --source-slot 1 --target-slot 2 --target-slot 3 --target-slot 4 \
  --include-group everything --exclude-group bases --exclude-group starships \
  --exclude-group multitools \
  --output-directory /path/inside/tranche/outputs/sync-plan
```

Groups are `player`, `common`, `discoveries`, `bases`, `freighter-base`, `starships`, `freighter`,
`frigates`, `squadron`, `multitools`, and `inventories`; `everything` selects their union.
`starships` selects starships only. Freighters, frigates, and squadrons are independently
selectable. `freighter-base` replaces only the `FreighterBase` record and preserves every other
base; `bases` selects complete base state. Repeat `--include-field` or `--exclude-field` for exact
semantic top-level fields. Exclusions win. Target save names and universal IDs are always retained,
and Auto and Manual snapshots are matched independently. The command emits guarded patches and
changes no live file; use the ordinary stage, verification, and atomic batch-apply workflow.

`merge-plan` composes multiple sources. Noncollection fields come from `--template-slot`, while
bases, starships, and multitools are unioned by stable identity and newer base revisions win:

```bash
tooling/squinch --tranche example-save-edit nms-save merge-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --source-slot 1 --source-slot 2 --template-slot 1 --target-slot 1 \
  --include-group everything \
  --output-directory /path/inside/tranche/outputs/merge-plan
```

Capacity overflow fails by default. `--capacity-policy template` instead keeps the template's
bounded collection and records every skipped identity in the manifest. To merge into a new save,
first clone a template into an empty slot, then target that slot with `merge-plan`.

`clone-slot` creates a new Auto/Manual pair in an empty slot, assigns a new universal save ID,
rekeys its metadata, and can clear entity ownership while retaining the rest of the template:

```bash
tooling/squinch --tranche example-save-edit nms-save clone-slot \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --source-slot 1 --destination-slot 7 --name 'Dev Testing' \
  --clear-group bases --clear-group starships --clear-group multitools --apply
```

Clone evidence and the original source hashes are retained in the selected tranche. The command
refuses an occupied destination, a running game, a changed source, or an invalid resulting pair.

## Inventory, standing, teleport, and discovery cleanup

`cleanup-plan` emits guarded patches for batch cleanup without changing a live save. Inventory
groups are independently selectable: `exosuit`, `starships`, `freighter`, and `exocraft`. Clearing
one empties its general and cargo `Slots` arrays while preserving every `Inventory_TechOnly` object,
inventory dimensions, class, capacity, and special-slot layout. Race-standing cleanup sets the Gek,
Korvax, Vy'keen, and Autophage standing statistics to zero.

```bash
tooling/squinch --tranche example-save-edit nms-save cleanup-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 2 --target-slot 3 \
  --clear-inventory exosuit --clear-inventory starships \
  --clear-inventory freighter --clear-inventory exocraft \
  --reset-race-standing \
  --output-directory /path/inside/tranche/outputs/inventory-cleanup
```

Discovery cleanup edits `DiscoveryData-v1`'s stored, available, and enqueued records together with
the fixed-capacity `VisitedSystems` history. First use `discovery-list` to obtain canonical system
addresses and see each system's decoded galaxy, custom names, current-system status, visited-history
status, and record counts. Its union includes stored, available, enqueued, and history-only systems
so targeted cleanup does not hide orphaned entries:

```bash
tooling/squinch --tranche example-save-edit nms-save discovery-list \
  /path/to/save3.hg --mapping /path/to/mapping-7.14.json
```

The discovery operation can `clear` every system, `retain` only selected systems, `remove` selected
systems, `prune-range`, or `purge-removed`. The last operation permanently deletes every complete
system discovery subtree whose SolarSystem record carries the game's removed/hidden flag, plus any
matching queue and visited-history references. Repeat `--discovery-system` for targeted edits;
decimal and `0x`-prefixed addresses are accepted. `--current-system` selects the snapshot's current
system. An optional `--expected-discovery-name` guard refuses to emit a patch unless the selected
discovery tree contains that custom name.

```bash
# Retain only the current system and its complete discovery tree.
tooling/squinch --tranche example-save-edit nms-save cleanup-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 2 --clear-teleports \
  --discovery-operation retain --current-system \
  --expected-discovery-name 'Apam Woods' \
  --output-directory /path/inside/tranche/outputs/retain-current

# Remove every discovery/history entry outside each save name's galaxy range.
tooling/squinch --tranche example-save-edit nms-save cleanup-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 2 --target-slot 3 --target-slot 4 \
  --discovery-operation prune-range \
  --output-directory /path/inside/tranche/outputs/prune-discoveries

# Permanently purge systems listed under Removed Systems in the discovery UI.
tooling/squinch --tranche example-save-edit nms-save cleanup-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 6 --discovery-operation purge-removed \
  --output-directory /path/inside/tranche/outputs/purge-removed
```

`prune-range` derives its inclusive galaxy range from the configured save-name policy and fails
closed for a non-galaxy-centric name. Galaxy identity is decoded from each system address's reality
index. As with projection and synchronization, the output is inert until every patch is staged,
verified, and installed with `apply-batch`.

### Deduplicated discovery redistribution

`discovery-redistribute-plan` combines the stored, available, enqueued, and visited-history systems
from complete galaxy save pairs, deduplicates discovery identities, selects the newest conflicting
record by discovery timestamp, and routes every system to one logical save. Auto and Manual receive
the same routed authority. If named ranges overlap, the narrowest range owns that galaxy; equally
specific overlaps fail closed.

```bash
tooling/squinch --tranche example-save-edit nms-save discovery-redistribute-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 1 --target-slot 2 --target-slot 3 \
  --target-slot 4 --target-slot 5 --target-slot 6 \
  --name-override '5=Galaxies 201-255' \
  --output-directory /path/inside/tranche/outputs/discovery-routing
```

The output includes guarded per-snapshot patches, a routing manifest, and a complete semantic
`systems.json` with provenance and selected revisions. A `SLOT=NAME` override both classifies and
renames the payload; pass the same manifest value to `stage --metadata-save-name` so the companion
menu name changes transactionally.

Publish the authority beside the other persistent entities without replacing them:

```bash
tooling/squinch --tranche example-save-edit nms-save library-publish-systems \
  --systems /path/inside/tranche/outputs/discovery-routing/systems.json \
  --output-directory games/no-mans-sky/local/save-library
```

### Operational location rehoming

`location-rehome-plan` finds operational player locations outside each galaxy-classified save's
inclusive range and points them at the first galaxy in that range. It changes only the address's
`RealityIndex`; voxel, system, planet, and local position data remain unchanged. The selectable
groups are `player` (`UniverseAddress`), `previous` (`PreviousUniverseAddress`), and `freighter`
(`FreighterUniverseAddress`). Historical and special-purpose locations such as grave, Atlas, Nexus,
portal-return, game-start, and fleet-expedition addresses are intentionally outside this operation.

```bash
tooling/squinch --tranche example-save-edit nms-save location-rehome-plan \
  --directory /path/to/st_profile --mapping /path/to/mapping-7.14.json \
  --target-slot 1 --target-slot 2 --target-slot 3 \
  --location player --location previous --location freighter \
  --output-directory /path/inside/tranche/outputs/location-rehome
```

The command emits guarded per-snapshot patches and a manifest without changing live saves. A slot
whose selected locations are already in range receives an empty patch. Stage and verify non-empty
patches, then install them together with `apply-batch`.

## Transactional editing

Author an RFC 6902 patch in the tranche. Use `test` operations to make assumptions explicit before
changes:

```json
[
  { "op": "test", "path": "/raw/path", "value": 10 },
  { "op": "replace", "path": "/raw/path", "value": 20 }
]
```

`add`, `remove`, `replace`, `test`, `copy`, and `move` are supported. A failing operation leaves the
source untouched. Stage and revalidate the resulting pair:

```bash
tooling/squinch --tranche example-save-edit nms-save stage /path/to/save.hg \
  --patch .squinch/scratch/tranches/example-save-edit/inputs/change.json

tooling/squinch --tranche example-save-edit nms-save verify-stage \
  .squinch/scratch/tranches/example-save-edit/no-mans-sky/save-edit/stages/<stage>
```

`stage` never writes to the source directory. Its manifest pins the source pair, patch, staged pair,
sizes, and format identity by hash. Re-run it if either source file changes.
`--metadata-save-name <name>` updates the companion metadata display name in the staged pair; use it
with a guarded payload-name patch when renaming a logical save.

After reviewing the staged diff and with NMS stopped, apply it explicitly:

```bash
tooling/squinch --tranche example-save-edit nms-save apply \
  .squinch/scratch/tranches/example-save-edit/no-mans-sky/save-edit/stages/<stage> \
  --apply
```

Apply refuses to proceed if `NMS.exe` is running, the source pair is missing or symlinked, source
hashes changed, staged artifacts fail validation, or `--apply` is absent. It copies and verifies
both originals into the tranche before replacement, preserves file modes, fsyncs replacements, and
checks installed hashes. If replacement fails partway through, it attempts rollback from that
backup. The returned backup path is the recovery authority.

For a reviewed multi-save projection, use `apply-batch <stage>... --apply`. It verifies every stage
and source first, copies and hash-checks every original pair into one batch backup before replacing
anything, and rolls back every replaced file if any replacement or post-apply hash check fails.

`archive-slots --slot <n>... --apply` recoverably removes complete logical Auto/Manual slots. It
copies and hash-verifies all data/metadata pairs and a manifest inside the tranche before deleting
any live file, then restores missing files from the archive if removal fails partway through.

`swap-slots --slot-a <n> --slot-b <n> --apply` transactionally exchanges two complete logical slots.
Both Auto and Manual snapshots move together. Because the companion metadata encryption key depends
on the destination filename, the command decrypts and re-encrypts metadata for each new storage slot
instead of merely renaming files. It verifies all four source pairs, creates and hashes a complete
rollback backup, installs through atomic replacements, validates the destination keys and save
payloads, and rolls back every replaced file if any step fails.

`move-slot --source-slot <n> --destination-slot <n> --apply` moves a complete Auto/Manual slot into
an empty destination. It applies the same metadata re-keying, backup, atomic-install, verification,
and rollback rules, then removes the source pair only after both destination snapshots validate.

The tool does not launch the game, choose a menu row, edit account data, update cloud state, or
invent semantics outside the pinned mapping. Keep semantic edits narrow and verify them in a
disposable or backed-up save workflow.
