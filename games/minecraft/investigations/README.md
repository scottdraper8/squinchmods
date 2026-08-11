# Minecraft investigations

This tree contains source-controlled investigation inputs and reusable probe code. Commit the things
needed to reproduce or extend an investigation:

- probe source, Gradle definitions, mixins, and their README instructions;
- canonical fixture inputs and JSON patches; and
- small control-project source/configuration files.

Do not commit execution products or tool caches. Gradle `.gradle/` directories, `build/` outputs,
`run/` directories, logs, classes, and JARs belong in local investigation state. The repository
already ignores `games/minecraft/investigation-state/` for larger generated reports and worlds.

The existing `vanilla-control` tree previously contained historically tracked generated files from
earlier runs. Those products have been removed; the remaining Gradle wrapper is source/configuration
support, while new execution output belongs in ignored investigation state.
