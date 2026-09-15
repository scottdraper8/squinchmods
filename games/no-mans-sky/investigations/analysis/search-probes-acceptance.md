# Search Probes acceptance

The installed package targets the pinned No Man's Sky 7.01 executable on this Steam Proton host. It
starts with an ordinary Steam launch and needs no external injector or controller. F7 creates and
shows the form on first use. Mod source lives in `mods/search-probes`; all build, installation,
test, investigation, and desktop-control tooling lives in the parent repository.

Raw records are
[`mission lifecycle`](../../investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json)
and
[`completed-target reuse`](../../investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json).

## Current colour/UI update gate

The
[reference capture](../../investigation-state/runs/20260915T030000Z-colour-island-reference/analysis.json)
and
[installed footprint](../../investigation-state/runs/20260915T030000Z-colour-island-reference/installation.json)
cover selected sky/water inputs, native water parity across 19 records, read-only selected colours
on six loaded planets, the captured island reference, and combined-filter negative controls. 270
investigation tests, 10 acquisition tests, and lint pass. All 32 installed modules match source;
1,728 immutable installed files match the manifest, and user presets are byte-identical.

Fresh-process gameplay-callback and actual form validation of this update is **pending**. Host
Python crashed during packaging; the archive tool subsequently entered an uninterruptible kernel
memory-management wait, also blocking process-list readers. The unchanged, validated native mission
adapter was reused to finish packaging under the project's Python. NMS is stopped for the user's
requested PC restart. Do not promote captured-data/unit results to a fresh installed-runtime claim.
After host recovery, verify a normal Steam launch, reference snapshot/candidate controls, bounded
colour searches, island require/exclude controls, the simplified form, and exact saved-preset round
trips. Do not fly, warp, or change the working mission lifecycle.

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
| Packaging                | The lifecycle baseline's installed footprint is retained in its run; current update packaging and pending runtime gates are specified above.                                                      |
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
