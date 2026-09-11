# FreeTerraForged investigation fixtures

Each fixture is a compact, complete FTF preset input: `fixture.toml` carries its semantic purpose
and an exact SHA-256, while the adjacent `preset.json` is the sole generation input. There are no
tracked exported registry trees or prebuilt preset archives.

Before a scenario starts, `mc-investigate` runs the selected FTF worktree's real preset exporter,
validates the resulting dimension, noise, density-function, and registry boundaries, and packages
the generated tree deterministically in ignored `investigation-state` storage. The generator run ID
and hashes are retained with the scenario evidence.

Directories under `generated/` are compact parameterized preset variants, not generated datapack
caches. Fixture names describe the condition they create rather than an incident or historical run.
