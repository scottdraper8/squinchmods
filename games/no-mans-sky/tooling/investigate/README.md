# No Man's Sky investigation runner

`tooling/squinch nms-investigate` turns NMS asset and loose-mod inspection into reproducible,
machine-readable runs. It is intentionally an extraction and overlay tool, not a Minecraft-style
build-server wrapper: NMS exposes HGPAK assets, MBIN templates, EXML overlays, loose resources, and
an executable boundary rather than public loader mappings and a headless dedicated-server API.

## Evidence and ownership

Every evidence-bearing command creates a unique run below the ignored
`games/no-mans-sky/investigation-state/runs/<run-id>/` tree. `request.json` records normalized
inputs; `result.json` uses `schemas/cli-output-v1.json`; intermediate inventories, extracted inputs,
compiler products, hashes, and bounded diffs stay beside them. Runs are never silently reused.

The committed `toolchain.toml` targets public Cosmos 7.03.1, Steam build `25351301`, and pins
HGPAKtool `1.1.3` plus the latest published MBINCompiler release (`v7.02.0-pre2`) by URL and
SHA-256. HGPAKtool and its distributions are hash-locked in `uv.lock`. On this Linux host
MBINCompiler runs in a network-disabled .NET 8 container when a matching host runtime is absent.
Every result records the actual backend image ID and repo digest. The container reference itself is
digest-pinned, and the Windows asset compression mode is always explicit. `[target]` binds that
compiler to the validated public NMS version and Steam build IDs. Current-game checks that invoke
the compiler stop with `unsupported_game_build` after an update until the pin is reviewed; archive
inventory/extraction remains available for investigating the new build.

Investigation states mean:

- `succeeded`: the command's declared static or deterministic assertion passed;
- `failed`: a complete check disproved the assertion or found a hard incompatibility;
- `inconclusive`: bounded evidence found a possible overlap that needs a stronger oracle;
- `degraded`: host or owned state makes some evidence invalid;
- `staged`/`inactive`: an exact controlled deployment is present/absent; and
- `error`: the check itself could not complete.

A static `analyze-mod` success never claims runtime compatibility. Its result states
`runtime_compatibility_proven: false` explicitly.

## Bootstrap and health

```bash
tooling/squinch nms-investigate toolchain sync
tooling/squinch nms-investigate doctor
```

`doctor` discovers the Steam installation, build ID, archive snapshot, loader state, NMS processes,
and toolchain. It also identifies uninterruptible processes without invoking `ps` or reading every
process command line. When the host is degraded, it omits the expensive executable hash and labels
performance evidence invalid.

## Static and deterministic commands

Inventory or extract exact logical paths. Extraction rejects missing and multiply-owned paths and
hashes both the selected archive and output:

```bash
tooling/squinch nms-investigate inventory --json
tooling/squinch nms-investigate extract \
  --path UI/COMPONENTS/PAGESELECTBAR.MBIN
```

Prove the current compiler can preserve an MBIN semantically:

```bash
tooling/squinch nms-investigate roundtrip \
  --path UI/COMPONENTS/PAGESELECTBAR.MBIN
```

The round trip is MBIN → MXML → rebuilt MBIN → MXML. Binary hashes are retained, but pass/fail uses
the normalized XML object because compiler headers and serialization can make byte equality the
wrong contract.

Analyze a safely unpacked deployment root against the current game:

```bash
tooling/squinch nms-investigate analyze-mod --mod-root /exact/mod/root
tooling/squinch nms-investigate conflicts \
  --mod-root /exact/first/root --mod-root /exact/second/root
```

Analysis inventories and hashes runtime files, maps EXML to current MBIN targets, parses the AMUMSS
annotation dialect, compares templates and touched paths, decompiles full/custom MBINs, and compares
full replacements to current vanilla layouts. File-like XML references must resolve in the current
archives or the mod itself. A path absent from one current vanilla object is a warning—not a
fabricated schema failure—because an object instance cannot prove a generated template's complete
field space. Use a merged export for that gate. Conflicts are confirmed for full replacements and
matching explicit or directly inferred identifiers; ambiguous unselected list writes are reported as
potential and make the result inconclusive.

