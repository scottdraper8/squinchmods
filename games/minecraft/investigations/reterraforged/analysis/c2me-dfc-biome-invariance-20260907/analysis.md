# C2ME DFC biome and underground-banding invariance

## Question and conclusion

This comparison asks whether the focused C2ME density-function lifecycle fix or the broader
`experimentalChunkFixes` branch changes biome selection, including the vertical distribution of
underground biomes. In the tested modern-default FTF preset, seed, and vanilla-biome corpus, neither
branch changes a single sampled biome coordinate under any tested C2ME mode on Fabric or NeoForge.

All 14 accepted runs produced the same position-sensitive SHA-256 digest over the ordered sequence
of `(block x, block y, block z, biome id)` values:

`4174568743a25b34a69b70aeefbb9e2a10b600d5cc3062d9f786df6f6da7e5b9`

Each run queried 532,512 exact positions from the live server biome source. Across the complete
7,455,168-query comparison, the digest, total cave-biome count, per-height-band counts, and every
generated-chunk parity result agree. The evidence therefore falsifies a biome-layout or vertical
biome-banding change in this corpus. It does not prove universal equivalence for every seed, preset,
biome-provider mod, or custom density function.

## Revisions and runtime modes

- Correct reference: live `upstream/1.21.1` parent `22a212bbcfe5bb697251417a399cf4ff4acba5b7`, with
  C2ME present and DFC explicitly disabled.
- Focused fix: `94120258e85672cb445188103545069853aed66a`, tested with C2ME DFC explicitly disabled,
  explicitly enabled, and C2ME absent.
- Experimental: live `upstream/experimentalChunkFixes` `8591d2b2dd51d4f004460af21696e9f1fc3886c5`,
  tested in the same three modes.
- Fabric C2ME: `0.4.0-alpha.0.27+1.21.1`.
- NeoForge C2ME: `0.4.0-alpha.0.120+1.21.1`.

The reference does not include a DFC-on cell because that combination is independently proven to
skip the whole-router `NoiseChunk::wrap` lifecycle and generate incorrect terrain. The question is
whether either corrected implementation or its C2ME-mode transitions depart from the known-correct
DFC-off biome field.

## Method

Every run used the repository's neutral packaged-server harness, seed `3216933670`, and
`modern-default-with-rivers-live-export/reterraforged-preset.zip`. The dedicated
`squinch:rtf-underground-biome-distribution` probe queried the server's biome source at:

- block X and Z from -32,768 through 32,768 inclusive, in 512-block increments;
- block Y from -64 through 60 inclusive, in four-block increments;
- 129 x 129 horizontal positions, 32 vertical positions each, or 532,512 selections per run.

The probe hashes coordinates as well as the biome ID. Matching aggregate counts alone could hide a
spatial rearrangement; matching this ordered digest requires the same biome ID at the same sampled
coordinate throughout the grid, subject only to SHA-256's negligible collision possibility.

The probe separately reports recognized cave-biome selections in three vertical bands and generates
chunk `(0, 0)`. It then compares 512 quart-resolution biome cells stored in that finished chunk with
fresh direct biome-source queries. This distinguishes the selection field from chunk storage and
checks that generation does not substitute a different biome result.

## Accepted runs

| Revision               | Loader   | Runtime mode  | Run ID                        |
| ---------------------- | -------- | ------------- | ----------------------------- |
| parent `22a212b`       | Fabric   | C2ME, DFC off | `20260907T035523Z-9c9b34096c` |
| fix `9412025`          | Fabric   | C2ME, DFC off | `20260907T035551Z-14e5b7d9eb` |
| fix `9412025`          | Fabric   | C2ME, DFC on  | `20260907T035621Z-ce38882f47` |
| fix `9412025`          | Fabric   | C2ME absent   | `20260907T035649Z-bf5e76b31f` |
| parent `22a212b`       | NeoForge | C2ME, DFC off | `20260907T035834Z-4cf4116254` |
| fix `9412025`          | NeoForge | C2ME, DFC off | `20260907T035904Z-eb00fb91b4` |
| fix `9412025`          | NeoForge | C2ME, DFC on  | `20260907T035934Z-238fe52bb0` |
| fix `9412025`          | NeoForge | C2ME absent   | `20260907T040003Z-0b3dbbae20` |
| experimental `8591d2b` | Fabric   | C2ME, DFC off | `20260907T040335Z-62d1e973a6` |
| experimental `8591d2b` | Fabric   | C2ME, DFC on  | `20260907T040405Z-92fba1d37e` |
| experimental `8591d2b` | Fabric   | C2ME absent   | `20260907T040433Z-125f7577dd` |
| experimental `8591d2b` | NeoForge | C2ME, DFC off | `20260907T040524Z-e90378894c` |
| experimental `8591d2b` | NeoForge | C2ME, DFC on  | `20260907T040553Z-a2cc102eaf` |
| experimental `8591d2b` | NeoForge | C2ME absent   | `20260907T040622Z-429a791e80` |

