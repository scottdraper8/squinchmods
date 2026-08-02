# ReTerraForged investigation fixtures

These are executable, source-form RTF datapack inputs. `_base/` is the common exported datapack
content; each semantic fixture declares that base and an optional small overlay in `fixture.toml`.
The materializer overlays files by relative path and writes a sorted, timestamp-normalized ZIP.

Fixture names describe the condition they create. Historical discovery names and ZIP hashes remain
in investigation history only. A run manifest records the fixture metadata, complete resolved
`preset.json`, logical content hash, and generated archive hash.

The three fixtures under `archipelago/` are feature-specific inputs for the active cellular-island
rewrite. They are not a default global matrix.