Compare XML or validate a merged export:

```bash
tooling/squinch nms-investigate compare \
  --left before.MXML --right after.MXML --expect different
tooling/squinch nms-investigate verify-export \
  --patch authored.EXML --exported merged.MXML --vanilla vanilla.MXML
```

`verify-export` proves intended leaf name/value presence (and removal absence) and optionally
retains the complete bounded vanilla/export semantic diff. It does not claim gameplay behavior or
complete absence of unintended changes.

Retain executable-level string evidence with byte offsets and an exact executable hash:

```bash
tooling/squinch nms-investigate exe-strings \
  --pattern PAGESELECTBAR --pattern FrontendPage
```

This is static evidence, not a decompiler and not proof that a callable hook seam exists. By default
every requested pattern must match at least once; `--allow-missing-patterns` makes an absence
exploratory instead of a failed assertion.

Retain selected files and bounded symbol matches from an exact clean Git source checkout:

```bash
tooling/squinch nms-investigate source-snapshot \
  --repository /exact/source/checkout \
  --expect-revision <full-commit-id> \
  --expect-origin https://github.com/example/project.git \
  --file README.md --file src/relevant.py \
  --pattern 'RelevantType|RelevantFunction'
```

The command is read-only. It requires the exact worktree root, rejects dirty trees by default,
requires selected files to be tracked regular files, records Git identity, the local upstream ref
and ahead/behind state when configured, and per-file hashes, and copies only those files into the
ignored run. It does not fetch or acquire source, prove that a local remote-tracking ref is still
current on the network, execute project code, or turn a mapped symbol into runtime evidence.

Verify named NMS.py-style byte signatures against the exact installed executable:

```bash
tooling/squinch nms-investigate exe-patterns \
  --catalog /exact/NMS.py/tools/data.json \
  --name 'cGcSolarSystemQuery::Run' \
  --name 'cGcScanEventManager::PassesPlanetInfoChecks' \
  --disassemble-bytes 4096
```

The scanner accepts whole-byte hexadecimal tokens and `?`/`??` wildcards, records the executable and
catalog hashes, retains the selected catalog, validates the PE headers, maps every match to its
section, relative virtual address, and preferred virtual address, and requires exactly one match per
selected signature. `--allow-nonunique` is available for exploratory evidence. A unique byte match
supports function location for that executable; it does not prove the signature, calling convention,
object layout, call safety, loaded address after relocation, or semantics. `--disassemble-bytes`
additionally retains a bounded Intel-syntax `objdump` range from every unique preferred virtual
address and records the disassembler identity. The requested byte range can cross a function
boundary; function limits and call-target identities remain analysis conclusions rather than
properties asserted by the tool.

Retain function-level evidence once current-executable addresses have been established:

```bash
tooling/squinch nms-investigate exe-functions \
  --address 0x140A27240 --address 0x1405AFDC0 \
  --vtable 0x144A82F88 --vtable-count 36 \
  --memory-displacement 0x3BF0
```

The command obtains x64 unwind-fragment bounds from the executable's `.pdata`, follows direct
conditional and unconditional branches into other bounded fragments, and decodes the reachable chain
with the pinned iced-x86 library. It retains disassembly, direct calls, RIP-relative memory
references, the exact executable hash, and optional vtable entries. `--include-callers` performs the
more expensive full-`.text` scan for direct calls to any retained fragment. This is a reproducible
static control-flow view, not proof of C++ function ownership, a function's name or semantics,
virtual dispatch, runtime reachability, or execution.