All 14 scenarios reached the terminal probe, passed, shut down cleanly, left their investigation
state inactive, and left no JVM. A user-interrupted Fabric attempt `20260907T035418Z-f4ea77a172` is
retained but rejected from the comparison. A prelaunch NeoForge attempt was correctly rejected
because the neutral harness contained a stale 458-byte manifest-only probe stub. That stub was
moved, not deleted, to
`games/minecraft/investigation-state/quarantine/vanilla-control-neoforge-run-mods/vanilla-control-probe.jar`;
no behavior-bearing run was created by that attempt.

## Results

Every row above has the following exact values:

| Measurement                      |          Per run |      Across 14 runs |
| -------------------------------- | ---------------: | ------------------: |
| direct positional biome samples  |          532,512 |           7,455,168 |
| recognized cave-biome selections |           59,061 |             826,854 |
| lower band, Y -64 through -4     | 32,151 / 266,256 | 450,114 / 3,727,584 |
| middle band, Y 0 through 28      | 14,466 / 133,128 | 202,524 / 1,863,792 |
| upper band, Y 32 through 60      | 12,444 / 133,128 | 174,216 / 1,863,792 |
| finished-chunk parity samples    |              512 |               7,168 |
| finished-chunk parity mismatches |                0 |                   0 |

The identical positional digest is stronger than the identical band totals: it also covers exact
horizontal placement and every sampled vertical transition. The band totals make the underground
portion independently inspectable.

## Relation to terrain and surface maps

Biome selection and terrain density are separate domains. The earlier pre-surface comparison proves
that distinction directly:

- Parent DFC off has terrain hash `c3c9fd38d6eb17cde37c60e654cf2cb66da30587df10084b35071c64a4e78ab1`
  and biome hash `e31b6068c7e34e482c884e5c5d8e18cf62a7e62a7f853efb9958acfcf8f07aba`.
- Broken parent DFC on changes the terrain hash to `35bfd35e...` while retaining the same
  pre-surface biome hash `e31b6068...`.
- The focused fix produces the correct `c3c9fd38...` terrain hash and `e31b6068...` biome hash with
  DFC off, on, default, or absent.

A surface biome map samples the three-dimensional biome field at terrain-dependent heights. Broken
terrain can therefore change the map's apparent biome shapes even when the underlying biome field is
unchanged: the map is asking for a biome at a different Y coordinate. Restoring correct terrain can
visibly change such a map back to the DFC-off reference without constituting a biome-selection
change.

## Source interpretation and limits

The focused fix changes the `NoiseChunk` initialization injection point so that vanilla's existing
whole-router mapping executes. It contains no biome-selection, climate-sampling, or underground
banding policy change. The cross-loader positional comparison supports that source-locality claim.

Experimental contains the same essential lifecycle correction but also changes `CellSampler`
identity, an out-of-chunk `sampleClimate` fallback, compiled-function unwrapping, and wrapping
timing. Those extras are behavior-bearing and are not needed for the C2ME root cause. This matrix
shows that they do not alter the tested default vanilla-biome field, but it does not clear them for
custom presets or third-party biome-provider mechanisms. In particular, this corpus does not load
Biomes O' Plenty and therefore does not directly reproduce a BOP `lavender_field` screenshot.

Accordingly, the evidence supports merging the focused fix. It does not support merging the whole
experimental branch on the assumption that its additional behavior is inert. A claim about the exact
modded screenshot requires the same positional comparison with that exact preset and mod set.
