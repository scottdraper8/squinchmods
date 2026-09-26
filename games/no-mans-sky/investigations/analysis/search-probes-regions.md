# Search Probes region streaming

## Supported contract

Search budgets count distinct systems evaluated, excluding the starting system, and accept up to
1,000,000,000 systems. The form uses a dropdown with the seven powers of ten from 1,000 through
1,000,000,000 and defaults to 10,000. Existing preset budgets round to the nearest dropdown value
(ties upward), with the original file retained as a backup. Nearby indexed systems are checked in
native distance order. Once that batch is consumed, the runtime generates additional regions in
expanding, clipped cube shells within the same galaxy. The loaded graph is not enlarged or modified.
Later results follow traversal order, without a global nearest-distance guarantee.

Each request retains the initial nearby address set, one region batch, and at most 100 results.
Region arrays are copied and released within one gameplay update. Candidate evaluation uses later
updates and retains the existing cooperative slice limits. Requests stop at their system budget,
requested result count, cancellation, or exhausted region space. Cancellation keeps completed
matches. There is no elapsed-time cutoff; paused gameplay pauses progress, and NMS exit discards
active requests. A galaxy change aborts rather than mixing results from different galaxies.

## Native boundary

The supported executable is NMS 7.04, public build `25442159`, SHA-256
`b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`.

| Operation          | Preferred VA  | Ownership                                       |
| ------------------ | ------------- | ----------------------------------------------- |
| Voxel construction | `0x1404C3090` | Initializes caller-owned `0x260` storage        |
| Region population  | `0x14135D7B0` | Fills that voxel from its packed region address |
| Voxel destruction  | `0x1404C2E90` | Releases its internal dynamic arrays            |

The
[portal validation and classification disassembly](../../investigation-state/runs/20260924T173520Z-exe-functions-6497eedf/result.json),
[population/destruction disassembly](../../investigation-state/runs/20260924T173555Z-exe-functions-16ceb858/result.json),
and
[native distance consumers](../../investigation-state/runs/20260924T173636Z-exe-functions-39aaf4e8/result.json)
establish the isolated lifecycle. The constructor is a leaf without a function-table entry; its
retained
[disassembly](../../investigation-state/runs/20260924T173720Z-region-enumeration/voxel-constructor.asm)
and
[unique exact-build signatures](../../investigation-state/runs/20260924T173720Z-region-enumeration/signatures.json)
complete the call boundary. A historical NMS.py Populate signature matched a terrain UI function in
this executable and is not used.

The address array header is at voxel `+0x250` (count `+0x254`, pointer `+0x258`); position arrays
are at `+0x210`. Native addresses include a discontiguous purple-system range beginning at 1001.
Enumerating a guessed contiguous system-index interval is therefore invalid. Production copies the
actual arrays, validates counts, coordinates, uniqueness, and finite positions, then destroys the
voxel in `finally`. Both the voxel and root vector require explicit 16-byte alignment on bundled
Windows Python. Exploratory unaligned root calls raised access violations; aligned calls and the
guarded ownership controls passed. Those failures remain raw evidence, not a supported call form.

## Region controls

The
[native controls](../../investigation-state/runs/20260924T173720Z-region-enumeration/controls-summary.json)
cover 121 regions, 69,753 generated systems, and 59,273 systems outside the active graph. All graph
hash comparisons and allocation guards passed. Repeated region generation and three repeated remote
full snapshots matched. The local region's 591 generated addresses matched all 591 indexed entries
in that region, including its 65 purple systems.

The deterministic tests cover clipped traversal at interior and galaxy-edge origins, unique region
and system visitation, current-system exclusion by identity, overlap removal, discontiguous native
indices, bounded batch retention, exact budgets, native cleanup on failure, galaxy-change failure,
and cancellation retaining completed matches. Native buffers remain bounded even for a
billion-system request. Exhaustive whole-galaxy coverage and an hours-long live soak are not claimed
by these tests.

## Packaged runtime controls

The ordinary Steam self-start run is retained under
[`20260924T175504Z-expanded-region-search`](../../investigation-state/runs/20260924T175504Z-expanded-region-search).
Its `matrix` directory contains the local/remote controls. The requested 100,000-system run was
cancelled at the user's direction after 30,447 checked systems, including 21,150 streamed systems
from 56 generated regions. Cancellation completed normally. A second selective search was also
cancelled before reaching its outside-graph target; direct evaluation of that target had accepted
its exact criteria. No complete 100,000-system run or billion-system live request was performed. The
[cancelled results](../../investigation-state/runs/20260924T175504Z-expanded-region-search/cancelled-searches.json)
preserve the actual boundary. Both the 20,000 former cap and the observed graph ceiling were
exceeded.

The final graph diagnostic timed out while gameplay was paused, then became stale when shutdown
advanced the command generation. It is not evidence of graph parity after the long run; graph parity
is supported by the separate 121-region controls. Shutdown restored the hooks and closed the
executor with NMS still alive. The game was then closed before final deployment. The repeatable host
harness is `tooling/runtime/resident_region_matrix.py`; it can resume monitoring an existing request
after a host reader interruption. Progress files are mutable under the runtime's in-process lock, so
host readers retry partial writes. Final results are atomically published.

The
[package parity record](../../investigation-state/runs/20260924T175504Z-expanded-region-search/package-parity.json)
compares all 1,724 runtime files, the proxy, and four adapter files with the direct installation and
Amethyst managed sources. Product Python sources match the packaged files exactly. All 308
deterministic tests pass, including formatted dropdown choices and preserving legacy budgets. The
final dropdown change was checked without launching another live search. A packaging attempt under
the host Python exited with signal 11; the completed build used the repository's Python 3.13
environment. Both build logs are retained.

Player movement, warp, and navigation publication are outside these controls. Save files were backed
up before launch and were not edited by the probes. NMS's ordinary idle autosave changed `save7.hg`
and its metadata during both runtime sessions; before/after hashes and backups are retained. The
launcher requested `save2.hg`, but that request alone does not prove which menu row NMS loaded.
Runtime origin and graph addresses are the authority for these controls. No claim of byte-identical
saves or new mission/navigation lifecycle coverage is made.