Repeatable `--memory-displacement` values scan `.text` for base/index memory operands using an exact
structure offset and retain the containing unwind-fragment bounds. This is useful for locating
candidate readers and writers of a recovered field. It deliberately excludes RIP-relative globals,
and an offset match alone does not prove that two base registers have the same concrete type.

Build the disposable native-resolver vertical slice from the exact current Wiki mission table:

```bash
tooling/squinch nms-investigate native-search-probe
```

The command extracts the current Wiki, Wiki mission table, and NPC mission table. It clones the
current `WIKI_TRADE5` mission into a uniquely named one-profile Guide probe and requires the current
`SE_PHOTO_BIOME_LUSH` event to retain its `PlanetSearch`/`Any`/no-building contract. It separately
requires at least one current mission to retain the bounded `Near`, `ForceWideRandom=false`, and
`MustFindSystem=false` location policy before composing those current contracts into a nearby
Lush-biome query. It emits the loose mod inside the ignored run, analyzes it against current assets,
and compiles/decompiles the generated four-file adapter as a structural check. It does not stage or
run the mod. The generated mission intentionally has no quick-warp stage; primary and fallback
predicates are identical so a fallback cannot silently weaken the result. The new composition still
requires merged-export and runtime proof.

## Declarative scenarios

Run a committed TOML workflow:

```bash
tooling/squinch nms-investigate scenario \
  games/no-mans-sky/investigations/scenarios/current-ui-assets.toml
```

Scenario schema version 1 requires a kebab-case `id` and one or more unique `[[steps]]`. Supported
operations are `extract`, `roundtrip`, `analyze-mod`, `conflicts`, `compare`, `verify-export`, and
`exe-strings`. Each step defaults to `expect = "succeeded"`; expected negative controls can declare
`failed`, `inconclusive`, or `error`. Relative filesystem inputs resolve beside the scenario file.
`fail_fast` defaults to true. A scenario succeeds only if every step ran and reached its expected
state.

The scenario envelope is deliberately compact. Each step is retained at
`steps/<step-id>/result.json`; mod and conflict steps link normalized analysis reports and exact
touched-path records under that step instead of duplicating them into terminal output.

## Controlled staging

`stage` is dry-run by default. `--apply` copies one validated deployment root to the unique
`GAMEDATA/MODS/SQUINCH_INVESTIGATION_<run-id>` directory only while NMS is stopped. It neither
launches the game nor edits `GCMODSETTINGS.MXML`, `DISABLEMODS.TXT`, saves, or another mod.

```bash
tooling/squinch nms-investigate stage --mod-root /exact/mod/root
tooling/squinch nms-investigate stage --mod-root /exact/mod/root --apply
tooling/squinch nms-investigate stage-status --run <run-id>
tooling/squinch nms-investigate collect --run <run-id> --screenshot result.png
tooling/squinch nms-investigate unstage --run <run-id> --apply
```

The external stage manifest records every deployed hash and the preparation state before files are
atomically moved into `MODS`; interrupted copies remain outside the active mod tree and can be
removed with `unstage --apply`. That command refuses modified, missing, extra, symlinked,
running-game, or incorrectly named active targets. After NMS is stopped, `collect` copies and hashes
available `FullLog.txt`, `GCMODSETTINGS.MXML`, `MODS/EXPORTED` content, and explicit screenshots
into a timestamped run-owned snapshot. Remove run evidence only after unstaging:

```bash
tooling/squinch nms-investigate clean --run <run-id>
tooling/squinch nms-investigate clean --run <run-id> --apply
```

## Deliberate runtime boundary

The investigation command does not launch Steam/Proton, select a personal save, toggle game-owned
settings, inject a Windows hook, or pronounce a visual result. Runtime injection is a separately
bounded product path under [`../runtime/`](../runtime/README.md), with its own executable identity,
threading, lifecycle, and save-isolation gates. Static staging conclusions remain limited to the
data path: use a backed-up save, collect `FullLog.txt` and `MODS/EXPORTED`, and retain any required
human/visual observation beside the run.
