# Resumption prompt: RTF ocean-depth biome-banding follow-up (Thread 1 shipped)

One active thread remains under `games/minecraft/mods/ReTerraForged` (branch
`feat/configurable-ocean-depth`), stemming from PR #97's configurable `oceanDepth`. Read the
relevant doc fully before resuming — this file is an index, not a substitute.

```text
.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/biome-climate-banding-investigation.md
```

## Thread 1: Trial Chambers / Ancient City structure placement — shipped 2026-07-20

Done. Production mixin `MixinJigsawStructure` (no logging, no QA scaffolding) is committed to
`feat/configurable-ocean-depth` (`6b180fd`, pushed to origin) and live-verified across three preset
depths for all four required behaviors: skip (no valid window), bury/push-down under deep oceans,
push-up window rescue (proven via a `worldDepth=16` preset where the blind range is categorically
invalid), and unaffected normal generation. A follow-up commit (`69d2f5b`) fixed a real gap found by
playing on a real client afterward, a surface-protrusion case the pre-build ceiling check couldn't
catch because it was comparing against a distant hill instead of the real footprint, see the
"Real-footprint ceiling" section in `trial-chambers-and-ocean-structures.md` for the mechanism. The
five QA-only diagnostic scanner mixins were not carried over — they remain only on the local
`qa/configurable-ocean-depth` branch for future re-verification if ever needed. Full detail,
live-verification results, and the still-open product/scope call (does this belong in
`feat/configurable-ocean-depth` at all, vs. a documented known limitation — not a technical
question) are in `trial-chambers-and-ocean-structures.md`'s "Status" and "Production cleanup and
live verification" sections. Do not re-derive any of this.

## Biome climate-banding — deliberately deferred, zero progress since flagged

Separate, real issue: RTF's `deep_dark`/`dripstone_caves`/`lush_caves` climate eligibility can
become unreachable under very deep, shallow-`worldDepth` oceans, independent of the
structure-placement bug above. Mechanism is understood at the source-code level (see "Larger Open
Question" in `biome-climate-banding-investigation.md`) and two candidate fix directions are
documented (a formula-derived `oceanDepth` clamp vs. a decoupled climate-only `depth` function) but
neither is built. **This was deliberately set aside this session** ("things to look further into
later on") — next steps are exactly the "Remaining evidence needed" list in that doc (vanilla
empirical baselines, a controlled RTF preset matrix, and the terrain-vs-climate-only `DEPTH`
distinction with blast-radius measurement). Do not start building a fix without that evidence
gathered first.

## Practical notes carried forward

- Use `games/minecraft/tooling/dev-server`, not manual Gradle/RCON — see
  `live-worldgen-investigation-howto.md` for the full workflow, including known `dev-server` process
  cleanup gaps and their workarounds (also documented in `games/minecraft/tooling/README.md`'s
  "Known limitations").
- A full decompiled/mapped vanilla 1.21.1 source tree exists locally at
  `games/minecraft/reference/sources/1.21.1/official/src/` — read it directly for anything
  vanilla-behavior-related rather than reconstructing from memory.
- Reference presets (very-deep, Goldilocks, `worldDepth=16` mountain) are committed at
  `.agent-docs/games/minecraft/mods/ReTerraForged/plans/ocean-depth/test-presets/` — see
  `qa-presets.md` for checksums. Prefer these canonical copies over re-exporting or
  hand-reconstructing.
- Seed `3216933670` is the standard seed for all of this investigation's reproduction cases.
