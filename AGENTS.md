# Repository operating rules

## Priorities

- Establish the truth from current source and reproducible runtime evidence. Correctness and
  completeness outrank speed, convenience, or agreement with a requested conclusion.
- Elapsed time is not a completion metric. Within the authorized scope, continue through
  investigation, implementation, and validation until every acceptance gate is satisfied or a
  concrete external blocker makes further safe progress impossible. Do not stop at a plausible
  diagnosis, partial implementation, green unit test, or intermediate milestone.
- Prefer the smallest _correct_ design, not the quickest patch. A substantial refactor is acceptable
  when the existing ownership or lifecycle model cannot support a sound result.
- Do not preserve, wrap, or layer new abstractions over an unsound internal design merely to reduce
  the diff. FreeTerraForged is pre-release and its compatibility-runtime internals may be replaced
  in place, with obsolete paths and tests removed. Preserve backward compatibility for previously
  valid preset inputs; internal Java APIs, implementation classes, caches, plan representations,
  Mixins, and historical pre-release runtime behavior are not compatibility contracts.
- Do not write changelog-style narratives. Keep documentation current-state and forward-facing;
  retain raw run artifacts and calculations as evidence instead.
- Continue safe, in-scope acquisition, probe construction, and information gathering autonomously;
  do not pause for clarification while more evidence can resolve the question. Stop compatibility
  investigation only at the actual implementation boundary or a demonstrated impossibility.
- Preserve unrelated dirty work and never use a personal Minecraft launcher profile.

## FreeTerraForged work

- Start with `agent-resume.md`, then read the task's linked canonical plan completely. Live Git,
  worktree, dependency, and runtime state supersede stale prose.
- Use a clean worktree based on the live `upstream/1.21.1` tip for new evidence or implementation.
- Use `tooling/squinch mc-investigate` and repository-relative scenarios. Follow
  `.agent-docs/games/minecraft/agentic-development-guide.md` and retain exact run IDs/artifacts.
- Before using wall-clock, allocation, RSS, JFR, startup, shutdown, or cleanup evidence, verify that
  the host is healthy and that no prior investigation-owned JVM remains in uninterruptible teardown.
  Treat measurements from a degraded host as invalid, retain them only as labeled failure artifacts,
  and rerun the affected comparison after host recovery.
- Acquire and validate third-party jars and sources through `tooling/squinch third-party`; the
  catalog is `.squinch/games/minecraft/third-party/artifacts.toml`.
- Before drawing a primary compatibility conclusion, verify against the live latest release that
  supports the scenario's exact Minecraft version and loader under the acquisition pipeline's
  release-channel policy. If that release changes, reacquire it through the catalog and rerun every
  affected behavior-bearing scenario. Older artifacts are permitted only as explicitly labeled
  fallback, regression, or failure-boundary controls; they never substitute for the latest result.
- Follow the evidence ladder: source/bytecode, deterministic probes, generated tiles or chunks, then
  client/visual QA only when lower layers cannot answer the question.
- Treat preview, biome selection, spatial ownership, climate sampling, surface rules, density,
  placed features, and diagnostics as separate compatibility domains until evidence proves a shared
  contract.
- Treat the compatibility runtime as an ETL boundary: discover and extract stable worldgen inputs,
  validate and normalize them into immutable FTF-owned containers and typed plans, then let FTF own
  the resulting selection, spatial, ordering, and execution policy. TerraBlender, Lithostitched,
  Biolith, loader APIs, and vanilla/datapack registries are peer input mechanisms; none is the
  runtime's authority.
- Keep preview, generation, diagnostics, and every other downstream consumer zero-knowledge. They
  consume immutable FTF plans and results, never third-party registries, providers, callbacks,
  samplers, or mod-specific failure terms.
- Prefer registries, resources, codecs, and stable public snapshots or query/factory contracts. If a
  mechanism does not expose a complete snapshot, contain any necessary version-qualified bridge
  behind that mechanism's runtime provider and require evidence for completeness, ordering,
  lifecycle, reload, and concurrency. Never infer semantics from private fields, replay registration
  events, or maintain brittle per-mod Mixins. Keep an unsupported facet explicit until a sound seam
  exists.
- Do not equate the absence of a public finalized snapshot with proof that request-owned resolution
  is impossible. Inspect the mechanism's finalizer and current upstream consumers for an isolated
  pre-server resolution path. A manual finalizer invocation or callback replay proves feasibility,
  but is not itself a production contract until purity, repeatability, ownership, reload, ordering,
  and concurrency are established. Keep any proven resolver inside runtime acquisition rather than
  exposing it to preview or another downstream consumer.
- Named third-party mods are a diverse falsification and coverage corpus, never an allowlist or the
  architecture's optimization target. Classify and support stable worldgen mechanisms; an unseen mod
  using a supported mechanism must work without code changes, while an unsupported mechanism must
  produce bounded, actionable capability diagnostics without corrupting supported domains. Absence
  from the corpus never means unsupported, and passing only the named corpus is insufficient.
- Do not implement a production compatibility fix until the canonical plan's feasibility,
  extraction-completeness, ownership, ordering, reload, parity, failure, lifecycle, and cross-domain
  acceptance gates are supported by current-tip evidence.
- Maintain one complete dependency-ordered compatibility plan, but execute one coherent vertical
  workstream at a time. A workstream is complete only after obsolete implementation paths are
  removed and its source, deterministic probes, loader coverage, reload/concurrency behavior,
  failure boundaries, and production packaging gates pass. Shared evidence infrastructure may be
  advanced when it is required to prove the active workstream; do not scatter partial production
  changes across later workstreams.

## Context hygiene

- Keep this file limited to durable rules and pointers. Put investigation conclusions in the
  canonical plan and raw observations in retained run artifacts or focused analysis outputs.
- On context restoration, inspect current status and continue from completed artifacts rather than
  repeating finished work.
