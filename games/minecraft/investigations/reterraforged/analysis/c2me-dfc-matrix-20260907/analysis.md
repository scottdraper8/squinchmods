# C2ME density-function compiler runtime-mode matrix

## Result

The corrected matrix completed 27 of 27 fresh-JVM scenarios: three FreeTerraForged revisions, three
C2ME runtime modes, and three independent JVMs per cell. Every scenario succeeded, every measured
observation released exactly its four acknowledged force-load regions, cleanup was complete, the
investigation state became inactive, and the post-run process gate found no Java process.

The compatibility fix removes the large DFC-enabled regression. Using the median of the three JVM
medians, the exact parent needs 9.9893 seconds per 441 chunks with DFC enabled and the fix needs
2.8626 seconds. That is 3.4895x the throughput and 71.34% less generation time. The fix and
`experimentalChunkFixes` are close in all three modes; the three-replication design does not support
treating their 1.9%-2.4% differences as meaningful branch effects.

## Method

- Revisions: exact parent `22a212bbcfe5bb697251417a399cf4ff4acba5b7`, compatibility fix
  `94120258e85672cb445188103545069853aed66a`, and live experimental tip
  `8591d2b2dd51d4f004460af21696e9f1fc3886c5`.
- Modes: C2ME installed with DFC enabled, C2ME installed with DFC disabled, and C2ME absent.
- Runtime: packaged Fabric harness, Temurin 21.0.11+10, 12 GiB maximum heap, no JFR.
- Workload: seed `3216933670`; one 441-chunk warmup; seven disjoint 441-chunk measured windows;
  finished-chunk terminal probe.
- Lifetime: each observation removed its four exact owned force-load regions after the terminal
  probe. Release time is recorded separately and excluded from generation and total timing.
- Replication order: the first pass mixed cells, the second ran absent/off/on, and the third
  reversed the order to on/off/absent. Each cell therefore represents three server launches and 21
  measured windows.
- Statistical unit: the JVM is the independent replication unit. The aggregate below is the median
  of three JVM medians. The 21 spatial windows are nested observations and are not presented as 21
  independent replications.

## Results

Times are seconds per 441 chunks. The range is across the three JVM medians, not the 21 nested
windows.

| Revision               | C2ME mode | JVM medians               | Aggregate |       JVM range | Chunks/s |
| ---------------------- | --------- | ------------------------- | --------: | --------------: | -------: |
| parent `22a212b`       | DFC on    | 9.5144, 10.1051, 9.9893   |    9.9893 |  9.5144-10.1051 |  44.1472 |
| fix `9412025`          | DFC on    | 2.8107, 2.8626, 2.8955    |    2.8626 |   2.8107-2.8955 | 154.0536 |
| experimental `8591d2b` | DFC on    | 2.7975, 2.7346, 2.8150    |    2.7975 |   2.7346-2.8150 | 157.6388 |
| parent `22a212b`       | DFC off   | 3.3105, 3.1939, 3.4098    |    3.3105 |   3.1939-3.4098 | 133.2121 |
| fix `9412025`          | DFC off   | 3.1481, 3.0980, 3.0991    |    3.0991 |   3.0980-3.1481 | 142.2998 |
| experimental `8591d2b` | DFC off   | 3.2661, 3.1309, 3.1738    |    3.1738 |   3.1309-3.2661 | 138.9517 |
| parent `22a212b`       | absent    | 12.7085, 14.2757, 13.8262 |   13.8262 | 12.7085-14.2757 |  31.8960 |
| fix `9412025`          | absent    | 13.4192, 14.0978, 13.2276 |   13.4192 | 13.2276-14.0978 |  32.8635 |
| experimental `8591d2b` | absent    | 13.6768, 14.0180, 13.5313 |   13.6768 | 13.5313-14.0180 |  32.2445 |

Direct aggregate comparisons:

- Fix versus parent, DFC on: 3.4895x throughput, 71.34% less time.
- Fix versus parent, DFC off: 1.0682x throughput, 6.39% less time.
- Fix versus parent, C2ME absent: 1.0303x throughput, 2.94% less time. The JVM-median ranges overlap
  substantially, so this is not evidence of a reliable absent-mode improvement.
- Within the fixed revision, DFC on is 7.63% faster by time than DFC off. Within the experimental
  revision, it is 11.85% faster. The parent instead becomes 3.0175x slower with DFC on, matching its
  demonstrated failure to install chunk-owned wrappers and caches in the compiled graph.
- Experimental versus fix: experimental is 2.33% faster with DFC on, 2.41% slower with DFC off, and
  1.92% slower with C2ME absent. These small changes reverse direction by mode and are bounded by
  only three independent JVMs; no general experimental-branch performance claim follows.

## Run inventory

| Revision/mode          | Run IDs                                                                                     |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| parent / DFC on        | `20260907T021100Z-1ec06374f0`, `20260907T023050Z-17514ce3f6`, `20260907T023535Z-f7bb646416` |
| fix / DFC on           | `20260907T021241Z-f2c0beebe3`, `20260907T023235Z-84060dc06f`, `20260907T023450Z-bc1364113c` |
| experimental / DFC on  | `20260907T021326Z-756d0a276c`, `20260907T023320Z-c836136351`, `20260907T023406Z-108967e06d` |
| parent / DFC off       | `20260907T021410Z-e067796f49`, `20260907T022829Z-a11244052a`, `20260907T023857Z-3f10103ab1` |
| fix / DFC off          | `20260907T021500Z-75568d0da4`, `20260907T022916Z-0b3536d090`, `20260907T023809Z-e0d0dd1165` |
| experimental / DFC off | `20260907T021548Z-983634ce8a`, `20260907T023002Z-b63b1bc78c`, `20260907T023721Z-5be04ce599` |
| parent / absent        | `20260907T015914Z-635be9b7c6`, `20260907T021712Z-64c695a023`, `20260907T024716Z-d0a924f2dc` |
| fix / absent           | `20260907T020715Z-99aaac6fd8`, `20260907T022056Z-736eb20cec`, `20260907T024331Z-e1d333af00` |
| experimental / absent  | `20260907T020328Z-0da58d5010`, `20260907T022440Z-a9b860e897`, `20260907T023946Z-8cb10f9812` |

## Earlier failures and validity boundary

The earlier accumulated-ticket attempts are not part of this matrix. The runner previously retained
the warmup and all seven measured windows simultaneously, growing from 441 to 3,528 force-loaded
chunks. At 4 GiB, profiler-free run `20260907T010315Z-1c6346bcbf` exhausted the G1 heap and crashed
inside `RegisterNMethodOopClosure::do_oop`. Parent/no-C2ME run `20260907T012004Z-caa696b70e` and
experimental/no-C2ME run `20260906T233513Z-99905130ee` later stopped making progress and became
unkillable during teardown.

Those failures establish real unsafe behavior in the old stress workload, but they do not establish
a branch-specific no-C2ME defect. With exact per-observation release, the same previously failing
parent and experimental cells passed three times each, as did every other cell. The corrected matrix
therefore answers the requested branch/mode performance question; it does not prove that HotSpot
cannot still fail under deliberately accumulated 3,528-chunk pressure.
