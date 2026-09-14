# NMS client operator helper

`launch-latest-save.py` launches the current host's stopped NMS client and leaves the save menu
ready for operator selection at the current 3840×2160 layout:

```bash
games/no-mans-sky/tooling/client/launch-latest-save.py
```

It requires Python's `evdev` package, `steam`, `xdotool`, and a local graphical login session. If
logind removed the user's `/dev/uinput` ACL after reboot or a virtual-terminal handoff, the helper
reactivates that local seat and verifies write access before creating its controller. On Wayland,
Spectacle is used for focused Vulkan window captures when available; X11 uses ImageMagick's `import`
command.

The helper creates its virtual controller before launching Steam, focuses the NMS window immediately
before every event, dismisses the mod warning, and holds Play. It reports the newest save file as
metadata for operator reference, but does not click a guessed save-menu coordinate. Use
`--save-menu-only` to state the safe stop behavior explicitly, `--interactive` to keep the
controller available for manual selection, and `--screenshot PATH` for an optional checkpoint. A
failure screenshot is written to `/tmp/squinch-nms-launch-failure.png` by default.

For the form itself, use the bounded evdev pointer helper after visually confirming the form window
and target:

```bash
games/no-mans-sky/tooling/client/form-control.py click 6500 1300
```

It accepts only a visible `NMS System Search` window, requires the target to remain inside that
window, checks focus while converging, waits for a stable pointer position, and releases the button
after a bounded click. Use `move` or `scroll` when selection needs separate confirmation.

The route fails closed when NMS is already running, the save profile is ambiguous, or the NMS window
is not 3840×2160. The launcher never emits a guessed save click or the right-stick click bound to
save deletion. After the save menu is ready, use `control-running.py` to reconnect a fresh
controller if NMS stops accepting the original virtual pad after loading.

Use the timing flags only when startup or loading behavior on this host changes. The 50-second
warning delay covers the observed cold-Steam case in which the window exists well before the mod
warning accepts input. The defaults are deliberately conservative and print timestamped JSON events
for diagnosis.

Interactive axis commands accept an optional magnitude between 0 and 1, such as `move_back 0.2 0.5`,
for slower sustained menu movement. Button and keyboard commands accept only the optional duration.
