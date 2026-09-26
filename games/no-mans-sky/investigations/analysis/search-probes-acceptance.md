# Search Probes acceptance

## Current package

The installed production package targets No Man's Sky 7.04, public Steam build `25442159`, on the
validated Steam/Proton installation. Its executable SHA-256 is
`b7913f268dfc62386b6b68f524bfc8ade4a44a9f4fbad39085b7bf51be3680cb`; the runtime fails closed on
other executable bytes. Ordinary Steam launch starts the package without an external injector.

## 7.04 acceptance

The full resident matrix completed through the normal Steam bootstrap using the documented
`save2.hg` control save. It covered all 62 visible fields and 304 selectable values, 65
composition/diagnostic searches, generated-field and colour surveys across 9,297 remote systems and
44,430 planets, and the required snapshot, parity, RNG, and native-output lifetime checks. All gates
passed, including prelaunch/runtime/shutdown health; the player remained idle and the save was not
mutated. Five deliberate negative controls returned no match as expected. The
[completed matrix summary](../../investigation-state/runs/20260923T171746Z-resident-matrix-full-retest-save2/session/results/matrix-full-1790183046419051873-summary.json)
and health-gate records are retained locally.

The production package manifest matches the E2E-tested package. All 1,724 packaged runtime files,
the WINMM proxy, and the four generated adapter files match both the direct game installation and
Amethyst's managed sources. The deployment record points to Amethyst's `Root_Folder/Binaries` and
`overwrite` sources so manager redeployment keeps this version. Valid user presets survive install.

The 7.04 source adapter and Guide/UI data round trips passed, and all 308 investigation tests
passed. Detailed technical findings and retained-run pointers are in the
[system-search investigation](../../../../.agent-docs/games/no-mans-sky/working/system-search-investigation.md).

## Region expansion

Searches accept budgets up to one billion systems and continue past the finite loaded index by
streaming native generated regions. Each system is evaluated once, memory remains bounded by the
initial nearby set and one region, and cancellation retains completed matches. The exact native
boundary, deterministic gates, and packaged runtime controls are in the
[region streaming record](search-probes-regions.md). The package is `SearchProbes-7.04-expanded`.
The earlier full criterion matrix is evidence for filters; expansion has its own runtime controls.

## Preset budgets and retained results

Preset budgets round to the nearest dropdown value by absolute system count, with ties upward.
Migration validates the complete library, atomically writes it, and retains the original file as a
backup. The installed Earthlike preset migrated from 5,000 to 1,000 systems; the three 20,000-system
presets migrated to 10,000. Their criteria and selected result counts are retained. New form
searches and freshly restored built-ins default to 10,000 systems. The result selector and protocol
permit 1 through 100 matches per search.

The rebuilt package and both NMS/Amethyst deployment trees match the manifest and product sources.
Migration files and the
[deployment record](../../investigation-state/runs/20260924T182002Z-preset-budgets-results/deployment.json)
are retained. This follow-up used source review, the build, and deployment file comparisons; no new
unit-test or live-search run was performed. The earlier 308-test result remains prior evidence.

## Validation boundary

The 7.04 matrix validates search behavior, not Guide mission acceptance, abandonment, restart,
completed-target reuse, save/reload, or Galaxy Map route ownership. Replaying those controls would
mutate persistent mission state; the retained 7.03.1
[mission lifecycle](../../investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
and
[completed-target reuse](../../investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json)
runs are historical evidence only. The current gate also does not claim automatic travel, native
Windows, VR, HDR, or multiplayer validation.

The newest visible `save7.hg` did not provide the matrix's positive Lush/HydroGarden floating-island
control in its first 64 nearby candidates, so that attempt stopped at the seed-dependent smoke
precondition. The completed run used `save2.hg`, whose nearby candidates provide the required
control; this is a test-fixture boundary, not a change in product behavior. The incomplete
[save7 control-miss run](../../investigation-state/runs/20260923T171746Z-resident-matrix-full-newest-save-control-miss/session/results/matrix-full-1790182695672355497-summary.json)
is retained separately.

Raw run directories are ignored local evidence, not tracked project files.
