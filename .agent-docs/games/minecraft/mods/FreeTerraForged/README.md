# FreeTerraForged Documentation

Documentation for the `games/minecraft/mods/FreeTerraForged` submodule lives here so engineering
reference, active planning, and local branch state do not need to be committed to an upstream-facing
code branch.

## Where to read

- [Repository `AGENTS.md`](../../../../../AGENTS.md) — concise rules shared across repository tasks.
- [`agent-resume.md`](../../../../../agent-resume.md) — concise routing, accepted state, and current
  integration boundary. It points to authoritative documents and retained evidence rather than
  preserving a session history.
- [FreeTerraForged wiki](../../../../../games/minecraft/mods/FreeTerraForged.wiki/Home.md) —
  engineering concepts and preset-editor setting guides.
- [`Compatibility-runtime acceptance`](refs/compatibility-runtime-acceptance.md) — the implemented
  runtime, accepted verification surface, and current production-artifact state.
- [`Minecraft reference`](../../wiki/README.md) — general Minecraft world-generation reference for
  reusable engine concepts such as extended height, placed features, structures, and biome climate.
- [`plans/`](plans/) — current product contracts and genuinely unfinished implementation work.
  Completed investigation narratives do not remain here.
- [`refs/branch-map.md`](refs/branch-map.md) — current local FTF branch/worktree state.

## FTF work workflow

For FTF source changes, compatibility investigations, and runtime evidence, start with the
repository's `agent-resume.md`, then read the linked canonical plan and acceptance record before
choosing implementation work.

- Use a clean worktree based on the live `upstream/1.21.1` tip for new evidence or implementation.
- Use `tooling/squinch mc-investigate` and repository-relative scenarios. Follow the
  [Minecraft agentic development guide](../../agentic-development-guide.md) and retain exact run IDs
  and artifacts.
- Before collecting wall-clock, allocation, RSS, JFR, startup, shutdown, or cleanup evidence, verify
  host health and confirm no prior investigation-owned JVM remains in uninterruptible teardown.
  Label evidence from a degraded host as invalid and rerun affected comparisons after recovery.
- Acquire and validate third-party jars and sources through `tooling/squinch third-party minecraft`.
  The catalog is `.squinch/games/minecraft/third-party/artifacts.toml`.
- Before a primary compatibility conclusion, verify the live latest release supporting the
  scenario's exact Minecraft version and loader under the acquisition pipeline's release-channel
  policy. If it changes, reacquire it and rerun affected behavior-bearing scenarios. Older artifacts
  are only labeled fallback, regression, or failure-boundary controls.
- Follow the evidence ladder: source and bytecode, deterministic probes, generated tiles or chunks,
  then client or visual QA only when lower layers cannot answer the question.
- Continue safe, in-scope artifact acquisition, probe construction, and information gathering
  autonomously. Use available evidence to resolve questions; stop compatibility investigation only
  at the implementation boundary or a demonstrated impossibility.

## Compatibility architecture

- FTF is pre-release, so replace unsound compatibility-runtime internals in place. Preserve
  compatibility for previously valid preset inputs; internal Java APIs, implementation classes,
  caches, plan representations, Mixins, and historical pre-release runtime behavior are not
  compatibility contracts.
- Treat preview, biome selection, spatial ownership, climate sampling, surface rules, density,
  placed features, and diagnostics as separate domains until evidence proves a shared contract.
- Treat the compatibility runtime as an ETL boundary: discover and extract stable worldgen inputs,
  validate and normalize them into immutable FTF-owned containers and typed plans, then let FTF own
  selection, spatial, ordering, and execution policy. TerraBlender, Lithostitched, Biolith, loader
  APIs, and vanilla or datapack registries are peer input mechanisms, not runtime authorities.
- Keep preview, generation, diagnostics, and other downstream consumers zero-knowledge. They consume
  immutable FTF plans and results, never third-party registries, providers, callbacks, samplers, or
  mod-specific failure terms.
- Prefer registries, resources, codecs, and stable public snapshots or query/factory contracts. If a
  mechanism lacks a complete snapshot, contain any necessary version-qualified bridge behind that
  mechanism's runtime provider and establish completeness, ordering, lifecycle, reload, and
  concurrency. Never infer semantics from private fields, replay registration events, or maintain
  brittle per-mod Mixins. Keep unsupported facets explicit until a sound seam exists.
- Do not equate the absence of a public finalized snapshot with proof that request-owned resolution
  is impossible. Inspect the mechanism's finalizer and current upstream consumers for an isolated
  pre-server path. Manual finalization or callback replay proves feasibility, not a production
  contract; establish purity, repeatability, ownership, reload, ordering, and concurrency. Keep any
  proven resolver inside runtime acquisition.
- Treat named third-party mods as a falsification and coverage corpus, never an allowlist or an
  architecture target. An unseen mod using a supported mechanism must work without code changes;
  unsupported mechanisms need bounded, actionable diagnostics without corrupting supported domains.
  Absence from the corpus does not imply unsupported, and passing only the named corpus is
  insufficient.
- Do not implement a production compatibility fix until the canonical plan's feasibility,
  extraction-completeness, ownership, ordering, reload, parity, failure, lifecycle, and cross-domain
  acceptance gates are supported by current-tip evidence.
- Maintain one complete dependency-ordered compatibility plan and execute one coherent vertical
  workstream at a time. Complete it only after obsolete paths are removed and source, deterministic
  probes, loader coverage, reload/concurrency, failure boundaries, and production packaging gates
  pass. Advance shared evidence infrastructure only when needed for the active workstream.
- Never use a personal Minecraft launcher profile.

## Documentation boundaries

The FTF wiki explains current FTF-specific engineering behavior. General Minecraft pages explain
reusable engine behavior. Plans contain current product contracts, unresolved decisions, and
acceptance boundaries only.

The root `AGENTS.md` contains repository-wide guidance. This README routes FTF work to its current
plan, acceptance record, and workflow above. `agent-resume.md` is a current-state router. If either
begins carrying run-by-run history or detailed conclusions, move that material to retained artifacts
or the active plan and restore the document to its stated role.

Retrospectives, session timelines, branch archaeology, feature summaries, QA records, and evidence
dumps are outside the wiki's scope. Reusable technical knowledge appears in concept pages;
feature-specific work appears in plans or PR descriptions.
