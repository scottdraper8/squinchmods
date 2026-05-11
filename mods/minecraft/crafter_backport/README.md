# Crafter Backport

Multi-loader (Forge + Fabric) development workspace for the `crafter_backport`
mod on Minecraft 1.20.1.

## Structure

- `common`: Shared gameplay logic, resources, and vanilla-first abstractions.
- `forge`: Forge-specific bootstrap, registrations, and capability adapters.
- `fabric`: Fabric-specific bootstrap, registrations, and entrypoints.

## Useful Commands

### Building

The preferred way to build the mod for all loaders is to use the monorepo
build helper:

```sh
# From the monorepo root
./mods/minecraft/build crafter_backport
```

Alternatively, you can run Gradle directly from this folder:

```sh
./gradlew assemble
```

### Forge Development

- `./gradlew :forge:runClient` - launch the Forge client
- `./gradlew :forge:runServer` - launch the Forge server

### Fabric Development

- `./gradlew :fabric:runClient` - launch the Fabric client
- `./gradlew :fabric:runServer` - launch the Fabric server

### General

- `./gradlew spotlessApply` - format all Java sources
