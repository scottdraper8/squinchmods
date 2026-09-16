# Search Probes acceptance

The installed package targets the pinned No Man's Sky 7.01 executable on this Steam Proton host. It
starts with an ordinary Steam launch and needs no external injector or controller. F7 creates and
shows the form on first use. Mod source lives in `mods/search-probes`; all build, installation,
test, investigation, and desktop-control tooling lives in the parent repository.

Raw records are
[`mission lifecycle`](../../investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
and
[`completed-target reuse`](../../investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json).

## Current 7.01 production state

The current public Steam executable is build `25320008`, SHA-256
`78c1d883a8d47c99308795ee22e8bdf7c03970f0af090effa45107cefb194ba4`. The minor game update recompiled
the native functions and moved their absolute virtual addresses and RIP-relative global references.
The old exact-build hash gate therefore stopped Search Probes before its hook could install; this
was a native compatibility failure, not an Amethyst priority or UI layout issue.

The product now uses the current function/global addresses, the current allocator instruction guard,
and the current executable allowlist. Hook installation also handles the updated client's
thread-snapshot race by retrying transient suspend failures and recognizing threads that exit
between enumeration and suspension while still failing closed for a live inaccessible thread.

The final production package was installed through the normal Steam launch path and through the
Amethyst managed source layout. Its current hook control passed (`42 → 43 → 42`), F7 opened the
rendered Search Probes form, and the full live matrix passed exhaustive survey, colour survey,
advertised filters, anomaly controls, and positive searches. The retained raw run is
[`20260915T153000Z-production-7.01-update`](../../investigation-state/runs/20260915T153000Z-production-7.01-update/manifest.json).

## Colour/UI and managed deployment

The
[reference capture](../../investigation-state/runs/20260915T030000Z-colour-island-reference/analysis.json)
and
[installed footprint](../../investigation-state/runs/20260915T030000Z-colour-island-reference/installation.json)
cover selected sky/water inputs, native water parity across 19 records, read-only selected colours
on six loaded planets, the captured island reference, and combined-filter negative controls.

The
[fresh installed run](../../investigation-state/runs/20260915T050700Z-colour-redeployment/analysis.json)
and its
[footprint](../../investigation-state/runs/20260915T050700Z-colour-redeployment/installation.json)
close the host-recovery gameplay-callback gate. Amethyst's mirrored source had redeployed eight
stale modules; both the game and managed sources now match the corrected package. The installer
updates all owned copies transactionally and remembers managed paths even after game files become
regular files. It rejects ambiguous/foreign sources and preserves user presets without shipping old
sessions and logs into managed sources. Failure-injection tests cover rollback after partial
publication.

The fresh runtime reproduces the loaded selected colours of the player's Bujav L2 exactly. Blue sky
and blue water each reject that target; non-colour criteria and its actual selected-colour controls
accept it. Bounded positive blue sky/water and island require/exclude searches return matches whose
exact criteria also pass independent candidate rechecks. The first F7 opens the simplified form;
saved legacy constraints remain explicit and are included unchanged in submitted searches.

276 investigation tests, 10 acquisition tests, and lint pass. All 32 product modules and 1,727
immutable payload files agree with source/manifest in both deployment destinations; user presets
remain byte-identical. Selected sky/water values are generated inputs, not promises about final
pixels after atmosphere, time of day, reflections, or screen grading. No flight, warp, or mission
lifecycle change was performed.

## Mission/lifecycle baseline

| Gate                     | Evidence                                                                                                                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Correct native ownership | Current reward/mission-sequence callers resolve the native mission start and manager; exact executable and byte prefixes are checked.                                                             |
| Form lifecycle           | Repeated start/abandon/restart, duplicate rejection before target mutation, one exact planet route, and zero owned routes after abandonment.                                                      |
| Completed-target reuse   | The player's naturally completed target is reused with a valid zero native seed; one mission instance and the exact next route remain active. Native selection is verified before acknowledgment. |
| Save/reload              | A saved active target survives a fresh process as one Log entry with the same exact destination; native abandonment still works.                                                                  |
| Actual form interaction  | Search and Navigate exercised through the visible form; names populated; first F7 verified on the final installed source.                                                                         |
| Guide lifecycle          | Actual Guide launch with a positive control produces one native mission-owned exact route; no-match control produces no target. Both abandon normally.                                            |
| Search parity            | Final installed smoke matrix completed; exhaustive generated-field controls remain linked from the canonical plan and filter audit.                                                               |
| Packaging                | Both game and managed-source payloads match the package; fresh gameplay-callback and form controls are specified above.                                                                           |
| Cleanup                  | Baseline native abandonment leaves zero owned routes and preserves unrelated routes. The player confirms mission lifecycle/galaxy-map behavior works; this update does not modify it.             |

The form uses a disposable native NPC mission, not a persistent Wiki listener. Guide slots retain
their separate native ready handshake; an abandoned slot cannot publish a route. No-match Guide
searches require abandoning the probe in the Log; their detailed status is available in the F7 form.
Guide preset edits are applied on the next launch.

The native mission seed is `value=0, valid=true`; an all-zero structure is a different identity.
Both fields participate in native restart matching. The active-query wildcard behavior must not be
mistaken for an identity suitable for starting a mission. NMS's restart queue drops the initial
selection flag, so the runtime explicitly selects the sole active matching instance after its exact
route is present. Route disappearance is not handled by republishing markers or delaying mission
stages.

The player completed the first target naturally. The follow-up uses that completed mission to
validate reuse; no automated flight, warp, movement, or fabricated completion was performed.
Fresh-process validation retains the exact route and selected Log target, followed by two installed
start/abandon cycles. Galaxy Map rendering is not newly exercised from the freighter hangar. Native
Windows, VR, HDR, other resolutions, multiplayer sessions, and broad graphics/input-overlay
compatibility are not claimed by this host's acceptance.

Desktop capture failures are retained separately as invalid host evidence. Wayland Vulkan
screenshots use the compositor; stale X11 window captures are not input or runtime evidence.
