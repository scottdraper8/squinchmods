# Mission identity and route retention

`observe.py` wraps the existing publisher detour and gameplay navigation check without changing
their behavior. Load its source into one explicit namespace in the existing runtime executor and
call `attach(mod_manager.mods["ResidentSearchProbe"])`. Call `detach` from that same namespace
before ending the control. Do not replace installed source while NMS is running.

The retained investigation is
[`20260914T223411Z-arrival-reuse`](../../../investigation-state/runs/20260914T223411Z-arrival-reuse/analysis.json).
Its bounded hardware watch observes the active scan-event vector count, ignores Wine's normal
SIGUSR1/SIGUSR2 signals, and detaches after publication and removal. Addresses are process-specific;
resolve them from the current scan manager before repeating the watch.

For the pinned executable, the native mission launcher uses `GcSeed(value=0, valid=true)`, a 16-byte
structure with the validity byte at offset 8. An all-zero structure is not that identity. The native
start function compares both fields, whereas the active query treats an invalid seed as a wildcard.
A first launch with an invalid seed can therefore appear successful but create a duplicate after
completion. Cleanup by the duplicate's shared mission context removes its route.

The native restart queue also discards the caller's selection flag. After an exact route is present,
production selects the sole active matching mission through the native selector and verifies the
selected index before acknowledging navigation.
