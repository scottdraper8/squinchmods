# Search Probes acceptance

The installed release supports the pinned No Man's Sky 7.01 executable on this Steam Proton host. It
starts with an ordinary Steam launch and needs no external injector or controller. F7 creates and
shows the form on first use. Mod source lives in `mods/search-probes`; all build, installation,
test, investigation, and desktop-control tooling lives in the parent repository.

The complete raw record is
[`20260914T200400Z-mission-lifecycle`](../../investigation-state/runs/20260914T200400Z-mission-lifecycle/analysis.json).

| Gate                     | Evidence                                                                                                                                                  |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Correct native ownership | Current reward/mission-sequence callers resolve the native mission start and manager; exact executable and byte prefixes are checked.                     |
| Form lifecycle           | Repeated start/abandon/restart, duplicate rejection before target mutation, one exact planet route, and zero owned routes after abandonment.              |
| Save/reload              | A saved active target survives a fresh process as one Log entry with the same exact destination; native abandonment still works.                          |
| Actual form interaction  | Search and Navigate exercised through the visible form; names populated; first F7 verified on the final installed source.                                 |
| Guide lifecycle          | Actual Guide launch with a positive control produces one native mission-owned exact route; no-match control produces no target. Both abandon normally.    |
| Search parity            | Final installed smoke matrix completed; exhaustive generated-field controls remain linked from the canonical plan and filter audit.                       |
| Packaging                | 1,726 immutable installed files and all 31 product Python modules match the package/source; 206 investigation tests, 10 acquisition tests, and lint pass. |
| Cleanup                  | Final native abandonment leaves zero owned routes and preserves 14 unrelated routes. Temporary verification preset is removed before handoff.             |

The form uses a disposable native NPC mission, not a persistent Wiki listener. Guide slots retain
their separate native ready handshake; an abandoned slot cannot publish a route. No-match Guide
searches require abandoning the probe in the Log; their detailed status is available in the F7 form.
Guide preset edits are applied on the next launch.

No new flight, warp, or arrival gameplay was performed. The complete generated arrival sequence
matches the retained player-tested control after identifier normalization; that is structural
parity, not a fresh travel test. Native Windows, VR, HDR, other resolutions, multiplayer sessions,
and broad graphics/input-overlay compatibility are not claimed by this host's acceptance.

Desktop capture failures are retained separately as invalid host evidence. Wayland Vulkan
screenshots use the compositor; stale X11 window captures are not input or runtime evidence.
