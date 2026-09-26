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

The helper creates its virtual controller before launching Steam and stops at a startup checkpoint.
It sends no automatic menu input. Use `--interactive` to keep the controller available, inspect a
screenshot, and select only the permitted **Galaxies 1-50** save (`save.hg` or `save2.hg`). Verify
the loaded universe address against that save pair before running probes. Save filenames do not
identify menu rows. Automatic latest-save and named-save loading options are rejected.

`--screenshot PATH` retains the startup checkpoint; a failure screenshot defaults to
`/tmp/squinch-nms-launch-failure.png`.

For the form itself, use the bounded evdev pointer helper after visually confirming the form window
and target:

```bash
games/no-mans-sky/tooling/client/form-control.py click 6500 1300
```

It accepts only a visible `Search Probes` window, requires the target to remain inside that window,
checks focus while converging, waits for a stable pointer position, and releases the button after a
bounded click. Use `move` or `scroll` when selection needs separate confirmation.

The route fails closed when NMS is already running, the save profile is ambiguous, or the NMS window
is not 3840×2160. It never uses the right-stick click bound to save deletion. After the save menu is
ready, use `control-running.py` to reconnect a fresh controller if NMS stops accepting the original
virtual pad after loading.

Use the timing flags only when startup or loading behavior on this host changes. The 50-second
warning delay covers the observed cold-Steam case in which the window exists well before the mod
warning accepts input. The defaults are deliberately conservative and print timestamped JSON events
for diagnosis.

Interactive axis commands accept an optional magnitude between 0 and 1, such as `move_back 0.2 0.5`,
for slower sustained menu movement. Button and keyboard commands accept only the optional duration.
